# ZeroCostBrain — Code Review

> Reviewed: 2026-04-16

---

## CRITICAL — Will Break or Already Broken

### 1. `brain_server.py:150-153` — Async event loop suicide

```python
if __name__ == "__main__":
    asyncio.run(_initialize())   # Loop #1 — creates LightRAG, then DIES
    mcp.run()                    # Loop #2 — tries to use it
```

`asyncio.run()` creates an event loop, runs the coroutine, then **tears the loop down**. LightRAG's internal async resources (locks, semaphores, connection pools) are all bound to the now-dead Loop #1. When `archive_search` later calls `rag.aquery()` inside Loop #2, you'll get `RuntimeError: Task attached to a different loop` or silent deadlocks.

**Fix:** Initialize inside FastMCP's lifespan hook, not before `mcp.run()`.

---

### 2. `watch_archive.py:51` — Wrong lock type, never used

```python
self._lock = asyncio.Lock() if sys.platform != "win32" else None
```

`asyncio.Lock` is for coroutines inside a single event loop. It is **not thread-safe**. The watchdog filesystem callbacks run on a background OS thread. `_debounce_loop` runs on the main thread. Both read and write `_pending` and `_last_trigger` with zero synchronization. The lock is also never used anywhere — it's assigned and forgotten. On Windows it's just `None`.

**Fix:** Use `threading.Lock`.

---

### 3. `query.py:131-155` — DB connection leaks on exception

```python
def search(query: str, k: int = TOPK) -> list[dict]:
    conn = open_db()
    # ... if anything throws here ...
    conn.close()   # never reached
```

No `try/finally`. Any exception between `open_db()` and `conn.close()` leaks the connection. SQLite handles orphaned connections at process exit, but this bites you in long-running server contexts.

**Fix:** Wrap in `try/finally` or use `contextlib.closing(open_db())`.

---

### 4. `index_archive.py:263-265` — `--reset` doesn't actually reset

```python
if force_reset:
    logger.info("🔄 FORCE RESET: Re-indexing all files from scratch.")
    failures = {}
```

Only the manifest and failures dict are cleared. LightRAG's data files (`kv_store_*.json`, `graph_chunk_entity_relation.graphml`, etc.) in `WORKING_DIR` are untouched. So `--reset` just re-inserts everything on top of what's already there — duplicate entities, duplicate edges, ballooning graph.

**Fix:** Delete or wipe the contents of `WORKING_DIR` before re-indexing.

---

## Security

### 5. `.env:21` — Live API key in plaintext file

```
GOOGLE_API_KEY=AIzaSyC1ZDUOCmfbNNH5Z7hEN7M1ly4jlFnLxGw
```

Yes, `.env` is in `.gitignore`. But this key is sitting in a plaintext file. **Rotate this key now** in Google Cloud Console. It costs nothing and takes 60 seconds.

---

### 6. `utils.py:87` — `shell=True` in subprocess

```python
subprocess.check_output(cmd, shell=True, timeout=5)
```

The command is hardcoded today so no injection risk right now. But `shell=True` means if `cmd` ever becomes dynamic or gets refactored to accept input, you have a shell injection vulnerability.

**Fix:** Use `shell=False` with a list:
```python
cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]
subprocess.check_output(cmd, shell=False, timeout=5)
```

---

## Architecture Problems

### 7. Two chunkers, two indexers, one incoherent system

- `embed.py:75-98` — `chunk_markdown()` splits by **word count** (500 words), paragraph-aware
- `utils.py:39-74` — `chunk_text()` splits by **char count** (4000 chars), used by `index_archive.py`

Resources and Archives are chunked completely differently. A dense 600-char paragraph is one chunk in Archives but might be merged with others in Resources. Semantically related content gets split or grouped inconsistently depending on which folder it's in.

**Fix:** Pick one chunking strategy and use it everywhere.

---

### 8. `index_archive.py:167-193` — Exception handler that never fires

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

## Missing Dependencies

### 9. `requirements.txt` — Three packages used but not listed

| Package | Used in | Impact if missing |
|---|---|---|
| `pyyaml` | `fetch_papers.py:28` — `import yaml` | **Hard crash** |
| `pyvis` | `visualize_graph.py:21` | **Hard crash** |
| `psutil` | `brain_tui.py:61` | Silent failure — indexer detection never works |

`matplotlib` is listed but not visibly used anywhere in the codebase.

---

## Bugs (Non-Fatal But Wrong)

### 10. `brain_tui.py:39-41` — Menu points to scripts that don't exist

```python
"2": ("Auto-Research", "auto_research.py"),   # file does not exist
"5": ("News Harvester", "news_harvester.py"), # actual file is news_ingest.py
```

`news_harvester.py` doesn't exist — the real script is `news_ingest.py`. Option 5 will always show as "(missing)". `auto_research.py` is also absent from root.

---

### 11. `embed.py:278` — Chunk count is wrong when embed errors happen

```python
total_chunks += len(chunks)  # added even if embeddings failed
```

The final summary inflates the count by including chunks that weren't actually stored due to embed errors.

---

### 12. `embed.py:160-167` — N individual deletes instead of one

```python
for rid in row_ids:
    conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (rid,))
```

This does N round-trips to the DB.

**Fix:**
```sql
DELETE FROM vec_chunks WHERE rowid IN (SELECT id FROM chunks WHERE path = ?)
```

---

### 13. `news_ingest.py:77-84` — O(n) file scan for dedup on every run

`_already_ingested()` opens and reads every `.md` file in the archive on every single run to find `Source:` lines. Every other ingester uses a manifest file. This gets painfully slow as the archive grows.

**Fix:** Use a JSON manifest file like `embed.py` and `index_archive.py` do.

---

## Summary

| Severity | Count |
|---|---|
| Critical (will break) | 4 |
| Security | 2 |
| Architecture | 2 |
| Bugs | 4 |
| Missing deps | 1 file, 3 packages |

**Most urgent:** Rotate the API key, then fix the event loop bug in `brain_server.py` — that one causes mysterious failures that are very hard to debug. Everything else is fixable incrementally.
