"""``circle.center_point``, ``circle.center_radius``, ``circle.three_points`` (docs/native/ops/circle.*.md)."""
from __future__ import annotations

import math

from ..values import Undefined
from . import op


@op('circle.center_point')
def center_point(args, ctx):
    c = args['center'].value
    t = args['through'].value
    cx, cy = c['x'], c['y']
    r = math.hypot(t['x'] - cx, t['y'] - cy)
    tol = ctx.tol.decide_length
    ctx.decide('nonpositive_radius', r, tol)
    if r <= tol:
        return {'circle': Undefined('nonpositive_radius')}
    return {'circle': {'c': [cx, cy], 'r': r}}


@op('circle.center_radius')
def center_radius(args, ctx):
    c = args['center'].value
    r = args['radius'].value['value']
    tol = ctx.tol.decide_length
    ctx.decide('nonpositive_radius', r, tol)
    if r <= tol:
        return {'circle': Undefined('nonpositive_radius')}
    return {'circle': {'c': [c['x'], c['y']], 'r': r}}


@op('circle.three_points')
def three_points(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    ax, ay = a['x'], a['y']
    la = math.hypot(b['x'] - c['x'], b['y'] - c['y'])
    lb = math.hypot(c['x'] - ax, c['y'] - ay)
    lc = math.hypot(ax - b['x'], ay - b['y'])
    longest = max(la, lb, lc)
    tol = ctx.tol.decide_length
    ctx.decide('collinear_points', longest, tol)
    if longest <= tol:
        none = Undefined('collinear_points')
        return {'circle': none, 'center': none}
    bx = b['x'] - ax
    by = b['y'] - ay
    cx = c['x'] - ax
    cy = c['y'] - ay
    cr = bx * cy - by * cx
    h = abs(cr) / longest
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        none = Undefined('collinear_points')
        return {'circle': none, 'center': none}
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    d = 2 * cr
    ux = (cy * b2 - by * c2) / d
    uy = (bx * c2 - cx * b2) / d
    ox = ax + ux
    oy = ay + uy
    return {'circle': {'c': [ox, oy], 'r': math.hypot(ux, uy)}, 'center': {'x': ox, 'y': oy}}
