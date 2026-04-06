"""Deterministic graph generators for benchmark and validation.

Every generator takes a seed-based RNG (or is purely structural) so that
the exact same graph is produced on every run.  This is critical: both
the reference and optimized implementations must receive identical input.

Each generator returns (graph, node_list, edge_list) so tests can inspect
the structure independently of the topology calculation.
"""

from __future__ import annotations
import random
from pydagger import DaggerGraph, DaggerNode, DaggerInputPin, DaggerOutputPin


class BenchNode(DaggerNode):
    """Node with configurable pin counts per topology."""

    def __init__(self, n_inputs: int = 1, n_outputs: int = 1, topology_count: int = 1):
        super().__init__()
        for t in range(topology_count):
            for i in range(n_inputs):
                self.input_pins(t).add_pin(DaggerInputPin(), f"in{i}")
            for i in range(n_outputs):
                self.output_pins(t).add_pin(DaggerOutputPin(), f"out{i}")


def build_linear_chain(n: int, topology_count: int = 1):
    """A -> B -> C -> ... -> N

    Worst case for depth.  max_ordinal = n-1, 1 subgraph.
    """
    graph = DaggerGraph(topology_count)
    nodes = [graph.add_node(BenchNode(1, 1, topology_count)) for _ in range(n)]
    edges = []
    for i in range(n - 1):
        for t in range(topology_count):
            out_pin = nodes[i].get_output_pin("out0", t)
            in_pin = nodes[i + 1].get_input_pin("in0", t)
            out_pin.connect_to_input(in_pin)
            edges.append((nodes[i], nodes[i + 1], t))
    for i, node in enumerate(nodes):
        node.name = f"chain_{i}"
    return graph, nodes, edges


def build_wide_fan_out(width: int, depth: int = 2, topology_count: int = 1):
    """One root fans out to `width` children, each of which fans out again, etc.

    Stress test for top-level fan-out and descendent set sizes.
    Total nodes ≈ (width^depth - 1) / (width - 1) for width > 1.
    """
    graph = DaggerGraph(topology_count)
    root = graph.add_node(BenchNode(0, width, topology_count))
    root.name = "root"
    all_nodes = [root]
    edges = []
    current_layer = [root]

    for d in range(1, depth):
        next_layer = []
        for parent in current_layer:
            for w in range(width):
                out_name = f"out{w}"
                child = graph.add_node(BenchNode(1, width if d < depth - 1 else 0, topology_count))
                child.name = f"d{d}_w{len(next_layer)}"
                all_nodes.append(child)
                for t in range(topology_count):
                    parent.get_output_pin(out_name, t).connect_to_input(
                        child.get_input_pin("in0", t)
                    )
                    edges.append((parent, child, t))
                next_layer.append(child)
        current_layer = next_layer

    return graph, all_nodes, edges


def build_diamond(layers: int, width: int, topology_count: int = 1):
    """Creates a diamond/mesh pattern with heavy convergence and divergence.

    Each layer has `width` nodes.  Every node in layer L connects to every
    node in layer L+1.  This is the worst case for descendent set fan-in.

    Total nodes = layers * width.
    Total edges = (layers - 1) * width * width per topology.
    """
    graph = DaggerGraph(topology_count)
    all_nodes = []
    edges = []

    prev_layer_nodes = []
    for layer in range(layers):
        layer_nodes = []
        for w in range(width):
            n_in = width if layer > 0 else 0
            n_out = width if layer < layers - 1 else 0
            node = graph.add_node(BenchNode(n_in, n_out, topology_count))
            node.name = f"L{layer}_W{w}"
            layer_nodes.append(node)
            all_nodes.append(node)

        if prev_layer_nodes:
            for pi, parent in enumerate(prev_layer_nodes):
                for ci, child in enumerate(layer_nodes):
                    for t in range(topology_count):
                        parent.get_output_pin(f"out{ci}", t).connect_to_input(
                            child.get_input_pin(f"in{pi}", t)
                        )
                        edges.append((parent, child, t))

        prev_layer_nodes = layer_nodes

    return graph, all_nodes, edges


def build_random_dag(n: int, edge_probability: float = 0.3, seed: int = 42,
                     topology_count: int = 1):
    """Random DAG via the "forward edges only" method.

    Nodes are numbered 0..n-1.  For each pair (i, j) where i < j, an edge
    is created with the given probability.  This guarantees acyclicity
    (edges only go from lower to higher index).

    Seeded RNG ensures reproducibility.
    """
    rng = random.Random(seed)
    graph = DaggerGraph(topology_count)

    # pre-calculate how many outputs each node needs
    out_counts = [0] * n
    in_counts = [0] * n
    planned_edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < edge_probability:
                planned_edges.append((i, j))
                out_counts[i] += 1
                in_counts[j] += 1

    # create nodes with correct pin counts
    nodes = []
    for i in range(n):
        node = graph.add_node(
            BenchNode(max(1, in_counts[i]), max(1, out_counts[i]), topology_count)
        )
        node.name = f"rand_{i}"
        nodes.append(node)

    # connect
    edges = []
    out_used = [0] * n
    in_used = [0] * n
    for i, j in planned_edges:
        for t in range(topology_count):
            out_pin = nodes[i].get_output_pin(f"out{out_used[i]}", t)
            in_pin = nodes[j].get_input_pin(f"in{in_used[j]}", t)
            if out_pin and in_pin:
                out_pin.connect_to_input(in_pin)
                edges.append((nodes[i], nodes[j], t))
        out_used[i] += 1
        in_used[j] += 1

    return graph, nodes, edges


def build_parallel_chains(n_chains: int, chain_length: int, topology_count: int = 1):
    """Multiple independent linear chains.

    Tests subgraph partitioning: should produce n_chains subgraphs.
    Total nodes = n_chains * chain_length.
    """
    graph = DaggerGraph(topology_count)
    all_nodes = []
    edges = []

    for c in range(n_chains):
        chain_nodes = []
        for i in range(chain_length):
            node = graph.add_node(BenchNode(1, 1, topology_count))
            node.name = f"c{c}_n{i}"
            chain_nodes.append(node)
            all_nodes.append(node)
        for i in range(chain_length - 1):
            for t in range(topology_count):
                chain_nodes[i].get_output_pin("out0", t).connect_to_input(
                    chain_nodes[i + 1].get_input_pin("in0", t)
                )
                edges.append((chain_nodes[i], chain_nodes[i + 1], t))

    return graph, all_nodes, edges


def build_hourglass(top_width: int, bottom_width: int, neck_size: int = 1,
                    topology_count: int = 1):
    """Wide top -> narrow neck -> wide bottom.

    Tests convergence then divergence through a bottleneck.
    3 layers: top_width -> neck_size -> bottom_width.
    """
    graph = DaggerGraph(topology_count)
    all_nodes = []
    edges = []

    # top layer: no inputs, neck_size outputs each
    top_nodes = []
    for i in range(top_width):
        node = graph.add_node(BenchNode(0, neck_size, topology_count))
        node.name = f"top_{i}"
        top_nodes.append(node)
        all_nodes.append(node)

    # neck layer: top_width inputs, bottom_width outputs
    neck_nodes = []
    for i in range(neck_size):
        node = graph.add_node(BenchNode(top_width, bottom_width, topology_count))
        node.name = f"neck_{i}"
        neck_nodes.append(node)
        all_nodes.append(node)

    # bottom layer: neck_size inputs, no outputs
    bottom_nodes = []
    for i in range(bottom_width):
        node = graph.add_node(BenchNode(neck_size, 0, topology_count))
        node.name = f"bot_{i}"
        bottom_nodes.append(node)
        all_nodes.append(node)

    # connect top -> neck
    for ti, tnode in enumerate(top_nodes):
        for ni, nnode in enumerate(neck_nodes):
            for t in range(topology_count):
                tnode.get_output_pin(f"out{ni}", t).connect_to_input(
                    nnode.get_input_pin(f"in{ti}", t)
                )
                edges.append((tnode, nnode, t))

    # connect neck -> bottom
    for ni, nnode in enumerate(neck_nodes):
        for bi, bnode in enumerate(bottom_nodes):
            for t in range(topology_count):
                nnode.get_output_pin(f"out{bi}", t).connect_to_input(
                    bnode.get_input_pin(f"in{ni}", t)
                )
                edges.append((nnode, bnode, t))

    return graph, all_nodes, edges
