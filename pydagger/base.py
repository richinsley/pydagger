"""Base class for all Dagger objects.

Every object in the Dagger hierarchy has a globally unique identifier
(:attr:`instance_id`) and an optional parent reference that tracks
ownership within the object tree.
"""

from __future__ import annotations
import uuid


class DaggerBase:
    """Root base class shared by all Dagger objects.

    Provides:
    * A unique ``instance_id`` (UUID v4) assigned at construction.
    * A ``parent`` reference for ownership tracking.
    * A ``purge_all`` hook for cleanup when an object is being torn down.
    """

    def __init__(self):
        self._instance_id: str = str(uuid.uuid4())
        self._parent: DaggerBase | None = None

    @property
    def instance_id(self) -> str:
        """Globally unique identifier for this instance."""
        return self._instance_id

    @property
    def parent(self) -> DaggerBase | None:
        """The parent object in the Dagger ownership hierarchy."""
        return self._parent

    @parent.setter
    def parent(self, p: DaggerBase | None) -> None:
        self._parent = p

    def purge_all(self) -> None:
        """Release internal references during teardown.

        Subclasses should call ``super().purge_all()`` after their own
        cleanup.
        """
        pass
