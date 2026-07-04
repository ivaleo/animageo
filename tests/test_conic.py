"""Tests for Conic (lib_conic.py).

Covers matrix-based classification into all 9 ConicType branches,
canonical parametrizations for non-degenerate types (circle, ellipse,
parabola, hyperbola), degenerate decomposition into lines/points, and
transform invariance under translate/scale.

The two matrix fixtures `ggb_parabola_g` and `ggb_circle_h` are lifted
verbatim from examples/func/func5/geogebra.xml so we exercise the same
matrix layout GGB emits.
"""
import numpy as np
import pytest

from animageo.geo.lib_conic import Conic, ConicType
from animageo.geo.lib_elements import Line, Point


# ── Classification ─────────────────────────────────────────────────────

class TestClassification:
    def test_unit_circle(self):
        # x² + y² − 1 = 0
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert c.type == ConicType.CIRCLE

    def test_offset_circle(self):
        # (x − 2)² + (y + 3)² − 4 = 0  →  x² − 4x + 4 + y² + 6y + 9 − 4 = 0
        c = Conic.from_coeffs(a=1, c=1, d=-4, e=6, f=9)
        assert c.type == ConicType.CIRCLE

    def test_ellipse(self):
        # x²/4 + y²/9 − 1 = 0
        c = Conic.from_coeffs(a=1 / 4, c=1 / 9, f=-1)
        assert c.type == ConicType.ELLIPSE

    def test_rotated_ellipse(self):
        # Start with axis-aligned ellipse x²/4 + y²/9 = 1, rotate 30°.
        # Use the defining matrix M' = Rᵀ·M·R.
        M_axis = np.diag([1 / 4, 1 / 9, -1])
        theta = np.pi / 6
        cs, sn = np.cos(theta), np.sin(theta)
        R = np.array([[cs, -sn, 0], [sn, cs, 0], [0, 0, 1]])
        M_rot = R.T @ M_axis @ R
        c = Conic(M_rot)
        assert c.type == ConicType.ELLIPSE

    def test_parabola(self):
        # y = x²  →  x² − y = 0
        c = Conic.from_coeffs(a=1, e=-1)
        assert c.type == ConicType.PARABOLA

    def test_hyperbola(self):
        # x² − y² − 1 = 0
        c = Conic.from_coeffs(a=1, c=-1, f=-1)
        assert c.type == ConicType.HYPERBOLA

    def test_intersecting_lines(self):
        # (x − y)(x + y) = x² − y² = 0
        c = Conic.from_coeffs(a=1, c=-1)
        assert c.type == ConicType.INTERSECTING_LINES

    def test_parallel_lines(self):
        # x² − 1 = 0  →  x = ±1
        c = Conic.from_coeffs(a=1, f=-1)
        assert c.type == ConicType.PARALLEL_LINES

    def test_double_line(self):
        # x² = 0  →  x = 0 (rank-1 matrix)
        c = Conic.from_coeffs(a=1)
        assert c.type == ConicType.DOUBLE_LINE

    def test_single_point(self):
        # x² + y² = 0  →  only (0, 0) on ℝ²
        c = Conic.from_coeffs(a=1, c=1)
        assert c.type == ConicType.POINT

    def test_empty_imaginary_ellipse(self):
        # x² + y² + 1 = 0  →  no real points
        c = Conic.from_coeffs(a=1, c=1, f=1)
        assert c.type == ConicType.EMPTY

    def test_empty_imaginary_parallel(self):
        # x² + 1 = 0  →  no real points
        c = Conic.from_coeffs(a=1, f=1)
        assert c.type == ConicType.EMPTY


# ── GGB matrix fixtures ────────────────────────────────────────────────

class TestGGBMatrix:
    """Matrices copied verbatim from examples/func/func5/geogebra.xml."""

    def test_ggb_circle_h(self):
        # <matrix A0="1" A1="1" A2="-4" A3="0" A4="0" A5="0"/>
        # h: x² + y² = 4
        c = Conic.from_ggb_matrix(A0=1, A1=1, A2=-4, A3=0, A4=0, A5=0)
        assert c.type == ConicType.CIRCLE
        center, radius = c.as_circle()
        assert np.allclose(center, [0, 0])
        assert np.isclose(radius, 2)

    def test_ggb_parabola_g(self):
        # <matrix A0="-1" A1="0" A2="1" A3="0" A4="0" A5="0.5"/>
        # g: y = x² − 1  (written as −x² + y + 1 = 0)
        c = Conic.from_ggb_matrix(A0=-1, A1=0, A2=1, A3=0, A4=0, A5=0.5)
        assert c.type == ConicType.PARABOLA
        params = c.as_parabola()
        assert np.allclose(params['vertex'], [0, -1], atol=1e-9)
        # Opens upward: axis pointing +y.
        assert np.allclose(params['axis'], [0, 1], atol=1e-9)
        # For y = x², a = 1 → focal parameter p = 1/(4·a) = 0.25.
        assert np.isclose(params['focal_parameter'], 0.25)


# ── Canonical parametrizations ────────────────────────────────────────

class TestCanonicalParams:
    def test_circle_center_and_radius(self):
        # (x − 3)² + (y + 2)² = 25
        c = Conic.from_coeffs(a=1, c=1, d=-6, e=4, f=9 + 4 - 25)
        center, radius = c.as_circle()
        assert np.allclose(center, [3, -2])
        assert np.isclose(radius, 5)

    def test_ellipse_axis_aligned(self):
        # x²/16 + y²/9 = 1, a = 4, b = 3, rotation = 0.
        c = Conic.from_coeffs(a=1 / 16, c=1 / 9, f=-1)
        e = c.as_ellipse()
        assert np.allclose(e['center'], [0, 0])
        # Convention: a ≥ b.
        a, b = e['semi_axes']
        assert np.isclose(a, 4)
        assert np.isclose(b, 3)
        # rotation ∈ [0, π). Axis-aligned ellipse may give 0 or π/2
        # depending on eigenvector ordering; both are correct.
        assert (np.isclose(e['rotation'], 0, atol=1e-9)
                or np.isclose(e['rotation'], np.pi / 2, atol=1e-9))

    def test_ellipse_offset(self):
        # ((x − 1)/2)² + ((y − 3)/5)² = 1 → a = 5, b = 2, center = (1, 3).
        # Multiply out: (x−1)²/4 + (y−3)²/25 − 1 = 0.
        c = Conic.from_coeffs(
            a=1 / 4, c=1 / 25, d=-2 / 4, e=-6 / 25,
            f=1 / 4 + 9 / 25 - 1,
        )
        e = c.as_ellipse()
        assert np.allclose(e['center'], [1, 3], atol=1e-9)
        a, b = e['semi_axes']
        assert np.isclose(a, 5)
        assert np.isclose(b, 2)

    def test_hyperbola_axis_aligned(self):
        # x²/4 − y²/9 = 1, transverse axis along x.
        c = Conic.from_coeffs(a=1 / 4, c=-1 / 9, f=-1)
        h = c.as_hyperbola()
        assert np.allclose(h['center'], [0, 0])
        a, b = h['semi_axes']
        # Transverse (a) along rotation direction; convention says a² > 0.
        assert np.isclose(a, 2)
        assert np.isclose(b, 3)

    def test_parabola_shifted(self):
        # y = (x − 2)² + 3  →  x² − 4x + 4 − y + 3 = 0
        #                       x² − 4x − y + 7 = 0
        c = Conic.from_coeffs(a=1, d=-4, e=-1, f=7)
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [2, 3], atol=1e-9)
        assert np.allclose(p['axis'], [0, 1], atol=1e-9)
        assert np.isclose(p['focal_parameter'], 0.25)

    def test_parabola_opens_down(self):
        # y = −(x + 1)² + 2  →  x² + 2x + 1 + y − 2 = 0
        #                       x² + 2x + y − 1 = 0
        c = Conic.from_coeffs(a=1, d=2, e=1, f=-1)
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [-1, 2], atol=1e-9)
        assert np.allclose(p['axis'], [0, -1], atol=1e-9)

    def test_parabola_rotated_45(self):
        # (x − y)² + (x + y) = 0 expands to
        # x² − 2xy + y² + x + y = 0.
        # Let u = (x − y)/√2, v = (x + y)/√2. Then u² + v/√2 · √2 = 0, so
        # u² = −v/√2 · … — enough: just check type + that vertex is origin
        # and axis is along (1, 1)/√2 direction (up to sign).
        c = Conic.from_coeffs(a=1, b=-2, c=1, d=1, e=1)
        assert c.type == ConicType.PARABOLA
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [0, 0], atol=1e-9)
        # axis should be parallel to (1, 1) up to sign
        axis = p['axis']
        assert np.isclose(abs(axis[0]), abs(axis[1]))
        # Focal parameter is positive.
        assert p['focal_parameter'] > 0


# ── Degenerate decomposition ──────────────────────────────────────────

class TestDegenerateDecomposition:
    def test_intersecting_at_origin(self):
        # x² − y² = (x − y)(x + y) = 0
        c = Conic.from_coeffs(a=1, c=-1)
        lines = c.as_lines()
        assert len(lines) == 2
        # Both pass through origin (line orientation sign doesn't matter).
        for l in lines:
            assert l.contains(np.array([0.0, 0.0]))
        # The two components are x = y and x = −y. Compare via Line.equivalent
        # so we don't depend on normal-direction sign.
        expected_lines = [Line([1, -1], 0), Line([1, 1], 0)]
        for el in expected_lines:
            assert any(l.equivalent(el) for l in lines), (
                f"No line equivalent to {el} found in {lines}"
            )

    def test_intersecting_at_point(self):
        # (x − 1)·(y − 2) = 0  →  xy − 2x − y + 2 = 0
        c = Conic.from_coeffs(b=1, d=-2, e=-1, f=2)
        assert c.type == ConicType.INTERSECTING_LINES
        lines = c.as_lines()
        assert len(lines) == 2
        # Both pass through (1, 2).
        for l in lines:
            assert l.contains(np.array([1.0, 2.0]))

    def test_parallel_lines_x(self):
        # x² − 1 = 0  →  x = ±1
        c = Conic.from_coeffs(a=1, f=-1)
        lines = c.as_lines()
        assert len(lines) == 2
        cs = sorted([float(l.offset) for l in lines])
        assert cs == pytest.approx([-1.0, 1.0], abs=1e-9)
        for l in lines:
            assert np.allclose(l.normal, [1, 0])

    def test_double_line(self):
        # x² = 0  →  x = 0 (single line, multiplicity 2)
        c = Conic.from_coeffs(a=1)
        lines = c.as_lines()
        assert len(lines) == 1
        assert np.allclose(lines[0].normal, [1, 0])
        assert np.isclose(lines[0].offset, 0)

    def test_single_point(self):
        # x² + y² = 0  →  only (0, 0)
        c = Conic.from_coeffs(a=1, c=1)
        p = c.as_point()
        assert p is not None
        assert np.allclose(p.coords, [0, 0])

    def test_single_point_offset(self):
        # (x − 2)² + (y + 1)² = 0  →  only (2, −1)
        c = Conic.from_coeffs(a=1, c=1, d=-4, e=2, f=5)
        assert c.type == ConicType.POINT
        p = c.as_point()
        assert np.allclose(p.coords, [2, -1], atol=1e-9)


# ── Transforms ────────────────────────────────────────────────────────

class TestTransforms:
    def test_translate_circle(self):
        # Unit circle, translate by (3, −2) → circle at (3, −2), r = 1.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        c.translate(np.array([3, -2]))
        assert c.type == ConicType.CIRCLE
        center, r = c.as_circle()
        assert np.allclose(center, [3, -2], atol=1e-9)
        assert np.isclose(r, 1)

    def test_translate_parabola(self):
        # y = x² translated by (2, 3) → y = (x − 2)² + 3 (vertex at (2, 3)).
        c = Conic.from_coeffs(a=1, e=-1)
        c.translate(np.array([2, 3]))
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [2, 3], atol=1e-9)
        assert np.allclose(p['axis'], [0, 1], atol=1e-9)

    def test_scale_circle(self):
        # Unit circle, scale by 2 → circle r = 2.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        c.scale(2)
        center, r = c.as_circle()
        assert np.allclose(center, [0, 0])
        assert np.isclose(r, 2)

    def test_scale_ellipse(self):
        # x²/4 + y²/9 = 1, scale by 3 → x²/36 + y²/81 = 1.
        c = Conic.from_coeffs(a=1 / 4, c=1 / 9, f=-1)
        c.scale(3)
        e = c.as_ellipse()
        a, b = e['semi_axes']
        assert np.isclose(a, 9)
        assert np.isclose(b, 6)


# ── Evaluate / contains ───────────────────────────────────────────────

class TestEvaluate:
    def test_unit_circle_on_curve(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert np.isclose(c.evaluate(1, 0), 0)
        assert np.isclose(c.evaluate(0, 1), 0)
        assert np.isclose(c.evaluate(-1, 0), 0)

    def test_unit_circle_inside_outside(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        # Inside: x² + y² − 1 < 0.
        assert c.evaluate(0, 0) < 0
        # Outside: > 0.
        assert c.evaluate(2, 0) > 0

    def test_contains(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert c.contains([1, 0])
        assert c.contains([0, -1])
        assert not c.contains([0, 0])

    def test_parabola_on_curve(self):
        # y = x²
        c = Conic.from_coeffs(a=1, e=-1)
        for x in (-2.0, -0.5, 0.0, 0.3, 1.0):
            assert c.contains([x, x * x])


# ── Equivalence ───────────────────────────────────────────────────────

class TestEquivalent:
    def test_same_matrix(self):
        M = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]], dtype=float)
        assert Conic(M).equivalent(Conic(M))

    def test_scalar_multiple(self):
        c1 = Conic.from_coeffs(a=1, c=1, f=-1)
        c2 = Conic.from_coeffs(a=2, c=2, f=-2)  # same curve, M × 2
        assert c1.equivalent(c2)

    def test_different_curve(self):
        c1 = Conic.from_coeffs(a=1, c=1, f=-1)    # unit circle
        c2 = Conic.from_coeffs(a=1, c=1, f=-4)    # radius-2 circle
        assert not c1.equivalent(c2)

    def test_not_a_conic(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert not c.equivalent("not a conic")
        assert not c.equivalent(None)


# ── Style defaults ────────────────────────────────────────────────────

class TestStyleDefaults:
    def test_style_initialized(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        assert isinstance(c.style, dict)
        assert c.style.get('fill_opacity') == 0
        assert 'z_index' in c.style


# ── Re-export from lib_elements ──────────────────────────────────────

class TestReExport:
    def test_import_from_lib_elements(self):
        from animageo.geo.lib_elements import Conic as C2, ConicType as CT2
        assert C2 is Conic
        assert CT2 is ConicType

    def test_star_import(self):
        # Ensure `from animageo.geo.lib_elements import *` picks up Conic.
        ns = {}
        exec("from animageo.geo.lib_elements import *", ns)
        assert 'Conic' in ns
        assert 'ConicType' in ns
