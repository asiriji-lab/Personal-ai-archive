"""
🧠 ZeroCostBrain — Archive Indexer (The Learner)

Scans the Archives folder and builds/updates the LightRAG Knowledge Graph.

Features:
  - Incremental indexing via file-hash manifest (skips unchanged files)
  - Large-document chunking for VRAM-safe processing
  - Hybrid LLM support (Local Ollama or Gemini Cloud)
"""

import asyncio
import glob
import hashlib
import json
import logging
import shutil
import sys
import time
from pathlib import Path

from lightrag import LightRAG, QueryParam
from lightrag.llm.gemini import gemini_model_complete
from lightrag.llm.ollama import ollama_model_complete
from lightrag.utils import EmbeddingFunc

from config import (
    ARCHIVE_PATH,
    CHUNK_MAX_CHARS,
    EMBED_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    INDEX_FAILURES_FILE,
    INDEX_MANIFEST_FILE,
    INDEX_MAX_RETRIES,
    INDEX_RETRY_BACKOFF,
    LLM_PROVIDER,
    LOCAL_CONTEXT_WINDOW,
    LOCAL_LLM_MODEL,
    OLLAMA_HOST,
    WORKING_DIR,
    validate_paths,
)
from utils import chunk_text, file_hash, setup_logging

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# MANIFEST (incremental indexing)
# ──────────────────────────────────────────────
MANIFEST_PATH = WORKING_DIR / INDEX_MANIFEST_FILE
FAILURES_PATH = WORKING_DIR / INDEX_FAILURES_FILE


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("⚠️ Corrupt manifest — will re-index everything.")
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_failures() -> dict:
    """Load the failure log for previously failed files."""
    if FAILURES_PATH.exists():
        try:
            return json.loads(FAILURES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_failures(failures: dict) -> None:
    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAILURES_PATH.write_text(
        json.dumps(failures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────
# PROVIDER SETUP
# ──────────────────────────────────────────────
import functools


def _make_timed_llm(func):
    """Wrap an LLM function to log duration and output size after every call."""

    @functools.wraps(func)
    async def timed(*args, **kwargs):
        t0 = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        out_tokens = len(result) // 4 if isinstance(result, str) else "?"
        flag = " <<< SLOW" if elapsed > 180 else ""
        logger.info(f"LLM call finished: {elapsed:.1f}s | ~{out_tokens} output tokens{flag}")
        return result

    return timed


def _setup_provider():
    """Configure LLM function and kwargs based on the chosen provider."""
    if LLM_PROVIDER == "GEMINI":
        if not GEMINI_API_KEY or "PASTE_YOUR_KEY" in GEMINI_API_KEY:
            logger.error("❌ No Gemini API key found in environment!")
            logger.error("Set GOOGLE_API_KEY in your .env file.")
            sys.exit(1)
        logger.info("🌍 HYBRID MODE: Gemini Cloud (Thinking) + RTX 4050 (Embedding)")
        logger.info(f"🔑 API Key: {GEMINI_API_KEY[:4]}...{GEMINI_API_KEY[-4:]}")
        return {
            "func": gemini_model_complete,
            "name": GEMINI_MODEL,
            "max_async": 10,
            "kwargs": {"api_key": GEMINI_API_KEY},
        }
    else:
        logger.info("🏠 LOCAL MODE: Full Ollama stack.")
        return {
            "func": _make_timed_llm(ollama_model_complete),
            "name": LOCAL_LLM_MODEL,
            "max_async": 1,
            "kwargs": {"host": OLLAMA_HOST, "think": False, "options": {"num_ctx": LOCAL_CONTEXT_WINDOW}},
        }


# ──────────────────────────────────────────────
# LOCAL EMBEDDING (always Ollama)
# ──────────────────────────────────────────────
async def _local_embed(texts):
    import numpy as np
    import ollama

    client = ollama.AsyncClient(host=OLLAMA_HOST)
    data = await client.embed(model=EMBED_MODEL, input=texts)
    return np.array(data["embeddings"])


# ──────────────────────────────────────────────
# RAG FACTORY (lazy initialization)
# ──────────────────────────────────────────────
_rag_instance = None
_rag_lock = asyncio.Lock()


def reset_rag():
    global _rag_instance
    _rag_instance = None


async def get_rag() -> LightRAG:
    """
    Create or return the singleton LightRAG instance.
    Lazy-loaded so imports don't trigger side effects.
    """
    global _rag_instance

    async with _rag_lock:
        if _rag_instance is not None:
            return _rag_instance

        validate_paths()
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        provider = _setup_provider()

    try:
        logger.info(f"Using model: {provider['name']} | num_ctx: {LOCAL_CONTEXT_WINDOW}")
        _rag_instance = LightRAG(
            working_dir=str(WORKING_DIR),
            llm_model_func=provider["func"],
            llm_model_name=provider["name"],
            llm_model_max_async=provider["max_async"],
            max_total_tokens=LOCAL_CONTEXT_WINDOW,
            llm_model_kwargs=provider["kwargs"],
            # Disable gleaning — second-pass extraction doubles LLM calls with minimal gain
            # for a small model like Qwen 3.5 4B. Re-enable if extraction quality is poor.
            entity_extract_max_gleaning=0,
            # VRAM-safe settings for RTX 4050 (6GB)
            summary_context_size=min(6000, LOCAL_CONTEXT_WINDOW),
            default_embedding_timeout=120,
            embedding_func=EmbeddingFunc(
                embedding_dim=768,
                max_token_size=8192,
                func=_local_embed,
            ),
        )
    except Exception as e:
        logger.error(f"❌ RAG INIT FAILED: {e}")
        sys.exit(1)

    return _rag_instance


# ──────────────────────────────────────────────
# SINGLE FILE INDEXER (with retry)
# ──────────────────────────────────────────────
async def index_single_file(file_path: Path) -> None:
    """
    Public API: index one file into LightRAG, update manifest and failure log.
    Raises RuntimeError on failure after all retries.
    Called by validate_and_archive.py; the existing CLI uses the batch indexer below.
    """
    rag = await get_rag()
    try:
        await rag.initialize_storages()
    except ConnectionError as e:
        raise RuntimeError(f"Cannot connect to Ollama: {e}")

    fp = str(file_path)
    fh = file_hash(fp)

    manifest = _load_manifest()
    failures = _load_failures()

    success, error_msg = await _index_single_file(rag, fp)

    if success:
        manifest[fp] = fh
        _save_manifest(manifest)
        if fp in failures:
            del failures[fp]
            _save_failures(failures)
        logger.info(f"✅ Indexed: {file_path.name}")
    else:
        failures[fp] = {
            "error": error_msg,
            "attempts": INDEX_MAX_RETRIES,
            "last_attempt": str(file_path.stat().st_mtime),
        }
        _save_failures(failures)
        raise RuntimeError(f"Failed to index {file_path.name}: {error_msg}")


async def _index_single_file(rag, file_path: str, max_retries: int = INDEX_MAX_RETRIES) -> tuple[bool, str]:
    """
    Index a single file with retry logic.
    Returns (success: bool, error_msg: str).
    """
    backoff = INDEX_RETRY_BACKOFF

    for attempt in range(max_retries):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if len(content.strip()) < 5:
                return True, ""  # Skip tiny files, not an error

            chunks = chunk_text(content, max_chars=CHUNK_MAX_CHARS)
            for chunk in chunks:
                await rag.ainsert(chunk)

            return True, ""

        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                wait = backoff[min(attempt, len(backoff) - 1)]
                logger.warning(
                    f"⚠️ Attempt {attempt + 1}/{max_retries} failed for "
                    f"{Path(file_path).name}: {error_msg}. Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)
            else:
                logger.error(f"❌ All {max_retries} attempts failed for {Path(file_path).name}: {error_msg}")
                return False, error_msg

    return False, "Unknown error"


# ──────────────────────────────────────────────
# INDEXER
# ──────────────────────────────────────────────
async def index_archive(force_reset: bool = False, retry_failed: bool = False) -> None:
    """
    Index markdown files from the Archives folder into LightRAG.

    Args:
        force_reset: If True, wipes WORKING_DIR and re-indexes everything from scratch.
        retry_failed: If True, only retry previously failed files.
    """
    from tqdm import tqdm

    if force_reset:
        logger.info("🔄 FORCE RESET: Wiping WORKING_DIR and re-indexing all files from scratch.")
        if WORKING_DIR.exists():
            for item in WORKING_DIR.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.info(f"  Cleared: {WORKING_DIR}")
        # Force get_rag() to build a fresh instance against the empty directory
        reset_rag()

    rag = await get_rag()
    try:
        await rag.initialize_storages()
    except ConnectionError as e:
        logger.error(f"❌ Cannot connect to Ollama at {OLLAMA_HOST}: {e}")
        logger.error("Make sure Ollama is running: `ollama serve`")
        sys.exit(1)

    manifest = {} if force_reset else _load_manifest()
    failures = {} if force_reset else _load_failures()

    if retry_failed:
        # Only process files that previously failed
        pending = []
        for fp, info in failures.items():
            if Path(fp).exists():
                pending.append((fp, file_hash(fp)))
        logger.info(f"🔁 Retrying {len(pending)} previously failed files.")
    else:
        all_files = glob.glob(str(ARCHIVE_PATH / "**" / "*.md"), recursive=True)

        # Determine which files are new or changed
        pending = []
        for fp in all_files:
            fh = file_hash(fp)
            if manifest.get(fp) != fh:
                pending.append((fp, fh))

        logger.info(
            f"📊 {len(all_files)} total files | {len(pending)} new/changed | {len(all_files) - len(pending)} skipped"
        )

    if not pending:
        logger.info("✅ Brain is already up-to-date. Nothing to index.")
        return

    success_count = 0
    error_count = 0

    for file_path, fh in tqdm(pending, desc="🧠 Indexing"):
        success, error_msg = await _index_single_file(rag, file_path)

        if success:
            # Mark as successfully indexed and save immediately
            manifest[file_path] = fh
            _save_manifest(manifest)

            # Remove from failures if it was there
            if file_path in failures:
                del failures[file_path]

            success_count += 1
        else:
            # Record failure with details
            failures[file_path] = {
                "error": error_msg,
                "attempts": INDEX_MAX_RETRIES,
                "last_attempt": str(Path(file_path).stat().st_mtime),
            }
            error_count += 1

    # Save failure log
    _save_failures(failures)

    logger.info(f"\n✅ DONE: {success_count} indexed, {error_count} errors, via {LLM_PROVIDER} mode.")
    if error_count > 0:
        logger.info(f"💡 {error_count} files failed. Run `python index_archive.py --retry-failed` to retry them.")


# ──────────────────────────────────────────────
# QUERY
# ──────────────────────────────────────────────
async def query_archive(query: str) -> str:
    """Run a hybrid RAG query against the knowledge graph."""
    rag = await get_rag()
    return await rag.aquery(query, param=QueryParam(mode="hybrid"))


# Deprecated alias — will be removed in a future version
test_query = query_archive


# ──────────────────────────────────────────────
# CLI ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index archive documents into the Brain.")
    parser.add_argument("--reset", action="store_true", help="Force re-index all files.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry only previously failed files.")
    parser.add_argument(
        "--provider",
        choices=["local", "gemini"],
        help="Override LLM provider (default: from config/env).",
    )
    args = parser.parse_args()

    if args.provider:
        import config as _cfg

        _cfg.LLM_PROVIDER = args.provider.upper()
        logger.info(f"Provider overridden via CLI: {_cfg.LLM_PROVIDER}")

    asyncio.run(index_archive(force_reset=args.reset, retry_failed=args.retry_failed))
