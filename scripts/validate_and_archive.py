#!/usr/bin/env python3
"""
ZeroCostBrain — Validation Harness

Sits between AutoResearchClaw paper generation and LightRAG indexing.
Validates factual claims, writes a review queue, enriches the paper with
metadata, archives it, and triggers incremental indexing.

Usage:
    python scripts/validate_and_archive.py --artifact autoresearchclaw/artifacts/rc-<id>/
    python scripts/validate_and_archive.py --watch
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Ensure project root is importable regardless of cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    ARCHIVE_PATH,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_HOST,
    VAULT_PATH,
)
from utils import sanitize_filename

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# CONFIGURATION (env overrides, no config.py changes needed)
# ──────────────────────────────────────────────
VALIDATOR_MODEL = os.getenv("BRAIN_VALIDATOR_MODEL", "qwen3.5:4b")
VALIDATOR_TIMEOUT = int(os.getenv("BRAIN_VALIDATOR_TIMEOUT", "15"))
ARTIFACTS_DIR = PROJECT_ROOT / "autoresearchclaw" / "artifacts"

QUEUE_DIR = VAULT_PATH / "system"
QUEUE_JSONL = QUEUE_DIR / "review-queue.jsonl"
QUEUE_MD = QUEUE_DIR / "review-queue.md"

_queue_lock = threading.Lock()  # same-process guard; cross-process not needed


# ──────────────────────────────────────────────
# STAGE 1 — LOCATE ARTIFACT FILES
# ──────────────────────────────────────────────
def locate_artifacts(artifact_dir: Path) -> tuple[Path, Path]:
    # paper_draft.md: check root first, then stage-17/ (real AutoResearchClaw layout)
    paper_candidates = [
        artifact_dir / "paper_draft.md",
        artifact_dir / "stage-17" / "paper_draft.md",
    ]
    paper = next((p for p in paper_candidates if p.exists()), None)
    summary = artifact_dir / "pipeline_summary.json"
    missing = []
    if paper is None:
        missing.append(str(artifact_dir / "paper_draft.md"))
    if not summary.exists():
        missing.append(str(summary))
    if missing:
        raise FileNotFoundError(f"Missing artifact file(s): {missing}")
    return paper, summary


# ──────────────────────────────────────────────
# STAGE 2 — CLAIMS EXTRACTION
# ──────────────────────────────────────────────
def _extract_section(text: str, heading_pattern: str) -> str:
    """Return body text under a markdown heading, stopping at the next heading."""
    lines = text.splitlines()
    in_section = False
    collected: list[str] = []
    heading_re = re.compile(heading_pattern, re.IGNORECASE)
    any_heading_re = re.compile(r"^#{1,6}\s+")

    for line in lines:
        if heading_re.match(line):
            in_section = True
            continue
        if in_section:
            if any_heading_re.match(line):
                break
            collected.append(line)

    return "\n".join(collected).strip()


def _claims_from_value(value) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("text", "claim", "content"):
                    if key in item and isinstance(item[key], str):
                        out.append(item[key])
                        break
        return out
    if isinstance(value, str):
        return [s.strip() for s in value.split(". ") if len(s.strip()) >= 20]
    return []


def _extract_from_summary(summary_data: dict) -> list[str]:
    for key in ("knowledge_cards", "claims", "summary", "key_findings"):
        if key in summary_data:
            claims = _claims_from_value(summary_data[key])
            if claims:
                return claims
    return []


def _extract_from_llm(paper_text: str) -> list[str]:
    """Fallback: ask Gemini Flash to extract claims from abstract + conclusion."""
    abstract = _extract_section(paper_text, r"^#{1,3}\s*(\d+\.\s*)?abstract")
    conclusion = _extract_section(paper_text, r"^#{1,3}\s*(\d+\.\s*)?conclusion")
    context = (abstract + "\n\n" + conclusion).strip() or paper_text[:800]

    if not GEMINI_API_KEY or "PASTE_YOUR_KEY" in GEMINI_API_KEY:
        logger.warning("No Gemini API key — skipping LLM claim extraction.")
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "You are a precise claim extractor. Return only a JSON array "
                        "of strings. Each string is one distinct factual claim from "
                        "the text. Limit to 15 claims maximum. No preamble."
                    )
                }
            ]
        },
        "contents": [{"parts": [{"text": context}]}],
    }

    try:
        resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Gemini claim extraction failed: {e}")
        return []


def extract_claims(paper_path: Path, summary_path: Path) -> tuple[list[str], str]:
    """Return (claims[:20], extraction_path) where path is 'primary' or 'fallback'."""
    try:
        summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read pipeline_summary.json: {e}")
        summary_data = {}

    claims = _extract_from_summary(summary_data)
    if claims:
        return claims[:20], "primary"

    paper_text = paper_path.read_text(encoding="utf-8")
    claims = _extract_from_llm(paper_text)
    return claims[:20], "fallback"


# ──────────────────────────────────────────────
# STAGE 3 — CLAIM VALIDATION
# ──────────────────────────────────────────────
def _probe_ollama() -> bool:
    try:
        requests.head(OLLAMA_HOST, timeout=3)
        return True
    except Exception:
        return False


async def _validate_one(claim: str, context: str) -> dict:
    import ollama as _ollama

    system_prompt = (
        "You are a fact-checking assistant. Given source text and a claim, "
        "decide if the claim accurately reflects the source. Respond ONLY "
        'with valid JSON: {"verdict": "pass" or "fail", '
        '"explanation": "one sentence"}. No other text.'
    )
    user_prompt = f"Source text:\n{context[:1200]}\n\nClaim:\n{claim}"

    try:
        client = _ollama.AsyncClient(host=OLLAMA_HOST)
        response = await asyncio.wait_for(
            client.chat(
                model=VALIDATOR_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={"num_ctx": 2048, "think": False},
            ),
            timeout=VALIDATOR_TIMEOUT,
        )
        text = response["message"]["content"].strip()
        # Strip thinking tags emitted by some Qwen variants
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        parsed = json.loads(text)
        verdict = str(parsed.get("verdict", "fail")).lower()
        if verdict not in ("pass", "fail"):
            verdict = "fail"
        return {
            "verdict": verdict,
            "explanation": str(parsed.get("explanation", "No explanation.")),
        }
    except asyncio.TimeoutError:
        return {"verdict": "skipped", "explanation": "Validator timeout"}
    except (json.JSONDecodeError, KeyError):
        return {
            "verdict": "fail",
            "explanation": "Validator returned unparseable response.",
        }
    except Exception as e:
        return {"verdict": "skipped", "explanation": f"Validator error: {e}"}


_CONFIDENCE = {"pass": 0.90, "fail": 0.20, "skipped": 0.50}


async def validate_claims(claims: list[str], context: str) -> list[dict]:
    """Validate all claims. Returns verdict records with claim_text, verdict, explanation, confidence."""
    if not _probe_ollama():
        logger.warning("Validator offline — all claims marked as skipped.")
        return [
            {
                "claim_text": c,
                "verdict": "skipped",
                "explanation": "Ollama unavailable at validation time",
                "confidence": 0.50,
            }
            for c in claims
        ]

    results: list[dict] = []
    for claim in claims:
        r = await _validate_one(claim, context)
        results.append(
            {
                "claim_text": claim,
                "verdict": r["verdict"],
                "explanation": r["explanation"],
                "confidence": _CONFIDENCE.get(r["verdict"], 0.50),
            }
        )
    return results


# ──────────────────────────────────────────────
# STAGE 4 — REVIEW QUEUE
# ──────────────────────────────────────────────
_VERDICT_EMOJI = {"pass": "✅", "fail": "❌", "skipped": "⏭️"}


def _trunc(text: str, n: int = 120) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _regen_md(entries: list[dict]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = ["# Review Queue", f"_Last updated: {now}_", ""]

    groups: dict[tuple, list[dict]] = {}
    for e in entries:
        key = (e.get("source_file", ""), e.get("run_id", ""))
        groups.setdefault(key, []).append(e)

    def _group_ts(kv: tuple) -> str:
        return kv[1][0].get("timestamp", "")

    for (source_file, run_id), group in sorted(groups.items(), key=_group_ts, reverse=True):
        lines.append(f"## {source_file} — {run_id}")
        lines.append("| # | Claim | Verdict | Confidence | Explanation | Status |")
        lines.append("|---|-------|---------|------------|-------------|--------|")
        for i, e in enumerate(group, 1):
            verdict = e.get("validator_verdict", "skipped")
            emoji = _VERDICT_EMOJI.get(verdict, "❓")
            lines.append(
                f"| {i} "
                f"| {_trunc(e.get('claim_text', ''))} "
                f"| {emoji} {verdict} "
                f"| {e.get('confidence', 0.50):.2f} "
                f"| {_trunc(e.get('validator_explanation', ''))} "
                f"| {e.get('status', 'pending_review')} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_review_queue(run_id: str, source_file: str, verdicts: list[dict]) -> None:
    """Append claim records and regenerate review-queue.md. Raises OSError on write failure."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    new_entries = [
        {
            "timestamp": now,
            "run_id": run_id,
            "source_file": source_file,
            "claim_text": v["claim_text"],
            "confidence": v["confidence"],
            "validator_verdict": v["verdict"],
            "validator_explanation": v["explanation"],
            "status": "pending_review",
        }
        for v in verdicts
    ]

    with _queue_lock:
        _append_and_regen(new_entries)


def _append_and_regen(new_entries: list[dict]) -> None:
    mode = "a" if QUEUE_JSONL.exists() else "w"
    with open(QUEUE_JSONL, mode, encoding="utf-8") as f:
        for entry in new_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()

    # Regenerate the human-readable MD from the full JSONL
    all_entries: list[dict] = []
    try:
        for line in QUEUE_JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(f"Skipping malformed queue line: {line[:80]}")
    except OSError as e:
        logger.warning(f"Could not read queue for MD regeneration: {e}")

    QUEUE_MD.write_text(_regen_md(all_entries), encoding="utf-8")


# ──────────────────────────────────────────────
# STAGE 5 — ENRICH PAPER_DRAFT.MD
# ──────────────────────────────────────────────
def _count_verdicts(verdicts: list[dict]) -> tuple[int, int, int]:
    passed = sum(1 for v in verdicts if v["verdict"] == "pass")
    failed = sum(1 for v in verdicts if v["verdict"] == "fail")
    skipped = sum(1 for v in verdicts if v["verdict"] == "skipped")
    return passed, failed, skipped


def enrich_paper(paper_text: str, run_id: str, verdicts: list[dict]) -> str:
    """Return a copy of paper_text with validation_summary frontmatter and warning block."""
    now = datetime.now(timezone.utc).isoformat()
    passed, failed, skipped = _count_verdicts(verdicts)
    failed_claims = [v["claim_text"] for v in verdicts if v["verdict"] == "fail"]

    summary_yaml = (
        f"validation_summary:\n"
        f'  run_id: "{run_id}"\n'
        f'  validated_at: "{now}"\n'
        f"  total_claims: {len(verdicts)}\n"
        f"  passed: {passed}\n"
        f"  failed: {failed}\n"
        f"  skipped: {skipped}\n"
    )
    if failed_claims:
        summary_yaml += "  failed_claims:\n"
        for c in failed_claims:
            escaped = c.replace('"', "'")
            summary_yaml += f'    - "{escaped}"\n'
    else:
        summary_yaml += "  failed_claims: []\n"

    if failed > 0:
        notice = (
            "> ⚠️ **Validation Warning:** This paper contains claims that did not pass\n"
            "> automated validation. Review flagged entries before treating this document\n"
            "> as authoritative.\n"
            "> See `vault/system/review-queue.md` for details.\n"
        )
    elif skipped > 0:
        notice = (
            f"> ℹ️ **Validation Note:** Automated validation was unavailable for\n"
            f"> {skipped} claim(s). Results are unverified.\n"
            f"> See `vault/system/review-queue.md` for details.\n"
        )
    else:
        notice = ""

    fm_re = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    match = fm_re.match(paper_text)

    if match:
        fm_body = match.group(1)
        new_fm = f"---\n{fm_body}\n{summary_yaml}---\n"
        rest = paper_text[match.end() :]
        return new_fm + (notice + "\n" if notice else "") + rest
    else:
        new_fm = f"---\n{summary_yaml}---\n"
        return new_fm + (notice + "\n" if notice else "") + paper_text


# ──────────────────────────────────────────────
# STAGE 6 — COPY TO ARCHIVES (destination derivation)
# ──────────────────────────────────────────────
def _derive_title(paper_text: str, run_id: str) -> str:
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", paper_text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            m = re.match(r'^title:\s*["\']?(.+?)["\']?\s*$', line)
            if m:
                return m.group(1).strip()
    h1 = re.search(r"^#\s+(.+)", paper_text, re.MULTILINE)
    if h1:
        return h1.group(1).strip()
    return run_id


def _destination_path(paper_text: str, run_id: str) -> Path:
    title = _derive_title(paper_text, run_id)
    safe = sanitize_filename(title)
    dest = ARCHIVE_PATH / f"{safe}.md"
    if dest.exists():
        dest = ARCHIVE_PATH / f"{safe}_{run_id}.md"
    return dest


# ──────────────────────────────────────────────
# STAGE 7 — TRIGGER LIGHTRAG INDEXING
# ──────────────────────────────────────────────
async def _trigger_indexing(dest_path: Path) -> None:
    from index_archive import index_single_file

    await index_single_file(dest_path)


# ──────────────────────────────────────────────
# PIPELINE RUNNER
# ──────────────────────────────────────────────
async def run_pipeline(artifact_dir: Path) -> int:
    """Run all 7 stages. Returns an exit code (0 = success, 1 = error, 2 = indexing failure)."""
    run_id = artifact_dir.name
    logger.info(f"Starting validation pipeline for {run_id}")

    # Stage 1
    try:
        paper_path, summary_path = locate_artifacts(artifact_dir)
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    # Stage 2
    claims, extraction_path = extract_claims(paper_path, summary_path)
    logger.info(f"Extracted {len(claims)} claims via {extraction_path} path")
    if not claims:
        logger.warning("No claims extracted — validation skipped.")

    paper_text = paper_path.read_text(encoding="utf-8")

    # Build validation context
    if extraction_path == "primary":
        context = _extract_section(paper_text, r"^#{1,3}\s*(\d+\.\s*)?abstract") or paper_text[:800]
    else:
        abstract = _extract_section(paper_text, r"^#{1,3}\s*(\d+\.\s*)?abstract")
        conclusion = _extract_section(paper_text, r"^#{1,3}\s*(\d+\.\s*)?conclusion")
        context = (abstract + "\n\n" + conclusion).strip() or paper_text[:800]

    # Stage 3
    verdicts = await validate_claims(claims, context) if claims else []

    # Pre-derive destination path so queue entry has the correct source_file
    ARCHIVE_PATH.mkdir(parents=True, exist_ok=True)
    dest_path = _destination_path(paper_text, run_id)
    try:
        source_file = str(dest_path.relative_to(VAULT_PATH)).replace("\\", "/")
    except ValueError:
        source_file = str(dest_path)

    # Stage 4 — Write review queue (abort on failure; queue integrity is priority)
    try:
        write_review_queue(run_id, source_file, verdicts)
    except OSError as e:
        logger.error(f"Queue write failed: {e}")
        return 1

    # Stage 5 — Enrich (in-memory copy only)
    enriched = enrich_paper(paper_text, run_id, verdicts)

    # Stage 6 — Write to Archives
    dest_path.write_text(enriched, encoding="utf-8")
    logger.info(f"Archived to: {dest_path}")

    # Stage 7 — Trigger LightRAG indexing
    try:
        await _trigger_indexing(dest_path)
    except Exception as e:
        logger.error(f"LightRAG indexing failed: {e}")
        return 2

    logger.info(f"Pipeline complete for {run_id}")
    return 0


# ──────────────────────────────────────────────
# WATCH MODE
# ──────────────────────────────────────────────
async def watch_mode() -> None:
    processed: set[str] = set()
    logger.info(f"Watch mode: polling {ARTIFACTS_DIR} every 30s. Ctrl-C to exit.")
    try:
        while True:
            if ARTIFACTS_DIR.exists():
                for entry in sorted(ARTIFACTS_DIR.iterdir()):
                    if not entry.is_dir() or not entry.name.startswith("rc-"):
                        continue
                    if entry.name in processed:
                        continue
                    if not (entry / "pipeline_summary.json").exists():
                        continue
                    logger.info(f"New artifact detected: {entry.name}")
                    code = await run_pipeline(entry)
                    processed.add(entry.name)
                    if code != 0:
                        logger.warning(f"Pipeline for {entry.name} exited with code {code}")
            else:
                logger.debug(f"Artifacts directory not found: {ARTIFACTS_DIR}")
            await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("Watch mode stopped.")


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and archive AutoResearchClaw paper artifacts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--artifact",
        type=Path,
        metavar="DIR",
        help="Path to rc-<run_id>/ artifact directory.",
    )
    group.add_argument(
        "--watch",
        action="store_true",
        help="Poll autoresearchclaw/artifacts/ every 30s for new runs.",
    )
    args = parser.parse_args()

    if args.watch:
        asyncio.run(watch_mode())
    else:
        sys.exit(asyncio.run(run_pipeline(args.artifact)))
