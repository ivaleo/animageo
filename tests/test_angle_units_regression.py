"""Regression test for Phase 4 angle-unit fix.

Before the fix:
  defaults.angle.arc_size_px=17 in JSON
  → GeoStyle.ang_rdefault = json_size_to_internal(17) = 0.34 (scene-units)
  → renderer divides by ptUnit=46: 0.34/46 ≈ 0.0074 → ~0.3 pixel arc
  → invisible angle arcs on DSL-built scenes.

After the fix:
  defaults.angle.arc_size_px=17 in JSON
  → GeoStyle.ang_rdefault = 17 (pixels)
  → renderer divides by ptUnit=46: 17/46 ≈ 0.37 scene-units = 17 pixels
  → visible, correctly-sized arc.

This test locks in the fix so a future refactor doesn't silently reintroduce
the double-scaling.
"""
import json

import pytest

from animageo.style import GeoStyle


def _write_json(tmp_path, angle_section):
    """Write a minimal valid style JSON with the given defaults.angle block."""
    data = {
        'name': 'test',
        'version': 0.1,
        'presets': {
            'color': {'main': '#000', 'light': '#ccc', 'accent': '#d05', 'accent_light': '#f6e'},
            'point_size': {'main': 2.83},
            'line_width': {'main': 1},
            'tick': {'main': {'tick_width_px': 1.5, 'tick_length_px': 18, 'tick_shift_px': 5}},
            'arrow': {'main': {'arrow_width_px': 15, 'arrow_length_px': 22}},
            'font_size': {'main': 10.5},
        },
        'defaults': {
            'angle': angle_section,
        },
    }
    p = tmp_path / 'style.json'
    p.write_text(json.dumps(data))
    return str(p)


class TestAnglePixelUnits:
    def test_radius_loaded_as_pixels(self, tmp_path):
        path = _write_json(tmp_path, {
            'stroke_width_px': 0.75, 'arc_size_px': 17,
            'arc_shift_px': 1.5, 'right_angle_size_px': 17,
        })
        s = GeoStyle(style=path)
        # In the pre-fix implementation these were 0.34, 0.03, 0.34
        # (all after × 0.02). After the fix they keep their JSON values.
        assert s.ang_rdefault == 17
        assert s.ang_rshift == 1.5
        assert s.ang_right == 17

    def test_large_radius_still_sane(self, tmp_path):
        """A large pixel value shouldn't be accidentally divided back down."""
        path = _write_json(tmp_path, {
            'stroke_width_px': 1, 'arc_size_px': 50,
            'arc_shift_px': 5, 'right_angle_size_px': 50,
        })
        s = GeoStyle(style=path)
        assert s.ang_rdefault == 50

    def test_init_defaults_are_in_pixels(self):
        """GeoStyle() with no JSON uses Python init defaults — also pixels."""
        s = GeoStyle()
        # These init values are pixels (10 px, 10 px, derived shift).
        # Renderer does value / ptUnit; for a typical ptUnit ≈ 46 the
        # result is ≈ 0.22 scene-units ≈ 10 pixels — a visible arc.
        assert s.ang_rdefault == 10
        assert s.ang_right == 10

    def test_dot_size_loaded_as_pixels(self, tmp_path):
        """point_size.main in JSON is now pixels, matches renderer contract."""
        data = {
            'name': 'test', 'version': 0.1,
            'presets': {
                'color': {'main': '#000', 'light': '#ccc', 'accent': '#d05', 'accent_light': '#f6e'},
                'point_size': {'main': 7, 'bold': 10, 'aux': 4},
                'line_width': {'main': 1},
            },
            'defaults': {
                'angle': {
                    'stroke_width_px': 1,
                    'arc_size_px': 17,
                    'arc_shift_px': 1.5,
                    'right_angle_size_px': 17,
                },
            },
        }
        p = tmp_path / 'style.json'
        p.write_text(json.dumps(data))
        s = GeoStyle(style=str(p))
        # In the pre-fix implementation this was 0.02 * 7 = 0.14 (scene-units).
        assert s.dot_size == 7
