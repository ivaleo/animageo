"""Intersections (docs/native/ops/intersect.*.md)."""
from __future__ import annotations

import math
from typing import NamedTuple

from ..values import Detailed, Undefined
from . import op


class Carrier(NamedTuple):
    """The line carrying a linear input: point ``(px, py)``, unit direction
    ``(dx, dy)``; ``length`` is the segment length (``None`` for a line or a
    ray); ``ray`` marks a ray (parameter ``s >= 0`` along ``dir``)."""

    px: float
    py: float
    dx: float
    dy: float
    length: float | None
    ray: bool = False


def carrier(inp, ctx):
    """Carrier of a ``line``, ``segment`` or ``ray`` input, or ``Undefined('zero_length')``."""
    v = inp.value
    if inp.type == 'line':
        return Carrier(v['p'][0], v['p'][1], v['dir'][0], v['dir'][1], None)
    if inp.type == 'ray':
        return Carrier(v['origin'][0], v['origin'][1], v['dir'][0], v['dir'][1], None, True)
    ax, ay = v['a']
    bx, by = v['b']
    dx = bx - ax
    dy = by - ay
    length = math.hypot(dx, dy)
    tol = ctx.tol.decide_length
    ctx.decide('zero_length', length, tol)
    if length <= tol:
        return Undefined('zero_length')
    return Carrier(ax, ay, dx / length, dy / length, length)


def distance_to_carrier(x: float, y: float, c: Carrier) -> float:
    """``|(X - p) × dir|``, the distance from ``(x, y)`` to the carrier line."""
    return abs((x - c.px) * c.dy - (y - c.py) * c.dx)


def line_line_point(first, second, ctx):
    """The intersection point of two linear inputs, or :class:`Undefined`."""
    c1 = carrier(first, ctx)
    if isinstance(c1, Undefined):
        return c1
    c2 = carrier(second, ctx)
    if isinstance(c2, Undefined):
        return c2
    tol = ctx.tol.decide_length
    cross = c1.dx * c2.dy - c1.dy * c2.dx
    ctx.decide('parallel', cross, ctx.tol.decide_scalar)
    wx = c2.px - c1.px
    wy = c2.py - c1.py
    if abs(cross) <= ctx.tol.decide_scalar:
        dist = abs(wx * c1.dy - wy * c1.dx)
        ctx.decide('coincident', dist, tol)
        return Undefined('coincident' if dist <= tol else 'parallel')
    t = (wx * c2.dy - wy * c2.dx) / cross
    x = c1.px + t * c1.dx
    y = c1.py + t * c1.dy
    for slot, c in (('first', c1), ('second', c2)):
        if c.ray:
            s = (x - c.px) * c.dx + (y - c.py) * c.dy
            ctx.decide('outside_part', s, tol)
            if s < -tol:
                return Undefined('outside_part', {'slot': slot})
            continue
        if c.length is None:
            continue
        s = (x - c.px) * c.dx + (y - c.py) * c.dy
        ctx.decide('outside_part', s, tol)
        ctx.decide('outside_part', s - c.length, tol)
        if s < -tol or s > c.length + tol:
            return Undefined('outside_part', {'slot': slot})
    return {'x': x, 'y': y}


@op('intersect.line_line')
def line_line(args, ctx):
    return {'point': line_line_point(args['first'], args['second'], ctx)}


def _circle(inp):
    v = inp.value
    return v['c'][0], v['c'][1], v['r']


_DOUBLE = {'multiplicity': 2}


def line_circle_points(linear, circle, ctx, line_slot: str) -> list:
    """``[first, second]`` of a linear input and a circle (``line_param_order``).

    Slots are fixed on the carrier line before the part filter; a slot outside
    the segment or ray is ``outside_part`` with ``detail.slot = line_slot``.
    """
    c = carrier(linear, ctx)
    if isinstance(c, Undefined):
        return [c, c]
    cx, cy, r = _circle(circle)
    tol = ctx.tol.decide_length
    wx = cx - c.px
    wy = cy - c.py
    m = wx * c.dx + wy * c.dy
    h = abs(wx * c.dy - wy * c.dx)
    delta = h - r
    ctx.decide('tangent', delta, tol)
    if delta > tol:
        return [Undefined('no_intersection'), Undefined('no_intersection')]
    if abs(delta) <= tol:
        params = ((m, _DOUBLE), (m, _DOUBLE))
    else:
        k = math.sqrt((r - h) * (r + h))
        params = ((m - k, None), (m + k, None))
    out = []
    for t, detail in params:
        if c.ray or c.length is not None:
            ctx.decide('outside_part', t, tol)
            if c.length is not None:
                ctx.decide('outside_part', t - c.length, tol)
            if t < -tol or (c.length is not None and t > c.length + tol):
                out.append(Undefined('outside_part', {'slot': line_slot}))
                continue
        point = {'x': c.px + t * c.dx, 'y': c.py + t * c.dy}
        out.append(Detailed(point, dict(detail)) if detail is not None else point)
    return out


@op('intersect.line_circle')
def line_circle(args, ctx):
    first, second = line_circle_points(args['line'], args['circle'], ctx, 'line')
    return {'first': first, 'second': second}


def circle_circle_points(first, second, ctx) -> list:
    """``[first, second]`` of two circles (``circle_side``): ``first`` lies to
    the left of the directed segment from the first centre to the second."""
    c1x, c1y, r1 = _circle(first)
    c2x, c2y, r2 = _circle(second)
    tol = ctx.tol.decide_length
    ex = c2x - c1x
    ey = c2y - c1y
    d = math.hypot(ex, ey)
    ctx.decide('concentric', d, tol)
    if d <= tol:
        diff = abs(r1 - r2)
        ctx.decide('coincident', diff, tol)
        reason = 'coincident' if diff <= tol else 'concentric'
        return [Undefined(reason), Undefined(reason)]
    ux = ex / d
    uy = ey / d
    a = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    e1 = d - (r1 + r2)
    e2 = abs(r1 - r2) - d
    ctx.decide('tangent', e1, tol)
    ctx.decide('tangent', e2, tol)
    if e1 > tol or e2 > tol:
        return [Undefined('no_intersection'), Undefined('no_intersection')]
    fx = c1x + a * ux
    fy = c1y + a * uy
    if abs(e1) <= tol or abs(e2) <= tol:
        return [Detailed({'x': fx, 'y': fy}, dict(_DOUBLE)), Detailed({'x': fx, 'y': fy}, dict(_DOUBLE))]
    h = math.sqrt(max(0.0, (r1 - a) * (r1 + a)))
    nx = -uy
    ny = ux
    return [{'x': fx + h * nx, 'y': fy + h * ny}, {'x': fx - h * nx, 'y': fy - h * ny}]


@op('intersect.circle_circle')
def circle_circle(args, ctx):
    first, second = circle_circle_points(args['first'], args['second'], ctx)
    return {'first': first, 'second': second}


_LINEAR = ('line', 'segment', 'ray')


def _plain(value):
    return value.value if isinstance(value, Detailed) else value


@op('intersect.other_than')
def other_than(args, ctx):
    first = args['first']
    second = args['second']
    known = args['known'].value
    if first.type in _LINEAR and second.type in _LINEAR:
        roots = [line_line_point(first, second, ctx)]
    elif first.type in _LINEAR:
        roots = line_circle_points(first, second, ctx, 'first')
    elif second.type in _LINEAR:
        roots = line_circle_points(second, first, ctx, 'second')
    else:
        roots = circle_circle_points(first, second, ctx)
    roots = [_plain(r) for r in roots]
    defined = [i for i, r in enumerate(roots) if not isinstance(r, Undefined)]
    if not defined:
        return {'point': roots[0]}
    tol = ctx.tol.decide_length
    kx = known['x']
    ky = known['y']
    hit = None
    for i in defined:
        dist = math.hypot(roots[i]['x'] - kx, roots[i]['y'] - ky)
        ctx.decide('known', dist, tol)
        if hit is None and dist <= tol:
            hit = i
    if hit is None:
        return {'point': Undefined('branch_absent')}
    rest = [i for i in range(len(roots)) if i != hit]
    for i in rest:
        if not isinstance(roots[i], Undefined):
            return {'point': roots[i]}
    if rest:
        return {'point': roots[rest[0]]}
    return {'point': Undefined('branch_absent')}
