"""Tests for elem.ggb_raw capture and the GGB style resolver.

Verifies:
1. Parser populates elem.ggb_raw with raw (unscaled) GGB values.
2. resolve_ggb_style(ggb_raw) reproduces elem.ggb_style for keys the parser touches.

Phase 3 contract: elem.ggb_raw is the single source of truth for GGB input.
Any future ImportPolicy can read from here to decide how to style an element.
"""
import os

import pytest

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser
from animageo.style.enums import ggb_point_style_to_elem_style
from animageo.style.ggb_resolver import resolve_ggb_style


FIXTURE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'examples',
    '0_sample_scenes',
    'scene.ggb',
)


@pytest.fixture(scope='module')
def parsed_scene():
    if not os.path.isfile(FIXTURE):
        pytest.skip(f'Fixture not found: {FIXTURE}')
    c = Construction()
    view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
    ggb_parser.load(c, view, FIXTURE, debug=False)
    return c


class TestGgbRawCapture:
    """elem.ggb_raw holds raw XML values — no ×2, /2, y-invert applied."""

    def test_point_A_raw_point_size(self, parsed_scene):
        # <pointSize val="5"/> → raw=5, NOT 10
        assert parsed_scene.element('A').ggb_raw['point_size'] == 5

    def test_point_D_raw_point_size(self, parsed_scene):
        assert parsed_scene.element('D').ggb_raw['point_size'] == 4

    def test_segment_c_raw_thickness(self, parsed_scene):
        # <lineStyle thickness="5"/> → raw=5, NOT 2.5
        assert parsed_scene.element('c').ggb_raw['line_thickness'] == 5

    def test_angle_alpha_raw_arc_size(self, parsed_scene):
        # <arcSize val="30"/> → raw=30 (no scaling ever applied)
        assert parsed_scene.element('α').ggb_raw['arc_size'] == 30

    def test_point_A_raw_label_offset_not_inverted(self, parsed_scene):
        # <labelOffset x="-28" y="32"/> → raw=[-28, 32] (NOT y-inverted)
        assert parsed_scene.element('A').ggb_raw['label_offset_px'] == [-28, 32]

    def test_point_A_raw_obj_color(self, parsed_scene):
        # <objColor r="21" g="101" b="192" alpha="0"/> → raw rgba dict
        c = parsed_scene.element('A').ggb_raw['obj_color']
        assert c['r'] == 21
        assert c['g'] == 101
        assert c['b'] == 192
        assert c['alpha'] == 0
        assert c['opacity'] == 0
        assert c['hex'] == '#1565c0'

    def test_elem_type_captured(self, parsed_scene):
        assert parsed_scene.element('A').ggb_raw['elem_type'] == 'point'
        assert parsed_scene.element('c').ggb_raw['elem_type'] == 'segment'
        assert parsed_scene.element('α').ggb_raw['elem_type'] == 'angle'

    def test_var_has_empty_ggb_raw(self, parsed_scene):
        # Vars don't receive GGB-raw (parser skips Vars in the style loop).
        pass  # Just confirm no crash during parse.


class TestGgbResolverMatchesParser:
    """resolve_ggb_style(ggb_raw) must equal the import style the parser wrote.

    GGB visual values are intentionally stored in ``elem.ggb_style`` rather
    than ``elem.style`` so ``import.enabled=false`` can disable the whole
    visual import layer without losing ``ggb_raw`` diagnostics.
    """

    def _assert_match(self, derived, elem):
        for k, v in derived.items():
            if k == 'visible':
                assert elem.visible is v
                continue
            assert k in elem.ggb_style, f"parser missing key {k!r}"
            assert elem.ggb_style[k] == v, (
                f"mismatch on {k!r}: derived={v!r}, parser={elem.ggb_style[k]!r}")

    def test_point_A_roundtrip(self, parsed_scene):
        elem = parsed_scene.element('A')
        self._assert_match(resolve_ggb_style(elem.ggb_raw), elem)

    def test_point_D_roundtrip(self, parsed_scene):
        elem = parsed_scene.element('D')
        self._assert_match(resolve_ggb_style(elem.ggb_raw), elem)

    def test_segment_c_roundtrip(self, parsed_scene):
        elem = parsed_scene.element('c')
        self._assert_match(resolve_ggb_style(elem.ggb_raw), elem)

    def test_angle_alpha_roundtrip(self, parsed_scene):
        elem = parsed_scene.element('α')
        self._assert_match(resolve_ggb_style(elem.ggb_raw), elem)


class TestGgbResolverUnit:
    """Unit tests on resolve_ggb_style without going through a full .ggb file."""

    def test_empty_raw(self):
        assert resolve_ggb_style({}) == {'label_offset_px': [0, 0]}

    def test_point_size_only(self):
        result = resolve_ggb_style({'elem_type': 'point', 'point_size': 5})
        assert result['size_px'] == 10
        assert result['label_offset_px'] == [0, 0]

    def test_label_offset_y_inverted(self):
        result = resolve_ggb_style({'label_offset_px': [3, 7]})
        assert result['label_offset_px'] == [3, -7]

    def test_angle_decoration_lines_incremented(self):
        # angle type adds +1 to decoration_lines
        result = resolve_ggb_style({'elem_type': 'angle', 'decoration_lines': 2})
        assert result['tick_count'] == 3

    def test_segment_decoration_lines_unchanged(self):
        result = resolve_ggb_style({'elem_type': 'segment', 'decoration_lines': 2})
        assert result['tick_count'] == 2

    @pytest.mark.parametrize('elem_type, decoration, keys', [
        ('angle', 0, {'tick_count': 1}),
        ('angle', 2, {'tick_count': 3}),
        # GeoGebra DECORATION_ANGLE_*_TICK(S): one arc, ticks across it
        ('angle', 3, {'tick_count': 1, 'arc_tick_count': 1}),
        ('angle', 5, {'tick_count': 1, 'arc_tick_count': 3}),
        # DECORATION_ANGLE_ARROW_ANTICLOCKWISE / _CLOCKWISE: a head on the arc
        ('angle', 6, {'tick_count': 1, 'arrow_head': 'end'}),
        ('angle', 7, {'tick_count': 1, 'arrow_head': 'start'}),
        ('segment', 3, {'tick_count': 3}),
        # DECORATION_SEGMENT_*_ARROW(S): parallel chevrons, no ticks
        ('segment', 4, {'tick_count': 0, 'parallel_count': 1}),
        ('segment', 6, {'tick_count': 0, 'parallel_count': 3}),
        ('vector', 4, {'tick_count': 4}),        # other types: as before
    ])
    def test_decoration_kinds(self, elem_type, decoration, keys):
        from animageo.style.ggb_resolver import ggb_decoration_style
        assert ggb_decoration_style(elem_type, decoration) == keys
        result = resolve_ggb_style({'elem_type': elem_type, 'decoration_lines': decoration})
        assert {k: result[k] for k in keys} == keys
        assert not ({'arc_tick_count', 'arrow_head', 'parallel_count'} - set(keys)) & set(result)


class TestGgbPointStyleMapping:
    """Lock GeoGebra pointStyle codes to AnimaGeo point_shape names."""

    def test_all_geogebra_point_style_codes(self):
        expected = {
            0: 'circle',
            1: 'cross',
            2: 'circle',
            3: 'plus',
            4: 'diamond',
            5: 'diamond',
            6: 'triangle_up',
            7: 'triangle_down',
            8: 'triangle_right',
            9: 'triangle_left',
            10: 'circle',
        }
        for code, shape in expected.items():
            assert ggb_point_style_to_elem_style(code, '#123456')['point_shape'] == shape

    def test_diamond_fill_and_outline_variants(self):
        filled = ggb_point_style_to_elem_style(4, '#123456')
        assert filled['point_shape'] == 'diamond'
        assert filled['fill'] == '#123456'
        assert filled['fill_opacity'] == 1.0
        assert filled['stroke_opacity'] == 0.0

        empty = ggb_point_style_to_elem_style(5, '#123456')
        assert empty['point_shape'] == 'diamond'
        assert empty['fill_opacity'] == 0.0
        assert empty['stroke'] == '#123456'
        assert empty['stroke_opacity'] == 1.0


class TestArcArrowFollowsTheDrawnArc:
    """GeoGebra's decoration 6 / 7 (anticlockwise / clockwise) points along the
    arc as drawn; an arc drawn the other way round swaps end and start."""

    @pytest.mark.parametrize('decoration, flipped, head', [
        (6, False, 'end'), (7, False, 'start'), (6, True, 'start'), (7, True, 'end'),
    ])
    def test_decoration_style(self, decoration, flipped, head):
        from animageo.style.ggb_resolver import ggb_decoration_style
        assert ggb_decoration_style('angle', decoration, flipped)['arrow_head'] == head
        raw = {'elem_type': 'angle', 'decoration_lines': decoration, 'decoration_flipped': flipped}
        assert resolve_ggb_style(raw)['arrow_head'] == head

    @pytest.mark.parametrize('size, angle_range, flipped', [
        (1.0, 'minor', False), (4.0, 'minor', True), (4.0, 'reflex', False), (1.0, 'reflex', True),
    ])
    def test_flip_after_the_build(self, size, angle_range, flipped):
        from types import SimpleNamespace
        from animageo.parsers.ggb_parser import _flip_arc_arrow
        elem = SimpleNamespace(data=SimpleNamespace(size=size))
        raw = {'elem_type': 'angle', 'decoration_lines': 6}
        style = {'angle_range': angle_range, 'arrow_head': 'end'}
        _flip_arc_arrow(elem, raw, style)
        assert style['arrow_head'] == ('start' if flipped else 'end')
        assert raw['decoration_flipped'] is flipped
