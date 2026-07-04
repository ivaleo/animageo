"""Test: style overlay (per_type, per_name) reaches DSL-built elements.

Regression test for bug #2 from the original architecture review:
``ImportPolicy`` only walks elements with non-empty ``ggb_raw`` — DSL-built
elements are silently skipped, so ``per_type`` / ``per_name`` overrides in
``style.json`` never apply.

After Phase 5 the overlay lives in ``StyleConfig.overlay`` and is applied
by ``AnimaGeoScene.addAllGeometry`` to *all* elements, regardless of
origin.
"""
import json

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.style.resolver import resolve


def _write_style(tmp_path, overlay):
    """Build a minimal valid style JSON with the given overlay block."""
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
        'overlay': overlay,
    }
    p = tmp_path / 'style.json'
    p.write_text(json.dumps(data))
    return str(p)


class TestOverlayAppliesToDSL:
    def test_per_type_reaches_dsl_point(self, tmp_path):
        """``overlay.per_type.point.size_px`` resolves for a DSL-built point."""
        style = _write_style(tmp_path, {
            'per_type': {'point': {'size_px': 99}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)

        elem = scene.geo.element('A')
        assert elem is not None
        assert 'size_px' not in elem.style
        assert resolve(scene, elem, 'size_px') == 99

    def test_per_name_reaches_dsl_element(self, tmp_path):
        """``overlay.per_name.<name>`` resolves for DSL elements."""
        style = _write_style(tmp_path, {
            'per_name': {'A': {'size_px': 42, 'fill': '#ff0000'}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("A = Point(0, 0); B = Point(1, 1)")
        scene.addAllGeometry(show=True)

        assert resolve(scene, scene.geo.element('A'), 'size_px') == 42
        assert resolve(scene, scene.geo.element('A'), 'fill') == '#ff0000'
        assert 'size_px' not in scene.geo.element('A').style
        assert 'fill' not in scene.geo.element('A').style
        # B was NOT in per_name — no explicit size_px/fill override.
        assert 'size_px' not in scene.geo.element('B').style

    def test_pre_setup_dsl_write_wins_over_overlay(self, tmp_path):
        """DSL/Python explicit style stays above overlay."""
        style = _write_style(tmp_path, {
            'per_type': {'point': {'size_px': 99}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("""
A = Point(0, 0)
A.style.size_px = 7
""")
        scene.addAllGeometry(show=True)
        assert scene.geo.element('A').style.get('size_px') == 7
        assert resolve(scene, scene.geo.element('A'), 'size_px') == 7

    def test_pre_setup_dsl_stroke_width_survives_render_passes(self, tmp_path):
        """Regression: add/update geometry must not replace explicit DSL style with overlay."""
        style = _write_style(tmp_path, {
            'per_type': {'segment': {'stroke_width_px': 1}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("""
A = Point(0, 0)
B = Point(1, 0)
d = Segment(A, B)
d.style.stroke_width_px = 10
""")
        elem = scene.geo.element('d')
        assert elem.style.get('stroke_width_px') == 10

        scene.addAllGeometry(show=True)
        scene.updateAllGeometry()

        assert elem.style.get('stroke_width_px') == 10
        assert resolve(scene, elem, 'stroke_width_px') == 10
        from animageo.constants import STROKE_WIDTH_SCALE
        ptUnit = scene.style.export['ptUnit']
        assert scene._build_render_ctx(elem, z_auto=True).lw == pytest.approx(10 * STROKE_WIDTH_SCALE / ptUnit)

    def test_post_setup_dsl_write_wins_over_overlay(self, tmp_path):
        """DSL writes after addAllGeometry survive — overlay already ran."""
        style = _write_style(tmp_path, {
            'per_type': {'point': {'size_px': 99}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)
        scene.geo.element('A').style['size_px'] = 7
        assert scene.geo.element('A').style.get('size_px') == 7
        assert resolve(scene, scene.geo.element('A'), 'size_px') == 7

    def test_per_name_beats_per_type(self, tmp_path):
        """Named override takes precedence over type override."""
        style = _write_style(tmp_path, {
            'per_type': {'point': {'size_px': 10}},
            'per_name': {'A': {'size_px': 99}},
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("A = Point(0, 0); B = Point(1, 1)")
        scene.addAllGeometry(show=True)
        assert resolve(scene, scene.geo.element('A'), 'size_px') == 99   # per_name
        assert resolve(scene, scene.geo.element('B'), 'size_px') == 10   # per_type

    def test_overlay_applies_to_multiple_types(self, tmp_path):
        """Overlay per_type keys route by Python type, not by GGB origin."""
        style = _write_style(tmp_path, {
            'per_type': {
                'point':   {'size_px': 99},
                'segment': {'stroke_width_px': 5},
            },
        })
        scene = AnimaGeoScene()
        scene.applyStyle(style=style)
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 5)
s = Segment(A, B)
""")
        scene.addAllGeometry(show=True)

        assert resolve(scene, scene.geo.element('A'), 'size_px') == 99
        assert resolve(scene, scene.geo.element('s'), 'stroke_width_px') == 5
