"""Phase 1 — registrar unit tests."""

import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.parsers.dsl import registrar
from animageo.parsers.dsl.proxy import ElementProxy
from animageo.parsers.dsl.registrar import (
    __reg__,
    __reg_loop__,
    __reg_loop_tuple__,
    __reg_tuple__,
    reset_current_construction,
    set_current_construction,
)


@pytest.fixture
def ctx():
    c = Construction()
    token = set_current_construction(c)
    yield c
    reset_current_construction(token)


def _make_phantom_proxy(c, name_hint: str | None = None) -> ElementProxy:
    """Register a phantom Point command and return its proxy."""
    name = name_hint if name_hint is not None else c.add_new_phantom()
    c.add_and_build(Command("Point", [0, 0], [name]))
    return ElementProxy(c, name, explicit=False)


class TestTopLevelReg:
    def test_rename_phantom_to_target(self, ctx):
        proxy = _make_phantom_proxy(ctx)
        assert proxy._name.startswith("_")
        new_proxy = __reg__("A", proxy)
        assert new_proxy.name == "A"
        assert ctx.element("A") is not None
        assert ctx.element(proxy._name) is None

    def test_explicit_name_kept(self, ctx):
        ctx.add_and_build(Command("Point", [1, 1], ["foo"]))
        explicit_proxy = ElementProxy(ctx, "foo", explicit=True)
        result = __reg__("A", explicit_proxy)
        # Must keep "foo", not rename to "A".
        assert result.name == "foo"
        assert ctx.element("foo") is not None
        assert ctx.element("A") is None

    def test_literal_value_calls_update(self, ctx):
        # Scalar literal: Python name binds to the raw value (so
        # ``x * 2`` still works), while the Construction still tracks
        # a Var under name ``x`` for the dependency graph.
        result = __reg__("x", 42)
        assert result == 42              # Python-value passthrough
        assert not isinstance(result, ElementProxy)
        assert ctx.var("x") is not None  # Construction still has it
        assert ctx.var("x").data == 42

    def test_reg_outside_context_raises(self):
        with pytest.raises(RuntimeError, match="outside dsl.run"):
            __reg__("A", 5)

    def test_overwrite_top_level_name(self, ctx):
        p1 = _make_phantom_proxy(ctx)
        __reg__("A", p1)
        assert ctx.element("A") is not None
        # New binding for the same name.
        p2 = _make_phantom_proxy(ctx)
        __reg__("A", p2)
        # Only one "A" exists.
        names = [e.name for e in ctx.elements if e.name == "A"]
        assert len(names) == 1


class TestLoopReg:
    def test_first_call_uses_base_name(self, ctx):
        proxy = _make_phantom_proxy(ctx)
        result = __reg_loop__("p", proxy)
        assert result.name == "p"

    def test_second_call_uses_suffix_2(self, ctx):
        p1 = _make_phantom_proxy(ctx)
        p2 = _make_phantom_proxy(ctx)
        r1 = __reg_loop__("p", p1)
        r2 = __reg_loop__("p", p2)
        assert r1.name == "p"
        assert r2.name == "p_2"

    def test_three_iterations(self, ctx):
        names = []
        for _ in range(3):
            p = _make_phantom_proxy(ctx)
            names.append(__reg_loop__("p", p).name)
        assert names == ["p", "p_2", "p_3"]

    def test_skips_existing_base_name(self, ctx):
        # Pre-existing "p" from top level.
        existing = _make_phantom_proxy(ctx)
        __reg__("p", existing)
        # Loop should start from p_2.
        p = _make_phantom_proxy(ctx)
        r = __reg_loop__("p", p)
        assert r.name == "p_2"


class TestTupleReg:
    def test_tuple_top_level(self, ctx):
        p1 = _make_phantom_proxy(ctx)
        p2 = _make_phantom_proxy(ctx)
        results = __reg_tuple__(("A", "B"), (p1, p2))
        assert results[0].name == "A"
        assert results[1].name == "B"

    def test_tuple_length_mismatch_raises(self, ctx):
        p = _make_phantom_proxy(ctx)
        with pytest.raises(ValueError, match="expected 2 values"):
            __reg_tuple__(("A", "B"), (p,))

    def test_tuple_non_iterable_raises(self, ctx):
        with pytest.raises(TypeError, match="iterable"):
            __reg_tuple__(("A", "B"), 42)

    def test_loop_tuple_uniquifies(self, ctx):
        for _ in range(2):
            p1 = _make_phantom_proxy(ctx)
            p2 = _make_phantom_proxy(ctx)
            __reg_loop_tuple__(("a", "b"), (p1, p2))
        # Names: a, b then a_2, b_2.
        assert ctx.element("a") is not None
        assert ctx.element("b") is not None
        assert ctx.element("a_2") is not None
        assert ctx.element("b_2") is not None
