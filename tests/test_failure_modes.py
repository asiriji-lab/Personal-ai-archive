"""
Fault-injection tests for the failure-mode VERIFICATION sprint.

These do not fix anything — they PROVE two silent Tier-1 (embed.py) failure
modes from docs/failure-mode-research.md are real and deterministic:

  D1 — Embedding count < chunk count silently drops the trailing chunks, yet the
       file is still recorded in the manifest as fully indexed (embed.py:250-266).
  D2 — A non-UTF-8 (.md) file raises UnicodeDecodeError, which is a ValueError and
       therefore NOT caught by the `except OSError` guard, aborting the whole run
       (embed.py:226-229).

Both tests are hermetic: a temp vault + monkeypatched module globals, no Ollama,
no touching the real data/index.db.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path when running from the tests/ subdirectory
sys.path.insert(0, str(Path(__file__).parent.parent))

import embed
from utils import chunk_text


def _make_temp_vault(tmp_path: Path):
    """Build a minimal vault skeleton and point embed.py's globals at it."""
    vault = tmp_path / "vault"
    resources = vault / "3. Resources"
    resources.mkdir(parents=True)
    data = tmp_path / "data"
    data.mkdir()
    return vault, resources, data


def _patch_embed_paths(monkeypatch, vault, resources, data):
    monkeypatch.setattr(embed, "VAULT_PATH", vault)
    monkeypatch.setattr(embed, "RESOURCES_PATH", resources)
    monkeypatch.setattr(embed, "_SKELETON_DIRS", [resources])
    monkeypatch.setattr(embed, "DB_PATH", data / "index.db")
    monkeypatch.setattr(embed, "MANIFEST_PATH", data / "embed_manifest.json")
    # SCHEMA_PATH stays pointed at the real data/schema.sql (read-only).


# ── D1: silent chunk drop when embeddings are short ───────────────────────────

def test_d1_short_embedding_list_silently_drops_chunks(tmp_path, monkeypatch):
    """
    If get_embeddings returns fewer vectors than chunks, zip() truncates and the
    trailing chunk(s) are never stored — but the file is still marked complete in
    the manifest and NO exception is raised.
    """
    vault, resources, data = _make_temp_vault(tmp_path)
    _patch_embed_paths(monkeypatch, vault, resources, data)

    # Build a doc that produces several chunks (paragraphs > CHUNK_MAX_CHARS total).
    paras = [f"Paragraph {i}. " + ("filler sentence. " * 40) for i in range(6)]
    text = "\n\n".join(paras)
    md = resources / "multi.md"
    md.write_text(text, encoding="utf-8")

    produced = chunk_text(text, embed.CHUNK_MAX_CHARS)
    assert len(produced) >= 3, f"need a multi-chunk doc; got {len(produced)} chunks"

    # Inject the fault: return one FEWER 768-dim vector than there are chunks.
    def fake_get_embeddings(texts):
        n = len(texts) - 1
        return [[0.0] * 768 for _ in range(n)]

    monkeypatch.setattr(embed, "get_embeddings", fake_get_embeddings)

    # Must complete without raising.
    embed.index_resources(reset=True)

    # Stored count is short by exactly the dropped chunk(s).
    conn = sqlite3.connect(str(data / "index.db"))
    stored = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE path = ?", ("3. Resources/multi.md",)
    ).fetchone()[0]
    conn.close()

    assert stored == len(produced) - 1, (
        f"expected silent drop: stored={stored}, produced={len(produced)}"
    )

    # ...yet the manifest records the file as fully indexed (the lie).
    import json
    manifest = json.loads((data / "embed_manifest.json").read_text(encoding="utf-8"))
    assert "3. Resources/multi.md" in manifest, (
        "file marked complete despite dropped chunks — no retry will ever happen"
    )


# ── D2: non-UTF-8 file aborts the entire run ──────────────────────────────────

def test_d2_non_utf8_file_aborts_run_with_unicodedecodeerror(tmp_path, monkeypatch):
    """
    A latin-1/binary .md raises UnicodeDecodeError (a ValueError subclass) on
    read_text(encoding='utf-8'). The surrounding `except OSError` does not catch
    it, so the whole index_resources run aborts with an uncaught traceback.
    """
    vault, resources, data = _make_temp_vault(tmp_path)
    _patch_embed_paths(monkeypatch, vault, resources, data)

    # 0xE9 ('é' in latin-1) followed by a continuation-less byte → invalid UTF-8.
    bad = resources / "latin1.md"
    bad.write_bytes(b"Caf\xe9 notes about agents. " * 5)

    # Guard: confirm it really is invalid UTF-8 (so the test asserts the right cause).
    with pytest.raises(UnicodeDecodeError):
        bad.read_text(encoding="utf-8")

    # The run itself must propagate UnicodeDecodeError (NOT swallowed by except OSError).
    with pytest.raises(UnicodeDecodeError):
        embed.index_resources(reset=True)

    # And it is NOT an OSError, proving the existing guard cannot catch it.
    assert not issubclass(UnicodeDecodeError, OSError)
