"""Base class for all Dagger pins.

A *pin* is a connection point on a :class:`~pydagger.node.DaggerNode`.
Pins come in two flavours — input and output — and connections always
flow from an output pin to an input pin.  This module provides the
abstract base class and the :class:`PinDirection` enum shared by both.

Pins support *auto-cloning*: when a pin marked for auto-clone is
connected, the owning node automatically creates a duplicate so that
additional connections can be made without manual pin management.
"""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING

from .base import DaggerBase
from .signal import Signal

if TYPE_CHECKING:
    from .node import DaggerNode
    from .pin_collection import DaggerPinCollection


class PinDirection(Enum):
    """Direction of data flow through a pin."""
    UNKNOWN = "Unknown"
    INPUT = "Input"
    OUTPUT = "Output"


class DaggerBasePin(DaggerBase):
    """Abstract base for :class:`~pydagger.input_pin.DaggerInputPin` and
    :class:`~pydagger.output_pin.DaggerOutputPin`.

    Attributes (signals)
    --------------------
    parent_node_changed : Signal
        Emitted when this pin is assigned to a different node.
    pin_name_changed : Signal
        Emitted when the pin's name changes (only after parenting).
    pin_connected / pin_disconnected : Signal
        Emitted when a connection is made or broken on this pin.
    """

    def __init__(self):
        super().__init__()
        self._pin_name: str = ""
        self._parent_node: DaggerNode | None = None
        self._name_set: bool = False
        self._can_rename: bool = False
        self._max_auto_clone: int = 0
        self._auto_clone_count: int = 0
        self._auto_clone_ref: int = 0
        self._auto_clone_master: DaggerBasePin | None = None
        self._auto_clone_name_template: str = ""
        self._original_name: str = ""

        self.parent_node_changed = Signal()
        self.parent_graph_changed = Signal()
        self.pin_name_changed = Signal()
        self.can_rename_changed = Signal()
        self.pin_connected = Signal()
        self.pin_disconnected = Signal()

    # -- direction -----------------------------------------------------------

    @property
    def direction(self) -> PinDirection:
        """The direction of flow this pin represents.  Subclasses override."""
        return PinDirection.UNKNOWN

    @property
    def is_input_pin(self) -> bool:
        """Convenience check: ``True`` if this is an input pin."""
        return self.direction == PinDirection.INPUT

    # -- naming --------------------------------------------------------------

    @property
    def pin_name(self) -> str:
        """Current name of the pin (unique within its collection)."""
        return self._pin_name

    @pin_name.setter
    def pin_name(self, name: str) -> None:
        self._pin_name = name
        if not self._name_set:
            self._name_set = True
            self._original_name = name
        if self._parent_node:
            self.pin_name_changed.emit()

    @property
    def original_name(self) -> str:
        """The first name assigned to this pin.  Unchanged by later renames."""
        return self._original_name

    @property
    def can_rename(self) -> bool:
        """Whether this pin is allowed to be renamed."""
        return self._can_rename

    @can_rename.setter
    def can_rename(self, val: bool) -> None:
        self._can_rename = val
        if self._parent_node:
            self.can_rename_changed.emit()

    # -- parent references ---------------------------------------------------

    @property
    def parent_node(self) -> DaggerNode | None:
        """The node that owns this pin."""
        return self._parent_node

    @parent_node.setter
    def parent_node(self, n: DaggerNode | None) -> None:
        self._parent_node = n
        self.parent_node_changed.emit()

    @property
    def topology_system(self) -> int:
        """Which topology system this pin belongs to (from its collection)."""
        collection: DaggerPinCollection = self.parent  # type: ignore
        return collection.topology_system

    @property
    def index(self) -> int:
        """Position of this pin within its parent collection."""
        collection: DaggerPinCollection = self.parent  # type: ignore
        return collection.index(self)

    # -- connection ----------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Whether this pin currently has any connections.  Subclasses override."""
        return False

    def can_connect_to_pin(self, pin: DaggerBasePin) -> bool:
        """Base connectivity test: pins must have opposite directions."""
        return self.direction != pin.direction

    # -- auto-clone ----------------------------------------------------------

    @property
    def auto_clone_master(self) -> DaggerBasePin | None:
        """The original pin this was cloned from, or ``self`` if this is the master."""
        return self._auto_clone_master

    @property
    def is_auto_cloned(self) -> bool:
        """``True`` if this pin was created by the auto-clone mechanism."""
        return self._auto_clone_master is not None and self._auto_clone_master is not self

    @property
    def auto_clone_count(self) -> int:
        """Current number of live clones made from this pin's master."""
        return self._auto_clone_count

    @property
    def auto_clone_ref_count(self) -> int:
        """Total number of clones ever made (used for name generation)."""
        return self._auto_clone_ref

    @property
    def max_auto_clone(self) -> int:
        """Maximum clones allowed.  ``0`` = disabled, ``-1`` = unlimited."""
        return self._max_auto_clone

    @property
    def auto_clone_name_template(self) -> str:
        """Template for generating clone names.  ``%`` is replaced with the clone index."""
        return self._auto_clone_name_template

    def get_auto_clone(self) -> bool:
        """``True`` if this pin is the auto-clone master (i.e., the original)."""
        return self._auto_clone_master is self

    def set_auto_clone(self, max_count: int, name_template: str) -> bool:
        """Enable auto-cloning on this pin.

        Parameters
        ----------
        max_count : int
            Maximum clones allowed (``-1`` for unlimited, ``0`` to disable).
        name_template : str
            Template string where ``%`` is replaced with the clone index.
        """
        self._max_auto_clone = max_count
        self._auto_clone_name_template = name_template
        self._auto_clone_master = self
        return True

    def inc_auto_clone_count(self) -> None:
        self._auto_clone_count += 1
        self._auto_clone_ref += 1

    def dec_auto_clone_count(self) -> None:
        self._auto_clone_count -= 1

    def gen_cloned_name_from_template(self) -> None:
        """Set this pin's name from the master's template + ref count."""
        master = self._auto_clone_master
        assert master is not None
        rcount = str(master.auto_clone_ref_count)
        self.pin_name = master.auto_clone_name_template.replace("%", rcount)

    def cloned(self, from_master: DaggerBasePin) -> None:
        """Called after this pin was cloned from *from_master*.

        Subclasses that override must call ``super().cloned(from_master)``.
        """
        self._auto_clone_master = from_master
        from_master.inc_auto_clone_count()
        self._can_rename = from_master.can_rename
        self.gen_cloned_name_from_template()

    def _clone(self) -> DaggerBasePin:
        """Create a new instance of the same concrete pin class."""
        return self.__class__()

    def on_removed(self) -> None:
        """Hook called when this pin is removed from its collection."""
        pass

    def on_cloned(self) -> None:
        """Hook called on a newly cloned pin after it has been added to a collection."""
        pass

    def purge_all(self) -> None:
        super().purge_all()
