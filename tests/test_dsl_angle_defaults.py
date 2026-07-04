"""Regression test: DSL-built angle without explicit style keys must render.

Before the Phase 3 defensive fixes, ``CreateMObject`` indexed
``elem.style['arc_shift_px']`` and ``elem.style['tick_count']`` unconditionally.
DSL angles start with ``elem.style = {}``, so these indexes raised ``KeyError``.

After the fix:
- ``arc_shift_px`` goes through the resolver; builtin/defaults provide 0+.
- ``tick_count`` goes through the resolver; builtin defaults to 1.
- ``arc_size_px`` goes through the resolver too, so DSL angles use the same
  pixel path as imported GGB angles.
"""
import pytest

from animageo.animageo import AnimaGeoScene


class TestDSLAngleNoCrash:
    def test_plain_dsl_angle_builds(self):
        """The minimal DSL angle — no overlay, no elem.style tweaks — renders."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
C = Point(0, 5)
alpha = Angle(B, A, C)
""")
        # No style file loaded; no overlay; no explicit elem.style writes.
        # Must not crash.
        scene.addAllGeometry(show=True)

        mobj = scene.mobject('alpha')
        assert mobj is not None

    def test_dsl_angle_with_only_arc_size_px(self):
        """Explicit arc_size_px drives the pixel path."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
C = Point(0, 5)
alpha = Angle(B, A, C)
alpha.style.arc_size_px = 20
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('alpha') is not None

    def test_dsl_right_angle_marker_no_crash(self):
        """Right-angle marker path also used to require arc_shift_px."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
C = Point(0, 5)
alpha = Angle(B, A, C)
alpha.style.right_angle_marker = True
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('alpha') is not None
