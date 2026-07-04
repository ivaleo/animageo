"""Tests for Line / Ray viewport clipping.

Guards the fix that replaced a hardcoded 100×100 viewport in
``CreateMObject`` with real camera-frame bounds. The geometry-side logic
lives in ``Line.get_endpoints`` / ``Ray.get_endpoints``; the scene-side
logic lives in ``AnimaGeoScene._get_scene_bounds``. Tests cover both.
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import Line, Ray


# ── Line.get_endpoints ─────────────────────────────────────────────────

class TestLineClipping:
    def test_horizontal_line_intersects_wide_box(self):
        # y = 0, box [-5, 5] × [-3, 3]
        line = Line([0.0, 1.0], 0.0)
        corners = [(-5, -3), (5, 3)]
        endpoints = line.get_endpoints(corners)
        assert endpoints is not None
        xs = sorted(p[0] for p in endpoints)
        ys = sorted(p[1] for p in endpoints)
        assert np.isclose(xs, [-5, 5]).all()
        assert np.isclose(ys, [0, 0]).all()

    def test_vertical_line_intersects_tall_box(self):
        # x = 2, box [-10, 10] × [-10, 10]
        line = Line([1.0, 0.0], 2.0)
        corners = [(-10, -10), (10, 10)]
        endpoints = line.get_endpoints(corners)
        assert endpoints is not None
        xs = sorted(p[0] for p in endpoints)
        ys = sorted(p[1] for p in endpoints)
        assert np.isclose(xs, [2, 2]).all()
        assert np.isclose(ys, [-10, 10]).all()

    def test_diagonal_line_through_corners(self):
        # y = x, box [-4, 4] × [-4, 4]
        line = Line([-1.0, 1.0], 0.0)
        corners = [(-4, -4), (4, 4)]
        endpoints = line.get_endpoints(corners)
        assert endpoints is not None
        pts = sorted((p[0], p[1]) for p in endpoints)
        assert np.isclose(pts[0], (-4, -4)).all()
        assert np.isclose(pts[1], (4, 4)).all()

    def test_line_entirely_outside_viewport(self):
        # y = 100, far above the box [-5, 5] × [-5, 5]
        line = Line([0.0, 1.0], 100.0)
        corners = [(-5, -5), (5, 5)]
        assert line.get_endpoints(corners) is None

    def test_clipping_adapts_to_viewport_size(self):
        # Same line, different viewports: endpoints must track viewport
        line = Line([0.0, 1.0], 0.0)  # y = 0

        wide = line.get_endpoints([(-20, -5), (20, 5)])
        tall = line.get_endpoints([(-5, -20), (5, 20)])

        assert wide is not None and tall is not None
        wide_xs = sorted(p[0] for p in wide)
        tall_xs = sorted(p[0] for p in tall)
        assert np.isclose(wide_xs, [-20, 20]).all()
        assert np.isclose(tall_xs, [-5, 5]).all()

    def test_regression_not_100_unit_hardcoded_viewport(self):
        """Guard against the old bug: Line was clipped to [-50, 50] regardless
        of the actual scene. After the fix, the caller passes real bounds,
        and get_endpoints honors them.
        """
        line = Line([0.0, 1.0], 0.0)  # y = 0
        small = line.get_endpoints([(-2, -2), (2, 2)])
        assert small is not None
        xs = sorted(p[0] for p in small)
        assert np.isclose(xs, [-2, 2]).all(), (
            "endpoints must reflect the 2×2 viewport, not a 100×100 default"
        )


# ── Ray.get_endpoints ──────────────────────────────────────────────────

class TestRayClipping:
    def test_ray_clipped_to_viewport(self):
        # Ray from origin, direction +x, box [-10, 10] × [-1, 1]
        r = Ray(np.array([0.0, 0.0]), np.array([1.0, 0.0]))
        endpoints = r.get_endpoints([(-10, -1), (10, 1)])
        assert endpoints is not None
        # Start point preserved; far end at box edge
        starts = [p for p in endpoints if np.allclose(p, [0, 0])]
        ends = [p for p in endpoints if not np.allclose(p, [0, 0])]
        assert starts and ends
        assert np.isclose(ends[0][0], 10)

    def test_ray_pointing_away_returns_none_if_start_outside(self):
        # Ray from (20, 0) pointing +x; box [-5, 5] → no visible part
        r = Ray(np.array([20.0, 0.0]), np.array([1.0, 0.0]))
        endpoints = r.get_endpoints([(-5, -5), (5, 5)])
        assert endpoints is None

    def test_ray_adapts_to_viewport(self):
        r = Ray(np.array([0.0, 0.0]), np.array([1.0, 0.0]))

        short = r.get_endpoints([(-1, -1), (3, 1)])
        long = r.get_endpoints([(-1, -1), (30, 1)])

        assert short is not None and long is not None

        def farther_x(pts):
            return max(p[0] for p in pts)

        assert np.isclose(farther_x(short), 3)
        assert np.isclose(farther_x(long), 30)


# ── _get_scene_bounds integration ──────────────────────────────────────

# These tests verify the scene-side helper without running the full
# manim render loop. We use a lightweight fake camera/frame to isolate
# the geometry math from manim internals.

class _FakeFrame:
    def __init__(self, left, bottom, right, top):
        self._left = left
        self._bottom = bottom
        self._right = right
        self._top = top

    def get_left(self):   return np.array([self._left, 0, 0])
    def get_right(self):  return np.array([self._right, 0, 0])
    def get_bottom(self): return np.array([0, self._bottom, 0])
    def get_top(self):    return np.array([0, self._top, 0])


class _FakeCamera:
    def __init__(self, frame):
        self.frame = frame


class _FakeScene:
    """Minimal stand-in for AnimaGeoScene carrying only what
    ``_get_scene_bounds`` reads."""
    def __init__(self, left, bottom, right, top):
        self.camera = _FakeCamera(_FakeFrame(left, bottom, right, top))

    # Re-binds the real method so tests check the real code path.
    from animageo.animageo import AnimaGeoScene
    _get_scene_bounds = AnimaGeoScene._get_scene_bounds


class TestSceneBounds:
    def test_returns_camera_frame_with_padding(self):
        scene = _FakeScene(-8, -4, 8, 4)
        left, bottom, right, top = scene._get_scene_bounds(padding=0.5)
        assert np.isclose(left, -8.5)
        assert np.isclose(bottom, -4.5)
        assert np.isclose(right, 8.5)
        assert np.isclose(top, 4.5)

    def test_padding_defaults_are_nonzero(self):
        scene = _FakeScene(0, 0, 10, 10)
        left, bottom, right, top = scene._get_scene_bounds()
        assert left < 0
        assert bottom < 0
        assert right > 10
        assert top > 10

    def test_clipping_uses_asymmetric_frame(self):
        # Camera not centered on origin: [2, 20] × [-3, 5]
        scene = _FakeScene(2, -3, 20, 5)
        left, bottom, right, top = scene._get_scene_bounds(padding=0)
        assert (left, bottom, right, top) == (2, -3, 20, 5)

        # Line y = 1 intersects at x = 2 and x = 20.
        line = Line([0.0, 1.0], 1.0)
        endpoints = line.get_endpoints([(left, bottom), (right, top)])
        assert endpoints is not None
        xs = sorted(p[0] for p in endpoints)
        assert np.isclose(xs, [2, 20]).all()
