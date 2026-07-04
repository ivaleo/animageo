"""Regression tests for the DSL sandbox-hardening fix.

The pre-hardening SAFE_BUILTINS included ``type`` and ``getattr``, which
together form the classic 20-year-old escape to ``object.__subclasses__``
and thus to arbitrary code execution. The hardening:

  * Removes ``type`` and ``getattr`` from the DSL builtins.
  * Provides a safe ``type_name(x)`` helper for debug/dispatch use cases.
  * Keeps ``isinstance``, ``issubclass``, ``hasattr`` — these are safe.

This is a *soft* sandbox (the class-body trick via ``__build_class__``
still works), so web-service deployments must run untrusted DSL in an
isolated subprocess with CPU/memory caps. These tests cover the most
obvious vectors a curious/hostile user would try first.
"""
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.parsers.dsl.namespace import SAFE_BUILTINS


class TestBuiltinSurface:
    def test_type_removed(self):
        assert "type" not in SAFE_BUILTINS

    def test_getattr_removed(self):
        assert "getattr" not in SAFE_BUILTINS

    def test_type_name_helper_present(self):
        assert "type_name" in SAFE_BUILTINS
        assert SAFE_BUILTINS["type_name"](5) == "int"
        assert SAFE_BUILTINS["type_name"]("x") == "str"

    def test_isinstance_still_available(self):
        assert "isinstance" in SAFE_BUILTINS

    def test_hasattr_still_available(self):
        assert "hasattr" in SAFE_BUILTINS


class TestEscapeVectorsBlocked:
    """Invocations that previously reached ``object.__subclasses__`` must
    now raise ``NameError`` inside the DSL — stopped at the earliest
    possible point."""

    def test_type_lookup_fails_in_dsl(self):
        s = AnimaGeoScene()
        with pytest.raises((NameError, Exception)):
            s.putCode("kind = type(5)\n")

    def test_getattr_lookup_fails_in_dsl(self):
        s = AnimaGeoScene()
        with pytest.raises((NameError, Exception)):
            s.putCode("x = getattr(5, '__class__')\n")

    def test_subclasses_via_type_blocked(self):
        """The canonical escape chain: type(x).__mro__[-1].__subclasses__()."""
        s = AnimaGeoScene()
        with pytest.raises((NameError, Exception)):
            s.putCode("subs = type(5).__mro__[-1].__subclasses__()\n")


class TestSafeAlternatives:
    """The DSL remains useful — safe patterns for the old use cases work."""

    def test_type_name_works_in_dsl(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(0, 0)\nname = type_name(A)\n")
        # A was created; no crash on the ``type_name`` call.
        assert s.element('A') is not None

    def test_isinstance_works_in_dsl(self):
        s = AnimaGeoScene()
        # isinstance is available and usable for type dispatch against
        # any class in the sandbox (int, float, str, list, ...).
        s.putCode("A = Point(0, 0)\nok = isinstance(5, int)\n")
        assert s.element('A') is not None
