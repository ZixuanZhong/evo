#!/usr/bin/env python3
"""
propagation.py — Semantic Propagation Algorithm PoC

Implements field-level semantic propagation across microservice call chains,
using the mock live-streaming services (user-service, gift-service, payment-service).

Demonstrates:
  - Forward propagation: API request field → downstream services → DB column
  - Backward propagation: DB column → upstream API fields that touch it
  - Confidence scoring with decay by mapping type
  - Noisy-OR merging for multi-path convergence

Usage:
    python3 propagation.py
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class MappingType(Enum):
    """How a field value is transformed between hops."""
    PASS_THROUGH = "pass_through"   # Direct copy, no change
    TRANSFORM = "transform"         # Computed/formatted (e.g., price * count)
    AGGREGATE = "aggregate"         # Multiple fields merged into one
    FAN_OUT = "fan_out"             # One field split into multiple

    @property
    def confidence_decay(self) -> float:
        """Confidence decay factor per hop for this mapping type."""
        return {
            MappingType.PASS_THROUGH: 0.00,
            MappingType.TRANSFORM: 0.15,
            MappingType.AGGREGATE: 0.25,
            MappingType.FAN_OUT: 0.20,
        }[self]


class Sensitivity(Enum):
    NONE = "none"
    PII = "pii"
    FINANCIAL = "financial"
    INTERNAL_ID = "internal_id"


class NodeType(Enum):
    SERVICE = "Service"
    API = "API"
    FIELD = "Field"
    DB_TABLE = "DBTable"
    DB_COLUMN = "DBColumn"


@dataclass
class Node:
    """A node in the ontology graph."""
    id: str                          # Unique identifier (e.g., "user-service.GetUserProfile.req.user_id")
    name: str                        # Display name
    node_type: NodeType
    service: str = ""                # Which service this belongs to
    sensitivity: Sensitivity = Sensitivity.NONE
    semantic: str = ""               # Chinese semantic description

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Node) and self.id == other.id


@dataclass
class Edge:
    """A directed edge representing field propagation."""
    source: Node
    target: Node
    mapping_type: MappingType
    label: str = ""                  # Description of the mapping

    def __repr__(self):
        return f"{self.source.name} --[{self.mapping_type.value}]--> {self.target.name}"


@dataclass
class PropagationPath:
    """A complete propagation path from source to sink."""
    nodes: list[Node]
    edges: list[Edge]
    confidence: float

    def __repr__(self):
        path_str = " → ".join(f"{n.name}({n.service})" for n in self.nodes)
        return f"[conf={self.confidence:.3f}] {path_str}"


@dataclass
class OntologyGraph:
    """The field-level ontology graph."""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    # Adjacency lists for efficient traversal
    _forward: dict[str, list[Edge]] = field(default_factory=dict)
    _backward: dict[str, list[Edge]] = field(default_factory=dict)

    def add_node(self, node: Node) -> Node:
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
        self._forward.setdefault(edge.source.id, []).append(edge)
        self._backward.setdefault(edge.target.id, []).append(edge)

    def get_forward_edges(self, node_id: str) -> list[Edge]:
        return self._forward.get(node_id, [])

    def get_backward_edges(self, node_id: str) -> list[Edge]:
        return self._backward.get(node_id, [])


# =============================================================================
# CONFIDENCE COMPUTATION
# =============================================================================

def compute_confidence(edges: list[Edge], initial: float = 1.0) -> float:
    """
    Compute cumulative confidence along a propagation path.
    Each hop decays confidence based on the mapping type.

    Formula: conf = initial * ∏(1 - decay_i)
    """
    conf = initial
    for edge in edges:
        conf *= (1.0 - edge.mapping_type.confidence_decay)
    return conf


def noisy_or_merge(confidences: list[float]) -> float:
    """
    Merge multiple path confidences using Noisy-OR.
    P(correct) = 1 - ∏(1 - p_i)

    This models the intuition that more independent paths confirming
    a relationship increase our confidence.
    """
    if not confidences:
        return 0.0
    product = 1.0
    for c in confidences:
        product *= (1.0 - c)
    return 1.0 - product


# =============================================================================
# MOCK CALL GRAPH CONSTRUCTION
# =============================================================================

def build_mock_call_graph() -> OntologyGraph:
    """
    Build a mock ontology graph based on the 3 live-streaming services:
      user-service → gift-service → payment-service

    Models the field propagation paths from IDL/handler/DB schema.
    """
    g = OntologyGraph()

    # ── user-service nodes ──
    us_get_req_uid = g.add_node(Node("us.GetUserProfile.req.user_id", "req.user_id",
        NodeType.FIELD, "user-service", Sensitivity.INTERNAL_ID, "要查询的用户 ID"))
    us_resp_phone = g.add_node(Node("us.GetUserProfile.resp.phone_number", "resp.phone_number",
        NodeType.FIELD, "user-service", Sensitivity.PII, "用户手机号"))
    us_resp_idcard = g.add_node(Node("us.GetUserProfile.resp.id_card", "resp.id_card",
        NodeType.FIELD, "user-service", Sensitivity.PII, "用户身份证号"))
    us_resp_nickname = g.add_node(Node("us.GetUserProfile.resp.nickname", "resp.nickname",
        NodeType.FIELD, "user-service", Sensitivity.NONE, "用户昵称"))

    us_update_phone = g.add_node(Node("us.UpdateUser.req.phone_number", "req.phone_number",
        NodeType.FIELD, "user-service", Sensitivity.PII, "新手机号"))

    # user-service DB columns
    db_users_id = g.add_node(Node("db.users.id", "users.id",
        NodeType.DB_COLUMN, "user-service", Sensitivity.INTERNAL_ID, "用户表主键"))
    db_users_phone = g.add_node(Node("db.users.phone_number", "users.phone_number",
        NodeType.DB_COLUMN, "user-service", Sensitivity.PII, "用户手机号（DB 列）"))
    db_users_idcard = g.add_node(Node("db.users.id_card", "users.id_card",
        NodeType.DB_COLUMN, "user-service", Sensitivity.PII, "身份证号（DB 列）"))
    db_users_nickname = g.add_node(Node("db.users.nickname", "users.nickname",
        NodeType.DB_COLUMN, "user-service", Sensitivity.NONE, "昵称（DB 列）"))

    # user-service edges: DB → response (read path)
    g.add_edge(Edge(db_users_phone, us_resp_phone, MappingType.PASS_THROUGH, "DB read → response"))
    g.add_edge(Edge(db_users_idcard, us_resp_idcard, MappingType.PASS_THROUGH, "DB read → response"))
    g.add_edge(Edge(db_users_nickname, us_resp_nickname, MappingType.PASS_THROUGH, "DB read → response"))
    # user-service edges: request → DB (write path)
    g.add_edge(Edge(us_update_phone, db_users_phone, MappingType.PASS_THROUGH, "request → DB write"))

    # ── gift-service nodes ──
    gs_send_sender = g.add_node(Node("gs.SendGift.req.sender_id", "req.sender_id",
        NodeType.FIELD, "gift-service", Sensitivity.INTERNAL_ID, "送礼者用户 ID"))
    gs_send_receiver = g.add_node(Node("gs.SendGift.req.receiver_id", "req.receiver_id",
        NodeType.FIELD, "gift-service", Sensitivity.INTERNAL_ID, "收礼主播 ID"))
    gs_send_room = g.add_node(Node("gs.SendGift.req.room_id", "req.room_id",
        NodeType.FIELD, "gift-service", Sensitivity.INTERNAL_ID, "直播间 ID"))
    gs_send_price = g.add_node(Node("gs.SendGift.req.gift_price", "req.gift_price",
        NodeType.FIELD, "gift-service", Sensitivity.FINANCIAL, "礼物单价（分）"))
    gs_send_count = g.add_node(Node("gs.SendGift.req.gift_count", "req.gift_count",
        NodeType.FIELD, "gift-service", Sensitivity.NONE, "礼物数量"))
    gs_resp_balance = g.add_node(Node("gs.SendGift.resp.remaining_balance", "resp.remaining_balance",
        NodeType.FIELD, "gift-service", Sensitivity.FINANCIAL, "送礼后剩余余额"))

    # gift-service DB columns
    db_gift_sender = g.add_node(Node("db.gift_records.sender_id", "gift_records.sender_id",
        NodeType.DB_COLUMN, "gift-service", Sensitivity.INTERNAL_ID, "送礼者 ID（DB 列）"))
    db_gift_receiver = g.add_node(Node("db.gift_records.receiver_id", "gift_records.receiver_id",
        NodeType.DB_COLUMN, "gift-service", Sensitivity.INTERNAL_ID, "收礼者 ID（DB 列）"))
    db_gift_value = g.add_node(Node("db.gift_records.gift_value", "gift_records.gift_value",
        NodeType.DB_COLUMN, "gift-service", Sensitivity.FINANCIAL, "礼物总价值（DB 列）"))
    db_gift_sname = g.add_node(Node("db.gift_records.sender_name", "gift_records.sender_name",
        NodeType.DB_COLUMN, "gift-service", Sensitivity.NONE, "送礼者昵称（DB 列）"))

    # gift-service edges: request → DB
    g.add_edge(Edge(gs_send_sender, db_gift_sender, MappingType.PASS_THROUGH, "sender_id 直传 DB"))
    g.add_edge(Edge(gs_send_receiver, db_gift_receiver, MappingType.PASS_THROUGH, "receiver_id 直传 DB"))
    g.add_edge(Edge(gs_send_price, db_gift_value, MappingType.TRANSFORM, "gift_price × gift_count → gift_value"))
    g.add_edge(Edge(gs_send_count, db_gift_value, MappingType.TRANSFORM, "gift_count × gift_price → gift_value"))

    # gift-service → user-service (cross-service): sender_id → GetUserProfile
    g.add_edge(Edge(gs_send_sender, us_get_req_uid, MappingType.PASS_THROUGH, "sender_id → user_id (cross-service)"))
    # user-service resp nickname → gift DB sender_name
    g.add_edge(Edge(us_resp_nickname, db_gift_sname, MappingType.PASS_THROUGH, "nickname → sender_name (cross-service)"))

    # ── payment-service nodes ──
    ps_deduct_uid = g.add_node(Node("ps.Deduct.req.user_id", "req.user_id",
        NodeType.FIELD, "payment-service", Sensitivity.INTERNAL_ID, "被扣款用户 ID"))
    ps_deduct_amount = g.add_node(Node("ps.Deduct.req.amount", "req.amount",
        NodeType.FIELD, "payment-service", Sensitivity.FINANCIAL, "扣款金额（分）"))
    ps_deduct_resp_balance = g.add_node(Node("ps.Deduct.resp.remaining_balance", "resp.remaining_balance",
        NodeType.FIELD, "payment-service", Sensitivity.FINANCIAL, "扣款后剩余余额"))

    # payment-service DB columns
    db_wallet_uid = g.add_node(Node("db.wallets.user_id", "wallets.user_id",
        NodeType.DB_COLUMN, "payment-service", Sensitivity.INTERNAL_ID, "钱包表用户 ID"))
    db_wallet_balance = g.add_node(Node("db.wallets.balance", "wallets.balance",
        NodeType.DB_COLUMN, "payment-service", Sensitivity.FINANCIAL, "余额（DB 列）"))

    # payment-service edges
    g.add_edge(Edge(ps_deduct_uid, db_wallet_uid, MappingType.PASS_THROUGH, "user_id → WHERE wallets.user_id"))
    g.add_edge(Edge(ps_deduct_amount, db_wallet_balance, MappingType.TRANSFORM, "amount → balance -= amount"))
    g.add_edge(Edge(db_wallet_balance, ps_deduct_resp_balance, MappingType.PASS_THROUGH, "balance → remaining_balance"))

    # gift-service → payment-service (cross-service)
    g.add_edge(Edge(gs_send_sender, ps_deduct_uid, MappingType.PASS_THROUGH, "sender_id → user_id (cross-service rename)"))
    g.add_edge(Edge(gs_send_price, ps_deduct_amount, MappingType.TRANSFORM, "gift_price × count → amount"))
    g.add_edge(Edge(ps_deduct_resp_balance, gs_resp_balance, MappingType.PASS_THROUGH, "remaining_balance passthrough"))

    return g


# =============================================================================
# PROPAGATION ALGORITHMS
# =============================================================================

MAX_HOPS = 10
CONFIDENCE_THRESHOLD = 0.3


def forward_propagate(start_node_id: str, graph: OntologyGraph) -> list[PropagationPath]:
    """
    Forward BFS propagation from a source field to all reachable sinks.
    Tracks the full path and cumulative confidence at each hop.

    Args:
        start_node_id: ID of the starting field node
        graph: The ontology graph

    Returns:
        List of all propagation paths from start to leaf nodes
    """
    if start_node_id not in graph.nodes:
        return []

    start_node = graph.nodes[start_node_id]
    # BFS queue: (current_node, path_nodes, path_edges, current_confidence)
    queue: deque[tuple[Node, list[Node], list[Edge], float]] = deque()
    queue.append((start_node, [start_node], [], 1.0))

    results: list[PropagationPath] = []
    visited_paths: set[tuple[str, ...]] = set()  # Avoid duplicate paths

    while queue:
        current, path_nodes, path_edges, conf = queue.popleft()

        # Get outgoing edges
        forward_edges = graph.get_forward_edges(current.id)

        if not forward_edges or len(path_nodes) >= MAX_HOPS:
            # Leaf node or max depth — record path if non-trivial
            if len(path_nodes) > 1 and conf >= CONFIDENCE_THRESHOLD:
                path_key = tuple(n.id for n in path_nodes)
                if path_key not in visited_paths:
                    visited_paths.add(path_key)
                    results.append(PropagationPath(
                        nodes=list(path_nodes),
                        edges=list(path_edges),
                        confidence=conf,
                    ))
            continue

        for edge in forward_edges:
            target = edge.target
            # Avoid cycles
            if target.id in {n.id for n in path_nodes}:
                continue

            new_conf = conf * (1.0 - edge.mapping_type.confidence_decay)
            if new_conf < CONFIDENCE_THRESHOLD:
                continue

            queue.append((
                target,
                path_nodes + [target],
                path_edges + [edge],
                new_conf,
            ))

        # Also record current as a terminal if it has edges but some lead nowhere
        if len(path_nodes) > 1 and conf >= CONFIDENCE_THRESHOLD:
            path_key = tuple(n.id for n in path_nodes)
            if path_key not in visited_paths:
                # Only add if this is a DB column (meaningful sink)
                if current.node_type == NodeType.DB_COLUMN:
                    visited_paths.add(path_key)
                    results.append(PropagationPath(
                        nodes=list(path_nodes),
                        edges=list(path_edges),
                        confidence=conf,
                    ))

    return results


def backward_propagate(db_column_id: str, graph: OntologyGraph) -> list[PropagationPath]:
    """
    Backward BFS propagation from a DB column to all API fields that feed into it.

    Args:
        db_column_id: ID of the DB column node
        graph: The ontology graph

    Returns:
        List of propagation paths (reversed: DB → ... → API field)
    """
    if db_column_id not in graph.nodes:
        return []

    start_node = graph.nodes[db_column_id]
    queue: deque[tuple[Node, list[Node], list[Edge], float]] = deque()
    queue.append((start_node, [start_node], [], 1.0))

    results: list[PropagationPath] = []
    visited_paths: set[tuple[str, ...]] = set()

    while queue:
        current, path_nodes, path_edges, conf = queue.popleft()

        backward_edges = graph.get_backward_edges(current.id)

        if not backward_edges or len(path_nodes) >= MAX_HOPS:
            if len(path_nodes) > 1 and conf >= CONFIDENCE_THRESHOLD:
                path_key = tuple(n.id for n in path_nodes)
                if path_key not in visited_paths:
                    visited_paths.add(path_key)
                    # Reverse to show source → sink direction
                    results.append(PropagationPath(
                        nodes=list(reversed(path_nodes)),
                        edges=list(reversed(path_edges)),
                        confidence=conf,
                    ))
            continue

        for edge in backward_edges:
            source = edge.source
            if source.id in {n.id for n in path_nodes}:
                continue

            new_conf = conf * (1.0 - edge.mapping_type.confidence_decay)
            if new_conf < CONFIDENCE_THRESHOLD:
                continue

            queue.append((
                source,
                path_nodes + [source],
                path_edges + [edge],
                new_conf,
            ))

    return results


# =============================================================================
# MAIN — Demo the propagation with mock services
# =============================================================================

def print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   Ontology Pipeline — Semantic Propagation Algorithm PoC   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Build the graph
    graph = build_mock_call_graph()
    print(f"\nGraph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # ── Forward Propagation: sender_id ──
    print_section("Forward Propagation: sender_id (gift-service)")
    paths = forward_propagate("gs.SendGift.req.sender_id", graph)
    print(f"Found {len(paths)} propagation paths:\n")
    for i, path in enumerate(paths, 1):
        print(f"  Path {i}: {path}")
        for edge in path.edges:
            print(f"    └─ {edge}")

    # ── Forward Propagation: gift_price ──
    print_section("Forward Propagation: gift_price (gift-service)")
    paths = forward_propagate("gs.SendGift.req.gift_price", graph)
    print(f"Found {len(paths)} propagation paths:\n")
    for i, path in enumerate(paths, 1):
        print(f"  Path {i}: {path}")
        for edge in path.edges:
            print(f"    └─ {edge}")

    # ── Backward Propagation: phone_number (DB) ──
    print_section("Backward Propagation: users.phone_number (PII)")
    paths = backward_propagate("db.users.phone_number", graph)
    print(f"Found {len(paths)} paths that write to users.phone_number:\n")
    for i, path in enumerate(paths, 1):
        print(f"  Path {i}: {path}")

    # ── Backward Propagation: wallets.balance (Financial) ──
    print_section("Backward Propagation: wallets.balance (Financial)")
    paths = backward_propagate("db.wallets.balance", graph)
    print(f"Found {len(paths)} paths that affect wallets.balance:\n")
    for i, path in enumerate(paths, 1):
        print(f"  Path {i}: {path}")
        for edge in path.edges:
            print(f"    └─ {edge}")

    # ── Multi-path confidence merging ──
    print_section("Multi-path Confidence Merging (Noisy-OR)")
    # gift_price reaches gift_value via transform, and amount reaches balance via transform
    # Two independent paths to the "financial impact" conclusion
    c1 = compute_confidence([Edge(Node("a","a",NodeType.FIELD), Node("b","b",NodeType.FIELD), MappingType.PASS_THROUGH)])
    c2 = compute_confidence([Edge(Node("a","a",NodeType.FIELD), Node("b","b",NodeType.FIELD), MappingType.TRANSFORM)])
    c3 = compute_confidence([
        Edge(Node("a","a",NodeType.FIELD), Node("b","b",NodeType.FIELD), MappingType.PASS_THROUGH),
        Edge(Node("b","b",NodeType.FIELD), Node("c","c",NodeType.FIELD), MappingType.TRANSFORM),
    ])
    print(f"  Single pass_through hop:          conf = {c1:.3f}")
    print(f"  Single transform hop:             conf = {c2:.3f}")
    print(f"  pass_through + transform (2 hop): conf = {c3:.3f}")
    print(f"  Noisy-OR merge of {c2:.3f} and {c3:.3f}: conf = {noisy_or_merge([c2, c3]):.3f}")

    # ── Summary statistics ──
    print_section("Graph Statistics")
    by_type = {}
    for n in graph.nodes.values():
        by_type.setdefault(n.node_type.value, []).append(n)
    for t, nodes in sorted(by_type.items()):
        print(f"  {t}: {len(nodes)} nodes")

    sensitive = [n for n in graph.nodes.values() if n.sensitivity != Sensitivity.NONE]
    print(f"\n  Sensitive nodes: {len(sensitive)}")
    for n in sensitive:
        print(f"    [{n.sensitivity.value:>11}] {n.id} — {n.semantic}")

    print(f"\n  Total edges: {len(graph.edges)}")
    by_mapping = {}
    for e in graph.edges:
        by_mapping.setdefault(e.mapping_type.value, 0)
        by_mapping[e.mapping_type.value] += 1
    for mt, count in sorted(by_mapping.items()):
        print(f"    {mt}: {count}")

    print("\n✅ Propagation PoC complete.")


if __name__ == "__main__":
    main()
