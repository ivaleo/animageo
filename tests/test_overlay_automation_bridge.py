"""Overlay automation is read directly from StyleConfig."""
import json
import math

import pytest

from animageo.animageo import AnimaGeoScene


def _write_style(tmp_path, overlay_block):
    data = {
        'name': 'test', 'version': 0.1,
        'presets': {
            'color': {'main': '#000', 'light': '#ccc', 'accent': '#d05', 'accent_light': '#f6e'},
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
        'overlay': overlay_block,
    }
    p = tmp_path / 'style.json'
    p.write_text(json.dumps(data))
    return str(p)


class TestOverlayAutomationCanonicalContract:
    def test_angle_radius_stays_in_overlay_not_rendering(self, tmp_path):
        style = _write_style(tmp_path, {
            'angle_radius': {'enabled': True, 'exp': 0.5, 'min_px': 20},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)

        ar = scene.style_config.overlay.angle_radius
        assert ar.get('enabled') is True
        assert ar.get('exp') == 0.5
        assert ar.get('min_px') == 20
        assert 'angle_radius' not in scene.style.rendering

    def test_label_placement_stays_in_overlay_not_rendering(self, tmp_path):
        style = _write_style(tmp_path, {
            'label_placement': {'enabled': True, 'distance_px': 10},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)

        lp = scene.style_config.overlay.label_placement
        assert lp.get('enabled') is True
        assert lp.get('distance_px') == 10
        assert 'label_placement' not in scene.style.rendering

    def test_rendering_automation_keys_are_rejected(self, tmp_path):
        """Automation settings belong to overlay, not rendering."""
        style = _write_style(tmp_path, {})
        with open(style) as f:
            data = json.load(f)
        data['rendering'] = {
            'angle_radius': {'enabled': True, 'exp': 0.3},
            'label_placement': {'enabled': True, 'distance_px': 8},
        }
        p = tmp_path / 'style.json'
        p.write_text(json.dumps(data))

        scene = AnimaGeoScene()
        with pytest.raises(ValueError, match='Automation setting'):
            scene.applyStyle(style=str(p))

    def test_rendering_contains_only_renderer_flags(self, tmp_path):
        style = _write_style(tmp_path, {
            'angle_radius': {'enabled': True},
            'label_placement': {'enabled': True},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)

        assert set(scene.style.rendering) <= {
            'background',
            'line_cap',
            'right_angle_joint',
            'polygon_boundary_layer',
            'points_display',
            'label_anchor',
            'label_value_precision',
        }

    def test_overlay_angle_radius_directly_affects_arc_helper(self, tmp_path):
        style = _write_style(tmp_path, {
            'angle_radius': {
                'enabled': True,
                'exp': 0.5,
                'pivot_rad': math.pi / 2,
                'min_px': 0,
                'max_arm_fraction': 10,
            },
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("""
A = Point(0, 0)
B = Point(10, 0)
C = Point(9.848, 1.736)
alpha = Angle(B, A, C)
""")
        elem = scene.geo.element('alpha')
        from animageo.label_placement import compute_effective_arc_size_px
        scaled = compute_effective_arc_size_px(elem, elem.data, scene, base_px=20)
        assert scaled > 20
        assert 'angle_radius' not in scene.style.rendering

    def test_overlay_label_placement_directly_reaches_layout(self, tmp_path, monkeypatch):
        style = _write_style(tmp_path, {
            'label_placement': {'enabled': True, 'distance_px': 17},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)

        captured = {}
        import animageo.label_placement as lp

        def fake_compute(scene_arg, *, cfg=None, canonicalize=False):
            captured['cfg'] = cfg
            captured['canonicalize'] = canonicalize
            return {}

        monkeypatch.setattr(lp, 'compute_label_layout', fake_compute)
        lp.auto_place_labels(scene)

        assert captured['cfg']['distance_px'] == 17
        assert 'label_placement' not in scene.style.rendering
