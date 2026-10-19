"""The flat scene ``/1`` of a space document and its plane document (3D-1)."""
from __future__ import annotations

import pytest

from animageo.native import REGISTRY_VERSION
from animageo.native.document import validate as validate_plane
from animageo.native.space.bridge import HIDDEN_LOOKS, piece_id, space_style, to_document
from animageo.native.space.build import SpaceBuilder
from animageo.native.space.scene import FLAT_SCENE_FORMAT, flat_scene

CUBE_NAMES = ['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1']
CAMERA = {'azimuthDeg': -60, 'elevationDeg': 25, 'target': [1, 1, 1]}


def cube_doc(camera=CAMERA, section=True):
    b = SpaceBuilder('cube', camera=camera)
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=CUBE_NAMES)
    if section:
        b.on_edge('M', cube.edge(9), 0.5)
        b.midpoint('N', 'B', 'C_1')
        b.plane('P', 'M', 'N', 'D_1')
        b.section('S', 'P', 'K')
    return b.data()


def strokes_by_id(flat):
    return {(s['id'], s['part']): s for s in flat['strokes']}


def test_ids_are_element_ids():
    doc = cube_doc()
    flat = flat_scene(doc)
    assert flat['format'] == FLAT_SCENE_FORMAT == 'animageo-flat-scene/1'
    elements = set(doc['elements'])
    for item in flat['fills'] + flat['strokes'] + flat['points']:
        assert item['id'] in elements
    assert {s['id'] for s in flat['strokes'] if s['role'] == 'edge'} == {f'K_edge_{k}' for k in range(1, 13)}
    assert [s['part'] for s in flat['strokes'] if s['id'] == 'S'] == ['side.1', 'side.2', 'side.3', 'side.4']
    assert flat['solids'] == ['K']
    assert flat['diagnostics'] == []


def test_school_rules_on_a_cube():
    flat = flat_scene(cube_doc(section=False))
    hidden = {s['id'] for s in flat['strokes'] if any(p['visibility'] == 'hidden' for p in s['pieces'])}
    # seen from azimuth -60, above: the three edges at D are hidden
    assert hidden == {'K_edge_3', 'K_edge_4', 'K_edge_12'}
    points = {p['id']: p['visibility'] for p in flat['points']}
    assert points['D'] == 'hidden' and points['B'] == 'visible'
    faces = {f['id']: f['facing'] for f in flat['fills'] if f['role'] == 'face'}
    assert sorted(v for v in faces.values()) == ['back'] * 3 + ['front'] * 3


def test_layers():
    flat = flat_scene(cube_doc())
    layers = [f['layer'] for f in flat['fills']]
    assert layers == sorted(layers)                       # painting order
    assert {f['role']: f['layer'] for f in flat['fills']} == {'plane': 0, 'face': 14, 'section': 12}
    for s in flat['strokes']:
        for p in s['pieces']:
            assert p['layer'] == (13 if p['visibility'] == 'hidden' else 20)


def test_cameras_and_projections():
    for camera in ({'projection': 'oblique', 'target': [1, 1, 1]},
                   {'projection': 'perspective', 'azimuthDeg': -50, 'elevationDeg': 20, 'target': [1, 1, 1],
                    'distance': 12},
                   {'azimuthDeg': 0, 'elevationDeg': 90, 'target': [1, 1, 1]}):
        flat = flat_scene(cube_doc(), camera)
        assert flat['camera']['projection'] == camera.get('projection', 'orthographic')
    top = flat_scene(cube_doc(section=False), {'azimuthDeg': 0, 'elevationDeg': 90, 'target': [1, 1, 1]})
    vertical = [s for s in top['strokes'] if s['id'] in ('K_edge_9', 'K_edge_10', 'K_edge_11', 'K_edge_12')]
    assert all(s['pieces'] == [] for s in vertical)       # seen end-on
    with pytest.raises(ValueError, match='behind_eye'):
        flat_scene(cube_doc(), {'projection': 'perspective', 'target': [1, 1, 1], 'distance': 1.0})


def test_visibility_policy_and_hidden_elements():
    doc = cube_doc(section=False)
    doc['appearance'] = {'K_edge_4': {'visibility': 'always'}, 'K_face_1': {'visible': False},
                         'D': {'visibility': 'always'}}
    flat = flat_scene(doc)
    edge = strokes_by_id(flat)[('K_edge_4', None)]
    assert [p['visibility'] for p in edge['pieces']] == ['visible']
    assert 'K_face_1' not in {f['id'] for f in flat['fills']}
    assert {p['id']: p['visibility'] for p in flat['points']}['D'] == 'visible'
    doc['appearance'] = {'K': {'visible': False}}
    flat = flat_scene(doc)
    assert flat['solids'] == [] and not [s for s in flat['strokes'] if s['role'] == 'edge']
    doc['appearance'] = {'K_edge_4': {'visibility': 'sometimes'}}
    with pytest.raises(ValueError, match='visibility'):
        flat_scene(doc)


def test_undefined_elements_are_diagnosed_not_drawn():
    b = SpaceBuilder('bad')
    b.point('A', 0, 0, 0)
    b.point('B', 0, 0, 0)
    b.point('C', 1, 1, 1)
    b.cube('K', 'A', 'B')
    flat = flat_scene(b.data())
    assert {d['id'] for d in flat['diagnostics']} >= {'K', 'K_edge_1', 'K_face_6'}
    assert {p['id'] for p in flat['points']} == {'A', 'B', 'C'}


def test_a_segment_behind_a_solid_is_cut_into_pieces():
    b = SpaceBuilder('behind', camera={'azimuthDeg': 0, 'elevationDeg': 0, 'target': [0, 0, 0]})
    b.point('A', -1, -1, -1)
    b.point('B', 1, -1, -1)
    b.cube('K', 'A', 'B')
    b.point('U', -5, -4, 0)                # a line behind the cube, seen from +x
    b.point('V', -5, 4, 0)
    b.segment('s', 'U', 'V')
    doc = b.data()
    flat = flat_scene(doc)
    seg = strokes_by_id(flat)[('s', None)]
    assert [p['visibility'] for p in seg['pieces']] == ['visible', 'hidden', 'visible']
    assert seg['pieces'][1]['hiddenBy'] == ['K'] and seg['pieces'][1]['t'] == pytest.approx([0.375, 0.625])


# ── the plane document ──

def test_plane_document_is_valid_and_keeps_ids():
    doc = cube_doc()
    flat = flat_scene(doc)
    plane = to_document(flat, doc)
    assert [i for i in validate_plane(plane) if i.severity == 'error'] == []
    assert plane['operationRegistryVersion'] == REGISTRY_VERSION
    for p in flat['points']:
        assert plane['elements'][p['id']]['displayName'] == doc['elements'][p['id']]['displayName']
    assert piece_id('S', 'side.3', 1) in plane['elements']
    assert 'K_face_2' in plane['elements']


def test_hidden_piece_paint_is_the_element_paint_with_space_hidden():
    doc = cube_doc(section=False)
    doc['appearance'] = {'K_edge_3': {'overrides': {'stroke_width_px': 3.0, 'stroke_opacity': 0.8}},
                         'K_edge_12': {'overrides': {'hidden_look': 'thin'}}}
    plane = to_document(flat_scene(doc), doc)
    hidden = plane['appearance'][piece_id('K_edge_3', None, 1)]['overrides']
    assert hidden['stroke_opacity'] == pytest.approx(0.8 * 0.55)
    assert hidden['stroke_width_px'] == pytest.approx(3.0)
    assert (hidden['stroke_dash_ratio'], hidden['stroke_dash_period_px']) == (0.55, 8.0)
    thin = plane['appearance'][piece_id('K_edge_12', None, 1)]['overrides']
    assert 'stroke_dash_ratio' not in thin and thin['stroke_width_px'] == pytest.approx(1.5 * 0.5)
    seen = plane['appearance'][piece_id('K_edge_1', None, 1)]['overrides']
    assert 'stroke_dash_ratio' not in seen and 'stroke_opacity' not in seen


def test_space_style_keys_and_looks():
    style = space_style({'space': {'hidden': {'look': 'none'}, 'face': {'fill_opacity_back': 0.2}}})
    assert style['hidden']['look'] == 'none' and style['face']['fill_opacity_back'] == 0.2
    assert style['section']['fill_opacity'] == 0.7
    doc = cube_doc(section=False)
    flat = flat_scene(doc)
    plane = to_document(flat, doc, style_config={'space': {'hidden': {'look': 'none'}}})
    assert piece_id('K_edge_3', None, 1) not in plane['elements']
    plane = to_document(flat, doc, style_config={'space': {'face': {'look': 'none'}}})
    assert 'K_face_1' not in plane['elements']
    with pytest.raises(ValueError):
        space_style({'space': {'hidden': {'look': 'wavy'}}})
    assert set(HIDDEN_LOOKS) == {'dashpale', 'dash', 'pale', 'thin', 'both', 'none'}


def test_z_index_follows_layers():
    doc = cube_doc()
    flat = flat_scene(doc)
    plane = to_document(flat, doc)
    z = {el_id: a.get('overrides', {}).get('z_index') for el_id, a in plane['appearance'].items()}
    assert z['P'] < z['K_face_1'] < z['S'] < z[piece_id('K_edge_3', None, 1)] < z['K_face_2'] < \
        z[piece_id('K_edge_1', None, 1)] < 50
