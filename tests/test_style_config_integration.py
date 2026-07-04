"""Integration tests for StyleConfig wired to AnimaGeoScene.

Phase 2 scope: verifies that every scene has a non-empty style_config from
construction, and that applyStyle(style=...) merges user JSON on top
of builtin defaults. Does NOT exercise the renderer — that migration
happens in Phase 3.
"""
import json

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.style.config import StyleConfig
from animageo.style.scaling import stroke_width_to_manim


class TestSceneHasStyleConfig:
    def test_fresh_scene_has_builtin_config(self):
        scene = AnimaGeoScene()
        assert isinstance(scene.style_config, StyleConfig)
        # builtin.json has point defaults
        assert scene.style_config.defaults.get('point', 'size_px') is not None

    def test_fresh_scene_config_has_all_core_types(self):
        scene = AnimaGeoScene()
        expected = {'point', 'segment', 'line', 'ray', 'angle', 'polygon',
                    'circle', 'arc', 'vector'}
        assert expected.issubset(set(scene.style_config.defaults.by_type.keys()))

    def test_fresh_scene_color_presets_populated(self):
        scene = AnimaGeoScene()
        assert 'main' in scene.style_config.presets['color']
        assert 'strong' in scene.style_config.presets['color']


class TestApplyStyleReloadsConfig:
    def test_applyStyle_without_file_keeps_builtin(self, tmp_path):
        scene = AnimaGeoScene()
        original_main = scene.style_config.presets['color']['main']
        scene.applyStyle()  # no user file
        assert scene.style_config.presets['color']['main'] == original_main

    def test_applyStyle_with_user_file_merges(self, tmp_path):
        user = {
            'presets': {'color': {'main': '#ff0000'}},
            'defaults': {'point': {'size_px': 77}},
        }
        p = tmp_path / 'user.json'
        p.write_text(json.dumps(user))

        scene = AnimaGeoScene()
        scene.applyStyle(style=str(p))

        # User value overrides builtin.
        assert scene.style_config.presets['color']['main'] == '#ff0000'
        assert scene.style_config.defaults.get('point', 'size_px') == 77
        # Builtin value survives for keys the user didn't touch.
        assert scene.style_config.defaults.get('segment', 'stroke_width_px') is not None
        assert scene.style_config.defaults.get('angle', 'arc_size_px') is not None

    def test_rendering_background_uses_color_preset(self, tmp_path):
        user = {
            'presets': {
                'color': {
                    'background': '#101820',
                    'strong': '#f8f8f8',
                },
            },
            'rendering': {
                'background': 'presets.color.background',
            },
        }
        p = tmp_path / 'dark.json'
        p.write_text(json.dumps(user))

        scene = AnimaGeoScene()
        scene.applyStyle(style=str(p))

        assert str(scene.style.background).lower() == '#101820'
        assert str(scene.camera.background_color).lower() == '#101820'

    def test_svg_export_paints_rendering_background(self, tmp_path):
        user = {
            'presets': {
                'color': {
                    'background': '#101820',
                    'strong': '#f8f8f8',
                },
            },
            'rendering': {
                'background': 'presets.color.background',
            },
        }
        p = tmp_path / 'dark.json'
        p.write_text(json.dumps(user))

        scene = AnimaGeoScene()
        scene.applyStyle(style=str(p), export={"size": [120, 80]})
        out = tmp_path / 'out.svg'
        scene.exportSVG(str(out))

        svg = out.read_text()
        assert '<rect' in svg
        assert '6.27451%' in svg
        assert '9.411765%' in svg
        assert '12.54902%' in svg

    def test_applyStyle_keeps_scene_style_container(self):
        """Regression: scene self.style remains populated alongside style_config."""
        scene = AnimaGeoScene()
        scene.applyStyle()
        assert hasattr(scene, 'style')
        assert hasattr(scene.style, 'ang_rdefault')
        assert isinstance(scene.style_config, StyleConfig)


class TestFontSizePxPrecedence:
    """``font_size_px`` in elem.style (from builtin defaults / overlay) must
    reach the renderer. Previously the renderer only read ``font_size``
    (manim units), so pixel-based builtin defaults were silently dropped."""

    def _point_elem(self, scene):
        scene.putCode("P = Point(0, 0)\n")
        return scene.element('P')

    def test_renderer_honors_font_size_px(self):
        from animageo.constants import GGB_FONT_SCALE
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._point_elem(scene)
        e.style['font_size_px'] = 21.0
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.font_size == pytest.approx(21.0 * GGB_FONT_SCALE / ptUnit)

    def test_removed_font_size_is_not_runtime_fallback(self):
        """Runtime font sizing uses only canonical ``font_size_px``.

        Removed ``font_size`` does not participate in the render fallback path.
        """
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.style_config.defaults.by_type.get('point', {}).pop('font_size_px', None)
        e = self._point_elem(scene)
        e.style['font_size'] = 42.5
        ctx = scene._build_render_ctx(e, z_auto=True)
        from animageo.constants import GGB_FONT_SCALE
        ptUnit = scene.style.export['ptUnit']
        assert ctx.font_size == pytest.approx(14.0 * GGB_FONT_SCALE / ptUnit)

    def test_font_size_px_wins_over_font_size(self):
        """If both keys are present, the pixel-invariant one wins (newer
        convention). This matches the scaling.py ``_px`` contract."""
        from animageo.constants import GGB_FONT_SCALE
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._point_elem(scene)
        e.style['font_size_px'] = 14.0
        e.style['font_size'] = 99.0
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.font_size == pytest.approx(14.0 * GGB_FONT_SCALE / ptUnit)


class TestResolverReachesRenderer:
    """Regression: overlay customisation for stroke_width_px / font_size_px /
    size_px was bypassed — the renderer read ``elem.style.get(...)`` directly,
    stopping at explicit per-element writes. Routing through the resolver
    makes ``overlay.per_type.<type>.<key>`` reach the render ctx even when
    ``elem.style`` is empty."""

    def _segment(self, scene):
        scene.putCode("A = Point(0, 0)\nB = Point(1, 0)\ns1 = Segment(A, B)\n")
        return scene.element('s1')

    def test_overlay_per_type_stroke_width_reaches_renderer(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.style_config.overlay.per_type['segment'] = {'stroke_width_px': 7.5}
        e = self._segment(scene)
        ctx = scene._build_render_ctx(e, z_auto=True)
        # ctx.lw is stroke_width_to_manim(7.5, ptUnit) = 7.5 * 100 / ptUnit.
        from animageo.constants import STROKE_WIDTH_SCALE
        ptUnit = scene.style.export['ptUnit']
        assert ctx.lw == pytest.approx(7.5 * STROKE_WIDTH_SCALE / ptUnit)

    def test_overlay_per_name_font_size_reaches_renderer(self):
        from animageo.constants import GGB_FONT_SCALE
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.style_config.overlay.per_name['A'] = {'font_size_px': 28}
        scene.putCode("A = Point(0, 0)\n")
        e = scene.element('A')
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.font_size == pytest.approx(28 * GGB_FONT_SCALE / ptUnit)


class TestPixelInvariantDecorations:
    """Per-element ``tick_*_px`` / ``arrow_*_px`` in elem.style are
    pixel-invariant: their on-screen size does not scale with canvas
    ``ptUnit``. Semantic defaults use the same canonical keys."""

    def _segment(self, scene):
        scene.putCode("A = Point(0, 0)\nB = Point(1, 0)\ns = Segment(A, B)\n")
        return scene.element('s')

    def test_tick_length_px_opt_in(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._segment(scene)
        e.style['tick_length_px'] = 20.0
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.strich_len == pytest.approx(20.0 / ptUnit)

    def test_tick_length_default_uses_semantic_preset(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._segment(scene)
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.strich_len == pytest.approx(
            scene.style_config.defaults.get('segment', 'tick_length_px') / ptUnit
        )

    def test_tick_width_px_uses_manim_stroke_units(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._segment(scene)
        e.style['tick_width_px'] = 2.0
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.strich_width == pytest.approx(stroke_width_to_manim(2.0, ptUnit))

    def test_arrow_px_opt_in(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.putCode("A = Point(0, 0)\nB = Point(1, 0)\nv = Vector(A, B)\n")
        e = scene.element('v')
        e.style['arrow_width_px'] = 12
        e.style['arrow_length_px'] = 18
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.arrow_width == pytest.approx(12 / ptUnit)
        assert ctx.arrow_height == pytest.approx(18 / ptUnit)

    def test_segment_line_tick_width_reaches_manim_stroke(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._segment(scene)
        e.style['tick_count'] = 1
        e.style['tick_style'] = 'line'
        e.style['tick_width_px'] = 2.0
        ptUnit = scene.style.export['ptUnit']

        mobj = scene.CreateMObject(e, z_auto=True)

        tick = mobj.submobjects[1]
        assert tick.get_stroke_width() == pytest.approx(
            stroke_width_to_manim(2.0, ptUnit)
        )

    def test_segment_wave_tick_width_reaches_manim_stroke(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._segment(scene)
        e.style['tick_count'] = 2
        e.style['tick_style'] = 'wave'
        e.style['tick_width_px'] = 2.0
        ptUnit = scene.style.export['ptUnit']

        mobj = scene.CreateMObject(e, z_auto=True)

        wave = mobj.submobjects[1]
        assert wave.get_stroke_width() == pytest.approx(
            stroke_width_to_manim(2.0, ptUnit)
        )

    def test_vector_tick_width_reaches_manim_stroke(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.putCode("A = Point(0, 0)\nB = Point(1, 0)\nv = Vector(A, B)\n")
        e = scene.element('v')
        e.style['tick_count'] = 1
        e.style['tick_width_px'] = 2.0
        ptUnit = scene.style.export['ptUnit']

        mobj = scene.CreateMObject(e, z_auto=True)

        tick = mobj.submobjects[1]
        assert tick.get_stroke_width() == pytest.approx(
            stroke_width_to_manim(2.0, ptUnit)
        )

    def test_vector_wave_tick_width_reaches_manim_stroke(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        scene.putCode("A = Point(0, 0)\nB = Point(1, 0)\nv = Vector(A, B)\n")
        e = scene.element('v')
        e.style['tick_count'] = 2
        e.style['tick_style'] = 'wave'
        e.style['tick_width_px'] = 2.0
        ptUnit = scene.style.export['ptUnit']

        mobj = scene.CreateMObject(e, z_auto=True)

        wave = mobj.submobjects[1]
        assert wave.get_stroke_width() == pytest.approx(
            stroke_width_to_manim(2.0, ptUnit)
        )


class TestLabelRadialOffsetPx:
    """``label_radial_offset_px`` is named pixels — must behave as pixels.
    Previously the value was passed through to manim-unit math unchanged,
    so a user setting ``5`` (intending 5 px) got a 5-MU offset (~500 px)."""

    def _angle_elem(self, scene):
        scene.putCode("""
A = Point(0, 0)
B = Point(1, 0)
C = Point(0, 1)
ang = Angle(B, A, C)
""")
        return scene.element('ang')

    def test_px_value_converted_to_mu_via_ptUnit(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._angle_elem(scene)
        e.style['label_radial_offset_px'] = 10.0
        ctx = scene._build_render_ctx(e, z_auto=True)
        ptUnit = scene.style.export['ptUnit']
        assert ctx.label_roff == pytest.approx(10.0 / ptUnit)

    def test_no_override_uses_canonical_zero_default(self):
        scene = AnimaGeoScene()
        scene.applyStyle()
        e = self._angle_elem(scene)
        ctx = scene._build_render_ctx(e, z_auto=True)
        assert ctx.label_roff == pytest.approx(0.0)


class TestCanonicalJsonValidation:
    def test_removed_visual_keys_are_rejected(self, tmp_path):
        user = {
            'defaults': {
                'segment': {
                    'line_width': 3,
                },
            },
        }
        p = tmp_path / 'removed.json'
        p.write_text(json.dumps(user))

        with pytest.raises(ValueError, match='defaults.segment.line_width'):
            StyleConfig.load(str(p))

    def test_canonical_visual_keys_load_without_aliases(self, tmp_path):
        user = {
            'defaults': {
                'segment': {
                    'stroke_width_px': 3,
                    'tick_length_px': 12,
                    'tick_width_px': 2,
                    'tick_shift_px': 4,
                    'font_size_px': 15,
                },
                'vector': {
                    'arrow_length_px': 18,
                    'arrow_width_px': 11,
                },
                'angle': {
                    'arc_size_px': 25,
                    'arc_shift_px': 5,
                    'right_angle_size_px': 20,
                    'label_radial_offset_px': 6,
                },
            },
            'overlay': {
                'per_type': {
                    'point': {'font_size_px': 16},
                },
                'per_name': {
                    'A': {'stroke_width_px': 7},
                },
            },
        }
        p = tmp_path / 'canonical.json'
        p.write_text(json.dumps(user))

        cfg = StyleConfig.load(str(p))

        assert cfg.defaults.get('segment', 'stroke_width_px') == 3
        assert cfg.defaults.get('segment', 'tick_length_px') == 12
        assert cfg.defaults.get('segment', 'tick_width_px') == 2
        assert cfg.defaults.get('segment', 'tick_shift_px') == 4
        assert cfg.defaults.get('segment', 'font_size_px') == 15
        assert cfg.defaults.get('vector', 'arrow_length_px') == 18
        assert cfg.defaults.get('vector', 'arrow_width_px') == 11
        assert cfg.defaults.get('angle', 'arc_size_px') == 25
        assert cfg.defaults.get('angle', 'arc_shift_px') == 5
        assert cfg.defaults.get('angle', 'right_angle_size_px') == 20
        assert cfg.defaults.get('angle', 'label_radial_offset_px') == 6
        assert cfg.overlay.per_type['point']['font_size_px'] == 16
        assert cfg.overlay.per_name['A']['stroke_width_px'] == 7

    def test_renderer_needs_no_web_side_legacy_bridge(self, tmp_path):
        user = {
            'presets': {
                'line_width': {'main': 2.25},
                'point_size': {'main': 9},
                'angle_radius': {'main': 31, 'shift': 6, 'right': 19},
                'tick': {'main': {'tick_length_px': 13, 'tick_width_px': 2, 'tick_shift_px': 5}},
                'arrow': {'main': {'arrow_length_px': 17, 'arrow_width_px': 10}},
                'font_size': {'main': 18},
            },
            'defaults': {
                'point': {'size_px': 'presets.point_size.main', 'font_size_px': 'presets.font_size.main'},
                'segment': {
                    '$include': 'presets.tick.main',
                    'stroke_width_px': 'presets.line_width.main',
                    'font_size_px': 'presets.font_size.main',
                },
                'vector': {
                    '$include': ['presets.tick.main', 'presets.arrow.main'],
                    'stroke_width_px': 'presets.line_width.main',
                },
                'angle': {
                    'stroke_width_px': 0.75,
                    'arc_size_px': 'presets.angle_radius.main',
                    'arc_shift_px': 'presets.angle_radius.shift',
                    'right_angle_size_px': 'presets.angle_radius.right',
                    'font_size_px': 'presets.font_size.main',
                    'label_radial_offset_px': 4,
                },
            },
        }
        p = tmp_path / 'canonical.json'
        p.write_text(json.dumps(user))

        scene = AnimaGeoScene()
        scene.applyStyle(style=str(p))
        scene.putCode("""
A = Point(0, 0)
B = Point(1, 0)
C = Point(0, 1)
s = Segment(A, B)
v = Vector(A, B)
alpha = Angle(B, A, C)
""")

        ptUnit = scene.style.export['ptUnit']
        s_ctx = scene._build_render_ctx(scene.element('s'), z_auto=True)
        v_ctx = scene._build_render_ctx(scene.element('v'), z_auto=True)
        a_ctx = scene._build_render_ctx(scene.element('alpha'), z_auto=True)

        assert s_ctx.strich_len == pytest.approx(13 / ptUnit)
        assert s_ctx.strich_width == pytest.approx(stroke_width_to_manim(2, ptUnit))
        assert s_ctx.strich_rshift == pytest.approx(5 / ptUnit)
        assert v_ctx.arrow_height == pytest.approx(17 / ptUnit)
        assert v_ctx.arrow_width == pytest.approx(10 / ptUnit)
        assert a_ctx.arc_shift_px == 6
        assert a_ctx.label_roff == pytest.approx(4 / ptUnit)
