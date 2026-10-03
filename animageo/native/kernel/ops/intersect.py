"""``intersect.line_line`` (docs/native/ops/intersect.line_line.md)."""
from __future__ import annotations

import math
from typing import NamedTuple

from ..values import Undefined
from . import op


class Carrier(NamedTuple):
    """The line carrying a linear input: point ``(px, py)``, unit direction
    ``(dx, dy)``; ``length`` is the segment length (``None`` for a line)."""

    px: float
    py: float
    dx: float
    dy: float
    length: float | None


def carrier(inp, ctx):
    """Carrier of a ``line`` or ``segment`` input, or ``Undefined('zero_length')``."""
    v = inp.value
    if inp.type == 'line':
        return Carrier(v['p'][0], v['p'][1], v['dir'][0], v['dir'][1], None)
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


@op('intersect.line_line')
def line_line(args, ctx):
    c1 = carrier(args['first'], ctx)
    if isinstance(c1, Undefined):
        return {'point': c1}
    c2 = carrier(args['second'], ctx)
    if isinstance(c2, Undefined):
        return {'point': c2}
    tol = ctx.tol.decide_length
    cross = c1.dx * c2.dy - c1.dy * c2.dx
    ctx.decide('parallel', cross, ctx.tol.decide_scalar)
    wx = c2.px - c1.px
    wy = c2.py - c1.py
    if abs(cross) <= ctx.tol.decide_scalar:
        dist = abs(wx * c1.dy - wy * c1.dx)
        ctx.decide('coincident', dist, tol)
        return {'point': Undefined('coincident' if dist <= tol else 'parallel')}
    t = (wx * c2.dy - wy * c2.dx) / cross
    x = c1.px + t * c1.dx
    y = c1.py + t * c1.dy
    for slot, c in (('first', c1), ('second', c2)):
        if c.length is None:
            continue
        s = (x - c.px) * c.dx + (y - c.py) * c.dy
        ctx.decide('outside_part', s, tol)
        ctx.decide('outside_part', s - c.length, tol)
        if s < -tol or s > c.length + tol:
            return {'point': Undefined('outside_part', {'slot': slot})}
    return {'point': {'x': x, 'y': y}}
