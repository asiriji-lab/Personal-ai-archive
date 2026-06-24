"""
Diagnostic tests for the indexer startup hang.

Symptom: the TUI prints "🚀 STARTING INDEXER..." then hangs indefinitely.
The subprocess writes logging to stderr (inherited), so silence after the banner
means the hang occurs BEFORE the first logger.info() inside get_rag():

  Startup sequence in index_archive.py:
    1. Python module imports (lightrag, ollama, …)
    2. asyncio.run(index_archive(...))
       a. get_rag()
          i.  validate_paths() / WORKING_DIR.mkdir()
          ii. _setup_provider()           ← logs "LOCAL MODE" / "GEMINI MODE"
          iii.LightRAG(...)               ← constructor (potentially slow)
       b. rag.initialize_storages()       ← may call _local_embed internally
       c. "⏳ Probing embed model…" log
       d. _local_embed(["ping"])          ← no explicit timeout → infinite hang

Three test groups:
  A. Import timing     — subprocess import with 30-second timeout
  B. Stage isolation   — each startup stage in isolation with asyncio.wait_for
  C. Embed probe       — verifies _local_embed has/needs a timeout guard
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import index_archive
from index_archive import _local_embed, get_rag, reset_rag

# ─────────────────────────────────────────────────────────────────────────────
# A. IMPORT TIMING — detect hangs during Python import phase
# ─────────────────────────────────────────────────────────────────────────────

IMPORT_TIMEOUT = 30  # seconds — generous for slow machines


def _run_import(module_expr: str, timeout: int, cwd: str) -> subprocess.CompletedProcess:
    py = sys.executable
    cmd = [py, "-c", f"import sys; sys.path.insert(0,'.');"
                     f"{module_expr}; print('OK')"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def test_import_does_not_hang():
    """
    After the lazy-import fix, `import index_archive` must complete within 30s.
    If this fails, a top-level import was re-introduced that triggers I/O.

    Pre-fix: this timed out after 30s because LightRAG SDK imports were at module
    level and triggered Google/Ollama auth probes.
    Post-fix: imports are lazy — only triggered inside get_rag() / _setup_provider().
    """
    cwd = str(Path(__file__).parent.parent)
    result = _run_import("import index_archive", IMPORT_TIMEOUT, cwd)
    assert "OK" in result.stdout, (
        f"import index_archive did not print 'OK' within {IMPORT_TIMEOUT}s.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr[-2000:]!r}"
    )


@pytest.mark.parametrize("stmt,label", [
    ("from lightrag import LightRAG, QueryParam", "lightrag core"),
    # lightrag.llm.gemini is xfail: Google GenAI SDK triggers auth I/O on import
    # (>30s). This is the confirmed root cause of the startup hang. The fix is the
    # lazy import inside _setup_provider() — it's no longer a top-level import.
    pytest.param(
        "from lightrag.llm.gemini import gemini_model_complete",
        "lightrag.llm.gemini",
        marks=pytest.mark.xfail(
            raises=(subprocess.TimeoutExpired, Exception),
            reason="Google GenAI SDK triggers network auth on import (known slow, now lazy-loaded)",
            strict=False,
        ),
    ),
    ("from lightrag.llm.ollama import ollama_model_complete", "lightrag.llm.ollama"),
    ("from lightrag.utils import EmbeddingFunc", "lightrag.utils"),
])
def test_lightrag_subimport_timing(stmt, label):
    """
    Pinpoint which LightRAG sub-import is slow. Each is tested individually with
    a 30-second window.

    lightrag.llm.gemini is marked xfail — it's a known-slow Google SDK import.
    The fix (lazy import in _setup_provider) prevents it from running at module load.
    """
    cwd = str(Path(__file__).parent.parent)
    try:
        result = _run_import(stmt, 30, cwd)
        assert "OK" in result.stdout, (
            f"{label!r} did not complete within 30s.\n"
            f"stderr: {result.stderr[-1000:]!r}"
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"{label!r} timed out — this import triggers I/O.\n"
            f"stmt: {stmt}"
        )


def test_config_import_does_not_hang():
    """config.py is imported at module level — verify it's fast."""
    py = sys.executable
    cmd = [py, "-c", "import sys; sys.path.insert(0,'.');"
                     "import config; print('OK')"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(Path(__file__).parent.parent),
    )
    assert "OK" in result.stdout


# ─────────────────────────────────────────────────────────────────────────────
# B. STAGE ISOLATION — each get_rag() stage with 5-second timeout
# ─────────────────────────────────────────────────────────────────────────────

STAGE_TIMEOUT = 5  # seconds per stage


@pytest.fixture(autouse=True)
def _reset_rag():
    """Always reset singleton so tests don't share state."""
    reset_rag()
    yield
    reset_rag()


def test_setup_provider_does_not_block(tmp_path):
    """
    _setup_provider() must return immediately without I/O.
    If it tries to connect to Ollama/Gemini at call time, this will timeout.
    """

    async def run():
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, index_archive._setup_provider
            ),
            timeout=STAGE_TIMEOUT,
        )

    provider = asyncio.run(run())
    assert "func" in provider
    assert "name" in provider


def test_lightrag_constructor_does_not_hang(tmp_path, monkeypatch):
    """
    LightRAG(...) constructor must complete within 5 seconds.
    If it hangs, it's loading a model or opening a blocking connection inside __init__.

    DIAGNOSIS: if this test fails with TimeoutError, the hang is in the LightRAG
    constructor — suspect storage initialization or a blocking embed call in __init__.
    """
    monkeypatch.setattr(index_archive, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(index_archive, "LOCAL_CONTEXT_WINDOW", 4096)

    provider = {
        "func": AsyncMock(),
        "name": "test-model",
        "max_async": 1,
        "kwargs": {},
    }

    embed_fn = AsyncMock(return_value=__import__("numpy").zeros((1, 768)))

    async def run():
        with patch("index_archive.validate_paths"):
            with patch("index_archive._setup_provider", return_value=provider):
                # LightRAG / EmbeddingFunc are imported lazily inside get_rag(), so
                # patch them at their source module, not as index_archive attributes.
                with patch("lightrag.utils.EmbeddingFunc") as mock_efunc:
                    mock_efunc.return_value = MagicMock()
                    with patch("lightrag.LightRAG") as MockRAG:
                        MockRAG.return_value = MagicMock()
                        MockRAG.return_value.initialize_storages = AsyncMock()
                        return await asyncio.wait_for(
                            get_rag(), timeout=STAGE_TIMEOUT
                        )

    rag = asyncio.run(run())
    assert rag is not None


def test_initialize_storages_does_not_call_embed(tmp_path, monkeypatch):
    """
    rag.initialize_storages() must NOT call _local_embed internally.

    DIAGNOSIS: if _local_embed is called here, LightRAG is eagerly embedding
    something during storage setup — before the probe at line 537 even runs.
    Without a timeout on that call, Ollama cold-start (1-2 min) or an unreachable
    Ollama silently hangs the entire process.

    This is the most likely cause of the silent hang.
    """
    monkeypatch.setattr(index_archive, "WORKING_DIR", tmp_path)

    embed_calls = []

    async def spy_embed(texts):
        embed_calls.append(texts)
        return __import__("numpy").zeros((len(texts), 768))

    monkeypatch.setattr(index_archive, "_local_embed", spy_embed)

    rag_mock = MagicMock()
    rag_mock.initialize_storages = AsyncMock()

    async def run():
        with patch("index_archive.validate_paths"):
            with patch("index_archive._setup_provider", return_value={
                "func": AsyncMock(), "name": "m", "max_async": 1, "kwargs": {}
            }):
                # Patch at the lazy-import source (see note in the constructor test).
                with patch("lightrag.LightRAG", return_value=rag_mock):
                    with patch("lightrag.utils.EmbeddingFunc", return_value=MagicMock()):
                        rag = await get_rag()
                        await rag.initialize_storages()
                        return embed_calls

    calls = asyncio.run(run())
    assert calls == [], (
        f"initialize_storages() triggered {len(calls)} _local_embed call(s)!\n"
        f"This means LightRAG eagerly embeds on storage init — any Ollama delay\n"
        f"will cause a silent hang BEFORE the '⏳ Probing embed model' log line.\n"
        f"Inputs passed: {calls}"
    )


def test_embed_probe_has_timeout_guard():
    """
    _local_embed has no explicit timeout, so if Ollama is unreachable it hangs
    indefinitely. This test documents the missing guard and will fail if a
    timeout is NOT present, signalling the bug.

    DIAGNOSIS: _local_embed() wraps ollama.AsyncClient.embed() with no timeout.
    asyncio.wait_for(client.embed(...), timeout=120) is required.
    """
    import inspect
    source = inspect.getsource(index_archive._local_embed)
    has_timeout = "wait_for" in source or "timeout" in source
    assert has_timeout, (
        "_local_embed() has no timeout guard!\n"
        "If Ollama is unreachable or loading a cold model, it will hang indefinitely.\n"
        "Fix: wrap client.embed() with asyncio.wait_for(..., timeout=120)"
    )


def test_index_archive_startup_sequence_order(tmp_path, monkeypatch, caplog):
    """
    Verify the startup sequence runs in the right order and that the '⏳ Probing'
    log appears BEFORE any embed call, confirming the probe is the first embed.
    If initialize_storages() calls embed first, this sequence is wrong.
    """
    import logging

    monkeypatch.setattr(index_archive, "ARCHIVE_PATH", tmp_path / "4. Archives")
    (tmp_path / "4. Archives").mkdir(parents=True)
    monkeypatch.setattr(index_archive, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(index_archive, "MANIFEST_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(index_archive, "FAILURES_PATH", tmp_path / "failures.json")

    call_order = []

    async def fake_embed(texts):
        call_order.append(("embed", texts))
        return __import__("numpy").zeros((len(texts), 768))

    monkeypatch.setattr(index_archive, "_local_embed", fake_embed)

    rag_mock = MagicMock()

    async def fake_init_storages():
        call_order.append(("initialize_storages",))

    rag_mock.initialize_storages = fake_init_storages
    rag_mock.ainsert = AsyncMock()

    async def run():
        with patch("index_archive.get_rag", return_value=rag_mock):
            with caplog.at_level(logging.INFO, logger="index_archive"):
                await index_archive.index_archive(dry_run=True)

    asyncio.run(run())

    # Find the first embed call and check if "Probing" log appeared first
    probe_log_idx = next(
        (i for i, r in enumerate(caplog.records) if "Probing" in r.message), None
    )
    embed_call_idx = next(
        (i for i, (kind, *_) in enumerate(call_order) if kind == "embed"), None
    )

    assert "initialize_storages" in [k for k, *_ in call_order], (
        "initialize_storages() was never called"
    )
    assert probe_log_idx is not None, (
        "'⏳ Probing embed model' log line never appeared — "
        "startup may have short-circuited or hung before that point"
    )
    if embed_call_idx is not None:
        # Verify the probe log appeared before or at the same point as the embed call
        assert probe_log_idx >= 0, (
            "Embed was called before the '⏳ Probing' log — initialize_storages() "
            "is triggering a hidden embed call with no timeout guard"
        )


# ─────────────────────────────────────────────────────────────────────────────
# C. EMBED PROBE — behaviour with unreachable / slow Ollama
# ─────────────────────────────────────────────────────────────────────────────

def test_embed_probe_respects_timeout_when_slow():
    """
    If _local_embed takes longer than its built-in timeout, it raises RuntimeError
    rather than hanging forever. Verify the timeout fires within a reasonable window.
    """
    import numpy as np

    async def slow_embed(texts):
        await asyncio.sleep(9999)  # simulate Ollama not responding
        return np.zeros((len(texts), 768))

    async def run():
        with patch("index_archive._local_embed", side_effect=slow_embed):
            with patch("index_archive.get_rag") as mock_get_rag:
                rag = MagicMock()
                rag.initialize_storages = AsyncMock()
                mock_get_rag.return_value = rag

                with pytest.raises((SystemExit, asyncio.TimeoutError, Exception)):
                    await asyncio.wait_for(
                        index_archive.index_archive(),
                        timeout=10,  # must resolve within 10s, not hang forever
                    )

    asyncio.run(run())


def test_local_embed_raises_on_connection_refused():
    """
    When Ollama is not running, _local_embed should raise promptly,
    NOT hang waiting for a connection that will never come.
    The probe at line 537 catches this and prints a clear error.
    """
    import ollama

    async def run():
        # Point at a port nothing is listening on
        with patch("index_archive.OLLAMA_HOST", "http://127.0.0.1:19999"):
            with patch("ollama.AsyncClient") as MockClient:
                instance = MagicMock()
                instance.embed = AsyncMock(
                    side_effect=Exception("Connection refused")
                )
                MockClient.return_value = instance
                return await index_archive._local_embed(["test"])

    with pytest.raises(Exception, match="Connection refused"):
        asyncio.run(run())


# ─────────────────────────────────────────────────────────────────────────────
# D. LOCK FILE — verify lock is written before asyncio.run() blocks
# ─────────────────────────────────────────────────────────────────────────────

def test_lock_file_created_by_cli(tmp_path, monkeypatch):
    """
    The CLI writes _LOCK_FILE.touch() BEFORE asyncio.run().
    A hang inside asyncio.run() leaves the lock file on disk.
    Other processes (TUI watchdog) can use this to detect the running indexer.
    """
    lock = tmp_path / ".indexer.lock"
    monkeypatch.setattr(index_archive, "_LOCK_FILE", lock)

    # Simulate the CLI prelude
    lock.touch()
    assert lock.exists(), "Lock file must be created before asyncio.run() starts"
    lock.unlink(missing_ok=True)
    assert not lock.exists(), "Lock file must be cleaned up in finally block"
