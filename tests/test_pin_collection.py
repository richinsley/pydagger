"""Tests for DaggerPinCollection."""
import pytest
from pydagger import DaggerPinCollection, DaggerInputPin, DaggerOutputPin, PinDirection
from pydagger.node import DaggerNode


class TestDaggerPinCollection:
    def test_add_pin_with_name(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        pin = DaggerInputPin()
        assert coll.add_pin(pin, "mypin") is True
        assert pin.pin_name == "mypin"

    def test_pin_lookup_by_name(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        pin = DaggerInputPin()
        coll.add_pin(pin, "mypin")
        assert coll.pin("mypin") is pin

    def test_pin_lookup_missing_returns_none(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        assert coll.pin("nope") is None

    def test_all_pins_returns_copy(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        pin = DaggerInputPin()
        coll.add_pin(pin, "p1")
        pins = coll.all_pins
        pins.clear()
        assert len(coll.all_pins) == 1  # original unaffected

    def test_index_of_pin(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        p1 = DaggerInputPin()
        p2 = DaggerInputPin()
        coll.add_pin(p1, "a")
        coll.add_pin(p2, "b")
        assert coll.index(p1) == 0
        assert coll.index(p2) == 1

    def test_topology_system(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.OUTPUT, 1)
        assert coll.topology_system == 1

    def test_pin_direction(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.OUTPUT, 0)
        assert coll.pin_direction == PinDirection.OUTPUT

    def test_first_unconnected_pin(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        p1 = DaggerInputPin()
        p2 = DaggerInputPin()
        coll.add_pin(p1, "a")
        coll.add_pin(p2, "b")
        assert coll.first_unconnected_pin is p1

    def test_add_pin_null_returns_false(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        assert coll.add_pin(None, "x") is False

    def test_pin_added_signal(self):
        node = DaggerNode()
        coll = DaggerPinCollection(node, PinDirection.INPUT, 0)
        added = []
        coll.pin_added.connect(lambda p: added.append(p))
        pin = DaggerInputPin()
        coll.add_pin(pin, "p")
        assert added == [pin]
