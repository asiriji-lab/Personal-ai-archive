# 🛠️ Zero-Cost Virtual Brain: Development & Customization Guide

This guide is for users and developers who want to modify, extend, or deeply understand the internals of the Zero-Cost Virtual Brain.

---

## 📖 Table of Contents
1. [User Customization](#user-customization)
2. [Developer Onboarding](#developer-onboarding)
3. [Indexing & Fault Tolerance](#indexing--fault-tolerance)
4. [Data Ingestion (Papers & News)](#data-ingestion-papers--news)
5. [Automated Indexing (Watcher)](#automated-indexing-watcher)
6. [Extending the MCP Bridge](#extending-the-mcp-bridge)
7. [Troubleshooting & Performance](#troubleshooting--performance)

---

## 👤 User Customization

Most user-level customization is handled through the `.env` file. 

### Switching Models
If you have more VRAM (8GB+), you can switch to a larger model for better reasoning:
1. Open `.env`.
2. Change `BRAIN_LOCAL_MODEL=qwen2.5:7b`.
3. Increase `BRAIN_CONTEXT_WINDOW=32768` (or higher if VRAM allows).
4. Restart the indexer or server.

---

## 💻 Developer Onboarding

### Environment Setup
1. **Virtual Environment:** It is highly recommended to use a venv.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
2. **Debug Mode:** Use the provided VS Code launch configurations (`.vscode/launch.json`) to step through the code.

### Tech Stack
- **Engine:** [LightRAG](https://github.com/HKUDS/LightRAG) (Archive Graph).
- **Hybrid Search:** `sqlite-vec` + FTS5 (Active Vault).
- **Server:** [FastMCP](https://github.com/jlowin/fastmcp).
- **UI:** [Textual](https://github.com/Textualize/textual).
- **Validation:** `scripts/validate_and_archive.py` — 7-stage pipeline (claims → Ollama → queue → archive → index).
- **Graph Maintenance:** `scripts/prune_graph.py` — removes noisy/isolated LightRAG entities to reduce latency.

---

## ⚙️ Indexing & Fault Tolerance

The indexer (`index_archive.py`) is designed for long-running processes and resilience.

### Incremental Logic
- **Hashing:** Fast MD5 hashes are stored in `.lightrag/index_manifest.json`. Files are only re-indexed if their hash changes.
- **Failures:** Files that cause LLM timeouts or crashes are logged to `.lightrag/index_failures.json`.
- **Retries:** Use `python index_archive.py --retry-failed` to specifically target files that previously errored.
- **Max Retries:** Controlled by `BRAIN_INDEX_MAX_RETRIES` with exponential backoff (`5s`, `15s`, `30s`).

---

## 📥 Data Ingestion (Papers & News)

There are three ingestion paths into `4. Archives/`:

### Primary: AutoResearchClaw → Validation Harness (`validate_and_archive.py`)
The main research ingestion path for AI-generated papers.
- **Trigger:** `python scripts/validate_and_archive.py --artifact autoresearchclaw/artifacts/rc-<run-id>/`
- **Flow:** Locates `paper_draft.md` → extracts claims → validates via Ollama → writes review queue → enriches paper → copies to `4. Archives/` → triggers LightRAG indexing
- **Watch mode:** `--watch` polls `artifacts/` every 30s and processes new runs automatically
- See [validation-harness.md](validation-harness.md) for full spec

### AI Papers (`fetch_papers.py`)
- **Sources:** arXiv RSS + Hugging Face Daily Papers.
- **Keyword Filter:** Controlled via `papers_config.yaml`. Only arXiv papers matching these keywords are saved; all HF Daily papers pass through.
- **Dedup:** Uses `data/papers_manifest.json` to prevent duplicate ingestion of the same arXiv ID.
- **Note:** Writes directly to `4. Archives/` — bypasses the validation harness.

### News Ingest (`news_ingest.py`)
- **Sources:** Google News (AI, Tech, Finance), Lab Blogs (DeepMind, Meta, Qwen, Apple, Google Research), arXiv RSS.
- **Logic:** Extracts summaries and creates clean Markdown files in `4. Archives/News_Ingest/`.
- **Note:** Writes directly to `4. Archives/` — bypasses the validation harness.

---

## 👁️ Automated Indexing (Watcher)

The `watch_archive.py` script monitors your archive folder for changes.

### Debounce Mechanism
To prevent VRAM thrashing during bulk file operations (e.g., moving a folder), the watcher uses a **Debounce Window** (default: 60s).
- It waits until 60 seconds have passed since the *last* file change before triggering the indexer.
- You can adjust this via `python watch_archive.py --debounce 30`.

---

## 🔌 Extending the MCP Bridge

To add a new tool for your AI agent (e.g., "Summarize Project"):
1. Open `brain_server.py`.
2. Add a new function with the `@mcp.tool()` decorator. Always include `ToolAnnotations` so calling agents know whether the tool is safe to auto-approve:
```python
from mcp.types import ToolAnnotations

# Read-only tool — agents can call without confirmation
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def summarize_project(name: str) -> str:
    """Summarize a specific project from the archive."""
    # Your logic here...
    return "Summary result"

# Destructive tool — agents should confirm before calling
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False))
def delete_note(title: str) -> str:
    """Delete a note from Resources."""
    ...
```
3. Restart `brain_server.py`.

**Annotation reference:**
- `readOnlyHint=True` — tool does not modify any state
- `destructiveHint=True` — tool may overwrite or delete data
- `idempotentHint=True` — calling it twice has the same effect as once (safe to retry)

---

## 🚀 Troubleshooting & Performance

### VRAM Management
The system is tuned for 6GB VRAM. If you encounter `llama runner process has terminated`:
- Ensure `OLLAMA_MAX_LOADED_MODELS=1` is set.
- Lower `BRAIN_CONTEXT_WINDOW` in `.env`.
- Check `utils.py -> get_gpu_stats()` to monitor real-time usage in the TUI.

---

*For detailed setup, see [docs/setup_brain.md](setup_brain.md).*
