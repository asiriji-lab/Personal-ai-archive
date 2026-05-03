# Two-Tier Virtual Brain — Vision & Design Rationale

> **Status:** System is built and running. This document explains WHY the design decisions were made, not what to do next.
> For current status and bug history, see `dev_log.md`. For sprint tracking, see `SPRINT_LOG.md`.

---

## Core Goal

A personal knowledge system that acts like a human brain: a fast, lightweight **Active Brain** for daily thinking and note-taking, and a deep, queryable **Archive Brain** for long-term memory and cross-field discovery.

**Three non-negotiable constraints:**
1. **Zero recurring cost** — no API keys, no cloud services.
2. **All data on local machine** — privacy absolute.
3. **Low latency** — retrieval target <2 seconds.

---

## The Two Tiers (Why This Architecture)

### Active Brain (Obsidian + SQLite-vec)
- **Why Obsidian:** The only interface the user touches daily. PARA organization maps directly to how humans think about projects. Zettelkasten atomic notes are the right granularity for LLM retrieval.
- **Why SQLite-vec:** Zero infrastructure. Runs in-process. Good enough for Tier 1 (vault notes are small, dense, and frequently changing).
- **Why BM25 + vector + RRF:** Neither BM25 nor pure vector search is reliably better alone. RRF fusion is deterministic, requires no training, and consistently outperforms either alone for this use case.

### Archive Brain (LightRAG)
- **Why LightRAG over raw vector DB:** Graph traversal finds connections you didn't know to ask for. Named entity queries (e.g., "everything about cross-encoder reranking") work correctly because the graph preserves relationships between entities, not just proximity in embedding space.
- **Why nomic-embed-text (768-dim) over bge-m3 (1024-dim):** Fits in RAM, runs fast on CPU, sufficient quality. The 768-dim model was chosen after Bug 4 (LightRAG hardcodes 1024-dim in `ollama_embed`). See `Known_Bugs_and_Fixes.md`.
- **Why Qwen 3.5:4b over larger models:** The only local model that fits in 6GB VRAM with room for KV cache. Q4_K_M quantization = 3.4GB. 7B+ models swap to CPU, destroying throughput.

---

## The Self-Improvement Loop (The Core Insight)

The system is not just a knowledge store — it is designed to research its own improvement:

```
Open question → AutoResearchClaw → Paper → Validate → Archive → LightRAG index → Better answers → Implement → New question
```

Each sprint uses the brain to research how to make the brain better. Sprint 1 researched reranking → findings feed into `query.py`. Sprint 2 will research graph pruning → findings feed into `index_archive.py`.

---

## Key Design Decisions (Locked In)

| Decision | Why | Alternatives Rejected |
|----------|-----|----------------------|
| LightRAG for archive | Graph traversal for named entities | Raw vector DB — no relationship traversal |
| SQLite-vec for vault | Zero infrastructure | Chroma, Weaviate — overkill for local use |
| Custom MCP server | Standard protocol for agent integration | Direct function calls — not portable |
| Chunk at 1500 chars | Hardware-derived from RTX 4050 at 15 tok/s | 4000 chars → timeouts (Bug 5) |
| Qwen 3.5:4b-brain | Custom model, thinking OFF | Base model → indexing impossible (Bug 7) |
| Obsidian as sole UI | Human-in-the-loop by design | Custom UI — unnecessary complexity |

---

## Open Questions (Still Unresolved as of 2026-05-04)

| Question | Sprint Targeting It |
|----------|-------------------|
| Optimal automated pruning strategy as graph scales | Sprint 2 |
| How to auto-generate/update MOCs from LightRAG entities | Sprint 3 |
| Best local reranking model for zero-cost retrieval | Sprint 1 findings → Sprint 2 pre-work |
| Whether system can extend to automated trading | Sprint 4 (scope TBD) |

---

*This document is design rationale, not a how-to guide.*
*Setup: `docs/setup_brain.md` | Engineering log: `docs/dev_log.md` | Sprint tracking: `docs/SPRINT_LOG.md`*