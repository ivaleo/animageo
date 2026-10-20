"""Parity fixtures of space (3D-1): ``animageo-space-parity/v1`` in
``animageo/native/parity/v1/space`` — the reference the TypeScript copy of
the kernel and the projector (``frontend/src/canvas/space``) replays.

Two kinds of files, ``{format, id, kind, registry, generatedBy, cases}``:

- ``kind: "values"`` (``space_values_*.json``) — a case ``{name, document,
  inputs, expect: {scale, elements}}``: ``elements`` is
  :func:`~animageo.native.space.evaluate.evaluate` of the document (state,
  type, value or reason and cause by element ID). A value compares by the
  kinds of its type (``ops/v1/space/_types.json``): a length within
  ``1e-9·S``, an area ``1e-9·S²``, a volume ``1e-9·S³``, a scalar ``1e-9``,
  a field without a kind (indices) exactly; a state, a reason and a cause
  exactly.
- ``kind: "flat"`` (``space_flat_*.json``) — a case ``{name, document,
  planeLook, views: [{name, camera, expect}]}``: ``expect`` is the flat
  scene ``animageo-flat-scene/1`` (:func:`~animageo.native.space.scene.flat_scene`)
  of the document seen by ``camera``. Numbers compare within ``1e-9·max(1,
  scale)``, everything else (ids, parts, roles, visibility, layers, the
  number of pieces) exactly. Every scene is seen by two or three cameras of
  a grid (orthographic orbits, the oblique view, a perspective; the
  degenerate scenes also from the top, the front and the side).

Numbers are rounded to 9 decimals as in the 2D fixtures. A value case whose
decision lies near its threshold (``tol/m < |value| < m·tol``,
``decisionMargin`` of ``_numeric.json``) is refused: degenerate cases are
exactly degenerate, the others far from degeneracy.

    python -m animageo.native fixtures space [-o <dir>] [--check]
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .build import SpaceBuilder
from .evaluate import compare_space_values, evaluate
from .registry import SPACE_REGISTRY_VERSION, space_registry
from .scene import flat_scene

__all__ = ['SPACE_PARITY_FORMAT', 'DEFAULT_DIR', 'CAMERAS', 'build_fixtures', 'write_fixtures', 'check_fixtures',
           'verify_fixture', 'verify_fixtures', 'value_themes', 'flat_themes']

SPACE_PARITY_FORMAT = 'animageo-space-parity/v1'
DEFAULT_DIR = Path(__file__).resolve().parents[1] / 'parity' / 'v1' / 'space'
TOLERANCE = 1e-9
CUBE = ['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1']

# The camera grid of the flat scenes (the target is the scene's).
CAMERAS = {
    'ortho-a': {'projection': 'orthographic', 'azimuthDeg': -60, 'elevationDeg': 25},
    'ortho-b': {'projection': 'orthographic', 'azimuthDeg': 35, 'elevationDeg': 40},
    'ortho-low': {'projection': 'orthographic', 'azimuthDeg': -110, 'elevationDeg': 8},
    'oblique': {'projection': 'oblique'},
    'persp': {'projection': 'perspective', 'azimuthDeg': -50, 'elevationDeg': 22, 'distance': 14},
}


def _round(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 9) + 0.0
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return value


def _regular(b, n, *, r=1.0, z=0.0, cx=0.0, cy=0.0, phase=0.0, prefix='P'):
    ids = []
    for k in range(n):
        a = phase + 2 * math.pi * k / n
        ids.append(b.point(f'{prefix}{k}', cx + r * math.cos(a), cy + r * math.sin(a), z))
    return ids


def _cube(b, a=(0, 0, 0), bb=(2, 0, 0), solid='K', names=CUBE):
    b.point('A', *a)
    b.point('B', *bb)
    return b.cube(solid, 'A', 'B', vertices=names)


# ── value scenes ─────────────────────────────────────────────────────────

def _solids():
    out = []
    for name, a, bb in (('cube_axis', (0, 0, 0), (2, 0, 0)), ('cube_turned', (1, 1, 0), (3, 2, 0)),
                        ('cube_tilted', (0, 0, 0), (1, 1, 1)), ('cube_vertical', (0, 0, 0), (0, 0, 2))):
        b = SpaceBuilder(name)
        _cube(b, a, bb)
        out.append((name, b))
    for n in (3, 4, 5, 6):
        b = SpaceBuilder(f'prism_{n}')
        base = _regular(b, n, phase=0.3)
        b.point('T', math.cos(0.3) + 0.25, math.sin(0.3) - 0.5, 2.5)
        b.prism('Z', base, 'T')
        out.append((f'prism_{n}', b))
    b = SpaceBuilder('prism_right')
    base = _regular(b, 6, r=1.5)
    b.point('T', 1.5, 0, 3)
    b.prism('Z', base, 'T')
    out.append(('prism_right', b))
    for n in (3, 4, 5, 6):
        b = SpaceBuilder(f'pyramid_{n}')
        base = _regular(b, n, phase=0.1)
        b.point('S', 0.1, -0.2, 2.0)
        b.pyramid('Y', base, 'S')
        out.append((f'pyramid_{n}', b))
    b = SpaceBuilder('pyramid_slanted')
    for name, p in zip(('A', 'B', 'C', 'D'), [(0, 0, 0), (3, 0, 0), (3, 2, 0), (0, 2, 0)]):
        b.point(name, *p)
    b.point('S', 4, 3, 2)
    b.pyramid('Y', ['A', 'B', 'C', 'D'], 'S')
    out.append(('pyramid_slanted', b))
    b = SpaceBuilder('tetra_corner')
    for name, p in zip('ABCD', [(0, 0, 0), (3, 0, 0), (0, 2, 0), (0, 0, 1.5)]):
        b.point(name, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    out.append(('tetra_corner', b))
    b = SpaceBuilder('tetra_regular')
    s = math.sqrt(3)
    for name, p in zip('ABCD', [(0, 0, 0), (2, 0, 0), (1, s, 0), (1, s / 3, 2 * math.sqrt(2 / 3))]):
        b.point(name, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    out.append(('tetra_regular', b))
    return out


def _points():
    out = []
    for name, t in (('on_edge_start', 0.0), ('on_edge_inside', 0.3), ('on_edge_end', 1.0), ('on_edge_clamped', 1.5)):
        b = SpaceBuilder(name)
        cube = _cube(b)
        b.on_edge('M', cube.edge(9), t)
        b.on_edge('L', cube.edge(6), t)
        out.append((name, b))
    for name, face, u, v in (('on_face_top', 2, 0.25, 0.5), ('on_face_side', 4, 0.5, 0.75),
                             ('on_face_outside', 3, 1.25, -0.5)):
        b = SpaceBuilder(name)
        cube = _cube(b, (0, 0, 0), (2, 1, 0))
        b.on_face('F', cube.face(face), u, v)
        out.append((name, b))
    b = SpaceBuilder('midpoints_and_segment')
    _cube(b)
    b.midpoint('M', 'A', 'C_1')
    b.midpoint('N', 'B_1', 'D')
    b.segment('s', 'M', 'C')
    out.append(('midpoints_and_segment', b))
    b = SpaceBuilder('polygons')
    for name, p in zip('ABCDE', [(0, 0, 0), (2, 0, 0), (2, 2, 1), (0, 2, 1), (1, 3, 1.5)]):
        b.point(name, *p)
    b.polygon('Q', 'A', 'B', 'C', 'D')
    b.polygon('R', 'A', 'B', 'E')
    out.append(('polygons', b))
    b = SpaceBuilder('planes')
    for name, p in zip('ABCDEF', [(0, 0, 0), (2, 0, 0), (0, 2, 0), (1, 1, 3), (0, 0, 1), (3, 1, -1)]):
        b.point(name, *p)
    b.plane('P', 'A', 'B', 'C')
    b.plane('Q', 'B', 'D', 'E')
    b.plane('R', 'F', 'D', 'A')
    out.append(('planes', b))
    return out


def _cut(name, build, a, bb, c):
    b = SpaceBuilder(name)
    solid = build(b)
    for label, p in zip(('U', 'V', 'W'), (a, bb, c)):
        b.point(label, *p)
    b.plane('P', 'U', 'V', 'W')
    b.section('S', 'P', solid)
    return name, b


def _cube_solid(b):
    _cube(b)
    return 'K'


def _sections():
    out = [
        _cut('cube_triangle', _cube_solid, (1, 0, 0), (0, 1, 0), (0, 0, 1.5)),
        _cut('cube_quad', _cube_solid, (0, 0, 0.5), (2, 0, 1.5), (0, 2, 0.5)),
        _cut('cube_pentagon', _cube_solid, (1, 0, 0), (0, 1.5, 0), (2, 2, 1.25)),
        _cut('cube_hexagon', _cube_solid, (1, 0, 0), (2, 1, 0), (0, 2, 1.5)),
        _cut('cube_diagonal', _cube_solid, (0, 0, 0), (2, 2, 0), (2, 2, 2)),
        _cut('cube_outside', _cube_solid, (0, 0, 3), (1, 0, 3), (0, 1, 3.5)),
        _cut('cube_touch_vertex', _cube_solid, (2, 2, 2), (4, 2, 0), (2, 4, 0)),
        _cut('cube_touch_edge', _cube_solid, (4, 0, 0), (0, 4, 0), (2, 2, 2)),
        _cut('cube_through_edge', _cube_solid, (0, 0, 0), (2, 0, 0), (2, 2, 2)),
    ]

    def tetra(b):
        for label, p in zip('ABCD', [(0, 0, 0), (4, 0, 0), (0, 4, 0), (0, 0, 4)]):
            b.point(label, *p)
        b.tetrahedron('T', 'A', 'B', 'C', 'D')
        return 'T'

    def prism(b):
        base = _regular(b, 5, r=1.5)
        b.point('X', 1.5, 0, 3)
        b.prism('Z', base, 'X')
        return 'Z'

    def pyramid(b):
        base = _regular(b, 4, r=2)
        b.point('X', 0, 0, 3)
        b.pyramid('Y', base, 'X')
        return 'Y'

    out += [_cut('tetra_middle', tetra, (2, 0, 0), (0, 2, 0), (0, 0, 2)),
            _cut('tetra_parallel_edge', tetra, (1, 0, 0), (1, 1, 0), (0, 0, 2.5)),
            _cut('prism_slanted', prism, (0, 0, 0.5), (1, 0, 1), (0, 1, 2)),
            _cut('pyramid_horizontal', pyramid, (0, 0, 1), (1, 0, 1), (0, 1, 1)),
            _cut('pyramid_vertical', pyramid, (0.5, 0, 0), (0.5, 1, 0), (0.5, 0, 1))]
    return out


def _reasons():
    out = []
    b = SpaceBuilder('cube_coincident')
    _cube(b, (1, 1, 1), (1, 1, 1))
    b.midpoint('M', 'C', 'A')
    out.append(('cube_coincident', b))
    b = SpaceBuilder('prism_flat')
    base = _regular(b, 4)
    b.point('T', 3, 2, 0)
    b.prism('Z', base, 'T')
    out.append(('prism_flat', b))
    b = SpaceBuilder('pyramid_not_convex')
    for k, (x, y) in enumerate([(0, 0), (4, 0), (2, 1), (2, 4)]):
        b.point(f'Q{k}', x, y, 0)
    b.point('S', 1, 1, 2)
    b.pyramid('Y', ['Q0', 'Q1', 'Q2', 'Q3'], 'S')
    out.append(('pyramid_not_convex', b))
    b = SpaceBuilder('pyramid_not_planar')
    for name, p in zip('ABCD', [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 1)]):
        b.point(name, *p)
    b.point('S', 1, 1, 3)
    b.pyramid('Y', ['A', 'B', 'C', 'D'], 'S')
    out.append(('pyramid_not_planar', b))
    b = SpaceBuilder('tetra_flat')
    for name, p in zip('ABCD', [(0, 0, 0), (2, 0, 0), (0, 2, 0), (1, 1, 0)]):
        b.point(name, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    out.append(('tetra_flat', b))
    b = SpaceBuilder('polygon_collinear')
    for name, p in zip('ABC', [(0, 0, 0), (1, 1, 1), (2, 2, 2)]):
        b.point(name, *p)
    b.polygon('Q', 'A', 'B', 'C')
    b.plane('P', 'A', 'B', 'C')
    out.append(('polygon_collinear', b))
    b = SpaceBuilder('polygon_not_planar')
    for name, p in zip('ABCD', [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 1)]):
        b.point(name, *p)
    b.polygon('Q', 'A', 'B', 'C', 'D')
    out.append(('polygon_not_planar', b))
    b = SpaceBuilder('upstream_chain')
    cube = _cube(b, (0, 0, 0), (0, 0, 0))
    b.on_edge('M', cube.edge(9), 0.5)
    b.on_face('F', cube.face(1), 0.5, 0.5)
    b.point('X', 1, 1, 1)
    b.segment('s', 'M', 'X')
    out.append(('upstream_chain', b))
    b = SpaceBuilder('plane_op_in_space')
    b.point('A', 0, 0, 0)
    b.point('B', 1, 0, 0)
    doc = b.data()
    doc['operations']['op-X'] = {'id': 'op-X', 'op': 'point.midpoint',
                                 'args': {'a': {'kind': 'ref', 'elementId': 'A'}, 'b': {'kind': 'ref', 'elementId': 'B'}},
                                 'outputs': [{'slot': 'point', 'elementId': 'X'}]}
    doc['elements']['X'] = {'id': 'X', 'type': 'point', 'displayName': 'X',
                            'producer': {'operationId': 'op-X', 'slot': 'point'}}
    out.append(('plane_op_in_space', doc))
    doc = dict(doc, operationRegistryVersion='1.1', documentId='newer_registry')
    doc['operations'] = dict(doc['operations'])
    doc['operations']['op-X'] = dict(doc['operations']['op-X'], op='point3.on_line')
    out.append(('newer_registry', doc))
    b = SpaceBuilder('cycle')
    b.point('A', 0, 0, 0)
    b.point('B', 1, 0, 0)
    b.segment('s', 'A', 'B')
    doc = b.data()
    doc['operations']['op-s']['args']['a'] = {'kind': 'ref', 'elementId': 'm'}
    doc['operations']['op-m'] = {'id': 'op-m', 'op': 'point3.on_path',
                                 'args': {'path': {'kind': 'ref', 'elementId': 's'}},
                                 'outputs': [{'slot': 'point', 'elementId': 'm'}]}
    doc['elements']['m'] = {'id': 'm', 'type': 'point3', 'displayName': 'm',
                            'producer': {'operationId': 'op-m', 'slot': 'point'}}
    doc['inputs']['m'] = {'kind': 'pathParameter', 'value': 0.5}
    out.append(('cycle', doc))
    return out


def value_themes():
    """``[(file stem, [(case name, builder or document), …])]``."""
    return [('space_values_solids', _solids()), ('space_values_points', _points()),
            ('space_values_sections', _sections()), ('space_values_reasons', _reasons())]


# ── flat scenes ──────────────────────────────────────────────────────────

def _target(points):
    return [sum(p[i] for p in points) / len(points) for i in range(3)]


def _flat_solids():
    out = []
    b = SpaceBuilder('cube')
    _cube(b)
    out.append(('cube', b, [1, 1, 1], ('ortho-a', 'ortho-b', 'persp')))
    for n in (3, 6):
        b = SpaceBuilder(f'prism_{n}')
        base = _regular(b, n, r=1.5)
        b.point('T', 1.5, 0, 3)
        b.prism('Z', base, 'T')
        out.append((f'prism_{n}', b, [0, 0, 1.5], ('ortho-a', 'ortho-low', 'oblique')))
    for n in (4, 5):
        b = SpaceBuilder(f'pyramid_{n}')
        base = _regular(b, n, r=1.5, phase=0.2)
        b.point('S', 0, 0, 2.5)
        b.pyramid('Y', base, 'S')
        out.append((f'pyramid_{n}', b, [0, 0, 1], ('ortho-a', 'ortho-b', 'persp')))
    b = SpaceBuilder('tetrahedron')
    for name, p in zip('ABCD', [(0, 0, 0), (3, 0, 0), (1, 2.5, 0), (1.2, 0.9, 2.4)]):
        b.point(name, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    out.append(('tetrahedron', b, [1.3, 0.8, 0.8], ('ortho-a', 'ortho-low', 'oblique')))
    b = SpaceBuilder('two_solids')
    _cube(b)
    base = _regular(b, 4, r=1, cx=-2.5, cy=3.5, prefix='Q')
    b.point('S', -2.5, 3.5, 2.5)
    b.pyramid('Y', base, 'S')
    out.append(('two_solids', b, [-0.5, 2, 1], ('ortho-a', 'ortho-b', 'persp')))
    b = SpaceBuilder('points_and_segments')
    cube = _cube(b)
    b.on_face('F', cube.face(2), 0.25, 0.25)
    b.on_face('G', cube.face(5), 0.5, 0.5)
    b.on_edge('M', cube.edge(12), 0.5)
    b.segment('s', 'F', 'G')
    b.segment('r', 'M', 'B_1')
    out.append(('points_and_segments', b, [1, 1, 1], ('ortho-a', 'ortho-b', 'ortho-low')))
    b = SpaceBuilder('segment_behind')
    _cube(b)
    b.point('U', -3, -1, 1)
    b.point('V', 1, 5, 1.5)
    b.segment('s', 'U', 'V')
    out.append(('segment_behind', b, [0, 1.5, 1], ('ortho-a', 'oblique', 'persp')))
    return out


def _flat_sections():
    out = []
    # far_plane: the triangle of cube_triangle three times as far, a sheet of the plane far beyond the
    # cube — the frame reaches three times as far, the labels keep their pixels (test_native_space_render_manim)
    for name, (a, bb, c), cams in (('cube_triangle', ((1, 0, 0), (0, 1, 0), (0, 0, 1.5)), ('ortho-a', 'ortho-b')),
                                   ('cube_far_plane', ((3, 0, 0), (0, 3, 0), (0, 0, 4.5)), ('ortho-a', 'ortho-b')),
                                   ('cube_quad', ((0, 0, 0.5), (2, 0, 1.5), (0, 2, 0.5)), ('ortho-a', 'persp')),
                                   ('cube_pentagon', ((1, 0, 0), (0, 1.5, 0), (2, 2, 1.25)), ('ortho-a', 'oblique')),
                                   ('cube_hexagon', ((1, 0, 0), (2, 1, 0), (0, 2, 1.5)),
                                    ('ortho-a', 'ortho-b', 'ortho-low'))):
        _n, b = _cut(name, _cube_solid, a, bb, c)
        out.append((f'section_{name}', b, [1, 1, 1], cams))
    _n, b = _cut('tetra', lambda b: (
        [b.point(label, *p) for label, p in zip('ABCD', [(0, 0, 0), (4, 0, 0), (0, 4, 0), (0, 0, 4)])],
        b.tetrahedron('T', 'A', 'B', 'C', 'D'))[-1].main, (2, 0, 0), (0, 2, 0), (0, 0, 2))
    out.append(('section_tetra', b, [1, 1, 1], ('ortho-a', 'ortho-b')))

    def pyramid(b):
        base = _regular(b, 4, r=2)
        b.point('X', 0, 0, 3)
        b.pyramid('Y', base, 'X')
        return 'Y'
    _n, b = _cut('pyramid', pyramid, (0.5, 0, 0), (0.5, 1, 0), (-0.5, 0, 1.5))
    out.append(('section_pyramid', b, [0, 0, 1], ('ortho-a', 'persp')))
    # 1.11.0rc8: the cube hidden, its section shown — a plane figure
    _n, b = _cut('hidden_solid', _cube_solid, (0, 0, 0.5), (2, 0, 1.5), (0, 2, 0.5))
    doc = b.data()
    doc['appearance'] = {'K': {'visible': False}}
    out.append(('section_hidden_solid', doc, [1, 1, 1], ('ortho-a', 'persp')))
    return out


def _flat_degenerate():
    out = []
    b = SpaceBuilder('top_view')
    _cube(b)
    out.append(('top_view', b, [1, 1, 1], ('top', 'ortho-a')))
    b = SpaceBuilder('front_view')
    _cube(b)
    out.append(('front_view', b, [1, 1, 1], ('front', 'side')))
    _n, b = _cut('through_vertices', _cube_solid, (0, 0, 0), (2, 2, 0), (2, 2, 2))
    out.append(('through_vertices', b, [1, 1, 1], ('ortho-a', 'ortho-b')))
    _n, b = _cut('side_on_edge', _cube_solid, (0, 0, 0), (2, 0, 0), (2, 2, 2))
    out.append(('side_on_edge', b, [1, 1, 1], ('ortho-a', 'ortho-low')))
    _n, b = _cut('touch_vertex', _cube_solid, (2, 2, 2), (4, 2, 0), (2, 4, 0))
    out.append(('touch_vertex', b, [1, 1, 1], ('ortho-a', 'oblique')))
    b = SpaceBuilder('point_on_edge')
    cube = _cube(b)
    b.on_edge('M', cube.edge(3), 0.5)
    b.on_edge('N', cube.edge(5), 0.5)
    out.append(('point_on_edge', b, [1, 1, 1], ('ortho-a', 'ortho-b', 'persp')))
    return out


EXTRA_CAMERAS = {
    'top': {'projection': 'orthographic', 'azimuthDeg': 0, 'elevationDeg': 90},
    'front': {'projection': 'orthographic', 'azimuthDeg': -90, 'elevationDeg': 0},
    'side': {'projection': 'orthographic', 'azimuthDeg': 0, 'elevationDeg': 0},
}


def flat_themes():
    """``[(file stem, [(scene name, builder, target, camera names), …])]``."""
    return [('space_flat_solids', _flat_solids()), ('space_flat_sections', _flat_sections()),
            ('space_flat_degenerate', _flat_degenerate())]


def _camera(name, target):
    cam = dict(CAMERAS.get(name) or EXTRA_CAMERAS[name])
    cam['target'] = [float(c) for c in target]
    return cam


# ── build, check, replay ─────────────────────────────────────────────────

def _document(item):
    return item.data() if isinstance(item, SpaceBuilder) else item


def _values_expect(document, inputs=None, decisions=None) -> dict:
    result = evaluate(document, inputs=inputs, _decisions=decisions)
    return _round({'scale': result.scale, 'elements': result.elements})


def _margin_problems(decisions) -> list:
    from ..parity import decision_margin
    factor = decision_margin()
    return [f'{op_id}: {name} = {value!r} is within {factor:g}·tol of its threshold'
            for op_id, name, value, tol in decisions
            if math.isfinite(value) and tol / factor < abs(value) < factor * tol]


def _value_rows(cases) -> list:
    rows = []
    for name, item in cases:
        document = _document(item)
        decisions = []
        expect = _values_expect(document, None, decisions)
        problems = _margin_problems(decisions)
        if problems:
            raise ValueError(f'space fixture {name}: near-degenerate decisions: {problems}')
        rows.append({'name': name, 'document': document, 'inputs': None, 'expect': expect})
    return rows


def _flat_rows(scenes) -> list:
    rows = []
    for name, item, target, cameras in scenes:
        document = _document(item)
        views = []
        for cam_name in cameras:
            camera = _camera(cam_name, target)
            views.append({'name': cam_name, 'camera': camera,
                          'expect': _round(flat_scene(document, camera, plane_look='sheet'))})
        rows.append({'name': name, 'document': document, 'planeLook': 'sheet', 'views': views})
    return rows


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    from ... import __version__
    out = {}
    for stem, cases in value_themes():
        out[stem + '.json'] = {'format': SPACE_PARITY_FORMAT, 'id': stem, 'kind': 'values',
                               'registry': SPACE_REGISTRY_VERSION, 'generatedBy': f'animageo {__version__}',
                               'cases': _value_rows(cases)}
    for stem, scenes in flat_themes():
        out[stem + '.json'] = {'format': SPACE_PARITY_FORMAT, 'id': stem, 'kind': 'flat',
                               'registry': SPACE_REGISTRY_VERSION, 'generatedBy': f'animageo {__version__}',
                               'cases': _flat_rows(scenes)}
    return out


def _dump(fixture) -> str:
    return json.dumps(fixture, ensure_ascii=False, indent=1) + '\n'


def write_fixtures(directory=DEFAULT_DIR) -> list:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside)."""
    directory = Path(directory)
    problems = []
    built = build_fixtures()
    for name, fixture in sorted(built.items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        old = json.loads(path.read_text(encoding='utf-8'))
        old.pop('generatedBy', None)
        new = dict(fixture)
        new.pop('generatedBy', None)
        if old != json.loads(json.dumps(new)):
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')):
        if path.name not in built:
            problems.append(f'{path}: not built here')
    return problems


def _compare(expected, actual, tol, where) -> list:
    if isinstance(expected, bool) or isinstance(actual, bool) or expected is None or actual is None:
        return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return [] if abs(expected - actual) <= tol else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f'{where}: expected {len(expected)} items, got {len(actual)}']
        out = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += _compare(e, a, tol, f'{where}[{i}]')
        return out
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return [f'{where}: keys {sorted(expected)} != {sorted(actual)}']
        out = []
        for key in sorted(expected):
            out += _compare(expected[key], actual[key], tol, f'{where}.{key}')
        return out
    return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']


def _verify_values(case, where) -> list:
    actual = _values_expect(case['document'], case.get('inputs'))
    expect = case['expect']
    scale = expect['scale']
    out = _compare(scale, actual['scale'], TOLERANCE * scale, where + '.scale')
    types = space_registry().types
    exp_el, act_el = expect['elements'], actual['elements']
    if set(exp_el) != set(act_el):
        return out + [f'{where}: elements {sorted(exp_el)} != {sorted(act_el)}']
    for el_id in sorted(exp_el):
        e, a = exp_el[el_id], act_el[el_id]
        head = {k: v for k, v in e.items() if k != 'value'}
        if head != {k: v for k, v in a.items() if k != 'value'}:
            out.append(f'{where} {el_id}: expected {head}, got {a}')
            continue
        if 'value' in e:
            out += compare_space_values(types.get(e['type'], {}), e['value'], a['value'], scale,
                                        f'{where} {el_id}')
    return out


def _verify_flat(case, where) -> list:
    out = []
    for view in case['views']:
        actual = _round(flat_scene(case['document'], view['camera'], plane_look=case.get('planeLook', 'sheet')))
        expect = view['expect']
        out += _compare(expect, actual, TOLERANCE * max(1.0, float(expect.get('scale') or 1.0)),
                        f"{where}@{view['name']}")
    return out


def verify_fixture(fixture: dict, label: str = '') -> tuple:
    """``(cases, mismatches)`` of one ``animageo-space-parity/v1`` fixture."""
    label = label or str(fixture.get('id', '?'))
    out = []
    check = _verify_flat if fixture.get('kind') == 'flat' else _verify_values
    for case in fixture.get('cases') or []:
        where = f"{label} [{case.get('name')}]"
        try:
            out += check(case, where)
        except (KeyError, ValueError) as exc:
            out.append(f'{where}: {exc}')
    return len(fixture.get('cases') or []), out


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` over the fixtures in ``directory``."""
    files = cases = 0
    mismatches = []
    for path in sorted(Path(directory).glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        n, out = verify_fixture(fixture, path.stem)
        files += 1
        cases += n
        mismatches += out
    return files, cases, mismatches
