"""``point.free``, ``point.midpoint``, ``point.on_path``, ``point.projection``; registry 1.4:
``point.divide``, ``point.center``, ``point.closest``, ``point.at_distance`` (docs/native/ops/point.*.md).
Registry 1.9: ``point.on_path`` and ``point.closest`` on a conic and on a graph."""
from __future__ import annotations

import math

from ..paths import frame, locate, point_at
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
    inp = ctx.input
    if path.type == 'conic' and inp.get('pathKind', path.value['kind']) != path.value['kind']:
        return {'point': Undefined('path_kind_changed')}       # registry 1.9: the same t when the kind returns
    f = path.frame if path.frame is not None else frame(path.type, path.value)
    point = point_at(f, float(inp['value']), inp.get('branch', 1))
    return {'point': Undefined('out_of_domain') if point is None else point}


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
    found = locate(f, p['x'], p['y'], ctx.tol.decide_length, ctx.bounds, ctx.decide)
    if found is None:                   # registry 1.9: a graph without a point in its search interval
        return {'foot': Undefined('out_of_domain')}
    foot = point_at(f, *found)
    return {'foot': Undefined('out_of_domain') if foot is None else foot}


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
