# ZeroCostBrain System Connectivity Map

This document provides a granular technical view of how the various ZeroCostBrain modules interact. It maps the lifecycle of data from ingestion to retrieval.

> **Last audited:** 2026-05-04 — Verified against actual codebase. All claims reflect current code, not aspirational design.

## System Relationship Diagram

```mermaid
graph TD
    subgraph "External Input & Generation"
        RSS["RSS Feeds (arXiv/News)"]
        ARC["AutoResearchClaw (23-Stage Pipeline)"]
        User["Manual Notes (Obsidian)"]
        FP["fetch_papers.py (arXiv + HF Daily)"]
    end

    subgraph "Ingest & Validation Gate"
        NI["news_ingest.py"]
        VAL["validate_and_archive.py"]
        RSS --> NI
        NI -->|Writes MD direct| ARCH_DIR
        FP -->|Writes MD direct| ARCH_DIR
        ARC -->|Artifacts| VAL
        VAL -->|Validated & Enriched MD| ARCH_DIR
    end

    subgraph "Vault Storage (PARA-Lite)"
        ARCH_DIR[("4. Archives/ (Long-term)")]
        RES_DIR[("3. Resources/ (Active)")]
        User -->|Edit| RES_DIR
    end

    subgraph "The Dual-Brain Indexing"
        WA["watch_archive.py (Watchdog)"]
        IA["index_archive.py"]
        EM["embed.py (Manual CLI)"]

        ARCH_DIR -->|Filesystem Events| WA
        WA -->|Triggers on .md change| IA
        IA -->|LightRAG Graph| LRAG[(".lightrag/ (KG Store)")]
        IA -->|Manifest| MANIFEST_A[("data/index_manifest.json")]

        RES_DIR -.->|Run manually: python embed.py| EM
        EM -->|sqlite-vec + FTS5| SDB[("data/index.db (Vector Store)")]
        EM -->|Manifest| MANIFEST_E[("data/embed_manifest.json")]

        EM & IA & VAL & NI -.->|Shared Logic| Utils["utils.py"]
        EM & IA & VAL & NI -.->|Settings| Config["config.py"]
    end

    subgraph "Retrieval — Two Independent Paths"
        QP["query.py (Active Brain only)"]
        QA["query_archive() in index_archive.py"]
        BS["brain_server.py (FastMCP — BrainBridge)"]

        SDB -->|Vector + BM25| QP
        QP -->|RRF Fusion (internal)| BS
        LRAG -->|LightRAG hybrid query| QA
        QA --> BS
    end

    subgraph "MCP Tools (5 total)"
        BS -->|vault_search| T1["vault_search(query)"]
        BS -->|archive_search| T2["archive_search(query)"]
        BS -->|save_active_note| T3["save_active_note(title, content)"]
        BS -->|brain_status| T4["brain_status()"]
        BS -->|review_queue| T5["review_queue(status_filter)"]
    end

    subgraph "Consumers"
        T1 & T2 & T3 & T4 & T5 -->|MCP Protocol| Claude["Claude / Cursor Agent"]
        BS -->|TUI| TUI["brain_tui.py"]
    end

    %% AI Models
    OLLAMA["Ollama (Local LLM/Embed)"]
    GEMINI["Gemini 2.0 Flash (Cloud — Validation)"]

    IA & EM & QP & QA --- OLLAMA
    VAL --- GEMINI
```

---

## Functional Layers

### 1. The Validation Firewall

All automated research from `AutoResearchClaw` is gated by `scripts/validate_and_archive.py`. This script:
1. Locates `paper_draft.md` (at artifact root or `stage-17/` fallback)
2. Extracts claims from `pipeline_summary.json`, or falls back to Gemini 2.0 Flash extraction from the abstract/conclusion
3. Validates each claim against the source text using a local Ollama model (`qwen3.5:4b`)
4. Writes results to `knowledge_base/system/review-queue.jsonl`
5. Enriches the paper with a `validation_summary:` YAML frontmatter block
6. Copies the enriched file to `4. Archives/`
7. Triggers incremental LightRAG indexing via `index_single_file()`

`news_ingest.py` and `fetch_papers.py` bypass the validation harness and write directly to `4. Archives/`.

### 2. The Active Brain (Tier 1)

`embed.py` is a **manual CLI script** (not a background watcher). Run it after adding or editing notes in `3. Resources/`:

```powershell
python embed.py          # incremental (new/changed/deleted)
python embed.py --reset  # full rebuild
```

It uses a hash-based manifest (`data/embed_manifest.json`) for atomic, resumable indexing. Chunks are produced by `utils.chunk_text()` (max 1500 chars, paragraph-aware). Embeddings are stored in `data/index.db` via `sqlite-vec` + `FTS5`.

### 3. The Archive Brain (Tier 2)

`index_archive.py` indexes files from `4. Archives/` into the LightRAG Knowledge Graph (stored in `.lightrag/`). Manifest is at `.lightrag/index_manifest.json`.

`watch_archive.py` runs as a background service that monitors `4. Archives/` with watchdog. On `.md` file changes it triggers `index_archive.py` after a 60-second debounce to avoid VRAM thrashing during bulk file moves.

Both tiers use `utils.chunk_text()` — the same paragraph-aware, char-bounded chunking strategy.

### 4. Retrieval — Two Independent Paths (NOT merged)

> ⚠️ The two brains are **not fused** during retrieval. They are exposed as separate, independent MCP tools.

| Tool | Source | Internal Logic |
|------|--------|----------------|
| `vault_search(query)` | `data/index.db` (Active Brain) | `query.py`: vector search + BM25 via FTS5, fused with RRF internally. Returns top-5 chunks with path, chunk index, RRF score, and 400-char preview. |
| `archive_search(query)` | `.lightrag/` (Archive Brain) | `index_archive.query_archive()`: LightRAG hybrid mode (local + global + graph traversal). Returns narrative text. |

`query.py`'s RRF fusion only operates **within** the Active Brain (merging vector and BM25 rankings). It does not touch LightRAG.

### 5. The MCP Bridge (`brain_server.py`)

Exposes the system to any MCP-compatible agent (Claude Desktop, Cursor, VS Code) via FastMCP (`BrainBridge` server).

| Tool | Read-Only | Destructive | Idempotent | Description |
|------|-----------|-------------|------------|-------------|
| `vault_search(query)` | ✅ | ❌ | ✅ | Hybrid search over Active Vault |
| `archive_search(query)` | ✅ | ❌ | ✅ | Semantic + graph search over Archives |
| `save_active_note(title, content)` | ❌ | ✅ | ❌ | Write a new note to `3. Resources/` |
| `brain_status()` | ✅ | ❌ | ✅ | GPU stats, indexed doc count, entity count |
| `review_queue(status_filter)` | ✅ | ❌ | ✅ | Validation queue contents (filter: all/pending_review/failed/skipped) |

Query length limit: 2000 characters. Note content limit: 100 KB.

### 6. AI Models

| Model | Role | Provider |
|-------|------|----------|
| `qwen3.5:4b-brain` | Entity extraction (LightRAG), Archive indexing | Ollama (Local) |
| `nomic-embed-text` | 768-dim text embeddings (both tiers) | Ollama (Local) |
| `gemini-2.0-flash` | Claims extraction fallback (validation harness) | Google Cloud |
| `qwen3.5:4b` | Claim validation (validation harness) | Ollama (Local) |
