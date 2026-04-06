"""DAG container with topology calculation.

:class:`DaggerGraph` is the main entry point for pydagger.  It holds a
collection of :class:`~pydagger.node.DaggerNode` instances and
automatically computes a layered topological ordering whenever the
graph's structure changes.

The topology calculation produces three results **per topology system**:

* **Ordinals** — the causal depth of each node (longest path from any root).
  Nodes at the same ordinal are independent and may run in parallel.
* **Descendents** — the transitive closure of reachable nodes from each
  node, sorted by ordinal.
* **Subgraph affiliations** — connected-component membership, so
  independent subgraphs can be identified and processed separately.

Multiple topology systems
-------------------------
A single graph can maintain up to ``MAX_TOPOLOGY_COUNT`` independent
topologies.  Each topology has its own set of pins, connections, ordinals,
descendents, and subgraphs.  This allows patterns like:

* **Topology 0** — execution order (frame processing pipeline)
* **Topology 1** — parameter feedback (computed values flowing "backwards"
  to adjust future frames)

Connections on topology 1 that would be cycles on topology 0 are perfectly
valid, because each topology enforces acyclicity independently.
"""

from __future__ import annotations
from collections import deque

from .base import DaggerBase
from .base_pin import DaggerBasePin
from .signal import Signal
from .node import DaggerNode
from .types import MAX_TOPOLOGY_COUNT


class _UnionFind:
    """Disjoint-set / union-find for subgraph computation."""

    __slots__ = ("_parent", "_rank")

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = {}

    def make_set(self, x: int) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: int) -> int:
        r = x
        while self._parent[r] != r:
            r = self._parent[r]
        while self._parent[x] != r:
            self._parent[x], x = r, self._parent[x]
        return r

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


class DaggerGraph(DaggerBase):
    """A directed acyclic graph with automatic layered topological ordering.

    Parameters
    ----------
    topology_count : int
        Number of independent topology systems (default 1, max
        ``MAX_TOPOLOGY_COUNT``).

    Signals
    -------
    node_added(node)
        Emitted after a node is added.
    node_removed(node_id)
        Emitted after a node is removed.
    pins_connected(output_pin, input_pin)
        Emitted after two pins are connected.
    pins_disconnected(output_id, input_id)
        Emitted after two pins are disconnected.
    topology_changed()
        Emitted after any topology recalculation.
    """

    def __init__(self, topology_count: int = 1):
        super().__init__()
        self._nodes: list[DaggerNode] = []
        self._sub_graph_count: list[int] = [0] * MAX_TOPOLOGY_COUNT
        self._max_ordinal: list[int] = [0] * MAX_TOPOLOGY_COUNT
        self._topology_count: int = topology_count
        self._topology_enabled: bool = True

        self.pins_disconnected = Signal()
        self.pins_connected = Signal()
        self.node_removed = Signal()
        self.node_added = Signal()
        self.topology_changed = Signal()

        self.calculate_topology()

    # -- topology control ----------------------------------------------------

    @property
    def enable_topology(self) -> bool:
        """When ``False``, acyclicity is not enforced and ordinals are not computed."""
        return self._topology_enabled

    @enable_topology.setter
    def enable_topology(self, enabled: bool) -> None:
        if enabled == self._topology_enabled:
            return
        self._topology_enabled = enabled
        self.calculate_topology()

    def calculate_topology(self) -> None:
        """Recompute ordinals, descendents, and subgraphs for all topologies.

        Called automatically whenever the graph structure changes (nodes
        added/removed, pins connected/disconnected).  Can also be called
        manually after batch modifications.

        The algorithm runs three passes per topology:

        1. **Kahn's BFS** — computes ordinals as the longest path from any
           root to each node.  O(N + E).
        2. **Reverse-topological sweep** — computes descendent sets bottom-up
           so each node is processed exactly once.  O(N + E + total desc size).
        3. **Union-find** — computes connected components for subgraph
           affiliation.  O(N * alpha(N)).
        """
        if not self._topology_enabled:
            return

        nodes = self._nodes
        n_nodes = len(nodes)

        for t in range(self._topology_count):

            # --- reset --------------------------------------------------
            for node in nodes:
                node._ordinal[t] = -1
                node._subgraph_affiliation[t] = -1
                node._descendents[t] = []

            if n_nodes == 0:
                self._max_ordinal[t] = 0
                self._sub_graph_count[t] = 0
                continue

            # --- build adjacency ----------------------------------------
            children: dict[int, list[int]] = {}
            parents: dict[int, list[int]] = {}
            in_degree: dict[int, int] = {}

            for node in nodes:
                nid = id(node)
                children[nid] = []
                if nid not in parents:
                    parents[nid] = []
                in_degree[nid] = 0

            for node in nodes:
                nid = id(node)
                for opin in node._output_pins[t]._ordered_collection:
                    for ipin in opin._connected_to:
                        child = ipin._parent_node
                        if child is not None:
                            cid = id(child)
                            children[nid].append(cid)
                            parents[cid].append(nid)
                            in_degree[cid] += 1

            # --- Pass 1: ordinals via Kahn's BFS -----------------------
            node_by_id: dict[int, DaggerNode] = {id(n): n for n in nodes}
            queue: deque[int] = deque()

            for node in nodes:
                nid = id(node)
                if in_degree[nid] == 0:
                    node._ordinal[t] = 0
                    queue.append(nid)

            max_ord = 0
            topo_order: list[int] = []

            while queue:
                nid = queue.popleft()
                topo_order.append(nid)
                node = node_by_id[nid]
                cur_ord = node._ordinal[t]
                if cur_ord > max_ord:
                    max_ord = cur_ord

                for cid in children[nid]:
                    child = node_by_id[cid]
                    new_ord = cur_ord + 1
                    if new_ord > child._ordinal[t]:
                        child._ordinal[t] = new_ord
                    in_degree[cid] -= 1
                    if in_degree[cid] == 0:
                        queue.append(cid)

            self._max_ordinal[t] = max_ord

            # --- Pass 2: descendents via reverse topological order ------
            desc_sets: dict[int, set[int]] = {}

            for nid in reversed(topo_order):
                my_desc: set[int] = set()
                for cid in children[nid]:
                    my_desc.add(cid)
                    my_desc |= desc_sets[cid]
                desc_sets[nid] = my_desc

            for nid in topo_order:
                node = node_by_id[nid]
                ds = desc_sets.get(nid)
                if ds:
                    desc_list = [node_by_id[did] for did in ds]
                    desc_list.sort(key=lambda n: n._ordinal[t])
                    node._descendents[t] = desc_list
                else:
                    node._descendents[t] = []

            # --- Pass 3: subgraph affiliation via union-find -----------
            uf = _UnionFind()
            for node in nodes:
                uf.make_set(id(node))

            for node in nodes:
                nid = id(node)
                for cid in children[nid]:
                    uf.union(nid, cid)

            root_to_index: dict[int, int] = {}
            next_index = 0
            for node in nodes:
                root = uf.find(id(node))
                if root not in root_to_index:
                    root_to_index[root] = next_index
                    next_index += 1
                node._subgraph_affiliation[t] = root_to_index[root]

            self._sub_graph_count[t] = next_index

        self.graph_topology_changed()
        self.topology_changed.emit()

    # -- node queries --------------------------------------------------------

    @property
    def nodes(self) -> list[DaggerNode]:
        """All nodes in the graph (copy)."""
        return list(self._nodes)

    def max_ordinal(self, topology_system: int = 0) -> int:
        """The highest ordinal value in the given topology."""
        return self._max_ordinal[topology_system]

    def sub_graph_count(self, topology_system: int = 0) -> int:
        """Number of connected components in the given topology."""
        return self._sub_graph_count[topology_system]

    def top_level_nodes(self, topology_system: int = 0) -> list[DaggerNode]:
        """Nodes with no connected inputs (ordinal 0) in the given topology."""
        return [n for n in self._nodes if n.is_top_level(topology_system)]

    def bottom_level_nodes(self, topology_system: int = 0) -> list[DaggerNode]:
        """Nodes with no connected outputs in the given topology."""
        return [n for n in self._nodes if n.is_bottom_level(topology_system)]

    def get_sub_graph_nodes(self, index: int, topology_system: int = 0) -> list[DaggerNode]:
        """All nodes belonging to subgraph *index* in the given topology."""
        if index > self._sub_graph_count[topology_system] - 1:
            return []
        return [n for n in self._nodes if n.subgraph_affiliation(topology_system) == index]

    def get_sub_graphs(self, topology_system: int = 0) -> list[list[DaggerNode]]:
        """List of all subgraphs, each as a list of nodes."""
        return [
            self.get_sub_graph_nodes(i, topology_system)
            for i in range(self._sub_graph_count[topology_system])
        ]

    def get_nodes_with_name(self, name: str) -> list[DaggerNode]:
        """All nodes with the given name."""
        return [n for n in self._nodes if n.name == name]

    def get_node_with_instance_id(self, node_id: str) -> DaggerNode | None:
        """Find a node by its unique instance ID."""
        for n in self._nodes:
            if n.instance_id == node_id:
                return n
        return None

    def all_connections(self, topology_system: int = 0) -> list:
        """All connected input pins in the given topology."""
        retv = []
        for node in self._nodes:
            for pin in node.input_pins(topology_system).all_pins:
                if pin and pin.is_connected:
                    retv.append(pin)
        return retv

    # -- node mutation -------------------------------------------------------

    def add_node(self, node: DaggerNode, calculate: bool = False) -> DaggerNode | None:
        """Add a node to the graph.

        Parameters
        ----------
        node : DaggerNode
            Must not already belong to a graph.
        calculate : bool
            If ``True``, run a full topology recalculation immediately.
            The default (``False``) uses a fast path that assigns the node
            ordinal 0 and a new subgraph — suitable when adding nodes
            before any connections are made.

        Returns the node on success, or ``None`` if it already belongs
        to a graph.
        """
        if node.parent_graph is not None:
            return None

        node.before_added_to_graph.emit()
        node._parent_graph = self
        self._nodes.append(node)

        if calculate:
            self.calculate_topology()
        else:
            for t in range(self._topology_count):
                node._subgraph_affiliation[t] = self._sub_graph_count[t]
                self._sub_graph_count[t] += 1
                node._ordinal[t] = 0
                node._descendents[t] = []

        self.node_added.emit(node)
        node.added_to_graph()
        node.after_added_to_graph.emit()
        return node

    def add_nodes(self, nodes: list[DaggerNode]) -> list[DaggerNode] | None:
        """Add multiple nodes and recalculate topology once.

        Returns ``None`` if any node already belongs to a graph (no nodes
        are added in that case).
        """
        for node in nodes:
            if node.parent_graph is not None:
                return None

        for node in nodes:
            node.before_added_to_graph.emit()
            node._parent_graph = self
            self._nodes.append(node)
            self.node_added.emit(node)
            node.added_to_graph()
            node.after_added_to_graph.emit()

        self.calculate_topology()
        return nodes

    def remove_node(self, node: DaggerNode) -> bool:
        """Remove a node, disconnecting all its pins first.

        Returns ``False`` if the node is ``None``, if
        :meth:`before_node_removed` vetoes it, or if any pin fails to
        disconnect.
        """
        if not node:
            return False
        if self.before_node_removed(node):
            if not node.disconnect_all_pins():
                return False
            self._nodes.remove(node)
            node.purge_all()
            self.node_removed.emit(node.instance_id)
            node._parent_graph = None
            self.calculate_topology()
            return True
        return False

    # -- hooks (override in subclasses) --------------------------------------

    def before_node_removed(self, node: DaggerNode) -> bool:
        """Return ``False`` to veto node removal."""
        return True

    def before_pins_connected(self, connect_from: DaggerBasePin, connect_to: DaggerBasePin) -> bool:
        """Return ``False`` to veto a pending connection."""
        return True

    def after_pins_connected(self, connect_from: DaggerBasePin, connect_to: DaggerBasePin) -> None:
        """Called after pins connect.  Triggers auto-cloning if applicable."""
        if connect_from.parent_node.should_clone_pin(connect_from):
            connect_from.parent_node.clone_pin(connect_from)
        if connect_to.parent_node.should_clone_pin(connect_to):
            connect_to.parent_node.clone_pin(connect_to)

    def before_pins_disconnected(self, connect_from: DaggerBasePin, connect_to: DaggerBasePin) -> bool:
        """Return ``False`` to veto a pending disconnection."""
        return True

    def after_pins_disconnected(self, connect_from: DaggerBasePin, connect_to: DaggerBasePin) -> None:
        """Called after pins disconnect.  Removes auto-cloned pins if applicable."""
        if connect_from.parent_node.should_remove_clone_pin(connect_from):
            connect_from.parent_node.remove_clone_pin(connect_from)
        if connect_to.parent_node.should_remove_clone_pin(connect_to):
            connect_to.parent_node.remove_clone_pin(connect_to)

    def on_pins_disconnected(self, disconnect_output: DaggerBasePin, disconnect_input: DaggerBasePin) -> None:
        """Internal: recalculate topology and emit signal after disconnection."""
        self.calculate_topology()
        self.pins_disconnected.emit(disconnect_output.instance_id, disconnect_input.instance_id)

    def on_pins_connected(self, connect_from: DaggerBasePin, connect_to: DaggerBasePin) -> None:
        """Internal: recalculate topology and emit signal after connection."""
        self.calculate_topology()
        self.pins_connected.emit(connect_from, connect_to)

    def graph_topology_changed(self) -> None:
        """Hook called after topology recalculation.  Override in subclasses."""
        pass
