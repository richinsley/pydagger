"""Benchmark and validation test suite.

These tests serve two purposes:

1. **Correctness validation** — capture a topology snapshot, force a full
   recalculation, capture again, and verify they match.  This proves the
   current implementation is at least self-consistent.

2. **Performance baseline** — time the calculate_topology() call across
   various graph shapes and sizes.  Results are printed as a table so you
   can compare before/after optimization.

Run with:  pytest tests/test_benchmark.py -v -s
The -s flag is needed to see the timing table.
"""

import time
import pytest

from pydagger import DaggerGraph
from tests.topology_snapshot import capture_snapshot
from tests.graph_generators import (
    build_linear_chain,
    build_wide_fan_out,
    build_diamond,
    build_random_dag,
    build_parallel_chains,
    build_hourglass,
)


# ---------------------------------------------------------------------------
# Correctness: self-consistency after recalculation
# ---------------------------------------------------------------------------

class TestTopologyConsistency:
    """Verify that recalculating topology produces identical results."""

    def _assert_consistent(self, graph: DaggerGraph):
        snap_before = capture_snapshot(graph)
        graph.calculate_topology()
        snap_after = capture_snapshot(graph)
        diffs = snap_before.diff(snap_after)
        assert diffs == [], f"Topology inconsistent after recalculation:\n" + "\n".join(diffs)

    def test_linear_chain_10(self):
        graph, _, _ = build_linear_chain(10)
        self._assert_consistent(graph)

    def test_linear_chain_100(self):
        graph, _, _ = build_linear_chain(100)
        self._assert_consistent(graph)

    def test_wide_fan_out_5x3(self):
        graph, _, _ = build_wide_fan_out(5, 3)
        self._assert_consistent(graph)

    def test_diamond_5x4(self):
        graph, _, _ = build_diamond(5, 4)
        self._assert_consistent(graph)

    def test_diamond_4x3_dual_topology(self):
        graph, _, _ = build_diamond(4, 3, topology_count=2)
        self._assert_consistent(graph)

    def test_random_dag_50(self):
        graph, _, _ = build_random_dag(50, 0.2, seed=42)
        self._assert_consistent(graph)

    def test_random_dag_100(self):
        graph, _, _ = build_random_dag(100, 0.15, seed=123)
        self._assert_consistent(graph)

    def test_parallel_chains_10x10(self):
        graph, _, _ = build_parallel_chains(10, 10)
        self._assert_consistent(graph)

    def test_hourglass_10_10_2(self):
        graph, _, _ = build_hourglass(10, 10, 2)
        self._assert_consistent(graph)


# ---------------------------------------------------------------------------
# Correctness: structural invariants
# ---------------------------------------------------------------------------

class TestTopologyInvariants:
    """Verify structural properties that must hold for any correct topology."""

    def _check_invariants(self, graph: DaggerGraph):
        for t in range(graph._topology_count):
            for node in graph.nodes:
                ordinal = node.ordinal(t)

                # ordinal must be >= 0 for nodes in the graph
                assert ordinal >= 0, (
                    f"Node '{node.name}' has negative ordinal {ordinal} in topology {t}"
                )

                # top-level nodes must have ordinal 0
                if node.is_top_level(t):
                    assert ordinal == 0, (
                        f"Top-level node '{node.name}' has ordinal {ordinal} != 0 in topology {t}"
                    )

                # every descendent must have a strictly higher ordinal
                for desc in node.descendents(t):
                    assert desc.ordinal(t) > node.ordinal(t), (
                        f"Node '{node.name}' (ord {ordinal}) has descendent "
                        f"'{desc.name}' with ordinal {desc.ordinal(t)} in topology {t}"
                    )

                # descendents must be sorted by ordinal
                desc = node.descendents(t)
                for i in range(len(desc) - 1):
                    assert desc[i].ordinal(t) <= desc[i + 1].ordinal(t), (
                        f"Descendents of '{node.name}' not sorted by ordinal in topology {t}"
                    )

                # connected output targets must be in descendents
                for opin in node.output_pins(t).all_pins:
                    for ipin in opin.connected_to:
                        child = ipin.parent_node
                        assert child in node.descendents(t), (
                            f"Connected child '{child.name}' not in descendents of '{node.name}'"
                        )

            # subgraph affiliations: nodes in same subgraph must be reachable
            sub_count = graph.sub_graph_count(t)
            for si in range(sub_count):
                sub_nodes = graph.get_sub_graph_nodes(si, t)
                assert len(sub_nodes) > 0, f"Empty subgraph {si} in topology {t}"

    def test_linear_chain(self):
        graph, nodes, _ = build_linear_chain(20)
        self._check_invariants(graph)
        # linear chain: ordinals should be 0, 1, 2, ... n-1
        for i, node in enumerate(nodes):
            assert node.ordinal(0) == i

    def test_wide_fan_out(self):
        graph, _, _ = build_wide_fan_out(4, 3)
        self._check_invariants(graph)

    def test_diamond(self):
        graph, _, _ = build_diamond(4, 3)
        self._check_invariants(graph)
        # all nodes in same layer should have same ordinal
        for node in graph.nodes:
            layer = int(node.name.split("_")[0][1:])  # extract layer from "L{n}_W{m}"
            assert node.ordinal(0) == layer

    def test_random_dag(self):
        graph, _, _ = build_random_dag(80, 0.2, seed=99)
        self._check_invariants(graph)

    def test_parallel_chains(self):
        graph, _, _ = build_parallel_chains(5, 10)
        self._check_invariants(graph)
        # should have exactly 5 subgraphs
        assert graph.sub_graph_count(0) == 5

    def test_hourglass(self):
        graph, _, _ = build_hourglass(8, 8, 2)
        self._check_invariants(graph)

    def test_dual_topology(self):
        graph, _, _ = build_diamond(3, 3, topology_count=2)
        self._check_invariants(graph)


# ---------------------------------------------------------------------------
# Benchmark: timing
# ---------------------------------------------------------------------------

class TestBenchmark:
    """Time calculate_topology() across graph shapes and sizes.

    These aren't pass/fail tests — they capture timing baselines.
    Run with -s to see the table.
    """

    SCENARIOS = [
        # linear chains — depth stress
        ("linear_20",           lambda: build_linear_chain(20)),
        ("linear_50",           lambda: build_linear_chain(50)),
        ("linear_100",          lambda: build_linear_chain(100)),
        ("linear_200",          lambda: build_linear_chain(200)),
        # fan-out — breadth stress
        ("fan_out_3x3",         lambda: build_wide_fan_out(3, 3)),
        ("fan_out_4x3",         lambda: build_wide_fan_out(4, 3)),
        ("fan_out_3x4",         lambda: build_wide_fan_out(3, 4)),
        # diamond — convergent paths (descendent set worst case)
        ("diamond_4x3",         lambda: build_diamond(4, 3)),
        ("diamond_5x4",         lambda: build_diamond(5, 4)),
        ("diamond_6x3",         lambda: build_diamond(6, 3)),
        ("diamond_5x5",         lambda: build_diamond(5, 5)),
        # random DAGs
        ("random_30_p20",       lambda: build_random_dag(30, 0.2, seed=42)),
        ("random_50_p15",       lambda: build_random_dag(50, 0.15, seed=42)),
        ("random_50_p10",       lambda: build_random_dag(50, 0.10, seed=42)),
        ("random_100_p05",      lambda: build_random_dag(100, 0.05, seed=42)),
        # parallel chains — subgraph partitioning
        ("parallel_5x20",       lambda: build_parallel_chains(5, 20)),
        ("parallel_10x10",      lambda: build_parallel_chains(10, 10)),
        # hourglass — convergent + divergent
        ("hourglass_10_10_2",   lambda: build_hourglass(10, 10, 2)),
        ("hourglass_15_15_2",   lambda: build_hourglass(15, 15, 2)),
        # dual topology
        ("diamond_4x3_dual",    lambda: build_diamond(4, 3, topology_count=2)),
    ]

    @pytest.fixture(autouse=True, scope="class")
    def _run_benchmarks(self, request):
        """Run all scenarios once, store results for individual test access."""
        results = {}
        for name, builder in self.SCENARIOS:
            graph, nodes, edges = builder()
            n_nodes = len(graph.nodes)
            n_edges = len(edges)

            # time multiple iterations for stability
            iterations = 3
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                graph.calculate_topology()
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            avg_ms = (sum(times) / len(times)) * 1000
            min_ms = min(times) * 1000
            max_ms = max(times) * 1000

            results[name] = {
                "n_nodes": n_nodes,
                "n_edges": n_edges,
                "avg_ms": avg_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "graph": graph,
            }

        request.cls._results = results

        # print the table after all scenarios
        yield

        print("\n")
        print("=" * 85)
        print(f"{'Scenario':<25} {'Nodes':>6} {'Edges':>6} {'Avg ms':>10} {'Min ms':>10} {'Max ms':>10}")
        print("-" * 85)
        for name, _ in self.SCENARIOS:
            r = results[name]
            print(
                f"{name:<25} {r['n_nodes']:>6} {r['n_edges']:>6} "
                f"{r['avg_ms']:>10.3f} {r['min_ms']:>10.3f} {r['max_ms']:>10.3f}"
            )
        print("=" * 85)

    def test_benchmark_ran(self):
        """Verify benchmarks completed and results were captured."""
        assert hasattr(self, "_results")
        assert len(self._results) == len(self.SCENARIOS)

    def test_all_scenarios_valid(self):
        """Verify all benchmarked graphs pass invariant checks."""
        for name, r in self._results.items():
            graph = r["graph"]
            for t in range(graph._topology_count):
                for node in graph.nodes:
                    assert node.ordinal(t) >= 0, f"{name}: node '{node.name}' has negative ordinal"
                    for desc in node.descendents(t):
                        assert desc.ordinal(t) > node.ordinal(t), (
                            f"{name}: descendent ordering violated"
                        )
