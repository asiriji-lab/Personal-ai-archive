"""
🧠 ZeroCostBrain — Graph Pruning Utility

This script loads the LightRAG GraphML file and prunes noisy or stale entities.
Reducing the graph size directly improves Tier 2 (LightRAG) query latency.

Pruning strategies:
- orphans: Remove nodes with degree 0
- dates: Remove degree 1 nodes that are just date strings
- symbols: Remove degree 1 nodes that are purely non-alphanumeric

Usage:
    python scripts/prune_graph.py --dry-run
    python scripts/prune_graph.py --apply
"""

import argparse
import re
import sys
from pathlib import Path

# Ensure sys path includes the root so we can import config
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    import networkx as nx
except ImportError:
    print("Error: networkx is required. Install it with `pip install networkx`.")
    sys.exit(1)

from config import WORKING_DIR, validate_paths

GRAPH_PATH = WORKING_DIR / "graph_chunk_entity_relation.graphml"

# Regex for common date patterns (YYYY-MM-DD, Month YYYY, etc.)
DATE_PATTERN = re.compile(r"^(?:19|20)\d{2}-\d{2}-\d{2}$|^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$")
SYMBOL_PATTERN = re.compile(r"^[^a-zA-Z0-9]+$")


def load_graph() -> nx.Graph:
    if not GRAPH_PATH.exists():
        print(f"Graph file not found: {GRAPH_PATH}")
        sys.exit(1)
    print(f"Loading graph from {GRAPH_PATH}...")
    return nx.read_graphml(str(GRAPH_PATH))


def save_graph(G: nx.Graph) -> None:
    print(f"Saving pruned graph to {GRAPH_PATH}...")
    # Create backup
    backup_path = GRAPH_PATH.with_suffix(".graphml.bak")
    GRAPH_PATH.rename(backup_path)
    nx.write_graphml(G, str(GRAPH_PATH))
    print(f"Original graph backed up to {backup_path}")


def prune_graph(G: nx.Graph, dry_run: bool = True):
    initial_nodes = G.number_of_nodes()
    initial_edges = G.number_of_edges()

    nodes_to_remove = set()

    orphans = 0
    date_nodes = 0
    symbol_nodes = 0

    for node, degree in G.degree():
        # 1. Orphans (Degree 0)
        if degree == 0:
            nodes_to_remove.add(node)
            orphans += 1
            continue

        # 2. Low-degree noise (Degree 1)
        if degree == 1:
            # The 'id' attribute in graphml is the node name in NetworkX
            node_name = str(node).strip()

            # Check if it's just a date
            if DATE_PATTERN.match(node_name):
                nodes_to_remove.add(node)
                date_nodes += 1
                continue

            # Check if it's just symbols
            if SYMBOL_PATTERN.match(node_name):
                nodes_to_remove.add(node)
                symbol_nodes += 1
                continue

    if dry_run:
        print("=== DRY RUN MODE ===")
    else:
        print("=== APPLY MODE ===")

    print(f"Initial Graph: {initial_nodes} nodes, {initial_edges} edges")
    print("\nIdentified for pruning:")
    print(f"  - Orphans (degree 0): {orphans}")
    print(f"  - Date strings (degree 1): {date_nodes}")
    print(f"  - Symbols (degree 1): {symbol_nodes}")
    print(f"  TOTAL TO REMOVE: {len(nodes_to_remove)}")

    if not dry_run and nodes_to_remove:
        G.remove_nodes_from(nodes_to_remove)
        print(f"\nPruned Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        save_graph(G)
        print("✅ Graph successfully pruned.")
    elif dry_run:
        print("\nRun with --apply to perform the actual pruning.")


def main():
    parser = argparse.ArgumentParser(description="Prune noisy entities from LightRAG GraphML.")
    parser.add_argument("--apply", action="store_true", help="Apply changes and overwrite the graphml file.")
    args = parser.parse_args()

    # Ensure sys path includes the root so we can import config
    root_dir = Path(__file__).parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    validate_paths()
    G = load_graph()
    prune_graph(G, dry_run=not args.apply)


if __name__ == "__main__":
    main()
