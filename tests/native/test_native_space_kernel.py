"""The kernel of space: operations of registry 1.6 evaluated by ID (3D-1)."""
from __future__ import annotations

import math

import pytest

from animageo.native.space.build import SpaceBuilder
from animageo.native.space.evaluate import compare_space_values, evaluate, space_scale
from animageo.native.space.registry import space_registry

CUBE_NAMES = ['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1']


def base(b, n=4, z=0.0, r=1.0):
    ids = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ids.append(b.point(f'P{k}', r * math.cos(a), r * math.sin(a), z))
    return ids


def ev(b, **kw):
    return evaluate(b.data(), **kw).elements


def test_cube_value_and_canonical_outputs():
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=CUBE_NAMES)
    out = ev(b)
    k = out['K']['value']
    assert k['volume'] == pytest.approx(8) and k['area'] == pytest.approx(24)
    assert [out[n]['value'] for n in ('C', 'D_1')] == [{'x': 2.0, 'y': 2.0, 'z': 0.0}, {'x': 0.0, 'y': 2.0, 'z': 2.0}]
    assert out[cube.edge(9)]['value'] == {'a': [0.0, 0.0, 0.0], 'b': [0.0, 0.0, 2.0], 'length': 2.0}
    base_face = out[cube.face(1)]['value']
    assert base_face['normal'] == [0.0, 0.0, -1.0]
    assert base_face['vertices'][0] == [0.0, 0.0, 0.0]          # the first corner is kept
    assert out[cube.face(2)]['value']['normal'] == [0.0, 0.0, 1.0]


def test_cube_on_a_vertical_edge_is_defined():
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 0, 0, 3)
    b.cube('K', 'A', 'B')
    assert ev(b)['K']['value']['volume'] == pytest.approx(27)


@pytest.mark.parametrize('n', [3, 4, 5, 6])
def test_prism_and_pyramid_counts_and_volumes(n):
    b = SpaceBuilder()
    ids = base(b, n)
    b.point('T', 0.2, 0.1, 2.0)
    b.point('S', 0.0, 0.0, 3.0)
    prism = b.prism('Z', ids, 'T')
    b.pyramid('Y', ids, 'S')
    out = ev(b)
    area = 0.5 * n * math.sin(2 * math.pi / n)
    assert out['Z']['value']['volume'] == pytest.approx(area * 2.0)
    assert out['Y']['value']['volume'] == pytest.approx(area)
    assert len(out['Z']['value']['faces']) == n + 2 and len(out['Z']['value']['edges']) == 3 * n
    a = 2 * math.pi / n
    assert out[prism.vertex(1)]['value'] == pytest.approx({'x': math.cos(a) - 0.8, 'y': math.sin(a) + 0.1, 'z': 2.0})
    assert sum(s.startswith('vertex.') for s in prism.slots) == n - 1     # A_1 is the input T


def test_tetrahedron_and_section():
    b = SpaceBuilder()
    for name, p in zip('ABCD', [(0, 0, 0), (4, 0, 0), (0, 4, 0), (0, 0, 4)]):
        b.point(name, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    b.midpoint('M', 'A', 'B')
    b.midpoint('N', 'A', 'C')
    b.midpoint('K', 'A', 'D')
    b.plane('P', 'M', 'N', 'K')
    b.section('S', 'P', 'T')
    out = ev(b)
    assert out['T']['value']['volume'] == pytest.approx(64 / 6)
    cut = out['S']['value']
    assert len(cut['polygon']) == 3
    assert sorted(len(f) for f in cut['faces']) == [1, 1, 1]


def test_points_on_edges_and_faces():
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=CUBE_NAMES)
    b.on_edge('M', cube.edge(9), 0.25)
    b.on_edge('Q', cube.edge(9), 7)                 # clamped to the end
    b.on_face('F', cube.face(2), 0.5, 0.5)
    out = ev(b)
    assert out['M']['value'] == {'x': 0.0, 'y': 0.0, 'z': 0.5}
    assert out['Q']['value'] == {'x': 0.0, 'y': 0.0, 'z': 2.0}
    assert out['F']['value'] == {'x': 1.0, 'y': 1.0, 'z': 2.0}
    moved = evaluate(b.data(), inputs={'M': {'kind': 'pathParameter', 'value': 0.5}}).elements
    assert moved['M']['value']['z'] == 1.0


def test_polygon_and_plane():
    b = SpaceBuilder()
    for name, p in zip('ABCD', [(0, 0, 0), (2, 0, 0), (2, 2, 1), (0, 2, 1)]):
        b.point(name, *p)
    poly = b.polygon('Q', 'A', 'B', 'C', 'D')
    b.plane('P', 'A', 'B', 'D')
    out = ev(b)
    q = out['Q']['value']
    assert q['area'] == pytest.approx(2 * math.sqrt(5))
    assert out[poly.side(2)]['value']['length'] == pytest.approx(math.sqrt(5))
    n = out['P']['value']['n']
    assert n == pytest.approx([0, -1 / math.sqrt(5), 2 / math.sqrt(5)])
    assert out['P']['value']['p'] == pytest.approx([0, 0, 0])


@pytest.mark.parametrize('build,element,reason', [
    (lambda b: (b.point('A', 0, 0, 0), b.point('B', 0, 0, 0), b.cube('K', 'A', 'B')), 'K', 'coincident_points'),
    (lambda b: (b.point('A', 0, 0, 0), b.point('B', 1, 0, 0), b.point('C', 2, 0, 0), b.plane('P', 'A', 'B', 'C')),
     'P', 'collinear_points'),
    (lambda b: (base(b, 4), b.point('T', 3, 3, 0), b.prism('Z', ['P0', 'P1', 'P2', 'P3'], 'T')), 'Z', 'flat'),
    (lambda b: ([b.point(f'Q{k}', x, y, 0) for k, (x, y) in enumerate([(0, 0), (4, 0), (2, 1), (2, 4)])],
                b.point('S', 0, 0, 2), b.pyramid('Y', ['Q0', 'Q1', 'Q2', 'Q3'], 'S')), 'Y', 'not_convex'),
    (lambda b: (b.point('A', 0, 0, 0), b.point('B', 1, 0, 0), b.point('C', 1, 1, 0), b.point('D', 0, 1, 1),
                b.point('S', 0, 0, 3), b.pyramid('Y', ['A', 'B', 'C', 'D'], 'S')), 'Y', 'not_planar'),
    (lambda b: (b.point('A', 0, 0, 0), b.point('B', 1, 0, 0), b.point('C', 0, 1, 0), b.point('D', 1, 1, 0),
                b.tetrahedron('T', 'A', 'B', 'C', 'D')), 'T', 'flat'),
])
def test_undefined_reasons(build, element, reason):
    b = SpaceBuilder()
    build(b)
    rec = ev(b)[element]
    assert (rec['state'], rec['reason']) == ('undefined', reason)


def test_section_outside_and_touch():
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.cube('K', 'A', 'B', vertices=CUBE_NAMES)
    for name, p in zip(('U', 'V', 'W'), [(0, 0, 5), (1, 0, 5), (0, 1, 5)]):
        b.point(name, *p)
    b.plane('Far', 'U', 'V', 'W')
    b.section('S1', 'Far', 'K')
    b.point('E', 4, 0, 0)
    b.point('F', 0, 4, 0)
    b.point('G', 2, 2, 2)
    b.plane('Edge', 'E', 'F', 'G')                  # x + y = 4: only the edge C C_1
    b.section('S2', 'Edge', 'K')
    out = ev(b)
    assert out['S1']['reason'] == 'outside'
    assert out['S2']['reason'] == 'touch'


def test_upstream_unsupported_and_cycle():
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 0, 0, 0)
    cube = b.cube('K', 'A', 'B')
    b.on_edge('M', cube.edge(1), 0.5)
    doc = b.data()
    out = evaluate(doc).elements
    assert (out['M']['state'], out['M']['reason'], out['M']['cause']) == ('undefined', 'upstream', 'K_edge_1')

    doc['operations']['op-X'] = {'id': 'op-X', 'op': 'point.midpoint',
                                 'args': {'a': {'kind': 'ref', 'elementId': 'A'},
                                          'b': {'kind': 'ref', 'elementId': 'A'}},
                                 'outputs': [{'slot': 'point', 'elementId': 'X'}]}
    doc['elements']['X'] = {'id': 'X', 'type': 'point', 'displayName': 'X',
                            'producer': {'operationId': 'op-X', 'slot': 'point'}}
    out = evaluate(doc).elements
    assert (out['X']['state'], out['X']['reason']) == ('unsupported', 'space_unsupported')

    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 1, 0, 0)
    b.segment('s', 'A', 'B')
    doc = b.data()
    doc['operations']['op-s']['args']['a'] = {'kind': 'ref', 'elementId': 'm'}
    doc['operations']['op-m'] = {'id': 'op-m', 'op': 'point3.on_path', 'args': {'path': {'kind': 'ref',
                                                                                          'elementId': 's'}},
                                 'outputs': [{'slot': 'point', 'elementId': 'm'}]}
    doc['elements']['m'] = {'id': 'm', 'type': 'point3', 'displayName': 'm',
                            'producer': {'operationId': 'op-m', 'slot': 'point'}}
    doc['inputs']['m'] = {'kind': 'pathParameter', 'value': 0.5}
    out = evaluate(doc).elements
    assert out['s']['reason'] == 'cycle' and out['m']['reason'] == 'cycle'


def test_scale_and_tolerances():
    assert space_scale([]) == 1.0
    assert space_scale([(0, 0, 0), (3, 4, 12)]) == 13.0
    b = SpaceBuilder()
    b.point('A', 0, 0, 0)
    b.point('B', 30, 40, 120)
    result = evaluate(b.data())
    assert result.scale == 130.0 and result.registry == '1.6'


def test_compare_space_values_by_kind():
    info = space_registry().types['polyhedron']
    a = {'vertices': [[0, 0, 0]], 'faces': [[0]], 'edges': [], 'area': 1.0, 'volume': 1.0}
    near = dict(a, volume=1.0 + 5e-10)
    assert compare_space_values(info, a, near, 1.0) == []
    assert compare_space_values(info, a, dict(a, volume=1.0 + 5e-9), 1.0)
    assert compare_space_values(info, a, dict(a, faces=[[1]]), 1.0)
