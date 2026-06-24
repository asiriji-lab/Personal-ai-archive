import argparse
import json
import math
import sys
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# CONFIG — resolve paths from config to avoid working-directory dependency
from config import WORKING_DIR

# Import Sigma HUD
from sigma_hud import build_sigma_css, build_sigma_html, build_sigma_js

_PROJECT_ROOT = Path(__file__).parent
GRAPHML_PATH = WORKING_DIR / "graph_chunk_entity_relation.graphml"
OUTPUT_PATH = _PROJECT_ROOT / "docs" / "brain_graph_sigma.html"
DATA_JSON_PATH = _PROJECT_ROOT / "docs" / "graph_data.json"

def _parse_graphml(file_path):
    if not file_path.exists():
        return [], []

    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    try:
        tree = ET.parse(file_path)
    except ET.ParseError:
        return [], []

    root = tree.getroot()
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

_TYPE_COLORS = {
    "organization": "#818cf8",
    "person": "#fbbf24",
    "concept": "#34d399",
    "technology": "#60a5fa",
    "method": "#a78bfa",
    "dataset": "#fb923c",
    "model": "#22d3ee",
    "paper": "#f472b6",
}

def _node_color(node: dict) -> str:
    t = (node.get("entity_type") or node.get("type") or "").lower()
    for key, color in _TYPE_COLORS.items():
        if key in t:
            return color
    return "#cbd5e1"

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

def generate_json(top_n: int = 6000) -> bool:
    data = _prepare_graph_data(top_n)
    if not data:
        return False
    filtered_nodes, filtered_edges, degree = data

    vis_nodes = []
    for node in filtered_nodes:
        nid = node["id"]
        deg = degree[nid]
        # Size by degree — let Sigma's labelDensity control label visibility
        size = round(max(2.0, min(20.0, 2.0 + math.sqrt(deg) * 1.4)), 2)
        color = _node_color(node)
        desc = node.get("description") or node.get("entity_type") or ""
        tooltip = f"<b>{nid}</b><br>{desc[:400]}" if desc else f"<b>{nid}</b>"

        vis_nodes.append({
            "id": nid,
            "label": nid,
            "title": tooltip,
            "size": size,
            "color": {"background": color}
        })

    vis_edges = []
    seen_edges = set()
    for edge in filtered_edges:
        edge_key = tuple(sorted((edge["source"], edge["target"])))
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        vis_edges.append({
            "id": f"{edge['source']}--{edge['target']}",
            "source": edge["source"],
            "target": edge["target"]
        })

    DATA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_JSON_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"nodes": vis_nodes, "edges": vis_edges}, f)
    tmp.replace(DATA_JSON_PATH)
    return True

def start_server(port=8000):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args): pass

    for p in range(port, port + 10):
        try:
            server = HTTPServer(("localhost", p), QuietHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            return server, p
        except OSError:
            continue
    return None, None

def render_sigma(top_n: int = 6000, open_browser: bool = True):
    data = _prepare_graph_data(top_n)
    if not data:
        return False
    filtered_nodes, filtered_edges, _ = data

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ZeroCostBrain - Sigma v2</title>
    <style>{build_sigma_css()}</style>
</head>
<body>
    {build_sigma_html(len(filtered_nodes), len(filtered_edges), stamp)}
    {build_sigma_js()}
</body>
</html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    generate_json(top_n)

    server, port = start_server(port=8000)
    if not server:
        print("Error: Could not start HTTP server.")
        return False

    url = f"http://localhost:{port}/docs/brain_graph_sigma.html"
    print(f"Server started at {url}")

    if open_browser:
        webbrowser.open(url)

    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server...")
        server.shutdown()
        return True

def watch_sigma(top_n: int = 6000, poll_seconds: int = 1):
    print(f"Watching {GRAPHML_PATH} for changes...")
    server, port = start_server(port=8000)
    if not server:
        print("Error: Could not start HTTP server.")
        return

    # Generate initial HTML
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    nodes, edges, _ = _prepare_graph_data(top_n)
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ZeroCostBrain - Sigma v2</title>
    <style>{build_sigma_css()}</style>
</head>
<body>
    {build_sigma_html(len(nodes), len(edges), stamp)}
    {build_sigma_js()}
</body>
</html>"""
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    generate_json(top_n)

    url = f"http://localhost:{port}/docs/brain_graph_sigma.html"
    print(f"Open {url} in your browser.")
    webbrowser.open(url)

    last_mtime = 0.0
    try:
        while True:
            try:
                mtime = GRAPHML_PATH.stat().st_mtime if GRAPHML_PATH.exists() else 0.0
                if mtime != last_mtime:
                    last_mtime = mtime
                    generate_json(top_n=top_n)
            except Exception as e:
                print(f"Watch error: {e}")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("Stopping watch and server...")
        server.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--top", type=int, default=6000)
    args = parser.parse_args()

    if args.watch:
        watch_sigma(top_n=args.top)
    else:
        render_sigma(top_n=args.top)
