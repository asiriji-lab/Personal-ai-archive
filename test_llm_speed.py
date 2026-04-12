"""
test_llm_speed.py — Verify thinking mode is OFF and measure raw tok/s.

Fires a single LLM call with the same kwargs used by index_archive.py.
No LightRAG, no indexing — just the Ollama call.

Usage:
    python test_llm_speed.py

Expected output if thinking is OFF:  < 30s, > 10 tok/s
Expected output if thinking is ON:   > 120s, < 3 tok/s
"""

import asyncio
import time

import ollama
import numpy as np

from config import LOCAL_LLM_MODEL, LOCAL_CONTEXT_WINDOW, OLLAMA_HOST

# Same prompt shape LightRAG uses for entity extraction
TEST_PROMPT = (
    "List 5 key concepts from this text and explain each in one sentence.\n\n"
    "Text: Knowledge graphs represent information as entities and relationships. "
    "They enable hybrid search combining vector similarity with graph traversal. "
    "LightRAG builds a knowledge graph from documents using LLM-based entity extraction. "
    "The extraction prompt has a fixed overhead of approximately 1300 tokens. "
    "Chunking documents reduces per-call latency at the cost of more total calls."
)


async def run_test():
    print(f"Model  : {LOCAL_LLM_MODEL}")
    print(f"Host   : {OLLAMA_HOST}")
    print(f"num_ctx: {LOCAL_CONTEXT_WINDOW}")
    print(f"think  : False (top-level kwarg)")
    print("-" * 50)
    print("Sending test prompt...")

    client = ollama.AsyncClient(host=OLLAMA_HOST)
    t0 = time.perf_counter()

    response = await client.chat(
        model=LOCAL_LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": TEST_PROMPT},
        ],
        think=False,
        options={"num_ctx": LOCAL_CONTEXT_WINDOW},
    )

    elapsed = time.perf_counter() - t0
    result = response["message"]["content"]
    out_tokens = len(result) // 4
    toks_per_sec = out_tokens / elapsed if elapsed > 0 else 0

    print(f"\nElapsed  : {elapsed:.1f}s")
    print(f"Output   : ~{out_tokens} tokens")
    print(f"Tok/s    : {toks_per_sec:.1f}")
    print()

    if toks_per_sec > 10:
        print("PASS — thinking is OFF. Indexer should run cleanly.")
    elif toks_per_sec > 3:
        print("PARTIAL — better than before but still slow. Check VRAM contention.")
    else:
        print("FAIL — thinking is likely still ON or model is swapping to RAM.")
        print("Next step: check Ollama version supports think kwarg, or try /no_think prefix.")

    print()
    print("Response preview:")
    print(result[:300])


if __name__ == "__main__":
    asyncio.run(run_test())
