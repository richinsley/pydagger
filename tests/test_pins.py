"""Tests for pin classes."""
import pytest
from pydagger import DaggerBasePin, DaggerInputPin, DaggerOutputPin, PinDirection


class TestDaggerBasePin:
    def test_direction_is_unknown(self):
        pin = DaggerBasePin()
        assert pin.direction == PinDirection.UNKNOWN

    def test_default_pin_name_empty(self):
        pin = DaggerBasePin()
        assert pin.pin_name == ""

    def test_parent_node_defaults_none(self):
        pin = DaggerBasePin()
        assert pin.parent_node is None

    def test_is_input_pin_false(self):
        pin = DaggerBasePin()
        assert pin.is_input_pin is False

    def test_can_rename_default_false(self):
        pin = DaggerBasePin()
        assert pin.can_rename is False

    def test_auto_clone_defaults(self):
        pin = DaggerBasePin()
        assert pin.max_auto_clone == 0
        assert pin.auto_clone_count == 0
        assert pin.auto_clone_ref_count == 0
        assert pin.auto_clone_master is None
        assert pin.is_auto_cloned is False

    def test_set_auto_clone(self):
        pin = DaggerBasePin()
        pin.set_auto_clone(-1, "pin%")
        assert pin.max_auto_clone == -1
        assert pin.auto_clone_name_template == "pin%"
        assert pin.auto_clone_master is pin
        assert pin.get_auto_clone() is True

    def test_can_connect_to_pin_opposite_direction(self):
        inp = DaggerInputPin()
        out = DaggerOutputPin()
        assert inp.can_connect_to_pin(out) is True
        assert out.can_connect_to_pin(inp) is True

    def test_cannot_connect_same_direction(self):
        a = DaggerInputPin()
        b = DaggerInputPin()
        assert a.can_connect_to_pin(b) is False

    def test_pin_name_set_records_original(self):
        pin = DaggerBasePin()
        pin.pin_name = "first"
        assert pin.original_name == "first"
        pin.pin_name = "second"
        assert pin.original_name == "first"  # unchanged


class TestDaggerInputPin:
    def test_direction_is_input(self):
        pin = DaggerInputPin()
        assert pin.direction == PinDirection.INPUT

    def test_is_input_pin_true(self):
        pin = DaggerInputPin()
        assert pin.is_input_pin is True

    def test_not_connected_by_default(self):
        pin = DaggerInputPin()
        assert pin.is_connected is False
        assert pin.connected_to is None


class TestDaggerOutputPin:
    def test_direction_is_output(self):
        pin = DaggerOutputPin()
        assert pin.direction == PinDirection.OUTPUT

    def test_is_input_pin_false(self):
        pin = DaggerOutputPin()
        assert pin.is_input_pin is False

    def test_not_connected_by_default(self):
        pin = DaggerOutputPin()
        assert pin.is_connected is False
        assert pin.connected_to == []

    def test_allow_multi_connect_default_true(self):
        pin = DaggerOutputPin()
        assert pin.allow_multi_connect is True

    def test_allow_multi_connect_settable(self):
        pin = DaggerOutputPin()
        pin.allow_multi_connect = False
        assert pin.allow_multi_connect is False
