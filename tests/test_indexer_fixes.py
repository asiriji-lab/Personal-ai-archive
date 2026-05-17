"""
Unit tests for the 2026-05 indexer fixes:
  1. _prepend_frontmatter writes a real indexed_at timestamp
  2. Near-empty files (< 200 chars) are skipped without indexing
  3. [PHASE] timing log lines are emitted for Pipeline A and Pipeline B
  4. Pipeline B deletes stale chunks before re-inserting (dedup fix)
  5. get_rag() constructs LightRAG exactly once under concurrent access
"""
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Ensure project root is on sys.path when running from the tests/ subdirectory
sys.path.insert(0, str(Path(__file__).parent.parent))

import index_archive
from index_archive import _index_single_file, _prepend_frontmatter


# ── _prepend_frontmatter ──────────────────────────────────────────────────────

def test_prepend_frontmatter_writes_timestamp(tmp_path):
    md = tmp_path / "note.md"
    md.write_text("# Title\n\nBody text.")
    _prepend_frontmatter(str(md), "general", "A", indexed_at="2026-05-16T10:00:00+00:00")
    text = md.read_text()
    assert text.startswith("---\n")
    assert 'indexed_at: "2026-05-16T10:00:00+00:00"' in text


def test_prepend_frontmatter_default_empty_string(tmp_path):
    """Calling without indexed_at keeps backward-compatible empty string."""
    md = tmp_path / "note.md"
    md.write_text("Body.")
    _prepend_frontmatter(str(md), "general", "A")
    assert 'indexed_at: ""' in md.read_text()


def test_prepend_frontmatter_idempotent(tmp_path):
    """Files that already have frontmatter are not double-prepended."""
    original = "---\ncontent_type: general\n---\n\nBody."
    md = tmp_path / "existing.md"
    md.write_text(original)
    _prepend_frontmatter(str(md), "general", "A", indexed_at="2026-05-16T10:00:00+00:00")
    assert md.read_text() == original  # unchanged


# ── Pre-filter: near-empty files ──────────────────────────────────────────────

def test_short_content_is_skipped(tmp_path):
    """Files with fewer than 200 stripped chars return success without calling rag.ainsert."""
    md = tmp_path / "tiny.md"
    md.write_text("Too short.")  # well under 200 chars

    async def run():
        rag = MagicMock()
        rag.ainsert = AsyncMock()
        success, error, ct, pipeline = await _index_single_file(rag, str(md))
        return success, error, rag.ainsert.called

    success, error, called = asyncio.run(run())
    assert success is True
    assert error == ""
    assert not called, "rag.ainsert must not be called for near-empty files"


def test_short_content_boundary(tmp_path):
    """Content of exactly 200 chars must NOT be skipped."""
    md = tmp_path / "boundary.md"
    md.write_text("x" * 200)

    async def run():
        rag = MagicMock()
        rag.ainsert = AsyncMock()
        with patch("index_archive._prepend_frontmatter"):
            with patch("index_archive._index_pipeline_b", new_callable=AsyncMock) as mock_b:
                success, _, _, _ = await _index_single_file(rag, str(md))
                return success, rag.ainsert.called, mock_b.called

    success, insert_a, insert_b = asyncio.run(run())
    assert success is True
    assert insert_a or insert_b, "Content at 200 chars must proceed to indexing"


def test_short_content_199_chars_skipped(tmp_path):
    """Content of 199 chars is skipped (boundary exclusive)."""
    md = tmp_path / "note.md"
    md.write_text("x" * 199)

    async def run():
        rag = MagicMock()
        rag.ainsert = AsyncMock()
        success, error, _, _ = await _index_single_file(rag, str(md))
        return success, error, rag.ainsert.called

    success, error, called = asyncio.run(run())
    assert success is True
    assert not called


# ── Per-phase timing logs ─────────────────────────────────────────────────────

def test_phase_log_emitted_pipeline_a(tmp_path, caplog):
    """Pipeline A must emit a [PHASE] log line with chunking and kg_insert timings."""
    md = tmp_path / "paper.md"
    md.write_text("# Research Paper\n\n" + "word " * 100)  # > 200 chars, general → A

    async def run():
        rag = MagicMock()
        rag.ainsert = AsyncMock()
        with patch("index_archive._prepend_frontmatter"):
            with caplog.at_level(logging.INFO, logger="index_archive"):
                return await _index_single_file(rag, str(md))

    success, _, _, pipeline = asyncio.run(run())
    assert success is True
    assert pipeline == "A"
    phase_lines = [r.message for r in caplog.records if "[PHASE]" in r.message]
    assert phase_lines, "Expected at least one [PHASE] log line for Pipeline A"
    assert "chunking=" in phase_lines[0]
    assert "kg_insert=" in phase_lines[0]
    assert "pipeline=A" in phase_lines[0]


def test_phase_log_emitted_pipeline_b(tmp_path, caplog):
    """Pipeline B must emit a [PHASE] log line with chunking and embed+insert timings."""
    md = tmp_path / "news.md"
    # Dateline heuristic → news_article → Pipeline B
    md.write_text("Monday, May 12, 2025\nBreaking headline.\n" + "Content word " * 40)

    async def run():
        rag = MagicMock()
        rag.ainsert = AsyncMock()
        with patch("index_archive._prepend_frontmatter"):
            with patch("index_archive._index_pipeline_b", new_callable=AsyncMock):
                with caplog.at_level(logging.INFO, logger="index_archive"):
                    return await _index_single_file(rag, str(md))

    success, _, _, pipeline = asyncio.run(run())
    assert success is True
    assert pipeline == "B"
    phase_lines = [r.message for r in caplog.records if "[PHASE]" in r.message]
    assert phase_lines, "Expected at least one [PHASE] log line for Pipeline B"
    assert "embed+insert=" in phase_lines[0]
    assert "pipeline=B" in phase_lines[0]


# ── Pipeline B: deduplication ─────────────────────────────────────────────────

# Minimal schema without the vec0 virtual table — safe to run without the C extension.
_TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    path        TEXT    NOT NULL,
    chunk_index INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    embedder    TEXT    NOT NULL,
    indexed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vec_chunks (
    rowid   INTEGER PRIMARY KEY,
    embedding BLOB
);
"""


def test_pipeline_b_deletes_stale_rows_on_reindex(tmp_path, monkeypatch):
    """
    Re-indexing a Pipeline-B file must replace old chunk rows, not accumulate them.
    Uses a plain SQLite table for vec_chunks (no vec0 extension needed).
    """
    db_path = tmp_path / "index.db"
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(_TEST_SCHEMA)

    # Seed one stale row for the target path
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_TEST_SCHEMA)
    conn.execute(
        "INSERT INTO chunks(path, chunk_index, content, embedder) VALUES (?,?,?,?)",
        ("notes/article.md", 0, "stale chunk", "nomic-embed-text"),
    )
    old_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO vec_chunks(rowid, embedding) VALUES (?,?)",
        (old_rowid, b"\x00" * (768 * 4)),
    )
    conn.commit()
    conn.close()

    # Redirect DB and schema paths
    monkeypatch.setattr(index_archive, "_DB_PATH", db_path)
    monkeypatch.setattr(index_archive, "_SCHEMA_PATH", schema_path)

    # Mock sqlite_vec module so the C extension is not needed
    fake_sqlite_vec = MagicMock()
    monkeypatch.setitem(sys.modules, "sqlite_vec", fake_sqlite_vec)

    # Mock _local_embed to return dummy vectors
    async def fake_embed(texts):
        return np.zeros((len(texts), 768), dtype=np.float32)

    monkeypatch.setattr(index_archive, "_local_embed", fake_embed)

    async def run():
        from index_archive import _index_pipeline_b
        await _index_pipeline_b(["new chunk 1", "new chunk 2"], "notes/article.md")

    asyncio.run(run())

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT chunk_index, content FROM chunks WHERE path='notes/article.md' ORDER BY chunk_index"
    ).fetchall()
    vec_count = conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0]
    conn.close()

    assert rows == [(0, "new chunk 1"), (1, "new chunk 2")], (
        f"Expected 2 fresh rows only, got: {rows}"
    )
    assert vec_count == 2, f"Expected 2 vec_chunks rows, got {vec_count}"


# ── get_rag() singleton under concurrent access ───────────────────────────────

def test_get_rag_constructs_once_under_concurrency(tmp_path, monkeypatch):
    """
    Three concurrent get_rag() calls must result in exactly one LightRAG construction,
    and all callers must receive the same instance.
    """
    monkeypatch.setattr(index_archive, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(index_archive, "LOCAL_CONTEXT_WINDOW", 4096)

    mock_instance = MagicMock()

    async def run():
        index_archive.reset_rag()
        with patch("index_archive.validate_paths"):
            with patch("index_archive._setup_provider", return_value={
                "func": AsyncMock(),
                "name": "test-model",
                "max_async": 1,
                "kwargs": {},
            }):
                with patch("lightrag.LightRAG", return_value=mock_instance) as MockRAG:
                    results = await asyncio.gather(
                        index_archive.get_rag(),
                        index_archive.get_rag(),
                        index_archive.get_rag(),
                    )
                    call_count = MockRAG.call_count
        index_archive.reset_rag()
        return results, call_count

    results, call_count = asyncio.run(run())

    assert call_count == 1, f"LightRAG must be constructed once, was called {call_count} times"
    assert all(r is mock_instance for r in results), "All callers must receive the same instance"


# ── Auto-prune: no graph file ─────────────────────────────────────────────────

def test_index_archive_survives_missing_graph_file(tmp_path, monkeypatch):
    """
    index_archive() must not crash when the KG graph file does not exist yet.
    This covers the case where all indexed files went to Pipeline B (no LightRAG graph built).
    Previously, prune_graph.load_graph() called sys.exit(1) which escaped the except clause.
    """
    import glob as _glob

    # Seed one small Pipeline-B-routed file (news article → Pipeline B, no graph written)
    archives = tmp_path / "4. Archives"
    archives.mkdir(parents=True)
    news = archives / "news.md"
    news.write_text("Monday, May 12, 2025\nHeadline.\n" + "word " * 60)

    monkeypatch.setattr(index_archive, "ARCHIVE_PATH", archives)
    monkeypatch.setattr(index_archive, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(index_archive, "MANIFEST_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(index_archive, "FAILURES_PATH", tmp_path / "failures.json")

    async def run():
        index_archive.reset_rag()
        with patch("index_archive.get_rag") as mock_rag_fn:
            rag = MagicMock()
            rag.initialize_storages = AsyncMock()
            rag.ainsert = AsyncMock()
            mock_rag_fn.return_value = rag
            with patch("index_archive._local_embed", new=AsyncMock(
                return_value=np.zeros((1, 768), dtype=np.float32)
            )):
                with patch("index_archive._index_pipeline_b", new_callable=AsyncMock):
                    # No graph file exists — pruning must skip silently, not crash
                    await index_archive.index_archive(dry_run=False)
        index_archive.reset_rag()

    # Must not raise SystemExit or any other exception
    asyncio.run(run())
