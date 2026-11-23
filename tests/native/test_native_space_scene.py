"""The flat scene ``/1`` of a space document and its plane document (3D-1)."""
from __future__ import annotations

import pytest

from animageo.native import REGISTRY_VERSION
from animageo.native.document import validate as validate_plane
from animageo.native.space.bridge import HIDDEN_LOOKS, piece_id, space_style, to_document
from animageo.native.space.build import SpaceBuilder
from animageo.native.space import scene as scene_module
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


def test_a_section_of_a_hidden_solid_is_a_plane_figure():
    """1.11.0rc8: the solid hidden, its section shown — the section is drawn
    as a polygon (rank 0: its fill with the sheets, its sides hidden only by
    the solids that are drawn), not a KeyError."""
    doc = cube_doc()
    doc['appearance'] = {'K': {'visible': False}}
    flat = flat_scene(doc)
    assert flat['solids'] == []
    fills = [f for f in flat['fills'] if f['id'] == 'S']
    assert len(fills) == 1 and fills[0]['role'] == 'section' and fills[0]['layer'] == 0
    assert 'solid' not in fills[0]
    sides = [s for s in flat['strokes'] if s['id'] == 'S']
    assert [s['part'] for s in sides] == ['side.1', 'side.2', 'side.3', 'side.4']
    for side in sides:
        assert 'solid' not in side and side['role'] == 'section'
        assert [p['visibility'] for p in side['pieces']] == ['visible'] and side['pieces'][0]['layer'] == 10
    shown = flat_scene(cube_doc())
    assert [f['polygon'] for f in shown['fills'] if f['id'] == 'S'] == [fills[0]['polygon']]
    plane = to_document(flat, doc)
    assert [i for i in validate_plane(plane) if i.severity == 'error'] == []


def _python311_left_sum(values):
    """Isolate the old float reduction at the scene boundary on newer Python."""
    total = 0.0
    for value in values:
        total += value
    return total


@pytest.mark.parametrize('legacy_sum', [False, True], ids=['native-sum', 'python311-left-fold'])
def test_equal_fill_depth_keeps_exact_id_tie(monkeypatch, legacy_sum):
    # Both rectangles are centred on the camera target, so their mean depth is
    # exactly the eye distance. No golden fixture or sum implementation is an oracle.
    b = SpaceBuilder('equal_fill_depth', camera={'projection': 'perspective', 'azimuthDeg': -50,
                     'elevationDeg': 22, 'target': [1, 1, 1], 'distance': 14})
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.cube('K', 'A', 'B', vertices=CUBE_NAMES)
    for name, xyz in [('U', (0, 0, .5)), ('V', (2, 0, 1.5)), ('W', (0, 2, .5))]:
        b.point(name, *xyz)
    b.plane('P', 'U', 'V', 'W')
    b.section('S', 'P', 'K')
    doc = b.data()
    doc['appearance'] = {'K': {'visible': False}}
    if legacy_sum:
        monkeypatch.setattr(scene_module, 'sum', _python311_left_sum, raising=False)
    fills = flat_scene(doc)['fills']
    assert [(f['id'], f['role']) for f in fills] == [('P', 'plane'), ('S', 'section')]
    assert [f['depth'] for f in fills] == [14.0, 14.0]


@pytest.mark.parametrize('legacy_sum', [False, True], ids=['native-sum', 'python311-left-fold'])
@pytest.mark.parametrize('gap', [2.0 ** -40, 2.0], ids=['close-but-unequal', 'separated'])
def test_unequal_fill_depth_precedes_id_order(monkeypatch, legacy_sum, gap):
    # An exact axis-aligned projection gives constant depths 14 and 14+gap.
    # Z must precede A even for a gap below common geometry tolerances.
    b = SpaceBuilder('unequal_fill_depth', camera={'azimuthDeg': 0, 'elevationDeg': 0,
                                                 'target': [0, 0, 0]})
    for name, depth in [('A', 14.0), ('Z', 14.0 + gap)]:
        points = []
        for index, (y, z) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)]):
            points.append(b.point(f'{name}{index}', -depth, y, z))
        b.polygon(name, *points)
    if legacy_sum:
        monkeypatch.setattr(scene_module, 'sum', _python311_left_sum, raising=False)
    fills = flat_scene(b.data())['fills']
    assert [f['id'] for f in fills] == ['Z', 'A']
    assert [f['depth'] for f in fills] == [14.0 + gap, 14.0]
    assert fills[0]['depth'] > fills[1]['depth']


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


def _add_cube(b, name, x, y, z, size=2):
    a = b.point(f'{name}A', x, y, z)
    q = b.point(f'{name}B', x + size, y, z)
    return b.cube(name, a, q)


def _intersecting_cubes():
    b = SpaceBuilder('intersecting', camera={'azimuthDeg': 45, 'elevationDeg': 0})
    _add_cube(b, 'K', 0, 0, 0)
    _add_cube(b, 'J', 1, -1, 0)
    _add_cube(b, 'T', 7, 0, 0)
    for name, pt in {'P': (2, 0, 1), 'Q': (2, 2, 1), 'R': (1, 1, 1),
                     'U': (3, 1, 1)}.items():
        b.point(name, *pt)
    b.plane('pl', 'P', 'Q', 'R')
    b.section('cut', 'pl', 'K')
    b.section('cutJ', 'pl', 'J')
    b.segment('kFront', 'P', 'Q')
    b.segment('jFront', 'R', 'U')
    return b


def test_intersecting_cubes_keep_the_outline_and_lose_only_ambiguous_fills():
    flat = flat_scene(_intersecting_cubes().data())
    assert flat['diagnostics'] == [{'code': 'overlap_order', 'id': 'J', 'otherId': 'K'}]
    assert set(flat['solids']) == {'J', 'K', 'T'}
    assert {(f['role'], f.get('solid')) for f in flat['fills']} == {('plane', None), ('face', 'T')}
    assert {s['solid'] for s in flat['strokes'] if s['role'] == 'edge'} == {'J', 'K', 'T'}
    assert {s['id'] for s in flat['strokes'] if s['role'] == 'section'} == {'cut', 'cutJ'}
    assert {'KA', 'JA', 'P', 'Q'} <= {p['id'] for p in flat['points']}
    # The front surface alternates between the two bodies across this projection.
    # On each face, the first half of the probe sits behind the other body.
    strokes = strokes_by_id(flat)
    for probe, occluder in [('kFront', 'J'), ('jFront', 'K')]:
        hidden, visible = strokes[(probe, None)]['pieces']
        assert (hidden['visibility'], hidden['hiddenBy'], visible['visibility']) == ('hidden', [occluder], 'visible')
        assert hidden['t'] == pytest.approx([0, 0.5])
        assert visible['t'] == pytest.approx([0.5, 1])


def test_hiding_a_solid_restores_supported_fills():
    doc = _intersecting_cubes().data()
    doc['appearance'] = {'K': {'visible': False}}
    flat = flat_scene(doc)
    assert flat['diagnostics'] == []
    assert {f.get('solid') for f in flat['fills'] if f['role'] == 'face'} == {'J', 'T'}
    assert {(f['id'], f.get('solid')) for f in flat['fills'] if f['role'] == 'section'} == {
        ('cut', None), ('cutJ', 'J'),
    }


@pytest.mark.parametrize('contact', [(2, 0, 0), (2, 2, 0), (2, 2, 2), (2.5, 1, 1)])
def test_cube_contact_and_separation_preserve_fills(contact):
    b = SpaceBuilder('contact')
    _add_cube(b, 'K', 0, 0, 0)
    _add_cube(b, 'J', *contact)
    flat = flat_scene(b.data())
    assert flat['diagnostics'] == []
    assert {f['solid'] for f in flat['fills']} == {'J', 'K'}


@pytest.mark.parametrize('y,intersect', [(3, False), (2.25, False), (1, True)])
@pytest.mark.parametrize('shift', [0, 1_000_000])
def test_oblique_prism_and_cube_with_overlapping_bounds(y, intersect, shift):
    # Their face-normal intervals all overlap. At y=3 the edge-cross axis
    # z-y separates the solids; at y=2.25 they touch along the support of that axis.
    b = SpaceBuilder('prism', camera={'target': [shift] * 3})
    _add_cube(b, 'K', shift, shift, shift)
    for name, (x, dy, z) in {'P': (2, 0, -1), 'Q': (3, 1, 1), 'R': (3, 3, -1),
                              'U': (2, 2, -3), 'V': (0, -2, -3)}.items():
        b.point(name, x + shift, dy + y + shift, z + 0.25 + shift)
    b.prism('J', ['P', 'Q', 'R', 'U'], 'V')
    flat = flat_scene(b.data())
    assert flat['diagnostics'] == ([{'code': 'overlap_order', 'id': 'J', 'otherId': 'K'}] if intersect else [])
    assert {f['solid'] for f in flat['fills']} == (set() if intersect else {'J', 'K'})


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


@pytest.mark.parametrize('build', ['by_points', 'parallel', 'perpendicular'])
def test_a_scene_of_lines_alone_is_framed_by_their_supports(build):
    b = SpaceBuilder('lines-only', camera=CAMERA)
    b.point('A', 0, 0, 0)
    b.point('B', 3, 1, 0)
    b.point('P', 1, 2, 2)
    b.line('l', 'A', 'B')
    shown = {'l': 'l', 'parallel': 'm', 'perpendicular': 'q'}
    if build == 'parallel':
        b.parallel('m', 'P', 'l')
    elif build == 'perpendicular':
        b.perpendicular_line('q', 'P', 'l')
    doc = b.data()
    drawn = 'l' if build == 'by_points' else shown[build]
    doc['appearance'] = {el: {'visible': False} for el in doc['elements'] if el != drawn}
    flat = flat_scene(doc)
    stroke, = flat['strokes']
    assert stroke['id'] == drawn and stroke['pieces']
    assert flat['points'] == [] and flat['bounds'][0] < flat['bounds'][2]
    xmin, ymin, xmax, ymax = flat['bounds']
    for piece in stroke['pieces']:
        for x, y in (piece['a'], piece['b']):
            assert xmin - 1e-9 <= x <= xmax + 1e-9 and ymin - 1e-9 <= y <= ymax + 1e-9


def test_a_scene_with_nothing_drawn_is_still_empty():
    b = SpaceBuilder('nothing', camera=CAMERA)
    b.point('A', 0, 0, 0)
    b.point('B', 3, 1, 0)
    b.line('l', 'A', 'B')
    doc = b.data()
    doc['appearance'] = {el: {'visible': False} for el in doc['elements']}
    with pytest.raises(ValueError, match='empty'):
        flat_scene(doc)


def test_the_sheet_hugs_what_it_is_drawn_around():
    """The sheet of a plane leaves ``SHEET_MARGIN`` of the size of its points and
    sections on each side (the school sheet of the reference drawings), not a
    large parallelogram far beyond the solid. In a parallel view the sheet is a
    parallelogram and its affine coordinates are those of the plane."""
    from animageo.native.space.section import SHEET_MARGIN

    flat = flat_scene(cube_doc({**CAMERA, 'projection': 'orthographic'}))
    sheet = next(f['polygon'] for f in flat['fills'] if f['role'] == 'plane')
    cut = next(f['polygon'] for f in flat['fills'] if f['role'] == 'section')
    around = cut + [p['at'] for p in flat['points'] if p['id'] in ('M', 'N', 'D_1')]
    o, a, b = sheet[0], sheet[1], sheet[3]
    ax, ay, bx, by = a[0] - o[0], a[1] - o[1], b[0] - o[0], b[1] - o[1]
    det = ax * by - ay * bx

    def coords(p):
        px, py = p[0] - o[0], p[1] - o[1]
        return ((px * by - py * bx) / det, (ax * py - ay * px) / det)

    us, vs = zip(*(coords(p) for p in around))
    edge = SHEET_MARGIN / (1 + 2 * SHEET_MARGIN)
    for lo, hi in ((min(us), max(us)), (min(vs), max(vs))):
        assert lo == pytest.approx(edge, abs=1e-9) and hi == pytest.approx(1 - edge, abs=1e-9)
    assert SHEET_MARGIN == 0.12
