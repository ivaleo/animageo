"""Straight lines and perpendicular feet in space registry 1.1."""
import hashlib
import json
import math

import pytest

from animageo.native.space import SpaceBuilder, evaluate, flat_scene, validate
from animageo.native.space.registry import SPACE_REGISTRY_VERSION, space_registry
from animageo.native.space.vec import dot, norm


OPS_11 = {
    'line3.by_points', 'line3.parallel', 'line3.perpendicular_line', 'line3.perpendicular_plane',
    'point3.projection_line', 'point3.projection_plane',
}


def test_additive_registry_and_builder_versions():
    reg = space_registry()
    assert SPACE_REGISTRY_VERSION == '1.1'
    assert {name for name, spec in reg.ops.items() if spec['since'] == '1.1'} == OPS_11
    old = {name: spec['signatureHash'] for name, spec in reg.ops.items() if spec['since'] == '1.0'}
    assert hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest() == '7fdb9081510cfd1babba624d69b0175a0691e7195dad838f51473704b9020913'
    b = SpaceBuilder('versions')
    b.point('A', 0, 0, 0)
    b.point('B', 2, 1, 0)
    assert b.data()['operationRegistryVersion'] == '1.0'
    b.line('l', 'A', 'B')
    doc = b.data()
    assert doc['operationRegistryVersion'] == '1.1'
    assert validate(doc) == []


def test_oriented_lines_have_canonical_origin_and_feet_are_on_unbounded_carriers():
    b = SpaceBuilder('feet')
    b.point('A', 3, 2, -1)
    b.point('B', 4, 2, -1)
    b.point('X', 7, -1, 4)
    b.point('C', 3, 3, -1)
    seg = b.segment('s', 'A', 'B')
    line = b.line('l', 'A', 'B')
    b.line('r', 'B', 'A')
    b.parallel('p', 'X', line)
    b.perpendicular_line('q', 'X', seg)
    b.projection_line('F', 'X', seg)
    b.projection_line('G', 'X', line)
    face = b.polygon('f', 'A', 'B', 'C').main
    plane = b.plane('u', 'A', 'C', 'B')
    b.perpendicular_plane('n', 'X', face)
    b.perpendicular_plane('v', 'X', plane)
    b.projection_plane('H', 'X', face)
    b.projection_plane('I', 'X', plane)
    doc = b.data()
    assert validate(doc) == []
    result = evaluate(doc).elements
    assert all(item['state'] == 'defined' for item in result.values())

    def value(name):
        return result[name]['value']

    assert value('l') == {'p': [0, 2, -1], 'dir': [1, 0, 0]}
    assert value('r') == {'p': [0, 2, -1], 'dir': [-1, 0, 0]}
    assert value('p') == {'p': [0, -1, 4], 'dir': [1, 0, 0]}
    assert value('q')['dir'] == pytest.approx([0, 3 / math.sqrt(34), -5 / math.sqrt(34)])
    assert value('F') == value('G') == {'x': 7, 'y': 2, 'z': -1}
    assert value('H') == value('I') == {'x': 7, 'y': -1, 'z': -1}
    assert value('n') == {'p': [7, -1, 0], 'dir': [0, 0, 1]}
    assert value('v') == {'p': [7, -1, 0], 'dir': [0, 0, -1]}
    for name in ('l', 'r', 'p', 'q', 'n', 'v'):
        assert norm(value(name)['dir']) == pytest.approx(1)
        assert dot(value(name)['dir'], value(name)['p']) == pytest.approx(0, abs=1e-12)

    moved = evaluate(doc, inputs={'X': {'kind': 'point3', 'value': [-8, 3, 4]}}).elements
    assert moved['F']['value'] == {'x': -8, 'y': 2, 'z': -1}
    assert moved['H']['value'] == {'x': -8, 'y': 3, 'z': -1}


def test_undefined_carriers_and_point_on_line_are_distinct():
    b = SpaceBuilder('degenerate')
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.point('X', 3, 0, 0)
    s = b.segment('s', 'A', 'A')
    good = b.line('good', 'A', 'B')
    bad = b.line('bad', 'A', 'A')
    b.perpendicular_line('on', 'X', good)
    b.projection_line('F', 'X', good)
    b.projection_line('G', 'X', s)
    b.parallel('R', 'X', bad)
    b.parallel('S', 'X', s)
    b.perpendicular_line('T', 'X', s)
    b.plane('flat', 'A', 'B', 'X')
    b.perpendicular_plane('N', 'B', 'flat')
    b.projection_plane('P', 'B', 'flat')
    out = evaluate(b.data()).elements
    assert out['F']['value'] == {'x': 3, 'y': 0, 'z': 0}
    assert out['on']['reason'] == 'point_on_line'
    assert out['on']['state'] == 'undefined'
    for name in ('bad', 'G', 'S', 'T'):
        assert out[name]['reason'] == 'coincident_points'
    assert out['R']['reason'] == out['N']['reason'] == out['P']['reason'] == 'upstream'
    assert (out['R']['cause'], out['N']['cause'], out['P']['cause']) == ('bad', 'flat', 'flat')



@pytest.mark.parametrize('origin', [0.0, 1e6, -1e6])
def test_translated_diagonal_agrees_for_a_line_and_its_segment(origin):
    b = SpaceBuilder('translated-diagonal')
    b.point('A', origin, origin, 0)
    b.point('B', origin + 1, origin + 1, 0)
    b.point('P', origin + 2, origin + 2, 0)
    line = b.line('l', 'A', 'B')
    b.line('r', 'B', 'A')
    segment = b.segment('s', 'A', 'B')
    b.perpendicular_line('ql', 'P', line)
    b.perpendicular_line('qs', 'P', segment)
    b.projection_line('fl', 'P', line)
    b.projection_line('fs', 'P', segment)

    doc = b.data()
    on = evaluate(doc).elements
    assert on['ql'] == on['qs'] == {'state': 'undefined', 'type': 'line3', 'reason': 'point_on_line'}
    for name, sign in (('l', 1), ('r', -1)):
        assert on[name]['value']['p'] == pytest.approx([0, 0, 0], abs=1e-12)
        assert on[name]['value']['dir'] == pytest.approx([sign / math.sqrt(2), sign / math.sqrt(2), 0])
    foot = {'x': origin + 2, 'y': origin + 2, 'z': 0}
    assert on['fl']['value'] == on['fs']['value'] == foot

    off = evaluate(doc, inputs={'P': {'kind': 'point3', 'value': [origin + 2, origin + 2, 0.125]}}).elements
    for tip in ('fl', 'fs'):
        for coordinate, expected in foot.items():
            assert off[tip]['value'][coordinate] == pytest.approx(expected, rel=0, abs=1e-12)
    assert off['ql']['value'] == off['qs']['value'] == {'p': [origin + 2, origin + 2, 0], 'dir': [0, 0, -1]}


def stroke(scene, name):
    return next(s for s in scene['strokes'] if s['id'] == name)


def test_finite_frame_clips_lines_before_ordinary_visibility():
    b = SpaceBuilder('cube-shadow')
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.cube('K', 'A', 'B')
    b.point('U', -1, 3, 1)
    b.point('V', 3, 3, 1)
    b.line('l', 'U', 'V')
    doc = b.data()
    doc['appearance'] = {'U': {'visible': False}, 'V': {'visible': False}}
    cam = {'azimuthDeg': -90, 'elevationDeg': 0}
    scene = flat_scene(doc, cam)
    no_line = {**doc, 'appearance': {**doc['appearance'], 'l': {'visible': False}}}
    assert scene['bounds'] == flat_scene(no_line, cam)['bounds']
    xmin, _, xmax, _ = scene['bounds']
    parts = stroke(scene, 'l')['pieces']
    assert [p['visibility'] for p in parts] == ['visible', 'hidden', 'visible']
    assert parts[1]['hiddenBy'] == ['K']
    assert parts[0]['a'] == pytest.approx([xmin, 1])
    assert parts[-1]['b'] == pytest.approx([xmax, 1])
    always = {**doc, 'appearance': {**doc['appearance'], 'l': {'visibility': 'always'}}}
    assert [p['visibility'] for p in stroke(flat_scene(always, cam), 'l')['pieces']] == ['visible']


@pytest.mark.parametrize('projection', ['orthographic', 'oblique', 'perspective'])
def test_clips_each_projection_without_enlarging_frame(projection):
    b = SpaceBuilder('frame')
    b.point('A', 0, -2, -2)
    b.point('B', 0, 2, 2)
    b.point('P', -2, 1, 0)
    b.point('Q', 6, 1, 0)
    b.line('l', 'P', 'Q')
    doc = b.data()
    doc['appearance'] = {'P': {'visible': False}, 'Q': {'visible': False}}
    camera = {'projection': projection, 'azimuthDeg': 0, 'elevationDeg': 10, 'distance': 4}
    truncated = flat_scene(doc, camera)
    without = {**doc, 'appearance': {**doc['appearance'], 'l': {'visible': False}}}
    assert truncated['bounds'] == flat_scene(without, camera)['bounds']
    lo_x, lo_y, hi_x, hi_y = truncated['bounds']
    piece, = stroke(truncated, 'l')['pieces']
    for x, y in (piece['a'], piece['b']):
        assert lo_x - 1e-9 <= x <= hi_x + 1e-9
        assert lo_y - 1e-9 <= y <= hi_y + 1e-9


def test_perspective_near_plane_end_on_and_vanishing_point():
    b = SpaceBuilder('near')
    b.point('A', 0, -2, -2)
    b.point('B', 0, 2, 2)
    b.point('P', 0, 1, 0)
    b.point('Q', 6, 1, 0)
    b.point('U', 0, 0, 0)
    b.point('V', 6, 0, 0)
    b.line('l', 'P', 'Q')
    b.line('eye', 'U', 'V')
    doc = b.data()
    doc['appearance'] = {name: {'visible': False} for name in 'PQUV'}
    cam = {'projection': 'perspective', 'azimuthDeg': 0, 'elevationDeg': 0, 'distance': 4}
    scene = flat_scene(doc, cam)
    piece, = stroke(scene, 'l')['pieces']
    assert piece['a'] == pytest.approx([0, 0])  # t→−∞; no artificial far plane
    assert piece['b'] == pytest.approx([scene['bounds'][2], 0])
    assert stroke(scene, 'eye')['pieces'] == []
    ortho = flat_scene(doc, dict(cam, projection='orthographic'))
    assert stroke(ortho, 'l')['pieces'] == []


def test_perspective_visibility_of_unbounded_side():
    b = SpaceBuilder('far-shadow')
    b.point('A', 0, 0, 0)
    b.point('B', 2, 0, 0)
    b.cube('K', 'A', 'B')
    b.point('P', 0, 1.25, 1)
    b.point('Q', 3, 1.25, 1)
    b.line('l', 'P', 'Q')
    doc = b.data()
    doc['appearance'] = {'P': {'visible': False}, 'Q': {'visible': False}}
    cam = {'projection': 'perspective', 'azimuthDeg': 0, 'elevationDeg': 0,
           'distance': 5, 'target': [1, 1, 1]}
    scene = flat_scene(doc, cam)
    hidden, visible = stroke(scene, 'l')['pieces']
    assert hidden['a'] == pytest.approx([0, 0])
    assert hidden['b'] == pytest.approx([5 * 0.25 / 4, 0])
    assert hidden['visibility'] == 'hidden' and hidden['hiddenBy'] == ['K']
    assert visible['visibility'] == 'visible'


def test_near_plane_limits_an_otherwise_visible_projection():
    b = SpaceBuilder('near-depth')
    b.point('A', 0, -2, -2)
    b.point('B', 0, 2, 2)
    b.point('P', 0, 1e-7, 0)
    b.point('Q', 6, 1e-7, 0)
    b.point('R', 6, -1, 0)
    b.point('S', 6, 1, 0)
    b.line('nearly_end_on', 'P', 'Q')
    b.line('behind', 'R', 'S')
    doc = b.data()
    doc['appearance'] = {name: {'visible': False} for name in 'PQRS'}
    cam = {'projection': 'perspective', 'azimuthDeg': 0, 'elevationDeg': 0, 'distance': 4}
    scene = flat_scene(doc, cam)
    piece, = stroke(scene, 'nearly_end_on')['pieces']
    assert piece['a'] == pytest.approx([0, 0])
    assert piece['b'] == pytest.approx([4e-7 / (1e-6 * scene['scale']), 0])
    assert stroke(scene, 'behind')['pieces'] == []
