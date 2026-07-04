"""Phase 1 — Construction.rename / add_and_build / release_phantom."""

import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command


def test_release_phantom_removes_entry():
    c = Construction()
    p = c.add_new_phantom()
    assert p in c.phantoms
    c.release_phantom(p)
    assert p not in c.phantoms


def test_release_phantom_noop_for_unknown():
    c = Construction()
    c.release_phantom("_999")  # must not raise


def test_rename_element_moves_name():
    c = Construction()
    c.add_and_build(Command("Point", [3, 4], ["_1"]))
    assert c.element("_1") is not None
    c.rename("_1", "A")
    assert c.element("_1") is None
    assert c.element("A") is not None
    assert c.element("A").data.coords.tolist() == [3.0, 4.0]


def test_rename_updates_command_references():
    c = Construction()
    c.add_and_build(Command("Point", [0, 0], ["_1"]))
    c.add_and_build(Command("Point", [3, 4], ["_2"]))
    c.add_and_build(Command("Midpoint", ["_1", "_2"], ["_3"]))
    c.rename("_1", "A")
    c.rename("_2", "B")
    c.rename("_3", "M")
    # After rename, the Midpoint command must reference A, B.
    midpoint_cmd = [cmd for cmd in c.commands if cmd.name == "Midpoint"][0]
    assert midpoint_cmd.inputs == ["A", "B"]
    assert midpoint_cmd.outputs == ["M"]


def test_rename_updates_state_graph():
    c = Construction()
    c.add_and_build(Command("Point", [0, 0], ["_1"]))
    c.add_and_build(Command("Point", [3, 4], ["_2"]))
    c.add_and_build(Command("Midpoint", ["_1", "_2"], ["_3"]))
    c.rename("_1", "A")
    # A's outputs should include _3 (Midpoint depends on it).
    assert "_3" in c.state["A"]["outputs"]
    # _3's inputs should reference A.
    assert "A" in c.state["_3"]["inputs"]
    # Old name is gone from state.
    assert "_1" not in c.state


def test_rename_rejects_collision():
    c = Construction()
    c.add_and_build(Command("Point", [0, 0], ["A"]))
    c.add_and_build(Command("Point", [3, 4], ["_1"]))
    with pytest.raises(ValueError, match="already exists"):
        c.rename("_1", "A")


def test_rename_idempotent_same_name():
    c = Construction()
    c.add_and_build(Command("Point", [3, 4], ["A"]))
    c.rename("A", "A")  # must not raise
    assert c.element("A") is not None


def test_rename_drops_phantom_bookkeeping():
    c = Construction()
    # Phantom entries come from add_new_phantom(), not add_and_build —
    # this mimics the factory flow where a phantom is reserved first,
    # then filled by Command registration.
    p = c.add_new_phantom()
    c.add_and_build(Command("Point", [3, 4], [p]))
    assert p in c.phantoms
    c.rename(p, "A")
    assert p not in c.phantoms


def test_add_and_build_builds_eagerly():
    c = Construction()
    c.add_and_build(Command("Point", [3, 4], ["A"]))
    # After add_and_build, data is populated (eager).
    assert c.element("A").data is not None
    assert c.element("A").data.coords.tolist() == [3.0, 4.0]
    # State entry is marked built.
    assert c.state["A"]["built"] is True


def test_naming_counters_attr_present():
    c = Construction()
    assert c.naming_counters == {}
