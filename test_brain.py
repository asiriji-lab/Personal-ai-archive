"""
🧠 ZeroCostBrain — Memory Access Test

Interactive or CLI-driven query tester for the Archive Brain.
Verifies that RAG initialization, embedding, and hybrid search all work end-to-end.
"""

import asyncio
import logging
import os
import sys

# ── Quieten noisy LightRAG internals ──
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("lightrag.utils").setLevel(logging.ERROR)
logging.getLogger("lightrag.lightrag").setLevel(logging.ERROR)

from config import WORKING_DIR
from index_archive import get_rag, test_query


async def run_query(query: str):
    """Execute a single query against the Archive Brain."""
    print(f"\n🔍 Reasoning about: '{query}'...")

    rag = get_rag()
    await rag.initialize_storages()

    answer = await test_query(query)

    print("\n--- 💡 BRAIN RESPONSE ---")
    print(answer)
    print("-------------------------")


async def interactive_mode():
    """Loop for multiple queries without restarting."""
    rag = get_rag()
    await rag.initialize_storages()
    print("✅ Brain online. Type 'quit' to exit.\n")

    while True:
        try:
            query = input("🧠 Ask > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            break

        try:
            answer = await test_query(query)
            print(f"\n💡 {answer}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


async def main():
    print("\n--- 🧠 ARCHIVE BRAIN: ACCESSING MEMORY ---")

    # Pre-flight check
    doc_status_file = WORKING_DIR / "kv_store_doc_status.json"
    if not doc_status_file.exists():
        print("\n⚠️ ERROR: Brain storage not found.")
        print("Please run 'python index_archive.py' first to build the knowledge graph.")
        return

    # Check for CLI arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await run_query(query)
    else:
        # Interactive mode
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
