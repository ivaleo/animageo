"""Path defaults, independent fill layers and render integration."""
import copy
import math

import pytest

from animageo import native
from animageo.native.paint_fixtures import _Doc
from animageo.style.config import StyleConfig


def nested_document():
    d = _Doc('nested_circle_and_polygon', bounds=(-4, -4, 4, 4))
    d.free('A', -.5, -.5).free('B', .5, -.5).free('C', 0, .5).free('O', 0, 0).free('R', 3, 0)
    d.polygon('inner', 'A', 'B', 'C').circle('outer', 'O', 'R')
    d.doc['operations']['zz_outer'] = d.doc['operations'].pop('op_outer')
    d.doc['operations']['zz_outer']['id'] = 'zz_outer'
    d.doc['elements']['outer']['producer']['operationId'] = 'zz_outer'
    d.overrides('inner', fill='#ff0000', fill_opacity=1)
    d.overrides('outer', fill='#0000ff', fill_opacity=1)
    return d.doc


@pytest.mark.parametrize('style', [None, {}, {'presets': {'color': {'main': '#123456'}}}, StyleConfig.load(None)])
def test_native_default_sorts_by_area_without_mutating_inputs(style):
    doc = nested_document()
    before = copy.deepcopy(doc)
    out = native.resolve_paint(doc, style)
    assert out['fillOrder'] == ['outer', 'inner']
    assert [p['id'] for p in out['partOrder'] if p['part'] == 'fill'] == out['fillOrder']
    assert out['elements']['inner']['fill']['z'] == out['elements']['outer']['fill']['z'] == .01
    assert doc == before


def test_explicit_native_construction_keeps_legacy_order():
    out = native.resolve_paint(nested_document(), {'rendering': {'fill_order': 'construction'}})
    assert out['fillOrder'] == ['inner', 'outer']
    assert out['elements']['inner']['fill']['z'] != out['elements']['outer']['fill']['z']


@pytest.mark.parametrize('key,value,fixed', [('z_index', 7, False), ('z_index_label', -1, False),
                                           ('z_index_fill', 7, True), ('z_index_fill', 0, True),
                                           ('z_index_fill', -.5, True), ('z_index_fill', None, False)])
def test_circle_only_fill_z_excludes_area_sort(key, value, fixed):
    doc = nested_document()
    doc['appearance']['outer']['overrides'][key] = value
    out = native.resolve_paint(doc)
    z = out['elements']['outer']['fill']['z']
    assert (z != .01) == fixed
    if fixed:
        assert z == pytest.approx(value + 8e-6)


def test_polygon_independent_fill_layer_does_not_change_stroke_or_label():
    doc = nested_document()
    old = native.resolve_paint(doc)
    doc['appearance']['inner']['overrides'].update(z_index_fill=7)
    new = native.resolve_paint(doc)
    assert new['fillOrder'] == ['outer', 'inner']
    assert new['elements']['inner']['fill']['z'] > 7
    for part in ('stroke', 'label', 'z'):
        assert new['elements']['inner'][part] == old['elements']['inner'][part]


def test_null_masks_only_its_own_channel():
    doc = nested_document()
    doc['appearance']['inner']['overrides'].update(z_index=8, z_index_fill=None)
    out = native.resolve_paint(doc, {'defaults': {'polygon': {'z_index_fill': -2}}})
    assert out['elements']['inner']['fill']['z'] > 8
    doc['appearance']['inner']['overrides']['z_index'] = None
    assert native.resolve_paint(doc)['elements']['inner']['fill']['z'] == .01


def test_style_contract_and_capability():
    assert native.has('fill_order')
    key = native.style_keys()['rendering']['keys']['fill_order']
    assert key == {'unit': 'enum', 'values': ['area', 'construction'], 'default': 'area'}
    assert 'fill_order' not in StyleConfig.load(None).rendering
    for kind in ('polygon', 'angle', 'mark.right_angle'):
        assert 'z_index_fill' in native.style_keys()['types'][kind]['keys']


@pytest.mark.parametrize('mode', [None, True, 'wrong', 1])
def test_invalid_fill_mode_is_rejected(mode):
    with pytest.raises(ValueError, match='fill_order'):
        StyleConfig.load({'rendering': {'fill_order': mode}})


@pytest.mark.parametrize('z', [True, math.nan, math.inf, '1'])
def test_invalid_fill_z_is_rejected(z):
    with pytest.raises(ValueError, match='z_index_fill'):
        StyleConfig.load({'defaults': {'polygon': {'z_index_fill': z}}})


def classic_scene(style=None):
    from animageo import AnimaGeoScene
    scene = AnimaGeoScene()
    if style is not None:
        scene.applyStyle(style=style)
    scene.putCode('A=Point(-.5,-.5)\nB=Point(.5,-.5)\nC=Point(0,.5)\nO=Point(0,0)\nR=Point(3,0)\ninner=Polygon(A,B,C)\nouter=Circle(O,R)')
    scene.geo.element('inner').style.update(fill='#ff0000', fill_opacity=1)
    scene.geo.element('outer').style.update(fill='#0000ff', fill_opacity=1)
    scene.updateAllGeometry()
    return scene


@pytest.mark.parametrize('mode,expected', [(None, ['inner', 'outer']), ('construction', ['inner', 'outer']),
                                          ('area', ['outer', 'inner'])])
def test_classic_default_and_override(mode, expected):
    scene = classic_scene(None if mode is None else {'rendering': {'fill_order': mode}})
    family = scene._ordered_display_family()
    colors = [m.get_fill_color().to_hex().lower() for m in family if m.get_fill_opacity() > 0
              and m.get_fill_color().to_hex().lower() in ('#ff0000', '#0000ff')]
    assert colors == [{'inner': '#ff0000', 'outer': '#0000ff'}[p] for p in expected]


@pytest.mark.parametrize('source', ['defaults', 'per_type', 'per_name'])
def test_winning_config_source_and_null_masking(source):
    doc = nested_document()
    if source == 'defaults':
        style = {'defaults': {'circle': {'z_index_fill': 7}}}
    else:
        key = 'circle' if source == 'per_type' else 'e_outer'
        style = {'overlay': {source: {key: {'z_index_fill': 7}}}}
    assert native.resolve_paint(doc, style)['elements']['outer']['fill']['z'] > 7
    doc['appearance']['outer']['overrides']['z_index_fill'] = None
    assert native.resolve_paint(doc, style)['elements']['outer']['fill']['z'] == .01


def test_body_only_z_of_conic_and_region_remains_automatic():
    from animageo.native.paint_fixtures import _curves
    from tests.native.test_native_region_paint import area_doc
    doc = _curves()[1][1].doc
    doc['appearance'].setdefault('e', {}).setdefault('overrides', {})['z_index'] = 100
    assert native.resolve_paint(doc)['elements']['e']['fill']['z'] == .01
    assert native.resolve_paint(area_doc({'S': {'overrides': {'z_index': 100}}}))['elements']['S']['fill']['z'] == .01


def test_native_render_passes_path_default_through_bridge(tmp_path):
    from animageo import AnimaGeoScene
    doc = nested_document()
    native.render(doc, fmt='svg', out=tmp_path / 'native.svg')
    scene = AnimaGeoScene()
    scene.loadDocument(doc)
    scene.exportSVG(tmp_path / 'bridge.svg')
    assert (tmp_path / 'native.svg').read_bytes() == (tmp_path / 'bridge.svg').read_bytes()
    scene.applyStyle(style={'rendering': {'fill_order': 'construction'}})
    scene.updateAllGeometry()
    scene.exportSVG(tmp_path / 'construction.svg')
    assert (tmp_path / 'native.svg').read_bytes() != (tmp_path / 'construction.svg').read_bytes()


def test_classic_native_value_does_not_switch_scene_default():
    scene = classic_scene()
    scene.geo.element('outer').data.native_value = {'c': [0, 0], 'r': 3}
    scene.updateAllGeometry()
    assert scene._fill_order_mode() == 'construction'
