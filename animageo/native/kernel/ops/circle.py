"""``circle.center_point``, ``circle.center_radius``, ``circle.three_points``, ``circle.incircle``;
registry 1.4: ``circle.diameter``, ``circle.center_segment``, ``circle.excircle``
(docs/native/ops/circle.*.md)."""
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


INCIRCLE_SLOTS = ('circle', 'center', 'touch_a', 'touch_b', 'touch_c')


@op('circle.incircle')
def incircle(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    ax, ay = a['x'], a['y']
    bx, by = b['x'], b['y']
    cx, cy = c['x'], c['y']
    la = math.hypot(bx - cx, by - cy)
    lb = math.hypot(cx - ax, cy - ay)
    lc = math.hypot(ax - bx, ay - by)
    longest = max(la, lb, lc)
    tol = ctx.tol.decide_length
    ctx.decide('collinear_points', longest, tol)
    if longest <= tol:
        return dict.fromkeys(INCIRCLE_SLOTS, Undefined('collinear_points'))
    cr = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    h = abs(cr) / longest
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        return dict.fromkeys(INCIRCLE_SLOTS, Undefined('collinear_points'))
    p = la + lb + lc
    s = p / 2
    ox = (la * ax + lb * bx + lc * cx) / p
    oy = (la * ay + lb * by + lc * cy) / p
    ta = (s - lb) / la
    tb = (s - lc) / lb
    tc = (s - la) / lc
    return {
        'circle': {'c': [ox, oy], 'r': abs(cr) / p},
        'center': {'x': ox, 'y': oy},
        'touch_a': {'x': bx + ta * (cx - bx), 'y': by + ta * (cy - by)},
        'touch_b': {'x': cx + tb * (ax - cx), 'y': cy + tb * (ay - cy)},
        'touch_c': {'x': ax + tc * (bx - ax), 'y': ay + tc * (by - ay)},
    }


def circumcenter(a: dict, b: dict, c: dict, ctx):
    """``(ox, oy, r)`` by steps 1–4 of ``circle.three_points``, or
    ``Undefined("collinear_points")``."""
    ax, ay = a['x'], a['y']
    la = math.hypot(b['x'] - c['x'], b['y'] - c['y'])
    lb = math.hypot(c['x'] - ax, c['y'] - ay)
    lc = math.hypot(ax - b['x'], ay - b['y'])
    longest = max(la, lb, lc)
    tol = ctx.tol.decide_length
    ctx.decide('collinear_points', longest, tol)
    if longest <= tol:
        return Undefined('collinear_points')
    bx = b['x'] - ax
    by = b['y'] - ay
    cx = c['x'] - ax
    cy = c['y'] - ay
    cr = bx * cy - by * cx
    h = abs(cr) / longest
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        return Undefined('collinear_points')
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    d = 2 * cr
    ux = (cy * b2 - by * c2) / d
    uy = (bx * c2 - cx * b2) / d
    return ax + ux, ay + uy, math.hypot(ux, uy)


@op('circle.diameter')
def diameter(args, ctx):
    a = args['a'].value
    b = args['b'].value
    length = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        none = Undefined('coincident_points')
        return {'circle': none, 'center': none}
    cx = (a['x'] + b['x']) / 2
    cy = (a['y'] + b['y']) / 2
    return {'circle': {'c': [cx, cy], 'r': length / 2}, 'center': {'x': cx, 'y': cy}}


@op('circle.center_segment')
def center_segment(args, ctx):
    c = args['center'].value
    r = args['radius'].value['length']
    tol = ctx.tol.decide_length
    ctx.decide('nonpositive_radius', r, tol)
    if r <= tol:
        return {'circle': Undefined('nonpositive_radius')}
    return {'circle': {'c': [c['x'], c['y']], 'r': r}}


EXCIRCLE_SLOTS = ('circle', 'center', 'touch')


@op('circle.excircle')
def excircle(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    ax, ay = a['x'], a['y']
    bx, by = b['x'], b['y']
    cx, cy = c['x'], c['y']
    la = math.hypot(bx - cx, by - cy)
    lb = math.hypot(cx - ax, cy - ay)
    lc = math.hypot(ax - bx, ay - by)
    longest = max(la, lb, lc)
    tol = ctx.tol.decide_length
    ctx.decide('collinear_points', longest, tol)
    if longest <= tol:
        return dict.fromkeys(EXCIRCLE_SLOTS, Undefined('collinear_points'))
    cr = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    h = abs(cr) / longest
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        return dict.fromkeys(EXCIRCLE_SLOTS, Undefined('collinear_points'))
    s = -la + lb + lc
    ox = (-la * ax + lb * bx + lc * cx) / s
    oy = (-la * ay + lb * by + lc * cy) / s
    ex = (cx - bx) / la
    ey = (cy - by) / la
    t = (ox - bx) * ex + (oy - by) * ey
    tx = bx + t * ex
    ty = by + t * ey
    return {
        'circle': {'c': [ox, oy], 'r': math.hypot(ox - tx, oy - ty)},
        'center': {'x': ox, 'y': oy},
        'touch': {'x': tx, 'y': ty},
    }
