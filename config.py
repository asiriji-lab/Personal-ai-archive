"""
🧠 ZeroCostBrain — Central Configuration

All paths, model settings, and runtime options live here.
Override any value via environment variables or a `.env` file.
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars still work

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
VAULT_PATH = Path(os.getenv("BRAIN_VAULT_PATH", "./knowledge_base"))
ARCHIVE_PATH = VAULT_PATH / "4. Archives"
RESOURCES_PATH = VAULT_PATH / "3. Resources"
WORKING_DIR = VAULT_PATH / ".lightrag"

# ──────────────────────────────────────────────
# LLM PROVIDER  ("LOCAL" or "GEMINI")
# ──────────────────────────────────────────────
LLM_PROVIDER = os.getenv("BRAIN_LLM_PROVIDER", "LOCAL").upper()

# Local (Ollama)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LOCAL_LLM_MODEL = os.getenv("BRAIN_LOCAL_MODEL", "qwen3.5:4b-brain")
EMBED_MODEL = os.getenv("BRAIN_EMBED_MODEL", "nomic-embed-text")
LOCAL_CONTEXT_WINDOW = int(os.getenv("BRAIN_CONTEXT_WINDOW", "4096"))

# Cloud (Gemini)
GEMINI_MODEL = os.getenv("BRAIN_GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ──────────────────────────────────────────────
# INDEXER SETTINGS
# ──────────────────────────────────────────────
CHUNK_MAX_CHARS = int(os.getenv("BRAIN_CHUNK_SIZE", "1500"))
if CHUNK_MAX_CHARS > 1500:
    import warnings

    warnings.warn(f"BRAIN_CHUNK_SIZE={CHUNK_MAX_CHARS} exceeds safe limit of 1500 for RTX 4050 6GB")
INDEX_MANIFEST_FILE = "index_manifest.json"
INDEX_FAILURES_FILE = "index_failures.json"
INDEX_MAX_RETRIES = int(os.getenv("BRAIN_INDEX_MAX_RETRIES", "3"))
INDEX_RETRY_BACKOFF = [5, 15, 30]  # seconds between retries

# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────
from typing import TypedDict


class RAGConfig(TypedDict):
    working_dir: str
    llm_provider: str
    chunk_max_chars: int


_SKELETON_DIRS = [
    VAULT_PATH / "1. Projects",
    VAULT_PATH / "2. Areas",
    RESOURCES_PATH,  # 3. Resources
    ARCHIVE_PATH,  # 4. Archives
    VAULT_PATH / "system",
]


def validate_paths():
    """Ensure critical directories exist, creating the skeleton vault if needed."""
    bootstrapped = []
    for d in _SKELETON_DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            bootstrapped.append(d)

    if bootstrapped:
        print("🗂️  First run: created vault skeleton:", file=sys.stderr)
        for d in bootstrapped:
            print(f"   {d}", file=sys.stderr)
        print("💡 To use an existing Obsidian vault, set BRAIN_VAULT_PATH in .env\n", file=sys.stderr)


def is_safe_path(target_path: Path, base_path: Path) -> bool:
    """Ensure that the target_path strictly resolves within the base_path boundary."""
    try:
        resolved_target = target_path.resolve()
        resolved_base = base_path.resolve()
        return resolved_target.is_relative_to(resolved_base)
    except Exception:
        return False
