"""Tests for geometric conic constructors.

- Ellipse from (foci, semi-major axis).
- Ellipse from (foci, point on curve).
- Hyperbola from (foci, semi-transverse axis).
- Hyperbola from (foci, point on curve).
- Parabola from (focus, directrix line).

Round-trip check: construct → read back canonical params via
``as_ellipse`` / ``as_hyperbola`` / ``as_parabola`` → compare to the
analytically-expected values. Also verifies the classifier puts each
constructor's output in the right ConicType.
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import Conic, Line, Point, Segment
from animageo.geo.lib_vars import Measure
from animageo.geo.lib_conic import ConicType
from animageo.geo.lib_commands import (
    ellipse_ppi, ellipse_ppm, ellipse_ppp,
    hyperbola_ppi, hyperbola_ppm, hyperbola_ppp,
    parabola_pl, parabola_ps,
    center_K, focus_K, vertex_K,
)


# ── Ellipse ──────────────────────────────────────────────────────────

class TestEllipseConstructor:
    def test_axis_aligned(self):
        # foci (±3, 0), a=5 → c=3, b=4, canonical: x²/25 + y²/16 = 1.
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        c = ellipse_ppi(f1, f2, 5.0)
        assert c is not None
        assert c.type == ConicType.ELLIPSE
        p = c.as_ellipse()
        assert np.allclose(p['center'], [0, 0], atol=1e-9)
        a_semi, b_semi = p['semi_axes']
        assert np.isclose(a_semi, 5)
        assert np.isclose(b_semi, 4)

    def test_rotated(self):
        # foci (0, ±3), a=5 → rotation 90° equivalent.
        f1 = Point([0, -3])
        f2 = Point([0, 3])
        c = ellipse_ppi(f1, f2, 5.0)
        assert c.type == ConicType.ELLIPSE
        p = c.as_ellipse()
        a_semi, b_semi = p['semi_axes']
        assert np.isclose(max(a_semi, b_semi), 5)
        assert np.isclose(min(a_semi, b_semi), 4)

    def test_foci_verified_via_focus_K(self):
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        c = ellipse_ppi(f1, f2, 5.0)
        foci = focus_K(c)
        assert isinstance(foci, list) and len(foci) == 2
        xs = sorted([f.coords[0] for f in foci])
        assert np.isclose(xs[0], -3, atol=1e-9)
        assert np.isclose(xs[1], 3, atol=1e-9)

    def test_a_too_small_returns_none(self):
        # a must exceed focal distance c for a real ellipse.
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        # c = 3, so a = 2 → invalid.
        assert ellipse_ppi(f1, f2, 2.0) is None

    def test_measure_variant(self):
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        c = ellipse_ppm(f1, f2, Measure(5.0, 1))
        assert c.type == ConicType.ELLIPSE

    def test_from_point_on_curve(self):
        # Point (5, 0) on ellipse with foci (±3, 0) → a = (2 + 8)/2 = 5.
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        on_curve = Point([5, 0])
        c = ellipse_ppp(f1, f2, on_curve)
        assert c.type == ConicType.ELLIPSE
        p = c.as_ellipse()
        a_semi, _ = p['semi_axes']
        assert np.isclose(a_semi, 5, atol=1e-9)


# ── Hyperbola ────────────────────────────────────────────────────────

class TestHyperbolaConstructor:
    def test_axis_aligned(self):
        # foci (±√13, 0), a=2 → b² = 13 − 4 = 9, b = 3.
        cc = np.sqrt(13)
        c = hyperbola_ppi(Point([-cc, 0]), Point([cc, 0]), 2.0)
        assert c is not None
        assert c.type == ConicType.HYPERBOLA
        p = c.as_hyperbola()
        a_semi, b_semi = p['semi_axes']
        assert np.isclose(a_semi, 2, atol=1e-9)
        assert np.isclose(b_semi, 3, atol=1e-9)

    def test_foci_via_focus_K(self):
        cc = np.sqrt(13)
        hyp = hyperbola_ppi(Point([-cc, 0]), Point([cc, 0]), 2.0)
        foci = focus_K(hyp)
        assert isinstance(foci, list) and len(foci) == 2
        xs = sorted([f.coords[0] for f in foci])
        assert np.isclose(xs[0], -cc)
        assert np.isclose(xs[1],  cc)

    def test_a_too_large_returns_none(self):
        # For hyperbola, a must be less than c.
        f1 = Point([-3, 0])
        f2 = Point([3, 0])
        assert hyperbola_ppi(f1, f2, 5.0) is None

    def test_from_point_on_curve(self):
        # Point (2, 0) on hyperbola x²/4 - y²/9 = 1 with foci (±√13, 0).
        # a = ||f1−p| − |f2−p|| / 2 = |(√13+2) − (√13−2)| / 2 = 2.
        cc = np.sqrt(13)
        on_curve = Point([2, 0])
        c = hyperbola_ppp(Point([-cc, 0]), Point([cc, 0]), on_curve)
        assert c.type == ConicType.HYPERBOLA
        p = c.as_hyperbola()
        a_semi, _ = p['semi_axes']
        assert np.isclose(a_semi, 2, atol=1e-9)


# ── Parabola ─────────────────────────────────────────────────────────

class TestParabolaConstructor:
    def test_upward_canonical(self):
        # focus (0, 1), directrix y = −1 → vertex (0, 0), axis +y,
        # focal parameter p = distance(vertex, focus) = 1.
        focus = Point([0, 1])
        directrix = Line([0, 1], -1)   # y = −1
        c = parabola_pl(focus, directrix)
        assert c.type == ConicType.PARABOLA
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [0, 0], atol=1e-9)
        assert np.allclose(p['axis'], [0, 1], atol=1e-9)
        assert np.isclose(p['focal_parameter'], 1.0)

    def test_shifted_and_rotated(self):
        # focus (2, 3), directrix through (0, 0) with normal (1, 1)/√2,
        # i.e., x + y = 0. vertex = projection-midpoint.
        focus = Point([2, 3])
        directrix = Line([1, 1], 0)
        c = parabola_pl(focus, directrix)
        assert c.type == ConicType.PARABOLA

    def test_focus_via_focus_K(self):
        focus = Point([0, 1])
        directrix = Line([0, 1], -1)
        c = parabola_pl(focus, directrix)
        returned_focus = focus_K(c)
        assert np.allclose(returned_focus.coords, [0, 1], atol=1e-9)

    def test_focus_on_directrix_returns_none(self):
        focus = Point([0, 0])
        directrix = Line([0, 1], 0)
        assert parabola_pl(focus, directrix) is None

    def test_segment_as_directrix(self):
        focus = Point([0, 1])
        # Segment along y = −1.
        seg = Segment(np.array([-5.0, -1.0]), np.array([5.0, -1.0]))
        c = parabola_ps(focus, seg)
        assert c.type == ConicType.PARABOLA
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [0, 0], atol=1e-9)
