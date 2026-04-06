"""Directed output pin.

A :class:`DaggerOutputPin` can connect to **multiple**
:class:`~pydagger.input_pin.DaggerInputPin` instances (fan-out), unless
``allow_multi_connect`` is set to ``False``.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base_pin import DaggerBasePin, PinDirection
from .input_pin import DaggerInputPin


class DaggerOutputPin(DaggerBasePin):
    """An output connection point on a node.

    By default an output may fan out to any number of input pins.
    Set :attr:`allow_multi_connect` to ``False`` to restrict it to one.
    """

    def __init__(self):
        super().__init__()
        self._connected_to: list[DaggerInputPin] = []
        self._allow_multi_connect: bool = True

    @property
    def direction(self) -> PinDirection:
        return PinDirection.OUTPUT

    @property
    def connected_to(self) -> list[DaggerInputPin]:
        """List of input pins this output is currently connected to (copy)."""
        return list(self._connected_to)

    @property
    def allow_multi_connect(self) -> bool:
        """Whether this output may connect to more than one input."""
        return self._allow_multi_connect

    @allow_multi_connect.setter
    def allow_multi_connect(self, val: bool) -> None:
        self._allow_multi_connect = val

    @property
    def is_connected(self) -> bool:
        return len(self._connected_to) != 0

    @property
    def connected_to_uuids(self) -> list[str]:
        """Instance IDs of all connected input pins."""
        return [p.instance_id for p in self._connected_to]

    def connect_to_input(self, inp: DaggerInputPin) -> bool:
        """Connect this output to the given input pin.

        Validates that both pins belong to the same graph, checks
        acyclicity within the topology, and fires signals on success.

        Returns ``True`` if the connection was made.
        """
        if inp is None:
            return False

        output_container = self._parent_node.parent_graph
        input_container = inp.parent_node.parent_graph

        if output_container is None or input_container is None:
            return False

        if input_container is not output_container:
            return False

        if self._parent_node.parent_graph.enable_topology:
            if not inp.can_connect_to_pin(self):
                return False
            if not self.can_connect_to_pin(inp):
                return False

        if inp.is_connected:
            if inp.auto_clone_master:
                return False
            if not inp.disconnect_pin(False):
                return False

        if output_container.before_pins_connected(self, inp):
            self._connected_to.append(inp)
            inp._connected_to = self

            output_container.on_pins_connected(self, inp)

            self.pin_connected.emit(inp)
            inp.pin_connected.emit(self)

            output_container.after_pins_connected(self, inp)
            return True

        return False

    def can_connect_to_pin(self, pin: DaggerBasePin) -> bool:
        """Test whether this output may connect to *pin* (an input).

        Checks type, topology match, multi-connect limits, and acyclicity.
        """
        if not isinstance(pin, DaggerInputPin):
            return False

        if self.parent is None or pin.parent is None:
            return super().can_connect_to_pin(pin)

        mtop = self.topology_system
        if mtop != pin.topology_system:
            return False

        if pin.is_connected:
            return False

        if not self.allow_multi_connect and self.is_connected:
            return False

        if pin.parent_node not in self.parent_node.descendents(mtop):
            return super().can_connect_to_pin(pin)
        elif pin.parent_node.ordinal(mtop) >= self.parent_node.ordinal(mtop):
            return super().can_connect_to_pin(pin)

        return False

    def disconnect_pin(self, ipin: DaggerInputPin, force_disconnect: bool = False) -> bool:
        """Disconnect this output from the given input pin.

        Returns ``True`` if the pins are now disconnected (including if
        they were never connected).
        """
        parent_graph = self.parent_node.parent_graph
        if not parent_graph:
            return False

        if ipin in self._connected_to:
            if force_disconnect or parent_graph.before_pins_disconnected(self, ipin):
                self._connected_to.remove(ipin)
                ipin._connected_to = None

                parent_graph.on_pins_disconnected(self, ipin)

                self.pin_disconnected.emit(ipin)
                ipin.pin_disconnected.emit(self)

                parent_graph.after_pins_disconnected(self, ipin)
                return True
            else:
                return False
        else:
            return True

    def disconnect_all(self, force_disconnect: bool = False) -> bool:
        """Disconnect this output from every connected input pin."""
        for pin in reversed(list(self._connected_to)):
            if not pin.disconnect_pin(force_disconnect):
                return False
        return True

    def purge_all(self) -> None:
        super().purge_all()
        self._connected_to = []
