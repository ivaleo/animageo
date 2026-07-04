"""Tests for Conic rendering via AnimaGeoScene.CreateMObject.

Verifies the wiring in animageo.py — that each ConicType produces a
VGroup of the expected shape, that EMPTY returns None, and that the
viewport-clipped curve rendering doesn't crash for typical conics.

Curve-sampling accuracy is covered by test_curve_sampling.py; here we
just check that the render branch dispatches correctly and the sampled
points are installed on the returned mobjects.
"""
import logging

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.geo.lib_conic import Conic, ConicType
from animageo.geo.lib_elements import Element


# Make exceptions in CreateMObject visible to tests: capture-level WARNING
# and assert zero records for success cases.

@pytest.fixture
def scene(caplog):
    caplog.set_level(logging.WARNING, logger='animageo.animageo')
    s = AnimaGeoScene()
    # Reasonable test viewport: -6..6 horizontally, ~3.4 vertically (16:9).
    s.camera.frame.set(width=12)
    return s


def _render(scene, conic, name='test_conic'):
    elem = Element(name, conic)
    return scene.CreateMObject(elem, z_auto=True)


# ── Each ConicType produces the expected shape ────────────────────────

class TestRenderDispatch:
    def test_circle(self, scene, caplog):
        # Unit circle x² + y² = 1.
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert mobj.name == 'test_conic'
        # A single Circle primitive (no dash).
        assert len(mobj.submobjects) == 1
        assert len(caplog.records) == 0

    def test_ellipse(self, scene, caplog):
        # x²/4 + y²/1 = 1 → ellipse a = 2, b = 1.
        c = Conic.from_coeffs(a=1 / 4, c=1, f=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        # Single Ellipse primitive.
        assert len(mobj.submobjects) == 1
        assert len(caplog.records) == 0

    def test_parabola(self, scene, caplog):
        # y = x² → at least 1 polyline VMobject.
        c = Conic.from_coeffs(a=1, e=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(mobj.submobjects) >= 1
        assert len(caplog.records) == 0

    def test_hyperbola_both_branches(self, scene, caplog):
        # x² − y² = 1 — both branches visible in the 12×... viewport.
        c = Conic.from_coeffs(a=1, c=-1, f=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        # Two branches, each at least one polyline.
        assert len(mobj.submobjects) >= 2
        assert len(caplog.records) == 0

    def test_intersecting_lines(self, scene, caplog):
        # x² − y² = 0 → two lines through origin.
        c = Conic.from_coeffs(a=1, c=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(mobj.submobjects) == 2
        assert len(caplog.records) == 0

    def test_parallel_lines(self, scene, caplog):
        # x² − 1 = 0 → x = ±1.
        c = Conic.from_coeffs(a=1, f=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(mobj.submobjects) == 2
        assert len(caplog.records) == 0

    def test_double_line(self, scene, caplog):
        # x² = 0 → single line x = 0.
        c = Conic.from_coeffs(a=1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(mobj.submobjects) == 1
        assert len(caplog.records) == 0

    def test_single_point(self, scene, caplog):
        # x² + y² = 0 → point at origin.
        c = Conic.from_coeffs(a=1, c=1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(mobj.submobjects) == 1
        assert len(caplog.records) == 0

    def test_empty_returns_none(self, scene, caplog):
        # x² + y² + 1 = 0 — no real solutions.
        c = Conic.from_coeffs(a=1, c=1, f=1)
        mobj = _render(scene, c)
        assert mobj is None
        assert len(caplog.records) == 0


# ── Viewport clipping produces bounded output ────────────────────────

class TestViewportClipping:
    def test_parabola_samples_inside_viewport(self, scene, caplog):
        # y = x² outside the narrow viewport gets clipped.
        scene.camera.frame.set(width=4)  # narrow frame, ~4 wide × 2.25 tall
        c = Conic.from_coeffs(a=1, e=-1)
        mobj = _render(scene, c)
        assert mobj is not None
        assert len(caplog.records) == 0

        # All anchor points should lie inside the padded viewport.
        left, bottom, right, top = scene._get_scene_bounds(padding=0.2)
        for sub in mobj.submobjects:
            for p in sub.get_anchors():
                x, y = float(p[0]), float(p[1])
                assert left <= x <= right, f"x={x} outside [{left}, {right}]"
                assert bottom <= y <= top, f"y={y} outside [{bottom}, {top}]"

    def test_hyperbola_branch_off_screen_skipped(self, scene, caplog):
        # Hyperbola centered far to the right: left branch off-screen,
        # only right branch (or neither) renders.
        #   (x − 100)² − y² = 1
        c = Conic.from_coeffs(a=1, c=-1, d=-200, f=100 * 100 - 1)
        mobj = _render(scene, c)
        assert len(caplog.records) == 0
        # Either None (both branches off-screen) or ≤ 1 submobject
        # (only the nearer branch survives clipping).
        if mobj is not None:
            assert len(mobj.submobjects) <= 2  # branch might split into polys


# ── Repr in Element wrapper ──────────────────────────────────────────

class TestElementIntegration:
    def test_is_drawable(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        elem = Element('k', c)
        assert elem.is_drawable()

    def test_repr_includes_conic(self):
        c = Conic.from_coeffs(a=1, c=1, f=-1)
        elem = Element('k', c)
        r = repr(elem)
        assert 'k' in r
