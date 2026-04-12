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
VAULT_PATH = Path(os.getenv(
    "BRAIN_VAULT_PATH",
    "./knowledge_base"
))
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
GEMINI_MODEL = os.getenv("BRAIN_GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ──────────────────────────────────────────────
# INDEXER SETTINGS
# ──────────────────────────────────────────────
CHUNK_MAX_CHARS = int(os.getenv("BRAIN_CHUNK_SIZE", "1500"))
INDEX_MANIFEST_FILE = "index_manifest.json"
INDEX_FAILURES_FILE = "index_failures.json"
INDEX_MAX_RETRIES = int(os.getenv("BRAIN_INDEX_MAX_RETRIES", "3"))
INDEX_RETRY_BACKOFF = [5, 15, 30]  # seconds between retries

# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────
def validate_paths():
    """Check that critical directories exist at startup."""
    errors = []
    if not VAULT_PATH.exists():
        errors.append(f"Vault path not found: {VAULT_PATH}")
    if not ARCHIVE_PATH.exists():
        errors.append(f"Archive path not found: {ARCHIVE_PATH}")
    if errors:
        for e in errors:
            print(f"❌ CONFIG ERROR: {e}", file=sys.stderr)
        print("\n💡 Set BRAIN_VAULT_PATH in your .env file or environment.", file=sys.stderr)
        sys.exit(1)
