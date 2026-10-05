"""Lines, rays, segments and vectors (docs/native/ops/*.md):
``segment.by_points``, ``line.by_points``, ``ray.by_points``, ``line.parallel``,
``line.perpendicular``, ``line.perpendicular_bisector``, ``line.angle_bisector``,
``vector.by_points``; registry 1.4: ``line.angle_bisectors_of_lines``,
``line.external_bisector``, ``ray.at_angle``, ``ray.by_vector``,
``line.tangents_from_point``, ``line.tangent_at``, ``segment.from_point_length``,
``segment.midline``."""
from __future__ import annotations

import math

from ..values import Detailed, Undefined
from . import op
from .intersect import carrier


def line_through(qx: float, qy: float, dx: float, dy: float) -> dict:
    """The line through ``(qx, qy)`` with unit direction ``(dx, dy)``:
    ``k = q·d``, ``p = q − k·d``."""
    k = qx * dx + qy * dy
    return {'p': [qx - k * dx, qy - k * dy], 'dir': [dx, dy]}


@op('segment.by_points')
def segment(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
    return {'segment': {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}}


@op('line.by_points')
def line(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay = a['x'], a['y']
    dx = b['x'] - ax
    dy = b['y'] - ay
    length = math.hypot(dx, dy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return {'line': Undefined('coincident_points')}
    dirx = dx / length
    diry = dy / length
    k = ax * dirx + ay * diry
    return {'line': {'p': [ax - k * dirx, ay - k * diry], 'dir': [dirx, diry]}}


@op('ray.by_points')
def ray(args, ctx):
    o = args['origin'].value
    t = args['through'].value
    ox, oy = o['x'], o['y']
    dx = t['x'] - ox
    dy = t['y'] - oy
    length = math.hypot(dx, dy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return {'ray': Undefined('coincident_points')}
    return {'ray': {'origin': [ox, oy], 'dir': [dx / length, dy / length]}}


@op('line.parallel')
def parallel(args, ctx):
    c = carrier(args['base'], ctx)
    if isinstance(c, Undefined):
        return {'line': c}
    p = args['point'].value
    return {'line': line_through(p['x'], p['y'], c.dx, c.dy)}


@op('line.perpendicular')
def perpendicular(args, ctx):
    c = carrier(args['base'], ctx)
    if isinstance(c, Undefined):
        return {'line': c}
    p = args['point'].value
    return {'line': line_through(p['x'], p['y'], -c.dy, c.dx)}


@op('line.perpendicular_bisector')
def perpendicular_bisector(args, ctx):
    a = args['a'].value
    b = args['b'].value
    vx = b['x'] - a['x']
    vy = b['y'] - a['y']
    length = math.hypot(vx, vy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        return {'line': Undefined('coincident_points')}
    ux = vx / length
    uy = vy / length
    mx = (a['x'] + b['x']) / 2
    my = (a['y'] + b['y']) / 2
    return {'line': line_through(mx, my, -uy, ux)}


def bisector_direction(a: dict, v: dict, b: dict, ctx):
    """The unit direction of ``line.angle_bisector`` (into the convex angle; a
    straight angle gives the first side turned by +90°), or
    ``Undefined("coincident_points")``."""
    vx, vy = v['x'], v['y']
    ax = a['x'] - vx
    ay = a['y'] - vy
    bx = b['x'] - vx
    by = b['y'] - vy
    la = math.hypot(ax, ay)
    lb = math.hypot(bx, by)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', la, tol)
    ctx.decide('coincident_points', lb, tol)
    if la <= tol or lb <= tol:
        return Undefined('coincident_points')
    uax = ax / la
    uay = ay / la
    ubx = bx / lb
    uby = by / lb
    q = uax * ubx + uay * uby
    if q >= 0:
        sx = uax + ubx
        sy = uay + uby
        n = math.hypot(sx, sy)
        dx = sx / n
        dy = sy / n
    else:
        wx = ubx - uax
        wy = uby - uay
        n = math.hypot(wx, wy)
        cr = uax * uby - uay * ubx
        tol_s = ctx.tol.decide_scalar
        ctx.decide('straight_angle', cr, tol_s)
        sigma = -1.0 if cr < -tol_s else 1.0
        dx = sigma * wy / n
        dy = -sigma * wx / n
    return dx, dy


@op('line.angle_bisector')
def angle_bisector(args, ctx):
    v = args['vertex'].value
    d = bisector_direction(args['a'].value, v, args['b'].value, ctx)
    if isinstance(d, Undefined):
        return {'line': d}
    return {'line': line_through(v['x'], v['y'], d[0], d[1])}


@op('vector.by_points')
def vector(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
    return {'vector': {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}}


@op('line.angle_bisectors_of_lines')
def angle_bisectors_of_lines(args, ctx):
    c1 = carrier(args['first'], ctx)
    if isinstance(c1, Undefined):
        return {'internal': c1, 'external': c1}
    c2 = carrier(args['second'], ctx)
    if isinstance(c2, Undefined):
        return {'internal': c2, 'external': c2}
    tol = ctx.tol.decide_length
    tol_s = ctx.tol.decide_scalar
    cr = c1.dx * c2.dy - c1.dy * c2.dx
    q = c1.dx * c2.dx + c1.dy * c2.dy
    ctx.decide('parallel', cr, tol_s)
    wx = c2.px - c1.px
    wy = c2.py - c1.py
    if abs(cr) > tol_s:
        t = (wx * c2.dy - wy * c2.dx) / cr
        x = c1.px + t * c1.dx
        y = c1.py + t * c1.dy
        if q >= 0:
            sx = c1.dx + c2.dx
            sy = c1.dy + c2.dy
            n = math.hypot(sx, sy)
            ix = sx / n
            iy = sy / n
        else:
            ux = c2.dx - c1.dx
            uy = c2.dy - c1.dy
            n = math.hypot(ux, uy)
            sigma = 1.0 if cr > 0 else -1.0
            ix = sigma * uy / n
            iy = -sigma * ux / n
        return {'internal': line_through(x, y, ix, iy), 'external': line_through(x, y, -iy, ix)}
    h = wx * c1.dy - wy * c1.dx
    ctx.decide('coincident', h, tol)
    absent = Undefined('coincident' if abs(h) <= tol else 'parallel')
    # the midpoint of a point of each line lies on the midline
    mx = c1.px + wx / 2
    my = c1.py + wy / 2
    mid = line_through(mx, my, c1.dx, c1.dy)
    if q > 0:
        return {'internal': mid, 'external': absent}
    return {'internal': absent, 'external': mid}


@op('line.external_bisector')
def external_bisector(args, ctx):
    v = args['vertex'].value
    d = bisector_direction(args['a'].value, v, args['b'].value, ctx)
    if isinstance(d, Undefined):
        return {'line': d}
    return {'line': line_through(v['x'], v['y'], -d[1], d[0])}


@op('ray.at_angle')
def ray_at_angle(args, ctx):
    v = args['vertex'].value
    a = args['a'].value
    vx, vy = v['x'], v['y']
    wx = a['x'] - vx
    wy = a['y'] - vy
    length = math.hypot(wx, wy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        none = Undefined('coincident_points')
        return {'ray': none, 'point': none}
    alpha = args['size'].value['value']
    co = math.cos(alpha)
    si = math.sin(alpha)
    rx = co * wx - si * wy
    ry = si * wx + co * wy
    return {'ray': {'origin': [vx, vy], 'dir': [rx / length, ry / length]},
            'point': {'x': vx + rx, 'y': vy + ry}}


@op('ray.by_vector')
def ray_by_vector(args, ctx):
    o = args['origin'].value
    v = args['vector'].value
    vx = v['b'][0] - v['a'][0]
    vy = v['b'][1] - v['a'][1]
    length = math.hypot(vx, vy)
    tol = ctx.tol.decide_length
    ctx.decide('zero_length', length, tol)
    if length <= tol:
        return {'ray': Undefined('zero_length')}
    return {'ray': {'origin': [o['x'], o['y']], 'dir': [vx / length, vy / length]}}


TANGENT_SLOTS = ('tangent.1', 'tangent.2', 'touch.1', 'touch.2')


@op('line.tangents_from_point')
def tangents_from_point(args, ctx):
    p = args['point'].value
    circle = args['circle'].value
    px, py = p['x'], p['y']
    cx, cy = circle['c']
    r = circle['r']
    wx = px - cx
    wy = py - cy
    d2 = wx * wx + wy * wy
    d = math.sqrt(d2)
    tol = ctx.tol.decide_length
    ctx.decide('point_inside', d - r, tol)
    if d - r < -tol:
        return dict.fromkeys(TANGENT_SLOTS, Undefined('point_inside'))
    if abs(d - r) <= tol:
        ux = wx / d
        uy = wy / d
        touch = {'x': px, 'y': py}
        double = {'multiplicity': 2}
        return {
            'tangent.1': Detailed(line_through(px, py, uy, -ux), dict(double)),
            'tangent.2': Detailed(line_through(px, py, -uy, ux), dict(double)),
            'touch.1': Detailed(dict(touch), dict(double)),
            'touch.2': Detailed(dict(touch), dict(double)),
        }
    h = math.sqrt((d - r) * (d + r))
    k1 = r * r / d2
    k2 = r * h / d2
    out = {}
    for i, sign in ((1, -1.0), (2, 1.0)):
        tx = cx + k1 * wx + sign * k2 * (-wy)
        ty = cy + k1 * wy + sign * k2 * wx
        ex = tx - px
        ey = ty - py
        n = math.hypot(ex, ey)
        out[f'tangent.{i}'] = line_through(px, py, ex / n, ey / n)
        out[f'touch.{i}'] = {'x': tx, 'y': ty}
    return {slot: out[slot] for slot in TANGENT_SLOTS}


@op('line.tangent_at')
def tangent_at(args, ctx):
    p = args['point'].value
    circle = args['circle'].value
    px, py = p['x'], p['y']
    wx = px - circle['c'][0]
    wy = py - circle['c'][1]
    d = math.hypot(wx, wy)
    tol = ctx.tol.decide_length
    ctx.decide('not_on_curve', d - circle['r'], tol)
    if abs(d - circle['r']) > tol:
        return {'line': Undefined('not_on_curve')}
    return {'line': line_through(px, py, -wy / d, wx / d)}


@op('segment.from_point_length')
def from_point_length(args, ctx):
    a = args['start'].value
    ax, ay = a['x'], a['y']
    theta = float(ctx.input['value']) if ctx.input is not None else 0.0
    length = args['length'].value['value']
    tol = ctx.tol.decide_length
    ctx.decide('invalid_parameter', length, tol)
    if length < -tol:
        none = Undefined('invalid_parameter')
        return {'segment': none, 'end': none}
    if length < 0:
        length = 0.0
    ex = ax + length * math.cos(theta)
    ey = ay + length * math.sin(theta)
    return {'segment': {'a': [ax, ay], 'b': [ex, ey], 'length': length}, 'end': {'x': ex, 'y': ey}}


@op('segment.midline')
def midline(args, ctx):
    s1 = args['first'].value
    s2 = args['second'].value
    m1x = (s1['a'][0] + s1['b'][0]) / 2
    m1y = (s1['a'][1] + s1['b'][1]) / 2
    m2x = (s2['a'][0] + s2['b'][0]) / 2
    m2y = (s2['a'][1] + s2['b'][1]) / 2
    return {'segment': {'a': [m1x, m1y], 'b': [m2x, m2y], 'length': math.hypot(m2x - m1x, m2y - m1y)},
            'mid.1': {'x': m1x, 'y': m1y}, 'mid.2': {'x': m2x, 'y': m2y}}
