"""Phase 4 — IDE stubs: direct imports + runtime parity."""

import pytest

from animageo.geo.construction import Construction
from animageo.parsers.dsl.registrar import (
    reset_current_construction,
    set_current_construction,
)


class TestDirectImports:
    """``from animageo.parsers.dsl.namespace import Point`` must work."""

    def test_common_constructors_importable(self):
        from animageo.parsers.dsl.namespace import (
            Angle,
            Arc,
            Circle,
            Conic,
            Function,
            ImplicitCurve,
            Line,
            Point,
            Polygon,
            Ray,
            Segment,
            Vector,
        )
        assert all(callable(f) for f in [
            Angle, Arc, Circle, Conic, Function, ImplicitCurve,
            Line, Point, Polygon, Ray, Segment, Vector,
        ])

    def test_common_commands_importable(self):
        from animageo.parsers.dsl.namespace import (
            AreCollinear,
            Center,
            Distance,
            Focus,
            Intersect,
            Midpoint,
            Radius,
            Vertex,
        )
        assert all(callable(f) for f in [
            AreCollinear, Center, Distance, Focus,
            Intersect, Midpoint, Radius, Vertex,
        ])

    def test_helpers_importable(self):
        from animageo.parsers.dsl.namespace import hide, show, style
        assert all(callable(f) for f in [hide, show, style])


class TestDirectUseWithContext:
    """Factories work when called with a ContextVar-bound Construction."""

    def test_point_via_direct_import(self):
        from animageo.parsers.dsl.namespace import Point
        c = Construction()
        token = set_current_construction(c)
        try:
            p = Point(3, 4, name="A")
            assert p.name == "A"
            assert p.x == 3.0
            assert p.y == 4.0
        finally:
            reset_current_construction(token)

    def test_no_context_raises(self):
        from animageo.parsers.dsl.namespace import Point
        with pytest.raises(RuntimeError, match="outside dsl.run"):
            Point(3, 4)


class TestFactoryCoverage:
    """Every auto-discovered command must have a callable factory."""

    def test_all_discovered_commands_have_factories(self):
        from animageo.parsers.dsl.namespace import (
            _DISCOVERED_COMMANDS,
            _FACTORIES,
        )
        assert len(_DISCOVERED_COMMANDS) == len(_FACTORIES)
        for name in _DISCOVERED_COMMANDS:
            assert name in _FACTORIES
            assert callable(_FACTORIES[name])

    def test_discovered_count_reasonable(self):
        """Sanity: we should discover dozens of commands, not 0 or 1000."""
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        assert 50 <= len(_DISCOVERED_COMMANDS) <= 200


class TestStubFilesExist:
    """Phase 4 ships .pyi stubs. Verify they're on disk."""

    def test_namespace_stub_exists(self):
        from pathlib import Path
        root = Path(__file__).parent.parent
        assert (root / "animageo/parsers/dsl/namespace.pyi").exists()

    def test_proxy_stub_exists(self):
        from pathlib import Path
        root = Path(__file__).parent.parent
        assert (root / "animageo/parsers/dsl/proxy.pyi").exists()

    def test_style_proxy_stub_exists(self):
        from pathlib import Path
        root = Path(__file__).parent.parent
        assert (root / "animageo/style/proxy.pyi").exists()
