# Failure-Mode Research: What Can Make the Brain Go Haywire

> A researcher's catalog of the things that can break retrieval quality in
> ZeroCostBrain — mischunking, wrong indexing, missing-metadata retrieval, and
> silent failures. Each finding is grounded in the actual code (`file:line`),
> explains *why* it goes haywire, and gives a concrete way to **test/verify** it
> plus a few mitigation ideas. **This document changes no code.**

## How to read this

Each finding uses the same template:

- **Symptom** — what you'd observe.
- **Root cause** — the code responsible, with `file:line`.
- **Why it goes haywire** — the failure mechanism.
- **Test / verify** — how to prove it's real.
- **Ideas** — possible directions (not prescriptions).

Findings are tagged by **impact × confidence**: **[High]**, **[Med]**, **[Low]**.

## The system in one breath

Two memory tiers share a chunker (`utils.py::chunk_text`):

- **Tier 1 — vault search.** `embed.py` scans markdown, chunks it, embeds via Ollama
  `nomic-embed-text`, and stores vectors in **sqlite-vec** plus a **FTS5** full-text
  index. `query.py` runs vector + BM25 search and fuses them with **Reciprocal Rank
  Fusion (RRF)**.
- **Tier 2 — knowledge graph.** `index_archive.py` chunks the `4. Archives` folder and
  feeds the chunks into **LightRAG**, which extracts entities/relationships.
- **Ingestion.** `fetch_papers.py` and `news_ingest.py` write markdown files with a
  metadata header block. `scripts/validate_and_archive.py` is a claim-validation gate
  that sits before archiving/indexing.

## Priority summary

| ID | Area | Finding | Impact |
|----|------|---------|--------|
| A1 | Mischunking | Zero chunk overlap — boundary facts lost | High |
| A3 | Mischunking | Markdown structure ignored — tables/code shredded | High |
| A4 | Mischunking | Double-chunking defeats LightRAG entity extraction | High |
| B1 | Indexing | Archives double-indexed into both tiers | High |
| B2 | Indexing | LightRAG never purges deleted/changed docs | High |
| C1 | Metadata | Chunks carry no metadata; only chunk 0 has provenance | High |
| C3 | Retrieval | nomic-embed-text task prefixes missing | High |
| C4 | Retrieval | RRF never over-retrieves (`CANDIDATE_K == TOPK`) | High |
| C5 | Retrieval | Verbose queries silently disable BM25 (implicit AND) | High |
| C6 | Retrieval | No relevance threshold — junk returned for off-topic queries | High |
| D1 | Silent | Embedding count < chunk count silently drops chunks | High |
| D2 | Silent | `UnicodeDecodeError` aborts the whole Tier-1 run | High |
| A2 | Mischunking | Hard mid-word cut for long sentences | Med |
| B3 | Indexing | Tier-1/Tier-2 manifests use inconsistent path keys | Med |
| B4 | Indexing | Embedding-dimension / model mismatch unguarded | Med |
| C2 | Metadata | Boilerplate headers pollute embeddings and BM25 | Med |
| C7 | Retrieval | Tier-2 (LightRAG) retrieval quality is unmeasured | Med |
| D3 | Silent | Validator passes "skipped" claims into the archive | Med |
| A5 | Mischunking | Char-based budget vs token-based model limits | Low |
| B5 | Indexing | MD5 over raw bytes → cosmetic edits force full re-embed | Low |
| D4 | Silent | Manifest/DB sync edge cases on interrupt | Low |

---

## A. Mischunking

The chunker `chunk_text` (`utils.py:42`) splits on paragraph boundaries (`\n\n`), falls
back to sentence boundaries, then hard-cuts. It is shared by **both** tiers.

### A1. Zero chunk overlap — facts on a boundary are lost  **[High]**

- **Symptom:** a fact that exists in the corpus is never retrieved, even with the right
  keywords.
- **Root cause:** `chunk_text` (`utils.py:42`) flushes `current_chunk` and starts a
  fresh empty one; there is no overlap window. A sentence/fact split across the boundary
  lands half in chunk *n* and half in *n+1*, so neither chunk independently contains the
  full fact.
- **Why it goes haywire:** the answer span is silently truncated; both vector and BM25
  search score each half-chunk poorly because the complete fact appears in neither.
- **Test / verify:** craft a doc where a unique fact (e.g. "the Leiden algorithm runs in
  12.4ms") straddles a 1500-char boundary; index it; query for the fact; check whether
  any single returned chunk contains the whole thing. Then sweep overlap = 0 / 100 / 200
  chars and measure recall@10 on `eval/eval_queries.json` via `eval/run_eval.py`.
- **Ideas:** add a sliding overlap (~10–15% of `max_chars`); or sentence-window
  retrieval (embed sentences, return neighbors at query time).

### A2. Hard mid-word cut for long sentences  **[Med]**

- **Symptom:** chunks that end/begin mid-word or mid-token; poor matches on long URLs,
  code, or unpunctuated text.
- **Root cause:** `utils.py:69` slices `sentence[i : i + max_chars]` by raw character
  count — cutting mid-word, mid-URL, mid-token.
- **Why it goes haywire:** broken tokens degrade the chunk's embedding and pollute the
  BM25 index with word fragments that match nothing useful.
- **Test / verify:** feed a doc containing one 3000-char "sentence" (a long code line,
  base64 blob, or URL list); print the resulting chunks and inspect the boundaries.
  Compare the embedding cosine of the two halves against the whole.
- **Ideas:** before a hard cut, back off to the nearest word/whitespace boundary.

### A3. Markdown structure is ignored — tables/code/lists shredded  **[High]**

- **Symptom:** retrieved chunks contain half a table, a code block missing its opening
  fence, or two unrelated topics mashed together.
- **Root cause:** `chunk_text` only knows `\n\n` and a sentence regex (`utils.py:52-79`).
  It has no notion of markdown tables, fenced code blocks, lists, or headings. Tables and
  code get split arbitrarily; small paragraphs from *different* `##` sections get merged
  into one chunk.
- **Why it goes haywire:** a half-table or fenceless code block is close to meaningless
  to the LLM, and merging across section boundaries blends unrelated topics into one
  embedding.
- **Test / verify:** index a paper produced by `fetch_papers.py` and a doc containing a
  markdown table; dump the chunks; count how many split a fenced code block or a table
  row group. Cross-check with eval doc `recall_13` (`graphify.md`), which describes a
  tool with structured content.
- **Ideas:** a structure-aware splitter that keeps code fences and tables atomic and
  prefers `#`/`##` boundaries before paragraph boundaries.

### A4. Double-chunking before LightRAG defeats entity extraction  **[High]**

- **Symptom:** the knowledge graph has fewer entities/relationships than the source
  material warrants; cross-section relationships are missing.
- **Root cause:** `index_archive.py:263-265` calls `chunk_text(...)` and then
  `await rag.ainsert(chunk)` **once per chunk**. LightRAG already performs its own
  chunking and entity extraction; handing it pre-sliced 1500-char fragments means
  extraction runs on fragments and loses cross-chunk / document-level context.
- **Why it goes haywire:** Tier 2's whole value is the graph; fragmenting the input
  starves entity/relationship extraction of context and produces a weaker graph.
- **Test / verify:** index one document two ways — (a) current pre-chunked, and (b) a
  single `ainsert(full_text)` — then compare entity/edge counts in the LightRAG working
  dir graph files and spot-check whether cross-section relationships survive.
- **Ideas:** insert whole documents and let LightRAG chunk; or use a larger
  `CHUNK_MAX_CHARS` only on the Tier-2 path.

### A5. Char-based budget vs token-based model limits  **[Low]**

- **Symptom:** inconsistent "amount of meaning" per chunk across content types.
- **Root cause:** `CHUNK_MAX_CHARS=1500` (`config.py:45`) counts characters, but the
  embed model is token-bounded (`max_token_size=8192`, `index_archive.py:197`). For dense
  text (CJK, code), chars↔tokens shifts, so "1500 chars" varies in token terms.
- **Test / verify:** tokenize a sample of chunks; plot chars→tokens across English prose,
  code, and non-Latin text; observe the variance.
- **Ideas:** budget by tokens, or at least document the char assumption.

---

## B. Indexing correctness

### B1. Archives are double-indexed into BOTH tiers  **[High]**

- **Symptom:** Tier-1 `vault_search` returns chunks from `4. Archives`, which it is not
  supposed to own; archive content is embedded twice.
- **Root cause:** `embed.py`'s docstring states "Archives are NOT indexed here — they go
  through LightRAG," but `index_resources` iterates `_SKELETON_DIRS` (`config.py:67-73`),
  and that list **includes `ARCHIVE_PATH` (`4. Archives`)**. So archive files are embedded
  into sqlite-vec (Tier 1) *and* fed to LightRAG (Tier 2).
- **Why it goes haywire:** it contradicts the documented architecture, wastes compute,
  pollutes Tier-1 results with archive material, and muddies eval (a query can be answered
  by the "wrong" tier).
- **Test / verify:** run `embed.py`, then query the DB:
  `SELECT DISTINCT path FROM chunks WHERE path LIKE '4. Archives/%'` against
  `data/index.db`. Any rows confirm the double-index.
- **Ideas:** drop `ARCHIVE_PATH` from `_SKELETON_DIRS`, or give Tier-1 an explicit
  resources-only scan list.

### B2. LightRAG never purges deleted or changed documents  **[High]**

- **Symptom:** querying the graph returns facts from documents that were deleted or
  edited long ago; contradictory facts coexist.
- **Root cause:** `index_archive.py` only adds/updates the manifest hash
  (`index_archive.py:332-369`). There is no deletion path (unlike `embed.py::_purge_chunks`
  at `embed.py:134`), and on a *changed* file it simply re-inserts chunks
  (`index_archive.py:263-265`). Old entities/relationships from the previous version
  remain in the graph.
- **Why it goes haywire:** the graph accumulates **stale and contradictory facts**. Edit a
  doc from "X is true" to "X is false," re-index, and both survive — the canonical
  "go haywire" scenario.
- **Test / verify:** index doc v1 (claim X) → query → edit the file to assert NOT-X →
  re-index → query. If both appear, confirmed. Separately, delete an indexed file, re-run,
  and query — the stale data persists.
- **Ideas:** track per-document IDs and call LightRAG's delete-by-doc on change/delete; or
  schedule a periodic full rebuild via `--reset`.

### B3. Tier-1 vs Tier-2 manifests use inconsistent path keys  **[Med]**

- **Symptom:** moving the vault or switching OS triggers a surprise full re-index of
  Tier 2, or creates duplicate graph content.
- **Root cause:** `embed.py` keys its manifest by **relative posix** path
  (`embed.py:169`), while `index_archive.py` keys by **absolute** `str(file_path)` from
  `glob` (`index_archive.py:333-336`). Absolute keys break when the vault moves and differ
  across Windows/posix separators.
- **Why it goes haywire:** the manifest can no longer match files to prior hashes, so
  everything looks "new" → full re-index (cost) or duplicates.
- **Test / verify:** record the Tier-2 manifest, move the vault directory, re-run; observe
  the "new/changed" count jump to the total file count.
- **Ideas:** store relative-to-`VAULT_PATH` posix keys in both manifests.

### B4. Embedding-dimension / model mismatch is unguarded  **[Med]**

- **Symptom:** insert errors after changing the embed model, or silently nonsensical
  rankings.
- **Root cause:** the schema hardcodes `vec0(embedding float[768])`
  (`data/schema.sql:15`) for `nomic-embed-text`, but `BRAIN_EMBED_MODEL` is user-overridable
  (`config.py:35`) with no dimension check. The `embedder` column is recorded
  (`embed.py:240`) but `query.py` never filters on it.
- **Why it goes haywire:** switching to a different-dimension model without `--reset` makes
  `pack_embedding` (`embed.py:92`) produce wrong-size blobs (insert error/corruption), or
  mixes geometrically incomparable vectors in one table → meaningless distances.
- **Test / verify:** set `BRAIN_EMBED_MODEL` to a model with a different dimension, run
  `embed.py` without `--reset`, and observe the error or the silently mixed-dim DB; then
  query and inspect ranking sanity.
- **Ideas:** assert `len(emb) == 768` (or read the dim from the model) before insert;
  refuse to mix embedders in one DB; namespace the DB by model name.

### B5. MD5 over raw bytes → cosmetic edits force full re-embed  **[Low]**

- **Symptom:** trivial whitespace edits cause a full re-embed of a file.
- **Root cause:** `file_hash` (`utils.py:126`) hashes raw bytes, so a trailing-newline
  change alters the hash.
- **Test / verify:** touch a trailing newline on an indexed file; re-run; confirm it is
  re-indexed.
- **Ideas:** hash normalized content if embedding cost becomes a concern.

---

## C. Metadata & retrieval (the central concern)

### C1. Chunks carry NO metadata; only chunk 0 has provenance  **[High]**

- **Symptom:** you can't filter by date/source/category, and a retrieved middle chunk
  gives no clue which document, section, or date it came from.
- **Root cause:** the `chunks` table stores only `path, chunk_index, content, embedder`
  (`data/schema.sql:5-12`). Ingested files put title/arxiv-id/authors/date/category in a
  **header block** at the top of the file (`fetch_papers.py:213-219`,
  `news_ingest.py:119-127`). After chunking, that header lives **only in chunk 0**; chunks
  1..n contain no title, source, date, or section. `query.py` returns just
  `path, chunk_index, content` (`query.py:137-149`).
- **Why it goes haywire:** this is precisely the user's "can't retrieve because there's no
  metadata." There's no way to filter by date/category/source; a middle chunk is
  unattributable; and a query like "what did the 2026 arXiv paper on X say" cannot bias
  toward `arXiv`/`2026` because those tokens aren't present in the body chunks.
- **Test / verify:** index a multi-chunk paper; retrieve a middle chunk; check whether its
  row lets you recover title/date/section. Then attempt a date- or source-scoped query and
  observe there's no mechanism to honor it.
- **Ideas:** parse the front-matter/header into real columns (title, source, date,
  category, section heading); prepend a compact `title › section` breadcrumb to each
  chunk's embedded text; surface metadata in `search()` results and allow filtering.

### C2. Boilerplate headers pollute embeddings and BM25  **[Med]**

- **Symptom:** off-target matches on structural words; many documents look similar in
  vector space.
- **Root cause:** every ingested file repeats `**Category:**`, `**Ingested:**`,
  `**Source:**`, `**PDF:**`, `## Summary`, etc. (`news_ingest.py:119-127`,
  `fetch_papers.py:213-219`). Hundreds of near-identical headers crowd the vector space and
  add BM25 noise — every doc "matches" *category*, *ingested*, *source*.
- **Why it goes haywire:** structural words create false matches and reduce the separation
  between genuinely different documents.
- **Test / verify:** BM25-query a boilerplate word ("category", "ingested") and count
  matches; measure pairwise cosine similarity of chunk-0 embeddings across many news files
  (expect suspiciously high similarity).
- **Ideas:** strip header boilerplate from the embedded text (keep it as metadata only);
  embed title + body rather than the decorative block.

### C3. nomic-embed-text task prefixes are missing  **[High]**

- **Symptom:** retrieval is systematically weaker than it should be, across all queries.
- **Root cause:** documents (`embed.py:80`) and queries (`query.py:47`) are embedded with
  **no** `search_document:` / `search_query:` prefix. `nomic-embed-text` is trained to
  expect these task prefixes; omitting them is a known, measurable retrieval hit and leaves
  query/doc embeddings in a slightly mismatched space.
- **Why it goes haywire:** it imposes a silent ceiling on vector recall for every query.
- **Test / verify:** A/B with `eval/run_eval.py` — current vs prefixed embeddings (the
  prefixed arm requires re-embedding the corpus). Compare recall@10 / precision@10. Cheap,
  high signal.
- **Ideas:** add `search_document:` at index time and `search_query:` at query time (needs
  a coordinated re-index so both sides match).

### C4. RRF never over-retrieves (`CANDIDATE_K == TOPK == 10`)  **[High]**

- **Symptom:** hybrid search performs no better than the stronger single retriever.
- **Root cause:** `query.py:23-24` sets `TOPK = 10` and `CANDIDATE_K = 10`, despite the
  comment "over-retrieve before RRF, then trim to TOPK." Each retriever only contributes its
  own top-10 (`query.py:131-132`), so a document ranked 11th by vector but 1st by BM25 (or
  vice-versa) can never be fused in.
- **Why it goes haywire:** RRF's main benefit — recovering items one retriever ranks low —
  is disabled, capping recall.
- **Test / verify:** set `CANDIDATE_K = 50` while keeping final `k = 10`; re-run
  `eval/run_eval.py`; compare recall@10.
- **Ideas:** make `CANDIDATE_K` substantially larger than `TOPK` (e.g. 50–100).

### C5. Verbose queries silently disable BM25 (implicit AND)  **[High]**

- **Symptom:** BM25 returns nothing for normal full-sentence questions, so "hybrid" search
  is really vector-only most of the time.
- **Root cause:** `_fts5_query` (`query.py:77-80`) wraps each token in quotes joined by
  spaces, which FTS5 treats as **implicit AND**. A query like "How does the Orchestrator
  Pattern work with sub-agents?" requires *all* ~8 tokens to co-occur in a single chunk →
  usually **zero** BM25 hits. The `if score > 0` filter (`query.py:101`) can further drop
  legitimate matches.
- **Why it goes haywire:** BM25's keyword/rare-term advantage (acronyms, IDs, proper nouns)
  vanishes exactly when it would help most, and the system silently degrades to vector-only.
- **Test / verify:** instrument `bm25_search` to log hit counts per eval query; expect many
  zeros on the verbose `recall_*` queries. Compare AND vs OR vs stopword-filtered behavior.
- **Ideas:** use OR semantics across significant tokens, drop stopwords, keep rare terms,
  and quote only genuine multi-word phrases.

### C6. No relevance threshold — junk returned for off-topic queries  **[High]**

- **Symptom:** an out-of-scope question ("how do I bake sourdough?") still returns 10
  confident-looking chunks.
- **Root cause:** `search()` (`query.py:127`) always returns top-k. The only cutoff,
  `NEGATIVE_SCORE_THRESHOLD = 0.018`, lives in the eval harness (`eval/run_eval.py:28`), not
  in `search()`. So the MCP `vault_search` / `archive_search` tools return chunks
  regardless of relevance.
- **Why it goes haywire:** the agent receives irrelevant context for off-topic questions and
  produces confident hallucinations grounded in unrelated chunks.
- **Test / verify:** run the three `negative_*` eval queries through `search()` directly;
  confirm it returns full result sets with non-trivial RRF scores; use the score
  distribution to calibrate a floor.
- **Ideas:** apply a minimum-score / margin gate inside `search()`; return an explicit "no
  relevant results" below threshold.

### C7. Tier-2 (LightRAG) retrieval quality is unmeasured  **[Med]**

- **Symptom:** nobody knows whether the knowledge graph answers correctly; regressions are
  invisible.
- **Root cause:** `_run_eval_tier2` (`eval/run_eval.py:102-121`) records **latency only** —
  no recall/precision — and `query_archive` (`index_archive.py:382`) always uses
  `mode="hybrid"` with no fallback or comparison.
- **Why it goes haywire:** half the product (the graph) has no correctness signal, so
  chunking/extraction changes can silently degrade it.
- **Test / verify:** build a small gold set of question → expected-entities/snippets and
  score Tier-2 answers (substring match or an LLM judge); compare LightRAG modes
  (local / global / hybrid).
- **Ideas:** add a Tier-2 correctness metric to the eval harness.

---

## D. Silent failures

These corrupt data or degrade quality without a loud crash — the most dangerous kind.

### D1. Embedding count < chunk count → chunks silently dropped  **[High]**

- **Symptom:** a file is marked "indexed" but some of its chunks were never stored;
  permanent, invisible recall holes.
- **Root cause:** `embed.py:237` iterates `zip(chunks, embeddings)`. If Ollama returns fewer
  embeddings than inputs (partial batch, truncation), `zip` stops at the shorter list and
  the trailing chunks are never inserted. There is no length assertion, and the file is
  still recorded in the manifest as complete (`embed.py:251-253`).
- **Why it goes haywire:** the manifest lies about completeness, so the gap never gets
  retried — the chunks are simply gone.
- **Test / verify:** monkeypatch `get_embeddings` to return `len(chunks) - 1` vectors; index
  a multi-chunk file; assert the stored chunk count is less than expected and that no error
  was raised.
- **Ideas:** assert `len(embeddings) == len(chunks)` and fail the file (record it in the
  failures log) rather than silently truncating.

### D2. `UnicodeDecodeError` aborts the whole Tier-1 run  **[High]**

- **Symptom:** a single odd file halts the entire `embed.py` run with a traceback; the index
  is left partial.
- **Root cause:** `embed.py:213` calls `read_text(encoding="utf-8")` inside a
  `try/except OSError` block (`embed.py:212-216`). `UnicodeDecodeError` is a subclass of
  `ValueError`, **not** `OSError`, so it isn't caught. (By contrast, Tier 2 reads inside
  `except Exception` at `index_archive.py:256-269`, so the two tiers behave inconsistently.)
- **Why it goes haywire:** one stray latin-1/binary `.md` file stops all indexing and leaves
  a partial index with a confusing failure.
- **Test / verify:** drop a latin-1-encoded `.md` into `3. Resources`; run `embed.py`;
  observe the uncaught traceback and aborted run.
- **Ideas:** catch `(OSError, UnicodeDecodeError)`, or read with `errors="replace"`, and
  skip-and-log like Tier 2 does.

### D3. Validator passes "skipped" claims straight into the archive  **[Med]**

- **Symptom:** when the validator is offline, papers are archived and indexed with every
  claim marked "skipped" but still treated as ingested knowledge.
- **Root cause:** if Ollama is unreachable or times out, `validate_claims`
  (`scripts/validate_and_archive.py:251-276`) marks every claim `skipped` with a hardcoded
  `confidence = 0.50` (`_CONFIDENCE`, `scripts/validate_and_archive.py:248`), and
  `run_pipeline` archives and indexes the paper regardless
  (`scripts/validate_and_archive.py:514-522`). Claims are also judged only against
  `context[:1200]` — the abstract — not the body (`_validate_one`,
  `scripts/validate_and_archive.py:202-245`).
- **Why it goes haywire:** the "validation gate" becomes a no-op exactly when the validator
  is down, so unverified or false claims enter the knowledge graph wearing a 0.50
  "confidence" that carries no real meaning.
- **Test / verify:** stop Ollama; run the pipeline on a sample artifact; confirm the paper is
  archived/indexed with all-skipped verdicts. Separately, check whether body-only claims are
  fairly judged against an abstract-only context.
- **Ideas:** treat an all-skipped run as a hold (don't auto-index); validate claims against
  the relevant section rather than just the abstract; stop presenting fixed numbers as
  "confidence."

### D4. Manifest/DB sync edge cases on interrupt  **[Low]**

- **Symptom:** after an interrupted run, the manifest and the index can disagree slightly.
- **Root cause:** both indexers save the manifest per file; an interrupt between DB commit
  and manifest write (or vice-versa) can leave them out of sync. `embed.py` writes the
  manifest atomically (`embed.py:57-63`), but `index_archive.py` does not
  (`index_archive.py:68-73`).
- **Test / verify:** kill the process mid-run; compare manifest entries against `chunks`
  rows (Tier 1) or graph contents (Tier 2).
- **Ideas:** make `index_archive` manifest writes atomic too; reconcile manifest vs index on
  startup.

---

## E. A verification harness (testing these as a suite)

Most findings can be proven with tooling that already exists — no new framework needed.

- **`eval/run_eval.py`** already computes recall@10 / precision@10 over
  `eval/eval_queries.json` and writes `failures.json`. Most of section C is verifiable as
  A/B runs of this harness: prefixes on/off (C3), `CANDIDATE_K` sweep (C4), BM25 AND-vs-OR
  (C5), score-threshold calibration (C6), and chunk-overlap sweep (A1).
- **`tests/`** (`test_utils.py`, `test_query.py`, `test_pipeline.py`) is the right home for
  unit-level reproductions: chunk-boundary cases (A1/A3), the `zip` truncation (D1), and the
  unicode crash (D2).

Suggested experiments (described as methods; not built here):

1. **Chunk-boundary recall** (A1/A3): synthetic docs with boundary-straddling facts →
   measure recall delta vs overlap / structure-aware splitting.
2. **Metadata-coverage audit** (C1): SQL over `data/index.db` measuring the share of chunks
   with recoverable title/date/source; pairwise cosine of header chunks (C2).
3. **nomic-prefix A/B** (C3): two re-indexed corpora, compare eval recall.
4. **Hybrid-health probe** (C4/C5): log per-query vector vs BM25 hit counts and their
   overlap.
5. **Negative-query gate** (C6): score distribution of negatives vs positives → choose a
   floor.
6. **Stale-graph test** (B2): edit-then-requery to show contradictory facts persisting.
7. **Fault injection** (D1/D2): a short embedding list and a non-UTF-8 file.

---

*Report only — no source files were modified. Section E describes how to turn these findings
into runnable diagnostics as a possible follow-up.*
