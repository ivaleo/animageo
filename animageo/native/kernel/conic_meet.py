"""Common points of two conics and of a graph and a conic (registry 1.8;
docs/native/ops/intersect.conic_conic.md, intersect.function_conic.md).

A *curve* is a conic value or a circle (an arc is its carrier circle):
:func:`curve_of` gives ``{kind, o, u, n, a, b, p, round}`` — ``o`` the
centre (the vertex of a parabola), ``u`` the unit axis, ``n`` the axis
turned by +90°; a circle is the ellipse ``a = b = r`` with ``u = (1, 0)``.

The canonical equation of a curve in lengths² (as
:func:`..conic.line_params`), with ``U = (X − o)·u``, ``V = (X − o)·n``:
ellipse ``G = U² + (a/b)²·V² − a²``, hyperbola ``G = U² − (a/b)²·V² − a²``,
parabola ``G = V² − 2p·U``. ``unit`` is ``2a`` (``2p``), and
:func:`measure` ``= G/unit`` is a length near the curve (the distance to it
to first order): the decision value of a tangency.

Two curves: one of them, the *param curve*, is written by a rational
parameter, and ``G`` of the other along it is a polynomial of degree four
at most whose real roots :func:`_roots` finds (:mod:`.poly`). The param
curve is the first input when it is an ellipse (or a circle), else the
second when that is one, else the first; a hyperbola or a parabola as the
param curve is searched only near the window ``B4`` (:func:`_window_radius`).
"""
from __future__ import annotations

import math

from . import poly
from .conic import normal
from .function import bisect
from .numeric import default_bounds

__all__ = ['ELLIPSE_DIRECTIONS', 'HYPERBOLA_SAMPLES', 'PARABOLA_SAMPLES', 'curve_equation', 'curve_meet',
           'curve_of', 'measure', 'order_key']

H = math.sqrt(0.5)          # Math.SQRT1_2
# Directions (cos, sin) on an ellipse: the samples of coincidence and the candidates of the chart's infinity.
ELLIPSE_DIRECTIONS = ((1.0, 0.0), (H, H), (0.0, 1.0), (-H, H), (-1.0, 0.0), (-H, -H), (0.0, -1.0), (H, -H))
PARABOLA_SAMPLES = (-2.0, -1.0, 0.0, 1.0, 2.0)                                            # t
HYPERBOLA_SAMPLES = ((1.0, 0.5), (1.0, 1.0), (1.0, 2.0), (-1.0, 1.0), (-1.0, 2.0))        # (branch, w)
TWO_PI = 2 * math.pi


def curve_of(inp) -> dict:
    """``{kind, o, u, n, a, b, p, round}`` of a ``conic``, ``circle`` or ``arc`` input."""
    v = inp.value
    if inp.type in ('circle', 'arc'):
        r = float(v['r'])
        return {'kind': 'ellipse', 'o': (float(v['c'][0]), float(v['c'][1])), 'u': (1.0, 0.0), 'n': (0.0, 1.0),
                'a': r, 'b': r, 'p': None, 'round': True}
    u = (float(v['axis'][0]), float(v['axis'][1]))
    if v['kind'] == 'parabola':
        return {'kind': 'parabola', 'o': (float(v['vertex'][0]), float(v['vertex'][1])), 'u': u, 'n': normal(u),
                'a': None, 'b': None, 'p': float(v['p']), 'round': False}
    return {'kind': v['kind'], 'o': (float(v['c'][0]), float(v['c'][1])), 'u': u, 'n': normal(u),
            'a': float(v['a']), 'b': float(v['b']), 'p': None, 'round': v['kind'] == 'ellipse' and v['a'] == v['b']}


def _coefficient(curve) -> float:
    """``k`` of ``U² + k·V² − a²``: ``(a/b)²`` for an ellipse, ``−(a/b)²`` for a hyperbola."""
    r = curve['a'] / curve['b']
    return r * r if curve['kind'] == 'ellipse' else -(r * r)


def curve_equation(curve):
    """``(G(U, V), unit)``: the canonical equation in the frame of the curve and its unit."""
    if curve['kind'] == 'parabola':
        p = curve['p']
        return (lambda U, V: V * V - 2 * p * U), 2 * p
    k = _coefficient(curve)
    a2 = curve['a'] * curve['a']
    return (lambda U, V: U * U + k * (V * V) - a2), 2 * curve['a']


def measure(curve, x: float, y: float) -> float:
    """``G(X)/unit`` of the point ``(x, y)`` (module docstring)."""
    g, unit = curve_equation(curve)
    dx = x - curve['o'][0]
    dy = y - curve['o'][1]
    U = dx * curve['u'][0] + dy * curve['u'][1]
    V = dx * curve['n'][0] + dy * curve['n'][1]
    return g(U, V) / unit


class _Relative:
    """The equation of ``other`` in the frame of ``param``: for the local
    coordinates ``(x', y')`` of ``param`` (``X = o + x'·u + y'·n``),
    ``U = U0 + x'·Ux + y'·Uy`` and ``V = V0 + x'·Vx + y'·Vy`` in the frame of
    ``other``; the centres are subtracted first."""

    def __init__(self, param, other):
        dx = param['o'][0] - other['o'][0]
        dy = param['o'][1] - other['o'][1]
        uo, no = other['u'], other['n']
        up, np_ = param['u'], param['n']
        self.U0 = dx * uo[0] + dy * uo[1]
        self.V0 = dx * no[0] + dy * no[1]
        self.Ux = up[0] * uo[0] + up[1] * uo[1]
        self.Uy = np_[0] * uo[0] + np_[1] * uo[1]
        self.Vx = up[0] * no[0] + up[1] * no[1]
        self.Vy = np_[0] * no[0] + np_[1] * no[1]
        self.g, self.unit = curve_equation(other)
        self.other = other

    def measure(self, x: float, y: float) -> float:
        """``G/unit`` of ``other`` at the local point ``(x', y')`` of the param curve."""
        U = self.U0 + x * self.Ux + y * self.Uy
        V = self.V0 + x * self.Vx + y * self.Vy
        return self.g(U, V) / self.unit

    def polynomial(self, xh, yh, wh) -> list:
        """``G`` along the homogeneous local point ``(xh, yh, wh)`` (polynomials in
        the parameter), times ``wh²``: ``Uh = U0·wh + Ux·xh + Uy·yh``, ``Vh`` alike;
        an ellipse or a hyperbola gives ``Uh² + k·Vh² − a²·wh²``, a parabola
        ``Vh² − 2p·Uh·wh``."""
        uh = poly.add(poly.scale(self.U0, wh), poly.scale(self.Ux, xh), poly.scale(self.Uy, yh))
        vh = poly.add(poly.scale(self.V0, wh), poly.scale(self.Vx, xh), poly.scale(self.Vy, yh))
        other = self.other
        if other['kind'] == 'parabola':
            return poly.add(poly.mul(vh, vh), poly.scale(-2 * other['p'], poly.mul(uh, wh)))
        a2 = other['a'] * other['a']
        return poly.add(poly.mul(uh, uh), poly.scale(_coefficient(other), poly.mul(vh, vh)),
                        poly.scale(-a2, poly.mul(wh, wh)))


def _world(curve, x: float, y: float) -> dict:
    o, u, n = curve['o'], curve['u'], curve['n']
    return {'x': o[0] + x * u[0] + y * n[0], 'y': o[1] + x * u[1] + y * n[1]}


def _roots(P, lo, hi, measure_at, ctx) -> list:
    """``[(t, multiplicity)]`` of the polynomial ``P`` on ``[lo, hi]``, ascending.

    The breakpoints are ``lo``, the extrema of ``P`` inside (the sign-change
    roots of ``P'``, :func:`.poly.sign_roots`) and ``hi``. An extremum whose
    ``measure_at`` is within ``tol.decide`` (decision ``tangent``) is a root
    of multiplicity 2 and its value counts as ``0``; ``lo`` or ``hi`` where
    ``P`` is exactly ``0`` is a simple root; between two breakpoints whose
    values are nonzero and of opposite signs a simple root is bisected
    (:func:`~.function.bisect`)."""
    tol = ctx.tol.decide_length
    P = poly.trim(P)
    if len(P) == 1:
        return []
    breaks = [lo] + poly.sign_roots(poly.derivative(P), lo, hi) + [hi]
    values = [poly.value(P, t) for t in breaks]
    found = []
    for k in range(1, len(breaks) - 1):
        m = measure_at(breaks[k])
        ctx.decide('tangent', m, tol)
        if abs(m) <= tol:
            values[k] = 0.0
            found.append((breaks[k], 2))
    if values[0] == 0.0:
        found.append((lo, 1))
    if values[-1] == 0.0:
        found.append((hi, 1))
    for k in range(len(breaks) - 1):
        v0 = values[k]
        v1 = values[k + 1]
        if v0 != 0.0 and v1 != 0.0 and (v0 < 0.0) != (v1 < 0.0):
            t, _ = bisect(lambda s: poly.value(P, s), breaks[k], breaks[k + 1], v0, v1)
            found.append((t, 1))
    found.sort(key=lambda item: item[0])
    return found


def _window_radius(curve, ctx) -> float:
    """``R + |o − Z|``: ``Z`` the centre of the window ``B4`` of the bounds, ``R``
    its half-diagonal — every point of ``B4`` is within it of ``o``."""
    from .ops.locus import window
    x0, y0, x1, y1 = window(ctx.bounds or default_bounds())
    zx = (x0 + x1) / 2
    zy = (y0 + y1) / 2
    return math.hypot(x1 - x0, y1 - y0) / 2 + math.hypot(curve['o'][0] - zx, curve['o'][1] - zy)


def _coincide(samples, ctx) -> bool:
    worst = max(abs(m) for m in samples)
    tol = ctx.tol.decide_length
    ctx.decide('same_curve', worst, tol)
    return worst <= tol


def _ellipse_meet(param, rel, ctx):
    """The chart ``θ = θc + 2·atan t`` of the ellipse ``(a cos θ, b sin θ)``: its
    infinity is the direction of :data:`ELLIPSE_DIRECTIONS` where ``|G/unit|``
    of the other curve is the largest (the first on a tie), so no root lies
    there; ``(cos θc, sin θc)`` is the opposite direction ``(c0, s0)`` and
    ``(cos θ, sin θ) = (c0(1 − t²) − 2·s0·t, s0(1 − t²) + 2·c0·t)/(1 + t²)``.
    Roots lie inside ``|t| < 1 + max |Pᵢ/P₄|`` (Cauchy)."""
    a, b = param['a'], param['b']
    samples = [rel.measure(a * cx, b * sy) for cx, sy in ELLIPSE_DIRECTIONS]
    if _coincide(samples, ctx):
        return None
    best = 0
    for k in range(1, len(samples)):
        if abs(samples[k]) > abs(samples[best]):
            best = k
    c0 = -ELLIPSE_DIRECTIONS[best][0]
    s0 = -ELLIPSE_DIRECTIONS[best][1]
    P = poly.trim(rel.polynomial([a * c0, -2 * a * s0, -a * c0], [b * s0, 2 * b * c0, -b * s0], [1.0, 0.0, 1.0]))

    def local(t):
        w = 1 + t * t
        q = 1 - t * t
        return a * (c0 * q - 2 * s0 * t) / w, b * (s0 * q + 2 * c0 * t) / w

    n = len(P) - 1
    if n == 0:
        return []
    bound = 1.0
    for i in range(n):
        bound = max(bound, 1.0 + abs(P[i] / P[n]))
    found = _roots(P, -bound, bound, lambda t: rel.measure(*local(t)), ctx)
    return [(_world(param, *local(t)), mult) for t, mult in found]


def _parabola_meet(param, rel, ctx):
    """The parabola ``(p·t²/2, p·t)`` for ``|t| ≤ T = √(2·R'/p)``, ``R'`` of :func:`_window_radius`."""
    p = param['p']
    if _coincide([rel.measure(p * t * t / 2, p * t) for t in PARABOLA_SAMPLES], ctx):
        return None
    T = math.sqrt(2 * _window_radius(param, ctx) / p)
    P = rel.polynomial([0.0, 0.0, p / 2], [0.0, p], [1.0])
    found = _roots(P, -T, T, lambda t: rel.measure(p * t * t / 2, p * t), ctx)
    return [(_world(param, p * t * t / 2, p * t), mult) for t, mult in found]


def _hyperbola_meet(param, rel, ctx):
    """Each branch ``σ = −1, +1``: ``(σ·a(w + 1/w)/2, b(w − 1/w)/2)``, ``w = e^t``,
    for ``1/W ≤ w ≤ W``, ``W = q + √((q − 1)(q + 1))``, ``q = R'/a`` (no point
    of the branch within ``R'`` of the centre when ``q ≤ 1``)."""
    a, b = param['a'], param['b']

    def local(sign, w):
        return sign * a * (w + 1 / w) / 2, b * (w - 1 / w) / 2
    if _coincide([rel.measure(*local(sign, w)) for sign, w in HYPERBOLA_SAMPLES], ctx):
        return None
    q = _window_radius(param, ctx) / a
    if q <= 1.0:
        return []
    W = q + math.sqrt((q - 1) * (q + 1))
    out = []
    for sign in (-1.0, 1.0):
        P = rel.polynomial([sign * a / 2, 0.0, sign * a / 2], [-b / 2, 0.0, b / 2], [0.0, 1.0])
        found = _roots(P, 1 / W, W, lambda w, s=sign: rel.measure(*local(s, w)), ctx)
        out.extend((_world(param, *local(sign, w)), mult) for w, mult in found)
    return out


def curve_meet(first, second, ctx):
    """The common points of two curves (:func:`curve_of`): ``None`` when they
    coincide, else ``[(point, multiplicity)]`` in the order of the param curve."""
    if first['kind'] == 'ellipse':
        param, other = first, second
    elif second['kind'] == 'ellipse':
        param, other = second, first
    else:
        param, other = first, second
    rel = _Relative(param, other)
    if param['kind'] == 'ellipse':
        return _ellipse_meet(param, rel, ctx)
    if param['kind'] == 'parabola':
        return _parabola_meet(param, rel, ctx)
    return _hyperbola_meet(param, rel, ctx)


def _direction(x: float, y: float) -> float:
    """``atan2`` in ``[0, 2π)`` (``_types.json → angles``)."""
    theta = math.atan2(y, x)
    if theta < 0:
        theta = theta + TWO_PI
    if theta >= TWO_PI:
        theta = 0.0
    return theta


def order_key(first_inp, first, second, ctx):
    """``key(point) -> (group, value)``: the order of the slots on the first
    input (policy ``first_curve_order``, docs/native/ops/intersect.conic_conic.md)."""
    tol = ctx.tol.decide_length
    if first_inp.type == 'arc':
        v = first_inp.value
        cx, cy, r, a0 = float(v['c'][0]), float(v['c'][1]), float(v['r']), float(v['a0'])

        def arc_key(pt):
            phi = _direction(pt['x'] - cx, pt['y'] - cy) - a0
            if phi < 0:
                phi = phi + TWO_PI
            ctx.decide('seam', r * (TWO_PI - phi), tol)
            if r * (TWO_PI - phi) <= tol:
                phi = 0.0
            return 0, phi
        return arc_key
    ox, oy = first['o']
    if first['kind'] == 'ellipse':
        dx = second['o'][0] - ox
        dy = second['o'][1] - oy
        dist = math.hypot(dx, dy)
        ctx.decide('same_centre', dist, tol)
        if dist <= tol:
            dx, dy = second['u'] if first['round'] else first['u']
        else:
            dx, dy = dx / dist, dy / dist

        def central_key(pt):
            rx = pt['x'] - ox
            ry = pt['y'] - oy
            along = dx * rx + dy * ry
            across = dx * ry - dy * rx
            if along > 0:
                ctx.decide('seam', across, tol)
                if abs(across) <= tol:
                    return 0, 0.0
            return 0, _direction(along, across)
        return central_key
    ux, uy = first['u']
    nx, ny = first['n']

    def frame_key(pt):
        rx = pt['x'] - ox
        ry = pt['y'] - oy
        group = 1 if first['kind'] == 'hyperbola' and rx * ux + ry * uy > 0 else 0
        return group, rx * nx + ry * ny
    return frame_key
