# 🛠️ Zero-Cost Virtual Brain: Development & Customization Guide

This guide is for users and developers who want to modify, extend, or deeply understand the internals of the Zero-Cost Virtual Brain.

---

## 📖 Table of Contents
1. [User Customization](#user-customization)
2. [Developer Onboarding](#developer-onboarding)
3. [Core Logic & Flow](#core-logic--flow)
4. [Customizing the Knowledge Graph](#customizing-the-knowledge-graph)
5. [Extending the MCP Bridge](#extending-the-mcp-bridge)
6. [Troubleshooting & Performance](#troubleshooting--performance)

---

## 👤 User Customization

Most user-level customization is handled through the `.env` file. 

### Switching Models
If you have more VRAM (8GB+), you can switch to a larger model for better reasoning:
1. Open `.env`.
2. Change `BRAIN_LOCAL_MODEL=qwen2.5:7b`.
3. Increase `BRAIN_CONTEXT_WINDOW=32768` (or higher if VRAM allows).
4. Restart the indexer or server.

### Custom Vault Structure
By default, the brain looks for `3. Resources` and `4. Archives`. To change these, modify `config.py`:
```python
ARCHIVE_PATH = VAULT_PATH / "Your_Custom_Archive_Folder"
RESOURCES_PATH = VAULT_PATH / "Your_Custom_Active_Folder"
```

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
- **Engine:** [LightRAG](https://github.com/HKUDS/LightRAG) (Dual-layer Graph RAG).
- **Server:** [FastMCP](https://github.com/jlowin/fastmcp) (Model Context Protocol).
- **UI:** [Textual](https://github.com/Textualize/textual) (TUI) and [Vis.js](https://visjs.org/) (Graph Visualizer).
- **Database:** `sqlite-vec` for fast local vector search in `3. Resources`.

---

## ⚙️ Core Logic & Flow

### 1. Indexing (`index_archive.py`)
The indexer performs the following steps:
- **Scan:** Traverses `4. Archives` for `.md` files.
- **Hash Check:** Compares file hashes against `index_manifest.json` to skip unchanged files.
- **Chunking:** Large files are split into `BRAIN_CHUNK_SIZE` characters to stay within context limits.
- **Entity Extraction:** LightRAG uses the local LLM to extract entities and relationships.
- **Graph Updates:** Updates the local Knowledge Graph in `.lightrag/`.

### 2. Retrieval (`query.py` & `brain_server.py`)
- **Semantic Search:** Uses vector embeddings to find relevant chunks.
- **Graph Search:** Traverses the Knowledge Graph to find related concepts that might not share keywords.
- **MCP Tools:** Exposes these retrieval methods as standard tools for AI agents.

---

## 🧩 Customizing the Knowledge Graph

You can modify how the AI perceives your data by editing the prompts used for extraction.
- **Extraction Prompts:** Located within the LightRAG initialization in `index_archive.py`.
- **Entity Types:** You can define specific entity types (e.g., "Project", "Concept", "Person") to guide the graph construction.

---

## 🔌 Extending the MCP Bridge

To add a new tool for your AI agent (e.g., "Summarize Project"):
1. Open `brain_server.py`.
2. Add a new function with the `@mcp.tool()` decorator:
```python
@mcp.tool()
def summarize_project(name: str) -> str:
    """Summarize a specific project from the archive."""
    # Your logic here...
    return "Summary result"
```
3. Restart the `brain_server.py`.

---

## 🚀 Troubleshooting & Performance

### VRAM Management
The system is tuned for 6GB VRAM. If you encounter `llama runner process has terminated`:
- Ensure `OLLAMA_MAX_LOADED_MODELS=1` is set.
- Lower `BRAIN_CONTEXT_WINDOW` in `.env`.
- Check `utils.py -> get_gpu_stats()` to monitor real-time usage in the TUI.

### Encoding Issues (Windows)
If you see broken characters in the terminal, ensure your environment is set to UTF-8:
```powershell
$env:PYTHONIOENCODING="utf-8"
```

---

*For detailed setup, see [docs/setup_brain.md](setup_brain.md).*
