"""Measures, registry 1.4 (docs/native/ops/measure.*.md): numbers with a unit.

``length``, ``distance``, ``perimeter``, ``radius``, ``circumference`` give
``unit: "length"``, ``area`` gives ``"area"``, ``angle`` gives ``"angle"``
(radians).
"""
from __future__ import annotations

import math

from ..paths import distance_to_path
from . import op
from .angle import TWO_PI


def _length(value: float) -> dict:
    return {'value': value, 'unit': 'length'}


@op('measure.length')
def length(args, ctx):
    of = args['of']
    v = of.value
    if of.type == 'arc':
        return {'number': _length(v['r'] * (v['a1'] - v['a0']))}
    return {'number': _length(v['length'])}


@op('measure.distance')
def distance(args, ctx):
    p = args['point'].value
    to = args['to']
    if to.type == 'point':
        d = math.hypot(to.value['x'] - p['x'], to.value['y'] - p['y'])
    else:
        d = distance_to_path(p['x'], p['y'], to.type, to.value)
    return {'number': _length(d)}


@op('measure.area')
def area(args, ctx):
    of = args['of']
    v = of.value
    if of.type == 'polygon':
        a = v['area']
    elif of.type == 'circle':
        a = math.pi * v['r'] * v['r']
    else:
        a = v['r'] * v['r'] * (v['a1'] - v['a0']) / 2
    return {'number': {'value': a, 'unit': 'area'}}


@op('measure.perimeter')
def perimeter(args, ctx):
    of = args['of']
    v = of.value
    if of.type == 'polygon':
        vs = v['vertices']
        n = len(vs)
        p = 0.0
        for i in range(n):
            p = p + math.hypot(vs[(i + 1) % n][0] - vs[i][0], vs[(i + 1) % n][1] - vs[i][1])
    elif of.type == 'circle':
        p = TWO_PI * v['r']
    else:
        p = v['r'] * (v['a1'] - v['a0']) + 2 * v['r']
    return {'number': _length(p)}


@op('measure.angle')
def angle(args, ctx):
    return {'number': {'value': args['angle'].value['size'], 'unit': 'angle'}}


@op('measure.radius')
def radius(args, ctx):
    return {'number': _length(args['of'].value['r'])}


@op('measure.circumference')
def circumference(args, ctx):
    return {'number': _length(TWO_PI * args['circle'].value['r'])}


@op('measure.polygon_angles')
def polygon_angles(args, ctx):
    from ..values import Undefined
    from .angle import angle_size, normalize_angle, unit_sides
    vs = args['polygon'].value['vertices']
    n = len(vs)
    acc = 0.0
    for i in range(n):
        xi, yi = vs[i]
        xj, yj = vs[(i + 1) % n]
        acc = acc + (xi * yj - xj * yi)
    perimeter = 0.0
    for i in range(n):
        perimeter = perimeter + math.hypot(vs[(i + 1) % n][0] - vs[i][0], vs[(i + 1) % n][1] - vs[i][1])
    h = abs(acc) / perimeter if perimeter > 0 else 0.0
    tol = ctx.tol.decide_length
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        undefined = Undefined('collinear_points')
        return {f'angle.{k}': undefined for k in range(1, n + 1)}
    tol_s = ctx.tol.decide_scalar
    out = {}
    for k in range(n):
        vx, vy = vs[k]
        prev = {'x': vs[k - 1][0], 'y': vs[k - 1][1]}
        nxt = {'x': vs[(k + 1) % n][0], 'y': vs[(k + 1) % n][1]}
        first, second = (nxt, prev) if acc > 0 else (prev, nxt)
        sides = unit_sides(first, {'x': vx, 'y': vy}, second, ctx)
        if isinstance(sides, Undefined):
            out[f'angle.{k + 1}'] = sides
            continue
        u, w = sides
        if u[0] > 0:
            ctx.decide('angle_wrap', u[1], tol_s)
        q = u[0] * w[0] + u[1] * w[1]
        if q > 0:
            ctx.decide('zero_angle', u[0] * w[1] - u[1] * w[0], tol_s)
        size = angle_size(u, w)
        a0 = normalize_angle(math.atan2(u[1], u[0]))
        out[f'angle.{k + 1}'] = {'vertex': [vx, vy], 'a0': a0, 'a1': a0 + size, 'size': size}
    return out
