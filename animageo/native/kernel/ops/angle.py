"""``angle.by_points`` (docs/native/ops/angle.by_points.md) and the angle helpers of registry 1.3.

Angles are radians. A direction is normalised to ``[0, 2 pi)``
(``_types.json → angles``): ``theta = atan2(y, x)``, ``theta < 0`` gives
``theta + 2 pi``, ``theta >= 2 pi`` gives ``0``, ``-0`` gives ``0``.
"""
from __future__ import annotations

import math

from ..values import Undefined
from . import op

TWO_PI = 2 * math.pi


def normalize_angle(theta: float) -> float:
    """``theta`` in ``[0, 2 pi)``; ``-0`` becomes ``0``."""
    if theta < 0:
        theta = theta + TWO_PI
    if theta >= TWO_PI:
        theta = 0.0
    return theta + 0.0


def convex_measure(size: float) -> float:
    """The convex measure of an angle: ``size`` up to ``pi``, else ``2 pi - size``."""
    return size if size <= math.pi else TWO_PI - size


def wrap_angle(d: float) -> float:
    """A difference of directions in ``[-pi, pi)``."""
    return d - TWO_PI * math.floor((d + math.pi) / TWO_PI)


def unit_sides(a: dict, vertex: dict, b: dict, ctx):
    """``((uax, uay), (ubx, uby))`` — the unit sides from the vertex to ``a`` and
    to ``b``, or ``Undefined("coincident_points")`` when a side has no length."""
    vx, vy = vertex['x'], vertex['y']
    wax = a['x'] - vx
    way = a['y'] - vy
    wbx = b['x'] - vx
    wby = b['y'] - vy
    la = math.hypot(wax, way)
    lb = math.hypot(wbx, wby)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', la, tol)
    ctx.decide('coincident_points', lb, tol)
    if la <= tol or lb <= tol:
        return Undefined('coincident_points')
    return (wax / la, way / la), (wbx / lb, wby / lb)


def angle_size(ua, ub) -> float:
    """The counterclockwise size from the unit side ``ua`` to ``ub`` in ``[0, 2 pi)``."""
    cr = ua[0] * ub[1] - ua[1] * ub[0]
    q = ua[0] * ub[0] + ua[1] * ub[1]
    return normalize_angle(math.atan2(cr, q))


@op('angle.by_points')
def by_points(args, ctx):
    vertex = args['vertex'].value
    sides = unit_sides(args['a'].value, vertex, args['b'].value, ctx)
    if isinstance(sides, Undefined):
        return {'angle': sides}
    (uax, uay), (ubx, uby) = sides
    tol_s = ctx.tol.decide_scalar
    if uax > 0:
        ctx.decide('angle_wrap', uay, tol_s)        # a0 jumps between 0 and 2 pi
    a0 = normalize_angle(math.atan2(uay, uax))
    cr = uax * uby - uay * ubx
    q = uax * ubx + uay * uby
    if q > 0:
        ctx.decide('zero_angle', cr, tol_s)         # size jumps between 0 and 2 pi
    size = normalize_angle(math.atan2(cr, q))
    return {'angle': {'vertex': [vertex['x'], vertex['y']], 'a0': a0, 'a1': a0 + size, 'size': size}}


# ── registry 1.4 (1.8.1a5) ───────────────────────────────────────────────

def _angle_value(vx: float, vy: float, ux: float, uy: float, size: float, ctx) -> dict:
    """The angle at ``(vx, vy)`` whose first side runs along the unit ``u``."""
    if ux > 0:
        ctx.decide('angle_wrap', uy, ctx.tol.decide_scalar)     # a0 jumps between 0 and 2 pi
    a0 = normalize_angle(math.atan2(uy, ux))
    return {'vertex': [vx, vy], 'a0': a0, 'a1': a0 + size, 'size': size}


@op('angle.between_lines')
def between_lines(args, ctx):
    from .intersect import carrier
    c1 = carrier(args['first'], ctx)
    if isinstance(c1, Undefined):
        return {'angle': c1}
    c2 = carrier(args['second'], ctx)
    if isinstance(c2, Undefined):
        return {'angle': c2}
    tol_s = ctx.tol.decide_scalar
    cross = c1.dx * c2.dy - c1.dy * c2.dx
    ctx.decide('parallel', cross, tol_s)
    wx = c2.px - c1.px
    wy = c2.py - c1.py
    if abs(cross) <= tol_s:
        dist = abs(wx * c1.dy - wy * c1.dx)
        tol = ctx.tol.decide_length
        ctx.decide('coincident', dist, tol)
        return {'angle': Undefined('coincident' if dist <= tol else 'parallel')}
    t = (wx * c2.dy - wy * c2.dx) / cross
    vx = c1.px + t * c1.dx
    vy = c1.py + t * c1.dy
    q = c1.dx * c2.dx + c1.dy * c2.dy
    size = normalize_angle(math.atan2(abs(cross), q))
    if cross > 0:
        return {'angle': _angle_value(vx, vy, c1.dx, c1.dy, size, ctx)}
    return {'angle': _angle_value(vx, vy, c2.dx, c2.dy, size, ctx)}


def _unit_vector(value: dict, ctx):
    ax, ay = value['a']
    bx, by = value['b']
    dx = bx - ax
    dy = by - ay
    length = math.hypot(dx, dy)
    tol = ctx.tol.decide_length
    ctx.decide('zero_length', length, tol)
    if length <= tol:
        return Undefined('zero_length')
    return dx / length, dy / length


@op('angle.between_vectors')
def between_vectors(args, ctx):
    first = args['first'].value
    u = _unit_vector(first, ctx)
    if isinstance(u, Undefined):
        return {'angle': u}
    w = _unit_vector(args['second'].value, ctx)
    if isinstance(w, Undefined):
        return {'angle': w}
    cr = u[0] * w[1] - u[1] * w[0]
    q = u[0] * w[0] + u[1] * w[1]
    if q > 0:
        ctx.decide('zero_angle', cr, ctx.tol.decide_scalar)     # size jumps between 0 and 2 pi
    size = normalize_angle(math.atan2(cr, q))
    return {'angle': _angle_value(first['a'][0], first['a'][1], u[0], u[1], size, ctx)}


@op('angle.by_size')
def by_size(args, ctx):
    v = args['vertex'].value
    a = args['a'].value
    vx, vy = v['x'], v['y']
    wx = a['x'] - vx
    wy = a['y'] - vy
    length = math.hypot(wx, wy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', length, tol)
    if length <= tol:
        undefined = Undefined('coincident_points')
        return {'angle': undefined, 'point': undefined}
    alpha = args['size'].value['value']
    c = math.cos(alpha)
    s = math.sin(alpha)
    px = vx + (c * wx - s * wy)
    py = vy + (s * wx + c * wy)
    ctx.decide('zero_angle', wrap_angle(alpha), ctx.tol.decide_scalar)   # size jumps between 0 and 2 pi
    if alpha >= 0:
        fx, fy, m = wx, wy, alpha
    else:
        fx, fy, m = px - vx, py - vy, -alpha
    m = m - TWO_PI * math.floor(m / TWO_PI)
    if m >= TWO_PI:
        m = 0.0
    lf = math.hypot(fx, fy)
    return {'angle': _angle_value(vx, vy, fx / lf, fy / lf, m, ctx), 'point': {'x': px, 'y': py}}
