#!/usr/bin/env python3
"""
visualize.py — Ontology Graph Visualization Demo

Builds a field-level ontology graph for the mock live-streaming services
and renders it as a PNG using networkx + matplotlib.

Node types are color-coded, PII fields are highlighted with red borders,
and edge types use different styles.

Usage:
    python3 visualize.py
    # Outputs: ontology_graph.png
"""

import networkx as nx
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless environments
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# =============================================================================
# DATA MODEL
# =============================================================================

class NodeType(Enum):
    SERVICE = "Service"
    API = "API"
    FIELD = "Field"
    DB_TABLE = "DBTable"
    DB_COLUMN = "DBColumn"


class EdgeType(Enum):
    BELONGS_TO = "belongs_to"       # Field→API, API→Service, DBColumn→DBTable
    PASSES_TO = "passes_to"         # Field→Field (propagation)
    MAPS_TO = "maps_to"             # Field→DBColumn (code→DB mapping)
    CALLS = "calls"                 # API→API (RPC call)


class Sensitivity(Enum):
    NONE = "none"
    PII = "pii"
    FINANCIAL = "financial"


# Color scheme for node types
NODE_COLORS = {
    NodeType.SERVICE:   "#4A90D9",   # Blue
    NodeType.API:       "#7B68EE",   # Medium slate blue
    NodeType.FIELD:     "#50C878",   # Emerald green
    NodeType.DB_TABLE:  "#FF8C00",   # Dark orange
    NodeType.DB_COLUMN: "#FFB347",   # Pastel orange
}

# Edge styles
EDGE_STYLES = {
    EdgeType.BELONGS_TO: {"color": "#AAAAAA", "style": "dotted", "width": 1.0},
    EdgeType.PASSES_TO:  {"color": "#E74C3C", "style": "solid",  "width": 2.0},
    EdgeType.MAPS_TO:    {"color": "#F39C12", "style": "dashed", "width": 1.5},
    EdgeType.CALLS:      {"color": "#3498DB", "style": "solid",  "width": 2.0},
}

# Sensitivity highlight colors (for node borders)
SENSITIVITY_BORDER = {
    Sensitivity.NONE:      "#333333",
    Sensitivity.PII:       "#FF0000",   # Red border for PII
    Sensitivity.FINANCIAL: "#FF6600",   # Orange border for financial
}


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def build_ontology_graph() -> nx.DiGraph:
    """
    Build the ontology graph for the 3 mock live-streaming services.
    Includes Service, API, Field, DBTable, DBColumn nodes and
    belongs_to, passes_to, maps_to, calls edges.
    """
    G = nx.DiGraph()

    def add(node_id: str, label: str, ntype: NodeType, sens: Sensitivity = Sensitivity.NONE):
        G.add_node(node_id, label=label, node_type=ntype, sensitivity=sens)

    def edge(src: str, dst: str, etype: EdgeType, label: str = ""):
        G.add_edge(src, dst, edge_type=etype, label=label)

    # ── Services ──
    add("svc:user",    "user-service",    NodeType.SERVICE)
    add("svc:gift",    "gift-service",    NodeType.SERVICE)
    add("svc:payment", "payment-service", NodeType.SERVICE)

    # ── APIs ──
    add("api:GetUserProfile", "GetUserProfile", NodeType.API)
    add("api:UpdateUser",     "UpdateUser",     NodeType.API)
    add("api:SendGift",       "SendGift",       NodeType.API)
    add("api:GetGiftHistory", "GetGiftHistory",  NodeType.API)
    add("api:Deduct",         "Deduct",         NodeType.API)
    add("api:GetBalance",     "GetBalance",     NodeType.API)

    # API → Service (belongs_to)
    edge("api:GetUserProfile", "svc:user",    EdgeType.BELONGS_TO)
    edge("api:UpdateUser",     "svc:user",    EdgeType.BELONGS_TO)
    edge("api:SendGift",       "svc:gift",    EdgeType.BELONGS_TO)
    edge("api:GetGiftHistory", "svc:gift",    EdgeType.BELONGS_TO)
    edge("api:Deduct",         "svc:payment", EdgeType.BELONGS_TO)
    edge("api:GetBalance",     "svc:payment", EdgeType.BELONGS_TO)

    # API → API (calls)
    edge("api:SendGift", "api:Deduct",         EdgeType.CALLS, "RPC")
    edge("api:SendGift", "api:GetUserProfile", EdgeType.CALLS, "RPC")

    # ── Fields (selected key fields for readability) ──
    # user-service fields
    add("f:gup.user_id",      "req.user_id",      NodeType.FIELD, Sensitivity.NONE)
    add("f:gup.phone_number", "resp.phone_number", NodeType.FIELD, Sensitivity.PII)
    add("f:gup.id_card",      "resp.id_card",      NodeType.FIELD, Sensitivity.PII)
    add("f:uu.phone_number",  "req.phone_number",  NodeType.FIELD, Sensitivity.PII)

    edge("f:gup.user_id",      "api:GetUserProfile", EdgeType.BELONGS_TO)
    edge("f:gup.phone_number", "api:GetUserProfile", EdgeType.BELONGS_TO)
    edge("f:gup.id_card",      "api:GetUserProfile", EdgeType.BELONGS_TO)
    edge("f:uu.phone_number",  "api:UpdateUser",     EdgeType.BELONGS_TO)

    # gift-service fields
    add("f:sg.sender_id",   "req.sender_id",         NodeType.FIELD)
    add("f:sg.gift_price",  "req.gift_price",         NodeType.FIELD, Sensitivity.FINANCIAL)
    add("f:sg.resp_bal",    "resp.remaining_balance",  NodeType.FIELD, Sensitivity.FINANCIAL)

    edge("f:sg.sender_id",  "api:SendGift", EdgeType.BELONGS_TO)
    edge("f:sg.gift_price", "api:SendGift", EdgeType.BELONGS_TO)
    edge("f:sg.resp_bal",   "api:SendGift", EdgeType.BELONGS_TO)

    # payment-service fields
    add("f:dd.user_id", "req.user_id",            NodeType.FIELD)
    add("f:dd.amount",  "req.amount",              NodeType.FIELD, Sensitivity.FINANCIAL)
    add("f:dd.resp_bal","resp.remaining_balance",   NodeType.FIELD, Sensitivity.FINANCIAL)

    edge("f:dd.user_id", "api:Deduct", EdgeType.BELONGS_TO)
    edge("f:dd.amount",  "api:Deduct", EdgeType.BELONGS_TO)
    edge("f:dd.resp_bal","api:Deduct", EdgeType.BELONGS_TO)

    # ── DB Tables ──
    add("tbl:users",        "users",        NodeType.DB_TABLE)
    add("tbl:gift_records", "gift_records", NodeType.DB_TABLE)
    add("tbl:wallets",      "wallets",      NodeType.DB_TABLE)

    # ── DB Columns ──
    add("col:users.phone",  "phone_number", NodeType.DB_COLUMN, Sensitivity.PII)
    add("col:users.idcard", "id_card",      NodeType.DB_COLUMN, Sensitivity.PII)
    add("col:gift.sender",  "sender_id",    NodeType.DB_COLUMN)
    add("col:gift.value",   "gift_value",   NodeType.DB_COLUMN, Sensitivity.FINANCIAL)
    add("col:wallet.uid",   "user_id",      NodeType.DB_COLUMN)
    add("col:wallet.bal",   "balance",      NodeType.DB_COLUMN, Sensitivity.FINANCIAL)

    # DBColumn → DBTable (belongs_to)
    edge("col:users.phone",  "tbl:users",        EdgeType.BELONGS_TO)
    edge("col:users.idcard", "tbl:users",        EdgeType.BELONGS_TO)
    edge("col:gift.sender",  "tbl:gift_records", EdgeType.BELONGS_TO)
    edge("col:gift.value",   "tbl:gift_records", EdgeType.BELONGS_TO)
    edge("col:wallet.uid",   "tbl:wallets",      EdgeType.BELONGS_TO)
    edge("col:wallet.bal",   "tbl:wallets",      EdgeType.BELONGS_TO)

    # ── Propagation edges (passes_to) ──
    # sender_id propagation chain
    edge("f:sg.sender_id", "f:dd.user_id",    EdgeType.PASSES_TO, "rename")
    edge("f:sg.sender_id", "f:gup.user_id",   EdgeType.PASSES_TO, "rename")

    # gift_price → amount (transform)
    edge("f:sg.gift_price", "f:dd.amount", EdgeType.PASSES_TO, "×count")

    # remaining_balance passthrough
    edge("f:dd.resp_bal", "f:sg.resp_bal", EdgeType.PASSES_TO, "passthrough")

    # ── maps_to edges (Field → DBColumn) ──
    edge("f:gup.phone_number", "col:users.phone",  EdgeType.MAPS_TO, "read")
    edge("f:gup.id_card",      "col:users.idcard", EdgeType.MAPS_TO, "read")
    edge("f:uu.phone_number",  "col:users.phone",  EdgeType.MAPS_TO, "write")
    edge("f:sg.sender_id",     "col:gift.sender",  EdgeType.MAPS_TO, "write")
    edge("f:sg.gift_price",    "col:gift.value",   EdgeType.MAPS_TO, "write(transform)")
    edge("f:dd.user_id",       "col:wallet.uid",   EdgeType.MAPS_TO, "WHERE")
    edge("f:dd.amount",        "col:wallet.bal",   EdgeType.MAPS_TO, "DECREMENT")

    return G


# =============================================================================
# LAYOUT — Manual hierarchical layout for clarity
# =============================================================================

def compute_layout(G: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """
    Compute a layered layout:
      Layer 0 (top):    Services
      Layer 1:          APIs
      Layer 2:          Fields
      Layer 3:          DB Tables
      Layer 4 (bottom): DB Columns
    """
    layers = {
        NodeType.SERVICE:   4.0,
        NodeType.API:       3.0,
        NodeType.FIELD:     2.0,
        NodeType.DB_TABLE:  1.0,
        NodeType.DB_COLUMN: 0.0,
    }

    # Group nodes by type
    by_type: dict[NodeType, list[str]] = {}
    for nid, data in G.nodes(data=True):
        nt = data["node_type"]
        by_type.setdefault(nt, []).append(nid)

    pos = {}
    for nt, node_ids in by_type.items():
        y = layers[nt]
        n = len(node_ids)
        # Center horizontally
        for i, nid in enumerate(sorted(node_ids)):
            x = (i - (n - 1) / 2) * 2.5
            pos[nid] = (x, y)

    return pos


# =============================================================================
# RENDERING
# =============================================================================

def render_graph(G: nx.DiGraph, output_path: str = "ontology_graph.png"):
    """Render the ontology graph to a PNG file."""
    pos = compute_layout(G)

    fig, ax = plt.subplots(1, 1, figsize=(22, 14))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    # Draw edges by type
    for etype in EdgeType:
        style_cfg = EDGE_STYLES[etype]
        edge_list = [(u, v) for u, v, d in G.edges(data=True) if d["edge_type"] == etype]
        if edge_list:
            nx.draw_networkx_edges(
                G, pos, edgelist=edge_list, ax=ax,
                edge_color=style_cfg["color"],
                style=style_cfg["style"],
                width=style_cfg["width"],
                arrows=True, arrowsize=15,
                alpha=0.7,
                connectionstyle="arc3,rad=0.1",
                min_source_margin=15, min_target_margin=15,
            )

    # Draw nodes by type, with sensitivity-based borders
    for ntype in NodeType:
        node_list = [n for n, d in G.nodes(data=True) if d["node_type"] == ntype]
        if not node_list:
            continue

        node_colors = [NODE_COLORS[ntype]] * len(node_list)
        edge_colors = [SENSITIVITY_BORDER[G.nodes[n]["sensitivity"]] for n in node_list]
        node_sizes = {
            NodeType.SERVICE: 2000,
            NodeType.API: 1500,
            NodeType.FIELD: 1000,
            NodeType.DB_TABLE: 1800,
            NodeType.DB_COLUMN: 1000,
        }

        nx.draw_networkx_nodes(
            G, pos, nodelist=node_list, ax=ax,
            node_color=node_colors,
            edgecolors=edge_colors,
            linewidths=[3.0 if G.nodes[n]["sensitivity"] != Sensitivity.NONE else 1.0 for n in node_list],
            node_size=node_sizes[ntype],
            alpha=0.9,
        )

    # Draw labels
    labels = {n: d["label"] for n, d in G.nodes(data=True)}
    nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=7, font_weight="bold")

    # Draw edge labels for propagation edges only
    prop_edge_labels = {
        (u, v): d["label"]
        for u, v, d in G.edges(data=True)
        if d["edge_type"] in (EdgeType.PASSES_TO, EdgeType.MAPS_TO) and d.get("label")
    }
    nx.draw_networkx_edge_labels(G, pos, prop_edge_labels, ax=ax, font_size=6, font_color="#666666")

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor=NODE_COLORS[NodeType.SERVICE],   label="Service",   edgecolor="black"),
        mpatches.Patch(facecolor=NODE_COLORS[NodeType.API],       label="API",       edgecolor="black"),
        mpatches.Patch(facecolor=NODE_COLORS[NodeType.FIELD],     label="Field",     edgecolor="black"),
        mpatches.Patch(facecolor=NODE_COLORS[NodeType.DB_TABLE],  label="DB Table",  edgecolor="black"),
        mpatches.Patch(facecolor=NODE_COLORS[NodeType.DB_COLUMN], label="DB Column", edgecolor="black"),
        mpatches.Patch(facecolor="white", label="── PII ──",      edgecolor="#FF0000", linewidth=3),
        mpatches.Patch(facecolor="white", label="── Financial ──", edgecolor="#FF6600", linewidth=3),
    ]

    # Edge type legend
    from matplotlib.lines import Line2D
    edge_legend = [
        Line2D([0], [0], color=EDGE_STYLES[EdgeType.BELONGS_TO]["color"], linestyle="dotted",  lw=1, label="belongs_to"),
        Line2D([0], [0], color=EDGE_STYLES[EdgeType.PASSES_TO]["color"],  linestyle="solid",   lw=2, label="passes_to"),
        Line2D([0], [0], color=EDGE_STYLES[EdgeType.MAPS_TO]["color"],    linestyle="dashed",  lw=1.5, label="maps_to"),
        Line2D([0], [0], color=EDGE_STYLES[EdgeType.CALLS]["color"],      linestyle="solid",   lw=2, label="calls"),
    ]
    legend_elements.extend(edge_legend)

    ax.legend(handles=legend_elements, loc="upper left", fontsize=8,
              framealpha=0.9, edgecolor="#CCCCCC")

    ax.set_title(
        "Ontology Graph — Live-Streaming Services (user / gift / payment)\n"
        "Field-level semantic propagation with PII/Financial highlighting",
        fontsize=14, fontweight="bold", pad=20,
    )
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"✅ Graph rendered to: {output_path}")


# =============================================================================
# STATS
# =============================================================================

def print_graph_stats(G: nx.DiGraph):
    """Print summary statistics about the ontology graph."""
    print(f"\n📊 Graph Statistics:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # Count by node type
    by_type = {}
    for _, d in G.nodes(data=True):
        nt = d["node_type"].value
        by_type[nt] = by_type.get(nt, 0) + 1
    for nt, count in sorted(by_type.items()):
        print(f"    {nt}: {count}")

    # Count by edge type
    by_etype = {}
    for _, _, d in G.edges(data=True):
        et = d["edge_type"].value
        by_etype[et] = by_etype.get(et, 0) + 1
    print(f"  Edge types:")
    for et, count in sorted(by_etype.items()):
        print(f"    {et}: {count}")

    # Sensitive nodes
    sensitive = [(nid, d) for nid, d in G.nodes(data=True) if d["sensitivity"] != Sensitivity.NONE]
    print(f"\n  🔴 Sensitive nodes: {len(sensitive)}")
    for nid, d in sensitive:
        print(f"    [{d['sensitivity'].value:>9}] {d['label']}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Ontology Pipeline — Graph Visualization Demo           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    G = build_ontology_graph()
    print_graph_stats(G)

    output_path = "output/poc/ontology_graph.png"
    render_graph(G, output_path)

    print(f"\n🎨 Visualization features:")
    print(f"  • 5 node types with distinct colors (blue/purple/green/orange/yellow)")
    print(f"  • PII fields have RED borders, Financial fields have ORANGE borders")
    print(f"  • 4 edge types: belongs_to (dotted), passes_to (red solid),")
    print(f"    maps_to (orange dashed), calls (blue solid)")
    print(f"  • Hierarchical layout: Service → API → Field → DBTable → DBColumn")
    print(f"  • Edge labels show propagation type (rename, ×count, passthrough, etc.)")


if __name__ == "__main__":
    main()
