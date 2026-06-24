import logging
import os
import tempfile

import pytest

from utils import chunk_text, chunk_text_sections, file_hash, sanitize_filename, setup_logging


def test_chunk_text():
    # Edge case: empty text
    assert chunk_text("", 100) == [""]

    # Short text
    assert chunk_text("Hello world", 100) == ["Hello world"]

    # Paragraph splitting
    text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
    assert chunk_text(text, 20) == ["Paragraph 1", "Paragraph 2", "Paragraph 3"]

    # Sentence fallback
    long_para = "This is sentence one. This is sentence two. This is sentence three."
    assert chunk_text(long_para, 30) == ["This is sentence one.", "This is sentence two.", "This is sentence three."]


def test_sanitize_filename():
    assert sanitize_filename("safe_name.md") == "safe_name.md"
    assert sanitize_filename("unsafe/name\\test?*.txt") == "unsafe_name_test__.txt"
    assert sanitize_filename("..traversal") == "traversal"
    assert sanitize_filename("valid\u1234.md") == "valid\u1234.md"

    with pytest.raises(ValueError):
        sanitize_filename("")

    with pytest.raises(ValueError):
        sanitize_filename("..")


def test_file_hash():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        tmp_path = f.name

    try:
        hash1 = file_hash(tmp_path)
        hash2 = file_hash(tmp_path)
        assert hash1 == hash2
        assert len(hash1) == 32
    finally:
        os.unlink(tmp_path)


def test_chunk_text_sections_with_headings():
    text = "Intro paragraph.\n\n## Background\nBG content.\n\n## Method\nMethod details.\n\n## Results\nResults here."
    chunks = chunk_text_sections(text, max_chars=500)
    # First chunk is the summary (first para + all headings)
    assert "## Background" in chunks[0]
    assert "## Method" in chunks[0]
    assert "## Results" in chunks[0]
    assert "Intro paragraph." in chunks[0]
    # Remaining chunks are individual sections
    assert any("## Background" in c for c in chunks[1:])
    assert any("## Method" in c for c in chunks[1:])
    assert any("## Results" in c for c in chunks[1:])


def test_chunk_text_sections_no_headings():
    text = "Just a plain paragraph without any headings."
    chunks = chunk_text_sections(text, max_chars=500)
    assert chunks == [text]


def test_chunk_text_sections_oversized_section():
    # A section body that exceeds max_chars should be sub-chunked
    body = "word " * 300  # ~1500 chars
    text = f"## Big Section\n{body}"
    chunks = chunk_text_sections(text, max_chars=200)
    # Summary + multiple sub-chunks from the oversized section
    assert len(chunks) > 2
    assert all(len(c) <= 200 or c.startswith("##") for c in chunks[1:])


def test_chunk_text_sections_no_preamble():
    text = "## First Section\nContent A.\n\n## Second Section\nContent B."
    chunks = chunk_text_sections(text, max_chars=500)
    # Summary contains headings even with no preamble
    assert "## First Section" in chunks[0]
    assert "## Second Section" in chunks[0]


def test_setup_logging():
    # Should not crash on multiple calls
    setup_logging(logging.DEBUG)
    setup_logging(logging.INFO)
    assert True
