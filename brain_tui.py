"""
🧠 ZeroCostBrain — Brain Command Center (The Cockpit)

A terminal UI dashboard for monitoring GPU, vault statistics,
and launching brain operations.
"""

import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from config import ARCHIVE_PATH, EMBED_MODEL, OLLAMA_HOST, VAULT_PATH, validate_paths
from utils import get_gpu_stats

console = Console()

# ──────────────────────────────────────────────
# SCRIPTS REGISTRY
# ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Always use the venv Python so all installed packages are available
_VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe")
PYTHON = _VENV_PYTHON if os.path.exists(_VENV_PYTHON) else sys.executable

SCRIPTS = {
    "1": ("Indexer", "index_archive.py"),
    "2": ("Resource Indexer", "embed.py"),
    "3": ("Bridge", "brain_server.py"),
    "4": ("Manual Query", "test_brain.py"),
    "5": ("News Harvester", "news_ingest.py"),
    "6": ("Brain Microscope", "brain_explorer.py"),
    "7": ("Auto-Watch", "watch_archive.py"),
    "8": ("Graph Watchdog", "visualize_graph.py"),
}

# Script that replaces slot "1" when indexing is detected running
_GRAPH_WATCHDOG = ("Graph Watchdog \\[indexing detected]", "visualize_graph.py")


def _script_exists(filename: str) -> bool:
    """Check if a script file exists in the project directory."""
    return os.path.exists(os.path.join(SCRIPT_DIR, filename))


_LOCK_FILE = Path(__file__).parent / ".indexer.lock"


def _is_indexer_running() -> bool:
    """Return True if index_archive.py is currently running as a live process."""
    if not _LOCK_FILE.exists():
        return False
    try:
        data = json.loads(_LOCK_FILE.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        if pid:
            os.kill(pid, 0)  # raises OSError if process is dead
            return True
    except (json.JSONDecodeError, ValueError, OSError):
        # Stale or corrupt lock — clean it up
        _LOCK_FILE.unlink(missing_ok=True)
    return False


def _active_scripts() -> dict:
    """Return the SCRIPTS dict with slot '1' swapped if indexing is running."""
    if _is_indexer_running():
        return {**SCRIPTS, "1": _GRAPH_WATCHDOG}
    return SCRIPTS


def _count_graph_nodes() -> int | None:
    """Count nodes in the LightRAG graphml file without full XML parse."""
    from config import WORKING_DIR
    graphml = WORKING_DIR / "graph_chunk_entity_relation.graphml"
    try:
        count = 0
        with open(graphml, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "<node " in line:
                    count += 1
        return count if count > 0 else None
    except OSError:
        return None


# ──────────────────────────────────────────────
# STATUS HELPERS
# ──────────────────────────────────────────────
def get_gpu_display() -> str:
    stats = get_gpu_stats()
    if stats["used_mb"] is not None:
        return f"[bold cyan]{stats['display']}[/]"
    return "[red]GPU Offline[/]"


def get_vault_stats() -> str:
    try:
        archive_count = len(glob.glob(str(ARCHIVE_PATH / "**" / "*.md"), recursive=True))
        reports_path = VAULT_PATH / "1. Projects" / "Research_Reports"
        report_count = len(glob.glob(str(reports_path / "*.md"), recursive=True)) if reports_path.exists() else 0
        return f"[bold white]{archive_count}[/] Archive | [bold white]{report_count}[/] Reports"
    except OSError:
        return "[red]N/A[/]"


# ──────────────────────────────────────────────
# LAYOUT COMPONENTS
# ──────────────────────────────────────────────
def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="side", size=32),
        Layout(name="body", ratio=1),
    )
    return layout


class Header:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            "[bold magenta]🧠 BRAIN COMMAND CENTER[/]",
            datetime.now().strftime("%H:%M:%S"),
        )
        return Panel(grid, style="white on blue")


class Sidebar:
    def __rich__(self) -> Panel:
        table = Table.grid(padding=1)
        active = _active_scripts()
        indexing = _is_indexer_running()
        for key, (name, script) in active.items():
            available = _script_exists(script)
            # Highlight slot 1 when it has been swapped
            if key == "1" and indexing:
                table.add_row(f"[bold yellow]{key}[/] [bold yellow]{name}[/]")
            elif available:
                table.add_row(f"[bold white]{key}[/] {name}")
            else:
                table.add_row(f"[dim]{key} {name} (missing)[/]")
        table.add_row("")
        table.add_row("[bold red]X[/] Shutdown")
        return Panel(table, title="[bold]MENU[/]", border_style="green")


# ──────────────────────────────────────────────
# GRAPH WATCHDOG LAUNCHER
# ──────────────────────────────────────────────
def _launch_graph_watchdog(node_count: int | None):
    """Sub-menu: pick renderer + top_n, then launch watchdog."""
    console.clear()

    default_renderer = "2" if (node_count or 0) > 1000 else "1"
    count_label = f"{node_count:,} nodes detected" if node_count else "graph size unknown"

    console.print(Panel(
        f"[bold]Graph Watchdog[/] — {count_label}\n\n"
        " [bold white]1[/]  PyVis   — up to ~1,000 nodes, CPU physics\n"
        " [bold white]2[/]  Sigma   — up to ~6,000 nodes, WebGL fast",
        border_style="cyan",
    ))

    renderer = Prompt.ask(
        "[bold yellow]Renderer[/]",
        choices=["1", "2"],
        default=default_renderer,
    )

    if renderer == "1":
        script = "visualize_graph.py"
        default_top = min(500, node_count) if node_count else 500
    else:
        script = "visualize_sigma.py"
        default_top = min(3000, node_count) if node_count else 3000

    top_n_str = Prompt.ask(
        "[bold yellow]How many nodes to render[/]",
        default=str(default_top),
    )
    try:
        top_n = max(1, int(top_n_str))
    except ValueError:
        top_n = default_top

    name = "Graph Watchdog (PyVis)" if renderer == "1" else "Graph Watchdog (Sigma)"
    run_task(name, script, extra_args=["--watch", "--top", str(top_n)])


# ──────────────────────────────────────────────
# EMBED PRE-WARM
# ──────────────────────────────────────────────
def _prewarm_embed() -> threading.Thread:
    """Fire a background embed ping so Ollama loads the model before the indexer needs it."""
    def _ping():
        try:
            payload = json.dumps({"model": EMBED_MODEL, "input": ["ping"], "keep_alive": "30m"}).encode()
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=300)
        except Exception:
            pass  # Indexer's own probe will surface any real error

    t = threading.Thread(target=_ping, daemon=True)
    t.start()
    return t


# ──────────────────────────────────────────────
# TASK RUNNER
# ──────────────────────────────────────────────
def run_task(name: str, script: str, extra_args: list[str] | None = None):
    script_path = os.path.join(SCRIPT_DIR, script)

    if not os.path.exists(script_path):
        console.print(
            Panel(
                f"[bold red]❌ Script not found:[/] {script}\n[dim]Expected at: {script_path}[/]",
                border_style="red",
            )
        )
        console.input("\n[bold white]Press Enter to return...[/]")
        return

    console.clear()
    console.print(
        Panel(
            f"🚀 [bold yellow]STARTING {name.upper()}...[/]",
            border_style="yellow",
        )
    )

    cmd = [PYTHON, script_path]
    if extra_args:
        cmd.extend(extra_args)

    if script == "index_archive.py":
        _prewarm_embed()

    proc = None
    try:
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        console.print(f"\n[bold green]✅ {name} finished successfully.[/]")
    except KeyboardInterrupt:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        console.print("\n[bold yellow]⚠️ Interrupted — subprocess stopped.[/]")
    except subprocess.CalledProcessError as e:
        console.print(
            Panel(
                f"[bold red]❌ ERROR IN {name}:[/]\nExit code {e.returncode}.",
                border_style="red",
            )
        )
    except FileNotFoundError:
        console.print(
            Panel(
                f"[bold red]❌ Python interpreter not found:[/] {sys.executable}",
                border_style="red",
            )
        )
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]❌ CRITICAL FAILURE:[/]\n{str(e)}",
                border_style="red",
            )
        )

    console.input("\n[bold white]Press Enter to return...[/]")


# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────
try:
    import msvcrt
    def _read_key(timeout: float = 0.25) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    continue
                return ch
            time.sleep(0.02)
        return None
except ImportError:
    import select
    def _read_key(timeout: float = 0.25) -> str | None:
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if r:
            return sys.stdin.read(1)
        return None


def _build_layout_content(layout: Layout) -> int | None:
    layout["header"].update(Header())
    layout["side"].update(Sidebar())
    node_count = _count_graph_nodes()
    graph_label = f"[bold white]{node_count:,}[/] nodes" if node_count else "[dim]no graph yet[/]"
    status_table = Table(show_header=False, box=box.SIMPLE, expand=True)
    status_table.add_row("📍 GPU", get_gpu_display())
    status_table.add_row("📍 VAULT", get_vault_stats())
    status_table.add_row("📍 GRAPH", graph_label)
    status_table.add_row("📍 MODE", "HITL Protected (Safeguarded)")
    status_table.add_row("📍 VAULT PATH", f"[dim]{VAULT_PATH}[/]")
    layout["body"].update(Panel(status_table, title="[bold blue]VITALS[/]", border_style="blue"))
    layout["footer"].update(Panel(
        "[bold yellow]NEW:[/] Option 6 for neural map | [dim]auto-refreshes every 3s[/]",
        border_style="white",
    ))
    return node_count


def main():
    validate_paths()
    layout = make_layout()
    node_count: int | None = None
    last_rebuild = 0.0
    REBUILD_EVERY = 3.0

    with Live(layout, console=console, screen=True, refresh_per_second=4) as live:
        node_count = _build_layout_content(layout)
        live.update(layout, refresh=True)

        while True:
            now = time.monotonic()
            if now - last_rebuild >= REBUILD_EVERY:
                node_count = _build_layout_content(layout) or node_count
                last_rebuild = now

            key = _read_key(timeout=0.25)
            if key is None:
                continue

            key = key.upper()
            active = _active_scripts()
            if key not in active and key != "X":
                continue

            live.stop()
            try:
                if key == "X":
                    break
                elif key == "1" and _is_indexer_running():
                    _launch_graph_watchdog(node_count)
                elif key == "8":
                    _launch_graph_watchdog(node_count)
                else:
                    name, script = active[key]
                    run_task(name, script)
            finally:
                if key != "X":
                    live.start(refresh=True)
                    last_rebuild = 0.0


if __name__ == "__main__":
    main()
