# ZeroCostBrain — Code Review

> Reviewed: 2026-04-16 | Status updated: 2026-04-29

---

## ✅ FIXED

### 1. ~~`brain_server.py` — Async event loop suicide~~ ✅ Fixed
Initialization now happens inside the FastMCP `lifespan` hook. LightRAG storages are initialized inside the server's own event loop, not before it.

### 2. ~~`watch_archive.py` — Wrong lock type~~ ✅ Fixed
Changed from `asyncio.Lock` to `threading.Lock`. The lock is now actually used for `_pending` and `_last_trigger` access.

### 3. ~~`query.py` — DB connection leaks on exception~~ ✅ Fixed
`conn.close()` is now inside a `try/finally` block.

### 4. ~~`index_archive.py` — `--reset` doesn't actually reset~~ ✅ Fixed
`force_reset` now wipes all files and subdirectories in `WORKING_DIR` before re-indexing, then forces `get_rag()` to build a fresh instance.

### 6. ~~`utils.py` — `shell=True` in subprocess~~ ✅ Fixed
`subprocess.check_output` now uses `shell=False` with a list command. No shell injection surface.

---

## CRITICAL — Will Break or Already Broken

### 8. `index_archive.py` — Exception handler that never fires

```python
try:
    _rag_instance = LightRAG(...)
except ConnectionError as e:   # ← LightRAG() doesn't make network calls
    logger.error(f"Cannot connect to Ollama...")
    sys.exit(1)
```

`LightRAG.__init__()` is pure construction — no network I/O. The actual connection to Ollama happens at `initialize_storages()`. That `ConnectionError` catch is dead code. Real connection errors propagate as unhandled exceptions from wherever `initialize_storages()` is called.

**Fix:** Move the error handling to wrap `rag.initialize_storages()` calls.

---

## Security

### 5. `.env` — Live API key in plaintext file

Yes, `.env` is in `.gitignore`. But the key is sitting in a plaintext file. Rotate it in Google Cloud Console if you haven't — 60 seconds, zero cost.

---

## Architecture Problems

### 7. Two chunkers, two indexers, one incoherent system

- `embed.py:75-98` — `chunk_markdown()` splits by **word count** (500 words), paragraph-aware
- `utils.py:39-74` — `chunk_text()` splits by **char count** (4000 chars), used by `index_archive.py`

Resources and Archives are chunked completely differently. Semantically related content gets split or grouped inconsistently depending on which folder it's in.

**Fix:** Pick one chunking strategy and use it everywhere.

---

## Missing Dependencies

### 9. `requirements.txt` — Three packages used but not listed

| Package | Used in | Impact if missing |
|---|---|---|
| `pyyaml` | `fetch_papers.py` — `import yaml` | Hard crash |
| `pyvis` | `visualize_graph.py` | Hard crash |
| `psutil` | `brain_tui.py` | Silent failure — indexer detection never works |

`matplotlib` is listed but not visibly used anywhere.

---

## Bugs (Non-Fatal But Wrong)

### 10. `brain_tui.py` — Menu points to scripts that don't exist

```python
"2": ("Auto-Research", "auto_research.py"),   # does not exist
"5": ("News Harvester", "news_harvester.py"), # actual file is news_ingest.py
```

Option 5 will always show as "(missing)".

### 11. `embed.py` — Chunk count inflated when embed errors happen

```python
total_chunks += len(chunks)  # added even if embeddings failed
```

Summary count includes chunks that weren't actually stored.

### 12. `embed.py` — N individual deletes instead of one

```python
for rid in row_ids:
    conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (rid,))
```

**Fix:**
```sql
DELETE FROM vec_chunks WHERE rowid IN (SELECT id FROM chunks WHERE path = ?)
```

### 13. `news_ingest.py` — O(n) file scan for dedup on every run

`_already_ingested()` reads every `.md` file in the archive on every run to find `Source:` lines. Every other ingester uses a manifest file.

**Fix:** Use a JSON manifest like `embed.py` and `index_archive.py` do.

---

## Summary

| Severity | Total | Fixed | Remaining |
|---|---|---|---|
| Critical | 4 | 3 | 1 (#8) |
| Security | 2 | 1 (shell=False) | 1 (API key — user action) |
| Architecture | 2 | 0 | 2 |
| Bugs | 4 | 0 | 4 |
| Missing deps | 1 file, 3 packages | 0 | 1 file, 3 packages |
