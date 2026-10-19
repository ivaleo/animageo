"""Implementations of the operations of space (space registry 1.0).

Each takes the resolved arguments (``Input`` s of
:mod:`animageo.native.kernel.values`) and an ``OpContext`` and returns
``{slot: value | Undefined}``. Values (``ops/v1/space/_types.json``):

| type       | value |
|------------|-------|
| point3     | ``{x, y, z}`` |
| segment3   | ``{a: [x, y, z], b: [x, y, z], length}`` |
| polygon3   | ``{vertices: [[x, y, z], …], normal: [x, y, z], area}`` |
| plane      | ``{p: [x, y, z], n: [x, y, z]}`` — ``p`` the projection of the origin |
| polyhedron | ``{vertices, faces, edges, area, volume}`` |
| section    | ``{polygon: [[x, y, z], …], faces: [[k, …], …]}`` |

The canonical order of a solid (the indices of its value and its outputs
``vertex.k``, ``edge.k``, ``face.k``): a prism over ``A, B, …`` (``n``
vertices) has the vertices ``A …, A_1 …`` (the top over the base), the
edges — the sides of the base, of the top, then the lateral ones ``AA_1,
BB_1, …``, the faces — the base, the top, then ``ABB_1A_1, …``; a pyramid —
the base and the apex ``S``; the edges of the base, then ``AS, BS, …``; the
faces — the base, then ``ABS, …``. A cube is the prism on the square
``ABCD`` over its edge ``AB``: ``AD`` is horizontal and square to ``AB``
(``z × AB``; ``AB`` vertical — ``AB × x``), ``AA_1 = AB × AD / |AB|``. A
tetrahedron ``ABCD`` is the pyramid on ``ABC`` with the apex ``D``.

Only the vertices the solid makes are outputs: ``vertex.k`` of a cube are
``C, D, A_1, B_1, C_1, D_1``, of a prism — the top but ``A_1`` (it is the
input ``top``): ``B_1, C_1, …``; a pyramid and a tetrahedron make none
(their vertices are their inputs). A face ring is
counterclockwise seen from outside: a canonical ring that looks inside is
reversed keeping its first vertex (``A B C D`` → ``A D C B``); the
``polygon3`` of a face has that ring and the outward normal.

Decisions use the decide tolerance of the scene (``1e-10·S``) as a length.
"""
from __future__ import annotations

import math

from ..kernel.values import Undefined
from . import vec
from .section import section as cut_solid
from .solids import Plane, Polyhedron

__all__ = ['IMPLEMENTATIONS', 'polyhedron_of', 'plane_of', 'xyz']


def xyz(value) -> tuple:
    """The coordinates of a ``point3`` value."""
    return (float(value['x']), float(value['y']), float(value['z']))


def _p(inp) -> tuple:
    return xyz(inp.value)


def _point(p) -> dict:
    return {'x': p[0], 'y': p[1], 'z': p[2]}


def _list(p) -> list:
    return [p[0], p[1], p[2]]


def _segment(a, b) -> dict:
    return {'a': _list(a), 'b': _list(b), 'length': vec.dist(a, b)}


def _newell(ring):
    n = (0.0, 0.0, 0.0)
    for i, p in enumerate(ring):
        q = ring[(i + 1) % len(ring)]
        n = vec.add(n, ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]),
                        (p[0] - q[0]) * (p[1] + q[1])))
    return n


def _diameter(points) -> float:
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return vec.norm(vec.sub(hi, lo))


def _flat_ring(ring, ctx, *, convex=False):
    """``(unit normal, area)`` of a planar ring, or an :class:`Undefined`
    (``collinear_points``, ``not_planar``, ``not_convex``)."""
    tol = ctx.tol.decide_length
    n = _newell(ring)
    area = vec.norm(n) / 2.0
    diam = _diameter(ring)
    ctx.decide('collinear', area / diam if diam > 0 else 0.0, tol)
    if diam <= tol or area <= tol * diam:
        return Undefined('collinear_points')
    unit = vec.mul(n, 1.0 / vec.norm(n))
    off = max(abs(vec.dot(unit, vec.sub(p, ring[0]))) for p in ring)
    ctx.decide('planar', off, tol)
    if off > tol:
        return Undefined('not_planar')
    if convex:
        turns = 0.0
        k = len(ring)
        for i in range(k):
            e1 = vec.sub(ring[(i + 1) % k], ring[i])
            e2 = vec.sub(ring[(i + 2) % k], ring[(i + 1) % k])
            c = vec.dot(unit, vec.cross(e1, e2))
            if c < -tol * diam:
                return Undefined('not_convex')
            turns += math.atan2(c, vec.dot(e1, e2))
        if abs(turns - 2.0 * math.pi) > 1e-6:
            return Undefined('not_convex')
    return unit, area


def _face_area(ring) -> float:
    return vec.norm(_newell(ring)) / 2.0


def _outward(vertices, faces):
    """The rings of ``faces`` counterclockwise seen from outside: a ring whose
    normal looks inside is reversed keeping its first vertex (``A B C D`` →
    ``A D C B``), so the frame of a face (its first corner) is that of the
    canonical order."""
    centre = vec.centroid(vertices)
    rings = []
    for ring in faces:
        pts = [vertices[i] for i in ring]
        if vec.dot(_newell(pts), vec.sub(vec.centroid(pts), centre)) < 0:
            ring = (ring[0],) + tuple(reversed(ring[1:]))
        rings.append(tuple(ring))
    return rings


def _solid(vertices, faces, edges, made, ctx):
    """``{solid, vertex.k, edge.k, face.k}`` of a convex solid in canonical
    order; the last ``made`` vertices are the outputs ``vertex.k``."""
    faces = _outward(vertices, faces)
    try:
        poly = Polyhedron(vertices, faces, [str(i) for i in range(len(vertices))])
    except ValueError as exc:
        code = str(exc).split(':')[0]
        reason = {'flat': 'flat', 'not_convex': 'not_convex', 'face_not_planar': 'not_planar',
                  'degenerate_face': 'collinear_points'}.get(code)
        if reason is None:
            raise
        return _all_undefined(made, len(edges), len(faces), Undefined(reason))
    rings = [[poly.vertices[i] for i in ring] for ring in poly.faces]
    area = sum(_face_area(r) for r in rings)
    volume = 0.0
    for ring in rings:
        p0 = ring[0]
        for i in range(1, len(ring) - 1):
            volume += vec.dot(p0, vec.cross(ring[i], ring[i + 1])) / 6.0
    out = {'solid': {'vertices': [_list(v) for v in poly.vertices], 'faces': [list(r) for r in poly.faces],
                     'edges': [[i, j] for i, j in edges], 'area': area, 'volume': abs(volume)}}
    first = len(poly.vertices) - made
    for k, v in enumerate(poly.vertices[first:], 1):
        out[f'vertex.{k}'] = _point(v)
    for k, (i, j) in enumerate(edges, 1):
        out[f'edge.{k}'] = _segment(poly.vertices[i], poly.vertices[j])
    for k, ring in enumerate(poly.faces, 1):
        pts = [poly.vertices[i] for i in ring]
        out[f'face.{k}'] = {'vertices': [_list(p) for p in pts], 'normal': _list(poly.normals[k - 1]),
                            'area': _face_area(pts)}
    return out


def _all_undefined(nv, ne, nf, undefined):
    out = {'solid': undefined}
    for name, n in (('vertex', nv), ('edge', ne), ('face', nf)):
        for k in range(1, n + 1):
            out[f'{name}.{k}'] = undefined
    return out


def _prism_topology(n):
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    edges = [(k, (k + 1) % n) for k in range(n)] + [(n + k, n + (k + 1) % n) for k in range(n)]
    edges += [(k, n + k) for k in range(n)]
    return faces, edges


def _pyramid_topology(n):
    faces = [tuple(range(n))] + [(k, (k + 1) % n, n) for k in range(n)]
    edges = [(k, (k + 1) % n) for k in range(n)] + [(k, n) for k in range(n)]
    return faces, edges


# ── points, segments, polygons, planes ───────────────────────────────────

def _point3_free(args, ctx):
    x, y, z = ctx.input['value']
    return {'point': _point((float(x), float(y), float(z)))}


def _point3_on_path(args, ctx):
    seg = args['path'].value
    t = min(1.0, max(0.0, float(ctx.input['value'])))
    return {'point': _point(vec.lerp(tuple(seg['a']), tuple(seg['b']), t))}


def _point3_on_surface(args, ctx):
    pts = [tuple(p) for p in args['surface'].value['vertices']]
    u, v = (float(c) for c in ctx.input['value'])
    p = vec.add(pts[0], vec.add(vec.mul(vec.sub(pts[1], pts[0]), u), vec.mul(vec.sub(pts[-1], pts[0]), v)))
    return {'point': _point(p)}


def _point3_midpoint(args, ctx):
    return {'point': _point(vec.lerp(_p(args['a']), _p(args['b']), 0.5))}


def _segment3_by_points(args, ctx):
    return {'segment': _segment(_p(args['a']), _p(args['b']))}


def _polygon3_by_points(args, ctx):
    pts = [_p(v) for v in args['vertices']]
    flat = _flat_ring(pts, ctx)
    n = len(pts)
    if isinstance(flat, Undefined):
        out = {'polygon': flat}
    else:
        out = {'polygon': {'vertices': [_list(p) for p in pts], 'normal': _list(flat[0]), 'area': flat[1]}}
    for k in range(n):
        out[f'side.{k + 1}'] = _segment(pts[k], pts[(k + 1) % n])
    return out


def _plane_by_points(args, ctx):
    a, b, c = _p(args['a']), _p(args['b']), _p(args['c'])
    n = vec.cross(vec.sub(b, a), vec.sub(c, a))
    longest = max(vec.dist(a, b), vec.dist(a, c), vec.dist(b, c))
    height = vec.norm(n) / longest if longest > 0 else 0.0
    ctx.decide('collinear', height, ctx.tol.decide_length)
    if height <= ctx.tol.decide_length:
        return {'plane': Undefined('collinear_points')}
    n = vec.unit(n)
    return {'plane': {'p': _list(vec.mul(n, vec.dot(n, a))), 'n': _list(n)}}


# ── solids ───────────────────────────────────────────────────────────────

def _polyhedron_cube(args, ctx):
    a, b = _p(args['a']), _p(args['b'])
    s = vec.dist(a, b)
    ctx.decide('coincident', s, ctx.tol.decide_length)
    faces, edges = _prism_topology(4)
    if s <= ctx.tol.decide_length:
        return _all_undefined(6, 12, 6, Undefined('coincident_points'))
    e1 = vec.mul(vec.sub(b, a), 1.0 / s)
    w = vec.cross((0.0, 0.0, 1.0), e1)
    if vec.norm(w) <= 1e-9:                       # AB vertical
        w = vec.cross(e1, (1.0, 0.0, 0.0))
    e2 = vec.unit(w)
    e3 = vec.cross(e1, e2)
    base = [a, vec.add(a, vec.mul(e1, s)), vec.add(a, vec.mul(vec.add(e1, e2), s)), vec.add(a, vec.mul(e2, s))]
    top = [vec.add(p, vec.mul(e3, s)) for p in base]
    return _solid(base + top, faces, edges, 6, ctx)


def _polyhedron_prism(args, ctx):
    base = [_p(v) for v in args['base']]
    n = len(base)
    faces, edges = _prism_topology(n)
    flat = _flat_ring(base, ctx, convex=True)
    if isinstance(flat, Undefined):
        return _all_undefined(n - 1, 3 * n, n + 2, flat)
    shift = vec.sub(_p(args['top']), base[0])
    height = vec.dot(flat[0], shift)
    ctx.decide('flat', height, ctx.tol.decide_length)
    if abs(height) <= ctx.tol.decide_length:
        return _all_undefined(n - 1, 3 * n, n + 2, Undefined('flat'))
    return _solid(base + [vec.add(p, shift) for p in base], faces, edges, n - 1, ctx)


def _pyramid(base, apex, ctx):
    n = len(base)
    faces, edges = _pyramid_topology(n)
    flat = _flat_ring(base, ctx, convex=True)
    if isinstance(flat, Undefined):
        return _all_undefined(0, 2 * n, n + 1, flat)
    height = vec.dot(flat[0], vec.sub(apex, base[0]))
    ctx.decide('flat', height, ctx.tol.decide_length)
    if abs(height) <= ctx.tol.decide_length:
        return _all_undefined(0, 2 * n, n + 1, Undefined('flat'))
    return _solid(base + [apex], faces, edges, 0, ctx)


def _polyhedron_pyramid(args, ctx):
    return _pyramid([_p(v) for v in args['base']], _p(args['apex']), ctx)


def _polyhedron_tetrahedron(args, ctx):
    return _pyramid([_p(args['a']), _p(args['b']), _p(args['c'])], _p(args['d']), ctx)


# ── sections ─────────────────────────────────────────────────────────────

def polyhedron_of(value) -> Polyhedron:
    """The :class:`~.solids.Polyhedron` of a ``polyhedron`` value (its face
    order is the canonical one of the value)."""
    vertices = [tuple(v) for v in value['vertices']]
    return Polyhedron(vertices, [tuple(f) for f in value['faces']], [str(i) for i in range(len(vertices))])


def plane_of(value) -> Plane:
    return Plane(tuple(value['p']), tuple(value['n']))


def _section_plane_polyhedron(args, ctx):
    cut = cut_solid(polyhedron_of(args['solid'].value), plane_of(args['plane'].value))
    if cut.state != 'defined':
        return {'section': Undefined(cut.reason)}
    return {'section': {'polygon': [_list(p) for p in cut.polygon], 'faces': [list(f) for f in cut.edge_faces]}}


IMPLEMENTATIONS = {
    'point3.free': _point3_free,
    'point3.on_path': _point3_on_path,
    'point3.on_surface': _point3_on_surface,
    'point3.midpoint': _point3_midpoint,
    'segment3.by_points': _segment3_by_points,
    'polygon3.by_points': _polygon3_by_points,
    'plane.by_points': _plane_by_points,
    'polyhedron.cube': _polyhedron_cube,
    'polyhedron.prism': _polyhedron_prism,
    'polyhedron.pyramid': _polyhedron_pyramid,
    'polyhedron.tetrahedron': _polyhedron_tetrahedron,
    'section.plane_polyhedron': _section_plane_polyhedron,
}
