# PDMPI Implementation Spec
# Purpose-Driven Multi-Pipeline Indexing for ZeroCostBrain

## 1. Problem Statement

`index_archive.py` currently applies a single, uniform indexing strategy to every `.md` file in `ARCHIVE_PATH`:

- Glob all `*.md` recursively → compare MD5 hash against `index_manifest.json` → skip if unchanged
- `chunk_text(content, max_chars=1500)` — one size, paragraph-first, no content awareness
- `rag.ainsert(chunk)` for every chunk — full LightRAG entity extraction on everything, including news snippets and 3-line meeting notes
- Manifest schema: `{path: md5_hash}` — no content type, no pipeline tag, no ingestion timestamp

This treats a validated research paper identically to a personal note. The result: LightRAG's expensive entity extraction is wasted on ephemeral content, and valuable structured documents (papers with clear sections) are chunked at arbitrary character boundaries that split arguments mid-way.

---

## 2. Decision Log

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Number of pipelines | 2 (Deep + Fast) | 3 (+ Summary) | Pipeline C is functionally identical to B; two pipelines is enough complexity |
| Lifecycle engine | Deferred | Implemented now | Single user generates insufficient query volume for heat maps to signal anything |
| Freshness tracking | `indexed_at` only | Full decay curves | One field in manifest; no scoring subsystem required for now |
| Content classifier | Rule-based | LLM classifier | Fast, deterministic, zero-cost; revisit only if accuracy < 90% on test set |
| Pipeline C | Dropped | Kept | sqlite-vec fast path (Pipeline B) already handles all low-value content |

---

## 3. YAML Frontmatter Schema

Every `.md` file entering the indexer should carry this frontmatter. The indexer writes it if absent; ingestion scripts write it at creation time.

```yaml
---
content_type: research_paper
source: fetch_papers
indexed_at: ""
pipeline: A
---
```

**Field values:**

| Field | Values |
|---|---|
| `content_type` | `research_paper` \| `news_article` \| `personal_note` \| `validated_artifact` \| `meeting_note` \| `general` |
| `source` | `fetch_papers` \| `news_ingest` \| `validate_and_archive` \| `manual` |
| `indexed_at` | ISO 8601 timestamp written by indexer on first successful index; `""` until then |
| `pipeline` | `A` \| `B` — set by router at index time |

### 3.1 Classifier Rules (rule-based, evaluated in order)

```
path contains "autoresearchlaw/artifacts/"  →  research_paper,  source: validate_and_archive
path contains "fetch_papers/"               →  research_paper,  source: fetch_papers
path contains "news_ingest/"                →  news_article,    source: news_ingest
path contains "validate_and_archive/"       →  validated_artifact, source: validate_and_archive
first 3 lines match dateline pattern        →  news_article,    source: manual
file content length < 500 chars             →  personal_note,   source: manual
otherwise                                   →  general,         source: manual
```

Dateline pattern: `^\w+,\s+\w+\s+\d{1,2},\s+\d{4}` (e.g. "Monday, April 14, 2025")

Files with existing valid frontmatter skip classification — frontmatter values are trusted.

---

## 4. Content Type → Chunking Matrix

| Content Type | Chunk Strategy | Max Chars | LightRAG? | Pipeline |
|---|---|---|---|---|
| `research_paper` | Section-based (H2/H3 headings) | 1500–2500 per section | Yes | A |
| `validated_artifact` | Section-based (H2/H3 headings) | 1500–2000 per section | Yes | A |
| `general` | Paragraph-first (existing logic) | 1500 | Yes | A |
| `news_article` | Paragraph-first, smaller chunks | 800–1200 | No | B |
| `meeting_note` | Paragraph-first, smaller chunks | 800–1200 | No | B |
| `personal_note` | Paragraph-first, smaller chunks | 600–1000 | No | B |

---

## 5. Two-Pipeline Architecture

```
                  ┌──────────────────────────────────┐
                  │   _index_single_file(path)        │
                  │   1. Read content                 │
                  │   2. Classify → content_type      │
                  │   3. Route → pipeline             │
                  └──────────┬───────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
   ┌─────────────────────┐      ┌──────────────────────┐
   │  Pipeline A          │      │  Pipeline B           │
   │  Deep Index          │      │  Fast Index           │
   │                      │      │                       │
   │  content_type:        │      │  content_type:        │
   │  research_paper       │      │  news_article         │
   │  validated_artifact   │      │  meeting_note         │
   │  general              │      │  personal_note        │
   │                      │      │                       │
   │  chunk_text_sections()│      │  chunk_text()         │
   │  (H2/H3 boundaries)  │      │  (paragraph-first,    │
   │  max 1500–2500 chars │      │   max 800–1000 chars) │
   │                      │      │                       │
   │  rag.ainsert(chunk)  │      │  embed → sqlite-vec   │
   │  (LightRAG graph)    │      │  (no LightRAG)        │
   │                      │      │                       │
   │  Storage: Tier 2     │      │  Storage: Tier 1      │
   │  Query: archive_search│      │  Query: vault_search  │
   │  Cost: HIGH          │      │  Cost: LOW            │
   └─────────────────────┘      └──────────────────────┘
```

**Pipeline A — Deep Index**
- Chunking: `chunk_text_sections(content, max_chars=CHUNK_SECTION_MAX_CHARS)` — splits on `## ` and `### ` Markdown headings, producing variable-length section chunks that respect semantic boundaries
- Entity extraction: `await rag.ainsert(chunk)` — existing LightRAG path, unchanged
- A document-level summary chunk (first paragraph + all headings concatenated) is prepended to the chunk list before insertion

**Pipeline B — Fast Index**
- Chunking: `chunk_text(content, max_chars=CHUNK_B_MAX_CHARS)` — existing paragraph-first logic with smaller max size
- Entity extraction: skipped entirely
- Embedding: `_local_embed([chunk])` → write embedding row to sqlite-vec table
- No changes to LightRAG graph

---

## 6. Manifest Schema Change

**Current schema** (`data/embed_manifest.json` / `WORKING_DIR/index_manifest.json`):
```json
{
  "4. Archives/some_paper.md": "a1b2c3d4e5f6..."
}
```

**New schema:**
```json
{
  "4. Archives/some_paper.md": {
    "hash": "a1b2c3d4e5f6...",
    "content_type": "research_paper",
    "pipeline": "A",
    "indexed_at": "2026-05-15T10:30:00"
  }
}
```

**Backward compatibility:** `scripts/migrate_manifest.py` reads the old flat format and converts each `path: hash` entry to `path: {hash, content_type: "general", pipeline: "A", indexed_at: ""}`. Run once before deploying Phase 3.

`_load_manifest()` must handle both formats during the transition — detect by checking if the first value is a `str` (old) or `dict` (new).

---

## 7. Files to Modify

| File | What Changes |
|---|---|
| `config.py` | Add `CHUNK_SECTION_MAX_CHARS`, `CHUNK_B_MAX_CHARS` constants |
| `utils.py` | Add `chunk_text_sections(text, max_chars)` function |
| `index_archive.py` | Add `_classify_content_type()`, `_select_pipeline()`, `_index_pipeline_b()`; update `_index_single_file()`, `_load_manifest()`, `_save_manifest()` |
| `data/embed_manifest.json` | Migrated by `scripts/migrate_manifest.py` (not hand-edited) |
| `scripts/migrate_manifest.py` | New file — one-time migration script |

**Ingestion scripts (Phase 2, optional):**

| File | What Changes |
|---|---|
| `validate_and_archive.py` | Prepend YAML frontmatter with `content_type: validated_artifact` at write time |
| `news_ingest.py` | Prepend YAML frontmatter with `content_type: news_article` at write time |
| `fetch_papers.py` (if exists) | Prepend YAML frontmatter with `content_type: research_paper` at write time |

---

## 8. New Functions — Signatures and Behavior

### `config.py`
```python
CHUNK_SECTION_MAX_CHARS = int(os.getenv("BRAIN_CHUNK_SECTION_SIZE", "2000"))
CHUNK_B_MAX_CHARS = int(os.getenv("BRAIN_CHUNK_B_SIZE", "900"))
```

### `utils.py`
```python
def chunk_text_sections(text: str, max_chars: int = 2000) -> list[str]:
    """
    Split text on Markdown H2/H3 heading boundaries (## or ###).
    Each section (heading + its body) becomes one chunk.
    If a section exceeds max_chars, fall back to chunk_text() on that section.
    Always prepend a summary chunk: first paragraph + all headings joined.
    Returns list of chunks; minimum 1 chunk (the full text if no headings found).
    """
```

### `index_archive.py`
```python
def _classify_content_type(path: Path, content: str) -> str:
    """
    Rule-based classifier. Returns one of:
    research_paper | news_article | personal_note | validated_artifact | meeting_note | general
    Checks path patterns first, then content heuristics.
    Honors existing YAML frontmatter content_type if present and valid.
    """

def _select_pipeline(content_type: str) -> Literal["A", "B"]:
    """
    Maps content_type to pipeline letter.
    A: research_paper, validated_artifact, general
    B: news_article, meeting_note, personal_note
    """

async def _index_pipeline_b(chunks: list[str], path: str) -> None:
    """
    Embed chunks via _local_embed() and write to sqlite-vec (Tier 1).
    Does NOT call rag.ainsert(). Does NOT modify LightRAG graph.
    Uses same sqlite-vec connection as vault_search.
    """
```

---

## 9. Implementation Phases

### Phase 1 — Metadata Foundation
**Goal:** Classifier + extended manifest. No pipeline changes yet.

- [ ] Add `CHUNK_SECTION_MAX_CHARS`, `CHUNK_B_MAX_CHARS` to `config.py`
- [ ] Implement `_classify_content_type(path, content)` in `index_archive.py`
- [ ] Update `_load_manifest()` to handle both old and new schema formats
- [ ] Update `_save_manifest()` to write new schema with `content_type`, `pipeline`, `indexed_at`
- [ ] Write `scripts/migrate_manifest.py`
- [ ] Unit tests for `_classify_content_type()` covering all 6 content types

**Deliverable:** Classifier runs on every indexed file; manifest records content type. No change to indexing behavior yet.

### Phase 2 — Adaptive Chunking
**Goal:** Section-aware chunking for Pipeline A content.

- [ ] Implement `chunk_text_sections(text, max_chars)` in `utils.py`
- [ ] Wire into `_index_single_file()`: use `chunk_text_sections` for `pipeline == "A"` with `research_paper` / `validated_artifact` types; keep `chunk_text` for everything else
- [ ] Add document summary chunk prepend logic
- [ ] Tests: verify section chunks on a real research paper MD; verify fallback on a file with no headings

**Deliverable:** Research papers chunked by section. Personal notes unchanged.

### Phase 3 — Pipeline Router
**Goal:** Pipeline B content skips LightRAG entirely.

- [ ] Implement `_index_pipeline_b(chunks, path)` — embed to sqlite-vec, no LightRAG
- [ ] Update `_index_single_file()`: after classifying and chunking, branch on `_select_pipeline()` result
- [ ] Write YAML frontmatter to file if not already present (non-destructive prepend)
- [ ] Integration test: index one research paper → confirm LightRAG graph has new entities; index one news article → confirm no new LightRAG entities, sqlite-vec row exists
- [ ] Add `--dry-run` flag to `index_archive.py` that prints route decisions without inserting

**Deliverable:** Full PDMPI routing live. LLM entity extraction only runs on Pipeline A content.

---

## 10. Verification

```bash
# Phase 1: Classifier smoke test
python -c "
from pathlib import Path
from index_archive import _classify_content_type
print(_classify_content_type(Path('4. Archives/fetch_papers/test.md'), 'content'))
# Expected: research_paper
print(_classify_content_type(Path('4. Archives/notes/short.md'), 'hi'))
# Expected: personal_note
"

# Phase 2: Section chunking
python -c "
from utils import chunk_text_sections
text = open('knowledge_base/4. Archives/some_paper.md').read()
chunks = chunk_text_sections(text, 2000)
print(f'{len(chunks)} chunks, sizes: {[len(c) for c in chunks]}')
"

# Phase 3: Dry run router
python index_archive.py --dry-run
# Expected output: each file with its detected content_type and selected pipeline

# Regression: eval suite must not degrade
python eval/run_eval.py
# Target: >= 95% of baseline score
```

---

## 11. Deferred (Not in This Spec)

The following were evaluated and explicitly deferred:

- **Phase 4 lifecycle engine** — promotion/demotion between pipelines based on query frequency; requires sustained query volume to generate meaningful signal
- **Query heat maps** — `last_accessed` tracking, access frequency scoring, knowledge value scores
- **Freshness decay curves** — `half_life_days` scoring at query time; `indexed_at` is stored but not used for ranking yet
- **LLM-based content classifier** — rule-based classifier ships first; upgrade path exists if accuracy proves insufficient
- **Ingestion-time frontmatter** — ingestion scripts write frontmatter at file creation; this is optional in Phase 2 since the indexer's classifier handles it as a fallback
