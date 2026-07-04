"""Phase 3 (partial): CreateMObject preamble colour/opacity reads through resolver.

Sanity-check that migrating 5 fields (stroke, fill, stroke_opacity,
fill_opacity, label_color) from ``elem.style.get(k, scene.style.X)`` to
``resolve(scene, elem, k)`` produces identical values for GGB-imported
elements (where elem.style already carries explicit colours) AND for
DSL-built elements (where the resolver consults builtin.json).
"""
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.style.resolver import resolve


class _Probe:
    """Mini-scene built around Construction for resolver tests."""
    def __init__(self):
        self.scene = AnimaGeoScene()


class TestPreambleResolverGGBCompatible:
    def test_dsl_point_stroke_fill_from_builtin(self):
        scene = AnimaGeoScene()
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)

        a = scene.geo.element('A')
        # Point has fill=presets.color.strong in builtin → resolves to BLACK.
        assert resolve(scene, a, 'fill') == '#000000'
        # stroke same.
        assert resolve(scene, a, 'stroke') == '#000000'
        # stroke_opacity, fill_opacity = 1.
        assert resolve(scene, a, 'stroke_opacity') == 1
        assert resolve(scene, a, 'fill_opacity') == 1

    def test_dsl_segment_colours(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 5)
s = Segment(A, B)
""")
        scene.addAllGeometry(show=True)

        s = scene.geo.element('s')
        # Segments: stroke presets.color.strong, fill presets.color.background (unused).
        assert resolve(scene, s, 'stroke') == '#000000'
        assert resolve(scene, s, 'fill') == '#ffffff'
        assert resolve(scene, s, 'label_color') == '#000000'

    def test_dsl_angle_colours(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
C = Point(0, 5)
alpha = Angle(B, A, C)
""")
        scene.addAllGeometry(show=True)

        ang = scene.geo.element('alpha')
        assert resolve(scene, ang, 'stroke') == '#000000'
        # After Phase 3 alignment: angle.fill is presets.color.background.
        assert resolve(scene, ang, 'fill') == '#ffffff'
        assert resolve(scene, ang, 'fill_opacity') == 1

    def test_explicit_write_beats_builtin(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
A.style.fill = '#ff0000'
""")
        scene.addAllGeometry(show=True)

        assert resolve(scene, scene.geo.element('A'), 'fill') == '#ff0000'

    def test_overlay_beats_builtin(self):
        """Sanity: resolver reads overlay lazily above builtin defaults."""
        scene = AnimaGeoScene()
        scene.style_config.overlay.per_type['point'] = {'fill': '#00ff00'}
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)

        assert resolve(scene, scene.geo.element('A'), 'fill') == '#00ff00'
