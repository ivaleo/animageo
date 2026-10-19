"""Plane sections of a convex polyhedron and the sheet of a plane.

:func:`section` — the polygon a plane cuts from a convex solid: the vertices
of the solid on the plane and the crossings of its edges, ordered
counterclockwise around the normal of the plane. A plane that misses the
solid gives ``undefined`` with the reason ``outside``; a plane through a
vertex or an edge only — ``touch``; the plane of a face gives that face.
Every edge of the polygon lies on one face of the solid (two when it runs
along an edge of the solid): ``edge_faces``. Decisions use
``1e-10·S``, membership of a face ``1e-9·S`` (``S`` — the scale of the solid).

:func:`section_visibility` — an edge of a section is seen exactly when one
of its faces is ``front`` (the section lies on the surface).

:func:`plane_sheet` — the four corners of the drawn part of a plane (the
sheet of a school drawing): the rectangle around given points of the plane
with its first side horizontal, widened by ``margin`` of its size.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import vec
from .solids import SHAPE_TOL
from .visibility import DECIDE_TOL, ConvexOccluder, face_facing

__all__ = ['Section', 'section', 'section_visibility', 'plane_basis', 'plane_sheet']


@dataclass(frozen=True)
class Section:
    plane: object
    polygon: tuple = ()
    edge_faces: tuple = ()
    state: str = 'defined'
    reason: str | None = None

    def edges(self):
        """The pairs ``(p, q)`` of consecutive vertices of the polygon."""
        n = len(self.polygon)
        return [(self.polygon[i], self.polygon[(i + 1) % n]) for i in range(n)]


def plane_basis(normal):
    """``(e1, e2)``: a right-handed frame of the plane, ``e1`` horizontal
    unless the plane is horizontal (then ``e1`` is +x)."""
    e1 = vec.cross((0.0, 0.0, 1.0), normal)
    if vec.norm(e1) <= 1e-9:
        e1 = (1.0, 0.0, 0.0)
    e1 = vec.unit(e1)
    return e1, vec.cross(normal, e1)


def section(poly, plane) -> Section:
    """The section of the convex ``poly`` by ``plane``."""
    tol = DECIDE_TOL * poly.scale
    d = [plane.distance(v) for v in poly.vertices]
    if all(x > tol for x in d) or all(x < -tol for x in d):
        return Section(plane, state='undefined', reason='outside')
    points = [v for v, x in zip(poly.vertices, d) if abs(x) <= tol]
    for e in poly.edges:
        da, db = d[e.a], d[e.b]
        if (da > tol and db < -tol) or (da < -tol and db > tol):
            points.append(vec.lerp(poly.vertices[e.a], poly.vertices[e.b], da / (da - db)))
    same = SHAPE_TOL * poly.scale
    unique = []
    for p in points:
        if all(vec.dist(p, q) > same for q in unique):
            unique.append(p)
    if len(unique) < 3:
        return Section(plane, state='undefined', reason='touch')
    centre = vec.centroid(unique)
    e1, e2 = plane_basis(plane.normal)

    def key(p):
        w = vec.sub(p, centre)
        return (math.atan2(vec.dot(w, e2), vec.dot(w, e1)), vec.norm(w))

    ring = sorted(unique, key=key)
    changed = True
    while changed and len(ring) >= 3:          # drop a vertex in the middle of a side
        changed = False
        for i, p in enumerate(ring):
            a, b = ring[i - 1], ring[(i + 1) % len(ring)]
            if vec.norm(vec.cross(vec.sub(p, a), vec.sub(b, a))) <= same * vec.dist(a, b):
                ring.pop(i)
                changed = True
                break
    if len(ring) < 3:
        return Section(plane, state='undefined', reason='touch')
    on_face = 1e-9 * poly.scale
    faces = []
    for i, p in enumerate(ring):
        q = ring[(i + 1) % len(ring)]
        owners = []
        for k, n in enumerate(poly.normals):
            a = poly.vertices[poly.faces[k][0]]
            if abs(vec.dot(n, vec.sub(p, a))) <= on_face and abs(vec.dot(n, vec.sub(q, a))) <= on_face:
                owners.append(k)
        faces.append(tuple(owners))
    return Section(plane, tuple(ring), tuple(faces))


def section_visibility(poly, cut, projector, facing=None) -> tuple:
    """``True`` (visible) or ``False`` for every edge of the section ``cut``."""
    facing = facing or face_facing(poly, projector)
    occluder = None
    out = []
    for (p, q), owners in zip(cut.edges(), cut.edge_faces):
        if owners:
            out.append(any(facing[f] == 'front' for f in owners))
            continue
        occluder = occluder or ConvexOccluder(poly, projector)
        out.append(not occluder.hides(vec.lerp(p, q, 0.5)))
    return tuple(out)


def plane_sheet(plane, around, margin=0.25, min_size=0.0) -> tuple:
    """The corners of the sheet of ``plane`` around the points ``around``
    (projected to the plane), counterclockwise about its normal."""
    e1, e2 = plane_basis(plane.normal)
    us = [vec.dot(vec.sub(p, plane.point), e1) for p in around]
    vs = [vec.dot(vec.sub(p, plane.point), e2) for p in around]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    du = max(u1 - u0, min_size)
    dv = max(v1 - v0, min_size)
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    hu, hv = du * (0.5 + margin), dv * (0.5 + margin)

    def at(u, v):
        return vec.add(plane.point, vec.add(vec.mul(e1, u), vec.mul(e2, v)))

    return (at(cu - hu, cv - hv), at(cu + hu, cv - hv), at(cu + hu, cv + hv), at(cu - hu, cv + hv))
