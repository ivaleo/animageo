"""Tests for Phase 9 — cross-type intersections + conic commands.

Sections:
- Function ∩ Conic / Circle / Function (numeric 1D).
- ImplicitCurve ∩ Line / Segment / Ray (param substitution + 1D root find).
- ImplicitCurve ∩ Conic / Circle / Function / ImplicitCurve (2D via
  marching squares + Newton refinement).
- Conic commands: Center, Focus, Vertex, Axes, Directrix, MajorAxis,
  MinorAxis, SemiMajorAxisLength, SemiMinorAxisLength, Eccentricity,
  LinearEccentricity, Coefficients.
- Polar and Tangent.
- Conic through 5 points.
- End-to-end: func5.ggb now resolves every Intersect command output
  that GGB itself can resolve.
"""
import os

import numpy as np
import pytest

from animageo.geo.lib_elements import (
    Point, Line, Segment, Ray, Circle, Conic, Function, ImplicitCurve,
)
from animageo.geo.lib_vars import Measure
from animageo.geo.lib_commands import (
    # F intersections
    intersect_FK, intersect_KF, intersect_Fc, intersect_cF, intersect_FF,
    # I intersections
    intersect_Il, intersect_lI, intersect_Is, intersect_Ir,
    intersect_IK, intersect_KI, intersect_Ic, intersect_cI,
    intersect_IF, intersect_FI, intersect_II,
    # Conic commands
    center_K, focus_K, vertex_K, axes_K, directrix_K,
    major_axis_K, minor_axis_K,
    semi_major_axis_length_K, semi_minor_axis_length_K,
    eccentricity_K, linear_eccentricity_K, coefficients_K,
    polar_pK, polar_Kp, tangent_pK, tangent_Kp,
    # Conic from 5 points
    conic_ppppp,
)
from animageo.geo.lib_conic import ConicType


# ── Function ∩ Conic ─────────────────────────────────────────────────

class TestFunctionConic:
    def test_parabola_function_meets_circle_conic(self):
        # y = x² (Function) ∩ x² + y² = 4 (Conic).
        # y² + y - 4 = 0 → y = (-1 + √17)/2 ≈ 1.5616
        # x = ±√y ≈ ±1.2494.
        f = Function.from_string('y = x**2')
        g = Conic.from_coeffs(a=1, c=1, f=-4)
        result = intersect_FK(f, g)
        assert isinstance(result, list) and len(result) == 2
        y_expected = (-1 + np.sqrt(17)) / 2
        for p in result:
            assert np.isclose(p.coords[1], y_expected, atol=1e-6)

    def test_reverse_dispatch(self):
        f = Function.from_string('y = x**2')
        g = Conic.from_coeffs(a=1, c=1, f=-4)
        r1 = intersect_FK(f, g)
        r2 = intersect_KF(g, f)
        assert len(r1) == len(r2)

    def test_function_circle(self):
        f = Function.from_string('y = x**2')
        c = Circle([0, 0], 2)
        result = intersect_Fc(f, c)
        assert isinstance(result, list) and len(result) == 2

    def test_function_function(self):
        # y = x² ∩ y = x + 2 → x² - x - 2 = 0 → x = -1, 2.
        f1 = Function.from_string('y = x**2')
        f2 = Function.from_string('y = x + 2')
        result = intersect_FF(f1, f2)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.allclose(xs, [-1, 2], atol=1e-6)


# ── ImplicitCurve ∩ Line / Segment ────────────────────────────────────

class TestImplicitLine:
    def test_circle_implicit_meets_xaxis(self):
        # x² + y² - 1 = 0 ∩ y = 0 → (±1, 0).
        F = ImplicitCurve.from_string('x**2 + y**2 - 1')
        line = Line([0, 1], 0)
        result = intersect_Il(F, line)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.allclose(xs, [-1, 1], atol=1e-6)

    def test_implicit_misses_line(self):
        F = ImplicitCurve.from_string('x**2 + y**2 - 1')
        line = Line([0, 1], 5)
        assert intersect_Il(F, line) is None

    def test_implicit_segment_filter(self):
        # x² + y² = 1 ∩ segment from (0, -2) to (0, 2) → (0, ±1).
        F = ImplicitCurve.from_string('x**2 + y**2 - 1')
        seg = Segment(np.array([0.0, -2.0]), np.array([0.0, 2.0]))
        result = intersect_Is(F, seg)
        assert isinstance(result, list) and len(result) == 2


class TestImplicitConic:
    def test_implicit_circle_meets_conic_secant(self):
        # Two secant circles, r=2 at (0,0) and r=2 at (1,0).
        # Subtract equations → 2x - 1 = 0 → x = 0.5, y = ±√(4-0.25).
        F = ImplicitCurve.from_string('x**2 + y**2 - 4')
        K = Conic.from_coeffs(a=1, c=1, d=-2, f=-3)
        result = intersect_IK(F, K)
        assert isinstance(result, list) and len(result) == 2
        for p in result:
            assert np.isclose(p.coords[0], 0.5, atol=1e-4)
            assert np.isclose(abs(p.coords[1]), np.sqrt(4 - 0.25), atol=1e-4)


# ── Conic commands: Center ────────────────────────────────────────────

class TestCenter:
    def test_ellipse_offset(self):
        # ((x-3)/2)² + ((y+1)/5)² = 1 → center (3, -1).
        c = Conic.from_coeffs(
            a=1/4, c=1/25, d=-6/4, e=2/25,
            f=9/4 + 1/25 - 1,
        )
        center = center_K(c)
        assert np.allclose(center.coords, [3, -1], atol=1e-9)

    def test_circle(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        center = center_K(c)
        assert np.allclose(center.coords, [0, 0])

    def test_parabola(self):
        # y = x² - 1 → vertex (0, -1).
        c = Conic.from_ggb_matrix(A0=-1, A1=0, A2=1, A3=0, A4=0, A5=0.5)
        center = center_K(c)
        assert np.allclose(center.coords, [0, -1], atol=1e-9)


# ── Focus ─────────────────────────────────────────────────────────────

class TestFocus:
    def test_ellipse_axis_aligned(self):
        # x²/9 + y²/4 = 1 → a=3, b=2, c = √5, foci (±√5, 0).
        c = Conic.from_coeffs(a=1/9, c=1/4, f=-1)
        foci = focus_K(c)
        assert isinstance(foci, list) and len(foci) == 2
        xs = sorted([f.coords[0] for f in foci])
        assert np.isclose(xs[0], -np.sqrt(5), atol=1e-9)
        assert np.isclose(xs[1],  np.sqrt(5), atol=1e-9)

    def test_hyperbola(self):
        # x²/4 - y²/9 = 1 → a=2, b=3, c = √13.
        c = Conic.from_coeffs(a=1/4, c=-1/9, f=-1)
        foci = focus_K(c)
        assert isinstance(foci, list) and len(foci) == 2
        xs = sorted([f.coords[0] for f in foci])
        assert np.isclose(xs[0], -np.sqrt(13), atol=1e-9)
        assert np.isclose(xs[1],  np.sqrt(13), atol=1e-9)

    def test_parabola(self):
        # y = x² → canonical x² = y. Focus at (0, 1/4).
        c = Conic.from_coeffs(a=1, e=-1)
        focus = focus_K(c)
        assert np.isclose(focus.coords[0], 0, atol=1e-9)
        assert np.isclose(focus.coords[1], 0.25, atol=1e-9)


# ── Vertex ────────────────────────────────────────────────────────────

class TestVertex:
    def test_ellipse_4_vertices(self):
        # x²/9 + y²/4 = 1 → vertices (±3, 0), (0, ±2).
        c = Conic.from_coeffs(a=1/9, c=1/4, f=-1)
        verts = vertex_K(c)
        assert isinstance(verts, list) and len(verts) == 4
        # Sort by (x, y) to get canonical ordering.
        verts_sorted = sorted([tuple(v.coords) for v in verts])
        expected = sorted([(-3, 0), (3, 0), (0, -2), (0, 2)])
        for got, exp in zip(verts_sorted, expected):
            assert np.allclose(got, exp, atol=1e-9)

    def test_hyperbola_2_vertices(self):
        # x²/4 - y²/9 = 1 → vertices (±2, 0).
        c = Conic.from_coeffs(a=1/4, c=-1/9, f=-1)
        verts = vertex_K(c)
        assert isinstance(verts, list) and len(verts) == 2

    def test_parabola_vertex(self):
        c = Conic.from_coeffs(a=1, e=-1)   # y = x²
        vert = vertex_K(c)
        assert np.allclose(vert.coords, [0, 0], atol=1e-9)


# ── Axes / MajorAxis / MinorAxis ──────────────────────────────────────

class TestAxes:
    def test_ellipse_axes(self):
        c = Conic.from_coeffs(a=1/9, c=1/4, f=-1)   # x²/9 + y²/4 = 1
        lines = axes_K(c)
        assert len(lines) == 2
        # Major axis along x (direction (1,0) → normal (0,1)), passes thru origin.
        major = major_axis_K(c)
        # y = 0 or equivalent: contains (2, 0), (3, 0).
        assert major.contains(np.array([1, 0]))
        assert major.contains(np.array([3, 0]))
        minor = minor_axis_K(c)
        assert minor.contains(np.array([0, 1]))


# ── Directrix ─────────────────────────────────────────────────────────

class TestDirectrix:
    def test_parabola_directrix(self):
        # y = x² ⇒ directrix y = -1/4.
        c = Conic.from_coeffs(a=1, e=-1)
        d = directrix_K(c)
        assert d is not None
        # Check (0, -0.25) on it.
        assert d.contains(np.array([0, -0.25]))
        assert d.contains(np.array([5, -0.25]))

    def test_ellipse_two_directrices(self):
        c = Conic.from_coeffs(a=1/9, c=1/4, f=-1)   # x²/9 + y²/4 = 1
        lines = directrix_K(c)
        assert isinstance(lines, list) and len(lines) == 2
        # a=3, c=√5, directrices at x = ±a²/c = ±9/√5.
        d = 9 / np.sqrt(5)
        xs = sorted([l.offset / l.normal[0] if abs(l.normal[0]) > 1e-9 else 0 for l in lines])
        assert np.isclose(abs(xs[0]), d, atol=1e-9)
        assert np.isclose(abs(xs[1]), d, atol=1e-9)


# ── Lengths and eccentricity ──────────────────────────────────────────

class TestLengthsEccentricity:
    def test_semi_major_minor_ellipse(self):
        c = Conic.from_coeffs(a=1/16, c=1/9, f=-1)   # a=4, b=3
        assert np.isclose(semi_major_axis_length_K(c).value, 4)
        assert np.isclose(semi_minor_axis_length_K(c).value, 3)

    def test_eccentricity_ellipse(self):
        # a=5, b=3, c=4, e=4/5=0.8.
        c = Conic.from_coeffs(a=1/25, c=1/9, f=-1)
        assert np.isclose(eccentricity_K(c).value, 4/5)

    def test_eccentricity_circle(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert np.isclose(eccentricity_K(c).value, 0)

    def test_eccentricity_parabola(self):
        c = Conic.from_coeffs(a=1, e=-1)
        assert np.isclose(eccentricity_K(c).value, 1)

    def test_linear_eccentricity_hyperbola(self):
        c = Conic.from_coeffs(a=1/4, c=-1/9, f=-1)   # a=2, b=3
        assert np.isclose(linear_eccentricity_K(c).value, np.sqrt(13))


# ── Coefficients ──────────────────────────────────────────────────────

class TestCoefficients:
    def test_unit_circle_coeffs(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        coeffs = coefficients_K(c)
        assert len(coeffs) == 6
        assert np.isclose(coeffs[0], 1)   # A
        assert np.isclose(coeffs[1], 0)   # B
        assert np.isclose(coeffs[2], 1)   # C
        assert np.isclose(coeffs[5], -1)  # F


# ── Polar / Tangent ───────────────────────────────────────────────────

class TestPolar:
    def test_polar_external_point_to_unit_circle(self):
        # Point (2, 0) w.r.t. x² + y² = 1: polar is x = 1/2.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        polar = polar_pK(Point([2.0, 0.0]), c)
        # Contains (0.5, 5) and (0.5, -5).
        assert polar.contains(np.array([0.5, 5]))
        assert polar.contains(np.array([0.5, -5]))

    def test_polar_of_origin(self):
        # For unit circle, polar of origin is the line at infinity
        # (no solution); my impl returns None.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        polar = polar_pK(Point([0.0, 0.0]), c)
        # M · [0, 0, 1]ᵀ = (0, 0, -1) → polar is 0·x + 0·y - 1 = 0,
        # degenerate. My code returns None since |n| = 0.
        assert polar is None


class TestTangent:
    def test_tangent_on_unit_circle(self):
        # Point (1, 0) is on unit circle; tangent is x = 1.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        t = tangent_pK(Point([1.0, 0.0]), c)
        assert t is not None
        assert t.contains(np.array([1, 5]))
        assert t.contains(np.array([1, -5]))

    def test_tangent_from_external(self):
        # Point (2, 0), unit circle: tangent points at (0.5, ±√3/2).
        # Two tangent lines through (2, 0) and those tangent points.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        t = tangent_pK(Point([2.0, 0.0]), c)
        assert isinstance(t, list) and len(t) == 2
        # Each tangent passes through (2, 0).
        for ln in t:
            assert ln.contains(np.array([2, 0]))

    def test_tangent_from_interior_returns_none(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        # Origin is inside unit circle → no real tangents.
        t = tangent_pK(Point([0.0, 0.0]), c)
        assert t is None


# ── Conic through 5 points ────────────────────────────────────────────

class TestConicThrough5Points:
    def test_unit_circle_recovered(self):
        # Any 5 points on x² + y² = 1 should recover a circle.
        pts = [
            Point([1, 0]), Point([-1, 0]),
            Point([0, 1]), Point([0, -1]),
            Point([np.sqrt(2)/2, np.sqrt(2)/2]),
        ]
        c = conic_ppppp(*pts)
        # Normalize matrix and check type.
        assert c.type == ConicType.CIRCLE
        center, r = c.as_circle()
        assert np.allclose(center, [0, 0], atol=1e-9)
        assert np.isclose(r, 1, atol=1e-9)

    def test_ellipse_recovered(self):
        # 5 points on x²/4 + y²/9 = 1.
        pts = [
            Point([2, 0]), Point([-2, 0]),
            Point([0, 3]), Point([0, -3]),
            Point([np.sqrt(2), 3*np.sqrt(2)/2]),
        ]
        c = conic_ppppp(*pts)
        assert c.type == ConicType.ELLIPSE
        params = c.as_ellipse()
        a, b = params['semi_axes']
        assert np.isclose(max(a, b), 3, atol=1e-6)
        assert np.isclose(min(a, b), 2, atol=1e-6)


# ── End-to-end: func5.ggb ─────────────────────────────────────────────

FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5EndToEnd:
    def test_all_intersections_resolved(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        constr = Construction()
        ggb_parser.load(constr, {}, FUNC5)

        # J, K — Intersect(function i, conic g).
        # Reference from geogebra.xml, atol loose because our numeric
        # solver may place the point slightly differently.
        expected = {
            'J': (-1.7912878602938678, 2.2087121397061322),
            'K': ( 1.7912878479308683, 2.2087121520691317),
            'L': (-5.500988177030235, -1.5009881770302353),
            'M': ( 5.931218024536485, -1.9312180245364852),
            'G': ( 0.531024403196342, -4.655198203413255),
            'H': ( 1.7488706784011268, -4.273784809530439),
        }
        for name, (ex, ey) in expected.items():
            elem = constr.element(name)
            assert elem is not None, f"{name} not created"
            if not isinstance(elem.data, Point):
                pytest.fail(f"{name} is not a Point (got {type(elem.data).__name__})")
            assert np.isclose(elem.data.coords[0], ex, atol=1e-3), (
                f"{name}: x expected {ex}, got {elem.data.coords[0]}"
            )
            assert np.isclose(elem.data.coords[1], ey, atol=1e-3), (
                f"{name}: y expected {ey}, got {elem.data.coords[1]}"
            )
