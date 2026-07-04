"""Phase 3 — human-friendly field access on geometry classes.

Tests that ``@property`` aliases on Point/Circle/Line/… work, and
that they're reachable via both ``Element.__getattr__`` (direct)
and ``ElementProxy.__getattr__`` (DSL).
"""

import numpy as np

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import (
    Angle, Arc, Circle, Line, Point, Polygon, Ray, Segment, Vector,
)
from animageo.geo.lib_vars import Boolean, Measure
from animageo.parsers import dsl


# ── Point ────────────────────────────────────────────────────────

class TestPointAccessors:
    def test_x_y(self):
        p = Point([3, 4])
        assert p.x == 3.0
        assert p.y == 4.0

    def test_coords(self):
        p = Point([1, 2])
        assert np.allclose(p.coords, [1, 2])

    def test_via_element_getattr(self):
        from animageo.geo.lib_elements import Element
        elem = Element("A", Point([3, 4]))
        # __getattr__ on Element forwards to data
        assert elem.x == 3.0
        assert elem.y == 4.0
        # Existing accessors (.name, .data, .style, .visible) still win.
        assert elem.name == "A"

    def test_via_proxy_in_dsl(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(3, 4)\n"
            "x_val = A.x\n"
            "y_val = A.y",
        )
        assert c.var("x_val").data == 3.0
        assert c.var("y_val").data == 4.0


# ── Circle ───────────────────────────────────────────────────────

class TestCircleAccessors:
    def test_center_radius(self):
        circ = Circle([0, 0], 5)
        assert np.allclose(circ.center, [0, 0])
        assert circ.radius == 5

    def test_via_dsl(self):
        c = Construction()
        dsl.run(
            c,
            "O = Point(2, 3)\n"
            "A = Point(5, 3)\n"
            "circ = Circle(O, A)\n"
            "r = circ.radius",
        )
        # Radius = distance from center to A = 3.
        assert abs(c.var("r").data - 3.0) < 1e-9


# ── Line / Segment / Ray ─────────────────────────────────────────

class TestLineAccessors:
    def test_line_normal_direction(self):
        L = Line([1, 0], 5)
        assert np.allclose(L.normal, [1, 0])
        # direction perpendicular to normal
        assert abs(np.dot(L.normal, L.direction)) < 1e-9

    def test_segment_start_end_length(self):
        s = Segment(np.array([0, 0]), np.array([3, 4]))
        assert np.allclose(s.start, [0, 0])
        assert np.allclose(s.end, [3, 4])
        assert abs(s.length - 5) < 1e-9

    def test_ray_start(self):
        r = Ray(np.array([1, 2]), np.array([1, 0]))
        assert np.allclose(r.start, [1, 2])


# ── Angle / Polygon / Vector ─────────────────────────────────────

class TestAngleAccessors:
    def test_angle_vertex_value(self):
        a = Angle(np.array([0, 0]), np.array([1, 0]), np.array([0, 1]))
        assert np.allclose(a.vertex, [0, 0])
        assert abs(a.value - np.pi / 2) < 1e-9


class TestPolygonAccessors:
    def test_vertices(self):
        p = Polygon([[0, 0], [1, 0], [0, 1]])
        assert p.vertices.shape == (3, 2)


class TestVectorAccessors:
    def test_start_end_direction(self):
        v = Vector([[0, 0], [3, 4]])
        assert np.allclose(v.start, [0, 0])
        assert np.allclose(v.end, [3, 4])
        assert np.allclose(v.direction, [3, 4])


# ── Measure / Boolean ────────────────────────────────────────────

class TestVarAccessors:
    def test_measure_value_dimension(self):
        m = Measure(42.0, dimension=1)
        assert m.value == 42.0
        assert m.dimension == 1

    def test_boolean_value(self):
        b = Boolean(True)
        assert b.value is True


# ── Conic / Function / ImplicitCurve ─────────────────────────────

class TestConicAccessors:
    def test_matrix_kind(self):
        from animageo.geo.lib_conic import Conic, ConicType
        g = Conic.from_coeffs(1, 0, 1, 0, 0, -4)  # x^2+y^2-4=0
        assert g.matrix.shape == (3, 3)
        assert g.kind == ConicType.CIRCLE


class TestFunctionAccessors:
    def test_expression_variable_source(self):
        from animageo.geo.lib_function import Function
        f = Function("y = x**2 + 1")
        assert f.expression is not None
        assert f.variable is not None
        assert "x" in f.source


class TestImplicitAccessors:
    def test_expression_vars(self):
        from animageo.geo.lib_implicit import ImplicitCurve
        h = ImplicitCurve("x**2 + y**2 - 1")
        assert h.expression is not None
        assert h.x_var is not None
        assert h.y_var is not None
