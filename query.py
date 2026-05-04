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
def _fts5_query(text: str) -> str:
    """Sanitize text for FTS5 MATCH. Wraps each word token in quotes."""
    tokens = re.findall(r"\w+", text)
    return " ".join(f'"{t}"' for t in tokens if t)


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
        query_emb = get_query_embedding(query)
        vector_scores = vector_search(conn, query_emb, k=CANDIDATE_K)
        bm25_scores = bm25_search(conn, query, k=CANDIDATE_K)
        fused = reciprocal_rank_fusion(vector_scores, bm25_scores, k=k)

        results = []
        for docid, rrf_score in fused:
            row = conn.execute(
                "SELECT path, chunk_index, content FROM chunks WHERE id = ?",
                (docid,),
            ).fetchone()
            if row:
                results.append(
                    {
                        "path": row[0],
                        "chunk_index": row[1],
                        "content": row[2],
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
