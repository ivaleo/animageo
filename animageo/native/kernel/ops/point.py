"""``point.free``, ``point.midpoint``, ``point.on_path``, ``point.projection``; registry 1.4:
``point.divide``, ``point.center``, ``point.closest``, ``point.at_distance`` (docs/native/ops/point.*.md)."""
from __future__ import annotations

import math

from ..paths import frame, point_at, project
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


@op('point.divide')
def divide(args, ctx):
    a = args['a'].value
    b = args['b'].value
    m = args['m'].value['value']
    n = args['n'].value['value']
    s = m + n
    tol_s = ctx.tol.decide_scalar
    ctx.decide('invalid_parameter', m, tol_s)
    ctx.decide('invalid_parameter', n, tol_s)
    ctx.decide('invalid_parameter', s, tol_s)
    if m < -tol_s or n < -tol_s or s <= tol_s:
        return {'point': Undefined('invalid_parameter')}
    return {'point': {'x': (n * a['x'] + m * b['x']) / s, 'y': (n * a['y'] + m * b['y']) / s}}


@op('point.center')
def center(args, ctx):
    c = args['of'].value['c']
    return {'center': {'x': c[0], 'y': c[1]}}


@op('point.closest')
def closest(args, ctx):
    path = args['path']
    p = args['point'].value
    f = path.frame if path.frame is not None else frame(path.type, path.value)
    t = project(f, p['x'], p['y'], ctx.tol.decide_length)
    return {'foot': point_at(f, t)}


@op('point.at_distance')
def at_distance(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay = a['x'], a['y']
    vx = b['x'] - ax
    vy = b['y'] - ay
    length = math.hypot(vx, vy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        none = Undefined('coincident_points')
        return {'point': none, 'segment': none}
    d = args['distance'].value['value']
    px = ax + d * (vx / length)
    py = ay + d * (vy / length)
    return {'point': {'x': px, 'y': py}, 'segment': {'a': [ax, ay], 'b': [px, py], 'length': abs(d)}}
