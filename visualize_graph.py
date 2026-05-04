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
import os
import time
import webbrowser
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

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
# RENDERER
# ──────────────────────────────────────────────
def render(top_n: int = 200, open_browser: bool = True) -> bool:
    """
    Parse graphml and render to HTML.
    Returns True if graph had content, False if empty.
    """
    if not GRAPHML_PATH.exists():
        print(f"Graph file not found: {GRAPHML_PATH}")
        print("Run `python index_archive.py` first to build the knowledge graph.")
        return False

    nodes, edges = _parse_graphml(GRAPHML_PATH)

    if not nodes:
        print("Graph is empty — no entities indexed yet.")
        print("Run `python index_archive.py` to populate the graph.")
        return False

    # Compute degree for each node to size and rank them
    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    # Keep top_n nodes by degree
    sorted_nodes = sorted(nodes, key=lambda n: degree[n["id"]], reverse=True)
    kept_ids = {n["id"] for n in sorted_nodes[:top_n]}
    filtered_nodes = [n for n in sorted_nodes if n["id"] in kept_ids]
    filtered_edges = [e for e in edges if e["source"] in kept_ids and e["target"] in kept_ids]

    # ── Build pyvis network ──
    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#0d1117",
        font_color="#e2e8f0",
        directed=False,
    )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.005,
          "springLength": 120,
          "springConstant": 0.08,
          "damping": 0.6
        },
        "solver": "forceAtlas2Based",
        "stabilization": { "iterations": 150 }
      },
      "edges": {
        "color": { "color": "#1e293b", "highlight": "#475569" },
        "width": 1,
        "smooth": { "type": "continuous" }
      },
      "nodes": {
        "borderWidth": 0,
        "shadow": { "enabled": true, "color": "rgba(0,0,0,0.5)", "size": 8 }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true
      }
    }
    """)

    for node in filtered_nodes:
        nid = node["id"]
        deg = degree[nid]
        size = max(8, min(40, 8 + deg * 2))
        color = _node_color(node)
        desc = node.get("description") or node.get("entity_type") or ""
        tooltip = f"<b>{nid}</b><br>{desc[:200]}" if desc else f"<b>{nid}</b>"

        # Truncate with ellipsis; hide label entirely for leaf nodes to reduce clutter
        max_chars = 22
        if len(nid) > max_chars:
            label = nid[: max_chars - 1] + "…"
        else:
            label = nid
        font_size = max(11, min(16, 10 + deg))
        # Suppress label for very low-degree nodes — tooltip still works on hover
        if deg == 0:
            label = ""
            font_size = 0

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
        net.add_edge(edge["source"], edge["target"], title=tooltip)

    # ── Write HTML ──
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(OUTPUT_PATH))

    # Inject title + timestamp into the HTML
    html = OUTPUT_PATH.read_text(encoding="utf-8")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    badge = (
        f'<div style="position:fixed;top:12px;left:12px;z-index:999;'
        f"background:#111827;border:1px solid #1e293b;border-radius:6px;"
        f'padding:8px 14px;font-family:monospace;font-size:12px;color:#64748b;">'
        f"🧠 ZeroCostBrain Graph &nbsp;·&nbsp; "
        f"{len(filtered_nodes)} nodes &nbsp;·&nbsp; "
        f"{len(filtered_edges)} edges &nbsp;·&nbsp; "
        f"Updated {stamp}</div>"
    )
    html = html.replace("<body>", f"<body>{badge}", 1)

    # Inject double-click focus: dim unconnected nodes/edges on node double-click,
    # double-click background to reset.
    hover_js = """
<script type="text/javascript">
(function waitForNetwork() {
  if (typeof network === "undefined" || typeof nodes === "undefined") {
    setTimeout(waitForNetwork, 100);
    return;
  }
  var _edgeDefaultColor = "#1e293b";
  var _focused = false;

  function focusNode(nodeId) {
    var connected = new Set(network.getConnectedNodes(nodeId));
    var connEdges = new Set(network.getConnectedEdges(nodeId));
    connected.add(nodeId);
    nodes.update(nodes.get().map(function(n) {
      return { id: n.id, opacity: connected.has(n.id) ? 1.0 : 0.06 };
    }));
    edges.update(edges.get().map(function(e) {
      return connEdges.has(e.id)
        ? { id: e.id, color: { color: "#94a3b8" }, width: 2.5 }
        : { id: e.id, color: { color: _edgeDefaultColor, opacity: 0.04 }, width: 0.5 };
    }));
    _focused = true;
  }

  function resetAll() {
    nodes.update(nodes.get().map(function(n) { return { id: n.id, opacity: 1.0 }; }));
    edges.update(edges.get().map(function(e) { return { id: e.id, color: { color: _edgeDefaultColor }, width: 1 }; }));
    _focused = false;
  }

  network.on("doubleClick", function(params) {
    if (params.nodes && params.nodes.length > 0) {
      focusNode(params.nodes[0]);
    } else {
      resetAll();
    }
  });
})();
</script>
"""
    html = html.replace("</body>", hover_js + "</body>", 1)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Graph rendered: {len(filtered_nodes)} nodes, {len(filtered_edges)} edges → {OUTPUT_PATH}")

    if open_browser:
        webbrowser.open(OUTPUT_PATH.as_uri())

    return True


# ──────────────────────────────────────────────
# WATCH MODE
# ──────────────────────────────────────────────
def watch(top_n: int = 200, poll_seconds: int = 10) -> None:
    """Poll graphml for changes and re-render automatically."""
    print(f"Watching {GRAPHML_PATH} for changes (every {poll_seconds}s)...")
    print("Open docs/brain_graph.html in your browser and refresh after each update.")
    print("Ctrl+C to stop.\n")

    last_mtime = 0.0
    first_run = True

    while True:
        try:
            try:
                mtime = GRAPHML_PATH.stat().st_mtime if GRAPHML_PATH.exists() else 0.0
            except OSError:
                mtime = 0.0

            if mtime != last_mtime:
                last_mtime = mtime
                print(f"[{time.strftime('%H:%M:%S')}] Graph changed — re-rendering...")
                try:
                    render(top_n=top_n, open_browser=first_run)
                    first_run = False
                except Exception as exc:
                    print(f"  Render skipped (file mid-write?): {exc}")

        except Exception as exc:
            print(f"[{time.strftime('%H:%M:%S')}] Watcher error (continuing): {exc}")

        time.sleep(poll_seconds)


# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize the LightRAG knowledge graph.")
    parser.add_argument("--watch", action="store_true", help="Re-render whenever graph updates.")
    parser.add_argument("--top", type=int, default=200, help="Max nodes to show (by degree).")
    parser.add_argument("--poll", type=int, default=10, help="Watch poll interval in seconds.")
    args = parser.parse_args()

    if args.watch:
        watch(top_n=args.top, poll_seconds=args.poll)
    else:
        render(top_n=args.top)
