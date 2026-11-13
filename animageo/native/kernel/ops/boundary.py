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
    """``(rings, None)`` — the rings in the order of the value (chain rings
    in document order, then ``inside``, then ``outside``) — or ``(None,
    Undefined)``."""
    curves, starts, ends = args['curves'], args['from'], args['to']
    pieces = chain_pieces(curves, starts, ends)
    if isinstance(pieces, Undefined):
        return None, pieces
    walks, _problem = boundary_chain([c.id for c in curves], [s.id for s in starts], [e.id for e in ends],
                                     [c.type in _ROUND for c in curves], len(args['inside']) + len(args['outside']))
    rings = [[pieces[i] if forward else pieces[i].reversed() for i, forward in walk] for walk in walks or ()]
    for k, contour in enumerate(args['inside']):
        rings.append(contour_ring(contour, f'inside.{k}'))
    for k, contour in enumerate(args['outside']):
        rings.append(reversed_ring(contour_ring(contour, f'outside.{k}')))
    if sum(len(ring) for ring in rings) > PIECES_MAX:
        return None, Undefined('limit_exceeded')
    return rings, None


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


@op('region.by_boundary')
def by_boundary(args, ctx):
    rings, failure = _rings(args)
    if failure is not None:
        return {'region': failure}
    failure = _incidence(args, ctx)
    if failure is None:
        failure = _parts(args, chain_pieces(args['curves'], args['from'], args['to']), ctx)
    if failure is not None:
        return {'region': failure}
    areas = [ring_area(ring) for ring in rings]
    return {'region': {'rings': [[p.value() for p in ring] for ring in rings],
                       'shape': [[[p.kind, p.source] for p in ring] for ring in rings],
                       'area': sum(areas)}}
