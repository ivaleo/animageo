"""``segment.by_points``, ``line.by_points`` (docs/native/ops/*.md)."""
from __future__ import annotations

import math

from ..values import Undefined
from . import op


@op('segment.by_points')
def segment(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
    return {'segment': {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}}


@op('line.by_points')
def line(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay = a['x'], a['y']
    dx = b['x'] - ax
    dy = b['y'] - ay
    length = math.hypot(dx, dy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return {'line': Undefined('coincident_points')}
    dirx = dx / length
    diry = dy / length
    k = ax * dirx + ay * diry
    return {'line': {'p': [ax - k * dirx, ay - k * diry], 'dir': [dirx, diry]}}
