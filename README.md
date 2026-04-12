# 🧠 The Zero-Cost Virtual Brain (Architecture & Big Picture)

Welcome to the **Zero-Cost Virtual Brain**. This system is a local, private, and free AI memory system that connects daily thought with deep historical knowledge using a Knowledge Graph.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Make sure Ollama is running with required models
ollama pull qwen3.5:4b
ollama pull nomic-embed-text

# 3. Customize environment variables
copy .env.example .env

# 4. Index your archives
python index_archive.py

# 5. Launch the dashboard
python brain_tui.py
```

---

## 🏗️ Project Structure

The repository is organized into core engine components, data ingestion tools, and utilities.

### ⚙️ Core Engine
| File | Description |
|------|-------------|
| `config.py` | Central configuration (paths, models, settings). |
| `utils.py` | Shared utilities (GPU monitoring, sanitization, chunking). |
| `index_archive.py` | Incremental indexer that builds the Knowledge Graph. |
| `brain_server.py` | FastMCP server exposing memory tools to AI agents. |
| `query.py` | Core logic for querying the knowledge graph. |
| `embed.py` | Embedding generation and manifest management. |

### 🛠️ Dashboards & Visualization
| File | Description |
|------|-------------|
| `brain_tui.py` | Terminal-based dashboard for monitoring and launching tasks. |
| `brain_explorer.py` | Web-based knowledge graph explorer. |
| `visualize_graph.py` | Tool for generating static graph visualizations. |

### 📥 Data Ingestion
| File | Description |
|------|-------------|
| `fetch_papers.py` | Automatically fetch and archive AI research papers. |
| `news_ingest.py` | Ingest news articles into the archival memory. |
| `watch_archive.py` | Background service to watch for new files and auto-index. |

### 🧪 Testing & Evaluation
| File | Description |
|------|-------------|
| `test_brain.py` | Interactive CLI for testing brain queries. |
| `test_llm_speed.py` | Benchmark tool for local LLM performance. |
| `eval/run_eval.py` | Evaluation suite for measuring retrieval accuracy. |

---

## 🌍 The Grand Vision
The goal is to build a **local, private, and free AI memory system** that operates entirely on local hardware (optimized for 6GB VRAM GPUs like the RTX 4050).

### Key Features
- **Incremental Indexing**: Only process what changed.
- **VRAM Optimized**: Designed to run reasoning and embeddings simultaneously in 6GB.
- **Hybrid Support**: Easily switch between Ollama (Local) and Gemini (API).
- **Agentic Integration**: Full MCP support for Claude/Cursor.

---
*For more detailed setup instructions, see [docs/setup_brain.md](docs/setup_brain.md).*
