"""
🧠 ZeroCostBrain — Brain Microscope (The Explorer)

Visualizes the knowledge graph: top concepts, neural pathways,
and relationship connections extracted by LightRAG.
"""

import argparse
import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import WORKING_DIR, validate_paths

console = Console()


def load_json(filename: str) -> dict | None:
    """Safely load a JSON file from the LightRAG working directory."""
    path = WORKING_DIR / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        console.print(f"[yellow]⚠️ JSON parse error in {filename}: {e}[/]")
        return None
    except OSError as e:
        console.print(f"[yellow]⚠️ Cannot read {filename}: {e}[/]")
        return None


def explore_brain(top_n: int = 15, max_relations: int = 12):
    """
    Analyze and display the brain's knowledge graph.

    Args:
        top_n: Number of top concepts to display.
        max_relations: Maximum neural pathways to show.
    """
    validate_paths()

    console.print(
        Panel(
            "[bold magenta]🧠 BRAIN MICROSCOPE: Neural Concept Analysis[/]",
            expand=False,
        )
    )

    # Load raw brain data
    doc_entities = load_json("kv_store_full_entities.json")
    relations = load_json("kv_store_full_relations.json")

    if not doc_entities:
        console.print("[bold red]❌ Brain index is currently empty or initializing.[/]")
        console.print("[dim]Run `python index_archive.py` first to build the knowledge graph.[/]")
        return

    # ── FLATTEN ENTITIES ──
    concept_map: dict[str, int] = {}
    for doc_id, data in doc_entities.items():
        if isinstance(data, dict):
            names = data.get("entity_names", [])
            for name in names:
                if name and not str(name).startswith("doc-"):
                    concept_map[name] = concept_map.get(name, 0) + 1

    sorted_concepts = sorted(concept_map.items(), key=lambda x: x[1], reverse=True)[:top_n]

    ent_table = Table(title=f"💎 TOP {len(sorted_concepts)} CORE CONCEPTS", border_style="cyan")
    ent_table.add_column("Concept", style="white")
    ent_table.add_column("Neural Frequency", justify="right", style="bold cyan")

    for name, freq in sorted_concepts:
        bar = "█" * min(freq, 20)
        ent_table.add_row(str(name), f"{freq} {bar}")

    console.print(ent_table)

    # ── STATISTICS ──
    console.print(f"\n[dim]📊 Total unique concepts: {len(concept_map)} | Total entity records: {len(doc_entities)}[/]")

    # ── NEURAL PATHWAYS ──
    rel_table = Table(
        title="🔗 NEURAL PATHWAYS (Cross-Document Connections)",
        border_style="green",
        expand=True,
    )
    rel_table.add_column("Source", style="bold green")
    rel_table.add_column("Connection", style="italic")
    rel_table.add_column("Target", style="bold green")

    if relations:
        count = 0
        for rid, rel in relations.items():
            src = rel.get("src_id", "")
            tgt = rel.get("tgt_id", "")
            logic = rel.get("description", "Related Connection")

            # Skip internal doc-id relations
            if src and tgt and not str(src).startswith("doc-") and not str(tgt).startswith("doc-"):
                short_logic = (logic[:85] + "...") if len(logic) > 85 else logic
                rel_table.add_row(str(src), short_logic, str(tgt))
                count += 1
                if count >= max_relations:
                    break

        if count > 0:
            console.print(rel_table)
            if count >= max_relations:
                total_rels = sum(1 for r in relations.values() if not str(r.get("src_id", "")).startswith("doc-"))
                console.print(
                    f"[dim]... showing {count} of {total_rels} total pathways. Use --relations N to see more.[/]"
                )
        else:
            console.print("[italic yellow]No cross-concept pathways discovered yet. Run more indexing![/]")
    else:
        console.print("[italic yellow]No relation data found. The brain needs more documents to find patterns.[/]")

    console.print("\n[italic blue]💡 TIP:[/] Use `--top 30 --relations 25` for a deeper view.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize the Brain's knowledge graph.")
    parser.add_argument("--top", type=int, default=15, help="Number of top concepts to show.")
    parser.add_argument("--relations", type=int, default=12, help="Max neural pathways to display.")
    args = parser.parse_args()

    explore_brain(top_n=args.top, max_relations=args.relations)
