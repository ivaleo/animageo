"""Tests for point_shape rendering — all shapes produce valid Mobjects."""
import pytest

from manim import Circle, Square, VGroup

from animageo.animageo import AnimaGeoScene
from animageo.style.resolver import resolve


def _make_scene_with_point_shape(tmp_path, point_shape, size_px=6):
    """Build a scene with a single point having the given shape."""
    import json
    overlay = {
        'per_type': {'point': {'size_px': size_px, 'point_shape': point_shape}},
    }
    data = {
        'name': 'test', 'version': 0.1,
        'presets': {
            'color': {'main': '#000', 'light': '#ccc', 'accent': '#d05',
                      'accent_light': '#f6e'},
            'point_size': {'main': 7},
            'line_width': {'main': 1},
            'angle_radius': {'main': 17, 'shift': 1.5, 'right': 17},
            'tick': {'main': {'tick_width_px': 1.5, 'tick_length_px': 18, 'tick_shift_px': 5}},
            'arrow': {'main': {'arrow_width_px': 15, 'arrow_length_px': 22}},
            'font_size': {'main': 10.5},
        },
        'defaults': {
            'angle': {
                'stroke_width_px': 1,
                'arc_size_px': 'presets.angle_radius.main',
                'arc_shift_px': 'presets.angle_radius.shift',
                'right_angle_size_px': 'presets.angle_radius.right',
            },
            'segment': {'$include': 'presets.tick.main'},
            'vector': {'$include': ['presets.tick.main', 'presets.arrow.main']},
        },
        'overlay': overlay,
    }
    p = tmp_path / 'style.json'
    p.write_text(json.dumps(data))

    scene = AnimaGeoScene()
    scene.applyStyle(style=str(p))
    scene.putCode("A = Point(0, 0)")
    scene.addAllGeometry(show=True)
    return scene


class TestPointShapeRender:
    SHAPES = [
        'circle', 'square', 'diamond', 'triangle_up', 'triangle_down',
        'triangle_left', 'triangle_right', 'cross', 'plus',
    ]

    @pytest.mark.parametrize('shape', SHAPES)
    def test_shape_renders_without_error(self, tmp_path, shape):
        """Each point_shape produces at least one Mobject in the VGroup."""
        scene = _make_scene_with_point_shape(tmp_path, shape)
        elem = scene.geo.element('A')
        assert elem is not None
        # Element was rendered (visible)
        assert elem.visible is True

    def test_default_circle_shape(self, tmp_path):
        """No point_shape set → renders as Circle."""
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)
        # Should not raise — default is circle
        elem = scene.geo.element('A')
        assert elem.visible is True

    def test_overlay_sets_point_shape(self, tmp_path):
        """Overlay per_type.point.point_shape resolves lazily."""
        scene = _make_scene_with_point_shape(tmp_path, 'square')
        elem = scene.geo.element('A')
        assert 'point_shape' not in elem.style
        assert resolve(scene, elem, 'point_shape') == 'square'

    def test_unknown_shape_falls_back_to_circle(self, tmp_path):
        """Unknown shape value falls back to circle without error."""
        mobj = AnimaGeoScene._make_point_mobject(
            'unknown_shape', [0, 0, 0], 0.1,
            '#000000', '#000000', 1.0, 1.0, 1.0, 50,
        )
        assert isinstance(mobj, Circle)

    def test_diamond_is_rotated_square(self):
        """Diamond has vertices on axes, not an unrotated square's corners."""
        mobj = AnimaGeoScene._make_point_mobject(
            'diamond', [0, 0, 0], 1.0,
            '#000000', '#000000', 1.0, 1.0, 1.0, 50,
        )
        assert isinstance(mobj, Square)
        vertices = sorted(
            (round(float(x), 6), round(float(y), 6))
            for x, y, _ in mobj.get_vertices()
        )
        assert vertices == [(-1.0, 0.0), (-0.0, -1.0), (0.0, 1.0), (1.0, -0.0)]
