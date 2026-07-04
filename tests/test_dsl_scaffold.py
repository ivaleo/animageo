"""DSL scaffolding smoke tests — modules import and basic types work."""

from animageo.parsers import dsl
from animageo.parsers.dsl import (
    namespace,
    proxy,
    registrar,
    style_proxy,
    transform,
)


def test_package_imports():
    assert hasattr(dsl, "run")
    assert hasattr(dsl, "DSLSyntaxError")
    assert hasattr(transform, "transform")
    assert hasattr(transform, "DSLSyntaxError")
    assert hasattr(registrar, "_current_construction")
    assert hasattr(namespace, "build_namespace")
    assert hasattr(namespace, "SAFE_BUILTINS")
    assert hasattr(proxy, "ElementProxy")
    assert hasattr(style_proxy, "StyleProxy")


def test_current_construction_default_none():
    assert registrar._current_construction() is None


def test_element_proxy_has_name():
    class DummyConstr:
        def element(self, n): return None
        def var(self, n): return None
    p = proxy.ElementProxy(DummyConstr(), "A")
    assert p.name == "A"
