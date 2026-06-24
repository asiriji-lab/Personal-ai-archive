"""
Tests for the 2026-05-17 GPU/VRAM fixes (Bugs 8-11).

Unit tests (no Ollama): run with  pytest tests/test_gpu_vram_fixes.py
Live tests (needs Ollama): pytest tests/test_gpu_vram_fixes.py -m live
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import index_archive
from index_archive import (
    _INDEXABLE_EXTENSIONS,
    _index_single_file,
    _prepend_frontmatter,
)

OLLAMA_HOST = "http://127.0.0.1:11434"


# ── helpers ───────────────────────────────────────────────────────────────────

def _ollama_ps() -> list[dict]:
    """Return currently loaded Ollama models. Empty list if Ollama unreachable."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/ps", timeout=3) as r:
            return json.loads(r.read()).get("models", [])
    except Exception:
        return []


def _ollama_reachable() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def _gpu_total_mb() -> int | None:
    """Return total GPU VRAM in MB via nvidia-smi, or None if unavailable."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        )
        return int(out.strip())
    except Exception:
        return None


# ── Bug 10: extension whitelist ───────────────────────────────────────────────

class TestExtensionWhitelist:
    """_index_single_file must reject any file type not in _INDEXABLE_EXTENSIONS."""

    @pytest.mark.parametrize("ext", [".cir", ".xml", ".pdf", ".docx", ".py", ".json", ".csv", ""])
    def test_non_markdown_rejected(self, tmp_path, ext):
        fname = f"circuit{ext}" if ext else "no_extension"
        f = tmp_path / fname
        f.write_text("<cir f='1'><r x='1 2 3 4'/></cir>" * 10)

        async def run():
            rag = MagicMock()
            rag.ainsert = AsyncMock()
            return await _index_single_file(rag, str(f))

        success, error, _, _ = asyncio.run(run())
        assert success is False, f"Expected rejection for '{ext}', got success"
        assert "Unsupported file type" in error or "not in" in error.lower() or ext in error

    @pytest.mark.parametrize("ext", [".md", ".txt"])
    def test_markdown_and_txt_accepted(self, tmp_path, ext):
        f = tmp_path / f"note{ext}"
        f.write_text("# Title\n\n" + "word " * 60)

        async def run():
            rag = MagicMock()
            rag.ainsert = AsyncMock()
            with patch("index_archive._prepend_frontmatter"):
                return await _index_single_file(rag, str(f))

        success, error, _, _ = asyncio.run(run())
        assert success is True, f"Expected acceptance for '{ext}', got error: {error}"

    def test_indexable_extensions_set_contents(self):
        assert ".md" in _INDEXABLE_EXTENSIONS
        assert ".txt" in _INDEXABLE_EXTENSIONS
        assert ".cir" not in _INDEXABLE_EXTENSIONS
        assert ".xml" not in _INDEXABLE_EXTENSIONS
        assert ".pdf" not in _INDEXABLE_EXTENSIONS


# ── Bug 10: _prepend_frontmatter data-corruption guard ───────────────────────

class TestPrependFrontmatterGuard:
    """_prepend_frontmatter must not write to non-markdown files."""

    def test_cir_file_not_mutated(self, tmp_path):
        original = "<cir f='1'><r x='1 2 3 4'/></cir>"
        f = tmp_path / "circuit.cir"
        f.write_text(original)
        _prepend_frontmatter(str(f), "general", "A", indexed_at="2026-05-17T00:00:00+00:00")
        assert f.read_text() == original, ".cir file must not be mutated"

    def test_xml_file_not_mutated(self, tmp_path):
        original = "<?xml version='1.0'?><root/>"
        f = tmp_path / "data.xml"
        f.write_text(original)
        _prepend_frontmatter(str(f), "general", "A")
        assert f.read_text() == original

    def test_pdf_file_not_mutated(self, tmp_path):
        original = b"%PDF-1.4 fake"
        f = tmp_path / "doc.pdf"
        f.write_bytes(original)
        _prepend_frontmatter(str(f), "general", "A")
        assert f.read_bytes() == original

    def test_md_file_still_gets_frontmatter(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("Body text.")
        _prepend_frontmatter(str(f), "general", "A", indexed_at="2026-05-17T00:00:00+00:00")
        assert f.read_text().startswith("---\n")


# ── Bug 11: infrastructure error aborts batch ─────────────────────────────────

class TestInfrastructureErrorAbort:
    """Ollama 500 errors must re-raise from _index_single_file, not soft-fail."""

    def test_ollama_500_re_raises(self, tmp_path):
        # >500 chars stripped so classifier returns "general" → Pipeline A → rag.ainsert is called
        f = tmp_path / "article.md"
        f.write_text("# Title\n\n" + "word " * 120)

        class FakeOllamaError(Exception):
            pass

        ollama_500_msg = "memory layout cannot be allocated with num_gpu = 99 (status code: 500)"

        async def run():
            rag = MagicMock()
            rag.ainsert = AsyncMock(side_effect=FakeOllamaError(ollama_500_msg))
            with patch("index_archive._prepend_frontmatter"):
                return await _index_single_file(rag, str(f))

        with pytest.raises(FakeOllamaError):
            asyncio.run(run())

    def test_status_code_minus1_re_raises(self, tmp_path):
        """LightRAG re-wraps with status code: -1 but message still contains the 500 text."""
        f = tmp_path / "article.md"
        f.write_text("# Title\n\n" + "word " * 120)

        wrapped_msg = (
            "C[1/1]: chunk-abc123: memory layout cannot be allocated "
            "with num_gpu = 28 (status code: -1)"
        )

        async def run():
            rag = MagicMock()
            rag.ainsert = AsyncMock(side_effect=RuntimeError(wrapped_msg))
            with patch("index_archive._prepend_frontmatter"):
                return await _index_single_file(rag, str(f))

        with pytest.raises(RuntimeError):
            asyncio.run(run())

    def test_content_error_does_not_re_raise(self, tmp_path):
        """Non-infrastructure errors (e.g. JSON parse failure) must NOT re-raise — they soft-fail."""
        # >500 chars stripped → "general" → Pipeline A → rag.ainsert called
        f = tmp_path / "article.md"
        f.write_text("# Title\n\n" + "word " * 120)

        async def run():
            rag = MagicMock()
            rag.ainsert = AsyncMock(side_effect=ValueError("unexpected JSON token"))
            with patch("index_archive._prepend_frontmatter"):
                return await _index_single_file(rag, str(f), max_retries=1)

        success, error, _, _ = asyncio.run(run())
        assert success is False
        assert "JSON" in error


# ── Bug 8/9: VRAM model sizing (live diagnostic) ─────────────────────────────

@pytest.mark.live
class TestVRAMSizing:
    """
    Live tests requiring a running Ollama instance and nvidia-smi.
    Run with:  pytest tests/test_gpu_vram_fixes.py -m live -v
    """

    def test_ollama_is_reachable(self):
        assert _ollama_reachable(), "Ollama is not running at 127.0.0.1:11434"

    def test_gpu_vram_detectable(self):
        mb = _gpu_total_mb()
        assert mb is not None, "nvidia-smi not available — cannot measure VRAM"
        assert mb > 0

    def test_llm_and_embedder_exceed_vram_when_both_gpu(self):
        """
        Documents the hard constraint: qwen3.5:4b-brain (auto GPU) + nomic-embed-text (F16 GPU)
        exceed 6 GB VRAM and cannot coexist. This test PASSES when the constraint is confirmed,
        which tells you the CPU-embedder fix is required.
        """
        vram_mb = _gpu_total_mb()
        if vram_mb is None:
            pytest.skip("nvidia-smi not available")

        # Known measured sizes from /api/ps on this machine
        LLM_VRAM_MB = 5651      # qwen3.5:4b-brain at num_gpu=-1 (auto)
        EMBED_VRAM_MB = 567     # nomic-embed-text:latest F16 (595142656 bytes / 1048576)
        WDDM_OVERHEAD_MB = 500  # conservative Windows GPU driver baseline

        total_needed = LLM_VRAM_MB + EMBED_VRAM_MB + WDDM_OVERHEAD_MB
        assert total_needed > vram_mb, (
            f"Constraint not present: {total_needed} MB needed vs {vram_mb} MB available. "
            f"If both models now fit, the CPU-embedder workaround may be unnecessary."
        )

    def test_nomic_embed_cpu_model_exists(self):
        """nomic-embed-text-cpu must exist in Ollama (created via Modelfile with num_gpu 0)."""
        try:
            import urllib.request
            with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as r:
                tags = json.loads(r.read())
            names = [m["name"] for m in tags.get("models", [])]
            assert any("nomic-embed-text-cpu" in n for n in names), (
                "nomic-embed-text-cpu not found in Ollama. Create it with:\n"
                "  ollama create nomic-embed-text-cpu -f <Modelfile with 'PARAMETER num_gpu 0'>"
            )
        except Exception as e:
            pytest.fail(f"Could not reach Ollama tags endpoint: {e}")

    def test_nomic_embed_cpu_uses_zero_vram(self):
        """After loading nomic-embed-text-cpu, it must appear in /api/ps with 0 VRAM."""
        import time
        import urllib.request

        if not _ollama_reachable():
            pytest.skip("Ollama not running")

        # Trigger a load by calling the embed endpoint
        try:
            import ollama
            client = ollama.Client(host=OLLAMA_HOST)
            client.embed(model="nomic-embed-text-cpu", input=["test"])
        except Exception as e:
            pytest.skip(f"Could not load nomic-embed-text-cpu: {e}")

        time.sleep(1)
        models = _ollama_ps()
        cpu_model = next((m for m in models if "nomic-embed-text-cpu" in m["name"]), None)

        assert cpu_model is not None, "nomic-embed-text-cpu not found in /api/ps after load"
        assert cpu_model.get("size_vram", -1) == 0, (
            f"Expected 0 VRAM for CPU model, got {cpu_model.get('size_vram')} bytes. "
            f"The num_gpu=0 Modelfile parameter is not taking effect."
        )

    def test_embedding_call_succeeds_with_cpu_model(self):
        """End-to-end: embed a string via nomic-embed-text-cpu and get a 768-dim vector."""
        if not _ollama_reachable():
            pytest.skip("Ollama not running")

        try:
            import numpy as np
            import ollama
            client = ollama.Client(host=OLLAMA_HOST)
            result = client.embed(model="nomic-embed-text-cpu", input=["hello world"])
            vec = np.array(result["embeddings"][0])
            assert vec.shape == (768,), f"Expected 768-dim embedding, got {vec.shape}"
            assert not (vec == 0).all(), "Embedding is all zeros — model may not have loaded"
        except Exception as e:
            pytest.fail(f"Embedding call failed: {e}")
