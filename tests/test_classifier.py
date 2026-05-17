from pathlib import Path

from index_archive import _classify_content_type, _select_pipeline


# ── _classify_content_type ─────────────────────────────────────────────────

def test_classify_fetch_papers_path():
    assert _classify_content_type(
        Path("4. Archives/fetch_papers/attention_is_all_you_need.md"), "some content"
    ) == "research_paper"


def test_classify_news_ingest_path():
    assert _classify_content_type(
        Path("4. Archives/news_ingest/techcrunch_2025.md"), "content"
    ) == "news_article"


def test_classify_validate_and_archive_path():
    assert _classify_content_type(
        Path("4. Archives/validate_and_archive/claim_report.md"), "content"
    ) == "validated_artifact"


def test_classify_autoresearchlaw_artifacts():
    assert _classify_content_type(
        Path("autoresearchlaw/artifacts/paper.md"), "content"
    ) == "research_paper"


def test_classify_personal_note_short_content():
    assert _classify_content_type(
        Path("4. Archives/notes/quick_note.md"), "short"
    ) == "personal_note"


def test_classify_personal_note_boundary():
    content = "x" * 499
    assert _classify_content_type(Path("4. Archives/notes/note.md"), content) == "personal_note"
    content = "x" * 500
    assert _classify_content_type(Path("4. Archives/notes/note.md"), content) == "general"


def test_classify_dateline_news_article():
    content = "Monday, April 14, 2025\nSome headline here.\nMore text follows."
    assert _classify_content_type(Path("4. Archives/notes/article.md"), content) == "news_article"


def test_classify_general_fallback():
    content = "x" * 600
    assert _classify_content_type(Path("4. Archives/misc/doc.md"), content) == "general"


def test_classify_honors_frontmatter():
    content = "---\ncontent_type: meeting_note\nsource: manual\n---\n\nSome long meeting content " + "x" * 600
    # Frontmatter says meeting_note; path would otherwise yield general
    assert _classify_content_type(Path("4. Archives/misc/meeting.md"), content) == "meeting_note"


def test_classify_ignores_invalid_frontmatter_type():
    content = "---\ncontent_type: bogus_type\n---\n\n" + "x" * 600
    # Invalid content_type in frontmatter → falls through to path/content rules
    assert _classify_content_type(Path("4. Archives/misc/doc.md"), content) == "general"


# ── _select_pipeline ───────────────────────────────────────────────────────

def test_pipeline_a_types():
    for ct in ("research_paper", "validated_artifact", "general"):
        assert _select_pipeline(ct) == "A", f"Expected A for {ct}"


def test_pipeline_b_types():
    for ct in ("news_article", "meeting_note", "personal_note"):
        assert _select_pipeline(ct) == "B", f"Expected B for {ct}"
