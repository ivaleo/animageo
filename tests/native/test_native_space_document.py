"""Registry 1.6 and the space document (3D-1, experimental)."""
from __future__ import annotations

import copy
import json

import pytest

from animageo.native import REGISTRY_VERSION, registry
from animageo.native.document import LoadError
from animageo.native.registry import build_index, registry_problems
from animageo.native.space import document as sdoc
from animageo.native.space.build import SpaceBuilder
from animageo.native.space.registry import (
    SPACE_REGISTRY_VERSION,
    build_space_index,
    space_registry,
    space_registry_problems,
    write_space_index,
)

MINIMUM = {'point3.free', 'point3.on_path', 'point3.on_surface', 'point3.midpoint', 'segment3.by_points',
           'polygon3.by_points', 'plane.by_points', 'polyhedron.cube', 'polyhedron.prism', 'polyhedron.pyramid',
           'polyhedron.tetrahedron', 'section.plane_polyhedron'}


def cube_doc(**camera):
    b = SpaceBuilder('cube', camera=camera or None)
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'])
    b.on_edge('M', cube.edge(9), 0.5)
    b.on_face('F', cube.face(2), 0.25, 0.25)
    b.midpoint('N', 'B', 'C_1')
    b.plane('P', 'M', 'N', 'D_1')
    b.section('S', 'P', 'K')
    return b.data()


# ── registry ──

def test_space_registry_is_1_6_and_consistent():
    reg = space_registry()
    assert SPACE_REGISTRY_VERSION == '1.6'
    assert reg.version == '1.6'
    assert set(reg.ops) == MINIMUM
    assert space_registry_problems() == []
    assert reg.index == build_space_index()
    assert reg.index['extends'] == '1.5'
    assert write_space_index(check=True) == []


def test_plane_registry_is_untouched():
    plane = registry()
    assert REGISTRY_VERSION == '1.5' and plane.version == '1.5'
    assert not (set(plane.ops) & MINIMUM)
    assert registry_problems() == []
    assert plane.index == build_index()
    assert 'point3' not in plane.types


def test_every_space_op_is_experimental_and_new_in_1_6():
    for record in space_registry().ops.values():
        assert record['status'] == 'experimental'
        assert record['since'] == '1.6'


@pytest.mark.parametrize('n,counts', [(3, (2, 9, 5)), (4, (3, 12, 6)), (6, (5, 18, 8))])
def test_prism_outputs_follow_the_count_formula(n, counts):
    reg = space_registry()
    record = reg.get('polyhedron.prism')
    args = {'base': {'kind': 'list', 'items': [{'kind': 'ref', 'elementId': f'P{k}'} for k in range(n)]},
            'top': {'kind': 'ref', 'elementId': 'T'}}
    slots = reg.output_slots(record, args)
    assert slots[0] == 'solid'
    for name, count in zip(('vertex', 'edge', 'face'), counts):
        assert sum(s.startswith(name + '.') for s in slots) == count
        assert reg.output_type(record, f'{name}.{count}', args) is not None
        assert reg.output_type(record, f'{name}.{count + 1}', args) is None


def test_fixed_count_of_cube_and_tetrahedron():
    reg = space_registry()
    cube = reg.output_slots(reg.get('polyhedron.cube'), {})
    tetra = reg.output_slots(reg.get('polyhedron.tetrahedron'), {})
    assert len(cube) == 1 + 6 + 12 + 6
    assert len(tetra) == 1 + 6 + 4


def test_space_reasons_extend_the_plane_catalog():
    reasons = space_registry().reasons
    for reason in ('outside', 'touch', 'flat', 'not_convex', 'not_planar', 'space_unsupported'):
        assert reason in reasons
    assert reasons['space_unsupported']['state'] == 'unsupported'
    assert 'outside' not in registry().reasons


# ── document ──

def test_builder_document_is_valid():
    doc = cube_doc()
    assert sdoc.is_space(doc)
    assert sdoc.validate(doc) == []
    loaded = sdoc.load(json.dumps(doc))
    assert loaded.registry_version == '1.6'


def test_camera_and_ground_in_view_defaults():
    doc = cube_doc(projection='perspective', azimuthDeg=-60, elevationDeg=25, target=[1, 1, 1], distance=12)
    doc['viewDefaults']['ground'] = {'look': 'grid', 'size': 6}
    assert sdoc.validate(doc) == []
    camera = sdoc.camera_of(doc)
    assert camera.projection == 'perspective' and camera.distance == 12
    assert sdoc.camera_of(cube_doc()).projection == 'orthographic'


@pytest.mark.parametrize('mutate,code,pointer', [
    (lambda d: d.pop('space'), 'schema', '/space'),
    (lambda d: d.setdefault('viewDefaults', {}).update(bounds=[0, 0, 1, 1]), 'schema', '/viewDefaults/bounds'),
    (lambda d: d.setdefault('viewDefaults', {}).update(camera={'projection': 'fisheye'}), 'schema',
     '/viewDefaults/camera'),
    (lambda d: d.setdefault('viewDefaults', {}).update(camera={'elevationDeg': 95}), 'schema',
     '/viewDefaults/camera'),
    (lambda d: d.setdefault('viewDefaults', {}).update(ground={'look': 'wood'}), 'schema',
     '/viewDefaults/ground/look'),
    (lambda d: d['inputs'].update(A={'kind': 'point', 'value': [0, 0]}), 'schema', '/inputs/A/kind'),
    (lambda d: d['inputs'].update(A={'kind': 'point3', 'value': [0, 0]}), 'schema', '/inputs/A/value'),
])
def test_structure_rules(mutate, code, pointer):
    doc = cube_doc()
    mutate(doc)
    issues = sdoc.validate(doc)
    assert any(i.code == code and i.path.startswith(pointer) for i in issues), issues
    with pytest.raises(LoadError):
        sdoc.load(doc)


def test_graph_rules():
    doc = cube_doc()
    doc['operations']['op-X'] = {'id': 'op-X', 'op': 'point.midpoint',
                                 'args': {'a': {'kind': 'ref', 'elementId': 'A'},
                                          'b': {'kind': 'ref', 'elementId': 'B'}},
                                 'outputs': [{'slot': 'point', 'elementId': 'X'}]}
    doc['elements']['X'] = {'id': 'X', 'type': 'point', 'displayName': 'X',
                            'producer': {'operationId': 'op-X', 'slot': 'point'}}
    codes = {i.code for i in sdoc.validate(doc)}
    assert 'space_unsupported' in codes

    doc = cube_doc()
    doc['operations']['op-S']['args']['solid'] = {'kind': 'ref', 'elementId': 'A'}
    assert {i.code for i in sdoc.validate(doc)} == {'type_mismatch'}

    doc = cube_doc()
    doc['operationRegistryVersion'] = '1.7'
    doc['operations']['op-M']['op'] = 'point3.on_line'
    codes = {i.code for i in sdoc.validate(doc)}
    assert 'newer_registry' in codes


def test_plane_document_is_not_space_and_round_trips():
    from animageo.native.document import dump, load
    plane = {'format': 'animageo-construction/v1', 'documentId': 'p', 'operationRegistryVersion': '1.5',
             'operations': {}, 'elements': {}}
    assert not sdoc.is_space(plane)
    assert dump(load(copy.deepcopy(plane))) == plane
