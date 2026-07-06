"""Tests for Conic intersections (intersect_Kl, intersect_KK, intersect_Kc).

Covers the analytic cases a geometric-construction app must handle:
- Conic ∩ Line: 0, 1 (tangent), or 2 intersections.
- Conic ∩ Conic: 0 to 4 intersections via the pencil method.
- Conic ∩ Circle: delegated to KK with circle→conic adapter.

The reference points A..D come from ``examples/func/func5/geogebra.xml``,
where GeoGebra recorded the exact coordinates of the Intersect command
outputs — a ground-truth cross-check against a well-known tool.
"""
import os

import numpy as np
import pytest

from animageo.geo.lib_elements import Conic, Line, Circle, Point
from animageo.geo.lib_conic import ConicType
from animageo.geo.lib_commands import (
    intersect_Kl, intersect_lK, intersect_Kli, intersect_lKi,
    intersect_KK, intersect_KKi,
    intersect_Kc, intersect_cK, intersect_Kci,
    intersect_Kr, intersect_Ks,
    type_to_shortcut,
)


# ── type_to_shortcut registration ─────────────────────────────────────

def test_conic_shortcut_registered():
    assert type_to_shortcut[Conic] == 'K'


# ── intersect_Kl ──────────────────────────────────────────────────────

class TestIntersectKl:
    def test_circle_crossed_by_line(self):
        # Unit circle x² + y² = 1, line y = 0 (x-axis).
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        line = Line([0, 1], 0)  # n=(0,1), c=0 → y = 0
        result = intersect_Kl(conic, line)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.allclose(xs, [-1, 1])
        for p in result:
            assert np.isclose(p.coords[1], 0)

    def test_line_tangent_to_circle(self):
        # x² + y² = 1, line y = 1 touches at (0, 1).
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        line = Line([0, 1], 1)
        result = intersect_Kl(conic, line)
        assert isinstance(result, Point)
        assert np.allclose(result.coords, [0, 1], atol=1e-9)

    def test_line_misses_circle(self):
        # x² + y² = 1, line y = 2 is above.
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        line = Line([0, 1], 2)
        assert intersect_Kl(conic, line) is None

    def test_parabola_crossed_by_line(self):
        # y = x² → x² − y = 0, line y = 1.
        # Substitute: x² − 1 = 0 → x = ±1.
        conic = Conic.from_coeffs(a=1, e=-1)
        line = Line([0, 1], 1)
        result = intersect_Kl(conic, line)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.allclose(xs, [-1, 1])

    def test_reverse_dispatch(self):
        # intersect_lK should give the same result as intersect_Kl.
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        line = Line([0, 1], 0)
        r1 = intersect_Kl(conic, line)
        r2 = intersect_lK(line, conic)
        assert len(r1) == len(r2)

    def test_index_selection(self):
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        line = Line([0, 1], 0)
        p1 = intersect_Kli(conic, line, 1)
        p2 = intersect_Kli(conic, line, 2)
        assert p1 is not None and p2 is not None
        assert not np.allclose(p1.coords, p2.coords)


# ── intersect_KK ──────────────────────────────────────────────────────

class TestIntersectKK:
    def test_two_circles_cross(self):
        # x² + y² = 4 ∩ (x−2)² + y² = 4 → x = 1, y = ±√3.
        K1 = Conic.from_coeffs(a=1, c=1, f=-4)
        K2 = Conic.from_coeffs(a=1, c=1, d=-4, f=0)
        result = intersect_KK(K1, K2)
        assert isinstance(result, list) and len(result) == 2
        for p in result:
            assert np.isclose(p.coords[0], 1)
        ys = sorted([p.coords[1] for p in result])
        assert np.allclose(ys, [-np.sqrt(3), np.sqrt(3)])

    def test_func5_g_h_intersections(self):
        # g: y = x² − 1, h: x² + y² = 4.
        # Substitute: x⁴ − x² − 3 = 0 → x² = (1+√13)/2 ≈ 2.30278.
        # x ≈ ±1.51749, y = x² − 1 ≈ 1.30278.
        g = Conic.from_ggb_matrix(A0=-1, A1=0, A2=1, A3=0, A4=0, A5=0.5)
        h = Conic.from_ggb_matrix(A0=1, A1=1, A2=-4, A3=0, A4=0, A5=0)
        result = intersect_KK(g, h)
        assert isinstance(result, list) and len(result) == 2
        pts = sorted(result, key=lambda p: p.coords[0])
        # Expected: C ≈ (−1.5175, 1.3028), D ≈ (1.5175, 1.3028).
        assert np.isclose(pts[0].coords[0], -1.5174899135519797, atol=1e-6)
        assert np.isclose(pts[0].coords[1],  1.3027756377319948, atol=1e-6)
        assert np.isclose(pts[1].coords[0],  1.5174899135519793, atol=1e-6)
        assert np.isclose(pts[1].coords[1],  1.3027756377319935, atol=1e-6)

    def test_disjoint_conics(self):
        # x² + y² = 1 and (x − 10)² + y² = 1: far apart.
        K1 = Conic.from_coeffs(a=1, c=1, f=-1)
        K2 = Conic.from_coeffs(a=1, c=1, d=-20, f=99)
        assert intersect_KK(K1, K2) is None

    def test_index_selection(self):
        g = Conic.from_ggb_matrix(A0=-1, A1=0, A2=1, A3=0, A4=0, A5=0.5)
        h = Conic.from_ggb_matrix(A0=1, A1=1, A2=-4, A3=0, A4=0, A5=0)
        p1 = intersect_KKi(g, h, 1)
        p2 = intersect_KKi(g, h, 2)
        assert p1 is not None and p2 is not None
        assert not np.allclose(p1.coords, p2.coords)


# ── intersect_Kc (Conic ∩ Circle) ─────────────────────────────────────

class TestIntersectKc:
    def test_parabola_meets_circle(self):
        # y = x² ∩ x² + y² = 4 → y + y² = 4, y² + y − 4 = 0.
        # y = (−1 ± √17)/2 ≈ 1.56155 or −2.56155 (rejected: y = x² ≥ 0).
        # x² = y = 1.56155 → x ≈ ±1.24940.
        parabola = Conic.from_coeffs(a=1, e=-1)
        circle = Circle([0, 0], 2)
        result = intersect_Kc(parabola, circle)
        assert isinstance(result, list) and len(result) == 2
        y_expected = (-1 + np.sqrt(17)) / 2
        for p in result:
            assert np.isclose(p.coords[1], y_expected, atol=1e-9)

    def test_reverse_dispatch(self):
        parabola = Conic.from_coeffs(a=1, e=-1)
        circle = Circle([0, 0], 2)
        r1 = intersect_Kc(parabola, circle)
        r2 = intersect_cK(circle, parabola)
        assert len(r1) == len(r2)


# ── intersect_Kr and intersect_Ks (ray/segment filters) ───────────────

class TestIntersectKrKs:
    def test_segment_hit_by_conic(self):
        from animageo.geo.lib_elements import Segment
        # Unit circle, segment from (−2, 0) to (2, 0): full x-axis diameter.
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        seg = Segment(np.array([-2.0, 0.0]), np.array([2.0, 0.0]))
        result = intersect_Ks(conic, seg)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.allclose(xs, [-1, 1])

    def test_segment_misses_conic(self):
        from animageo.geo.lib_elements import Segment
        # Unit circle, segment entirely inside.
        conic = Conic.from_coeffs(a=1, c=1, f=-1)
        seg = Segment(np.array([-0.3, 0.0]), np.array([0.3, 0.0]))
        assert intersect_Ks(conic, seg) is None


# ── Full GGB pipeline: func5.ggb Intersect commands ───────────────────

FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5IntersectCommands:
    def test_intersect_outputs_coincide_with_ggb_values(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        constr = Construction()
        ggb_parser.load(constr, {}, FUNC5)

        # GGB-computed intersection coordinates (from geogebra.xml).
        expected = {
            'A': (-1.2717797887081348, -1.5435595774162694),  # h ∩ f, idx 1
            'B': ( 0.47177978870813475, 1.9435595774162695),   # h ∩ f, idx 2
            'C': (-1.5174899135519797,  1.3027756377319948),   # g ∩ h, idx 1
            'D': ( 1.5174899135519793,  1.3027756377319935),   # g ∩ h, idx 2
        }

        for name, (ex, ey) in expected.items():
            elem = constr.element(name)
            assert elem is not None, f"element '{name}' not created"
            assert isinstance(elem.data, Point), f"'{name}' is not a Point"
            assert np.isclose(elem.data.coords[0], ex, atol=1e-6), (
                f"{name}: x expected {ex}, got {elem.data.coords[0]}"
            )
            assert np.isclose(elem.data.coords[1], ey, atol=1e-6), (
                f"{name}: y expected {ey}, got {elem.data.coords[1]}"
            )


# ── Axis intersection ordering matches GeoGebra ───────────────────────

class TestAxisIntersectOrder:
    """GeoGebra orients xAxis toward +x and yAxis toward +y, so
    ``Intersect(circle, axis, 1)`` is the point lower along the positive
    axis direction. The unit circle centred at the origin meets:
    - xAxis at (-1, 0) [index 1] and (1, 0) [index 2] — ascending x
    - yAxis at (0, -1) [index 1] and (0, 1) [index 2] — ascending y

    The yAxis case regresses if its normal is (1, 0) instead of (-1, 0):
    the direction vector flips to (0, -1) and the two points swap, which
    (via a downstream ``Line(I, H)``) skews lines built through the wrong
    intersection. Reproduced from shared/8wD1DwtEbOQ.
    """

    def _unit_circle(self):
        # x² + y² − 1 = 0.
        return Conic.from_coeffs(a=1, c=1, f=-1)

    def test_xaxis_order(self):
        from animageo.geo.construction import Construction
        c = self._unit_circle()
        xaxis = Construction().element('xAxis').data
        p1 = intersect_Kli(c, xaxis, 1)
        p2 = intersect_Kli(c, xaxis, 2)
        assert np.allclose(p1.coords[:2], [-1, 0], atol=1e-9)
        assert np.allclose(p2.coords[:2], [1, 0], atol=1e-9)

    def test_yaxis_order(self):
        from animageo.geo.construction import Construction
        c = self._unit_circle()
        yaxis = Construction().element('yAxis').data
        p1 = intersect_Kli(c, yaxis, 1)
        p2 = intersect_Kli(c, yaxis, 2)
        assert np.allclose(p1.coords[:2], [0, -1], atol=1e-9)
        assert np.allclose(p2.coords[:2], [0, 1], atol=1e-9)

