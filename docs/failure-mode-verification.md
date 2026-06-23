# Failure-Mode Verification — Evidence Table

> Companion to `docs/failure-mode-research.md`. That doc hypothesized 21 failure
> modes; this one turns the highest-value ones into **measured evidence**. This
> round **verifies only — no production code was fixed.** The table below scopes
> the fix sprint.
>
> Branch: `verify/failure-modes`. Corpus: live `data/index.db` (920 chunks).
> Eval: `eval/eval_queries.json` (17 recall + 3 negative). Baseline run:
> **Recall@10 = 0.700, Precision@10 = 0.211** (6/17 recall queries fail: 03, 04,
> 07, 08, 10, 11). `data/index.db` was confirmed byte-identical before/after all
> read-only probes.

## Evidence table

| Finding | Verdict | Measured impact | Fix-priority |
|---|---|---|---|
| **C5** — verbose queries silently disable BM25 (FTS5 implicit AND) | **Confirmed (severe)** | **BM25 returned 0 hits on 19/20 eval queries** (only `recall_14` got 1). "Hybrid" search is effectively **vector-only**; BM25's rare-term/acronym advantage is absent everywhere. | **P0** |
| **B1** — archives double-indexed into Tier-1 | **Confirmed** | **843/920 chunks (92%) are `4. Archives/*`** (442 distinct files). Two write paths: `_SKELETON_DIRS` includes `ARCHIVE_PATH` (`config.py:75`) **and** `index_archive.py::_index_pipeline_b` (`index_archive.py:340-397`). Contradicts the documented "archives NOT indexed here" (`embed.py:7`); wastes compute; pollutes Tier-1. | **P0** |
| **D1** — short embedding list silently drops chunks | **Confirmed** | Fault-injected `get_embeddings → len-1` vectors: trailing chunk **dropped, no error, file still recorded complete in manifest** (`test_failure_modes.py::test_d1...`). Permanent invisible recall hole; never retried. | **P0** |
| **D2** — non-UTF-8 file aborts the whole Tier-1 run | **Confirmed** | A latin-1 `.md` raises `UnicodeDecodeError` (a `ValueError`, **not** caught by `except OSError` at `embed.py:226-229`) → entire run aborts, partial index (`test_failure_modes.py::test_d2...`). Tier-2 swallows the same error (`except Exception`), so the tiers are inconsistent. | **P1** |
| **C6** — no relevance floor in `search()` | **Confirmed** | All 3 `negative_*` queries return **10 chunks** with top RRF = **0.01639**. Positives: top RRF min 0.01639 / max 0.03132 / avg 0.01727. The only floor (`0.018`) lives in the eval harness (`run_eval.py:28`), not in `search()` — so MCP `vault_search`/`archive_search` always return junk for off-topic questions. | **P1** |
| **C1** — chunks carry no provenance; only chunk 0 has the header | **Confirmed** | **431/920 chunks (47%) are not `chunk_index==0`** and carry no title/date/source. `chunks` columns are only `path, chunk_index, content, embedder, indexed_at`; `query.py:137-149` returns only `path, chunk_index, content`. No date/source/category filtering possible. | **P1** |
| **C4** — RRF never over-retrieves (`CANDIDATE_K == TOPK == 10`) | **Confirmed as coded, but no impact yet** | Static: `query.py:23-24` equal. Sweep `CANDIDATE_K=50` (final k=10): recall **0.647 → 0.647 (Δ 0.000)**. **Masked by C5** — over-retrieving a dead BM25 list changes nothing. Becomes meaningful only after C5 is fixed. | **P2 (after C5)** |

## What to fix first

1. **C5 (P0) is the keystone.** BM25 is dead on 95% of queries, so the system is a
   single-retriever (vector) engine wearing a "hybrid" label. Switch `_fts5_query`
   to OR semantics over significant tokens (drop stopwords, keep rare terms, quote
   only real phrases). This is the single highest-leverage change and it **unblocks
   C4** — only after BM25 contributes does a larger `CANDIDATE_K` matter.
2. **B1 (P0):** stop writing `4. Archives/*` into Tier-1 — drop `ARCHIVE_PATH` from
   `_SKELETON_DIRS` and the `_index_pipeline_b` archive write. Re-embed Tier-1 after,
   then re-baseline (recall numbers above will shift once 92% of the index changes).
3. **D1 (P0):** assert `len(embeddings) == len(chunks)`; fail the file into the
   failures log instead of silently truncating + lying in the manifest.
4. **D2 / C6 / C1 (P1):** catch `(OSError, UnicodeDecodeError)` (or read with
   `errors="replace"`); add a min-score gate in `search()`; lift front-matter into
   real columns + a `title › section` breadcrumb per chunk.
5. **C4 (P2):** bump `CANDIDATE_K` to ~50–100 — but only revisit *after* C5, since
   today it measurably does nothing.

## Not verified this round (gated / deferred)

Tier-4 items require a re-embed or LightRAG runs and were **left for a follow-up**
per the brief (ask before any big re-embed): **C3** (nomic `search_document:` /
`search_query:` prefixes A/B), **A1** (chunk-overlap sweep), **B2** (LightRAG stale-graph
persistence). Also not measured: A2/A3/A4/A5 (mischunking), B3/B4/B5, C2, C7, D3, D4.

## How to reproduce

- B1 / C1: SQL over `data/index.db` (`COUNT … WHERE path LIKE '4. Archives/%'`;
  `COUNT … WHERE chunk_index=0`).
- D1 / D2: `python -m pytest tests/test_failure_modes.py -v`.
- Baseline: `python eval/run_eval.py --tier 1`.
- C5 / C4 / C6: `scratchpad/probe_tier3.py` (read-only; re-embeds queries via Ollama).
