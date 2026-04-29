"""
🧠 ZeroCostBrain — MCP Bridge Server (The Bridge)

Exposes the Archive Brain and Active Vault to any MCP-compatible AI agent
(Cursor, Claude Desktop, VS Code, etc.) via FastMCP.

Tools provided:
  - archive_search(query)    — Semantic + graph search over long-term memory (LightRAG)
  - vault_search(query)      — Hybrid vector + BM25 search over Resources (sqlite-vec)
  - save_active_note(title, content) — Write a note to 3. Resources
  - brain_status()           — Health check (indexed docs, GPU, provider)
"""

import sys
import os
import json
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from config import RESOURCES_PATH, WORKING_DIR, LLM_PROVIDER, validate_paths
from utils import sanitize_filename, get_gpu_stats
from index_archive import get_rag, test_query
from query import search as hybrid_search

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# LIFESPAN — initialize RAG inside the server's event loop
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(server):
    """Initialize LightRAG storages inside FastMCP's event loop (not before it)."""
    validate_paths()
    rag = get_rag()
    try:
        await rag.initialize_storages()
    except ConnectionError as e:
        logger.error(f"❌ Cannot connect to Ollama: {e}")
        raise
    logger.info("✅ Brain Bridge is ONLINE. RAG storages initialized.")
    yield


# ──────────────────────────────────────────────
# SERVER
# ──────────────────────────────────────────────
mcp = FastMCP("BrainBridge", lifespan=lifespan)


_MAX_QUERY_LEN = 2000
_MAX_NOTE_BYTES = 100_000  # 100 KB


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
async def archive_search(query: str) -> str:
    """Search your Archive Brain for existing knowledge using semantic + graph retrieval."""
    if not query or not query.strip():
        return "Error: Query cannot be empty."
    if len(query) > _MAX_QUERY_LEN:
        return f"Error: Query exceeds {_MAX_QUERY_LEN} character limit."
    try:
        result = await test_query(query.strip())
        return result
    except Exception as e:
        logger.error(f"archive_search failed: {e}")
        return json.dumps({"error": str(e), "tool": "archive_search"})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def vault_search(query: str) -> str:
    """Fast hybrid search (vector + BM25 + RRF) over the full vault index. Best for exact recall and keyword queries."""
    if not query or not query.strip():
        return "Error: Query cannot be empty."
    if len(query) > _MAX_QUERY_LEN:
        return f"Error: Query exceeds {_MAX_QUERY_LEN} character limit."
    try:
        results = hybrid_search(query.strip())
        if not results:
            return json.dumps({"query": query, "results": [], "message": "No results found."})
        # Return top 5 with path, chunk, and a content preview
        output = []
        for r in results[:5]:
            output.append({
                "path": r["path"],
                "chunk_index": r["chunk_index"],
                "rrf_score": round(r["rrf_score"], 4),
                "preview": r["content"][:400],
            })
        return json.dumps({"query": query, "results": output}, indent=2)
    except Exception as e:
        logger.error(f"vault_search failed: {e}")
        return json.dumps({"error": str(e), "tool": "vault_search"})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False))
def save_active_note(title: str, content: str) -> str:
    """Save a new note into your 3. Resources folder (Active Vault)."""
    if not title or not title.strip():
        return "Error: Title cannot be empty."
    if not content or not content.strip():
        return "Error: Content cannot be empty."
    if len(content.encode("utf-8")) > _MAX_NOTE_BYTES:
        return f"Error: Content exceeds {_MAX_NOTE_BYTES // 1000}KB limit."

    try:
        safe_title = sanitize_filename(title.strip())
    except ValueError as e:
        return f"Error: Invalid title — {e}"

    try:
        RESOURCES_PATH.mkdir(parents=True, exist_ok=True)
        filepath = RESOURCES_PATH / f"{safe_title}.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"📝 Saved note: {safe_title}.md")
        return f"Successfully saved '{safe_title}' to Resources."
    except OSError as e:
        logger.error(f"save_active_note failed: {e}")
        return json.dumps({"error": str(e), "tool": "save_active_note"})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def brain_status() -> str:
    """Get the current health status of the Brain (indexed docs, GPU, provider mode)."""
    status = {
        "provider": LLM_PROVIDER,
        "working_dir": str(WORKING_DIR),
        "gpu": get_gpu_stats(),
    }

    # Count indexed documents
    doc_status_file = WORKING_DIR / "kv_store_doc_status.json"
    if doc_status_file.exists():
        try:
            docs = json.loads(doc_status_file.read_text(encoding="utf-8"))
            status["indexed_documents"] = len(docs)
        except (json.JSONDecodeError, OSError):
            status["indexed_documents"] = "unknown (corrupt status file)"
    else:
        status["indexed_documents"] = 0

    # Count entities
    entity_file = WORKING_DIR / "kv_store_full_entities.json"
    if entity_file.exists():
        try:
            entities = json.loads(entity_file.read_text(encoding="utf-8"))
            status["entities"] = len(entities)
        except (json.JSONDecodeError, OSError):
            status["entities"] = "unknown"
    else:
        status["entities"] = 0

    return json.dumps(status, indent=2, default=str)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def review_queue(status_filter: str = "all") -> str:
    """Return validation review queue contents.
       status_filter: "all" | "pending_review" | "failed" | "skipped"
    """
    valid_filters = {"all", "pending_review", "failed", "skipped"}
    if status_filter not in valid_filters:
        return json.dumps({
            "error": f"Invalid status_filter '{status_filter}'. Valid values: {sorted(valid_filters)}"
        })

    from config import VAULT_PATH as _VAULT
    queue_path = _VAULT / "system" / "review-queue.jsonl"

    if not queue_path.exists():
        return json.dumps({"entries": [], "message": "Queue is empty."})

    all_entries: list[dict] = []
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            all_entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning(f"review_queue: skipping malformed line: {line[:80]}")

    total_entries = len(all_entries)

    if status_filter == "pending_review":
        filtered = [e for e in all_entries if e.get("status") == "pending_review"]
    elif status_filter == "failed":
        filtered = [e for e in all_entries if e.get("validator_verdict") == "fail"]
    elif status_filter == "skipped":
        filtered = [e for e in all_entries if e.get("validator_verdict") == "skipped"]
    else:
        filtered = list(all_entries)

    filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    truncated = len(filtered) > 100
    result: dict = {
        "total_entries": total_entries,
        "filtered": len(filtered),
        "status_filter": status_filter,
        "entries": filtered[:100],
    }
    if truncated:
        result["truncated"] = True

    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
