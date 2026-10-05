"""``polygon.by_points``; registry 1.4: ``polygon.vertex``, ``polygon.regular``,
``polygon.regular_center``, ``polygon.parallelogram``, ``polygon.centroid``,
``polyline.by_points`` (docs/native/ops/polygon.*.md, polyline.by_points.md)."""
from __future__ import annotations

import math

from ...registry import repeat_count
from ..values import Undefined
from . import op


@op('polygon.by_points')
def by_points(args, ctx):
    pts = [(v.value['x'], v.value['y']) for v in args['vertices']]
    n = len(pts)
    acc = 0.0
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[(i + 1) % n]
        acc = acc + (xi * yj - xj * yi)
    out = {'polygon': {'vertices': [[x, y] for x, y in pts], 'area': abs(acc) / 2}}
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out[f'side.{i + 1}'] = {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}
    return out


def polygon_parts(pts) -> dict:
    """``polygon``, ``side.i`` of the vertices ``pts`` (area as in ``polygon.by_points``)."""
    n = len(pts)
    acc = 0.0
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[(i + 1) % n]
        acc = acc + (xi * yj - xj * yi)
    out = {'polygon': {'vertices': [[x, y] for x, y in pts], 'area': abs(acc) / 2}}
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out[f'side.{i + 1}'] = {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}
    return out


@op('polygon.vertex')
def vertex(args, ctx):
    k = args['k']
    tol_s = ctx.tol.decide_scalar
    if k is None or abs(k - round(k)) > tol_s or k < 1:
        return {'vertex': Undefined('invalid_parameter')}
    k = int(round(k))
    of = args['of']
    if of.type == 'segment':
        vertices = [of.value['a'], of.value['b']]
    else:
        vertices = of.value['vertices']
    if k > len(vertices):
        return {'vertex': Undefined('index_out_of_range')}
    x, y = vertices[k - 1]
    return {'vertex': {'x': x, 'y': y}}


def _regular_slots(n_param, reason):
    count = repeat_count(n_param)
    out = {'polygon': Undefined(reason)}
    for i in range(1, count + 1):
        out[f'side.{i}'] = Undefined(reason)
    for i in range(1, count + 1):
        out[f'vertex.{i}'] = Undefined(reason)
    return out


def _valid_n(n, ctx) -> int | None:
    if n is None or abs(n - round(n)) > ctx.tol.decide_scalar:
        return None
    k = int(round(n))
    return k if 3 <= k <= 100 else None


def _regular(ox, oy, first, second, n):
    """Vertices ``V_k = O + R((k − 1)·2π/n)(V_1 − O)``; ``second`` overrides ``V_2``."""
    wx = first[0] - ox
    wy = first[1] - oy
    pts = [first]
    for k in range(2, n + 1):
        if k == 2 and second is not None:
            pts.append(second)
            continue
        phi = (k - 1) * 2 * math.pi / n
        co = math.cos(phi)
        si = math.sin(phi)
        pts.append((ox + co * wx - si * wy, oy + si * wx + co * wy))
    return pts


def _with_vertices(pts) -> dict:
    out = polygon_parts(pts)
    for i, (x, y) in enumerate(pts, start=1):
        out[f'vertex.{i}'] = {'x': x, 'y': y}
    return out


@op('polygon.regular')
def regular(args, ctx):
    n = _valid_n(args['n'], ctx)
    if n is None:
        return _regular_slots(args['n'], 'invalid_parameter')
    a = args['a'].value
    b = args['b'].value
    ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
    vx = bx - ax
    vy = by - ay
    length = math.hypot(vx, vy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return _regular_slots(args['n'], 'coincident_points')
    h = length / (2 * math.tan(math.pi / n))
    ox = (ax + bx) / 2 + h * (-vy / length)
    oy = (ay + by) / 2 + h * (vx / length)
    return _with_vertices(_regular(ox, oy, (ax, ay), (bx, by), n))


@op('polygon.regular_center')
def regular_center(args, ctx):
    n = _valid_n(args['n'], ctx)
    if n is None:
        return _regular_slots(args['n'], 'invalid_parameter')
    o = args['center'].value
    a = args['a'].value
    ox, oy = o['x'], o['y']
    length = math.hypot(a['x'] - ox, a['y'] - oy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return _regular_slots(args['n'], 'coincident_points')
    return _with_vertices(_regular(ox, oy, (a['x'], a['y']), None, n))


@op('polygon.parallelogram')
def parallelogram(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    dx = a['x'] + c['x'] - b['x']
    dy = a['y'] + c['y'] - b['y']
    out = polygon_parts([(a['x'], a['y']), (b['x'], b['y']), (c['x'], c['y']), (dx, dy)])
    out['vertex'] = {'x': dx, 'y': dy}
    return out


@op('polygon.centroid')
def centroid(args, ctx):
    vs = args['polygon'].value['vertices']
    x0, y0 = vs[0]
    n = len(vs)
    a2 = 0.0
    sx = 0.0
    sy = 0.0
    for i in range(1, n - 1):
        ux = vs[i][0] - x0
        uy = vs[i][1] - y0
        wx = vs[i + 1][0] - x0
        wy = vs[i + 1][1] - y0
        cr = ux * wy - uy * wx
        a2 = a2 + cr
        sx = sx + (ux + wx) * cr
        sy = sy + (uy + wy) * cr
    perimeter = sum(math.hypot(vs[(i + 1) % n][0] - vs[i][0], vs[(i + 1) % n][1] - vs[i][1]) for i in range(n))
    tol = ctx.tol.decide_length
    h = abs(a2) / perimeter if perimeter > 0 else 0.0
    ctx.decide('collinear_points', h, tol)
    if h <= tol:
        return {'centroid': Undefined('collinear_points')}
    return {'centroid': {'x': x0 + sx / (3 * a2), 'y': y0 + sy / (3 * a2)}}


@op('polyline.by_points')
def polyline(args, ctx):
    pts = [(v.value['x'], v.value['y']) for v in args['points']]
    length = 0.0
    for i in range(len(pts) - 1):
        length = length + math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    return {'polyline': {'vertices': [[x, y] for x, y in pts], 'length': length}}
