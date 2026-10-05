"""Transformations, registry 1.4 (docs/native/ops/transform.*.md).

The image has the type of ``obj`` (output ``image``, ``like: "obj"``); the
image of a polygon also gives ``side.i`` and ``vertex.k`` (``vertex_index``):
``vertex.k`` is the image of vertex ``k``, the orientation is not
normalised (a reflection gives a clockwise polygon, its area stays
unsigned). Arcs and sectors stay counterclockwise: a reflection in a line
swaps their ends.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from ..values import Undefined
from . import op
from .angle import TWO_PI
from .intersect import carrier
from .line import line_through
from .polygon import polygon_parts


class Map(NamedTuple):
    """A similarity: ``point(x, y)`` maps a point, ``direction(dx, dy)`` the
    unit direction of a line or a ray (before renormalising), ``scale`` the
    length factor, ``turn(θ)`` a direction angle; ``reverses`` — the map
    reverses orientation (``turn`` then reflects: ``θ → 2β − θ``)."""

    point: object
    direction: object
    scale: float
    turn: object
    reverses: bool


def _translate(args, ctx):
    v = args['vector'].value
    vx = v['b'][0] - v['a'][0]
    vy = v['b'][1] - v['a'][1]
    return Map(lambda x, y: (x + vx, y + vy), lambda dx, dy: (dx, dy), 1.0, lambda t: t, False)


def _rotate(args, ctx):
    alpha = args['angle'].value['value']
    c = args['center'].value
    cx, cy = c['x'], c['y']
    co = math.cos(alpha)
    si = math.sin(alpha)

    def point(x, y):
        wx = x - cx
        wy = y - cy
        return cx + (co * wx - si * wy), cy + (si * wx + co * wy)

    return Map(point, lambda dx, dy: (co * dx - si * dy, si * dx + co * dy), 1.0, lambda t: t + alpha, False)


def _reflect_line(args, ctx):
    c = carrier(args['line'], ctx)
    if isinstance(c, Undefined):
        return c
    px, py, dx, dy = c.px, c.py, c.dx, c.dy
    beta = math.atan2(dy, dx)

    def point(x, y):
        wx = x - px
        wy = y - py
        s = wx * dx + wy * dy
        return px + (2 * s * dx - wx), py + (2 * s * dy - wy)

    def direction(ux, uy):
        s = ux * dx + uy * dy
        return 2 * s * dx - ux, 2 * s * dy - uy

    return Map(point, direction, 1.0, lambda t: 2 * beta - t, True)


def _reflect_point(args, ctx):
    c = args['point'].value
    cx, cy = c['x'], c['y']
    return Map(lambda x, y: (2 * cx - x, 2 * cy - y), lambda dx, dy: (-dx, -dy), 1.0, lambda t: t + math.pi,
               False)


def _dilate(args, ctx):
    k = args['factor'].value['value']
    tol_s = ctx.tol.decide_scalar
    ctx.decide('invalid_parameter', k, tol_s)
    if abs(k) <= tol_s:
        return Undefined('invalid_parameter')
    c = args['center'].value
    cx, cy = c['x'], c['y']
    if k > 0:
        return Map(lambda x, y: (cx + k * (x - cx), cy + k * (y - cy)), lambda dx, dy: (dx, dy), k,
                   lambda t: t, False)
    return Map(lambda x, y: (cx + k * (x - cx), cy + k * (y - cy)), lambda dx, dy: (-dx, -dy), -k,
               lambda t: t + math.pi, False)


def reduce_angle(t: float) -> float:
    """``t`` reduced into ``[0, 2 pi)``: ``t − 2π·floor(t / 2π)``, ``2π`` gives ``0``, ``−0`` gives ``0``."""
    t = t - TWO_PI * math.floor(t / TWO_PI)
    if t >= TWO_PI:
        t = 0.0
    return t + 0.0


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def image(type_: str, v: dict, m: Map) -> dict:
    """The image of the value ``v`` of type ``type_`` (one output dict)."""
    if type_ == 'point':
        x, y = m.point(v['x'], v['y'])
        return {'image': {'x': x, 'y': y}}
    if type_ in ('segment', 'vector'):
        ax, ay = m.point(*v['a'])
        bx, by = m.point(*v['b'])
        return {'image': {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}}
    if type_ == 'ray':
        ox, oy = m.point(*v['origin'])
        dx, dy = _unit(*m.direction(*v['dir']))
        return {'image': {'origin': [ox, oy], 'dir': [dx, dy]}}
    if type_ == 'line':
        qx, qy = m.point(*v['p'])
        dx, dy = _unit(*m.direction(*v['dir']))
        return {'image': line_through(qx, qy, dx, dy)}
    if type_ == 'circle':
        cx, cy = m.point(*v['c'])
        return {'image': {'c': [cx, cy], 'r': v['r'] * m.scale}}
    if type_ in ('arc', 'sector'):
        cx, cy = m.point(*v['c'])
        sweep = v['a1'] - v['a0']
        a0 = reduce_angle(m.turn(v['a1'] if m.reverses else v['a0']))
        return {'image': {'c': [cx, cy], 'r': v['r'] * m.scale, 'a0': a0, 'a1': a0 + sweep}}
    if type_ == 'polygon':
        pts = [m.point(x, y) for x, y in v['vertices']]
        out = polygon_parts(pts)
        out['image'] = out.pop('polygon')
        for k, (x, y) in enumerate(pts, start=1):
            out[f'vertex.{k}'] = {'x': x, 'y': y}
        return out
    raise ValueError(f'{type_!r} is not transformable')


def _undefined(obj, reason) -> dict:
    out = {'image': reason}
    if obj.type == 'polygon':
        n = len(obj.value['vertices'])
        for k in range(1, n + 1):
            out[f'side.{k}'] = reason
            out[f'vertex.{k}'] = reason
    return out


def _run(make):
    def run(args, ctx):
        m = make(args, ctx)
        obj = args['obj']
        if isinstance(m, Undefined):
            return _undefined(obj, m)
        return image(obj.type, obj.value, m)
    return run


MAPS = {
    'transform.translate': _translate,
    'transform.rotate': _rotate,
    'transform.reflect_line': _reflect_line,
    'transform.reflect_point': _reflect_point,
    'transform.dilate': _dilate,
}

for _name, _make in MAPS.items():
    op(_name)(_run(_make))
