"""Planes and convex polyhedra of space.

A :class:`Polyhedron` is convex and closed: every face is a planar convex
polygon, every edge belongs to exactly two faces, every vertex lies on the
inner side of every face plane. Faces are stored counterclockwise seen from
outside; the builders orient them by the centre of the vertices, so a
caller may list a face either way. Tolerances follow the scale of the solid
``S`` (the diagonal of its bounding box): ``1e-9·S`` for "planar" and
"convex".

Names of vertices follow school drawings: the base ``A, B, C, …``, the top
of a prism or a cube ``A_1, B_1, …`` (TeX subscripts), the apex of a
pyramid ``S``.
"""
from __future__ import annotations

import string
from dataclasses import dataclass

from . import vec

__all__ = ['Plane', 'Edge', 'Polyhedron', 'polyhedron', 'cube', 'prism', 'pyramid', 'tetrahedron',
           'scale_of']

SHAPE_TOL = 1e-9


def scale_of(points) -> float:
    """The diagonal of the bounding box of ``points`` (1 for a single point)."""
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    d = vec.norm(vec.sub(hi, lo))
    return d if d > 0.0 else 1.0


def _newell(ring):
    n = (0.0, 0.0, 0.0)
    for i, p in enumerate(ring):
        q = ring[(i + 1) % len(ring)]
        n = vec.add(n, ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]),
                        (p[0] - q[0]) * (p[1] + q[1])))
    return n


@dataclass(frozen=True)
class Plane:
    """The plane through ``point`` with the unit ``normal`` (normalised here)."""

    point: tuple
    normal: tuple

    def __post_init__(self):
        object.__setattr__(self, 'point', tuple(float(c) for c in self.point))
        object.__setattr__(self, 'normal', vec.unit(tuple(float(c) for c in self.normal)))

    @classmethod
    def through(cls, a, b, c) -> 'Plane':
        """The plane through three points; ``ValueError("collinear")``."""
        n = vec.cross(vec.sub(b, a), vec.sub(c, a))
        s = scale_of([a, b, c])
        if vec.norm(n) <= 1e-10 * s * s:
            raise ValueError('collinear: three points of a plane lie on one line')
        return cls(a, n)

    def distance(self, p) -> float:
        """The signed distance from ``p`` (positive on the side of the normal)."""
        return vec.dot(self.normal, vec.sub(p, self.point))


@dataclass(frozen=True)
class Edge:
    """An edge between vertices ``a < b`` and the indices of its two faces."""

    a: int
    b: int
    faces: tuple


class Polyhedron:
    """A convex polyhedron; see the module docstring."""

    def __init__(self, vertices, faces, labels):
        self.vertices = tuple(tuple(float(c) for c in v) for v in vertices)
        self.labels = tuple(labels)
        if len(self.labels) != len(self.vertices) or len(set(self.labels)) != len(self.labels):
            raise ValueError('labels: one distinct label per vertex expected')
        if len(self.vertices) < 4:
            raise ValueError('flat: a solid needs at least four vertices')
        self.scale = scale_of(self.vertices)
        self.centre = vec.centroid(self.vertices)
        tol = SHAPE_TOL * self.scale
        rings = [tuple(int(i) for i in f) for f in faces]
        normals = []
        for k, ring in enumerate(rings):
            if len(ring) < 3 or len(set(ring)) != len(ring):
                raise ValueError(f'degenerate_face: face {k}')
            n = _newell([self.vertices[i] for i in ring])
            if vec.norm(n) <= tol * self.scale:
                raise ValueError(f'degenerate_face: face {k} has no area')
            n = vec.unit(n)
            middle = vec.centroid([self.vertices[i] for i in ring])
            if vec.dot(n, vec.sub(middle, self.centre)) < 0:
                ring, n = tuple(reversed(ring)), vec.mul(n, -1.0)
            rings[k] = ring
            normals.append(n)
        self.faces = tuple(rings)
        self.normals = tuple(normals)
        self.face_centres = tuple(vec.centroid([self.vertices[i] for i in ring]) for ring in rings)
        if max(abs(vec.dot(self.normals[0], vec.sub(v, self.face_centres[0]))) for v in self.vertices) <= tol:
            raise ValueError('flat: all vertices lie in one plane')
        for k, ring in enumerate(self.faces):
            a = self.vertices[ring[0]]
            for i in ring:
                if abs(vec.dot(self.normals[k], vec.sub(self.vertices[i], a))) > tol:
                    raise ValueError(f'face_not_planar: face {k}')
            for v in self.vertices:
                if vec.dot(self.normals[k], vec.sub(v, a)) > tol:
                    raise ValueError(f'not_convex: a vertex lies outside the plane of face {k}')
        owners = {}
        for k, ring in enumerate(self.faces):
            for i, p in enumerate(ring):
                q = ring[(i + 1) % len(ring)]
                owners.setdefault((min(p, q), max(p, q)), []).append(k)
        for key, fs in owners.items():
            if len(fs) != 2:
                raise ValueError(f'not_closed: edge {key} belongs to {len(fs)} faces')
        self.edges = tuple(Edge(a, b, tuple(sorted(owners[(a, b)]))) for a, b in sorted(owners))

    def vertex(self, label) -> tuple:
        return self.vertices[self.labels.index(label)]

    def faces_at(self, index) -> tuple:
        """The faces meeting at vertex ``index``."""
        return tuple(k for k, ring in enumerate(self.faces) if index in ring)

    def __repr__(self):
        return f'Polyhedron({len(self.vertices)} vertices, {len(self.faces)} faces)'


def _letters(n):
    letters = [c for c in string.ascii_uppercase if c not in 'S']
    if n > len(letters):
        raise ValueError('labels: too many vertices for default labels')
    return letters[:n]


def polyhedron(vertices, faces, labels=None) -> Polyhedron:
    """A convex polyhedron from vertices and faces (index cycles)."""
    return Polyhedron(vertices, faces, labels or _letters(len(vertices)))


def cube(size=1.0, origin=(0.0, 0.0, 0.0), labels=None) -> Polyhedron:
    """The cube ``ABCDA_1B_1C_1D_1`` with the base ``ABCD`` on the plane
    ``z = origin.z``, counterclockwise from above, ``A`` at ``origin``."""
    s = float(size)
    if not s > 0:
        raise ValueError('flat: the size of a cube must be positive')
    base = [(0, 0), (s, 0), (s, s), (0, s)]
    o = origin
    verts = [(o[0] + x, o[1] + y, o[2]) for x, y in base] + [(o[0] + x, o[1] + y, o[2] + s) for x, y in base]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return Polyhedron(verts, faces, labels or ('A', 'B', 'C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'))


def _base_normal(base):
    n = _newell(base)
    if vec.norm(n) <= 1e-12 * scale_of(base) ** 2:
        raise ValueError('flat: the base has no area')
    return vec.unit(n)


def prism(base, shift, labels=None) -> Polyhedron:
    """The prism on a convex planar ``base`` and its translate by ``shift``
    (an oblique prism when ``shift`` is not square to the base)."""
    base = [tuple(float(c) for c in p) for p in base]
    n = len(base)
    if n < 3:
        raise ValueError('flat: a base needs three vertices')
    if abs(vec.dot(_base_normal(base), shift)) <= SHAPE_TOL * scale_of(base + [vec.add(base[0], shift)]):
        raise ValueError('flat: the shift of a prism lies in the plane of its base')
    top = [vec.add(p, shift) for p in base]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    if labels is None:
        letters = _letters(n)
        labels = tuple(letters) + tuple(f'{c}_1' for c in letters)
    return Polyhedron(base + top, faces, labels)


def pyramid(base, apex, labels=None) -> Polyhedron:
    """The pyramid on a convex planar ``base`` with the ``apex`` (``S``)."""
    base = [tuple(float(c) for c in p) for p in base]
    n = len(base)
    if n < 3:
        raise ValueError('flat: a base needs three vertices')
    if abs(vec.dot(_base_normal(base), vec.sub(apex, base[0]))) <= SHAPE_TOL * scale_of(base + [apex]):
        raise ValueError('flat: the apex lies in the plane of the base')
    faces = [tuple(range(n))] + [(i, (i + 1) % n, n) for i in range(n)]
    return Polyhedron(base + [tuple(apex)], faces, labels or tuple(_letters(n)) + ('S',))


def tetrahedron(a, b, c, d, labels=('A', 'B', 'C', 'D')) -> Polyhedron:
    """The tetrahedron ``ABCD``."""
    return pyramid([a, b, c], d, labels=labels)
