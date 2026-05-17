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
import logging
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

logger = logging.getLogger(__name__)

GRAPH_PATH = WORKING_DIR / "graph_chunk_entity_relation.graphml"

# Regex for common date patterns (YYYY-MM-DD, Month YYYY, etc.)
DATE_PATTERN = re.compile(
    r"^(?:19|20)\d{2}-\d{2}-\d{2}$|^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$"
)
SYMBOL_PATTERN = re.compile(r"^[^a-zA-Z0-9]+$")


def load_graph() -> nx.Graph:
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(f"Graph file not found: {GRAPH_PATH}")
    logger.info(f"Loading graph from {GRAPH_PATH}...")
    return nx.read_graphml(str(GRAPH_PATH))


def save_graph(G: nx.Graph) -> None:
    from datetime import datetime as _dt
    logger.info(f"Saving pruned graph to {GRAPH_PATH}...")
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    backup_path = GRAPH_PATH.with_name(f"{GRAPH_PATH.stem}_{ts}.graphml.bak")
    GRAPH_PATH.replace(backup_path)
    nx.write_graphml(G, str(GRAPH_PATH))
    logger.info(f"Original graph backed up to {backup_path}")


def prune_graph(G: nx.Graph, dry_run: bool = True):
    initial_nodes = G.number_of_nodes()
    initial_edges = G.number_of_edges()

    nodes_to_remove = set()
    orphans = 0
    date_nodes = 0
    symbol_nodes = 0

    for node, degree in G.degree():
        if degree == 0:
            nodes_to_remove.add(node)
            orphans += 1
            continue

        if degree == 1:
            node_name = str(node).strip()
            if DATE_PATTERN.match(node_name):
                nodes_to_remove.add(node)
                date_nodes += 1
                continue
            if SYMBOL_PATTERN.match(node_name):
                nodes_to_remove.add(node)
                symbol_nodes += 1
                continue

    mode = "DRY RUN" if dry_run else "APPLY"
    logger.info(f"=== PRUNE {mode} === initial: {initial_nodes} nodes, {initial_edges} edges")
    logger.info(
        f"  Identified for removal — orphans: {orphans}, dates: {date_nodes}, "
        f"symbols: {symbol_nodes}, total: {len(nodes_to_remove)}"
    )

    if not dry_run and nodes_to_remove:
        G.remove_nodes_from(nodes_to_remove)
        logger.info(f"  Pruned graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        save_graph(G)
        logger.info("✅ Graph successfully pruned.")
    elif dry_run:
        logger.info("  Run with --apply to perform the actual pruning.")


def main():
    parser = argparse.ArgumentParser(description="Prune noisy entities from LightRAG GraphML.")
    parser.add_argument("--apply", action="store_true", help="Apply changes and overwrite the graphml file.")
    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    validate_paths()
    try:
        G = load_graph()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    prune_graph(G, dry_run=not args.apply)


if __name__ == "__main__":
    main()
