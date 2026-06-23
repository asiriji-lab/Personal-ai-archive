# Failure-Mode Verification — Evidence Table

> Companion to `docs/failure-mode-research.md`. That doc hypothesized 21 failure
> modes; this one turned the highest-value ones into **measured evidence**, then the
> **fix sprint** (`fix/retrieval-sprint`) resolved them. Verdicts below are updated to
> **FIXED** with before/after numbers; see "Fix sprint results" for the summary.
>
> Verification corpus: live `data/index.db` (920 chunks), branch `verify/failure-modes`.
> Eval: `eval/eval_queries.json` (17 recall + 3 negative). **Stale baseline:
> Recall@10 = 0.700, Precision@10 = 0.211** (6/17 recall queries fail: 03, 04, 07, 08,
> 10, 11). After the sprint, `recall_13`/`recall_17` (archive files) are tagged
> `expected_tier: 2` and excluded from the Tier-1 metric (archives are now Tier-2-only,
> by B1), so the post-fix recall is reported **over the 15 eligible recall queries**.

## Evidence table

| Finding | Verdict | Measured impact | Fix-priority |
|---|---|---|---|
| **NEW — embedding version drift (stale index)** | **Confirmed (severe)** | The live `index.db` vectors are NOT in the same space as today's model. Cosine of a stored vector vs a **fresh re-embed of the identical text = 0.80–0.90** (would be ~1.0 if versions matched); `embedder` column reads `nomic-embed-text` for both, so the model drifted under the same Ollama tag. Re-embedding the same 920 chunks lifts recall@10 (17 recall queries) from **0.647 → 0.941 (+0.294)**, fixing 5 of 6 failures. Query embeddings are computed fresh at query time, so they silently mismatch the stale stored vectors. Extends **B4** (model recorded by name only; `query.py` never checks it). | **P0** |
| **C3** — nomic-embed-text task prefixes missing | **Refuted** | Controlled A/B on the same 920 chunks: CONTROL (no prefix) recall@10 = **0.941**, TREATMENT (`search_document:`/`search_query:`) = **0.941**, **Δ 0.000**, identical on every query and on all 3 negatives. Adding task prefixes does **not** improve recall on this corpus; the real query/doc space mismatch is version drift (above), not prefixes. | **Drop** |
| **C5** — verbose queries silently disable BM25 (FTS5 implicit AND) | **Confirmed (severe)** | **BM25 returned 0 hits on 19/20 eval queries** (only `recall_14` got 1). "Hybrid" search is effectively **vector-only**; BM25's rare-term/acronym advantage is absent everywhere. | **P0** |
| **B1** — archives double-indexed into Tier-1 | **Confirmed** | **843/920 chunks (92%) are `4. Archives/*`** (442 distinct files). Two write paths: `_SKELETON_DIRS` includes `ARCHIVE_PATH` (`config.py:75`) **and** `index_archive.py::_index_pipeline_b` (`index_archive.py:340-397`). Contradicts the documented "archives NOT indexed here" (`embed.py:7`); wastes compute; pollutes Tier-1. | **P0** |
| **D1** — short embedding list silently drops chunks | **Confirmed** | Fault-injected `get_embeddings → len-1` vectors: trailing chunk **dropped, no error, file still recorded complete in manifest** (`test_failure_modes.py::test_d1...`). Permanent invisible recall hole; never retried. | **P0** |
| **D2** — non-UTF-8 file aborts the whole Tier-1 run | **Confirmed** | A latin-1 `.md` raises `UnicodeDecodeError` (a `ValueError`, **not** caught by `except OSError` at `embed.py:226-229`) → entire run aborts, partial index (`test_failure_modes.py::test_d2...`). Tier-2 swallows the same error (`except Exception`), so the tiers are inconsistent. | **P1** |
| **C6** — no relevance floor in `search()` | **Confirmed** | All 3 `negative_*` queries return **10 chunks** with top RRF = **0.01639**. Positives: top RRF min 0.01639 / max 0.03132 / avg 0.01727. The only floor (`0.018`) lives in the eval harness (`run_eval.py:28`), not in `search()` — so MCP `vault_search`/`archive_search` always return junk for off-topic questions. | **P1** |
| **C1** — chunks carry no provenance; only chunk 0 has the header | **Confirmed** | **431/920 chunks (47%) are not `chunk_index==0`** and carry no title/date/source. `chunks` columns are only `path, chunk_index, content, embedder, indexed_at`; `query.py:137-149` returns only `path, chunk_index, content`. No date/source/category filtering possible. | **P1** |
| **C4** — RRF never over-retrieves (`CANDIDATE_K == TOPK == 10`) | **Confirmed as coded, but no impact yet** | Static: `query.py:23-24` equal. Sweep `CANDIDATE_K=50` (final k=10): recall **0.647 → 0.647 (Δ 0.000)**. **Masked by C5** — over-retrieving a dead BM25 list changes nothing. Becomes meaningful only after C5 is fixed. | **P2 (after C5)** |

## Fix sprint results (`fix/retrieval-sprint`)

All P0/P1/P2 findings above are now **FIXED** (one commit each). Tier-1 recall is
measured over the 15 eligible queries (archives excluded — Tier-2-only). Stale
baseline → final: **Recall@10 0.700 → 1.000**, **Precision@10 0.211 → 0.296**.

| Finding | Verdict | Fix + before/after |
|---|---|---|
| Embedding drift | **FIXED** | `embed.py --reset` re-embed; recall 0.700 → 1.000. |
| B1 (archives in Tier-1) | **FIXED** | Dropped `ARCHIVE_PATH` from `_SKELETON_DIRS`; pipeline B routes to LightRAG. Archive chunks 843 → **0**; Tier-1 920 → 60 → 154 chunks (154 after C1 section-splitting). |
| B4 (no model guard) | **FIXED** | `index_meta` records model + sha256 digest at index time; `query.py` warns once on query-time mismatch (ASCII-safe). |
| C5 (BM25 dead) | **FIXED** | `_fts5_query` OR-over-significant-tokens. BM25 hit-rate **1/20 → 19/20**. |
| D1 (silent chunk drop) | **FIXED** | Assert `len(embeddings)==len(chunks)`; mismatch → no write, no manifest entry, logged to `index_failures.json`. Test flipped. |
| D2 (non-UTF-8 abort) | **FIXED** | Read guard widened to `(OSError, UnicodeDecodeError)` → skip+log. Test flipped. |
| C6 (no relevance floor) | **FIXED** | `MIN_RRF_SCORE = 0.0310` in `search()`; all 3 negatives now return `[]`. |
| C1 (no provenance) | **FIXED** | `title/section/source/date` columns + section-aware chunking + `title › section` breadcrumb in embedded text. title 154/154, section 122/154. Precision 0.266 → 0.311 (0.296 after C4). |
| C4 (no over-retrieve) | **FIXED** | `CANDIDATE_K = 50`; meaningful now BM25 is alive. Recall stays 1.000. |
| C3 (nomic prefixes) | **Dropped** | Measured Δ 0.000 in verification — not implemented. |

> **Note on the floor (C6).** RRF scores cluster tightly (rank-agreement, not
> similarity): at `CANDIDATE_K=50` negatives top ~0.03078, positives floor ~0.03132.
> The 0.0310 floor sits between them with a small margin — robust on this eval but
> worth revisiting with a raw vector-distance floor if the corpus grows.

## What to fix first (historical — verification round)

1. **Re-embed the corpus (P0) — biggest, nearly-free win.** The live index is
   model-version-stale; a plain `python embed.py --reset` lifts recall@10 from
   **0.647 → 0.941 (+0.294)** on this eval set, no code change. **Bundle B1 into the
   same pass** (drop `ARCHIVE_PATH` from `_SKELETON_DIRS` and the `_index_pipeline_b`
   archive write) so the 92%-archive pollution is removed in the one re-embed.
   *Do **not** add nomic prefixes — C3 measured Δ 0.000.* Then add a guard so this
   can't recur: store the embed model **version/digest**, and have `query.py` warn
   (or refuse) when the query-time model differs from the index-time one (closes B4).
2. **C5 (P0) — unlock BM25.** It's dead on 95% of queries, so the system is
   vector-only despite the "hybrid" label. Switch `_fts5_query` to OR semantics over
   significant tokens (drop stopwords, keep rare terms, quote only real phrases).
   This restores the rare-term/acronym path and **unblocks C4**.
3. **D1 (P0):** assert `len(embeddings) == len(chunks)`; fail the file into the
   failures log instead of silently truncating + lying in the manifest.
4. **D2 / C6 / C1 (P1):** catch `(OSError, UnicodeDecodeError)` (or read with
   `errors="replace"`); add a min-score gate in `search()`; lift front-matter into
   real columns + a `title › section` breadcrumb per chunk.
5. **C4 (P2):** bump `CANDIDATE_K` to ~50–100 — but only revisit *after* C5, since
   today it measurably does nothing.

> **Note on the headline numbers.** The 0.700 / 0.647 baselines were measured against
> the *stale* live index. Re-baseline after the re-embed (#1) — the absolute recall
> figures for C5/C4/C6 will shift, but their *direction* (BM25 dead, no floor, C4
> masked) holds because those are structural, not embedding-quality, issues.

## Not verified this round (gated / deferred)

**C3 was run and refuted (above).** Remaining Tier-4 items left for a follow-up
(LightRAG runs / chunker rework): **A1** (chunk-overlap sweep) and **B2** (LightRAG
stale-graph persistence — note B2 is already near-certain by inspection: `index_archive.py`
has no delete-by-doc path, unlike `embed.py::_purge_chunks`). Also not measured:
A2/A3/A4/A5 (mischunking), B3/B5, C2, C7, D3, D4. **B4** is now partially evidenced via
the version-drift finding above.

## How to reproduce

- B1 / C1: SQL over `data/index.db` (`COUNT … WHERE path LIKE '4. Archives/%'`;
  `COUNT … WHERE chunk_index=0`).
- D1 / D2: `python -m pytest tests/test_failure_modes.py -v`.
- Baseline: `python eval/run_eval.py --tier 1`.
- C5 / C4 / C6: `probe_tier3.py` (read-only; re-embeds queries via Ollama).
- C3 + version-drift: `probe_c3.py` (rebuilds two temp DBs from the live chunk set,
  control vs prefixed; reports recall@10 and the stored-vs-fresh cosine). Writes only
  to temp DBs — the real `index.db` is untouched.
