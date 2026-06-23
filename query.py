"""
ZeroCostBrain — Hybrid Search (Vector + BM25 + RRF)

Usage:
    python query.py "your question here"
    python query.py          # prompts for input
"""

import re
import sqlite3
import struct
import sys
from collections import defaultdict
from pathlib import Path

import ollama
import sqlite_vec

from config import EMBED_MODEL

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "index.db"
TOPK = 10
CANDIDATE_K = 10  # over-retrieve before RRF, then trim to TOPK

# C6: relevance floor. Off-topic queries otherwise return 10 junk chunks. Calibrated
# on the eval set: negatives top out at RRF ~0.0299, positives floor at ~0.0318.
# If the best fused result is below this, the query has no relevant match.
MIN_RRF_SCORE = 0.0308

_drift_checked = False


def _warn_on_model_drift(conn: sqlite3.Connection) -> None:
    """Warn once if the live embed model digest differs from the one indexed with.

    Query vectors are embedded fresh; if the model changed under the same tag, the
    stored vectors are in a different space and recall silently collapses (B4).
    """
    global _drift_checked
    if _drift_checked:
        return
    _drift_checked = True
    try:
        row = conn.execute("SELECT value FROM index_meta WHERE key = 'embed_model_digest'").fetchone()
    except sqlite3.OperationalError:
        return  # pre-B4 index without index_meta — nothing to compare
    indexed_digest = row[0] if row else ""
    if not indexed_digest:
        return
    from embed import model_digest

    live = model_digest()
    if live and live != indexed_digest:
        print(
            f"WARNING: embed model '{EMBED_MODEL}' digest changed since indexing "
            f"({indexed_digest[:12]}… → {live[:12]}…). Stored vectors are stale — "
            f"re-run `python embed.py --reset` to restore recall.",
            file=sys.stderr,
        )


# ──────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────
def open_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print("ERROR: index.db not found. Run embed.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


# ──────────────────────────────────────────────
# EMBEDDING
# ──────────────────────────────────────────────
def get_query_embedding(query: str) -> bytes:
    try:
        resp = ollama.embed(model=EMBED_MODEL, input=query)
        emb = resp["embeddings"][0]
    except (AttributeError, KeyError):
        resp = ollama.embeddings(model=EMBED_MODEL, prompt=query)
        emb = resp["embedding"]
    return struct.pack(f"{len(emb)}f", *emb)


# ──────────────────────────────────────────────
# VECTOR SEARCH
# ──────────────────────────────────────────────
def vector_search(conn: sqlite3.Connection, query_emb: bytes, k: int = TOPK) -> dict[int, float]:
    rows = conn.execute(
        """
        SELECT rowid, distance
        FROM vec_chunks
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
        """,
        (query_emb, k),
    ).fetchall()

    # Convert distance to a score (lower distance = higher score)
    return {rowid: 1.0 / (1.0 + distance) for rowid, distance in rows}


# ──────────────────────────────────────────────
# BM25 SEARCH (via FTS5 — O(log n) SQL query)
# ──────────────────────────────────────────────
# Common query words that carry no retrieval signal. Quoting + AND-ing these (the
# old behavior) meant a doc had to contain EVERY word, so verbose questions matched
# nothing — BM25 was dead on 19/20 eval queries (C5).
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by", "from",
    "with", "as", "is", "are", "was", "were", "be", "been", "being", "do", "does",
    "did", "what", "how", "why", "when", "where", "which", "who", "whom", "whose",
    "this", "that", "these", "those", "i", "you", "it", "its", "we", "they", "he",
    "she", "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "about", "into", "over", "than", "then", "so", "if", "but", "not", "no", "yes",
}


def _fts5_query(text: str) -> str:
    """Build an FTS5 MATCH expression with OR semantics over significant tokens.

    Drops stopwords (keeping rare/specific terms) and OR-joins the rest so any
    matching term contributes — restoring BM25's rare-term/acronym path. Falls back
    to OR over all tokens when the query is entirely stopwords.
    """
    tokens = re.findall(r"\w+", text.lower())
    significant = [t for t in tokens if t not in _STOPWORDS] or tokens
    return " OR ".join(f'"{t}"' for t in significant)


def bm25_search(conn: sqlite3.Connection, query: str, k: int = TOPK) -> dict[int, float]:
    fts_q = _fts5_query(query)
    if not fts_q:
        return {}

    # bm25() returns negative scores — more negative = better match.
    # We negate so higher score = better, consistent with vector_search.
    rows = conn.execute(
        """
        SELECT rowid, -bm25(chunks_fts) AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY score DESC
        LIMIT ?
        """,
        (fts_q, k),
    ).fetchall()

    return {rowid: score for rowid, score in rows if score > 0}


# ──────────────────────────────────────────────
# RECIPROCAL RANK FUSION
# ──────────────────────────────────────────────
def reciprocal_rank_fusion(
    vector_scores: dict[int, float],
    bm25_scores: dict[int, float],
    k: int = TOPK,
    rrf_k: int = 60,
) -> list[tuple[int, float]]:
    ranks: dict[int, float] = defaultdict(float)

    for rank, (docid, _) in enumerate(sorted(vector_scores.items(), key=lambda x: -x[1])):
        ranks[docid] += 1.0 / (rrf_k + rank + 1)

    for rank, (docid, _) in enumerate(sorted(bm25_scores.items(), key=lambda x: -x[1])):
        ranks[docid] += 1.0 / (rrf_k + rank + 1)

    return sorted(ranks.items(), key=lambda x: -x[1])[:k]


# ──────────────────────────────────────────────
# MAIN SEARCH
# ──────────────────────────────────────────────
def search(query: str, k: int = TOPK) -> list[dict]:
    conn = open_db()
    try:
        _warn_on_model_drift(conn)
        query_emb = get_query_embedding(query)
        vector_scores = vector_search(conn, query_emb, k=CANDIDATE_K)
        bm25_scores = bm25_search(conn, query, k=CANDIDATE_K)
        fused = reciprocal_rank_fusion(vector_scores, bm25_scores, k=k)

        # C6: no result clears the relevance floor → "no relevant results".
        if not fused or fused[0][1] < MIN_RRF_SCORE:
            return []

        results = []
        for docid, rrf_score in fused:
            row = conn.execute(
                "SELECT path, chunk_index, content, title, section FROM chunks WHERE id = ?",
                (docid,),
            ).fetchone()
            if row:
                results.append(
                    {
                        "path": row[0],
                        "chunk_index": row[1],
                        "content": row[2],
                        "title": row[3],
                        "section": row[4],
                        "rrf_score": rrf_score,
                    }
                )

        return results
    finally:
        conn.close()


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip() or input("Query: ").strip()
    if not query:
        print("No query provided.")
        sys.exit(1)

    results = search(query)

    if not results:
        print("No results found.")
    else:
        for i, r in enumerate(results[:5], 1):
            print(f"{i}. {r['path']} (chunk {r['chunk_index']}) — score {r['rrf_score']:.4f}")
            print(f"   {r['content'][:200]}...\n")
