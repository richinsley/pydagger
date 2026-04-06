"""Graph node (vertex).

A :class:`DaggerNode` is the fundamental unit of a
:class:`~pydagger.graph.DaggerGraph`.  Each node holds separate
input/output :class:`~pydagger.pin_collection.DaggerPinCollection`
instances **per topology system**, allowing the same node to participate
in multiple independent topological orderings simultaneously.

Subclass ``DaggerNode`` and add pins in ``__init__`` to define custom
node types::

    class BlurNode(DaggerNode):
        def __init__(self):
            super().__init__()
            self.input_pins(0).add_pin(DaggerInputPin(), "image")
            self.output_pins(0).add_pin(DaggerOutputPin(), "result")
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import DaggerBase
from .base_pin import DaggerBasePin, PinDirection
from .signal import Signal
from .pin_collection import DaggerPinCollection
from .types import MAX_TOPOLOGY_COUNT

if TYPE_CHECKING:
    from .graph import DaggerGraph


class DaggerNode(DaggerBase):
    """A vertex in a Dagger graph.

    Signals
    -------
    before_added_to_graph()
        Emitted just before the node is added to a graph.
    after_added_to_graph()
        Emitted just after the node is added to a graph.
    pin_cloned(cloned_pin)
        Emitted when a pin is auto-cloned on this node.
    name_changed(new_name)
        Emitted when :attr:`name` is set.
    """

    def __init__(self):
        super().__init__()
        self._current_t_system_eval: int = -1
        self._name: str = "DaggerNode"
        self._parent_graph: DaggerGraph | None = None

        self._descendents: list[list[DaggerNode]] = [[] for _ in range(MAX_TOPOLOGY_COUNT)]
        self._subgraph_affiliation: list[int] = [-1] * MAX_TOPOLOGY_COUNT
        self._ordinal: list[int] = [-1] * MAX_TOPOLOGY_COUNT
        self._input_pins: list[DaggerPinCollection] = []
        self._output_pins: list[DaggerPinCollection] = []

        self.after_added_to_graph = Signal()
        self.before_added_to_graph = Signal()
        self.pin_cloned = Signal()
        self.name_changed = Signal()

        for i in range(MAX_TOPOLOGY_COUNT):
            self._input_pins.append(DaggerPinCollection(self, PinDirection.INPUT, i))
            self._output_pins.append(DaggerPinCollection(self, PinDirection.OUTPUT, i))

    # -- graph membership ----------------------------------------------------

    @property
    def parent_graph(self) -> DaggerGraph | None:
        """The graph this node belongs to, or ``None``."""
        return self._parent_graph

    # -- topology queries ----------------------------------------------------

    def ordinal(self, topology_system: int = 0) -> int:
        """The causal depth of this node in the given topology.

        Ordinal 0 means this is a root (top-level) node.  Higher values
        indicate deeper causality — a node at ordinal *n* depends (directly
        or transitively) on at least one node at every ordinal 0 .. *n*-1.

        Nodes at the **same ordinal** are independent of each other and
        may be processed in parallel.
        """
        return self._ordinal[topology_system]

    def subgraph_affiliation(self, topology_system: int = 0) -> int:
        """Index of the connected component this node belongs to."""
        return self._subgraph_affiliation[topology_system]

    def descendents(self, topology_system: int = 0) -> list[DaggerNode]:
        """All nodes reachable from this node, sorted by ordinal.

        The list is a copy — modifying it does not affect the graph.
        """
        return list(self._descendents[topology_system])

    def ascendents(self, topology_system: int = 0) -> list[DaggerNode]:
        """All nodes from which this node is reachable."""
        if not self._parent_graph:
            return []
        return [
            n for n in self._parent_graph.nodes
            if n is not self and self in n.descendents(topology_system)
        ]

    def is_top_level(self, topology_system: int = 0) -> bool:
        """``True`` if this node has no connected input pins in the topology."""
        for ipin in self._input_pins[topology_system].all_pins:
            if ipin.is_connected:
                if ipin.connected_to.parent_node is not None:
                    return False
        return True

    def is_bottom_level(self, topology_system: int = 0) -> bool:
        """``True`` if this node has no connected output pins in the topology."""
        for opin in self._output_pins[topology_system].all_pins:
            if opin.is_connected:
                return False
        return True

    def is_true_source(self, topology_system: int = 0) -> bool:
        """``True`` if this node has **no input pins at all** (not just unconnected)."""
        return len(self._input_pins[topology_system].all_pins) == 0

    def is_true_dest(self, topology_system: int = 0) -> bool:
        """``True`` if this node has **no output pins at all**."""
        return len(self._output_pins[topology_system].all_pins) == 0

    # -- naming --------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable name for this node."""
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        self._name = new_name
        self.name_changed.emit(new_name)

    # -- pin access ----------------------------------------------------------

    def input_pins(self, topology_system: int = 0) -> DaggerPinCollection:
        """Input pin collection for the given topology."""
        return self._input_pins[topology_system]

    def output_pins(self, topology_system: int = 0) -> DaggerPinCollection:
        """Output pin collection for the given topology."""
        return self._output_pins[topology_system]

    def get_output_pin(self, name: str, topology_system: int = 0) -> DaggerBasePin | None:
        """Find an output pin by name."""
        return self._output_pins[topology_system].pin(name)

    def get_input_pin(self, name: str, topology_system: int = 0) -> DaggerBasePin | None:
        """Find an input pin by name."""
        return self._input_pins[topology_system].pin(name)

    def disconnect_all_pins(self) -> bool:
        """Disconnect every pin on this node across all topologies."""
        for i in range(self._parent_graph._topology_count):
            for opin in reversed(self._output_pins[i].all_pins):
                if not opin.disconnect_all(False):
                    return False
            for ipin in reversed(self._input_pins[i].all_pins):
                if not ipin.disconnect_pin(False):
                    return False
        return True

    # -- auto-clone management -----------------------------------------------

    def should_clone_pin(self, pin: DaggerBasePin) -> bool:
        """Called after connection to decide whether *pin* should be cloned."""
        if pin.auto_clone_master:
            if pin.is_input_pin:
                to_max = pin.auto_clone_master.max_auto_clone
                if to_max != 0:
                    if to_max == -1 or pin.auto_clone_master.auto_clone_count < to_max:
                        return True
            else:
                if len(pin.connected_to) == 1:
                    to_max = pin.auto_clone_master.max_auto_clone
                    if to_max != 0:
                        if to_max == -1 or pin.auto_clone_master.auto_clone_count < to_max:
                            return True
        return False

    def clone_pin(self, pin: DaggerBasePin, force_auto_clone_master: DaggerBasePin | None = None) -> DaggerBasePin | None:
        """Clone *pin* and add the clone to the same collection."""
        master = force_auto_clone_master or pin.auto_clone_master
        if not master:
            return None

        cloned = master._clone()
        if cloned:
            cloned.cloned(master)
            collection = pin.parent
            if collection.add_pin(cloned, ""):
                self.pin_cloned.emit(cloned)
                cloned.on_cloned()
                return cloned
        return None

    def should_remove_clone_pin(self, pin: DaggerBasePin) -> bool:
        """Called after disconnection to decide whether a clone should be removed."""
        if pin.auto_clone_master:
            return not pin.is_connected
        return False

    def remove_clone_pin(self, pin: DaggerBasePin) -> bool:
        """Remove an auto-cloned pin (or its unconnected sibling)."""
        collection = pin.parent
        if pin.auto_clone_master is not pin:
            return collection.remove_pin(pin)
        else:
            for tpin in collection.all_non_connected_pins:
                if tpin is not pin and tpin.auto_clone_master is pin.auto_clone_master:
                    return collection.remove_pin(tpin)
        return False

    def rename_pin(self, pin: DaggerBasePin, pin_name: str) -> bool:
        """Rename *pin*.  Fails if the pin's ``can_rename`` is ``False``."""
        if not pin.can_rename:
            return False
        return pin.parent.set_pin_name(pin, pin_name)

    def can_remove_pin(self, pin: DaggerBasePin) -> bool:
        """Override to control whether a pin may be removed from this node."""
        return True

    def added_to_graph(self) -> None:
        """Hook called after this node has been added to a graph.  Override in subclasses."""
        pass

    @property
    def current_t_system_eval(self) -> int:
        return self._current_t_system_eval

    @current_t_system_eval.setter
    def current_t_system_eval(self, system: int) -> None:
        self._current_t_system_eval = system

    def purge_all(self) -> None:
        super().purge_all()
        for i in range(MAX_TOPOLOGY_COUNT):
            if self._input_pins[i]:
                self._input_pins[i].purge_all()
            if self._output_pins[i]:
                self._output_pins[i].purge_all()
            self._descendents[i] = []
