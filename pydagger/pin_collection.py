"""Container for pins of one direction.

Each :class:`~pydagger.node.DaggerNode` has one
:class:`DaggerPinCollection` per direction (input / output) per topology
system.  The collection provides named and indexed access to its pins,
ensures name uniqueness, and emits signals when pins are added or removed.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

from .base import DaggerBase
from .base_pin import DaggerBasePin, PinDirection
from .signal import Signal

if TYPE_CHECKING:
    from .node import DaggerNode


class DaggerPinCollection(DaggerBase):
    """An ordered, named container of pins belonging to a single node.

    Parameters
    ----------
    parent_node : DaggerNode
        The node that owns this collection.
    direction : PinDirection
        Whether this collection holds input or output pins.
    topology_system : int
        The topology index this collection belongs to.

    Signals
    -------
    pin_added(pin)
        Emitted after a pin is added.
    pin_removed(pin_id)
        Emitted after a pin is removed.
    """

    def __init__(self, parent_node: DaggerNode, direction: PinDirection, topology_system: int):
        super().__init__()
        self._direction = direction
        self._parent_node = parent_node
        self._topology_system = topology_system
        self._pin_collection: dict[str, DaggerBasePin] = {}
        self._ordered_collection: list[DaggerBasePin] = []

        self.pin_removed = Signal()
        self.pin_added = Signal()

    @property
    def topology_system(self) -> int:
        """The topology index this collection belongs to."""
        return self._topology_system

    def pin(self, name: str) -> DaggerBasePin | None:
        """Look up a pin by name, or ``None`` if not found."""
        return self._pin_collection.get(name)

    def add_pin(self, pin: DaggerBasePin | None, name: str) -> bool:
        """Add *pin* to the collection with the given *name*.

        If *name* collides with an existing pin, a numeric suffix is
        appended automatically.  Returns ``False`` only if *pin* is
        ``None``.
        """
        if pin is None:
            return False

        pin.parent = self

        if name:
            pin.pin_name = name
        elif not pin.pin_name:
            pin.pin_name = pin.instance_id

        if pin.pin_name in self._pin_collection:
            nn = re.sub(r"[0-9]", "", pin.pin_name)
            cc = 0
            while True:
                an = f"{nn}{cc}"
                if an not in self._pin_collection:
                    break
                cc += 1
            pin.pin_name = f"{nn}{cc}"

        pin.parent_node = self._parent_node

        self._pin_collection[pin.pin_name] = pin
        self._ordered_collection.append(pin)

        self.pin_added.emit(pin)
        return True

    def set_pin_name(self, pin: DaggerBasePin, name: str) -> bool:
        """Rename *pin* to *name*.  Fails if *name* is already taken."""
        if pin.pin_name == name:
            return True
        if self.pin(name) is not None:
            return False
        del self._pin_collection[pin.pin_name]
        self._pin_collection[name] = pin
        pin.pin_name = name
        return True

    def remove_pin(self, pin: DaggerBasePin) -> bool:
        """Remove *pin* from the collection.

        Fails if the pin is connected or the parent node vetoes removal
        via :meth:`~pydagger.node.DaggerNode.can_remove_pin`.
        """
        if pin in self._ordered_collection and not pin.is_connected:
            if self._parent_node and not self._parent_node.can_remove_pin(pin):
                return False

            pin_name = pin.pin_name
            self._pin_collection.pop(pin_name, None)
            if pin in self._ordered_collection:
                self._ordered_collection.remove(pin)
            pin.on_removed()
            self.pin_removed.emit(pin.instance_id)
            return True
        return False

    def index(self, pin: DaggerBasePin) -> int:
        """Return the positional index of *pin*, or ``-1`` if not found."""
        try:
            return self._ordered_collection.index(pin)
        except ValueError:
            return -1

    @property
    def parent_node(self) -> DaggerNode:
        """The node that owns this collection."""
        return self._parent_node

    @property
    def pin_direction(self) -> PinDirection:
        """The direction of pins in this collection."""
        return self._direction

    @property
    def all_pins(self) -> list[DaggerBasePin]:
        """A copy of the ordered list of all pins."""
        return list(self._ordered_collection)

    @property
    def all_non_connected_pins(self) -> list[DaggerBasePin]:
        """All pins that currently have no connections."""
        return [p for p in self._ordered_collection if not p.is_connected]

    @property
    def all_connected_pins(self) -> list[DaggerBasePin]:
        """All pins that currently have at least one connection."""
        return [p for p in self._ordered_collection if p.is_connected]

    @property
    def first_unconnected_pin(self) -> DaggerBasePin | None:
        """The first pin with no connection, or ``None``."""
        for p in self._ordered_collection:
            if not p.is_connected:
                return p
        return None

    def purge_all(self) -> None:
        for pin in self._ordered_collection:
            pin.purge_all()
        self._pin_collection.clear()
        self._ordered_collection.clear()
        super().purge_all()
