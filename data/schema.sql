-- ZeroCostBrain — SQLite-vec Schema
-- Apply via Python (embed.py handles extension loading).
-- Do NOT run this directly with sqlite3 CLI unless you load vec0 first.

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    path        TEXT    NOT NULL,       -- relative to RESOURCES_PATH
    chunk_index INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    embedder    TEXT    NOT NULL,
    indexed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Virtual table for vector search (nomic-embed-text = 768 dims)
CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    embedding float[768]
);

-- FTS5 index for BM25 search (replaces in-memory rank_bm25).
-- content= makes this a content table — no duplicate storage, reads from chunks.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    content='chunks',
    content_rowid='id'
);

-- Keep FTS5 in sync with chunks automatically.
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;
