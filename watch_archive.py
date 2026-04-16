"""
🧠 ZeroCostBrain — Archive Watcher (Auto-Indexer)

Monitors the Archives folder for file changes and triggers
incremental indexing automatically with a debounce period.

Usage:
    python watch_archive.py              # Watch with 60s debounce
    python watch_archive.py --debounce 30  # Custom debounce in seconds
"""

import asyncio
import logging
import sys
import threading
import time
import argparse
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import ARCHIVE_PATH, validate_paths
from index_archive import index_archive

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
# DEBOUNCED HANDLER
# ──────────────────────────────────────────────
class ArchiveChangeHandler(FileSystemEventHandler):
    """
    Watches for .md file changes in the Archives folder.
    Debounces rapid changes to avoid thrashing VRAM during bulk moves.
    """

    def __init__(self, debounce_seconds: int = 60):
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self._last_trigger = 0.0
        self._pending = False
        self._lock = threading.Lock()

    def _is_markdown(self, path: str) -> bool:
        return path.lower().endswith(".md")

    def _schedule_index(self, event_path: str, event_type: str):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_trigger

            if elapsed < self.debounce_seconds:
                if not self._pending:
                    self._pending = True
                    wait = self.debounce_seconds - elapsed
                    logger.info(
                        f"📋 Change detected ({event_type}: {Path(event_path).name}). "
                        f"Waiting {wait:.0f}s debounce..."
                    )
                return

            self._pending = False
            self._last_trigger = now

        logger.info(f"🔄 Change detected ({event_type}: {Path(event_path).name}). Starting index...")
        self._run_index()

    def _run_index(self):
        """Run the indexer in a fresh event loop."""
        try:
            asyncio.run(index_archive())
            logger.info("✅ Auto-index complete.")
        except Exception as e:
            logger.error(f"❌ Auto-index failed: {e}")

    def on_created(self, event):
        if not event.is_directory and self._is_markdown(event.src_path):
            self._schedule_index(event.src_path, "created")

    def on_modified(self, event):
        if not event.is_directory and self._is_markdown(event.src_path):
            self._schedule_index(event.src_path, "modified")

    def on_deleted(self, event):
        if not event.is_directory and self._is_markdown(event.src_path):
            logger.info(f"🗑️ Deleted: {Path(event.src_path).name} (manifest will update on next index)")

    def on_moved(self, event):
        if not event.is_directory and self._is_markdown(event.dest_path):
            self._schedule_index(event.dest_path, "moved")


# ──────────────────────────────────────────────
# BACKGROUND DEBOUNCE TICKER
# ──────────────────────────────────────────────
def _debounce_loop(handler: ArchiveChangeHandler):
    """
    Periodically checks if a debounced event is ready to fire.
    Runs in the main thread alongside the observer.
    """
    while True:
        time.sleep(5)  # check every 5 seconds
        fire = False
        with handler._lock:
            if handler._pending:
                elapsed = time.time() - handler._last_trigger
                if elapsed >= handler.debounce_seconds:
                    handler._pending = False
                    handler._last_trigger = time.time()
                    fire = True
        if fire:
            logger.info("⏰ Debounce window elapsed. Starting auto-index...")
            handler._run_index()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Watch Archives for changes and auto-index.")
    parser.add_argument(
        "--debounce", type=int, default=60,
        help="Seconds to wait after last change before indexing (default: 60)."
    )
    args = parser.parse_args()

    validate_paths()

    watch_path = str(ARCHIVE_PATH)
    handler = ArchiveChangeHandler(debounce_seconds=args.debounce)
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=True)

    logger.info(f"👁️ Watching: {watch_path}")
    logger.info(f"⏱️ Debounce: {args.debounce}s")
    logger.info("Press Ctrl+C to stop.\n")

    observer.start()

    try:
        _debounce_loop(handler)
    except KeyboardInterrupt:
        logger.info("\n🛑 Watcher stopped.")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
