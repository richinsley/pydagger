"""Tests for DaggerNode and DaggerGraph — ported from daggerlib test/test.js."""
import pytest
from pydagger import (
    DaggerGraph,
    DaggerNode,
    DaggerInputPin,
    DaggerOutputPin,
)


class SingleConnectOutputPin(DaggerOutputPin):
    """An output pin that does not allow multi-connect."""

    @property
    def allow_multi_connect(self):
        return False


class TestNode(DaggerNode):
    """Node with 2 inputs and 2 outputs per topology (mirrors JS DaggerTestNode)."""

    def __init__(self):
        super().__init__()
        for t in range(2):
            self.input_pins(t).add_pin(DaggerInputPin(), "ip1")
            self.input_pins(t).add_pin(DaggerInputPin(), "ip2")
            self.output_pins(t).add_pin(DaggerOutputPin(), "op1")
            self.output_pins(t).add_pin(SingleConnectOutputPin(), "op2")


# ---------------------------------------------------------------------------
# Node basics
# ---------------------------------------------------------------------------

class TestDaggerNode:
    def test_pin_collections_exist(self):
        node = TestNode()
        assert node.input_pins(0) is not None
        assert node.output_pins(0) is not None
        assert node.input_pins(1) is not None
        assert node.output_pins(1) is not None

    def test_default_name(self):
        node = DaggerNode()
        assert node.name == "DaggerNode"

    def test_name_change_emits_signal(self):
        node = DaggerNode()
        names = []
        node.name_changed.connect(lambda n: names.append(n))
        node.name = "Foo"
        assert names == ["Foo"]

    def test_is_true_source_no_input_pins(self):
        node = DaggerNode()
        assert node.is_true_source(0) is True

    def test_is_true_dest_no_output_pins(self):
        node = DaggerNode()
        assert node.is_true_dest(0) is True


# ---------------------------------------------------------------------------
# Simple topology (single topology system) — mirrors JS "Simple Topology Test"
# ---------------------------------------------------------------------------

class TestSimpleTopology:
    def test_initial_subgraph_count(self):
        graph = DaggerGraph()
        for _ in range(4):
            graph.add_node(TestNode())
        assert graph.sub_graph_count(0) == 4

    def test_connect_reduces_subgraph_count(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        graph.add_node(TestNode())
        graph.add_node(TestNode())

        op1 = n1.get_output_pin("op1", 0)
        ip1 = n2.get_input_pin("ip1", 0)
        assert op1 is not None
        assert ip1 is not None
        assert op1.connect_to_input(ip1) is True
        assert graph.sub_graph_count(0) == 3

    def test_fan_out_reduces_subgraph(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        graph.add_node(TestNode())

        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        assert n1.get_output_pin("op1", 0).connect_to_input(n3.get_input_pin("ip1", 0)) is True
        assert graph.sub_graph_count(0) == 2

    def test_cycle_prevention(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        # n2 -> n1 would create a cycle
        assert n2.get_output_pin("op1", 0).connect_to_input(n1.get_input_pin("ip1", 0)) is False

    def test_disconnect_increases_subgraph(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())

        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n1.get_output_pin("op1", 0).connect_to_input(n3.get_input_pin("ip1", 0))
        assert graph.sub_graph_count(0) == 1

        assert n1.get_output_pin("op1", 0).disconnect_pin(n2.get_input_pin("ip1", 0)) is True
        assert graph.sub_graph_count(0) == 2

    def test_no_multi_connect(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n4 = graph.add_node(TestNode())
        n1.get_output_pin("op2", 0).connect_to_input(n4.get_input_pin("ip1", 0))
        assert n1.get_output_pin("op2", 0).connect_to_input(n4.get_input_pin("ip2", 0)) is False

    def test_remove_node(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        n4 = graph.add_node(TestNode())
        n1.get_output_pin("op2", 0).connect_to_input(n4.get_input_pin("ip1", 0))
        assert graph.remove_node(n4) is True
        assert len(graph.nodes) == 3


# ---------------------------------------------------------------------------
# Dual topology — mirrors JS "Create a graph with two topology systems"
# ---------------------------------------------------------------------------

class TestDualTopology:
    @pytest.fixture()
    def setup(self):
        graph = DaggerGraph(topology_count=2)
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        n4 = graph.add_node(TestNode())
        return graph, n1, n2, n3, n4

    def test_connect_topology_0(self, setup):
        graph, n1, n2, n3, n4 = setup
        assert n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0)) is True

    def test_connect_topology_1(self, setup):
        graph, n1, n2, n3, n4 = setup
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        assert n2.get_output_pin("op1", 1).connect_to_input(n3.get_input_pin("ip1", 1)) is True

    def test_ordinals_across_topologies(self, setup):
        graph, n1, n2, n3, n4 = setup
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 1).connect_to_input(n3.get_input_pin("ip1", 1))
        n3.get_output_pin("op1", 1).connect_to_input(n4.get_input_pin("ip1", 1))

        assert graph.sub_graph_count(0) == 3
        assert graph.sub_graph_count(1) == 2

        assert n1.ordinal(0) == 0
        assert n1.ordinal(1) == 0
        assert n2.ordinal(0) == 1
        assert n2.ordinal(1) == 0
        assert n3.ordinal(0) == 0
        assert n3.ordinal(1) == 1
        assert n4.ordinal(0) == 0
        assert n4.ordinal(1) == 2

    def test_acyclic_failure_topology_1(self, setup):
        graph, n1, n2, n3, n4 = setup
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 1).connect_to_input(n3.get_input_pin("ip1", 1))
        n3.get_output_pin("op1", 1).connect_to_input(n4.get_input_pin("ip1", 1))
        # n4 -> n2 on topology 1 would create cycle
        assert n4.get_output_pin("op1", 1).connect_to_input(n2.get_input_pin("ip1", 1)) is False

    def test_cross_topology_non_cycle(self, setup):
        graph, n1, n2, n3, n4 = setup
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 1).connect_to_input(n3.get_input_pin("ip1", 1))
        n3.get_output_pin("op1", 1).connect_to_input(n4.get_input_pin("ip1", 1))
        # n4 -> n1 on topology 1 is fine (different topology)
        assert n4.get_output_pin("op1", 1).connect_to_input(n1.get_input_pin("ip1", 1)) is True
        assert n1.ordinal(1) == 3
        assert graph.sub_graph_count(1) == 1

    def test_disconnect_topology_1(self, setup):
        graph, n1, n2, n3, n4 = setup
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 1).connect_to_input(n3.get_input_pin("ip1", 1))
        n3.get_output_pin("op1", 1).connect_to_input(n4.get_input_pin("ip1", 1))
        n4.get_output_pin("op1", 1).connect_to_input(n1.get_input_pin("ip1", 1))

        assert n3.get_output_pin("op1", 1).disconnect_pin(n4.get_input_pin("ip1", 1)) is True
        assert n4.ordinal(1) == 0
        assert graph.sub_graph_count(1) == 2


# ---------------------------------------------------------------------------
# Autoclone — mirrors JS "Autoclone" tests
# ---------------------------------------------------------------------------

class TestAutoclone:
    def test_add_autoclone_pin(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        aclone = DaggerInputPin()
        aclone.set_auto_clone(-1, "pin%")
        n2.input_pins(0).add_pin(aclone, "pin%")
        assert len(n2.input_pins(0).all_pins) == 3  # ip1, ip2, pin%

    def test_clone_on_connect(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        aclone = DaggerInputPin()
        aclone.set_auto_clone(-1, "pin%")
        n2.input_pins(0).add_pin(aclone, "pin%")

        p1 = n1.get_output_pin("op1", 0)
        p2 = n2.get_input_pin("pin%", 0)
        assert p1.connect_to_input(p2) is True
        assert len(n2.input_pins(0).all_pins) == 4  # cloned pin added

    def test_remove_clone_on_disconnect(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        aclone = DaggerInputPin()
        aclone.set_auto_clone(-1, "pin%")
        n2.input_pins(0).add_pin(aclone, "pin%")

        p1 = n1.get_output_pin("op1", 0)
        p2 = n2.get_input_pin("pin%", 0)
        p1.connect_to_input(p2)
        assert p2.disconnect_pin() is True
        assert len(n2.input_pins(0).all_pins) == 3  # clone removed


# ---------------------------------------------------------------------------
# Graph signals
# ---------------------------------------------------------------------------

class TestGraphSignals:
    def test_node_added_signal(self):
        graph = DaggerGraph()
        added = []
        graph.node_added.connect(lambda n: added.append(n))
        node = graph.add_node(TestNode())
        assert len(added) == 1
        assert added[0] is node

    def test_pins_connected_signal(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        connected = []
        graph.pins_connected.connect(lambda o, i: connected.append((o, i)))
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        assert len(connected) == 1

    def test_topology_changed_signal(self):
        graph = DaggerGraph()
        changed = []
        graph.topology_changed.connect(lambda: changed.append(True))
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        assert len(changed) >= 1


# ---------------------------------------------------------------------------
# Graph queries
# ---------------------------------------------------------------------------

class TestGraphQueries:
    def test_top_level_nodes(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        top = graph.top_level_nodes(0)
        assert n1 in top
        assert n2 not in top

    def test_bottom_level_nodes(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        bottom = graph.bottom_level_nodes(0)
        assert n2 in bottom
        assert n1 not in bottom

    def test_get_nodes_with_name(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n1.name = "Foo"
        n2 = graph.add_node(TestNode())
        n2.name = "Foo"
        assert len(graph.get_nodes_with_name("Foo")) == 2

    def test_get_node_with_instance_id(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        found = graph.get_node_with_instance_id(n1.instance_id)
        assert found is n1

    def test_max_ordinal(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 0).connect_to_input(n3.get_input_pin("ip1", 0))
        assert graph.max_ordinal(0) == 2

    def test_descendents(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 0).connect_to_input(n3.get_input_pin("ip1", 0))
        desc = n1.descendents(0)
        assert n2 in desc
        assert n3 in desc

    def test_ascendents(self):
        graph = DaggerGraph()
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        n3 = graph.add_node(TestNode())
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        n2.get_output_pin("op1", 0).connect_to_input(n3.get_input_pin("ip1", 0))
        asc = n3.ascendents(0)
        assert n1 in asc
        assert n2 in asc

    def test_enable_topology_toggle(self):
        graph = DaggerGraph()
        graph.enable_topology = False
        n1 = graph.add_node(TestNode())
        n2 = graph.add_node(TestNode())
        # with topology disabled, even cycles should "connect" (no enforcement)
        n1.get_output_pin("op1", 0).connect_to_input(n2.get_input_pin("ip1", 0))
        # re-enable triggers recalculation
        graph.enable_topology = True
