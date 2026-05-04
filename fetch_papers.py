"""
ZeroCostBrain — Paper Fetcher

Two sources:
  1. arXiv RSS feeds (rss.arxiv.org) — filtered by keywords from papers_config.yaml
  2. Hugging Face Daily Papers — community-curated top papers, no keyword filter needed

Both write rich markdown into knowledge_base/4. Archives/AI Papers/YYYY-MM/.
Dedup by arXiv ID across both sources.

Usage:
    python fetch_papers.py               # incremental (new papers only)
    python fetch_papers.py --dry-run     # print what would be saved, don't write
    python fetch_papers.py --no-hf       # skip Hugging Face, arXiv only
    python fetch_papers.py --no-arxiv    # skip arXiv, HF only
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
CONFIG_PATH = PROJECT_ROOT / "papers_config.yaml"

ARXIV_RSS = "https://rss.arxiv.org/rss/{category}"

# XML namespaces used by arXiv RSS 2.0
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"ERROR: Config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# MANIFEST (dedup by arXiv ID)
# ──────────────────────────────────────────────
def _load_manifest(manifest_path: Path) -> set[str]:
    if manifest_path.exists():
        try:
            return set(json.loads(manifest_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            print("  WARNING: Corrupt manifest — starting fresh.")
    return set()


def _save_manifest(manifest_path: Path, seen_ids: set[str]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(sorted(seen_ids), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────
# RSS PARSER
# ──────────────────────────────────────────────
def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _extract_arxiv_id(link: str) -> str:
    """Extract arXiv ID from abstract URL like https://arxiv.org/abs/2604.08133"""
    m = re.search(r"arxiv\.org/abs/([^\s?]+)", link)
    return m.group(1) if m else ""


def _fetch_rss(category: str, timeout: int = 15) -> list[dict]:
    """Fetch and parse one arXiv RSS feed. Returns list of paper dicts."""
    url = ARXIV_RSS.format(category=category)
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ZeroCostBrain/1.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  FEED ERROR [{category}]: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  PARSE ERROR [{category}]: {e}", file=sys.stderr)
        return []

    papers = []
    for item in root.findall(".//item"):
        title_raw = item.findtext("title") or ""
        link = (item.findtext("link") or "").strip()
        abstract_raw = item.findtext("description") or ""
        authors_raw = item.findtext("dc:creator", namespaces=NS) or ""

        # arXiv RSS titles look like "[2604.08133] Paper Title"
        title = re.sub(r"^\[\d+\.\d+v?\d*\]\s*", "", _strip_html(title_raw)).strip()
        abstract = _strip_html(abstract_raw).strip()
        arxiv_id = _extract_arxiv_id(link)

        if not arxiv_id or not title:
            continue

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors_raw.strip(),
                "link": link,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "category": category,
            }
        )

    return papers


# ──────────────────────────────────────────────
# HUGGING FACE DAILY PAPERS
# ──────────────────────────────────────────────
def _fetch_hf_daily_papers() -> list[dict]:
    """Fetch today's Hugging Face Daily Papers via the HF papers API."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"https://huggingface.co/api/papers?date={today}"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "ZeroCostBrain/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  HF ERROR: {e}", file=sys.stderr)
        return []

    papers = []
    for item in data:
        arxiv_id = item.get("id", "")
        if not arxiv_id:
            continue
        title = item.get("title", "")
        abstract = (item.get("summary") or item.get("ai_summary") or "").replace("\n", " ").strip()
        author_list = item.get("authors", [])
        authors = ", ".join((a.get("name", "") if isinstance(a, dict) else str(a)) for a in author_list[:8])
        if len(author_list) > 8:
            authors += f" + {len(author_list) - 8} more"
        upvotes = item.get("upvotes", 0)

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "link": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "category": "HF-Daily",
                "upvotes": upvotes,
            }
        )

    # Sort by upvotes so the most community-validated papers come first
    papers.sort(key=lambda p: p["upvotes"], reverse=True)
    return papers


# ──────────────────────────────────────────────
# KEYWORD FILTER
# ──────────────────────────────────────────────
def _matches_any_keyword(paper: dict, keywords: list[str]) -> bool:
    """Return True if any keyword appears in title or abstract (case-insensitive)."""
    text = (paper["title"] + " " + paper["abstract"]).lower()
    for kw in keywords:
        # Match all words in the keyword phrase (order-insensitive)
        words = kw.lower().split()
        if all(w in text for w in words):
            return True
    return False


# ──────────────────────────────────────────────
# MARKDOWN WRITER
# ──────────────────────────────────────────────
def _safe_filename(arxiv_id: str, title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug)[:50].strip("-")
    return f"{arxiv_id.replace('/', '_')}_{slug}.md"


def _write_paper(paper: dict, output_dir: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    folder = output_dir / today
    folder.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(paper["arxiv_id"], paper["title"])
    filepath = folder / filename

    upvotes_line = f"\n**HF Upvotes:** {paper['upvotes']}" if paper.get("upvotes") else ""
    content = f"""# {paper["title"]}

**arXiv ID:** [{paper["arxiv_id"]}](https://arxiv.org/abs/{paper["arxiv_id"]})
**Ingested:** {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
**Authors:** {paper["authors"]}
**Category:** {paper["category"]}{upvotes_line}
**PDF:** {paper["pdf_url"]}

## Abstract

{paper["abstract"]}

## Links

- Abstract: {paper["link"]}
- PDF: {paper["pdf_url"]}
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def fetch_papers(dry_run: bool = False, skip_arxiv: bool = False, skip_hf: bool = False) -> None:
    cfg = _load_config()
    settings = cfg.get("settings", {})

    output_dir = PROJECT_ROOT / settings.get("output_dir", "knowledge_base/4. Archives/AI Papers")
    manifest_path = PROJECT_ROOT / settings.get("manifest", "data/papers_manifest.json")

    keywords = cfg.get("keywords", [])
    categories = cfg.get("categories", ["cs.AI", "cs.LG", "cs.CL"])

    seen_ids = _load_manifest(manifest_path)
    print(f"Manifest: {len(seen_ids)} papers already ingested.\n")

    all_papers: dict[str, dict] = {}

    # ── Source 1: arXiv RSS ───────────────────
    if not skip_arxiv:
        weekday = datetime.now(timezone.utc).weekday()  # 5=Sat, 6=Sun
        if weekday >= 5:
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
            print(f"NOTE: Today is {day_name}. arXiv does not publish on weekends — feeds will be empty.")
        else:
            print(f"arXiv RSS — {len(categories)} categories | {len(keywords)} keyword filters")
            for category in categories:
                print(f"  [{category}]...", end=" ", flush=True)
                papers = _fetch_rss(category)
                for p in papers:
                    all_papers[p["arxiv_id"]] = p
                print(f"{len(papers)} entries")

    # ── Source 2: Hugging Face Daily Papers ───
    if not skip_hf:
        print("\nHugging Face Daily Papers...")
        hf_papers = _fetch_hf_daily_papers()
        added = 0
        for p in hf_papers:
            if p["arxiv_id"] not in all_papers:  # arXiv wins on collision
                all_papers[p["arxiv_id"]] = p
                added += 1
        print(f"  {len(hf_papers)} fetched, {added} new (not already in arXiv batch)")

    print(f"\nTotal unique candidates: {len(all_papers)}")
    print("Filtering arXiv by keywords, keeping all HF Daily...\n")

    total_new = 0
    total_skipped = 0

    for arxiv_id, paper in all_papers.items():
        if arxiv_id in seen_ids:
            total_skipped += 1
            continue

        # HF Daily papers pass through without keyword filter (already curated)
        if paper["category"] != "HF-Daily" and not _matches_any_keyword(paper, keywords):
            continue

        if dry_run:
            src = "[HF]" if paper["category"] == "HF-Daily" else "[arXiv]"
            upvotes = f" ▲{paper['upvotes']}" if paper.get("upvotes") else ""
            print(f"  [dry-run] {src}{upvotes} {arxiv_id} — {paper['title'][:60]}")
        else:
            path = _write_paper(paper, output_dir)
            print(f"  + {path.relative_to(PROJECT_ROOT)}")
            seen_ids.add(arxiv_id)
            _save_manifest(manifest_path, seen_ids)

        total_new += 1

    print(f"\nDone. {total_new} new papers saved, {total_skipped} already known.")
    if total_new > 0 and not dry_run:
        print("Run `python index_archive.py` to index new papers into LightRAG.")


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI papers from arXiv + HuggingFace into Archives.")
    parser.add_argument("--dry-run", action="store_true", help="Print matches without writing.")
    parser.add_argument("--no-arxiv", action="store_true", help="Skip arXiv RSS source.")
    parser.add_argument("--no-hf", action="store_true", help="Skip Hugging Face Daily Papers.")
    args = parser.parse_args()

    fetch_papers(dry_run=args.dry_run, skip_arxiv=args.no_arxiv, skip_hf=args.no_hf)
