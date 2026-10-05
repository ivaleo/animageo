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
