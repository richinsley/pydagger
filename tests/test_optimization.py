"""Tests that compare optimized calculate_topology against the reference implementation.

Strategy:
  1. Build a graph using a generator
  2. Capture a snapshot (computed by the current/reference implementation)
  3. Call calculate_topology() again (which now runs the optimized code)
  4. Capture a second snapshot
  5. Diff — must be empty

This catches any divergence in ordinals, descendents, descendent ordering,
subgraph affiliations, subgraph counts, top/bottom level classification.
"""

import pytest

from pydagger import DaggerGraph, DaggerNode, DaggerInputPin, DaggerOutputPin
from tests.topology_snapshot import capture_snapshot
from tests.graph_generators import (
    build_linear_chain,
    build_wide_fan_out,
    build_diamond,
    build_random_dag,
    build_parallel_chains,
    build_hourglass,
)


class TestOptimizationCorrectness:
    """Every graph shape must produce identical topology after recalculation."""

    def _assert_identical(self, graph):
        snap_before = capture_snapshot(graph)
        graph.calculate_topology()
        snap_after = capture_snapshot(graph)
        diffs = snap_before.diff(snap_after)
        assert diffs == [], "Topology diverged:\n" + "\n".join(diffs)

    # linear chains
    def test_linear_5(self):
        self._assert_identical(build_linear_chain(5)[0])

    def test_linear_10(self):
        self._assert_identical(build_linear_chain(10)[0])

    def test_linear_50(self):
        self._assert_identical(build_linear_chain(50)[0])

    def test_linear_100(self):
        self._assert_identical(build_linear_chain(100)[0])

    def test_linear_200(self):
        self._assert_identical(build_linear_chain(200)[0])

    # fan-out
    def test_fan_out_3x3(self):
        self._assert_identical(build_wide_fan_out(3, 3)[0])

    def test_fan_out_4x3(self):
        self._assert_identical(build_wide_fan_out(4, 3)[0])

    def test_fan_out_3x4(self):
        self._assert_identical(build_wide_fan_out(3, 4)[0])

    # diamonds — the hardest case
    def test_diamond_3x2(self):
        self._assert_identical(build_diamond(3, 2)[0])

    def test_diamond_4x3(self):
        self._assert_identical(build_diamond(4, 3)[0])

    def test_diamond_5x4(self):
        self._assert_identical(build_diamond(5, 4)[0])

    def test_diamond_5x5(self):
        self._assert_identical(build_diamond(5, 5)[0])

    def test_diamond_6x3(self):
        self._assert_identical(build_diamond(6, 3)[0])

    # random DAGs with various densities
    def test_random_20_p30(self):
        self._assert_identical(build_random_dag(20, 0.3, seed=1)[0])

    def test_random_30_p20(self):
        self._assert_identical(build_random_dag(30, 0.2, seed=42)[0])

    def test_random_50_p15(self):
        self._assert_identical(build_random_dag(50, 0.15, seed=42)[0])

    def test_random_50_p10(self):
        self._assert_identical(build_random_dag(50, 0.10, seed=42)[0])

    def test_random_100_p05(self):
        self._assert_identical(build_random_dag(100, 0.05, seed=42)[0])

    def test_random_different_seeds(self):
        for seed in [7, 13, 99, 256, 1024]:
            self._assert_identical(build_random_dag(30, 0.2, seed=seed)[0])

    # parallel chains
    def test_parallel_3x5(self):
        self._assert_identical(build_parallel_chains(3, 5)[0])

    def test_parallel_5x20(self):
        self._assert_identical(build_parallel_chains(5, 20)[0])

    def test_parallel_10x10(self):
        self._assert_identical(build_parallel_chains(10, 10)[0])

    # hourglass
    def test_hourglass_5_5_1(self):
        self._assert_identical(build_hourglass(5, 5, 1)[0])

    def test_hourglass_10_10_2(self):
        self._assert_identical(build_hourglass(10, 10, 2)[0])

    def test_hourglass_15_15_2(self):
        self._assert_identical(build_hourglass(15, 15, 2)[0])

    # dual topology
    def test_diamond_4x3_dual(self):
        self._assert_identical(build_diamond(4, 3, topology_count=2)[0])

    def test_diamond_5x4_dual(self):
        self._assert_identical(build_diamond(5, 4, topology_count=2)[0])

    def test_linear_50_dual(self):
        self._assert_identical(build_linear_chain(50, topology_count=2)[0])

    def test_random_30_p20_dual(self):
        self._assert_identical(build_random_dag(30, 0.2, seed=42, topology_count=2)[0])

    # edge cases
    def test_single_node(self):
        graph = DaggerGraph()
        graph.add_node(DaggerNode())
        self._assert_identical(graph)

    def test_two_disconnected_nodes(self):
        graph = DaggerGraph()
        graph.add_node(DaggerNode())
        graph.add_node(DaggerNode())
        self._assert_identical(graph)

    def test_empty_graph(self):
        graph = DaggerGraph()
        self._assert_identical(graph)
