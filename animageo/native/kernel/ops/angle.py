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
