"""Qt-style signal/slot event system.

Provides a simple observer pattern where objects expose :class:`Signal`
instances as attributes.  External code connects callable *slots* to a
signal; when the signal is *emitted*, every connected slot is called with
the emitted arguments.

Example::

    graph.node_added.connect(lambda node: print(f"added {node.name}"))
    graph.add_node(my_node)  # prints "added ..."
"""

from __future__ import annotations
from typing import Callable


class Signal:
    """A signal that broadcasts to zero or more connected callback slots.

    Parameters
    ----------
    implementation : callable, optional
        If provided, registered as the first slot so that the owning object
        can supply a default handler while still allowing external listeners.
    """

    def __init__(self, implementation: Callable | None = None):
        self._callbacks: list[Callable] = []
        if implementation is not None:
            self._callbacks.append(implementation)

    def connect(self, slot: Callable) -> "Signal":
        """Register *slot* to be called on every future :meth:`emit`.

        Returns this signal so calls can be chained or the return value
        stored for a later :meth:`disconnect`.
        """
        self._callbacks.append(slot)
        return self

    def disconnect(self, slot: Callable) -> None:
        """Remove *slot* so it will no longer be called on :meth:`emit`.

        Silently does nothing if *slot* is not currently connected.
        """
        try:
            self._callbacks.remove(slot)
        except ValueError:
            pass

    def disconnect_all(self) -> None:
        """Remove every connected slot."""
        self._callbacks.clear()

    def emit(self, *args, **kwargs) -> None:
        """Call every connected slot with the given arguments."""
        for cb in list(self._callbacks):
            cb(*args, **kwargs)
