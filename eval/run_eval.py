"""
ZeroCostBrain — Evaluation Harness

Measures recall@10 across stratified queries.
Saves failures to failures.json for diagnosis.

Usage:
    python run_eval.py
    python run_eval.py --queries eval_queries.json
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from index_archive import query_archive as search_tier2
from query import search as search_tier1

PROJECT_ROOT = Path(__file__).parent
DEFAULT_QUERIES = PROJECT_ROOT / "eval_queries.json"
FAILURES_OUT = PROJECT_ROOT / "failures.json"

PASS_THRESHOLD = 0.8
NEGATIVE_SCORE_THRESHOLD = 0.018


# ──────────────────────────────────────────────
# METRICS
# ──────────────────────────────────────────────
def recall_at_k(results: list[dict], expected_paths: list[str], k: int = 10) -> float:
    if not expected_paths:
        if not results:
            return 1.0
        top_score = results[0].get("rrf_score", 0.0)
        return 1.0 if top_score < NEGATIVE_SCORE_THRESHOLD else 0.0

    returned = {r["path"] for r in results[:k]}
    expected = set(expected_paths)
    return len(returned & expected) / len(expected)


def precision_at_k(results: list[dict], expected_paths: list[str], k: int = 10) -> float:
    if not expected_paths:
        return 1.0 if (not results or results[0].get("rrf_score", 0.0) < NEGATIVE_SCORE_THRESHOLD) else 0.0
    returned = {r["path"] for r in results[:k]}
    if not returned:
        return 0.0
    expected = set(expected_paths)
    return len(returned & expected) / min(k, len(returned))


# ──────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────
async def run_eval(queries_path: Path, tier: str) -> None:
    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    if tier in ("1", "both"):
        print("=== RUNNING TIER 1 (sqlite-vec) ===")
        await _run_eval_tier1(queries)

    if tier in ("2", "both"):
        print("\n=== RUNNING TIER 2 (LightRAG) ===")
        await _run_eval_tier2(queries)


async def _run_eval_tier1(queries: list[dict]) -> None:
    recall_scores, precision_scores, latencies, _failures = [], [], [], []
    for q in queries:
        t0 = time.perf_counter()
        results = search_tier1(q["query"])
        latency = time.perf_counter() - t0

        recall = recall_at_k(results, q["expected_paths"])
        precision = precision_at_k(results, q["expected_paths"])

        recall_scores.append(recall)
        precision_scores.append(precision)
        latencies.append(latency)

        status = "PASS" if recall >= 1.0 else ("PARTIAL" if recall > 0 else "FAIL")
        print(f"[{q['id']}] {status:7s}  recall={recall:.2f}  precision={precision:.2f}  latency={latency:.2f}s")

    latencies.sort()
    avg_latency = sum(latencies) / len(latencies)
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0

    print(f"\n{'=' * 50}")
    print(f"Recall@10    : {avg_recall:.3f} (threshold {PASS_THRESHOLD})")
    print(f"Precision@10 : {avg_precision:.3f}")
    print(f"Latency      : Avg={avg_latency:.2f}s  p50={p50:.2f}s  p95={p95:.2f}s")


async def _run_eval_tier2(queries: list[dict]) -> None:
    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        try:
            _res = await search_tier2(q["query"])
            status = "SUCCESS"
        except Exception as e:
            status = f"FAIL ({e})"
        latency = time.perf_counter() - t0
        latencies.append(latency)
        print(f"[{q['id']}] {status:10s} latency={latency:.2f}s")

    latencies.sort()
    avg_latency = sum(latencies) / len(latencies)
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    print(f"\n{'=' * 50}")
    print(f"Latency      : Avg={avg_latency:.2f}s  p50={p50:.2f}s  p95={p95:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate recall@10 for the brain index.")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--tier", choices=["1", "2", "both"], default="1")
    args = parser.parse_args()
    if not args.queries.exists():
        print(f"ERROR: queries file not found: {args.queries}")
        raise SystemExit(1)
    asyncio.run(run_eval(args.queries, args.tier))
