# 🚀 Two-Tier Brain Setup Guide (ZeroCostBrain)

This is the control hub for your **Zero-Cost Virtual Brain**, connecting your active Obsidian Vault with deep archival knowledge using local AI.

---

## 📋 1. Prerequisites

- **Python 3.10+**
- **Ollama** installed and running (`ollama serve`).
- **NVIDIA GPU** with 6GB+ VRAM (e.g., RTX 4050).
- **SQLite with Vector Support:** The system uses `sqlite-vec` for fast local retrieval.

## 🏗️ 2. The Architecture

The system operates in two distinct tiers to optimize for performance and VRAM:

| Tier | Folder | Search Engine | Best For |
|------|--------|---------------|----------|
| **Active Vault** | `3. Resources` | **Hybrid Search** (Vector + BM25) | Fast recall, keyword matches, active notes. |
| **Long-Term Archive** | `4. Archives` | **Knowledge Graph** (LightRAG) | Thematic queries, entity relationships, old projects. |

- **Engine (Code):** This folder (`ZeroCostBrain/`)
- **Vault (Data):** Your Obsidian knowledge base (configured via `.env`)
- **Brain Storage:** `.lightrag/` (Graph) and `data/index.db` (Vector)
- **Ollama Models:** `qwen3.5:4b` (LLM) and `nomic-embed-text` (Embeddings)

## 🛠️ 3. First-Time Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Pull base model and embedder, then create the custom brain model
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
# Create qwen3.5:4b-brain: disables thinking trace (avoids timeout) and locks num_ctx=4096
# On Windows PowerShell:
@"
FROM qwen3.5:4b
PARAMETER num_ctx 4096
PARAMETER num_gpu 99
"@ | Out-File -FilePath "$env:TEMP\Modelfile" -Encoding utf8
ollama create qwen3.5:4b-brain -f "$env:TEMP\Modelfile"
# On Linux/macOS:
# printf "FROM qwen3.5:4b\nPARAMETER num_ctx 4096\nPARAMETER num_gpu 99\n" > /tmp/Modelfile
# ollama create qwen3.5:4b-brain -f /tmp/Modelfile

# 3. Configure your vault path
copy .env.example .env
# Edit .env and set BRAIN_VAULT_PATH to your Obsidian vault location

# 4. Verify setup — also bootstraps the vault skeleton on first run
python -c "from config import validate_paths; validate_paths(); print('Config OK')"
# First run will create knowledge_base/1. Projects/, 2. Areas/, 3. Resources/, 4. Archives/, system/
# To use an existing Obsidian vault instead, set BRAIN_VAULT_PATH in .env first.

# 5. Index your Active Vault (3. Resources) into the SQLite vector store
python embed.py
# Drop .md files into 3. Resources/ first. This enables vault_search via the MCP bridge.

# 6. Build the initial knowledge graph (drop .md files in 4. Archives/ first)
python index_archive.py
```

## 🔌 4. VS Code Integration

This folder is a complete VS Code workspace:
1.  Open **VS Code**.
2.  Go to **File > Open Folder...** and select the `ZeroCostBrain` folder.
3.  Press `Ctrl + Shift + D` to open the **Run and Debug** menu.
4.  Use the dropdown at the top to select:
    *   **🧠 Brain TUI (Full Control):** The main terminal dashboard.
    *   **🚀 Launch Bridge (MCP Server):** To connect AI agents (like Claude/Cursor).
    *   **⚙️ Run Indexer (Update Archive):** To scan new `.md` files.
    *   **🧪 Test Memory Access:** Interactive query testing.

## ⚙️ 5. The Core Scripts

| Command | Description |
|---------|-------------|
| `python brain_tui.py` | Main cockpit — dashboard, vitals, launcher. |
| `python embed.py` | Index `3. Resources/` into SQLite vector store (Tier 1). Run after adding notes. |
| `python embed.py --reset` | Drop and rebuild the Tier 1 index from scratch. |
| `python embed.py --resume` | Resume an interrupted indexing run. |
| `python index_archive.py` | Index new/changed archive files (Incremental). |
| `python index_archive.py --reset` | Full re-index from scratch. |
| `python index_archive.py --retry-failed` | Retry only files that failed previous indexing. |
| `python scripts/prune_graph.py` | Remove noisy or isolated entities from the knowledge graph to improve latency. |
| `python brain_server.py` | Start MCP Bridge for AI agents. |
| `python scripts/validate_and_archive.py --artifact <path>` | Validate and archive one AutoResearchClaw artifact. |
| `python scripts/validate_and_archive.py --watch` | Watch `artifacts/` and process new runs automatically (30s poll). |
| `python watch_archive.py` | Background service to auto-index new files (60s debounce). |
| `python brain_explorer.py` | View knowledge graph concepts & relations. |
| `python query.py "question"` | Fast hybrid search over the **Active Vault**. |
| `python test_brain.py` | Interactive query REPL for the **Archive Brain**. |

## 🌍 6. Environment Variables

All configuration is in `config.py` with `.env` overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAIN_VAULT_PATH` | *(hardcoded fallback)* | Path to your Obsidian vault. |
| `BRAIN_LLM_PROVIDER` | `LOCAL` | `LOCAL` (Ollama) or `GEMINI` (Cloud). |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address. |
| `BRAIN_LOCAL_MODEL` | `qwen3.5:4b-brain` | Local LLM model name. Uses the custom brain model (thinking OFF, num_ctx=4096). |
| `BRAIN_EMBED_MODEL` | `nomic-embed-text` | Embedding model name. |
| `BRAIN_CONTEXT_WINDOW` | `4096` | Context window size (4096 is optimal for RTX 4050). |
| `GOOGLE_API_KEY` | *(empty)* | Gemini API key (if using cloud). |
| `BRAIN_INDEX_MAX_RETRIES` | `3` | Max retry attempts per file during indexing. |
| `BRAIN_CHUNK_SIZE` | `1500` | Max chars per document chunk. |
| `BRAIN_GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model for claims extraction fallback. |
| `BRAIN_VALIDATOR_MODEL` | `qwen3.5:4b` | Ollama model for claim validation (separate from brain LLM). |
| `BRAIN_VALIDATOR_TIMEOUT` | `15` | Per-claim validation timeout in seconds. |

## 🏁 7. Performance Optimization (Windows)

Always set these before starting Ollama and running `index_archive.py` for best results on 6GB VRAM:

```powershell
$env:OLLAMA_FLASH_ATTENTION="1"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:PYTHONIOENCODING="utf-8"
```

Flash attention reduces VRAM usage and speeds up inference. The encoding fix prevents crashes on emoji/arrow characters in the Windows terminal.

---

*For developers, see [docs/customization.md](customization.md) for extension and internals.*
