# 🚀 Two-Tier Brain Setup Guide (ZeroCostBrain)

This is the control hub for your **Zero-Cost Virtual Brain**, connecting your active Obsidian Vault with deep archival knowledge using local AI.

## 1. Prerequisites

- **Python 3.10+**
- **Ollama** installed and running (`ollama serve`)
- **NVIDIA GPU** with drivers (for `nvidia-smi` monitoring)

## 2. The Architecture
*   **Engine (Code):** This folder (`ZeroCostBrain/`)
*   **Vault (Data):** Your Obsidian knowledge base (configured via `.env`)
*   **Brain Storage:** `.lightrag/` folder inside your vault
*   **LLM Model:** `qwen3.5:4b-brain` (Local via Ollama — custom variant with num_ctx=4096 baked in, see dev_log.md Bug 7)
*   **Embeddings:** `nomic-embed-text` (Local via Ollama)

## 3. First-Time Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Pull the required Ollama models
ollama pull qwen3.5:4b
ollama pull nomic-embed-text

# 3. Configure your vault path
copy .env.example .env
# Edit .env and set BRAIN_VAULT_PATH to your Obsidian vault location

# 4. Verify the setup
python -c "from config import validate_paths; validate_paths(); print('✅ Config OK')"

# 5. Build the initial knowledge graph
python index_archive.py
```

## 4. VS Code Integration

This folder is a complete VS Code workspace:
1.  Open **VS Code**.
2.  Go to **File > Open Folder...** and select the `ZeroCostBrain` folder.
3.  Press `Ctrl + Shift + D` to open the **Run and Debug** menu.
4.  Use the dropdown at the top to select:
    *   **🧠 Brain TUI (Full Control):** The main terminal dashboard.
    *   **🚀 Launch Bridge (MCP Server):** To connect AI agents (like Claude/Cursor).
    *   **⚙️ Run Indexer (Update Archive):** To scan new `.md` files.
    *   **🧪 Test Memory Access:** Interactive query testing.

## 5. The Core Scripts

| Command | Description |
|---------|-------------|
| `python brain_tui.py` | Main cockpit — dashboard, vitals, launcher |
| `python index_archive.py` | Index new/changed archive files |
| `python index_archive.py --reset` | Full re-index from scratch |
| `python brain_server.py` | Start MCP Bridge for AI agents |
| `python brain_explorer.py` | View knowledge graph concepts & relations |
| `python brain_explorer.py --top 30` | Show more concepts |
| `python test_brain.py` | Interactive query REPL |
| `python test_brain.py "your question"` | Single query via CLI |

## 6. Environment Variables

All configuration is in `config.py` with `.env` overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAIN_VAULT_PATH` | *(hardcoded fallback)* | Path to your Obsidian vault |
| `BRAIN_LLM_PROVIDER` | `LOCAL` | `LOCAL` (Ollama) or `GEMINI` (Cloud) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `BRAIN_LOCAL_MODEL` | `qwen3.5:4b` | Local LLM model name |
| `BRAIN_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `BRAIN_CONTEXT_WINDOW` | `4096` | Context window size (4096 is optimal for RTX 4050 — see dev_log.md) |
| `GOOGLE_API_KEY` | *(empty)* | Gemini API key (if using cloud) |
| `BRAIN_INDEX_MAX_RETRIES` | `3` | Max retry attempts per file during indexing |
| `BRAIN_CHUNK_SIZE` | `1500` | Max chars per document chunk (math-derived — see dev_log.md Bug 5) |

## 7. Before Running the Indexer (Windows)

Always set this before starting Ollama and running `index_archive.py`:

```powershell
$env:OLLAMA_FLASH_ATTENTION="1"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:PYTHONIOENCODING="utf-8"
```

Flash attention reduces VRAM usage and speeds up inference. The encoding fix prevents crashes on emoji/arrow characters in Windows terminal.

Full indexer reset sequence:

```powershell
$env:OLLAMA_FLASH_ATTENTION="1"
$env:OLLAMA_KV_CACHE_TYPE="q8_0"
$env:OLLAMA_MAX_LOADED_MODELS="1"
$env:PYTHONIOENCODING="utf-8"
Remove-Item "C:\Users\acer.nitrov15\ZeroCostBrain\knowledge_base\.lightrag" -Recurse -Force
python index_archive.py --reset
```

## 8. Dependencies

If you ever move this to a new machine:
```bash
pip install -r requirements.txt
```
