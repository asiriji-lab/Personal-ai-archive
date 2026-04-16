"""
ZeroCostBrain — SQLite-vec Indexer

Scans markdown files in 3. Resources, chunks them, embeds via Ollama,
and writes to index.db using sqlite-vec for vector search.

Archives are NOT indexed here — they go through LightRAG (index_archive.py).

Uses a file-hash manifest for true incremental indexing:
  - New files are indexed
  - Changed files are re-indexed (old chunks purged, new ones inserted)
  - Deleted files have their chunks purged

Usage:
    python embed.py           # incremental index (new/changed/deleted)
    python embed.py --reset   # drop and rebuild from scratch
"""

import hashlib
import json
import re
import sqlite3
import struct
import argparse
import sys
from pathlib import Path

import ollama
import sqlite_vec

from config import VAULT_PATH, RESOURCES_PATH, EMBED_MODEL, OLLAMA_HOST

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "index.db"
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"
MANIFEST_PATH = PROJECT_ROOT / "data" / "embed_manifest.json"


# ──────────────────────────────────────────────
# MANIFEST (incremental indexing via file hashes)
# ──────────────────────────────────────────────
def _file_hash(filepath: Path) -> str:
    """Fast MD5 hash of file contents."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> dict[str, str]:
    """Load {relative_path: md5_hash} from disk."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print("  WARNING: Corrupt embed manifest — will re-index everything.")
    return {}


def _save_manifest(manifest: dict[str, str]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────
# CHUNKING
# ──────────────────────────────────────────────
def chunk_markdown(text: str, max_words: int = 500) -> list[str]:
    """Split markdown into paragraph-aligned chunks under max_words."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para.split())
        if current_len + para_len > max_words and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ──────────────────────────────────────────────
# EMBEDDING
# ──────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama. Returns a flat list of floats."""
    try:
        # ollama >= 0.2 API
        resp = ollama.embed(model=EMBED_MODEL, input=text)
        return resp["embeddings"][0]
    except (AttributeError, KeyError):
        # ollama < 0.2 fallback
        resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
        return resp["embedding"]


def pack_embedding(emb: list[float]) -> bytes:
    """Pack float list into bytes for sqlite-vec storage."""
    return struct.pack(f"{len(emb)}f", *emb)


# ──────────────────────────────────────────────
# DB SETUP
# ──────────────────────────────────────────────
def open_db(reset: bool = False) -> sqlite3.Connection:
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Dropped existing index: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Load sqlite-vec extension
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # Apply schema
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()

    # One-time FTS5 population for databases that predate the FTS5 migration.
    # The triggers handle new inserts going forward; this covers existing rows.
    fts_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    if fts_count == 0:
        chunks_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if chunks_count > 0:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
            conn.commit()
            print(f"  FTS5: rebuilt index over {chunks_count} existing chunks.")

    return conn


# ──────────────────────────────────────────────
# CHUNK PURGE
# ──────────────────────────────────────────────
def _purge_chunks(conn: sqlite3.Connection, rel_path: str) -> int:
    """Delete all chunks (and their vec_chunks rows) for a given path. Returns count deleted."""
    row_ids = [
        r[0] for r in conn.execute("SELECT id FROM chunks WHERE path = ?", (rel_path,))
    ]
    if not row_ids:
        return 0
    placeholders = ",".join("?" * len(row_ids))
    conn.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})", row_ids)
    conn.execute("DELETE FROM chunks WHERE path = ?", (rel_path,))
    return len(row_ids)


# ──────────────────────────────────────────────
# INDEXER
# ──────────────────────────────────────────────
def index_resources(reset: bool = False) -> None:
    if not RESOURCES_PATH.exists():
        print(f"ERROR: Resources folder not found at {RESOURCES_PATH}", file=sys.stderr)
        sys.exit(1)

    if reset:
        # Clear manifest alongside the DB so we start clean
        if MANIFEST_PATH.exists():
            MANIFEST_PATH.unlink()
            print(f"Cleared embed manifest: {MANIFEST_PATH}")

    conn = open_db(reset=reset)
    manifest = {} if reset else _load_manifest()

    # Scan current files in Resources
    md_files = sorted(RESOURCES_PATH.rglob("*.md"))
    current_files: dict[str, str] = {}  # rel_path -> hash
    for f in md_files:
        rel = f.relative_to(VAULT_PATH).as_posix()
        current_files[rel] = _file_hash(f)

    # Classify: new, changed, deleted
    manifest_paths = set(manifest.keys())
    current_paths = set(current_files.keys())

    new_paths = current_paths - manifest_paths
    deleted_paths = manifest_paths - current_paths
    changed_paths = {
        p for p in (current_paths & manifest_paths)
        if current_files[p] != manifest[p]
    }

    print(f"Resources: {RESOURCES_PATH}")
    print(f"Total .md files : {len(current_files)}")
    print(f"New             : {len(new_paths)}")
    print(f"Changed         : {len(changed_paths)}")
    print(f"Deleted         : {len(deleted_paths)}")
    print(f"Unchanged       : {len(current_paths - new_paths - changed_paths)}")

    if not new_paths and not changed_paths and not deleted_paths:
        print("Nothing to do — index is up to date.")
        conn.close()
        return

    # 1. Purge deleted files
    for rel_path in sorted(deleted_paths):
        n = _purge_chunks(conn, rel_path)
        del manifest[rel_path]
        print(f"  Purged: {rel_path} ({n} chunks)")

    # 2. Re-index changed files (purge old, insert new)
    for rel_path in sorted(changed_paths):
        n = _purge_chunks(conn, rel_path)
        print(f"  Purged (changed): {rel_path} ({n} chunks)")

    conn.commit()

    # 3. Index new + changed files
    to_index = sorted(new_paths | changed_paths)
    total_chunks = 0

    for rel_path in to_index:
        abs_path = VAULT_PATH / rel_path

        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"  SKIP (read error): {rel_path} — {e}")
            continue

        if len(text.strip()) < 10:
            print(f"  SKIP (empty): {rel_path}")
            manifest[rel_path] = current_files[rel_path]
            _save_manifest(manifest)
            continue

        chunks = chunk_markdown(text)
        embed_ok = True
        stored_count = 0

        for idx, chunk in enumerate(chunks):
            try:
                emb = get_embedding(chunk)
            except Exception as e:
                print(f"  EMBED ERROR chunk {idx} of {rel_path}: {e}", file=sys.stderr)
                embed_ok = False
                continue

            cur = conn.execute(
                "INSERT INTO chunks (path, chunk_index, content, embedder) VALUES (?, ?, ?, ?)",
                (rel_path, idx, chunk, EMBED_MODEL),
            )
            chunk_id = cur.lastrowid

            conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (chunk_id, pack_embedding(emb)),
            )
            stored_count += 1

        conn.commit()

        if embed_ok:
            manifest[rel_path] = current_files[rel_path]
            _save_manifest(manifest)

        total_chunks += stored_count
        label = "Re-indexed" if rel_path in changed_paths else "Indexed"
        print(f"  {label}: {rel_path} ({len(chunks)} chunks)")

    # 4. Save final manifest (covers deletions)
    _save_manifest(manifest)

    conn.close()
    print(
        f"\nDone. {len(to_index)} indexed, {len(deleted_paths)} purged, "
        f"{total_chunks} total chunks → {DB_PATH}"
    )


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index Resources into sqlite-vec.")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild index from scratch.")
    args = parser.parse_args()

    index_resources(reset=args.reset)
