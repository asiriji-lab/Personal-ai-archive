"""
ZeroCostBrain — Knowledge Graph Visualizer

Reads LightRAG's graphml file and renders an interactive HTML graph
that looks like Obsidian's graph view (dark, force-directed, zoomable).

Usage:
    python visualize_graph.py              # render once, open in browser
    python visualize_graph.py --watch      # re-render whenever graph updates
    python visualize_graph.py --top 100    # limit to top N nodes by degree
"""

import argparse
import http.server
import json
import math
import os
import socketserver
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from graph_hud import EDGE_COLOR, EDGE_HIGHLIGHT, build_css, build_html, build_js
from pyvis.network import Network

from config import WORKING_DIR

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
GRAPHML_PATH = WORKING_DIR / "graph_chunk_entity_relation.graphml"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "brain_graph.html"
GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"


# ──────────────────────────────────────────────
# GRAPHML PARSER
# ──────────────────────────────────────────────
def _parse_graphml(path: Path) -> tuple[list[dict], list[dict]]:
    """Parse graphml into node/edge dicts. Returns (nodes, edges)."""
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"g": GRAPHML_NS}

    # Discover key mappings: id → attr.name
    key_map = {}
    for key in root.findall("g:key", ns):
        key_map[key.attrib.get("id", "")] = key.attrib.get("attr.name", "")

    def _node_data(el) -> dict:
        d = {"id": el.attrib.get("id", "")}
        for data in el.findall("g:data", ns):
            attr = key_map.get(data.attrib.get("key", ""), "")
            if attr:
                d[attr] = data.text or ""
        return d

    def _edge_data(el) -> dict:
        d = {
            "source": el.attrib.get("source", ""),
            "target": el.attrib.get("target", ""),
        }
        for data in el.findall("g:data", ns):
            attr = key_map.get(data.attrib.get("key", ""), "")
            if attr:
                d[attr] = data.text or ""
        return d

    graph_el = root.find("g:graph", ns)
    if graph_el is None:
        return [], []

    nodes = [_node_data(n) for n in graph_el.findall("g:node", ns)]
    edges = [_edge_data(e) for e in graph_el.findall("g:edge", ns)]
    return nodes, edges


# ──────────────────────────────────────────────
# COLOR BY ENTITY TYPE
# ──────────────────────────────────────────────
_TYPE_COLORS = {
    "organization": "#818cf8",  # indigo-400
    "person": "#fbbf24",  # amber-400
    "concept": "#34d399",  # emerald-400
    "technology": "#60a5fa",  # blue-400
    "method": "#a78bfa",  # violet-400
    "dataset": "#fb923c",  # orange-400
    "model": "#22d3ee",  # cyan-400
    "paper": "#f472b6",  # pink-400
}


def _node_color(node: dict) -> str:
    t = (node.get("entity_type") or node.get("type") or "").lower()
    for key, color in _TYPE_COLORS.items():
        if key in t:
            return color
    return "#94a3b8"  # slate-400 default


# ──────────────────────────────────────────────
# DATA PREPARATION
# ──────────────────────────────────────────────
def _prepare_graph_data(top_n: int):
    if not GRAPHML_PATH.exists():
        return None

    nodes, edges = _parse_graphml(GRAPHML_PATH)
    if not nodes:
        return None

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    sorted_nodes = sorted(nodes, key=lambda n: degree[n["id"]], reverse=True)
    kept_ids = {n["id"] for n in sorted_nodes[:top_n]}
    filtered_nodes = [n for n in sorted_nodes if n["id"] in kept_ids]
    filtered_edges = [e for e in edges if e["source"] in kept_ids and e["target"] in kept_ids]
    return filtered_nodes, filtered_edges, degree


# ──────────────────────────────────────────────
# JSON GENERATION (DELTA DATA)
# ──────────────────────────────────────────────
def generate_json(top_n: int = 1000) -> bool:
    data = _prepare_graph_data(top_n)
    if not data:
        return False
    filtered_nodes, filtered_edges, degree = data

    vis_nodes = []
    for node in filtered_nodes:
        nid = node["id"]
        deg = degree[nid]
        # Logarithmic sizing feels more natural for 5k+ nodes
        size = max(10, min(50, 10 + (math.log(deg + 1) * 8)))
        color = _node_color(node)
        desc = node.get("description") or node.get("entity_type") or ""
        tooltip = f"<b>{nid}</b><br>{desc[:200]}" if desc else f"<b>{nid}</b>"

        # Smarter label suppression: hide labels for low-degree nodes if the graph is huge
        is_large_view = top_n > 500
        show_label = deg > 1 if is_large_view else True

        label = nid if show_label else ""
        font_size = max(12, min(20, 11 + deg)) if show_label else 0

        vis_nodes.append({
            "id": nid,
            "label": label,
            "title": tooltip,
            "size": size,
            "color": {"background": color, "border": color, "highlight": {"background": "#ffffff", "border": "#ffffff"}},
            "borderWidth": 2,
            "font": {"size": font_size, "color": "#e2e8f0", "strokeWidth": 2, "strokeColor": "#0d1117"},
            "_defaultColor": {"background": color, "border": color, "highlight": {"background": "#ffffff", "border": "#ffffff"}},
            "_defaultSize": size
        })

    vis_edges = []
    for edge in filtered_edges:
        desc = edge.get("description") or edge.get("relation") or ""
        tooltip = desc[:150] if desc else ""
        vis_edges.append({
            "id": f"{edge['source']}--{edge['target']}",
            "from": edge["source"],
            "to": edge["target"],
            "title": tooltip,
            "_defaultColor": {"color": EDGE_COLOR, "highlight": EDGE_HIGHLIGHT},
            "_defaultWidth": 1
        })

    output = {"nodes": vis_nodes, "edges": vis_edges}

    json_path = PROJECT_ROOT / "docs" / "graph_data.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = json_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(output, indent=2), encoding="utf-8")
    tmp.replace(json_path)
    return True


# ──────────────────────────────────────────────
# LOCAL SERVER
# ──────────────────────────────────────────────
def start_server(port=8000):
    docs_dir = PROJECT_ROOT / "docs"
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(docs_dir), **kwargs)

        def log_message(self, format, *args):
            pass # Suppress HTTP logs to keep console clean

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", port), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        print(f"Local server started at http://localhost:{port}/brain_graph.html")
        return httpd
    except Exception as e:
        print(f"Failed to start local server on port {port}: {e}")
        return None


# ──────────────────────────────────────────────
# RENDERER
# ──────────────────────────────────────────────
def render(top_n: int = 1000, open_browser: bool = True) -> bool:
    """
    Parse graphml and render to HTML.
    Returns True if graph had content, False if empty.
    """
    data = _prepare_graph_data(top_n)
    if not data:
        print(f"Graph file not found or empty: {GRAPHML_PATH}")
        print("Run `python index_archive.py` first to build the knowledge graph.")
        return False

    filtered_nodes, filtered_edges, degree = data

    # Performance tuning for large graphs
    node_count = len(filtered_nodes)
    is_large = node_count > 500

    # ── Build pyvis network ──
    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#0d1117",
        font_color="#e2e8f0",
        directed=False,
    )

    net.set_options(json.dumps({
      "physics": {
        "enabled": True,
        "solver": "barnesHut",
        "barnesHut": {
          "gravitationalConstant": -60000 if is_large else -2000,
          "centralGravity": 0.3,
          "springLength": 200 if is_large else 95,
          "springConstant": 0.001 if is_large else 0.04,
          "damping": 0.2,
          "avoidOverlap": 0.2 if is_large else 0
        },
        "stabilization": {
          "enabled": True,
          "iterations": 1000 if is_large else 200,
          "updateInterval": 50,
          "onlyDynamicEdges": False,
          "fit": True
        }
      },
      "edges": {
        "color": { "color": "#2d3a4a", "highlight": "#64748b" },
        "width": 1,
        "smooth": { "enabled": False }
      },
      "nodes": {
        "borderWidth": 0,
        "shadow": { "enabled": False }
      },
      "interaction": {
        "hover": True,
        "tooltipDelay": 100,
        "hideEdgesOnDrag": False,
        "hideEdgesOnZoom": False,
        "navigationButtons": False,
        "keyboard": True
      }
    }))

    for node in filtered_nodes:
        nid = node["id"]
        deg = degree[nid]
        size = max(10, min(50, 10 + (math.log(deg + 1) * 8)))
        color = _node_color(node)
        desc = node.get("description") or node.get("entity_type") or ""
        tooltip = f"<b>{nid}</b><br>{desc[:200]}" if desc else f"<b>{nid}</b>"

        show_label = deg > 1 if is_large else True
        label = nid if show_label else ""
        font_size = max(12, min(20, 11 + deg)) if show_label else 0

        net.add_node(
            nid,
            label=label,
            title=tooltip,
            size=size,
            color={"background": color, "border": color, "highlight": {"background": "#ffffff", "border": "#ffffff"}},
            borderWidth=2,
            font={"size": font_size, "color": "#e2e8f0", "strokeWidth": 2, "strokeColor": "#0d1117"},
        )

    for edge in filtered_edges:
        desc = edge.get("description") or edge.get("relation") or ""
        tooltip = desc[:150] if desc else ""
        net.add_edge(edge["source"], edge["target"], id=f"{edge['source']}--{edge['target']}", title=tooltip)

    # ── Write HTML ──
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(OUTPUT_PATH))

    # ── Inject custom HUD overlay ──
    html = OUTPUT_PATH.read_text(encoding="utf-8")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    hud_css = f"<style>{build_css()}</style>"
    hud_html = build_html(len(filtered_nodes), len(filtered_edges), stamp)
    hud_js = build_js()

    html = html.replace("</style>", f"</style>{hud_css}", 1)
    html = html.replace("<body>", f"<body>{hud_html}", 1)
    html = html.replace("</body>", hud_js + "</body>", 1)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Graph rendered: {len(filtered_nodes)} nodes, {len(filtered_edges)} edges -> {OUTPUT_PATH}")

    if open_browser:
        webbrowser.open(OUTPUT_PATH.as_uri())

    return True


# ──────────────────────────────────────────────
# WATCH MODE
# ──────────────────────────────────────────────
def watch(top_n: int = 1000, poll_seconds: int = 1) -> None:
    """Poll graphml for changes and re-render automatically."""
    print(f"Watching {GRAPHML_PATH} for changes (every {poll_seconds}s)...")

    server = start_server(port=8000)

    # Initial generation — only if graph file already exists
    if GRAPHML_PATH.exists():
        render(top_n=top_n, open_browser=False)
        generate_json(top_n=top_n)
    else:
        print(f"  Graph file not found yet: {GRAPHML_PATH}")
        print("  Waiting for indexer to populate it...")

    if server:
        print("Open http://localhost:8000/brain_graph.html in your browser.")
        webbrowser.open("http://localhost:8000/brain_graph.html")
    else:
        print(f"Open {OUTPUT_PATH.as_uri()} in your browser.")
        webbrowser.open(OUTPUT_PATH.as_uri())

    print("Ctrl+C to stop.\n")

    last_mtime = 0.0

    while True:
        try:
            try:
                mtime = GRAPHML_PATH.stat().st_mtime if GRAPHML_PATH.exists() else 0.0
            except OSError:
                mtime = 0.0

            if mtime != last_mtime:
                last_mtime = mtime
                print(f"[{time.strftime('%H:%M:%S')}] Graph changed — generating JSON diff...")
                try:
                    generate_json(top_n=top_n)
                except Exception as exc:
                    print(f"  JSON generate skipped (file mid-write?): {exc}")

        except Exception as exc:
            print(f"[{time.strftime('%H:%M:%S')}] Watcher error (continuing): {exc}")

        time.sleep(poll_seconds)


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize the LightRAG knowledge graph.")
    parser.add_argument("--watch", action="store_true", help="Re-render whenever graph updates.")
    def _positive_int(val: str) -> int:
        n = int(val)
        if n < 1:
            raise argparse.ArgumentTypeError(f"Must be a positive integer, got {val!r}")
        return n

    parser.add_argument("--top", type=_positive_int, default=1000, help="Max nodes to show (by degree).")
    parser.add_argument("--poll", type=_positive_int, default=1, help="Watch poll interval in seconds.")
    args = parser.parse_args()

    if args.watch:
        watch(top_n=args.top, poll_seconds=args.poll)
    else:
        render(top_n=args.top)
