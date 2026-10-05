"""Arcs and sectors, registry 1.4 (docs/native/ops/arc.*.md, sector.*.md).

An arc or a sector is ``{c: [x, y], r, a0, a1}``: counterclockwise from
``a0`` to ``a1``, ``a0`` in ``[0, 2π)``, ``a1`` in ``[a0, a0 + 2π]``.
"""
from __future__ import annotations

import math

from ..values import Undefined
from . import op
from .angle import TWO_PI, normalize_angle
from .circle import circumcenter


def _direction(cx, cy, p: dict, ctx):
    """``(angle, length)`` of ``p − c``, or ``Undefined("coincident_points")``."""
    wx = p['x'] - cx
    wy = p['y'] - cy
    length = math.hypot(wx, wy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return Undefined('coincident_points')
    return normalize_angle(math.atan2(wy, wx)), length


def _end(a0: float, beta: float) -> float:
    """``a1`` of an arc from ``a0`` to the direction ``beta`` (both in ``[0, 2π)``)."""
    return beta if beta >= a0 else beta + TWO_PI


def _center_two_points(args, ctx):
    o = args['center'].value
    cx, cy = o['x'], o['y']
    start = _direction(cx, cy, args['a'].value, ctx)
    end = _direction(cx, cy, args['b'].value, ctx)
    if isinstance(start, Undefined):
        return start
    if isinstance(end, Undefined):
        return end
    a0, r = start
    return {'c': [cx, cy], 'r': r, 'a0': a0, 'a1': _end(a0, end[0])}


def _three_points(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    cc = circumcenter(a, b, c, ctx)
    if isinstance(cc, Undefined):
        return cc, cc
    ox, oy, r = cc
    ta = normalize_angle(math.atan2(a['y'] - oy, a['x'] - ox))
    tb = normalize_angle(math.atan2(b['y'] - oy, b['x'] - ox))
    tc = normalize_angle(math.atan2(c['y'] - oy, c['x'] - ox))
    pb = tb - ta
    if pb < 0:
        pb += TWO_PI
    pc = tc - ta
    if pc < 0:
        pc += TWO_PI
    if pb <= pc:
        value = {'c': [ox, oy], 'r': r, 'a0': ta, 'a1': ta + pc}
    else:
        value = {'c': [ox, oy], 'r': r, 'a0': tc, 'a1': tc + (TWO_PI - pc)}
    return value, {'x': ox, 'y': oy}


def _on_circle(args, ctx):
    circle = args['circle'].value
    cx, cy = circle['c']
    start = _direction(cx, cy, args['a'].value, ctx)
    end = _direction(cx, cy, args['b'].value, ctx)
    if isinstance(start, Undefined):
        return start
    if isinstance(end, Undefined):
        return end
    a0 = start[0]
    return {'c': [cx, cy], 'r': circle['r'], 'a0': a0, 'a1': _end(a0, end[0])}


@op('arc.center_two_points')
def arc_center_two_points(args, ctx):
    return {'arc': _center_two_points(args, ctx)}


@op('arc.three_points')
def arc_three_points(args, ctx):
    value, center = _three_points(args, ctx)
    return {'arc': value, 'center': center}


@op('arc.semicircle')
def arc_semicircle(args, ctx):
    a = args['a'].value
    b = args['b'].value
    length = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return {'arc': Undefined('coincident_points')}
    cx = (a['x'] + b['x']) / 2
    cy = (a['y'] + b['y']) / 2
    a0 = normalize_angle(math.atan2(b['y'] - cy, b['x'] - cx))
    return {'arc': {'c': [cx, cy], 'r': length / 2, 'a0': a0, 'a1': a0 + math.pi}}


@op('arc.on_circle')
def arc_on_circle(args, ctx):
    return {'arc': _on_circle(args, ctx)}


@op('sector.center_two_points')
def sector_center_two_points(args, ctx):
    return {'sector': _center_two_points(args, ctx)}


@op('sector.from_angle')
def sector_from_angle(args, ctx):
    o = args['center'].value
    cx, cy = o['x'], o['y']
    start = _direction(cx, cy, args['a'].value, ctx)
    if isinstance(start, Undefined):
        return {'sector': start}
    a, r = start
    alpha = args['size'].value['value']
    alpha = max(-TWO_PI, min(TWO_PI, alpha))
    if alpha >= 0:
        return {'sector': {'c': [cx, cy], 'r': r, 'a0': a, 'a1': a + alpha}}
    a0 = normalize_angle(a + alpha)
    return {'sector': {'c': [cx, cy], 'r': r, 'a0': a0, 'a1': a0 - alpha}}


@op('sector.three_points')
def sector_three_points(args, ctx):
    value, center = _three_points(args, ctx)
    return {'sector': value, 'center': center}


@op('sector.on_circle')
def sector_on_circle(args, ctx):
    return {'sector': _on_circle(args, ctx)}
