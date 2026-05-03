# ZeroCostBrain — Sprint Log

> Each sprint runs AutoResearchClaw, produces a paper, archives it, and feeds findings back into the engine.
> Update this file at the end of every sprint.

---

## ✅ Sprint 1 — Cross-Encoder Reranking Survey
**Status:** Complete  
**Completed:** 2026-05-03  
**Topic:** Survey of cross-encoder reranking for hybrid BM25 + dense retrieval on CPU with sub-2-second latency

### What Was Researched
- State of cross-encoder models on CPU (MiniLM, TinyBERT, DistilBERT-based rerankers)
- Trade-off between reranking accuracy gain and latency cost on consumer hardware
- Integration patterns for reranking after RRF fusion

### Key Findings
- Small cross-encoders (MiniLM-L-6) achieve meaningful Precision@5 improvements (~8–12%) at ~200–400ms latency on CPU
- Reranking top-20 RRF candidates down to top-10 is the recommended configuration
- Flash attention + quantization not applicable to cross-encoders (they're typically FP32 on CPU)

### Action Item (Sprint 1 → Codebase)
- [ ] Implement cross-encoder reranker in `query.py` after RRF step
  - Candidate: `cross-encoder/ms-marco-MiniLM-L-6-v2` (SentenceTransformers)
  - Config: rerank top-`CANDIDATE_K` (10) results, return top-10
  - Latency target: <500ms on RTX 4050 (CPU inference)

### Artifacts
- Paper: `autoresearchclaw/artifacts/<sprint-1-run-id>/stage-17/paper_draft.md`
- Archived to: `knowledge_base/4. Archives/research/`
- Review queue: `knowledge_base/system/review-queue.jsonl`

---

## ⬜ Sprint 2 — Knowledge Graph Pruning Strategies
**Status:** Planned  
**Depends on:** Sprint 1 implementation (cross-encoder) complete  
**Topic:** Knowledge graph pruning strategies for personal knowledge management (PKM)

### Goal
Improve `index_archive.py` pruning pass. Currently `scripts/prune_graph.py` removes degree-0 nodes and short/numeric entities. Sprint 2 researches more principled pruning: weak-edge removal, duplicate entity merging, schema validation.

### Improves
- `index_archive.py` — automated pruning after indexing
- `scripts/prune_graph.py` — richer pruning strategies

---

## ⬜ Sprint 3 — Auto MOC Generation from Entity Graphs
**Status:** Planned  
**Depends on:** Sprint 2 complete  
**Topic:** Automatic generation of Maps of Content (MOCs) from LightRAG entity graphs

### Goal
New script that reads the LightRAG entity graph and auto-writes/updates MOC notes in `knowledge_base/2. Areas/` or `knowledge_base/3. Resources/`. Closes the loop between Archive Brain (LightRAG) and Active Brain (Obsidian vault).

### Improves
- New script: `generate_mocs.py`
- Closes gap in self-improvement loop: graph insights → vault notes → human-readable context

---

## ⬜ Sprint 4 — RAG-Based Portfolio Management
**Status:** Planned  
**Depends on:** Sprint 3 complete  
**Topic:** Using RAG over historical portfolio data and research papers for investment insight

### Goal
Extend the system to ingest portfolio/financial data (PDFs, CSVs, news) and enable agent-assisted portfolio reasoning over the archive. Revisit `docs/idea.md` open question about automated trading.

### Improves
- `docs/idea.md` — roadmap update with portfolio scope
- New ingestion pipeline for financial documents
