# Two‑Tier Virtual Brain: Active + Archive Architecture

## Core Goal
Build a personal knowledge system that acts like a human brain: a fast, lightweight **Active Brain** for daily thinking and note‑taking, and a deep, queryable **Archive Brain** for long‑term memory and cross‑field discovery. The entire system must run **locally with zero API costs**, preserve **privacy**, and be **modular** for future AI agents.

## The Two Tiers

### Active Brain (Obsidian Vault)
- **Role**: Fast, daily decision‑making, note creation, and human review.
- **Content**: Maps of Content (MOCs), fleeting notes, active project notes.
- **Organization**: PARA (Projects, Areas, Resources, Archives) + Zettelkasten (atomic, linked notes).
- **Interface**: Human uses Obsidian directly; AI agents can read/write via an MCP server.

### Archive Brain (LightRAG + RAG‑Anything)
- **Role**: Long‑term storage, semantic search, and discovery of non‑obvious connections.
- **Content**: All historical notes, raw data, parsed financial documents, past failures/successes.
- **Engine**: 
  - **LightRAG** provides hybrid search (BM25 + vector embeddings + knowledge graph) and is 10x faster than GraphRAG.
  - **RAG‑Anything** parses multimodal inputs (PDFs, news, charts, images) into structured data.
- **Access**: AI agents query LightRAG via MCP; results are summarized and pushed to Active Brain.

## Bridge Between Tiers: MCP Server + Local LLM
- **MCP (Model Context Protocol) server** acts as a standardized API for all tools.
- **Local LLM (Ollama + small model like Qwen 2.5 7B or Llama 3.2 3B)** handles “dirty work”: query rewriting, summarization, drafting notes, reranking search results.
- **Cost**: Zero API credits. All models run on local CPU/GPU.

## Retrieval Pipeline (Ensuring Relevance)
1. **Query understanding** (local LLM or simple keyword extraction).
2. **Three parallel retrieval channels**: keyword (BM25), vector (semantic), graph (neighbors).
3. **Hybrid fusion** (Reciprocal Rank Fusion) + optional local reranking (cross‑encoder).
4. **Active Brain filtering**: MOCs boost relevant notes.
5. **Meta‑Cognition Agent** (local LLM) refines failed queries.

## Key Design Decisions (Already Made)
- Use LightRAG instead of a raw vector database.
- Use RAG‑Anything for document parsing.
- Build a custom MCP server with local LLM for retrieval and drafting.
- Handle contradictory research via confidence‑weighted voting, regime detection, and human‑in‑the‑loop.
- Obsidian is the **only** user interface; AI agents are background assistants.

## Current Constraints
- Zero recurring cost (no API keys).
- All data stays on local machine.
- Low latency for retrieval (target <2s).
- Human reviews all significant decisions (trading or critical insights).

## Open Questions (Not Yet Solved)
- Optimal pruning strategy for the Archive Brain as it grows.
- How to automatically generate/update MOCs from LightRAG insights.
- Best local reranking model for zero‑cost retrieval.
- Whether the system can be extended to automated trading (currently focused on portfolio management with human oversight).

## Next Steps (What We Are About to Do)
1. Install Ollama and pull a small model (e.g., `qwen2.5:7b`).
2. Set up LightRAG to index the Obsidian vault.
3. Build a minimal MCP server with tools: `search_notes`, `draft_note`, `get_session_context`.
4. Test hybrid retrieval with local embeddings.
5. Iterate based on retrieval quality.

## How You Can Help
You are now another LLM being given this context. Please read it carefully. I will then ask you to help me with a specific part of the implementation (e.g., writing the MCP server code, designing a MOC generation script, or debugging retrieval quality). Do not assume anything outside this description. Ask clarifying questions if needed.