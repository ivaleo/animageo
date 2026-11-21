"""Positive-volume intersections between drawn convex polyhedra."""
from __future__ import annotations

from itertools import combinations

from . import vec
from .visibility import DECIDE_TOL


def _bounds(poly):
    xs, ys, zs = zip(*poly.vertices)
    return tuple((min(coords), max(coords)) for coords in (xs, ys, zs))


def _edge_directions(poly):
    directions = set()
    for edge in poly.edges:
        delta = vec.sub(poly.vertices[edge.b], poly.vertices[edge.a])
        # Canonicalize opposite and repeated parallel directions without rounding.
        divisor = max(delta, key=abs)
        if divisor:
            directions.add(tuple(component / divisor for component in delta))
    return directions


def _interiors_overlap(a, b):
    # Use a shared local origin so that the projections and tolerance depend on
    # the sizes and separation of the bodies even far from the world origin.
    origin = a.vertices[0]
    av = [vec.sub(p, origin) for p in a.vertices]
    bv = [vec.sub(p, origin) for p in b.vertices]
    tol = DECIDE_TOL * min(a.scale, b.scale)

    def separated(axis, axis_tol):
        ap = [vec.dot(p, axis) for p in av]
        bp = [vec.dot(p, axis) for p in bv]
        return min(max(ap) - min(bp), max(bp) - min(ap)) <= axis_tol

    if any(separated(normal, tol) for normal in (*a.normals, *b.normals)):
        return False
    db = _edge_directions(b)
    for u in _edge_directions(a):
        for v in db:
            axis = vec.cross(u, v)
            length = vec.norm(axis)
            if length and separated(axis, tol * length):
                return False
    return True


def overlapping_solids(solids):
    """Yield sorted pairs of solid IDs whose convex interiors intersect.

    AABB contact is rejected first. The remaining separating axes are the
    face normals and cross products of directions of edges from both bodies.
    An interval contact to the visibility tolerance counts as tangency.
    """
    bounded = [(sid, poly, _bounds(poly)) for sid, poly in sorted(solids)]
    for (aid, a, ab), (bid, b, bb) in combinations(bounded, 2):
        if any(min(ahi, bhi) <= max(alo, blo) for (alo, ahi), (blo, bhi) in zip(ab, bb)):
            continue
        if _interiors_overlap(a, b):
            yield aid, bid
