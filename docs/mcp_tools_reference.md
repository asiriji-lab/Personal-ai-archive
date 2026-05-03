# ZeroCostBrain — MCP Tools Reference

> **Source of truth:** `brain_server.py` | **Server name:** `BrainBridge` | **Protocol:** FastMCP

This document describes all 5 tools exposed by `brain_server.py`. Any MCP-compatible agent (Claude Desktop, Cursor, VS Code with MCP extension) can call these tools once the server is running (`python brain_server.py`).

---

## Global Limits

| Limit | Value |
|-------|-------|
| Max query length | 2,000 characters |
| Max note content size | 100,000 bytes (100 KB) |
| Max review queue results returned | 100 entries |

---

## Tool 1: `vault_search`

**Description:** Fast hybrid search (vector + BM25 + RRF) over the **Active Vault** (`3. Resources/`). Best for exact recall and keyword queries over your active notes.

**ToolAnnotations:** `readOnlyHint=True`, `idempotentHint=True`

### Signature
```python
async def vault_search(query: str) -> str
```

### Input
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `query` | `str` | Yes | Non-empty, max 2000 chars |

### Output
JSON string with the following structure:
```json
{
  "query": "your query text",
  "results": [
    {
      "path": "3. Resources/My Note.md",
      "chunk_index": 0,
      "rrf_score": 0.0321,
      "preview": "First 400 characters of the matching chunk..."
    }
  ]
}
```
Returns top **5** results. Returns `{"results": [], "message": "No results found."}` if nothing matches.

### How it works
Calls `query.py:search()` which:
1. Embeds the query via `nomic-embed-text` (Ollama)
2. Runs vector search over `data/index.db` (`sqlite-vec`)
3. Runs BM25 keyword search via FTS5
4. Fuses rankings with Reciprocal Rank Fusion (RRF)
5. Returns top-10 candidates, trimmed to top-5 in response

> **Note:** This tool only searches the Active Vault (`3. Resources/`). For archived research papers, use `archive_search`.

---

## Tool 2: `archive_search`

**Description:** Semantic + graph search over the **Archive Brain** (`4. Archives/` indexed into LightRAG). Best for thematic queries, entity relationships, and long-term knowledge retrieval.

**ToolAnnotations:** `readOnlyHint=True`, `idempotentHint=True`

### Signature
```python
async def archive_search(query: str) -> str
```

### Input
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `query` | `str` | Yes | Non-empty, max 2000 chars |

### Output
A natural language string synthesized by LightRAG from retrieved graph context. Not JSON — it's a prose answer drawing from the knowledge graph.

### How it works
Calls `index_archive.query_archive()` which runs:
```python
rag.aquery(query, param=QueryParam(mode="hybrid"))
```
LightRAG hybrid mode combines:
- **Local search:** Entity-level retrieval (named entities matching query terms)
- **Global search:** Community-level summarization
- **Graph traversal:** Relationship paths between matched entities

---

## Tool 3: `save_active_note`

**Description:** Write a new Markdown note to `3. Resources/` (Active Vault). The file is saved immediately. Run `embed.py` afterwards to index it for `vault_search`.

**ToolAnnotations:** `readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`

### Signature
```python
def save_active_note(title: str, content: str) -> str
```

### Input
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `title` | `str` | Yes | Non-empty. Sanitized via `utils.sanitize_filename()` — unsafe chars replaced with `_`, path traversal sequences (`..`) stripped |
| `content` | `str` | Yes | Non-empty, max 100 KB (UTF-8 encoded) |

### Output
- Success: `"Successfully saved '<sanitized_title>' to Resources."`
- Error: JSON with `{"error": "...", "tool": "save_active_note"}`

### Security
The saved path is validated with `is_safe_path()` (from `config.py`) before writing. Any path that resolves outside `RESOURCES_PATH` is rejected with a boundary violation error.

### After saving
The note is **not automatically indexed**. To make it searchable via `vault_search`, run:
```powershell
python embed.py
```

---

## Tool 4: `brain_status`

**Description:** Health check for the Brain. Returns current provider mode, GPU memory stats, indexed document count, and entity count.

**ToolAnnotations:** `readOnlyHint=True`, `idempotentHint=True`

### Signature
```python
def brain_status() -> str
```

### Input
None.

### Output
JSON string:
```json
{
  "provider": "LOCAL",
  "working_dir": "C:/Users/.../knowledge_base/.lightrag",
  "gpu": {
    "used_mb": 3421,
    "total_mb": 6144,
    "utilization": 12,
    "display": "3421MB / 6144MB (12% Load)"
  },
  "indexed_documents": 112,
  "entities": 4823
}
```

| Field | Source |
|-------|--------|
| `provider` | `config.LLM_PROVIDER` (`LOCAL` or `GEMINI`) |
| `gpu` | `nvidia-smi` (via `utils.get_gpu_stats()`, cached 3s) |
| `indexed_documents` | Count of keys in `.lightrag/kv_store_doc_status.json` |
| `entities` | Count of keys in `.lightrag/kv_store_full_entities.json` |

If `nvidia-smi` is unavailable, `gpu.display` returns `"GPU Offline"` with null values.

---

## Tool 5: `review_queue`

**Description:** Returns entries from the validation review queue (`knowledge_base/system/review-queue.jsonl`). Used to inspect the results of `validate_and_archive.py` runs — which claims passed, failed, or were skipped.

**ToolAnnotations:** `readOnlyHint=True`, `idempotentHint=True`

### Signature
```python
def review_queue(status_filter: str = "all") -> str
```

### Input
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `status_filter` | `str` | No | One of: `"all"`, `"pending_review"`, `"failed"`, `"skipped"`. Defaults to `"all"`. |

Filter semantics:
- `"all"` — every entry in the queue
- `"pending_review"` — entries where `status == "pending_review"` (awaiting human review)
- `"failed"` — entries where `validator_verdict == "fail"` (claim did not pass Ollama validation)
- `"skipped"` — entries where `validator_verdict == "skipped"` (Ollama was unavailable or timed out)

### Output
JSON string:
```json
{
  "total_entries": 47,
  "filtered": 12,
  "status_filter": "failed",
  "entries": [
    {
      "timestamp": "2026-04-29T14:23:01Z",
      "run_id": "rc-abc123",
      "source_file": "4. Archives/My_Paper.md",
      "claim_text": "Cross-encoders achieve 12% improvement...",
      "confidence": 0.20,
      "validator_verdict": "fail",
      "validator_explanation": "The source text does not support this specific percentage.",
      "status": "pending_review"
    }
  ]
}
```

Results are sorted by `timestamp` descending (most recent first). Maximum 100 entries returned; if the filtered result exceeds 100, response includes `"truncated": true`.

If the queue file does not exist: `{"entries": [], "message": "Queue is empty."}`

### Queue entry schema
| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 UTC | When the validation run wrote this entry |
| `run_id` | string | AutoResearchClaw artifact run ID (e.g. `rc-abc123`) |
| `source_file` | string | Relative path from vault root to archived `.md` file |
| `claim_text` | string | The extracted factual claim |
| `confidence` | float | Static heuristic: pass=0.90, fail=0.20, skipped=0.50 |
| `validator_verdict` | string | `"pass"`, `"fail"`, or `"skipped"` |
| `validator_explanation` | string | One-sentence explanation from the validator |
| `status` | string | `"pending_review"`, `"accepted"`, or `"rejected"` — editable by human |

---

## Connecting an Agent

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "BrainBridge": {
      "command": "python",
      "args": ["C:/path/to/ZeroCostBrain/brain_server.py"]
    }
  }
}
```

### Cursor
Add to Cursor MCP settings (`.cursor/mcp.json`):
```json
{
  "BrainBridge": {
    "command": "python brain_server.py",
    "cwd": "C:/path/to/ZeroCostBrain"
  }
}
```

---

*For adding new tools, see [customization.md](customization.md#extending-the-mcp-bridge).*
