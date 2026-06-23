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
import json
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path

# LightRAG and its LLM adapters are imported lazily inside get_rag() /
# _setup_provider() / query_archive() so that `import index_archive` itself
# is fast. Importing LightRAG at module level triggers Google/Ollama SDK
# initialisation (auth probes, DNS lookups) that can block for minutes and
# cause the indexer subprocess to appear hung before any log line appears.

import re
from datetime import datetime, timezone
from typing import Literal

from config import (
    ARCHIVE_PATH,
    CHUNK_B_MAX_CHARS,
    CHUNK_MAX_CHARS,
    CHUNK_SECTION_MAX_CHARS,
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
    LOCAL_NUM_GPU,
    OLLAMA_HOST,
    VAULT_PATH,
    WORKING_DIR,
    validate_paths,
)

from utils import chunk_text, chunk_text_sections, file_hash, setup_logging

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
            raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            # Backward compat: old format stores plain hash strings as values
            if raw and isinstance(next(iter(raw.values())), str):
                return {
                    k: {"hash": v, "content_type": "general", "pipeline": "A", "indexed_at": ""}
                    for k, v in raw.items()
                }
            return raw
        except (json.JSONDecodeError, OSError):
            logger.warning("⚠️ Corrupt manifest — will re-index everything.")
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(MANIFEST_PATH)


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
    tmp = FAILURES_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(failures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(FAILURES_PATH)


# ──────────────────────────────────────────────
# CONTENT CLASSIFIER & PIPELINE ROUTER
# ──────────────────────────────────────────────
_VALID_CONTENT_TYPES = {
    "research_paper", "news_article", "personal_note",
    "validated_artifact", "meeting_note", "general",
}
_DATELINE_RE = re.compile(r"^\w+,\s+\w+\s+\d{1,2},\s+\d{4}", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n(.+?)\n---", re.DOTALL)


def _classify_content_type(path: Path, content: str) -> str:
    """
    Rule-based classifier. Checks existing frontmatter first, then path patterns,
    then content heuristics. Rules evaluated in order; first match wins.
    """
    m = _FRONTMATTER_RE.match(content)
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("content_type:"):
                ct = line.split(":", 1)[1].strip()
                if ct in _VALID_CONTENT_TYPES:
                    return ct

    path_str = str(path).replace("\\", "/")
    if "autoresearchlaw/artifacts/" in path_str:
        return "research_paper"
    if "fetch_papers/" in path_str:
        return "research_paper"
    if "news_ingest/" in path_str:
        return "news_article"
    if "validate_and_archive/" in path_str:
        return "validated_artifact"

    first_lines = "\n".join(content.splitlines()[:3])
    if _DATELINE_RE.search(first_lines):
        return "news_article"
    if len(content.strip()) < 500:
        return "personal_note"

    return "general"


def _select_pipeline(content_type: str) -> Literal["A", "B"]:
    """Map content_type to pipeline letter. B = fast/cheap; A = deep/LightRAG."""
    return "B" if content_type in {"news_article", "meeting_note", "personal_note"} else "A"


def _prepend_frontmatter(file_path: str, content_type: str, pipeline: str, indexed_at: str = "") -> None:
    """Prepend YAML frontmatter block only when the file does not already have one."""
    if Path(file_path).suffix.lower() not in _INDEXABLE_EXTENSIONS:
        return
    text = Path(file_path).read_text(encoding="utf-8")
    if text.startswith("---"):
        return
    source_map = {
        "research_paper": "fetch_papers",
        "news_article": "news_ingest",
        "validated_artifact": "validate_and_archive",
    }
    source = source_map.get(content_type, "manual")
    frontmatter = (
        f'---\ncontent_type: {content_type}\nsource: {source}\n'
        f'indexed_at: "{indexed_at}"\npipeline: {pipeline}\n---\n\n'
    )
    Path(file_path).write_text(frontmatter + text, encoding="utf-8")


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
    import config as _cfg
    if _cfg.LLM_PROVIDER == "GEMINI":
        from lightrag.llm.gemini import gemini_model_complete  # lazy — avoids Google SDK auth on import
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
        from lightrag.llm.ollama import ollama_model_complete  # lazy — avoids Ollama DNS probe on import
        options = {"num_ctx": LOCAL_CONTEXT_WINDOW}
        if LOCAL_NUM_GPU >= 0:
            options["num_gpu"] = LOCAL_NUM_GPU

        logger.info(f"🏠 LOCAL MODE: Full Ollama stack (num_gpu: {LOCAL_NUM_GPU if LOCAL_NUM_GPU >= 0 else 'auto'}).")
        return {
            "func": _make_timed_llm(ollama_model_complete),
            "name": LOCAL_LLM_MODEL,
            "max_async": 1,
            "kwargs": {"host": OLLAMA_HOST, "think": False, "options": options},
        }


# ──────────────────────────────────────────────
# LOCAL EMBEDDING (always Ollama)
# ──────────────────────────────────────────────
_EMBED_TIMEOUT = 120  # seconds — Ollama cold-start can take ~60s; >120s is stuck


async def _local_embed(texts):
    import numpy as np
    import ollama

    client = ollama.AsyncClient(host=OLLAMA_HOST)
    try:
        data = await asyncio.wait_for(
            client.embed(model=EMBED_MODEL, input=texts, keep_alive="30m"),
            timeout=_EMBED_TIMEOUT,
        )
        return np.array(data["embeddings"])
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Ollama embed timed out after {_EMBED_TIMEOUT}s "
            f"(model={EMBED_MODEL}, host={OLLAMA_HOST}). "
            "Is the model loaded? Run: ollama pull nomic-embed-text"
        )
    finally:
        try:
            await client._client.aclose()
        except Exception:
            pass


# ──────────────────────────────────────────────
# RAG FACTORY (lazy initialization)
# ──────────────────────────────────────────────
_rag_instance = None
_rag_lock = asyncio.Lock()


def reset_rag():
    global _rag_instance
    _rag_instance = None


async def get_rag():
    """
    Create or return the singleton LightRAG instance.
    LightRAG and EmbeddingFunc are imported here (not at module level) so that
    `import index_archive` stays fast — top-level LightRAG imports can trigger
    Google/Ollama SDK I/O that blocks for minutes before any log line appears.
    """
    global _rag_instance

    async with _rag_lock:
        if _rag_instance is not None:
            return _rag_instance

        logger.info("📦 Loading LightRAG SDK (first call only, may take a few seconds)...")
        _t_imp = time.perf_counter()
        from lightrag import LightRAG  # lazy — heavy SDK initialisation on first use only
        from lightrag.utils import EmbeddingFunc
        logger.info(f"✅ LightRAG loaded in {time.perf_counter() - _t_imp:.1f}s")

        validate_paths()
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        provider = _setup_provider()

        try:
            ctx_info = f"num_ctx: {LOCAL_CONTEXT_WINDOW}" if LLM_PROVIDER != "GEMINI" else "cloud LLM"
            logger.info(f"Using model: {provider['name']} | {ctx_info}")
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
                summary_context_size=min(6000, LOCAL_CONTEXT_WINDOW),
                # Ollama serializes embed requests — 1 worker prevents timeout cascade
                # where 8 concurrent workers queue up and the last ones exceed the 120s limit.
                embedding_func_max_async=1,
                default_embedding_timeout=300,
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
    await rag.initialize_storages()
    try:
        await _local_embed(["ping"])
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Ollama at {OLLAMA_HOST}: {e}")

    fp = str(file_path)
    fh = file_hash(fp)

    manifest = _load_manifest()
    failures = _load_failures()

    try:
        success, error_msg, content_type, pipeline = await _index_single_file(rag, fp)
    except BaseException:
        _save_manifest(manifest)  # flush whatever completed before cancellation
        raise

    if success:
        manifest[fp] = {
            "hash": fh,
            "content_type": content_type,
            "pipeline": pipeline,
            "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
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


_INDEXABLE_EXTENSIONS = {".md", ".txt"}


async def _index_single_file(
    rag,
    file_path: str,
    max_retries: int = INDEX_MAX_RETRIES,
    dry_run: bool = False,
) -> tuple[bool, str, str, str]:
    """
    Index a single file with retry logic.
    Returns (success, error_msg, content_type, pipeline).
    """
    ext = Path(file_path).suffix.lower()
    if ext not in _INDEXABLE_EXTENSIONS:
        return False, f"Unsupported file type '{ext}' — only {_INDEXABLE_EXTENSIONS} are indexed", "general", "A"

    backoff = INDEX_RETRY_BACKOFF

    for attempt in range(max_retries):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if len(content.strip()) < 200:
                return True, "", "general", "A"  # Skip near-empty files, not an error

            content_type = _classify_content_type(Path(file_path), content)
            pipeline = _select_pipeline(content_type)

            if not dry_run:
                _prepend_frontmatter(
                    file_path, content_type, pipeline,
                    indexed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )

            t_chunk = time.perf_counter()
            if pipeline == "A" and content_type in ("research_paper", "validated_artifact"):
                chunks = chunk_text_sections(content, max_chars=CHUNK_SECTION_MAX_CHARS)
            elif pipeline == "A":
                chunks = chunk_text(content, max_chars=CHUNK_MAX_CHARS)
            else:
                chunks = chunk_text(content, max_chars=CHUNK_B_MAX_CHARS)
            t_chunked = time.perf_counter()

            if dry_run:
                logger.info(
                    f"[DRY RUN] {Path(file_path).name}: {content_type} → Pipeline {pipeline} | {len(chunks)} chunks"
                )
            elif pipeline == "A":
                t_insert = time.perf_counter()
                await rag.ainsert(chunks)
                t_done = time.perf_counter()
                logger.info(
                    f"[PHASE] {Path(file_path).name}: chunking={t_chunked - t_chunk:.1f}s "
                    f"| kg_insert={t_done - t_insert:.1f}s | chunks={len(chunks)} | pipeline=A"
                )
            else:
                # Pipeline B = smaller chunks, but still LightRAG (Tier-2). Archives are
                # NOT written to the sqlite-vec Tier-1 index (see embed.py docstring).
                t_insert = time.perf_counter()
                await rag.ainsert(chunks)
                t_done = time.perf_counter()
                logger.info(
                    f"[PHASE] {Path(file_path).name}: chunking={t_chunked - t_chunk:.1f}s "
                    f"| kg_insert={t_done - t_insert:.1f}s | chunks={len(chunks)} | pipeline=B"
                )

            return True, "", content_type, pipeline

        except Exception as e:
            error_msg = str(e)
            # Ollama infrastructure failures (model load / VRAM) affect every subsequent doc —
            # re-raise immediately so the batch loop can abort rather than retry 36+ times.
            if "status code: 500" in error_msg or "memory layout cannot be allocated" in error_msg:
                raise
            if attempt < max_retries - 1:
                wait = backoff[min(attempt, len(backoff) - 1)]
                logger.warning(
                    f"⚠️ Attempt {attempt + 1}/{max_retries} failed for "
                    f"{Path(file_path).name}: {error_msg}. Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)
            else:
                logger.error(f"❌ All {max_retries} attempts failed for {Path(file_path).name}: {error_msg}")
                return False, error_msg, "general", "A"


# ──────────────────────────────────────────────
# INDEXER
# ──────────────────────────────────────────────
async def index_archive(
    force_reset: bool = False,
    retry_failed: bool = False,
    dry_run: bool = False,
    prune_after: bool = False,
) -> None:
    """
    Index markdown files from the Archives folder into LightRAG.

    Args:
        force_reset: If True, wipes WORKING_DIR and re-indexes everything from scratch.
        retry_failed: If True, only retry previously failed files.
        dry_run: If True, print route decisions without inserting anything.
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

    _t_phase1 = time.perf_counter()
    logger.info("━━━ PHASE 1 / INIT: loading RAG instance & storage ━━━")
    rag = await get_rag()
    logger.info("🗄  Initializing storage backends...")
    _t_stor = time.perf_counter()
    await rag.initialize_storages()
    logger.info(f"✅ Storages ready in {time.perf_counter() - _t_stor:.1f}s")

    # Verify Ollama embedding endpoint is actually reachable before processing any documents.
    # initialize_storages() only sets up storage backends and never calls Ollama, so without
    # this probe the indexer would silently spin in LightRAG's internal PENDING→FAILED→PENDING
    # retry loop indefinitely.
    logger.info(f"⏳ Probing embed model ({EMBED_MODEL}) — cold start may take up to 2 min...")
    _t_probe = time.perf_counter()
    try:
        await _local_embed(["ping"])
    except Exception as e:
        logger.error(f"❌ Ollama embedding unreachable at {OLLAMA_HOST}: {e}")
        logger.error("Start Ollama first:  ollama serve")
        logger.error(f"Then ensure the embed model is pulled:  ollama pull {EMBED_MODEL}")
        sys.exit(1)
    logger.info(f"✅ Embed model ready in {time.perf_counter() - _t_probe:.1f}s")
    logger.info(f"⏱  Phase 1 total: {time.perf_counter() - _t_phase1:.1f}s")

    _t_phase2 = time.perf_counter()
    logger.info("━━━ PHASE 2 / SCANNING: manifest & file hashing ━━━")
    manifest = {} if force_reset else _load_manifest()
    failures = {} if force_reset else _load_failures()
    logger.info(f"📒 Manifest: {len(manifest)} known | {len(failures)} previous failures")

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
            if manifest.get(fp, {}).get("hash") != fh:
                pending.append((fp, fh))

        logger.info(
            f"📊 {len(all_files)} total files | {len(pending)} new/changed | {len(all_files) - len(pending)} skipped"
        )

    logger.info(f"⏱  Phase 2 total: {time.perf_counter() - _t_phase2:.1f}s")

    if not pending:
        logger.info("✅ Brain is already up-to-date. Nothing to index.")
        return

    _t_phase3 = time.perf_counter()
    logger.info(f"━━━ PHASE 3 / INDEXING: {len(pending)} files to process ━━━")
    success_count = 0
    error_count = 0

    _bar = tqdm(pending, desc="🧠 Indexing")
    for file_path, fh in _bar:
        _t_file = time.perf_counter()
        _bar.set_postfix_str(Path(file_path).name[:40], refresh=False)
        try:
            success, error_msg, content_type, pipeline = await _index_single_file(
                rag, file_path, dry_run=dry_run
            )
        except Exception as infra_err:
            logger.error(
                f"🛑 Infrastructure error — aborting batch to prevent retry storm: {infra_err}\n"
                f"   Fix: check BRAIN_NUM_GPU in .env and that Ollama has enough VRAM."
            )
            _save_failures(failures)
            return

        if success:
            logger.info(
                f"  ✓ {Path(file_path).name}  [{pipeline}]  {time.perf_counter() - _t_file:.1f}s"
            )
            manifest[file_path] = {
                "hash": fh,
                "content_type": content_type,
                "pipeline": pipeline,
                "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
            if not dry_run:
                _save_manifest(manifest)

            if file_path in failures:
                del failures[file_path]

            success_count += 1
        else:
            failures[file_path] = {
                "error": error_msg,
                "attempts": INDEX_MAX_RETRIES,
                "last_attempt": str(Path(file_path).stat().st_mtime),
            }
            error_count += 1

    # Save failure log
    _save_failures(failures)

    _t_index = time.perf_counter() - _t_phase3
    _rate = success_count / _t_index * 60 if _t_index > 0 and success_count > 0 else 0
    logger.info(f"⏱  Phase 3 total: {_t_index:.1f}s  ({_rate:.1f} files/min)")
    logger.info("━━━ PHASE 4 / DONE ━━━")
    logger.info(f"✅ {success_count} indexed | {error_count} errors | mode={LLM_PROVIDER}")
    if error_count > 0:
        logger.info(f"💡 {error_count} files failed. Run `python index_archive.py --retry-failed` to retry them.")

    # Auto-prune the KG — only runs when --prune-after is passed explicitly.
    if prune_after and success_count > 0 and not dry_run:
        try:
            _scripts_dir = str(Path(__file__).parent / "scripts")
            _added = _scripts_dir not in sys.path
            if _added:
                sys.path.insert(0, _scripts_dir)
            try:
                import prune_graph as _pg  # type: ignore
                logger.info("🌿 Running graph pruning...")
                _G = _pg.load_graph()
                _pg.prune_graph(_G, dry_run=False)
            finally:
                if _added:
                    sys.path.remove(_scripts_dir)
        except FileNotFoundError:
            pass  # No graph yet (e.g. all files were Pipeline B)
        except Exception as _e:
            logger.warning(f"⚠️ Graph pruning skipped: {_e}")


# ──────────────────────────────────────────────
# QUERY
# ──────────────────────────────────────────────
async def query_archive(query: str) -> str:
    """Run a hybrid RAG query against the knowledge graph."""
    from lightrag import QueryParam  # lazy — avoid top-level import cost
    rag = await get_rag()
    return await rag.aquery(query, param=QueryParam(mode="hybrid"))


# Deprecated alias — will be removed in a future version
test_query = query_archive


def get_brain_counts() -> dict:
    """Return document and entity counts from LightRAG KV-store files.
    Centralised here so callers don't hardcode filenames that may change across LightRAG versions.
    """
    def _count(path, corrupt_msg="unknown"):
        if not path.exists():
            return 0
        try:
            return len(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return corrupt_msg
    return {
        "indexed_documents": _count(WORKING_DIR / "kv_store_doc_status.json", "unknown (corrupt status file)"),
        "entities": _count(WORKING_DIR / "kv_store_full_entities.json"),
    }


# ──────────────────────────────────────────────
# LOCK FILE  (heartbeat-based, self-healing)
# ──────────────────────────────────────────────
_LOCK_FILE = Path(__file__).parent / ".indexer.lock"
_HEARTBEAT_INTERVAL = 30   # seconds between writes
_HEARTBEAT_STALE = 120     # seconds before lock is considered dead
_stop_heartbeat = threading.Event()


def _heartbeat_loop() -> None:
    while not _stop_heartbeat.wait(_HEARTBEAT_INTERVAL):
        if not _LOCK_FILE.exists():
            break
        try:
            data = json.loads(_LOCK_FILE.read_text())
            data["heartbeat"] = datetime.now(timezone.utc).isoformat()
            _LOCK_FILE.write_text(json.dumps(data))
        except Exception:
            pass


def _lock_is_stale() -> bool:
    """Return True if the lock file belongs to a dead or frozen process."""
    try:
        data = json.loads(_LOCK_FILE.read_text())
        pid = data.get("pid")
        hb = data.get("heartbeat")
    except Exception:
        return True  # corrupt or old touch-file format

    if pid is not None:
        try:
            import psutil
            if not psutil.pid_exists(int(pid)):
                return True
        except ImportError:
            pass

    if hb:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(hb)).total_seconds()
            if age > _HEARTBEAT_STALE:
                return True
        except Exception:
            pass

    return False


# ──────────────────────────────────────────────
# CLI ENTRY
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index archive documents into the Brain.")
    parser.add_argument("--reset", action="store_true", help="Force re-index all files.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry only previously failed files.")
    parser.add_argument("--dry-run", action="store_true", help="Print route decisions without inserting.")
    parser.add_argument(
        "--provider",
        choices=["local", "gemini"],
        help="Override LLM provider (default: from config/env).",
    )
    parser.add_argument(
        "--prune-after",
        action="store_true",
        help="Run graph pruning after indexing completes (slow; off by default).",
    )
    args = parser.parse_args()

    if args.provider:
        import config as _cfg

        _cfg.LLM_PROVIDER = args.provider.upper()
        logger.info(f"Provider overridden via CLI: {_cfg.LLM_PROVIDER}")

    import atexit
    # heartbeat is intentionally "" here — _lock_is_stale() skips the age check when
    # the value is falsy, preventing a false-stale result before the heartbeat thread
    # writes its first real timestamp.
    _LOCK_FILE.write_text(
        json.dumps({"pid": os.getpid(), "started": datetime.now(timezone.utc).isoformat(), "heartbeat": ""}),
        encoding="utf-8",
    )
    atexit.register(lambda: _LOCK_FILE.unlink(missing_ok=True))
    _hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _hb_thread.start()
    try:
        asyncio.run(
            index_archive(
                force_reset=args.reset,
                retry_failed=args.retry_failed,
                dry_run=args.dry_run,
                prune_after=args.prune_after,
            )
        )
    finally:
        _stop_heartbeat.set()
        _LOCK_FILE.unlink(missing_ok=True)
