"""
One-time migration: convert flat {path: hash} index_manifest.json
to the new schema {path: {hash, content_type, pipeline, indexed_at}}.

Run once before deploying PDMPI Phase 3:
    python scripts/migrate_manifest.py

Safe to re-run — exits without changes if already in new format.
"""

import json
import sys
from pathlib import Path

MANIFEST = Path("knowledge_base/.lightrag/index_manifest.json")


def main() -> None:
    if not MANIFEST.exists():
        sys.exit(f"Manifest not found at {MANIFEST} — nothing to migrate.")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if not data:
        print("Manifest is empty. No action taken.")
        return

    first_val = next(iter(data.values()))
    if not isinstance(first_val, str):
        print("Already in new format. No action taken.")
        return

    new_data = {
        k: {"hash": v, "content_type": "general", "pipeline": "A", "indexed_at": ""}
        for k, v in data.items()
    }
    MANIFEST.write_text(json.dumps(new_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Migrated {len(new_data)} entries in {MANIFEST}.")


if __name__ == "__main__":
    main()
