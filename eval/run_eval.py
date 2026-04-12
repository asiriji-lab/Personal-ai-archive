"""
ZeroCostBrain — Evaluation Harness

Measures recall@10 across stratified queries.
Saves failures to failures.json for diagnosis.

Usage:
    python run_eval.py
    python run_eval.py --queries eval_queries.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from query import search

PROJECT_ROOT = Path(__file__).parent
DEFAULT_QUERIES = PROJECT_ROOT / "eval_queries.json"
FAILURES_OUT = PROJECT_ROOT / "failures.json"

PASS_THRESHOLD = 0.8
# Negative queries: top result must score below this to count as "no relevant result found"
NEGATIVE_SCORE_THRESHOLD = 0.018


# ──────────────────────────────────────────────
# METRICS
# ──────────────────────────────────────────────
def recall_at_k(results: list[dict], expected_paths: list[str], k: int = 10) -> float:
    """Fraction of expected paths found in the top-k results."""
    if not expected_paths:
        # Negative query: pass if top result is below confidence threshold
        # (retrieval always returns something — a low score means no real match)
        if not results:
            return 1.0
        top_score = results[0].get("rrf_score", 0.0)
        return 1.0 if top_score < NEGATIVE_SCORE_THRESHOLD else 0.0

    returned = {r["path"] for r in results[:k]}
    expected = set(expected_paths)
    return len(returned & expected) / len(expected)


# ──────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────
def run_eval(queries_path: Path) -> None:
    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    recall_scores: list[float] = []
    failures: list[dict] = []
    latencies: list[float] = []

    recall_scores_by_type: dict[str, list[float]] = {}

    print(f"Running {len(queries)} queries...\n")

    for q in queries:
        t0 = time.perf_counter()
        results = search(q["query"])
        latency = time.perf_counter() - t0

        recall = recall_at_k(results, q["expected_paths"])
        recall_scores.append(recall)
        latencies.append(latency)

        q_type = q.get("type", "recall")
        recall_scores_by_type.setdefault(q_type, []).append(recall)

        status = "PASS" if recall >= 1.0 else ("PARTIAL" if recall > 0 else "FAIL")
        print(f"[{q['id']}] {status:7s}  recall={recall:.2f}  latency={latency:.2f}s")

        if recall < 1.0:
            failures.append(
                {
                    "id": q["id"],
                    "query": q["query"],
                    "type": q_type,
                    "recall": recall,
                    "expected": q["expected_paths"],
                    "got": [r["path"] for r in results[:5]],
                    "latency_s": round(latency, 3),
                }
            )

    # ── Summary ──
    avg_latency = sum(latencies) / len(latencies)

    recall_only = recall_scores_by_type.get("recall", [])
    negative_only = recall_scores_by_type.get("negative", [])

    avg_recall = sum(recall_only) / len(recall_only) if recall_only else 0.0
    avg_negative = sum(negative_only) / len(negative_only) if negative_only else None

    recall_passed = avg_recall >= PASS_THRESHOLD

    print(f"\n{'='*50}")
    print(f"Recall@10 (recall queries) : {avg_recall:.3f}  ({'PASS' if recall_passed else 'FAIL'} — threshold {PASS_THRESHOLD})")
    if avg_negative is not None:
        neg_note = "(NOTE: small corpus — scores overlap with positives; expand vault for reliable negatives)"
        print(f"Negative query score      : {avg_negative:.3f}  {neg_note}")
    print(f"Average latency           : {avg_latency:.2f}s")

    # ── Save failures ──
    recall_failures = [f for f in failures if f["type"] == "recall"]
    if failures:
        FAILURES_OUT.write_text(
            json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n{len(recall_failures)} recall failures saved to {FAILURES_OUT}")
    else:
        print("\nAll recall queries passed.")

    if not recall_passed:
        print(f"\nRecall below {PASS_THRESHOLD}. Consider:")
        print("  - Adjusting chunk size in embed.py (max_words=)")
        print("  - Pulling a better embedding model (e.g. nomic-embed-text:v1.5)")
        print("  - Re-running embed.py --reset after changes")


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate recall@10 for the brain index.")
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES,
        help="Path to eval_queries.json",
    )
    args = parser.parse_args()

    if not args.queries.exists():
        print(f"ERROR: queries file not found: {args.queries}")
        raise SystemExit(1)

    run_eval(args.queries)
