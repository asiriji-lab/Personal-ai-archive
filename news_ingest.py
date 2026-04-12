"""
ZeroCostBrain — News Ingest (Local RSS Scraper)

Pulls articles from RSS feeds, writes one markdown file per article
into knowledge_base/4. Archives/News_Ingest/.

No external APIs needed — just RSS + requests.

Usage:
    python news_ingest.py              # run once
    python news_ingest.py --limit 10   # limit articles per feed
"""

import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

from config import ARCHIVE_PATH

# ──────────────────────────────────────────────
# OUTPUT
# ──────────────────────────────────────────────
INGEST_PATH = ARCHIVE_PATH / "News_Ingest"

# ──────────────────────────────────────────────
# FEEDS
# ──────────────────────────────────────────────
FEEDS = [
    # Tech
    {"category": "Tech", "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en"},
    {"category": "Tech", "url": "https://news.google.com/rss/search?q=large+language+models&hl=en-US&gl=US&ceid=US:en"},
    # Finance
    {"category": "Finance", "url": "https://news.google.com/rss/search?q=federal+reserve+interest+rates&hl=en-US&gl=US&ceid=US:en"},
    {"category": "Finance", "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"},
    # Research (arXiv)
    {"category": "Research", "url": "https://rss.arxiv.org/rss/cs.AI"},
    {"category": "Research", "url": "https://rss.arxiv.org/rss/cs.LG"},
    # Lab Blogs
    {"category": "LabBlog", "url": "https://deepmind.google/blog/rss.xml"},
    {"category": "LabBlog", "url": "https://engineering.fb.com/feed/"},
    {"category": "LabBlog", "url": "https://qwenlm.github.io/blog/index.xml"},
    {"category": "LabBlog", "url": "https://machinelearning.apple.com/rss.xml"},
    {"category": "LabBlog", "url": "https://research.google/blog/rss/"},
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def _safe_filename(title: str, category: str) -> str:
    """Generate a short deterministic filename from title."""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_-]+', '_', slug)[:40].strip('_')
    uid = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"{category}_{slug}_{uid}.md"


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '').strip()


def _fetch_feed(url: str, timeout: int = 10) -> ET.Element | None:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ZeroCostBrain/1.0"})
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except Exception as e:
        print(f"  FEED ERROR {url[:60]}: {e}", file=sys.stderr)
        return None


def _already_ingested(path: Path) -> set[str]:
    """Return set of source URLs already written."""
    seen = set()
    for f in path.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("**Source:**"):
                seen.add(line.replace("**Source:**", "").strip())
    return seen


# ──────────────────────────────────────────────
# WRITE
# ──────────────────────────────────────────────
def _write_article(category: str, title: str, link: str, summary: str) -> Path:
    INGEST_PATH.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(title, category)
    filepath = INGEST_PATH / filename

    clean_summary = _strip_html(summary) or "No summary available."
    # Trim very long arXiv abstracts
    if len(clean_summary) > 1200:
        clean_summary = clean_summary[:1200].rsplit(' ', 1)[0] + "..."

    content = f"""# {title}

**Category:** {category}
**Source:** {link}
**Ingested:** {datetime.now().strftime('%Y-%m-%d')}

## Summary
{clean_summary}
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ──────────────────────────────────────────────
# INGEST
# ──────────────────────────────────────────────
def run_ingest(limit_per_feed: int = 5) -> None:
    INGEST_PATH.mkdir(parents=True, exist_ok=True)
    seen_urls = _already_ingested(INGEST_PATH)

    total_new = 0
    total_skipped = 0

    for feed in FEEDS:
        category = feed["category"]
        url = feed["url"]
        print(f"Fetching [{category}] {url[:70]}...")

        root = _fetch_feed(url)
        if root is None:
            continue

        # Handle both RSS 2.0 and Atom
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        count = 0

        for item in items:
            if count >= limit_per_feed:
                break

            # Extract fields (RSS 2.0)
            title = _strip_html(item.findtext("title") or "Untitled")
            link = (item.findtext("link") or "").strip()
            summary = item.findtext("description") or item.findtext("summary") or ""

            if not link or link in seen_urls:
                total_skipped += 1
                continue

            path = _write_article(category, title, link, summary)
            seen_urls.add(link)
            print(f"  + {path.name}")
            total_new += 1
            count += 1

    print(f"\nDone. {total_new} new articles, {total_skipped} skipped (already ingested).")
    if total_new > 0:
        print("Run `python embed.py` to index new articles into the vault.")


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest RSS news into the vault.")
    parser.add_argument("--limit", type=int, default=5, help="Max articles per feed (default: 5)")
    args = parser.parse_args()

    run_ingest(limit_per_feed=args.limit)
