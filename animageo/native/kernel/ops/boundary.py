"""The region bounded by a chain of pieces and by contours (registry 1.9;
docs/native/ops/region.by_boundary.md, docs/native/kernel.md §16).

``region.by_boundary`` keeps its face by IDs: piece ``i`` runs on
``curves[i]`` from the vertex ``from[i]`` to ``to[i]`` (a line, segment or
ray gives a straight piece, a circle or an arc the arc counterclockwise
from ``from`` to ``to``; ``from == to`` the whole circle). The chain
(:func:`~animageo.native.kernel.region.boundary_chain`) walks the pieces
into rings; a backward piece reverses (an arc is then walked clockwise).
A contour of ``inside`` keeps the region inside itself (walked
counterclockwise), one of ``outside`` outside (clockwise).
"""
from __future__ import annotations

import math
from typing import NamedTuple

from ..region import PIECES_MAX, TWO_PI, arc_area_of, boundary_chain, line_area
from ..values import Undefined
from . import op

__all__ = ['Piece', 'carrier_distance', 'chain_pieces', 'contour_ring', 'reversed_ring', 'ring_area']

_LINEAR = ('line', 'segment', 'ray')
_ROUND = ('circle', 'arc')


class Piece(NamedTuple):
    """One piece of a ring as walked: ``kind`` ``line``, ``ccw`` or ``cw``;
    ``start``/``end`` points; ``circle`` ``(cx, cy, r)`` of an arc (else
    ``None``); ``t0`` the angle of the start about the centre and
    ``sweep`` the signed turn of an arc (``0`` for a line); ``whole`` — the
    whole circle; ``source`` the slot path of its carrier; ``index`` the
    item of ``curves`` (``None`` for a contour)."""

    kind: str
    start: tuple
    end: tuple
    circle: tuple | None
    t0: float
    sweep: float
    whole: bool
    source: str
    index: int | None

    def value(self) -> list:
        """The piece in the region value."""
        head = [[self.start[0], self.start[1]], [self.end[0], self.end[1]]]
        return head if self.circle is None else head + [list(self.circle)]

    def reversed(self) -> 'Piece':
        if self.circle is None:
            return self._replace(start=self.end, end=self.start)
        cx, cy, _r = self.circle
        t0 = self.t0 if self.whole else math.atan2(self.end[1] - cy, self.end[0] - cx)
        return self._replace(kind='cw' if self.kind == 'ccw' else 'ccw', start=self.end, end=self.start,
                             t0=t0, sweep=-self.sweep)


def _xy(inp) -> tuple:
    return float(inp.value['x']), float(inp.value['y'])


def _circle_of(inp) -> tuple:
    v = inp.value
    return float(v['c'][0]), float(v['c'][1]), float(v['r'])


def _arc_piece(circle, start, end, whole, source, index) -> Piece:
    """The counterclockwise arc on ``circle`` from ``start`` to ``end``:
    ``sweep = (θ_end − θ_start) mod 2π`` (``0`` when the angles are equal),
    ``2π`` for the whole circle (``end`` is then ``start`` itself)."""
    cx, cy, _r = circle
    t0 = math.atan2(start[1] - cy, start[0] - cx)
    if whole:
        return Piece('ccw', start, start, circle, t0, TWO_PI, True, source, index)
    t1 = math.atan2(end[1] - cy, end[0] - cx)
    return Piece('ccw', start, end, circle, t0, (t1 - t0) % TWO_PI, False, source, index)


def chain_pieces(curves, starts, ends) -> list:
    """The pieces of ``curves`` forward (from ``from[i]`` to ``to[i]``), or
    ``Undefined('unsupported_signature', {'slot': 'curves.<i>'})`` for a
    carrier other than a line, segment, ray, circle or arc (graphs and
    conics come later)."""
    out = []
    for i, carrier in enumerate(curves):
        source = f'curves.{i}'
        a, b = _xy(starts[i]), _xy(ends[i])
        if carrier.type in _LINEAR:
            out.append(Piece('line', a, b, None, 0.0, 0.0, False, source, i))
        elif carrier.type in _ROUND:
            whole = starts[i].id is not None and starts[i].id == ends[i].id
            out.append(_arc_piece(_circle_of(carrier), a, b, whole, source, i))
        else:
            return Undefined('unsupported_signature', {'slot': source})
    return out


def _point_at(circle, t) -> tuple:
    cx, cy, r = circle
    return cx + r * math.cos(t), cy + r * math.sin(t)


def contour_ring(inp, source: str) -> list:
    """The pieces of a contour walked counterclockwise.

    - circle: the whole circle from ``(cx + r, cy)``;
    - polygon: its sides, in the order of the vertices when their shoelace
      sum is not negative, else ``v0, v_{n−1}, …, v1``;
    - sector: centre → start of the arc, the arc, its end → centre;
    - circlesegment: the arc, then the chord from its end to its start;
    - a sector or a circle segment of a full turn (``a1 − a0 ≥ 2π``) is the
      whole circle from the start of its arc.
    """
    v = inp.value
    if inp.type == 'polygon':
        vs = [(float(x), float(y)) for x, y in v['vertices']]
        n = len(vs)
        twice = 0.0
        for i in range(n):
            twice = twice + (vs[i][0] * vs[(i + 1) % n][1] - vs[(i + 1) % n][0] * vs[i][1])
        if twice < 0:
            vs = [vs[0]] + vs[:0:-1]
        return [Piece('line', vs[i], vs[(i + 1) % n], None, 0.0, 0.0, False, source, None) for i in range(n)]
    circle = _circle_of(inp)
    if inp.type == 'circle':
        start = (circle[0] + circle[2], circle[1])
        return [_arc_piece(circle, start, start, True, source, None)]
    a0, a1 = float(v['a0']), float(v['a1'])
    start = _point_at(circle, a0)
    if a1 - a0 >= TWO_PI:
        return [_arc_piece(circle, start, start, True, source, None)]
    end = _point_at(circle, a1)
    arc = Piece('ccw', start, end, circle, a0, a1 - a0, False, source, None)
    if inp.type == 'sector':
        centre = (circle[0], circle[1])
        return [Piece('line', centre, start, None, 0.0, 0.0, False, source, None), arc,
                Piece('line', end, centre, None, 0.0, 0.0, False, source, None)]
    return [arc, Piece('line', end, start, None, 0.0, 0.0, False, source, None)]


def reversed_ring(ring) -> list:
    """The ring walked the other way, from the same start."""
    return [p.reversed() for p in reversed(ring)]


def ring_area(ring) -> float:
    """The signed area ``Σ −∫ y dx`` of a ring (positive counterclockwise)."""
    acc = 0.0
    for p in ring:
        if p.circle is None:
            acc = acc + line_area(p.start, p.end)
        else:
            acc = acc + arc_area_of(p.circle[1], p.circle[2], p.t0, p.sweep)
    return acc


def _rings(args):
    """``(pieces, rings, None)`` — the forward pieces of the chain and the
    rings in the order of the value (chain rings in document order, then
    ``inside``, then ``outside``) — or ``(None, None, Undefined)``."""
    curves, starts, ends = args['curves'], args['from'], args['to']
    pieces = chain_pieces(curves, starts, ends)
    if isinstance(pieces, Undefined):
        return None, None, pieces
    walks, _problem = boundary_chain([c.id for c in curves], [s.id for s in starts], [e.id for e in ends],
                                     [c.type in _ROUND for c in curves], len(args['inside']) + len(args['outside']))
    rings = [[pieces[i] if forward else pieces[i].reversed() for i, forward in walk] for walk in walks or ()]
    for k, contour in enumerate(args['inside']):
        rings.append(contour_ring(contour, f'inside.{k}'))
    for k, contour in enumerate(args['outside']):
        rings.append(reversed_ring(contour_ring(contour, f'outside.{k}')))
    if sum(len(ring) for ring in rings) > PIECES_MAX:
        return None, None, Undefined('limit_exceeded')
    return pieces, rings, None


def carrier_distance(carrier, x: float, y: float) -> float:
    """The distance from ``(x, y)`` to the line or the circle of a carrier (a
    segment of zero length: to its point)."""
    v = carrier.value
    if carrier.type in _ROUND:
        return abs(math.hypot(x - v['c'][0], y - v['c'][1]) - v['r'])
    if carrier.type == 'segment':
        (ax, ay), (bx, by) = v['a'], v['b']
        length = math.hypot(bx - ax, by - ay)
        if length == 0.0:
            return math.hypot(x - ax, y - ay)
        return abs((x - ax) * (by - ay) - (y - ay) * (bx - ax)) / length
    (px, py), (dx, dy) = (v['p'], v['dir']) if carrier.type == 'line' else (v['origin'], v['dir'])
    return abs((x - px) * dy - (y - py) * dx)


def _incidence(args, ctx):
    """Step 1: every vertex within ``tol.inc = tol.check.failed`` of the
    carrier of its piece (decision ``off_carrier``), else
    ``not_on_curve`` with ``detail.slot`` ``from.<i>`` / ``to.<i>``; the
    pieces in document order, ``from`` before ``to``."""
    tol = ctx.tol.check_failed
    for i, carrier in enumerate(args['curves']):
        for slot in ('from', 'to'):
            x, y = _xy(args[slot][i])
            d = carrier_distance(carrier, x, y)
            ctx.decide('off_carrier', d, tol)
            if d > tol:
                return Undefined('not_on_curve', {'slot': f'{slot}.{i}'})
    return None


def _within(carrier, piece, ctx) -> bool:
    """Whether a piece lies on the part of its carrier (decisions
    ``piece_part``, ``tol.decide``): a segment holds the parameters of both
    ends in ``[−tol, length + tol]``, a ray in ``[−tol, ∞)``; an arc
    ``{a0, a1}`` the piece ccw from ``from``: ``φ = (θ_from − a0) mod 2π``
    (``0`` when ``r·(2π − φ) ≤ tol``) and ``r·(φ + sweep − (a1 − a0)) ≤ tol``."""
    tol = ctx.tol.decide_length
    v = carrier.value
    if carrier.type == 'line' or carrier.type == 'circle':
        return True
    if carrier.type == 'arc':
        cx, cy = v['c']
        r = v['r']
        phi = (math.atan2(piece.start[1] - cy, piece.start[0] - cx) - v['a0']) % TWO_PI
        wrap = r * (TWO_PI - phi)
        ctx.decide('piece_part', wrap, tol)
        if wrap <= tol:
            phi = 0.0
        e = r * (phi + piece.sweep - (v['a1'] - v['a0']))
        ctx.decide('piece_part', e, tol)
        return e <= tol
    if carrier.type == 'ray':
        (ox, oy), (dx, dy) = v['origin'], v['dir']
        for x, y in (piece.start, piece.end):
            s = (x - ox) * dx + (y - oy) * dy
            ctx.decide('piece_part', s, tol)
            if s < -tol:
                return False
        return True
    (ax, ay), (bx, by) = v['a'], v['b']
    length = math.hypot(bx - ax, by - ay)
    if length == 0.0:
        return True
    ux, uy = (bx - ax) / length, (by - ay) / length
    for x, y in (piece.start, piece.end):
        s = (x - ax) * ux + (y - ay) * uy
        ctx.decide('piece_part', s, tol)
        ctx.decide('piece_part', s - length, tol)
        if s < -tol or s > length + tol:
            return False
    return True


def _parts(args, pieces, ctx):
    """Step 2: every piece on the part of its carrier, else ``outside_part``
    with ``detail.slot`` ``curves.<i>``."""
    for i, carrier in enumerate(args['curves']):
        if not _within(carrier, pieces[i], ctx):
            return Undefined('outside_part', {'slot': f'curves.{i}'})
    return None


# ── step 3: empty rings ──────────────────────────────────────────────────

def _empty(areas, ctx):
    """Step 3: a ring of ``|A| ≤ tol.decide·S`` (decision ``empty_region``)."""
    tol = ctx.tol.decide_length * ctx.tol.scale
    for area in areas:
        ctx.decide('empty_region', area, tol)
        if abs(area) <= tol:
            return Undefined('empty_region')
    return None


# ── step 4: a simple boundary ────────────────────────────────────────────

_OVERLAP = 'overlap'


def _interval(p) -> tuple:
    """``(s, w)``: an arc piece covers the counterclockwise interval ``[s, s + w]``."""
    return (p.t0, p.sweep) if p.sweep >= 0 else (p.t0 + p.sweep, -p.sweep)


def _on_arc(p, x, y, ctx) -> bool:
    """Whether ``(x, y)`` (on the circle of ``p``) lies on the arc piece:
    ``φ = (θ − s) mod 2π``, on it when ``r·(φ − w) ≤ tol`` or
    ``r·(2π − φ) ≤ tol`` (decisions ``crossing``)."""
    cx, cy, r = p.circle
    s, w = _interval(p)
    phi = (math.atan2(y - cy, x - cx) - s) % TWO_PI
    tol = ctx.tol.decide_length
    e1 = r * (phi - w)
    e2 = r * (TWO_PI - phi)
    ctx.decide('crossing', e1, tol)
    ctx.decide('crossing', e2, tol)
    return e1 <= tol or e2 <= tol


def _on_line(p, x, y, ctx) -> bool:
    """Whether ``(x, y)`` (on the line of ``p``) lies on the straight piece:
    its parameter in ``[−tol, length + tol]`` (decisions ``crossing``); a
    piece of zero length: within ``tol`` of its point."""
    (ax, ay), (bx, by) = p.start, p.end
    tol = ctx.tol.decide_length
    length = math.hypot(bx - ax, by - ay)
    if length == 0.0:
        d = math.hypot(x - ax, y - ay)
        ctx.decide('crossing', d, tol)
        return d <= tol
    t = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / length
    ctx.decide('crossing', t, tol)
    ctx.decide('crossing', t - length, tol)
    return -tol <= t <= length + tol


def _point_segment(x, y, a, b) -> float:
    """The distance from ``(x, y)`` to the closed segment ``ab``."""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    dd = dx * dx + dy * dy
    t = 0.0 if dd == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / dd))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def _line_line(p, q, ctx) -> list:
    """Common points of two straight pieces: an end of one within ``tol`` of
    the other (decision ``touch``), and the point of a proper crossing (the
    ends of each strictly on both sides of the other)."""
    tol = ctx.tol.decide_length
    out = []
    for (x, y), other in ((p.start, q), (p.end, q), (q.start, p), (q.end, p)):
        d = _point_segment(x, y, other.start, other.end)
        ctx.decide('touch', d, tol)
        if d <= tol:
            out.append((x, y))
    (ax, ay), (bx, by) = p.start, p.end
    (cx, cy), (dx, dy) = q.start, q.end
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    o1 = rx * (cy - ay) - ry * (cx - ax)
    o2 = rx * (dy - ay) - ry * (dx - ax)
    o3 = sx * (ay - cy) - sy * (ax - cx)
    o4 = sx * (by - cy) - sy * (bx - cx)
    if ((o1 > 0 > o2) or (o1 < 0 < o2)) and ((o3 > 0 > o4) or (o3 < 0 < o4)):
        t = o3 / (o3 - o4)
        out.append((ax + t * rx, ay + t * ry))
    return out


def _line_arc(p, q, ctx) -> list:
    """Common points of a straight piece ``p`` and an arc piece ``q``: the
    points of the line and the circle (decision ``tangent``: one point when
    ``|h − r| ≤ tol``) that lie on both pieces."""
    tol = ctx.tol.decide_length
    cx, cy, r = q.circle
    (ax, ay), (bx, by) = p.start, p.end
    length = math.hypot(bx - ax, by - ay)
    if length == 0.0:
        e = math.hypot(ax - cx, ay - cy) - r
        ctx.decide('tangent', e, tol)
        return [(ax, ay)] if abs(e) <= tol and _on_arc(q, ax, ay, ctx) else []
    ux, uy = (bx - ax) / length, (by - ay) / length
    m = (cx - ax) * ux + (cy - ay) * uy
    h = abs((cx - ax) * uy - (cy - ay) * ux)
    delta = h - r
    ctx.decide('tangent', delta, tol)
    if delta > tol:
        return []
    if abs(delta) <= tol:
        params = (m,)
    else:
        k = math.sqrt((r - h) * (r + h))
        params = (m - k, m + k)
    out = []
    for t in params:
        x, y = ax + t * ux, ay + t * uy
        if _on_line(p, x, y, ctx) and _on_arc(q, x, y, ctx):
            out.append((x, y))
    return out


def _arc_arc(p, q, ctx):
    """Common points of two arc pieces, or :data:`_OVERLAP`. One circle
    (decisions ``same_centre``, ``same_curve``): the overlap of the arcs
    longer than ``tol`` (decision ``touch``), else the ends of each on the
    other. Two circles: their points (decisions ``tangent``) on both arcs."""
    tol = ctx.tol.decide_length
    c1x, c1y, r1 = p.circle
    c2x, c2y, r2 = q.circle
    ex, ey = c2x - c1x, c2y - c1y
    d = math.hypot(ex, ey)
    ctx.decide('same_centre', d, tol)
    if d <= tol:
        diff = r1 - r2
        ctx.decide('same_curve', diff, tol)
        if abs(diff) > tol:
            return []
        s1, w1 = _interval(p)
        s2, w2 = _interval(q)
        shift = (s2 - s1) % TWO_PI
        overlap = 0.0
        for lo in (shift, shift - TWO_PI):
            a, b = max(0.0, lo), min(w1, lo + w2)
            if b > a:
                overlap = overlap + (b - a)
        ctx.decide('touch', r1 * overlap, tol)
        if r1 * overlap > tol:
            return _OVERLAP
        out = []
        for here, other in ((p, q), (q, p)):
            if here.whole:
                continue
            for x, y in (here.start, here.end):
                if _on_arc(other, x, y, ctx):
                    out.append((x, y))
        return out
    ux, uy = ex / d, ey / d
    a = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    e1 = d - (r1 + r2)
    e2 = abs(r1 - r2) - d
    ctx.decide('tangent', e1, tol)
    ctx.decide('tangent', e2, tol)
    if e1 > tol or e2 > tol:
        return []
    fx, fy = c1x + a * ux, c1y + a * uy
    if abs(e1) <= tol or abs(e2) <= tol:
        points = [(fx, fy)]
    else:
        h = math.sqrt(max(0.0, (r1 - a) * (r1 + a)))
        points = [(fx - h * uy, fy + h * ux), (fx + h * uy, fy - h * ux)]
    return [(x, y) for x, y in points if _on_arc(p, x, y, ctx) and _on_arc(q, x, y, ctx)]


def common_points(p, q, ctx):
    """The points common to two pieces (within ``tol.decide``), or
    :data:`_OVERLAP` when two arcs of one circle share a stretch."""
    if p.circle is None and q.circle is None:
        return _line_line(p, q, ctx)
    if p.circle is None:
        return _line_arc(p, q, ctx)
    if q.circle is None:
        return _line_arc(q, p, ctx)
    return _arc_arc(p, q, ctx)


def _box(p) -> tuple:
    """A box around a piece: the ends of a line, the square of the circle of an arc."""
    if p.circle is None:
        (ax, ay), (bx, by) = p.start, p.end
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    cx, cy, r = p.circle
    return cx - r, cy - r, cx + r, cy + r


def _simple(rings, ctx):
    """Step 4: no two pieces meet but adjacent ones at their common vertex
    (``tol.inc``, decision ``at_vertex``), else ``boundary_crossing``.
    Pairs in the order of the value; adjacent: the next piece of a ring (the
    last and the first too), a ring of two pieces meets at both ends. A pair
    whose boxes (:func:`_box`) are apart by more than ``tol`` has no common
    point and is skipped: a shortcut that changes no result."""
    tol_inc = ctx.tol.check_failed
    tol = ctx.tol.decide_length
    flat = [(k, j, p) for k, ring in enumerate(rings) for j, p in enumerate(ring)]
    boxes = [_box(p) for _k, _j, p in flat]
    for u in range(len(flat)):
        k1, j1, p = flat[u]
        n = len(rings[k1])
        x0, y0, x1, y1 = boxes[u]
        for v in range(u + 1, len(flat)):
            k2, j2, q = flat[v]
            bx0, by0, bx1, by1 = boxes[v]
            if bx0 > x1 + tol or x0 > bx1 + tol or by0 > y1 + tol or y0 > by1 + tol:
                continue                        # apart by more than tol: no common point (exact)
            shared = []
            if k1 == k2:
                if j2 == j1 + 1:
                    shared.append(p.end)
                if j1 == 0 and j2 == n - 1:
                    shared.append(q.end)
            common = common_points(p, q, ctx)
            if common == _OVERLAP:
                return Undefined('boundary_crossing')
            for x, y in common:
                near = False
                for vx, vy in shared:
                    dv = math.hypot(x - vx, y - vy)
                    ctx.decide('at_vertex', dv, tol_inc)
                    near = near or dv <= tol_inc
                if not near:
                    return Undefined('boundary_crossing')
    return None


# ── step 5: nesting ──────────────────────────────────────────────────────

def _midpoint(p) -> tuple:
    if p.circle is None:
        return (p.start[0] + p.end[0]) / 2, (p.start[1] + p.end[1]) / 2
    cx, cy, r = p.circle
    t = p.t0 + p.sweep / 2
    return cx + r * math.cos(t), cy + r * math.sin(t)


_HALF_PI = math.pi / 2


def monotone_parts(p) -> list:
    """The y-monotone parts of a piece in the order of the walk:
    ``[(a, b, side)]``, ``side`` 0 for a line, ``+1``/``−1`` for a part of an
    arc in the right/left half of its circle. An arc is cut at the angles
    ``π/2 + kπ`` strictly inside its sweep; the ends of the piece keep their
    coordinates, a cut is ``(cx + r cos τ, cy + r sin τ)``."""
    if p.circle is None:
        return [(p.start, p.end, 0)]
    cx, cy, r = p.circle
    lo, hi = (p.t0, p.t0 + p.sweep) if p.sweep >= 0 else (p.t0 + p.sweep, p.t0)
    k = math.floor((lo - _HALF_PI) / math.pi)
    cuts = []
    while True:
        tau = _HALF_PI + k * math.pi
        if tau >= hi:
            break
        if tau > lo:
            cuts.append(tau)
        k = k + 1
    if p.sweep < 0:
        cuts.reverse()
    angles = [p.t0] + cuts + [p.t0 + p.sweep]
    points = [p.start] + [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in cuts] + [p.end]
    return [(points[i], points[i + 1], 1 if math.cos((angles[i] + angles[i + 1]) / 2) >= 0 else -1)
            for i in range(len(points) - 1)]


def ring_contains(ring, x: float, y: float, ctx) -> bool:
    """The exact even-odd test of ``(x, y)`` against one ring: a ray to ``+x``
    crosses a monotone part ``(a, b)`` when ``(a.y > y) != (b.y > y)`` at
    ``x_c`` — on a line ``a.x + (y − a.y)(b.x − a.x)/(b.y − a.y)``, on an
    arc ``cx ± √(r² − (y − cy)²)`` by its side — when ``x_c > x``
    (decision ``nesting``: ``x_c − x``)."""
    tol = ctx.tol.decide_length
    odd = False
    for p in ring:
        for (ax, ay), (bx, by), side in monotone_parts(p):
            if (ay > y) == (by > y):
                continue
            if side == 0:
                xc = ax + (y - ay) * (bx - ax) / (by - ay)
            else:
                cx, cy, r = p.circle
                xc = cx + side * math.sqrt(max(0.0, r * r - (y - cy) * (y - cy)))
            ctx.decide('nesting', xc - x, tol)
            if xc > x:
                odd = not odd
    return odd


def _nested(rings, areas, ctx):
    """Step 5: the depth of a ring is the number of other rings that hold the
    middle of its first piece; an even depth needs ``A > 0``, an odd one
    ``A < 0``. A ring of the chain that breaks it is ``flipped``, a contour
    (its walk is fixed by its slot) ``boundary_crossing``."""
    for k, ring in enumerate(rings):
        x, y = _midpoint(ring[0])
        depth = sum(1 for j, other in enumerate(rings) if j != k and ring_contains(other, x, y, ctx))
        if (areas[k] > 0) != (depth % 2 == 0):
            return Undefined('flipped' if ring[0].index is not None else 'boundary_crossing')
    return None


@op('region.by_boundary')
def by_boundary(args, ctx):
    pieces, rings, failure = _rings(args)
    if failure is None:
        failure = _incidence(args, ctx)
    if failure is None:
        failure = _parts(args, pieces, ctx)
    if failure is None:
        areas = [ring_area(ring) for ring in rings]
        failure = _empty(areas, ctx) or _simple(rings, ctx) or _nested(rings, areas, ctx)
    if failure is None:
        total = sum(areas)
        tol = ctx.tol.decide_length * ctx.tol.scale
        ctx.decide('empty_region', total, tol)
        if total <= tol:
            failure = Undefined('empty_region')
    if failure is not None:
        return {'region': failure}
    return {'region': {'rings': [[p.value() for p in ring] for ring in rings],
                       'shape': [[[p.kind, p.source] for p in ring] for ring in rings],
                       'area': total}}
