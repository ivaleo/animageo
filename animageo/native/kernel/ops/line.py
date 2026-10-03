"""Lines, rays, segments and vectors (docs/native/ops/*.md):
``segment.by_points``, ``line.by_points``, ``ray.by_points``, ``line.parallel``,
``line.perpendicular``, ``line.perpendicular_bisector``, ``line.angle_bisector``,
``vector.by_points``."""
from __future__ import annotations

import math

from ..values import Undefined
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


@op('line.angle_bisector')
def angle_bisector(args, ctx):
    a = args['a'].value
    v = args['vertex'].value
    b = args['b'].value
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
        return {'line': Undefined('coincident_points')}
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
    return {'line': line_through(vx, vy, dx, dy)}


@op('vector.by_points')
def vector(args, ctx):
    a = args['a'].value
    b = args['b'].value
    ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
    return {'vector': {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}}
