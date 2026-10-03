"""``point.free``, ``point.midpoint``, ``point.on_path``, ``point.projection`` (docs/native/ops/point.*.md)."""
from __future__ import annotations

from ..paths import frame, point_at
from ..values import Undefined
from . import op
from .intersect import carrier


@op('point.free')
def free(args, ctx):
    x, y = ctx.input['value']
    return {'point': {'x': float(x), 'y': float(y)}}


@op('point.midpoint')
def midpoint(args, ctx):
    a = args['a'].value
    b = args['b'].value
    return {'point': {'x': (a['x'] + b['x']) / 2, 'y': (a['y'] + b['y']) / 2}}


@op('point.on_path')
def on_path(args, ctx):
    path = args['path']
    f = path.frame if path.frame is not None else frame(path.type, path.value)
    return {'point': point_at(f, float(ctx.input['value']))}


@op('point.projection')
def projection(args, ctx):
    strict = args['strict']
    if strict != 0 and strict != 1:
        return {'foot': Undefined('invalid_parameter')}
    c = carrier(args['base'], ctx)
    if isinstance(c, Undefined):
        return {'foot': c}
    p = args['point'].value
    t = (p['x'] - c.px) * c.dx + (p['y'] - c.py) * c.dy
    foot = {'x': c.px + t * c.dx, 'y': c.py + t * c.dy}
    if strict == 1 and (c.ray or c.length is not None):
        tol = ctx.tol.decide_length
        ctx.decide('outside_part', t, tol)
        if c.length is not None:
            ctx.decide('outside_part', t - c.length, tol)
        if t < -tol or (c.length is not None and t > c.length + tol):
            return {'foot': Undefined('outside_part', {'slot': 'base'})}
    return {'foot': foot}
