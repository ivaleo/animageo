"""Positive-volume intersections between drawn convex polyhedra."""
from __future__ import annotations

from itertools import combinations

from . import vec
from .visibility import DECIDE_TOL

# Unit edge directions equal to this many decimals are one family of
# parallel edges. Merging them moves an axis by far less than DECIDE_TOL.
DIRECTION_DIGITS = 12
# The vertex projections one pair may spend on separating axes; beyond it
# the pair is reported as overlapping, marked ``approximate``.
AXIS_BUDGET = 2_000_000


def _bounds(poly):
    xs, ys, zs = zip(*poly.vertices)
    return tuple((min(coords), max(coords)) for coords in (xs, ys, zs))


def _edge_directions(poly):
    """One unit direction per family of parallel edges, in edge order."""
    directions = {}
    for edge in poly.edges:
        delta = vec.sub(poly.vertices[edge.b], poly.vertices[edge.a])
        length = vec.norm(delta)
        if not length:
            continue
        unit = vec.mul(delta, 1.0 / length)
        if max(unit, key=abs) < 0:
            unit = vec.mul(unit, -1.0)
        # ``+ 0.0`` folds -0.0 into 0.0, so the key of a direction is unique.
        directions.setdefault(tuple(round(c, DIRECTION_DIGITS) + 0.0 for c in unit), unit)
    return list(directions.values())


def _planes(poly, origin):
    return [(normal, vec.dot(normal, vec.sub(poly.vertices[ring[0]], origin)))
            for ring, normal in zip(poly.faces, poly.normals)]


def _depth(planes, x):
    return min(offset - vec.dot(normal, x) for normal, offset in planes)


def _common_interior(a, b, origin, tol):
    """Whether a probe point lies deeper than ``tol`` inside both bodies.

    Such a point proves the overlap: a ball of radius ``tol`` around it lies in
    both, so every axis sees an overlap of at least ``2·tol``."""
    pa, pb = _planes(a, origin), _planes(b, origin)
    boxes = list(zip(_bounds(a), _bounds(b)))
    box = tuple((max(alo, blo) + min(ahi, bhi)) / 2 for (alo, ahi), (blo, bhi) in boxes)
    for probe in (box, vec.lerp(a.centre, b.centre, 0.5), a.centre, b.centre):
        x = vec.sub(probe, origin)
        if _depth(pa, x) > tol and _depth(pb, x) > tol:
            return True
    return False


def _relation(a, b):
    """``True`` (the interiors intersect), ``False`` (apart or touching) or
    ``None`` (no separating axis within :data:`AXIS_BUDGET`)."""
    # Use a shared local origin so that the projections and tolerance depend on
    # the sizes and separation of the bodies even far from the world origin.
    origin = a.vertices[0]
    tol = DECIDE_TOL * min(a.scale, b.scale)
    if _common_interior(a, b, origin, tol):
        return True
    av = [vec.sub(p, origin) for p in a.vertices]
    bv = [vec.sub(p, origin) for p in b.vertices]

    def separated(axis, axis_tol):
        ap = [vec.dot(p, axis) for p in av]
        bp = [vec.dot(p, axis) for p in bv]
        return min(max(ap) - min(bp), max(bp) - min(ap)) <= axis_tol

    def axes():
        yield from ((normal, tol) for normal in (*a.normals, *b.normals))
        db = _edge_directions(b)
        for u in _edge_directions(a):
            for v in db:
                axis = vec.cross(u, v)
                length = vec.norm(axis)
                if length:
                    yield axis, tol * length

    budget = AXIS_BUDGET // (len(av) + len(bv))
    for axis, axis_tol in axes():
        if budget <= 0:
            return None
        budget -= 1
        if separated(axis, axis_tol):
            return False
    return True


def overlapping_solids(solids):
    """Yield sorted ``(id, otherId, exact)`` of solids whose convex interiors
    intersect.

    AABB contact is rejected first, and a point found deeper than the
    tolerance inside both bodies proves an intersection. The remaining
    separating axes are the face normals and cross products of the
    directions of edges from both bodies, parallel edges counted once. An
    interval contact to the visibility tolerance counts as tangency. A pair
    that needs more than :data:`AXIS_BUDGET` vertex projections is yielded
    with ``exact`` false: its fills are not ordered.
    """
    bounded = [(sid, poly, _bounds(poly)) for sid, poly in sorted(solids)]
    for (aid, a, ab), (bid, b, bb) in combinations(bounded, 2):
        if any(min(ahi, bhi) <= max(alo, blo) for (alo, ahi), (blo, bhi) in zip(ab, bb)):
            continue
        relation = _relation(a, b)
        if relation is not False:
            yield aid, bid, relation is True
