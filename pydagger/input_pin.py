"""Directed input pin.

A :class:`DaggerInputPin` accepts at most **one** incoming connection from
a :class:`~pydagger.output_pin.DaggerOutputPin`.  This single-connection
constraint enforces a clear point of causality for each input.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base_pin import DaggerBasePin, PinDirection

if TYPE_CHECKING:
    from .output_pin import DaggerOutputPin


class DaggerInputPin(DaggerBasePin):
    """An input connection point on a node.

    At most one :class:`~pydagger.output_pin.DaggerOutputPin` may be
    connected to this pin at any time.  Attempting to connect a second
    output will first disconnect the existing one (unless the pin is an
    auto-clone, in which case the connection is refused).
    """

    def __init__(self):
        super().__init__()
        self._connected_to: DaggerOutputPin | None = None

    @property
    def direction(self) -> PinDirection:
        return PinDirection.INPUT

    @property
    def connected_to(self) -> DaggerOutputPin | None:
        """The output pin currently connected to this input, or ``None``."""
        return self._connected_to

    @property
    def is_connected(self) -> bool:
        return self._connected_to is not None

    def can_connect_to_pin(self, pin: DaggerBasePin) -> bool:
        """Test whether *pin* (an output) may connect to this input.

        Checks topology system match, same-node prohibition, and
        acyclicity (the output's parent must not be a descendent of
        this input's parent in the same topology).
        """
        if self.parent is None or pin.parent is None:
            return super().can_connect_to_pin(pin)

        tsystem = self.topology_system
        if tsystem != pin.topology_system:
            return False

        if not self.parent_node:
            return super().can_connect_to_pin(pin)

        if self.parent_node is pin.parent_node:
            return False

        if self._parent_node.parent_graph.enable_topology:
            if pin.parent_node not in self.parent_node.descendents(tsystem):
                return super().can_connect_to_pin(pin)
            elif pin.parent_node.ordinal(tsystem) <= self.parent_node.ordinal(tsystem):
                return super().can_connect_to_pin(pin)
            return False
        else:
            return True

    def disconnect_pin(self, force_disconnect: bool = False) -> bool:
        """Disconnect this input from its connected output.

        Parameters
        ----------
        force_disconnect : bool
            If ``True``, bypass the graph's ``before_pins_disconnected`` check.

        Returns ``True`` if the pin is now disconnected (including if it
        was never connected).
        """
        if self._parent_node is None:
            return False
        if self.is_connected:
            return self._connected_to.disconnect_pin(self, force_disconnect)
        return True

    def purge_all(self) -> None:
        super().purge_all()
        self._connected_to = None
