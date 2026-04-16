"""
🧠 ZeroCostBrain — Shared Utilities

Reusable functions for sanitization, chunking, and system monitoring.
"""

import os
import re
import subprocess


# ──────────────────────────────────────────────
# FILENAME SANITIZATION
# ──────────────────────────────────────────────
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAVERSAL = re.compile(r'\.\.')

def sanitize_filename(title: str) -> str:
    """
    Remove path-traversal sequences and unsafe characters from a filename.
    Raises ValueError if the result is empty or still dangerous.
    """
    cleaned = _TRAVERSAL.sub("", title)
    cleaned = _UNSAFE_CHARS.sub("_", cleaned).strip(". ")

    if not cleaned:
        raise ValueError(f"Invalid filename after sanitization: '{title}'")

    # Ensure no path separators snuck through
    if os.sep in cleaned or "/" in cleaned:
        raise ValueError(f"Path separator detected in filename: '{title}'")

    return cleaned


# ──────────────────────────────────────────────
# TEXT CHUNKING
# ──────────────────────────────────────────────
def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """
    Split text into chunks of approximately `max_chars` characters.
    Splits on paragraph boundaries (double newline) when possible,
    falling back to sentence boundaries, then hard cuts.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph exceeds the limit, flush
        if current_chunk and len(current_chunk) + len(para) + 2 > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If a single paragraph is too large, split it further
        if len(para) > max_chars:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    current_chunk += " " + sentence if current_chunk else sentence
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ──────────────────────────────────────────────
# GPU MONITORING
# ──────────────────────────────────────────────
def get_gpu_stats() -> dict:
    """
    Query nvidia-smi for GPU memory and utilization.
    Returns a dict with 'used_mb', 'total_mb', 'utilization', 'display'.
    Returns None values on failure.
    """
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]
        output = subprocess.check_output(cmd, shell=False, timeout=5).decode().strip()
        used, total, util = output.split(", ")
        return {
            "used_mb": int(used),
            "total_mb": int(total),
            "utilization": int(util),
            "display": f"{used}MB / {total}MB ({util}% Load)"
        }
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return {
            "used_mb": None,
            "total_mb": None,
            "utilization": None,
            "display": "GPU Offline"
        }

