"""
🧠 ZeroCostBrain — Brain Command Center (The Cockpit)

A terminal UI dashboard for monitoring GPU, vault statistics,
and launching brain operations.
"""

import glob
import os
import subprocess
import sys
from datetime import datetime

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from config import ARCHIVE_PATH, VAULT_PATH, validate_paths
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
_GRAPH_WATCHDOG = ("Graph Watchdog [indexing detected]", "visualize_graph.py")


def _script_exists(filename: str) -> bool:
    """Check if a script file exists in the project directory."""
    return os.path.exists(os.path.join(SCRIPT_DIR, filename))


def _is_indexer_running() -> bool:
    """Return True if index_archive.py is currently running as a process."""
    try:
        import psutil
        for proc in psutil.process_iter(["cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if any("index_archive" in str(arg) for arg in cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        pass
    return False


def _active_scripts() -> dict:
    """Return the SCRIPTS dict with slot '1' swapped if indexing is running."""
    if _is_indexer_running():
        return {**SCRIPTS, "1": _GRAPH_WATCHDOG}
    return SCRIPTS


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
        archive_count = len(glob.glob(
            str(ARCHIVE_PATH / "**" / "*.md"), recursive=True
        ))
        reports_path = VAULT_PATH / "1. Projects" / "Research_Reports"
        report_count = len(glob.glob(
            str(reports_path / "*.md"), recursive=True
        )) if reports_path.exists() else 0
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
# TASK RUNNER
# ──────────────────────────────────────────────
def run_task(name: str, script: str, extra_args: list[str] | None = None):
    script_path = os.path.join(SCRIPT_DIR, script)

    if not os.path.exists(script_path):
        console.print(Panel(
            f"[bold red]❌ Script not found:[/] {script}\n"
            f"[dim]Expected at: {script_path}[/]",
            border_style="red",
        ))
        console.input("\n[bold white]Press Enter to return...[/]")
        return

    console.clear()
    console.print(Panel(
        f"🚀 [bold yellow]STARTING {name.upper()}...[/]",
        border_style="yellow",
    ))

    cmd = [PYTHON, script_path]
    if extra_args:
        cmd.extend(extra_args)

    try:
        subprocess.run(cmd, check=True)
        console.print(f"\n[bold green]✅ {name} finished successfully.[/]")
    except subprocess.CalledProcessError as e:
        console.print(Panel(
            f"[bold red]❌ ERROR IN {name}:[/]\nExit code {e.returncode}.",
            border_style="red",
        ))
    except FileNotFoundError:
        console.print(Panel(
            f"[bold red]❌ Python interpreter not found:[/] {sys.executable}",
            border_style="red",
        ))
    except Exception as e:
        console.print(Panel(
            f"[bold red]❌ CRITICAL FAILURE:[/]\n{str(e)}",
            border_style="red",
        ))

    console.input("\n[bold white]Press Enter to return...[/]")


# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────
def main():
    validate_paths()
    layout = make_layout()

    while True:
        layout["header"].update(Header())
        layout["side"].update(Sidebar())

        status_table = Table(show_header=False, box=box.SIMPLE, expand=True)
        status_table.add_row("📍 GPU", get_gpu_display())
        status_table.add_row("📍 VAULT", get_vault_stats())
        status_table.add_row("📍 MODE", "HITL Protected (Safeguarded)")
        status_table.add_row("📍 VAULT PATH", f"[dim]{VAULT_PATH}[/]")

        layout["body"].update(Panel(
            status_table,
            title="[bold blue]VITALS[/]",
            border_style="blue",
        ))
        layout["footer"].update(Panel(
            "[bold yellow]NEW:[/] Option 6 for neural map | Config via [bold].env[/] file",
            border_style="white",
        ))

        console.clear()
        console.print(layout)

        active = _active_scripts()
        valid_choices = list(active.keys()) + ["X"]
        choice = Prompt.ask(
            "\n[bold yellow]Choice[/]",
            choices=valid_choices,
            default="X",
        ).upper()

        if choice == "X":
            break
        elif choice == "2":
            run_task("Resource Indexer", "embed.py")
        elif choice == "1" and _is_indexer_running():
            # Indexing is live — launch graph watchdog instead
            run_task("Graph Watchdog", "visualize_graph.py", extra_args=["--watch"])
        elif choice == "8":
            run_task("Graph Watchdog", "visualize_graph.py", extra_args=["--watch"])
        elif choice in active:
            name, script = active[choice]
            run_task(name, script)


if __name__ == "__main__":
    main()
