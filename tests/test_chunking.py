"""Minimal checks for the C1 section-aware chunker."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import chunk_with_headings


def test_sections_labelled_and_preamble_blank():
    text = "# Title\n\nIntro.\n\n## Mechanism\n\nHow.\n\n### Detail\n\nDeep."
    pairs = chunk_with_headings(text, 1500)
    sections = [s for s, _ in pairs]
    assert sections == ["", "Mechanism", "Detail"]
    # every chunk keeps its body
    assert all(c.strip() for _, c in pairs)


def test_no_headings_returns_blank_section():
    assert chunk_with_headings("Just text.", 1500) == [("", "Just text.")]
