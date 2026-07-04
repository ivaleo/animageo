"""Tests for ``dsl.scope(constr)`` context manager.

``scope`` is a companion to ``dsl.run``: it binds a Construction to
the ContextVar without running AST-transformed source. Useful for
direct use of the DSL namespace in Python code with full IDE
autocomplete.
"""

import pytest

from animageo.geo.construction import Construction
from animageo.parsers import dsl
from animageo.parsers.dsl.namespace import Midpoint, Point
from animageo.parsers.dsl.registrar import _current_construction


class TestScopeBasics:
    def test_context_manager_binds_and_unbinds(self):
        c = Construction()
        assert _current_construction() is None
        with dsl.scope(c):
            assert _current_construction() is c
        assert _current_construction() is None

    def test_factory_inside_scope_registers_phantom(self):
        c = Construction()
        with dsl.scope(c):
            proxy = Point(3, 4)
        # Phantom name since no explicit name= was passed.
        assert proxy.name.startswith("_")
        assert c.element(proxy.name) is not None

    def test_factory_with_explicit_name(self):
        c = Construction()
        with dsl.scope(c):
            A = Point(3, 4, name='A')
            M = Midpoint(A, Point(0, 0, name='O'), name='M')
        assert c.element("A") is not None
        assert c.element("O") is not None
        assert c.element("M") is not None
        assert A.x == 3.0
        assert A.y == 4.0

    def test_factory_outside_scope_raises(self):
        # No scope — factory should error, not silently no-op.
        with pytest.raises(RuntimeError, match="outside dsl.run"):
            Point(0, 0)


class TestNestedScopes:
    def test_nested_scope_restores_outer(self):
        outer = Construction()
        inner = Construction()
        with dsl.scope(outer):
            assert _current_construction() is outer
            with dsl.scope(inner):
                assert _current_construction() is inner
                Point(1, 1, name='pi')
            assert _current_construction() is outer
            Point(0, 0, name='po')
        assert inner.element("pi") is not None
        assert outer.element("po") is not None
        # No cross-contamination.
        assert outer.element("pi") is None
        assert inner.element("po") is None


class TestScopeExceptionSafety:
    def test_exception_inside_scope_still_unbinds(self):
        c = Construction()
        with pytest.raises(ValueError):
            with dsl.scope(c):
                raise ValueError("boom")
        assert _current_construction() is None
