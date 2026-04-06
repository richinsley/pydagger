"""Explicit descendent and ascendent verification against hand-computed values.

These tests construct small graphs where the correct descendent/ascendent
sets and their ordering can be verified by inspection.
"""

import pytest
from pydagger import DaggerGraph, DaggerNode, DaggerInputPin, DaggerOutputPin


class SimpleNode(DaggerNode):
    def __init__(self, n_in=1, n_out=1):
        super().__init__()
        for i in range(n_in):
            self.input_pins(0).add_pin(DaggerInputPin(), f"in{i}")
        for i in range(n_out):
            self.output_pins(0).add_pin(DaggerOutputPin(), f"out{i}")


class TestLinearChainDescendents:
    """A -> B -> C -> D

    Descendents:
        A: [B, C, D]  (ordinals 1, 2, 3)
        B: [C, D]     (ordinals 2, 3)
        C: [D]        (ordinal 3)
        D: []

    Ascendents:
        A: []
        B: [A]
        C: [A, B]
        D: [A, B, C]
    """

    @pytest.fixture()
    def chain(self):
        graph = DaggerGraph()
        a = graph.add_node(SimpleNode(0, 1)); a.name = "A"
        b = graph.add_node(SimpleNode(1, 1)); b.name = "B"
        c = graph.add_node(SimpleNode(1, 1)); c.name = "C"
        d = graph.add_node(SimpleNode(1, 0)); d.name = "D"
        a.get_output_pin("out0").connect_to_input(b.get_input_pin("in0"))
        b.get_output_pin("out0").connect_to_input(c.get_input_pin("in0"))
        c.get_output_pin("out0").connect_to_input(d.get_input_pin("in0"))
        return graph, a, b, c, d

    def test_ordinals(self, chain):
        _, a, b, c, d = chain
        assert a.ordinal(0) == 0
        assert b.ordinal(0) == 1
        assert c.ordinal(0) == 2
        assert d.ordinal(0) == 3

    def test_a_descendents(self, chain):
        _, a, b, c, d = chain
        assert a.descendents(0) == [b, c, d]

    def test_b_descendents(self, chain):
        _, a, b, c, d = chain
        assert b.descendents(0) == [c, d]

    def test_c_descendents(self, chain):
        _, a, b, c, d = chain
        assert c.descendents(0) == [d]

    def test_d_descendents(self, chain):
        _, a, b, c, d = chain
        assert d.descendents(0) == []

    def test_a_ascendents(self, chain):
        _, a, b, c, d = chain
        assert a.ascendents(0) == []

    def test_b_ascendents(self, chain):
        _, a, b, c, d = chain
        assert a in b.ascendents(0)
        assert len(b.ascendents(0)) == 1

    def test_c_ascendents(self, chain):
        _, a, b, c, d = chain
        asc = c.ascendents(0)
        assert set(asc) == {a, b}

    def test_d_ascendents(self, chain):
        _, a, b, c, d = chain
        asc = d.ascendents(0)
        assert set(asc) == {a, b, c}


class TestDiamondDescendents:
    """
        A
       / \\
      B   C
       \\ /
        D

    Descendents:
        A: [B, C, D]  (B,C at ordinal 1, D at ordinal 2 — B,C order may vary)
        B: [D]
        C: [D]
        D: []

    Ascendents:
        A: []
        B: [A]
        C: [A]
        D: [A, B, C]
    """

    @pytest.fixture()
    def diamond(self):
        graph = DaggerGraph()
        a = graph.add_node(SimpleNode(0, 2)); a.name = "A"
        b = graph.add_node(SimpleNode(1, 1)); b.name = "B"
        c = graph.add_node(SimpleNode(1, 1)); c.name = "C"
        d = graph.add_node(SimpleNode(2, 0)); d.name = "D"
        a.get_output_pin("out0").connect_to_input(b.get_input_pin("in0"))
        a.get_output_pin("out1").connect_to_input(c.get_input_pin("in0"))
        b.get_output_pin("out0").connect_to_input(d.get_input_pin("in0"))
        c.get_output_pin("out0").connect_to_input(d.get_input_pin("in1"))
        return graph, a, b, c, d

    def test_ordinals(self, diamond):
        _, a, b, c, d = diamond
        assert a.ordinal(0) == 0
        assert b.ordinal(0) == 1
        assert c.ordinal(0) == 1
        assert d.ordinal(0) == 2

    def test_a_descendents_set(self, diamond):
        _, a, b, c, d = diamond
        assert set(a.descendents(0)) == {b, c, d}

    def test_a_descendents_sorted_by_ordinal(self, diamond):
        _, a, b, c, d = diamond
        desc = a.descendents(0)
        # B and C are at ordinal 1, D at ordinal 2
        assert desc[-1] is d
        assert set(desc[:2]) == {b, c}
        # verify sorted by ordinal
        ordinals = [n.ordinal(0) for n in desc]
        assert ordinals == sorted(ordinals)

    def test_b_descendents(self, diamond):
        _, a, b, c, d = diamond
        assert b.descendents(0) == [d]

    def test_c_descendents(self, diamond):
        _, a, b, c, d = diamond
        assert c.descendents(0) == [d]

    def test_d_descendents(self, diamond):
        _, a, b, c, d = diamond
        assert d.descendents(0) == []

    def test_d_ascendents(self, diamond):
        _, a, b, c, d = diamond
        assert set(d.ascendents(0)) == {a, b, c}

    def test_b_ascendents(self, diamond):
        _, a, b, c, d = diamond
        assert b.ascendents(0) == [a]

    def test_c_ascendents(self, diamond):
        _, a, b, c, d = diamond
        assert c.ascendents(0) == [a]


class TestWideConvergence:
    """
      A   B   C
       \\ | /
         D
         |
         E

    Descendents:
        A: [D, E]
        B: [D, E]
        C: [D, E]
        D: [E]
        E: []

    Ordinals: A=0, B=0, C=0, D=1, E=2
    """

    @pytest.fixture()
    def graph(self):
        g = DaggerGraph()
        a = g.add_node(SimpleNode(0, 1)); a.name = "A"
        b = g.add_node(SimpleNode(0, 1)); b.name = "B"
        c = g.add_node(SimpleNode(0, 1)); c.name = "C"
        d = g.add_node(SimpleNode(3, 1)); d.name = "D"
        e = g.add_node(SimpleNode(1, 0)); e.name = "E"
        a.get_output_pin("out0").connect_to_input(d.get_input_pin("in0"))
        b.get_output_pin("out0").connect_to_input(d.get_input_pin("in1"))
        c.get_output_pin("out0").connect_to_input(d.get_input_pin("in2"))
        d.get_output_pin("out0").connect_to_input(e.get_input_pin("in0"))
        return g, a, b, c, d, e

    def test_ordinals(self, graph):
        _, a, b, c, d, e = graph
        assert a.ordinal(0) == 0
        assert b.ordinal(0) == 0
        assert c.ordinal(0) == 0
        assert d.ordinal(0) == 1
        assert e.ordinal(0) == 2

    def test_a_descendents(self, graph):
        _, a, b, c, d, e = graph
        desc = a.descendents(0)
        assert set(desc) == {d, e}
        assert desc == [d, e]  # sorted by ordinal: d=1, e=2

    def test_b_descendents(self, graph):
        _, a, b, c, d, e = graph
        assert b.descendents(0) == [d, e]

    def test_c_descendents(self, graph):
        _, a, b, c, d, e = graph
        assert c.descendents(0) == [d, e]

    def test_d_descendents(self, graph):
        _, a, b, c, d, e = graph
        assert d.descendents(0) == [e]

    def test_e_ascendents(self, graph):
        _, a, b, c, d, e = graph
        assert set(e.ascendents(0)) == {a, b, c, d}


class TestLongestPathOrdinal:
    """Test that ordinals use longest path, not shortest.

       A ----> C
       |       ^
       v       |
       B ------+

    A->B->C gives C ordinal 2.
    A->C gives C ordinal 1.
    Longest path wins: C.ordinal = 2.
    """

    @pytest.fixture()
    def graph(self):
        g = DaggerGraph()
        a = g.add_node(SimpleNode(0, 2)); a.name = "A"
        b = g.add_node(SimpleNode(1, 1)); b.name = "B"
        c = g.add_node(SimpleNode(2, 0)); c.name = "C"
        a.get_output_pin("out0").connect_to_input(b.get_input_pin("in0"))
        b.get_output_pin("out0").connect_to_input(c.get_input_pin("in0"))
        a.get_output_pin("out1").connect_to_input(c.get_input_pin("in1"))
        return g, a, b, c

    def test_ordinals(self, graph):
        _, a, b, c = graph
        assert a.ordinal(0) == 0
        assert b.ordinal(0) == 1
        assert c.ordinal(0) == 2  # longest path, not 1

    def test_a_descendents(self, graph):
        _, a, b, c = graph
        assert a.descendents(0) == [b, c]

    def test_b_descendents(self, graph):
        _, a, b, c = graph
        assert b.descendents(0) == [c]

    def test_c_ascendents(self, graph):
        _, a, b, c = graph
        assert set(c.ascendents(0)) == {a, b}


class TestDisconnectedSubgraphs:
    """Two separate chains: (A->B) and (C->D)

    Each chain's nodes should only have descendents/ascendents within their chain.
    """

    @pytest.fixture()
    def graph(self):
        g = DaggerGraph()
        a = g.add_node(SimpleNode(0, 1)); a.name = "A"
        b = g.add_node(SimpleNode(1, 0)); b.name = "B"
        c = g.add_node(SimpleNode(0, 1)); c.name = "C"
        d = g.add_node(SimpleNode(1, 0)); d.name = "D"
        a.get_output_pin("out0").connect_to_input(b.get_input_pin("in0"))
        c.get_output_pin("out0").connect_to_input(d.get_input_pin("in0"))
        return g, a, b, c, d

    def test_a_descendents_only_b(self, graph):
        _, a, b, c, d = graph
        assert a.descendents(0) == [b]

    def test_c_descendents_only_d(self, graph):
        _, a, b, c, d = graph
        assert c.descendents(0) == [d]

    def test_b_no_descendents(self, graph):
        _, a, b, c, d = graph
        assert b.descendents(0) == []

    def test_d_ascendents_only_c(self, graph):
        _, a, b, c, d = graph
        assert d.ascendents(0) == [c]

    def test_b_ascendents_only_a(self, graph):
        _, a, b, c, d = graph
        assert b.ascendents(0) == [a]

    def test_separate_subgraphs(self, graph):
        g, a, b, c, d = graph
        assert a.subgraph_affiliation(0) == b.subgraph_affiliation(0)
        assert c.subgraph_affiliation(0) == d.subgraph_affiliation(0)
        assert a.subgraph_affiliation(0) != c.subgraph_affiliation(0)


class TestDeepDiamond:
    """
        A
       / \\
      B   C
      |   |
      D   E
       \\ /
        F

    Ordinals: A=0, B=1, C=1, D=2, E=2, F=3
    A.descendents = [B, C, D, E, F] sorted by ordinal
    B.descendents = [D, F]
    C.descendents = [E, F]
    D.descendents = [F]
    E.descendents = [F]
    F.descendents = []
    """

    @pytest.fixture()
    def graph(self):
        g = DaggerGraph()
        a = g.add_node(SimpleNode(0, 2)); a.name = "A"
        b = g.add_node(SimpleNode(1, 1)); b.name = "B"
        c = g.add_node(SimpleNode(1, 1)); c.name = "C"
        d = g.add_node(SimpleNode(1, 1)); d.name = "D"
        e = g.add_node(SimpleNode(1, 1)); e.name = "E"
        f = g.add_node(SimpleNode(2, 0)); f.name = "F"
        a.get_output_pin("out0").connect_to_input(b.get_input_pin("in0"))
        a.get_output_pin("out1").connect_to_input(c.get_input_pin("in0"))
        b.get_output_pin("out0").connect_to_input(d.get_input_pin("in0"))
        c.get_output_pin("out0").connect_to_input(e.get_input_pin("in0"))
        d.get_output_pin("out0").connect_to_input(f.get_input_pin("in0"))
        e.get_output_pin("out0").connect_to_input(f.get_input_pin("in1"))
        return g, a, b, c, d, e, f

    def test_ordinals(self, graph):
        _, a, b, c, d, e, f = graph
        assert a.ordinal(0) == 0
        assert b.ordinal(0) == 1
        assert c.ordinal(0) == 1
        assert d.ordinal(0) == 2
        assert e.ordinal(0) == 2
        assert f.ordinal(0) == 3

    def test_a_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        desc = a.descendents(0)
        assert set(desc) == {b, c, d, e, f}
        ordinals = [n.ordinal(0) for n in desc]
        assert ordinals == sorted(ordinals)

    def test_b_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert set(b.descendents(0)) == {d, f}
        assert b.descendents(0) == [d, f]  # d=2, f=3

    def test_c_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert set(c.descendents(0)) == {e, f}
        assert c.descendents(0) == [e, f]

    def test_d_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert d.descendents(0) == [f]

    def test_e_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert e.descendents(0) == [f]

    def test_f_descendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert f.descendents(0) == []

    def test_f_ascendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert set(f.ascendents(0)) == {a, b, c, d, e}

    def test_d_ascendents(self, graph):
        _, a, b, c, d, e, f = graph
        assert set(d.ascendents(0)) == {a, b}

    def test_single_subgraph(self, graph):
        g, *_ = graph
        assert g.sub_graph_count(0) == 1
