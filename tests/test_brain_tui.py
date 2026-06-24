"""Unit tests for brain_tui helper functions.

Headless: no Rich rendering to stdout, no GPU, no real psutil walk.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import brain_tui


# ──────────────────────────────────────────────
# _is_indexer_running  (PID-based lock file)
# ──────────────────────────────────────────────
class TestIsIndexerRunning:
    """_is_indexer_running() reads a JSON lock file and validates the PID
    via os.kill(pid, 0).  If the file is missing, corrupt, or the PID is
    dead, it returns False (and cleans up the stale lock).
    """

    def _write_lock(self, path: Path, pid: int) -> None:
        path.write_text(
            json.dumps({"pid": pid, "started": "2026-05-17T00:00:00+00:00", "heartbeat": ""}),
            encoding="utf-8",
        )

    def test_returns_false_when_no_lock_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(brain_tui, "_LOCK_FILE", tmp_path / "nope.lock")
        assert brain_tui._is_indexer_running() is False

    def test_returns_true_when_live_pid_in_lock(self, tmp_path, monkeypatch):
        lock = tmp_path / ".indexer.lock"
        self._write_lock(lock, 9999)
        monkeypatch.setattr(brain_tui, "_LOCK_FILE", lock)
        with patch.object(brain_tui.os, "kill", return_value=None):  # process alive
            assert brain_tui._is_indexer_running() is True

    def test_returns_false_and_removes_lock_when_pid_dead(self, tmp_path, monkeypatch):
        lock = tmp_path / ".indexer.lock"
        self._write_lock(lock, 9999)
        monkeypatch.setattr(brain_tui, "_LOCK_FILE", lock)
        with patch.object(brain_tui.os, "kill", side_effect=OSError("no such process")):
            assert brain_tui._is_indexer_running() is False
        assert not lock.exists(), "stale lock should have been deleted"

    def test_returns_false_and_removes_lock_on_corrupt_json(self, tmp_path, monkeypatch):
        lock = tmp_path / ".indexer.lock"
        lock.write_text("NOT JSON", encoding="utf-8")
        monkeypatch.setattr(brain_tui, "_LOCK_FILE", lock)
        assert brain_tui._is_indexer_running() is False
        assert not lock.exists(), "corrupt lock should have been deleted"

    def test_returns_false_when_pid_is_zero(self, tmp_path, monkeypatch):
        lock = tmp_path / ".indexer.lock"
        lock.write_text(json.dumps({"pid": 0}), encoding="utf-8")
        monkeypatch.setattr(brain_tui, "_LOCK_FILE", lock)
        assert brain_tui._is_indexer_running() is False


# ──────────────────────────────────────────────
# _active_scripts
# ──────────────────────────────────────────────
class TestActiveScripts:
    def test_returns_default_scripts_when_idle(self, monkeypatch):
        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: False)
        result = brain_tui._active_scripts()
        assert result["1"] == ("Indexer", "index_archive.py")
        assert result == brain_tui.SCRIPTS

    def test_swaps_slot_1_when_indexer_running(self, monkeypatch):
        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: True)
        result = brain_tui._active_scripts()
        assert result["1"] == brain_tui._GRAPH_WATCHDOG
        assert "indexing detected" in result["1"][0]
        assert result["8"] == brain_tui.SCRIPTS["8"]
        assert set(result.keys()) == set(brain_tui.SCRIPTS.keys())

    def test_does_not_mutate_global_scripts(self, monkeypatch):
        original = dict(brain_tui.SCRIPTS)
        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: True)
        brain_tui._active_scripts()
        assert brain_tui.SCRIPTS == original


# ──────────────────────────────────────────────
# _count_graph_nodes
# ──────────────────────────────────────────────
class TestCountGraphNodes:
    def _patch_working_dir(self, monkeypatch, tmp_path):
        import config
        monkeypatch.setattr(config, "WORKING_DIR", tmp_path)
        return tmp_path

    def test_counts_node_tags(self, tmp_path, monkeypatch):
        wd = self._patch_working_dir(monkeypatch, tmp_path)
        (wd / "graph_chunk_entity_relation.graphml").write_text(
            '<graph>\n'
            '  <node id="a"/>\n'
            '  <node id="b" attr="x"/>\n'
            '  <edge source="a" target="b"/>\n'
            '  <node id="c"/>\n'
            '</graph>\n',
            encoding="utf-8",
        )
        assert brain_tui._count_graph_nodes() == 3

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        self._patch_working_dir(monkeypatch, tmp_path)
        assert brain_tui._count_graph_nodes() is None

    def test_returns_none_when_zero_nodes(self, tmp_path, monkeypatch):
        wd = self._patch_working_dir(monkeypatch, tmp_path)
        (wd / "graph_chunk_entity_relation.graphml").write_text(
            '<graph><edge source="a" target="b"/></graph>', encoding="utf-8"
        )
        assert brain_tui._count_graph_nodes() is None

    def test_does_not_match_nodes_tag(self, tmp_path, monkeypatch):
        wd = self._patch_working_dir(monkeypatch, tmp_path)
        (wd / "graph_chunk_entity_relation.graphml").write_text(
            '<nodes count="999">\n<node id="only-one"/>\n</nodes>',
            encoding="utf-8",
        )
        assert brain_tui._count_graph_nodes() == 1


# ──────────────────────────────────────────────
# _build_layout_content
# ──────────────────────────────────────────────
class TestBuildLayoutContent:
    def test_populates_layout_without_crashing(self, monkeypatch):
        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: False)
        monkeypatch.setattr(brain_tui, "_count_graph_nodes", lambda: 1234)
        monkeypatch.setattr(brain_tui, "get_gpu_display", lambda: "[cyan]MOCK GPU[/]")
        monkeypatch.setattr(brain_tui, "get_vault_stats", lambda: "[white]42 Archive[/]")

        layout = brain_tui.make_layout()
        result = brain_tui._build_layout_content(layout)
        assert result == 1234

        for region in ("header", "side", "body", "footer"):
            assert layout[region].renderable is not None

    def test_handles_missing_graph(self, monkeypatch):
        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: False)
        monkeypatch.setattr(brain_tui, "_count_graph_nodes", lambda: None)
        monkeypatch.setattr(brain_tui, "get_gpu_display", lambda: "x")
        monkeypatch.setattr(brain_tui, "get_vault_stats", lambda: "x")

        layout = brain_tui.make_layout()
        assert brain_tui._build_layout_content(layout) is None

    def test_slot1_swap_visible_in_render(self, monkeypatch):
        """Smoke-test: layout renders Graph Watchdog text when indexer running."""
        import io

        from rich.console import Console

        monkeypatch.setattr(brain_tui, "_is_indexer_running", lambda: True)
        monkeypatch.setattr(brain_tui, "_count_graph_nodes", lambda: 7)
        monkeypatch.setattr(brain_tui, "get_gpu_display", lambda: "gpu")
        monkeypatch.setattr(brain_tui, "get_vault_stats", lambda: "vault")

        layout = brain_tui.make_layout()
        brain_tui._build_layout_content(layout)

        buf = io.StringIO()
        rec = Console(record=True, width=120, file=buf)
        rec.print(layout)
        out = rec.export_text()
        flat = out.replace("\n", " ")
        assert "BRAIN COMMAND CENTER" in flat
        assert "indexing" in flat and "detected" in flat
