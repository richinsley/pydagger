"""Tests for Signal class."""
import pytest
from pydagger import Signal


class TestSignal:
    def test_emit_calls_connected_slots(self):
        sig = Signal()
        results = []
        sig.connect(lambda x: results.append(x))
        sig.emit("hello")
        assert results == ["hello"]

    def test_multiple_slots(self):
        sig = Signal()
        results = []
        sig.connect(lambda: results.append("a"))
        sig.connect(lambda: results.append("b"))
        sig.emit()
        assert results == ["a", "b"]

    def test_disconnect_specific_slot(self):
        sig = Signal()
        results = []
        slot_a = lambda: results.append("a")
        slot_b = lambda: results.append("b")
        sig.connect(slot_a)
        sig.connect(slot_b)
        sig.disconnect(slot_a)
        sig.emit()
        assert results == ["b"]

    def test_disconnect_all(self):
        sig = Signal()
        results = []
        sig.connect(lambda: results.append("a"))
        sig.connect(lambda: results.append("b"))
        sig.disconnect_all()
        sig.emit()
        assert results == []

    def test_emit_multiple_args(self):
        sig = Signal()
        results = []
        sig.connect(lambda a, b: results.append((a, b)))
        sig.emit(1, 2)
        assert results == [(1, 2)]

    def test_connect_returns_signal(self):
        sig = Signal()
        ret = sig.connect(lambda: None)
        assert ret is sig

    def test_constructor_with_implementation(self):
        results = []
        sig = Signal(lambda: results.append("impl"))
        sig.emit()
        assert results == ["impl"]

    def test_disconnect_nonexistent_slot_is_noop(self):
        sig = Signal()
        sig.disconnect(lambda: None)  # should not raise
