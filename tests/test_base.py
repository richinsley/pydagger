"""Tests for DaggerBase class."""
import pytest
from pydagger import DaggerBase


class TestDaggerBase:
    def test_has_instance_id(self):
        obj = DaggerBase()
        assert isinstance(obj.instance_id, str)
        assert len(obj.instance_id) == 36  # UUID format

    def test_unique_ids(self):
        a = DaggerBase()
        b = DaggerBase()
        assert a.instance_id != b.instance_id

    def test_parent_defaults_to_none(self):
        obj = DaggerBase()
        assert obj.parent is None

    def test_parent_get_set(self):
        parent = DaggerBase()
        child = DaggerBase()
        child.parent = parent
        assert child.parent is parent
