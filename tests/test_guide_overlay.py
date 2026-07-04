"""Test: guide_style.json's overlay section stylises DSL-built elements
without a manual import-policy replay hook.

This is the end-to-end validation of Phase 5 (overlay) + Phase 4 (unit
unification) + Phase 7 (guide migration): the workaround previously
needed in ``docs/style_guide/examples/generate_svg.py`` has been
eliminated because overlay now applies to DSL elements directly.
"""
from pathlib import Path

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.style.resolver import resolve


GUIDE_STYLE = Path(__file__).resolve().parents[1] / 'docs/guide/examples/guide_style.json'


class TestGuideOverlayReachesDSL:
    def test_guide_style_exists(self):
        assert GUIDE_STYLE.exists(), f"guide style missing: {GUIDE_STYLE}"

    def test_angle_gets_arc_size_from_overlay(self):
        """An ``Angle`` built in DSL picks up ``arc_size_px: 22`` from overlay.

        Before the fix: DSL angles had empty ``ggb_raw`` → ImportPolicy
        ignored them → ``arc_size_px`` was missing → the renderer fell
        back to ``scene.style.ang_rdefault`` which was collapsed by the
        × 0.02 unit bug.
        """
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        scene.putCode("""
A = Point(0, 0)
B = Point(3, 0)
C = Point(0, 3)
alpha = Angle(B, A, C)
""")
        scene.addAllGeometry(show=True)
        angle_elem = scene.geo.element('alpha')
        assert angle_elem is not None
        # arc_size_px comes from overlay.per_type.angle.
        assert resolve(scene, angle_elem, 'arc_size_px') == 22

    def test_point_gets_size_from_overlay(self):
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        scene.putCode("A = Point(1, 2)")
        scene.addAllGeometry(show=True)
        # size_px from overlay.per_type.point.
        assert resolve(scene, scene.geo.element('A'), 'size_px') == 7

    def test_segment_stroke_from_overlay(self):
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 5)
s = Segment(A, B)
""")
        scene.addAllGeometry(show=True)
        # stroke_width_px from overlay.per_type.segment.
        assert resolve(scene, scene.geo.element('s'), 'stroke_width_px') == 2.2

    def test_ang_rshift_no_longer_collapsed(self):
        """Phase 4 regression check: ``ang_rshift`` is now in pixels."""
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        # guide_style.json says defaults.angle.arc_shift_px: 1.5.
        # Before Phase 4: 0.02 × 1.5 = 0.03 (scene-units, ~1px / ptUnit).
        # After Phase 4: 1.5 (pixels).
        assert scene.style.ang_rshift == 1.5

    def test_dsl_write_wins_over_overlay(self):
        """Explicit DSL style remains above overlay."""
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        scene.putCode("""
A = Point(0, 0)
A.style.size_px = 3
""")
        scene.addAllGeometry(show=True)
        # guide_style.json sets per_type.point.size_px = 7
        assert resolve(scene, scene.geo.element('A'), 'size_px') == 3

    def test_overlay_angle_radius_reaches_renderer(self):
        """Guide's ``overlay.angle_radius`` is kept in the canonical overlay."""
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        ar = scene.style_config.overlay.angle_radius
        assert ar.get('enabled') is True
        # exp=0.4 comes from overlay.angle_radius in guide_style.json
        assert ar.get('exp') == 0.4
        assert 'angle_radius' not in scene.style.rendering

    def test_overlay_label_placement_reaches_renderer(self):
        scene = AnimaGeoScene()
        scene.applyStyle(style=str(GUIDE_STYLE), export={"size": [520, 340]})
        lp = scene.style_config.overlay.label_placement
        assert lp.get('enabled') is True
        # distance_px=7 from overlay.label_placement
        assert lp.get('distance_px') == 7
        assert 'label_placement' not in scene.style.rendering
