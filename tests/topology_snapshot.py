"""Capture and compare complete topology state for validation.

A TopologySnapshot freezes every piece of computed topology data so that
two algorithm implementations can be compared field-by-field.  When a
mismatch is found the diff report tells you exactly which node, which
topology system, and which field diverged.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pydagger import DaggerGraph


@dataclass(frozen=True)
class NodeSnapshot:
    """Complete topology state for a single node in one topology system."""
    node_id: str
    node_name: str
    topology_system: int
    ordinal: int
    subgraph_affiliation: int
    descendent_ids: tuple[str, ...]    # ordered — order matters for determinism
    is_top_level: bool
    is_bottom_level: bool


@dataclass
class TopologySnapshot:
    """Complete topology state for an entire graph."""
    node_count: int
    topology_count: int
    # per topology system
    max_ordinals: dict[int, int] = field(default_factory=dict)
    sub_graph_counts: dict[int, int] = field(default_factory=dict)
    top_level_node_ids: dict[int, tuple[str, ...]] = field(default_factory=dict)
    bottom_level_node_ids: dict[int, tuple[str, ...]] = field(default_factory=dict)
    # per node per topology
    node_snapshots: dict[tuple[str, int], NodeSnapshot] = field(default_factory=dict)

    def diff(self, other: TopologySnapshot) -> list[str]:
        """Return a list of human-readable differences.  Empty list = identical."""
        diffs: list[str] = []

        if self.node_count != other.node_count:
            diffs.append(f"node_count: {self.node_count} vs {other.node_count}")
        if self.topology_count != other.topology_count:
            diffs.append(f"topology_count: {self.topology_count} vs {other.topology_count}")

        for t in sorted(set(self.max_ordinals) | set(other.max_ordinals)):
            a = self.max_ordinals.get(t)
            b = other.max_ordinals.get(t)
            if a != b:
                diffs.append(f"topology {t}: max_ordinal {a} vs {b}")

        for t in sorted(set(self.sub_graph_counts) | set(other.sub_graph_counts)):
            a = self.sub_graph_counts.get(t)
            b = other.sub_graph_counts.get(t)
            if a != b:
                diffs.append(f"topology {t}: sub_graph_count {a} vs {b}")

        for t in sorted(set(self.top_level_node_ids) | set(other.top_level_node_ids)):
            a = self.top_level_node_ids.get(t, ())
            b = other.top_level_node_ids.get(t, ())
            if set(a) != set(b):
                diffs.append(f"topology {t}: top_level_nodes differ (len {len(a)} vs {len(b)})")

        for t in sorted(set(self.bottom_level_node_ids) | set(other.bottom_level_node_ids)):
            a = self.bottom_level_node_ids.get(t, ())
            b = other.bottom_level_node_ids.get(t, ())
            if set(a) != set(b):
                diffs.append(f"topology {t}: bottom_level_nodes differ (len {len(a)} vs {len(b)})")

        all_keys = sorted(set(self.node_snapshots) | set(other.node_snapshots))
        for key in all_keys:
            a = self.node_snapshots.get(key)
            b = other.node_snapshots.get(key)
            node_id, topo = key

            if a is None:
                diffs.append(f"node {node_id} topo {topo}: missing in first snapshot")
                continue
            if b is None:
                diffs.append(f"node {node_id} topo {topo}: missing in second snapshot")
                continue

            label = f"node '{a.node_name}' ({node_id[:8]}) topo {topo}"
            if a.ordinal != b.ordinal:
                diffs.append(f"{label}: ordinal {a.ordinal} vs {b.ordinal}")
            if a.subgraph_affiliation != b.subgraph_affiliation:
                diffs.append(f"{label}: subgraph_affiliation {a.subgraph_affiliation} vs {b.subgraph_affiliation}")
            if a.descendent_ids != b.descendent_ids:
                a_set, b_set = set(a.descendent_ids), set(b.descendent_ids)
                only_a = a_set - b_set
                only_b = b_set - a_set
                if only_a or only_b:
                    diffs.append(f"{label}: descendent sets differ (+{len(only_b)} -{len(only_a)})")
                elif a.descendent_ids != b.descendent_ids:
                    diffs.append(f"{label}: descendent order differs")
            if a.is_top_level != b.is_top_level:
                diffs.append(f"{label}: is_top_level {a.is_top_level} vs {b.is_top_level}")
            if a.is_bottom_level != b.is_bottom_level:
                diffs.append(f"{label}: is_bottom_level {a.is_bottom_level} vs {b.is_bottom_level}")

        return diffs


def capture_snapshot(graph: DaggerGraph) -> TopologySnapshot:
    """Capture the complete topology state of a graph."""
    snap = TopologySnapshot(
        node_count=len(graph.nodes),
        topology_count=graph._topology_count,
    )

    for t in range(graph._topology_count):
        snap.max_ordinals[t] = graph.max_ordinal(t)
        snap.sub_graph_counts[t] = graph.sub_graph_count(t)
        snap.top_level_node_ids[t] = tuple(
            n.instance_id for n in graph.top_level_nodes(t)
        )
        snap.bottom_level_node_ids[t] = tuple(
            n.instance_id for n in graph.bottom_level_nodes(t)
        )

        for node in graph.nodes:
            ns = NodeSnapshot(
                node_id=node.instance_id,
                node_name=node.name,
                topology_system=t,
                ordinal=node.ordinal(t),
                subgraph_affiliation=node.subgraph_affiliation(t),
                descendent_ids=tuple(d.instance_id for d in node.descendents(t)),
                is_top_level=node.is_top_level(t),
                is_bottom_level=node.is_bottom_level(t),
            )
            snap.node_snapshots[(node.instance_id, t)] = ns

    return snap
