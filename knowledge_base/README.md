# Knowledge Base — Vault Structure

This directory holds your Obsidian vault. It is **gitignored** to protect your private data.

When you first run the system, `config.py` auto-creates this skeleton if it doesn't exist. For manual setup, create these folders:

```
knowledge_base/
├── 1. Projects/          # Active project notes
├── 2. Areas/             # Ongoing responsibility areas
├── 3. Resources/         # Active memory (AI-written notes land here)
├── 4. Archives/          # Long-term memory (indexed by LightRAG)
├── system/
│   ├── review-queue.jsonl    # Validation harness output
│   └── embed_manifest.json   # Embedding tracking
└── README.md             # This file
```

## How It's Used

| Folder | Role | Accessed By |
|--------|------|-------------|
| `3. Resources/` | Active vault (Tier 1) | `save_active_note()`, `vault_search()` |
| `4. Archives/` | Long-term memory (Tier 2) | `index_archive.py`, `archive_search()` |
| `system/review-queue.jsonl` | Validation results | `review_queue()` |

## Getting Started

1. Copy your existing Obsidian vault here, or start fresh.
2. Point `BRAIN_VAULT_PATH` in `.env` at this directory.
3. Run `python index_archive.py` to build the Knowledge Graph from `4. Archives/`.
