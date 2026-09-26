"""Unit tests for ImportPolicy and the DSL parser.

Covers the import-adaptation scenarios: faithful/style_only, scalar
overrides, DSL directives (const/scale/quantize/remap), raw-derived fields,
and Python API callables.
"""
import pytest

from animageo.style.dsl import (
    parse_directive,
    SENTINEL_MATCH_ELEMENT,
    SENTINEL_AUTO,
)
from animageo.style.import_policy import ImportPolicy


class _FakeElem:
    """Minimal stand-in for a geometry Element in isolated tests."""

    def __init__(self, name='E', ggb_raw=None):
        self.name = name
        self.ggb_raw = ggb_raw or {}
        self.style = {}


# ══ DSL parser ═════════════════════════════════════════════════════════

class TestDslPassthrough:
    def test_non_string_unchanged(self):
        assert parse_directive(3) == 3
        assert parse_directive([1, 2]) == [1, 2]
        assert parse_directive(None) is None
        assert parse_directive(True) is True

    def test_bare_string_unchanged(self):
        assert parse_directive('#ff0000') == '#ff0000'

    def test_sentinels_unchanged(self):
        assert parse_directive(SENTINEL_MATCH_ELEMENT) == 'match_element'
        assert parse_directive(SENTINEL_AUTO) == 'auto'


class TestDslConst:
    def test_int(self):
        assert parse_directive('const:3') == 3

    def test_list(self):
        assert parse_directive('const:[1,2,3]') == [1, 2, 3]

    def test_string_literal(self):
        assert parse_directive("const:'#abc'") == '#abc'


class TestDslScale:
    def test_scale_callable(self):
        fn = parse_directive('scale:1.5')
        assert callable(fn)
        assert fn(4, {}, None) == 6.0
        assert fn(10, {}, None) == 15.0

    def test_scale_handles_none_raw(self):
        fn = parse_directive('scale:2')
        assert fn(None, {}, None) is None

    def test_scale_invalid_body(self):
        with pytest.raises(ValueError):
            parse_directive('scale:abc')


class TestDslQuantize:
    def test_picks_nearest(self):
        fn = parse_directive('quantize:[1,2,4]')
        assert fn(1.1, {}, None) == 1
        assert fn(1.6, {}, None) == 2
        assert fn(3, {}, None) == 2
        assert fn(3.5, {}, None) == 4
        assert fn(100, {}, None) == 4

    def test_single_bucket(self):
        fn = parse_directive('quantize:[3]')
        assert fn(0, {}, None) == 3
        assert fn(1000, {}, None) == 3

    def test_empty_bucket_rejected(self):
        with pytest.raises(ValueError):
            parse_directive('quantize:[]')


class TestDslRemap:
    def test_hit(self):
        fn = parse_directive("remap:{'#ff0000':'#c02121'}")
        assert fn('#ff0000', {}, None) == '#c02121'

    def test_miss_returns_original(self):
        fn = parse_directive("remap:{'#ff0000':'#c02121'}")
        assert fn('#00ff00', {}, None) == '#00ff00'

    def test_invalid_body(self):
        with pytest.raises(ValueError):
            parse_directive('remap:not-a-dict')


# ══ ImportPolicy factories ═════════════════════════════════════════════

class TestFactories:
    def test_faithful_default(self):
        p = ImportPolicy.faithful()
        assert p.base == 'faithful'
        assert p.size_px is None

    def test_style_only(self):
        p = ImportPolicy.style_only()
        assert p.base == 'style_only'

    def test_from_dict_preset_alias(self):
        p = ImportPolicy.from_dict({'preset': 'style_only'})
        assert p.base == 'style_only'

    def test_from_dict_rejects_unknown(self):
        with pytest.raises(ValueError, match='mystery_field'):
            ImportPolicy.from_dict({'mystery_field': 'xyz'})

    def test_from_dict_rejects_overlay_like_keys(self):
        # Type/name styling belongs to StyleConfig.overlay, not import.policy.
        with pytest.raises(ValueError, match='per_type'):
            ImportPolicy.from_dict({
                'size_px': 3,
                'per_type': {'segment': {'stroke_width_px': 10}},
            })

    def test_from_dict_parses_directives(self):
        p = ImportPolicy.from_dict({
            'size_px': 'scale:1.5',
            'stroke_width_px': 'quantize:[1,2,4]',
        })
        assert callable(p.size_px)
        assert callable(p.stroke_width_px)


# ══ Resolve ════════════════════════════════════════════════════════════

class TestResolveFaithful:
    """base=faithful without overrides must match resolve_ggb_style output."""

    def test_point_like(self):
        elem = _FakeElem('A', {
            'elem_type': 'point',
            'point_size': 5,
            'label_offset_px': [-28, 32],
            'obj_color': {'r': 21, 'g': 101, 'b': 192, 'alpha': 0},
            'point_style': 0,
        })
        style = ImportPolicy.faithful().resolve(elem)
        assert style['size_px'] == 10             # 5 * 2
        assert style['label_offset_px'] == [-28, -32]   # y-inverted
        assert style['fill'] == '#1565c0'

    def test_segment_like(self):
        elem = _FakeElem('c', {
            'elem_type': 'segment',
            'line_thickness': 5,
            'line_type': 0,
            'line_opacity': 204,
            'obj_color': {'r': 21, 'g': 101, 'b': 192, 'alpha': 0},
        })
        style = ImportPolicy.faithful().resolve(elem)
        assert style['stroke_width_px'] == 2.5     # 5 / 2


class TestResolveScalarOverride:
    def test_point_size_fixed(self):
        elem = _FakeElem('A', {'elem_type': 'point', 'point_size': 5})
        style = ImportPolicy(size_px=3).resolve(elem)
        # GGB would give size=10; policy override wins.
        assert style['size_px'] == 3

    def test_stroke_color_fixed(self):
        elem = _FakeElem('c', {
            'elem_type': 'segment',
            'line_thickness': 5,
            'line_type': 0,
            'line_opacity': 255,
            'obj_color': {'r': 100, 'g': 100, 'b': 100, 'alpha': 0},
        })
        style = ImportPolicy(stroke='#000000').resolve(elem)
        assert style['stroke'] == '#000000'


class TestResolveCallable:
    def test_callable_receives_raw(self):
        elem = _FakeElem('A', {'elem_type': 'point', 'point_size': 5})
        p = ImportPolicy(size_px=lambda raw, d, e: raw * 1.5)
        style = p.resolve(elem)
        assert style['size_px'] == 7.5    # callable sees raw=5, not 10

    def test_callable_handles_missing_raw(self):
        elem = _FakeElem('X', {'elem_type': 'point'})  # no point_size
        p = ImportPolicy(size_px=lambda raw, d, e: 9 if raw is None else raw)
        style = p.resolve(elem)
        assert style['size_px'] == 9

    def test_callable_receives_normalized_obj_color_source(self):
        elem = _FakeElem('c', {
            'elem_type': 'segment',
            'obj_color': {'r': 21, 'g': 101, 'b': 192, 'alpha': 0.4},
        })
        p = ImportPolicy(
            stroke=lambda raw, d, e: raw,
            fill_opacity=lambda raw, d, e: raw,
        )
        style = p.resolve(elem)
        assert style['stroke'] == '#1565c0'
        assert style['fill_opacity'] == 0.4


class TestResolveDslThroughJson:
    def test_scale_equivalent_to_callable(self):
        elem = _FakeElem('A', {'elem_type': 'point', 'point_size': 5})
        p = ImportPolicy.from_dict({'size_px': 'scale:1.5'})
        style = p.resolve(elem)
        assert style['size_px'] == 7.5

    def test_quantize(self):
        # GGB line_thickness=5 → default gives stroke_width=2.5.
        # quantize:[1,2,4] snaps raw 5 → 4.
        elem = _FakeElem('c', {
            'elem_type': 'segment',
            'line_thickness': 5,
            'line_type': 0,
            'line_opacity': 255,
            'obj_color': {'r': 0, 'g': 0, 'b': 0, 'alpha': 0},
        })
        p = ImportPolicy.from_dict({'stroke_width_px': 'quantize:[1,2,4]'})
        style = p.resolve(elem)
        assert style['stroke_width_px'] == 4

    def test_color_remap_uses_obj_color_hex(self):
        elem = _FakeElem('c', {
            'elem_type': 'segment',
            'obj_color': {'r': 21, 'g': 101, 'b': 192, 'alpha': 0.4},
        })
        p = ImportPolicy.from_dict({
            'stroke': "remap:{'#1565c0':'#0066cc'}",
            'fill_opacity': 'scale:0.5',
        })
        style = p.resolve(elem)
        assert style['stroke'] == '#0066cc'
        assert style['fill_opacity'] == 0.2

    def test_stroke_opacity_maps_from_line_opacity(self):
        elem = _FakeElem('c', {'elem_type': 'segment', 'line_opacity': 204})
        p = ImportPolicy.from_dict({'stroke_opacity': 'scale:0.001'})
        style = p.resolve(elem)
        assert style['stroke_opacity'] == pytest.approx(0.204)

    def test_stroke_dash_ratio_maps_from_line_type(self):
        elem = _FakeElem('c', {'elem_type': 'segment', 'line_type': 1})
        p = ImportPolicy.from_dict({'stroke_dash_ratio': 'remap:{0:0,1:0.65}'})
        style = p.resolve(elem)
        assert style['stroke_dash_ratio'] == 0.65


class TestResolveStyleOnly:
    def test_base_style_only_ignores_ggb(self):
        elem = _FakeElem('A', {'elem_type': 'point', 'point_size': 5,
                               'obj_color': {'r': 255, 'g': 0, 'b': 0, 'alpha': 1}})
        defaults = {'size_px': 2.0, 'stroke': '#abcdef'}
        style = ImportPolicy.style_only().resolve(elem, defaults=defaults)
        # GGB point_size=5 ignored; defaults used.
        assert style['size_px'] == 2.0
        assert style['stroke'] == '#abcdef'
        # No 'fill' derived from obj_color — style_only never reads ggb_raw.
        assert 'fill' not in style


# ══ Scenario coverage ══════════════════════════════════════════════════

class TestSpecScenarios:
    """Cover the 10 scenarios from the Phase 4 plan."""

    def _point(self, size=5):
        return _FakeElem('A', {
            'elem_type': 'point', 'point_size': size, 'point_style': 0,
            'obj_color': {'r': 255, 'g': 0, 'b': 0, 'alpha': 0},
        })

    def test_scenario_1_verbatim_ggb(self):
        style = ImportPolicy.faithful().resolve(self._point(5))
        assert style['size_px'] == 10

    def test_scenario_3_unified_labels(self):
        p = ImportPolicy(font_size_px=14, label_color='#222222')
        style = p.resolve(self._point())
        assert style['font_size_px'] == 14
        assert style['label_color'] == '#222222'

    def test_scenario_4_all_points_same_size(self):
        style = ImportPolicy(size_px=3).resolve(self._point(size=8))
        assert style['size_px'] == 3

    def test_scenario_5_scaled_sizes(self):
        p = ImportPolicy.from_dict({'size_px': 'scale:1.5'})
        assert p.resolve(self._point(4))['size_px'] == 6

    def test_scenario_10_bw_mode(self):
        p = ImportPolicy(stroke='#000000', fill='#cccccc',
                         label_color='#000000')
        style = p.resolve(self._point())
        assert style['stroke'] == '#000000'
        assert style['fill'] == '#cccccc'
        assert style['label_color'] == '#000000'

    def test_scenario_11_hide_all_labels(self):
        style = ImportPolicy(label_visible=False).resolve(self._point())
        assert style['label_visible'] is False


class TestNewFieldOverrides:
    """Tests for fields added to _FIELD_MAP: font_size_px, point_shape,
    stroke_opacity, stroke_dash_ratio, stroke_linecap."""

    def test_font_size_px_override(self):
        p = ImportPolicy(font_size_px=14)
        style = p.resolve(_FakeElem('A', {'elem_type': 'point', 'point_size': 5}))
        assert style['font_size_px'] == 14

    def test_point_shape_override(self):
        p = ImportPolicy(point_shape='square')
        style = p.resolve(_FakeElem('A', {'elem_type': 'point', 'point_style': 0}))
        assert style['point_shape'] == 'square'

    def test_stroke_opacity_override(self):
        p = ImportPolicy(stroke_opacity=0.5)
        style = p.resolve(_FakeElem('L', {'elem_type': 'segment', 'line_thickness': 2}))
        assert style['stroke_opacity'] == 0.5

    def test_stroke_dash_ratio_override(self):
        p = ImportPolicy(stroke_dash_ratio=0.3)
        style = p.resolve(_FakeElem('L', {'elem_type': 'segment'}))
        assert style['stroke_dash_ratio'] == 0.3

    def test_stroke_linecap_override(self):
        p = ImportPolicy(stroke_linecap='round')
        style = p.resolve(_FakeElem('L', {'elem_type': 'segment'}))
        assert style['stroke_linecap'] == 'round'

    def test_stroke_dash_period_override(self):
        p = ImportPolicy.from_dict({'stroke_dash_period_px': 14})
        style = p.resolve(_FakeElem('L', {'elem_type': 'segment'}))
        assert style['stroke_dash_period_px'] == 14

    def test_raw_derived_fields_can_be_overridden(self):
        p = ImportPolicy(
            visible=False,
            label_text='$Custom$',
            angle_range='reflex',
            tick_count=3,
        )
        style = p.resolve(_FakeElem('α', {
            'elem_type': 'angle',
            'show_object': True,
            'show_label': True,
            'label_caption': 'alpha',
            'angle_style': 1,
            'decoration_lines': 0,
        }))
        assert style['visible'] is False
        assert style['label_text'] == '$Custom$'
        assert style['angle_range'] == 'reflex'
        assert style['tick_count'] == 3

    def test_new_fields_default_to_none(self):
        p = ImportPolicy()
        assert p.font_size_px is None
        assert p.point_shape is None
        assert p.stroke_opacity is None
        assert p.stroke_dash_ratio is None
        assert p.stroke_linecap is None
        assert p.visible is None
        assert p.label_text is None
        assert p.angle_range is None
        assert p.tick_count is None

    def test_from_dict_recognises_new_fields(self):
        p = ImportPolicy.from_dict({
            'font_size_px': 14,
            'point_shape': 'triangle_up',
            'stroke_opacity': 0.8,
            'visible': False,
            'label_text': '$L$',
            'angle_range': 'minor',
            'tick_count': 2,
        })
        assert p.font_size_px == 14
        assert p.point_shape == 'triangle_up'
        assert p.stroke_opacity == 0.8
        assert p.visible is False
        assert p.label_text == '$L$'
        assert p.angle_range == 'minor'
        assert p.tick_count == 2
