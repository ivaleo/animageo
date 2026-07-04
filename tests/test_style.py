"""Tests for style system (style.py, style_schema.py)."""
import json
import os
import pytest
import tempfile

from animageo.style import GeoStyle, isnan, rgba, equal, getColorFromDict, hasParam, updateMin, updateMax
from animageo.style.schema import validate_style_json
from animageo.constants import (
    STYLE_TO_INTERNAL,
    LINE_WIDTH_SCALE,
    FONT_SIZE_RATIO,
    STROKE_WIDTH_SCALE,
    GGB_FONT_SCALE,
)


STYLE_DIR = os.path.join(os.path.dirname(__file__), '..', 'style')


# ── isnan ──────────────────────────────────────────────────────────────

class TestIsnan:
    def test_int(self):
        assert not isnan(0)
        assert not isnan(42)

    def test_float(self):
        assert not isnan(3.14)

    def test_none(self):
        assert isnan(None)

    def test_string_numeric(self):
        assert not isnan('3.14')

    def test_string_auto(self):
        assert isnan('auto')

    def test_list(self):
        assert isnan([1, 2])


# ── rgba ───────────────────────────────────────────────────────────────

class TestRgba:
    def test_hex_color(self):
        result = rgba('#ff0000')
        assert result is not None
        assert len(result) == 3

    def test_invalid(self):
        result = rgba('not_a_color')
        assert result is None


# ── equal ──────────────────────────────────────────────────────────────

class TestEqual:
    def test_exact(self):
        assert equal([1, 2, 3], [1, 2, 3])
        assert not equal([1, 2, 3], [1, 2, 4])

    def test_with_epsilon(self):
        assert equal([1.0, 2.0], [1.001, 2.001], eps=0.01)
        assert not equal([1.0, 2.0], [1.1, 2.1], eps=0.01)

    def test_different_length(self):
        assert not equal([1, 2], [1, 2, 3])


# ── import.colors resolution ───────────────────────────────────────────

class TestImportColors:
    def test_target_color_is_hex_and_explicit_opacity_is_separate(self):
        target = getColorFromDict(
            {'#1565c0 0.1': '#f15b5b 1'},
            ['#1565c0', 0.1],
        )

        assert target.color == '#f15b5b'
        assert target.opacity == 1.0

    def test_target_without_opacity_preserves_existing_opacity(self):
        target = getColorFromDict(
            {'#1565c0 0.1': '#f15b5b'},
            ['#1565c0', 0.1],
        )

        assert target.color == '#f15b5b'
        assert target.opacity is None

    def test_source_opacity_specific_rule_wins_over_bare_color_rule(self):
        target = getColorFromDict(
            {
                '#1565c0': '#4d87c6',
                '#1565c0 0.1': '#f15b5b 1',
            },
            ['#1565c0', 0.1],
        )

        assert target.color == '#f15b5b'
        assert target.opacity == 1.0


# ── hasParam ───────────────────────────────────────────────────────────

class TestHasParam:
    def test_present(self):
        assert hasParam({'key': 'value'}, 'key')

    def test_missing(self):
        assert not hasParam({'key': 'value'}, 'other')

    def test_falsy(self):
        assert not hasParam({'key': None}, 'key')
        assert not hasParam({'key': 0}, 'key')
        assert not hasParam({'key': ''}, 'key')


# ── updateMin/updateMax ───────────────────────────────────────────────

class TestUpdateMinMax:
    def test_normal(self):
        assert updateMin(5, 3) == 3
        assert updateMax(5, 3) == 5

    def test_with_nan(self):
        assert updateMin(None, 3) == 3
        assert updateMin(5, None) == 5
        assert updateMax(None, 3) == 3
        assert updateMax(5, None) == 5


# ── validate_style_json ───────────────────────────────────────────────

class TestValidateStyleJson:
    def test_valid(self):
        data = {
            'presets': {
                'color': {'main': '#000', 'light': '#fff', 'accent': '#f00', 'accent_light': '#fcc'},
                'point_size': {'main': 3},
                'line_width': {'main': 1},
            },
            'defaults': {},
            'rendering': {},
            'import': {},
        }
        warnings = validate_style_json(data)
        assert len(warnings) == 0

    def test_missing_sections(self):
        warnings = validate_style_json({})
        # Missing presets.color keys: main, light, accent, accent_light
        assert len(warnings) >= 4

    def test_missing_color_presets(self):
        data = {'presets': {}, 'defaults': {}, 'rendering': {}, 'import': {}}
        warnings = validate_style_json(data)
        assert any('presets.color.main' in w for w in warnings)

    def test_removed_schema_raises(self):
        from animageo.style.schema import RemovedStyleSchemaError
        data = {'style': {}, 'technic': {}, 'ggb_export': {}}
        with pytest.raises(RemovedStyleSchemaError, match='canonical top-level sections'):
            validate_style_json(data)

    @pytest.mark.parametrize('key', ['style', 'technic', 'ggb_export', 'palette'])
    def test_removed_top_level_keys_raise(self, key):
        from animageo.style.schema import RemovedStyleSchemaError
        with pytest.raises(RemovedStyleSchemaError):
            validate_style_json({key: {}})

    def test_rendering_angle_radius_rejected(self):
        with pytest.raises(ValueError, match='overlay.angle_radius'):
            validate_style_json({'rendering': {'angle_radius': {'enabled': True}}})

    def test_rendering_scale_export_rejected(self):
        with pytest.raises(ValueError, match='rendering.scale_export'):
            validate_style_json({'rendering': {'scale_export': 2}})

    def test_label_placement_angle_gap_px_rejected(self):
        with pytest.raises(ValueError, match='angle_gap_arc_px'):
            validate_style_json({'overlay': {'label_placement': {'angle_gap_px': 3}}})

    def test_removed_default_key_rejected(self):
        with pytest.raises(ValueError, match='defaults.segment.line_width'):
            validate_style_json({'defaults': {'segment': {'line_width': 2}}})

    def test_short_import_refs_are_accepted(self):
        warnings = validate_style_json({
            'import': {
                'point_size': {'5': 'main'},
                'line_width': {'5': 'line_width.main'},
                'colors': {'#1565c0': 'accent 1'},
            },
        })
        assert isinstance(warnings, list)

    def test_import_policy_unknown_key_rejected(self):
        with pytest.raises(ValueError, match='import.policy'):
            validate_style_json({'import': {'policy': {'per_type': {}}}})


# ── GeoStyle loading ──────────────────────────────────────────────────

class TestGeoStyleLoading:
    def _style_files(self):
        if not os.path.isdir(STYLE_DIR):
            return []
        return [
            os.path.join(STYLE_DIR, f)
            for f in os.listdir(STYLE_DIR)
            if f.endswith('.json')
        ]

    def test_default_init(self):
        style = GeoStyle()
        assert style.dot_size > 0
        assert style.line_width > 0
        assert isinstance(style.rendering, dict)
        assert isinstance(style.imp, dict)
        assert isinstance(style.export, dict)

    def test_load_all_style_files(self):
        """All style JSON files should load without errors."""
        files = self._style_files()
        if not files:
            pytest.skip('No style files found')

        for f in files:
            style = GeoStyle(style=f)
            assert style.dot_size > 0, f"dot_size invalid in {f}"
            assert style.line_width > 0, f"line_width invalid in {f}"

    def test_default_export_uses_manim_canvas(self):
        style = GeoStyle()
        assert style.export['ptWidth'] > 0
        assert style.export['ptHeight'] > 0

    def test_import_refs_resolve_against_builtin_presets(self, tmp_path):
        p = tmp_path / 'style.json'
        p.write_text(json.dumps({
            'import': {
                'point_size': {'5': 'main'},
                'line_width': {'5': 'line_width.main'},
                'colors': {'#1565c0': 'color.main'},
            },
        }))

        style = GeoStyle(style=str(p))

        assert style.imp['point_size']['5'] == 6
        assert style.imp['line_width']['5'] == 1.5
        assert style.imp['colors']['#1565c0'] == '#000000'

    def test_import_color_bare_token_preserves_explicit_opacity(self, tmp_path):
        p = tmp_path / 'style.json'
        p.write_text(json.dumps({
            'presets': {'color': {'accent': '#f15b5b'}},
            'import': {'colors': {'#1565c0 0.1': 'accent 1'}},
        }))

        style = GeoStyle(style=str(p))

        assert style.imp['colors']['#1565c0 0.1'] == '#f15b5b 1'


class TestApplyStyleImportColors:
    def _style_file(self, tmp_path, colors):
        data = {
            'presets': {
                'color': {
                    'main': '#1565c0',
                    'light': '#d6e5f6',
                    'accent': '#f15b5b',
                    'accent_light': '#fdddd7',
                },
            },
            'import': {'colors': colors},
        }
        p = tmp_path / 'style.json'
        p.write_text(json.dumps(data))
        return str(p)

    def test_apply_style_writes_hex_color_and_explicit_opacity(self, tmp_path):
        from animageo.animageo import AnimaGeoScene

        scene = AnimaGeoScene()
        scene.putCode('A = Point(0, 0)')
        elem = scene.geo.element('A')
        elem.ggb_style['fill'] = '#1565c0'
        elem.ggb_style['fill_opacity'] = 0.1

        scene.applyStyle(
            style=self._style_file(
                tmp_path,
                {'#1565c0 0.1': 'presets.color.accent 1'},
            ),
            export={'size': [800, 600]},
        )

        assert elem.ggb_style['fill'] == '#f15b5b'
        assert elem.ggb_style['fill_opacity'] == 1.0

    def test_apply_style_preserves_opacity_when_target_omits_it(self, tmp_path):
        from animageo.animageo import AnimaGeoScene

        scene = AnimaGeoScene()
        scene.putCode('A = Point(0, 0)')
        elem = scene.geo.element('A')
        elem.ggb_style['stroke'] = '#000000'
        elem.ggb_style['stroke_opacity'] = 0.6

        scene.applyStyle(
            style=self._style_file(tmp_path, {'#000000 0.6': '#2581b5'}),
            export={'size': [800, 600]},
        )

        assert elem.ggb_style['stroke'] == '#2581b5'
        assert elem.ggb_style['stroke_opacity'] == 0.6


# ── Scaling constants & formulas ──────────────────────────────────────
# Lock in the current values so Phase 2 refactor (extracting named
# scaling functions) cannot silently drift the coefficients.

class TestScalingConstants:
    def test_style_to_internal(self):
        assert STYLE_TO_INTERNAL == 0.02

    def test_line_width_scale(self):
        assert LINE_WIDTH_SCALE == 2

    def test_font_size_ratio(self):
        assert FONT_SIZE_RATIO == 50 / 25.9

    def test_stroke_width_scale(self):
        assert STROKE_WIDTH_SCALE == 100

    def test_ggb_font_scale(self):
        assert GGB_FONT_SCALE == 100.0


class TestGgbFontFormula:
    """applyStyle() computes style.font_size = ggb_font_px * GGB_FONT_SCALE / ptUnit.

    This locks in the current formula (animageo.py:284-286) at a unit level.
    Phase 2 will replace it with a named function in scaling.py; the value
    must stay identical for pixel-invariance.
    """

    @pytest.mark.parametrize('ggb_font_px,ptUnit,expected', [
        (16, 50.0, 32.0),           # 16 * 100 / 50 = 32
        (12, 50.0, 24.0),
        (20, 100.0, 20.0),          # doubled scale → half size
        (16, 25.0, 64.0),            # half scale → double size
    ])
    def test_formula(self, ggb_font_px, ptUnit, expected):
        assert ggb_font_px * GGB_FONT_SCALE / ptUnit == expected
