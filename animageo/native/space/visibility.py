"""Visibility in space: faces, edges and vertices of a convex polyhedron,
segments behind solids, and the pieces of a segment.

**Faces** (:func:`face_facing`): ``front`` when the outward normal looks at
the eye (the cosine > ``FACING_TOL``), ``back`` when it looks away, ``side``
when the face is seen edge-on.

**Own edges and vertices** (:func:`edge_visibility`,
:func:`vertex_visibility`): of a convex solid an edge or a vertex is visible
exactly when one of its faces is ``front``.

**Other segments** (:class:`ConvexOccluder`): the points a convex solid hides
form its shadow volume — the solid swept away from the eye. It is the
intersection of half-spaces: strictly behind the plane of every ``front``
face, and inside the side plane of every silhouette edge (an edge between a
``front`` face and another one) and of every ``side`` face. The planes are
linear in a point, so the hidden part of a segment is one interval of its
parameter, found by clipping. Points on a front face stay visible, points
inside the solid are hidden. In perspective the side planes pass through
the eye.

**Pieces** (:func:`pieces`): the union of the hidden intervals of a segment
cut into alternating visible and hidden pieces; a gap or a bit shorter than
``min_t`` (the share of the segment that is ``min_piece_px`` long in px of
the reference frame of the flat scene, :func:`~.flat.flat_scene`) merges
into its neighbour, so tiny pieces do not flicker while the camera turns.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import vec

__all__ = ['FACING_TOL', 'DECIDE_TOL', 'SIDE_TOL', 'face_facing', 'edge_visibility', 'vertex_visibility',
           'ConvexOccluder', 'Piece', 'pieces']

FACING_TOL = 1e-10         # cosine: a face closer to edge-on is ``side``
DECIDE_TOL = 1e-10         # times the scale of the solid: a point this close to a plane is on it
SIDE_TOL = 1e-12           # a side normal shorter than this (times S, or S² in perspective) is none


def face_facing(poly, projector) -> tuple:
    """``front`` | ``back`` | ``side`` for every face of ``poly``."""
    out = []
    for n, centre in zip(poly.normals, poly.face_centres):
        s = projector.facing(n, centre)
        out.append('front' if s > FACING_TOL else 'back' if s < -FACING_TOL else 'side')
    return tuple(out)


def edge_visibility(poly, projector, facing=None) -> tuple:
    """``True`` (visible) or ``False`` for every edge of ``poly``, in the
    order of ``poly.edges``."""
    facing = facing or face_facing(poly, projector)
    return tuple(any(facing[f] == 'front' for f in e.faces) for e in poly.edges)


def vertex_visibility(poly, projector, facing=None) -> tuple:
    """``True`` or ``False`` for every vertex of ``poly``."""
    facing = facing or face_facing(poly, projector)
    return tuple(any(facing[f] == 'front' for f in poly.faces_at(i)) for i in range(len(poly.vertices)))


class ConvexOccluder:
    """The shadow volume of a convex polyhedron for one projector."""

    def __init__(self, poly, projector):
        self.poly = poly
        facing = face_facing(poly, projector)
        tol = DECIDE_TOL * poly.scale
        planes = []
        for k, state in enumerate(facing):
            a = poly.vertices[poly.faces[k][0]]
            if state == 'front':
                planes.append((poly.normals[k], a, -tol))
            elif state == 'side':
                planes.append((poly.normals[k], a, tol))
        # a side normal is a length (parallel: edge × unit view) or an area
        # (perspective: the two rays from the eye); below this the edge runs
        # along the view and its side plane is the plane of a side face
        degenerate = SIDE_TOL * poly.scale * (1.0 if projector.parallel else poly.scale)
        for e in poly.edges:
            states = [facing[f] for f in e.faces]
            if 'front' not in states or all(s == 'front' for s in states):
                continue
            q1, q2 = poly.vertices[e.a], poly.vertices[e.b]
            m = projector.side_normal(q1, q2)
            if vec.norm(m) <= degenerate:
                continue
            m = vec.unit(m)
            if vec.dot(m, vec.sub(poly.centre, q1)) > 0:
                m = vec.mul(m, -1.0)
            planes.append((m, q1, tol))
        # without a front face the eye is inside the solid: it hides nothing here
        self._planes = tuple(planes) if 'front' in facing else None

    @property
    def planes(self):
        """The half-spaces of the shadow volume, ``(normal, point, offset)``:
        a point ``p`` is inside when ``normal·(p − point) − offset ≤ 0``;
        ``None`` when the solid hides nothing."""
        return self._planes

    def hidden_interval(self, a, b):
        """``(t0, t1)`` — the part of the segment ``a + t·(b − a)``, ``t`` in
        ``[0, 1]``, the solid hides, or ``None``."""
        if self._planes is None:
            return None
        t0, t1 = 0.0, 1.0
        for m, q, c in self._planes:
            h0 = vec.dot(m, vec.sub(a, q)) - c
            h1 = vec.dot(m, vec.sub(b, q)) - c
            if h0 > 0 and h1 > 0:
                return None
            if h0 > 0:
                t0 = max(t0, h0 / (h0 - h1))
            elif h1 > 0:
                t1 = min(t1, h0 / (h0 - h1))
            if t0 >= t1:
                return None
        return (t0, t1)

    def hides(self, p) -> bool:
        return self.hidden_interval(p, p) is not None


@dataclass(frozen=True)
class Piece:
    """``[t0, t1]`` of a segment, ``hidden`` or not; ``occluders`` — how many
    hidden intervals overlap at most inside a hidden piece (a solid behind a
    solid counts twice), 0 for a visible one."""

    t0: float
    t1: float
    hidden: bool
    occluders: int = 0


def _max_cover(spans):
    events = sorted([(t0, 1, w) for t0, _, w in spans] + [(t1, 0, w) for _, t1, w in spans])
    best = depth = 0
    for _, start, w in events:
        depth += w if start else -w
        best = max(best, depth)
    return best


def pieces(intervals, min_t) -> list:
    """Visible and hidden :class:`Piece` s from hidden intervals ``(t0, t1)``
    or ``(t0, t1, weight)``; ``None`` entries are skipped."""
    spans = []
    for item in intervals:
        if item is None:
            continue
        t0, t1 = max(0.0, float(item[0])), min(1.0, float(item[1]))
        if t1 > t0:
            spans.append((t0, t1, int(item[2]) if len(item) > 2 else 1))
    if not spans:
        return [Piece(0.0, 1.0, False, 0)]
    spans.sort()
    runs = [[spans[0][0], spans[0][1], [spans[0]]]]
    for span in spans[1:]:
        last = runs[-1]
        if span[0] <= last[1] + min_t:
            last[1] = max(last[1], span[1])
            last[2].append(span)
        else:
            runs.append([span[0], span[1], [span]])
    out = []
    t = 0.0
    for h0, h1, members in runs:
        if h1 - h0 < min_t:
            continue
        s = t if h0 - t < min_t else h0
        if s > t:
            out.append(Piece(t, s, False, 0))
        out.append(Piece(s, h1, True, _max_cover(members)))
        t = h1
    if 1.0 - t >= min_t:
        out.append(Piece(t, 1.0, False, 0))
    elif out:
        last = out[-1]
        out[-1] = Piece(last.t0, 1.0, last.hidden, last.occluders)
    return out or [Piece(0.0, 1.0, False, 0)]
