"""Tests for curve_sampling.py.

Covers:
- `_clip_segment_to_box` (Liang–Barsky) across the 8 classic cases
  (both inside, both outside but crosses, both outside no crossing,
  partial clips from each side).
- `_split_by_viewport` polyline splitting at viewport crossings.
- `sample_parametric` adaptive refinement + hard cap + viewport clipping.
- `viewport_aabb_in_frame` for rotated and translated frames.
- `viewport_t_ranges_parabola` for vertex below/inside/above viewport.
- `viewport_t_range_hyperbola_branch` for both branches.
- Integration: render a parabola with the full pipeline and verify
  all returned points satisfy y = x²/(4p) within tolerance.
"""
import numpy as np
import pytest

from animageo.geo.curve_sampling import (
    sample_parametric,
    _clip_segment_to_box,
    _split_by_viewport,
    viewport_aabb_in_frame,
    viewport_t_ranges_parabola,
    viewport_t_range_hyperbola_branch,
    make_parabola_param,
    make_hyperbola_branch_param,
    make_ellipse_param,
)


VIEWPORT = (-2.0, -2.0, 2.0, 2.0)   # [-2, 2] × [-2, 2]


# ── _clip_segment_to_box ──────────────────────────────────────────────

class TestClipSegment:
    def test_both_inside(self):
        cp = _clip_segment_to_box(
            np.array([0.0, 0.0]), np.array([1.0, 1.0]),
            -2, -2, 2, 2,
        )
        assert cp is not None
        cp1, cp2 = cp
        assert np.allclose(cp1, [0, 0])
        assert np.allclose(cp2, [1, 1])

    def test_both_outside_no_intersection(self):
        cp = _clip_segment_to_box(
            np.array([3.0, 3.0]), np.array([4.0, 4.0]),
            -2, -2, 2, 2,
        )
        assert cp is None

    def test_both_outside_crossing(self):
        # Segment from (-3, 0) to (3, 0) crosses the box left→right.
        cp = _clip_segment_to_box(
            np.array([-3.0, 0.0]), np.array([3.0, 0.0]),
            -2, -2, 2, 2,
        )
        assert cp is not None
        cp1, cp2 = cp
        assert np.allclose(cp1, [-2, 0])
        assert np.allclose(cp2, [2, 0])

    def test_p1_inside_p2_outside(self):
        cp = _clip_segment_to_box(
            np.array([0.0, 0.0]), np.array([5.0, 0.0]),
            -2, -2, 2, 2,
        )
        cp1, cp2 = cp
        assert np.allclose(cp1, [0, 0])
        assert np.allclose(cp2, [2, 0])

    def test_p1_outside_p2_inside(self):
        cp = _clip_segment_to_box(
            np.array([-5.0, 0.0]), np.array([0.0, 0.0]),
            -2, -2, 2, 2,
        )
        cp1, cp2 = cp
        assert np.allclose(cp1, [-2, 0])
        assert np.allclose(cp2, [0, 0])

    def test_diagonal_clip(self):
        # Segment from (-3, -3) to (3, 3) crosses box at (-2, -2) to (2, 2).
        cp = _clip_segment_to_box(
            np.array([-3.0, -3.0]), np.array([3.0, 3.0]),
            -2, -2, 2, 2,
        )
        cp1, cp2 = cp
        assert np.allclose(cp1, [-2, -2])
        assert np.allclose(cp2, [2, 2])

    def test_parallel_to_edge_inside(self):
        # Horizontal segment at y=1, entirely inside box.
        cp = _clip_segment_to_box(
            np.array([-1.0, 1.0]), np.array([1.0, 1.0]),
            -2, -2, 2, 2,
        )
        cp1, cp2 = cp
        assert np.allclose(cp1, [-1, 1])
        assert np.allclose(cp2, [1, 1])

    def test_parallel_to_edge_outside(self):
        # Horizontal segment at y=3, parallel to top edge and above it.
        cp = _clip_segment_to_box(
            np.array([-1.0, 3.0]), np.array([1.0, 3.0]),
            -2, -2, 2, 2,
        )
        assert cp is None


# ── _split_by_viewport ────────────────────────────────────────────────

class TestSplitByViewport:
    def test_empty_polyline(self):
        assert _split_by_viewport(np.array([[0, 0]]), VIEWPORT) == []
        assert _split_by_viewport(np.array([]).reshape(0, 2), VIEWPORT) == []

    def test_entirely_inside(self):
        pts = np.array([[0.0, 0.0], [1.0, 1.0], [-1.0, -1.0]])
        polys = _split_by_viewport(pts, VIEWPORT, pad=0.0)
        assert len(polys) == 1
        assert polys[0].shape == (3, 2)

    def test_entirely_outside(self):
        pts = np.array([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0]])
        polys = _split_by_viewport(pts, VIEWPORT, pad=0.0)
        assert polys == []

    def test_one_crossing_enter(self):
        # From outside, enters viewport.
        pts = np.array([[-3.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
        polys = _split_by_viewport(pts, VIEWPORT, pad=0.0)
        assert len(polys) == 1
        assert np.allclose(polys[0][0], [-2, 0])  # clipped at left edge
        assert np.allclose(polys[0][-1], [1, 0])

    def test_dip_in_and_out(self):
        # Enters and exits: 3 polylines will reduce to 1 if contiguous.
        pts = np.array([[-5.0, 0.0], [-1.0, 0.0], [1.0, 0.0], [5.0, 0.0]])
        polys = _split_by_viewport(pts, VIEWPORT, pad=0.0)
        assert len(polys) == 1
        # Boundary-enter, through, boundary-exit
        assert np.allclose(polys[0][0], [-2, 0])
        assert np.allclose(polys[0][-1], [2, 0])

    def test_out_in_out_in_out(self):
        # Curve enters, exits, re-enters, exits → two polylines.
        pts = np.array([
            [-5.0, 0.0], [0.0, 0.0], [-5.0, 0.0],  # dip in-out via midpoint
            [5.0, 0.0], [0.0, 1.5], [5.0, 0.0],    # re-enter and exit
        ])
        polys = _split_by_viewport(pts, VIEWPORT, pad=0.0)
        assert len(polys) >= 2  # exact split depends on geometry


# ── viewport_aabb_in_frame ─────────────────────────────────────────────

class TestViewportAABBInFrame:
    def test_identity_frame(self):
        # Frame origin at (0,0), axes aligned with world.
        u_min, v_min, u_max, v_max = viewport_aabb_in_frame(
            VIEWPORT, origin=[0, 0], axis_u=[1, 0], axis_v=[0, 1],
        )
        assert np.isclose(u_min, -2) and np.isclose(u_max, 2)
        assert np.isclose(v_min, -2) and np.isclose(v_max, 2)

    def test_translated_frame(self):
        # Origin at (1, 0): u-range shifts by -1.
        u_min, v_min, u_max, v_max = viewport_aabb_in_frame(
            VIEWPORT, origin=[1, 0], axis_u=[1, 0], axis_v=[0, 1],
        )
        assert np.isclose(u_min, -3) and np.isclose(u_max, 1)
        assert np.isclose(v_min, -2) and np.isclose(v_max, 2)

    def test_rotated_frame_45deg(self):
        # Rotate 45°: u = (x + y)/√2, v = (-x + y)/√2.
        s = 1 / np.sqrt(2)
        u_min, v_min, u_max, v_max = viewport_aabb_in_frame(
            VIEWPORT, origin=[0, 0], axis_u=[s, s], axis_v=[-s, s],
        )
        # AABB corners project to u ∈ [-2√2, 2√2] approx.
        assert np.isclose(u_min, -2 * np.sqrt(2))
        assert np.isclose(u_max, 2 * np.sqrt(2))


# ── Parabola t-range ───────────────────────────────────────────────────

class TestParabolaTRanges:
    def test_vertex_inside_viewport(self):
        # y = x² vertex at origin, inside [-2, 2]².
        # p = 0.25 (y = x² → u² = 4·0.25·v), axis = (0, 1), perp = (1, 0).
        ranges = viewport_t_ranges_parabola(
            vertex=[0, 0], axis=[0, 1], perp=[1, 0],
            focal_parameter=0.25, viewport=VIEWPORT,
        )
        assert len(ranges) == 1
        t_min, t_max = ranges[0]
        # u range from AABB: [-2, 2], v_max = 2, u_bound = 2√(0.25·2) = √2.
        # Intersection: [max(-2, -√2), min(2, √2)] = [-√2, √2].
        assert np.isclose(t_min, -np.sqrt(2))
        assert np.isclose(t_max, np.sqrt(2))

    def test_vertex_below_viewport(self):
        # y = x²/(4p) - 10, p = 0.25, vertex (0, -10). Wide viewport
        # needed so parabola's u = ±2√(p·v) is inside. At y = -2 (v = 8):
        # |x| = 2√2 ≈ 2.83. At y = 2 (v = 12): |x| = 2√3 ≈ 3.46. So the
        # curve enters the viewport only in u ∈ [-3.46, -2.83] ∪ [2.83, 3.46].
        wide = (-5.0, -2.0, 5.0, 2.0)
        ranges = viewport_t_ranges_parabola(
            vertex=[0, -10], axis=[0, 1], perp=[1, 0],
            focal_parameter=0.25, viewport=wide,
        )
        assert len(ranges) == 2
        # Left and right ranges are symmetric about u=0.
        left, right = sorted(ranges)
        assert left[0] < left[1] < 0
        assert 0 < right[0] < right[1]
        assert np.isclose(-left[1], right[0])   # symmetry of inner u-bound
        assert np.isclose(-left[0], right[1])   # symmetry of outer u-bound

    def test_curve_entirely_above_viewport(self):
        # Vertex at (0, 10), opens up: v_max = 2 - 10 = -8 → empty.
        ranges = viewport_t_ranges_parabola(
            vertex=[0, 10], axis=[0, 1], perp=[1, 0],
            focal_parameter=0.25, viewport=VIEWPORT,
        )
        assert ranges == []

    def test_narrow_focal_parameter(self):
        # p = 0.01 → narrow parabola. y=x²/(0.04)·…  With u_max = 2,
        # at u=2: v = 4/(0.04) = 100. Way above v_max=2 → u-bound tight.
        ranges = viewport_t_ranges_parabola(
            vertex=[0, 0], axis=[0, 1], perp=[1, 0],
            focal_parameter=0.01, viewport=VIEWPORT,
        )
        assert len(ranges) == 1
        t_min, t_max = ranges[0]
        # u_bound = 2·√(0.01·2) = 2·√0.02 ≈ 0.283.
        assert np.isclose(t_max, 2 * np.sqrt(0.02))


# ── Hyperbola t-range ──────────────────────────────────────────────────

class TestHyperbolaTRange:
    def test_right_branch_visible(self):
        # Hyperbola x² - y² = 1, right branch (u ≥ 1). Viewport [-2, 2]².
        # u_max = 2 → cosh_limit = 2 → t_u = acosh(2) ≈ 1.317.
        # v_abs_max = 2 → t_v = asinh(2/1) = asinh(2) ≈ 1.444.
        # t_bound = min(acosh(2), asinh(2)) = acosh(2).
        r = viewport_t_range_hyperbola_branch(
            center=[0, 0], axis_u=[1, 0], axis_v=[0, 1],
            a=1.0, b=1.0, branch_sign=+1, viewport=VIEWPORT,
        )
        assert r is not None
        t_min, t_max = r
        assert np.isclose(t_max, np.arccosh(2.0))
        assert np.isclose(t_min, -np.arccosh(2.0))

    def test_left_branch_visible(self):
        r = viewport_t_range_hyperbola_branch(
            center=[0, 0], axis_u=[1, 0], axis_v=[0, 1],
            a=1.0, b=1.0, branch_sign=-1, viewport=VIEWPORT,
        )
        assert r is not None
        t_min, t_max = r
        assert np.isclose(t_max, np.arccosh(2.0))

    def test_right_branch_off_screen(self):
        # Hyperbola at x=5, branch at u ≥ 5+1=6, viewport stops at x=2.
        r = viewport_t_range_hyperbola_branch(
            center=[5, 0], axis_u=[1, 0], axis_v=[0, 1],
            a=1.0, b=1.0, branch_sign=+1, viewport=VIEWPORT,
        )
        assert r is None


# ── sample_parametric ─────────────────────────────────────────────────

class TestSampleParametric:
    def test_straight_line_no_clipping(self):
        # x = t, y = 0, t ∈ [-1, 1].
        polys = sample_parametric(
            lambda t: (t, 0.0),
            t_range=(-1, 1),
            viewport=None,
            initial_samples=5, max_samples=10,
        )
        assert len(polys) == 1
        assert polys[0].shape[0] >= 5

    def test_straight_line_clipped(self):
        # x = t, y = 0, t ∈ [-5, 5]. Viewport [-2, 2], no padding.
        polys = sample_parametric(
            lambda t: (t, 0.0),
            t_range=(-5, 5),
            viewport=VIEWPORT,
            initial_samples=11, max_samples=100, segment_mu=1.0,
            viewport_pad=0.0,
        )
        assert len(polys) == 1
        first = polys[0][0]
        last = polys[0][-1]
        assert np.isclose(first[0], -2, atol=1e-9)
        assert np.isclose(last[0], 2, atol=1e-9)

    def test_hard_cap_respected(self):
        # Pathological: very oscillatory curve that always needs more samples.
        polys = sample_parametric(
            lambda t: (t, np.sin(100 * t)),
            t_range=(-1, 1),
            viewport=None,
            initial_samples=10, max_samples=50, segment_mu=0.0001,
        )
        total = sum(p.shape[0] for p in polys)
        # Each polyline shares endpoints with viewport crossings; underlying
        # sample count shouldn't exceed max_samples.
        assert total <= 50 + 5  # tiny slack for boundary interpolations

    def test_adaptive_refines_curved_segments(self):
        # Half-circle at high curvature: adaptive should add many samples.
        polys = sample_parametric(
            lambda t: (np.cos(t), np.sin(t)),
            t_range=(0, np.pi),
            viewport=None,
            initial_samples=4, max_samples=200, segment_mu=0.05,
        )
        total = sum(p.shape[0] for p in polys)
        # A circle discretized with 0.05 MU max segment needs at least
        # π/0.05 ≈ 63 samples.
        assert total >= 50

    def test_empty_when_curve_entirely_outside(self):
        polys = sample_parametric(
            lambda t: (10.0 + t, 10.0),
            t_range=(0, 1),
            viewport=VIEWPORT,
            initial_samples=5, max_samples=20,
        )
        assert polys == []


# ── Integration: full parabola rendering ──────────────────────────────

class TestIntegrationParabola:
    def test_y_equals_x_squared(self):
        # y = x²: vertex (0, 0), axis +y, perp +x, p = 0.25.
        vertex = np.array([0, 0])
        axis = np.array([0, 1])
        perp = np.array([1, 0])
        p = 0.25

        ranges = viewport_t_ranges_parabola(vertex, axis, perp, p, VIEWPORT)
        assert len(ranges) == 1

        param = make_parabola_param(vertex, axis, perp, p)
        polys = sample_parametric(
            param, ranges[0], VIEWPORT,
            initial_samples=32, max_samples=200, segment_mu=0.05,
        )
        assert len(polys) >= 1

        # Every returned point satisfies y ≈ x² within tolerance
        # (allowing for viewport-edge interpolation tweaks).
        for poly in polys:
            for x, y in poly:
                # Points exactly at the top edge y = 2 + pad are clipped
                # linearly → small error acceptable.
                if abs(y - 2.1) < 0.01:  # at padded top edge
                    continue
                assert np.isclose(y, x * x, atol=0.05), (
                    f"point ({x}, {y}) not on y=x² within 0.05 "
                    f"(error {abs(y - x * x)})"
                )


class TestIntegrationHyperbola:
    def test_unit_hyperbola_right_branch(self):
        # x² - y² = 1, right branch (u ≥ 1).
        center = np.array([0, 0])
        axis_u = np.array([1, 0])
        axis_v = np.array([0, 1])
        a = b = 1.0

        r = viewport_t_range_hyperbola_branch(
            center, axis_u, axis_v, a, b, +1, VIEWPORT,
        )
        assert r is not None

        param = make_hyperbola_branch_param(center, axis_u, axis_v, a, b, +1)
        polys = sample_parametric(
            param, r, VIEWPORT,
            initial_samples=32, max_samples=200, segment_mu=0.05,
        )
        assert len(polys) >= 1

        for poly in polys:
            for x, y in poly:
                # x² - y² = 1 for every sample on the curve.
                residual = x * x - y * y - 1
                assert abs(residual) < 0.05, (
                    f"point ({x}, {y}) not on x²-y²=1 within 0.05 "
                    f"(residual {residual})"
                )


class TestIntegrationEllipse:
    def test_unit_circle_via_ellipse_param(self):
        param = make_ellipse_param(
            center=[0, 0], a=1, b=1, rotation=0,
        )
        polys = sample_parametric(
            param, t_range=(0, 2 * np.pi), viewport=VIEWPORT,
            initial_samples=32, max_samples=200, segment_mu=0.05,
        )
        assert len(polys) >= 1
        for poly in polys:
            for x, y in poly:
                r = np.sqrt(x * x + y * y)
                assert np.isclose(r, 1, atol=0.05)


class TestEdgePointDivisionGuard:
    """Near-coincident corner values in marching-squares cells must not
    produce ``inf``/``nan`` from the linear-interpolation step."""

    def test_equal_corners_collapse_to_midpoint(self):
        from animageo.geo.curve_sampling import _edge_point
        # f[0] = f[1] (bottom edge corners equal) → denom zero; guard
        # returns the midpoint instead of propagating an inf.
        x, y = _edge_point(0, x_l=0.0, x_r=2.0, y_b=5.0, y_t=9.0,
                           f=[1e-30, 1e-30, 2.0, 3.0])
        assert np.isfinite(x) and np.isfinite(y)
        assert x == pytest.approx(1.0)  # midpoint of [0, 2]
        assert y == pytest.approx(5.0)  # bottom edge

    def test_nonzero_denom_preserves_linear_interp(self):
        from animageo.geo.curve_sampling import _edge_point
        # f00 = -1, f10 = +1 → zero at midpoint.
        x, y = _edge_point(0, x_l=0.0, x_r=2.0, y_b=0.0, y_t=1.0,
                           f=[-1.0, 1.0, 5.0, 5.0])
        assert x == pytest.approx(1.0)
        assert y == pytest.approx(0.0)
