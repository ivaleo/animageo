"""Path parameters (``ops/v1/_types.json`` → ``paths``; docs/native/ops/point.on_path.md).

A point on a path is ``P(t)`` in the frame of the path element:

- ``affine`` (segment, line, ray): ``P = o + t'·v``, ``t' = t`` clamped to
  ``[min, max]`` when ``outside`` is ``clamp``; ``o`` and ``v`` come from
  ``frames[<producer op>]``, else ``frames["*"]``: a line through ``a`` and
  ``b`` has ``o = a``, ``v = b − a``, so the point moves with ``a`` and ``b``;
  a perpendicular bisector has ``o = mid(a, b)``, ``v = dir``;
- ``angle`` (circle): ``P = c + r·(cos t, sin t)``;
- ``perimeter`` (polygon, ``n`` vertices ``V``): ``t' = t − n·floor(t/n)``,
  ``t' < 0 → t' + n``, ``t' ≥ n → 0``; ``k = floor(t')``, ``f = t' − k``,
  ``P = V[k] + f·(V[(k+1) mod n] − V[k])``.

- ``arc`` (arc): ``t' = clamp(t, 0, 1)``, ``φ = a0 + t'(a1 − a0)``,
  ``P = c + r·(cos φ, sin φ)``;
- ``sector`` (sector): ``t`` wraps to ``[0, 3)``; ``[0, 1]`` is the arc,
  ``[1, 2]`` the radius ``S1 → c``, ``[2, 3)`` the radius ``c → S0``;
- ``polyline`` (polyline, ``n`` vertices): ``t' = clamp(t, 0, n − 1)``,
  ``k = min(floor(t'), n − 2)``, ``P = V[k] + (t' − k)(V[k+1] − V[k])``.

``project`` is the inverse: the parameter of the nearest point of the path,
ties to the smallest parameter.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from ..registry import registry

__all__ = ['Frame', 'frame', 'point_at', 'project', 'distance_to_path', 'parameter_range', 'arc_fraction']

TWO_PI = 2 * math.pi


class Frame(NamedTuple):
    """The frame of a path element.

    ``kind`` ``affine``: ``origin``, ``vector``, ``lo``/``hi`` (``None`` — no
    bound); ``angle``: ``origin`` = centre, ``radius``; ``perimeter``:
    ``vertices``.
    """

    kind: str
    origin: tuple = (0.0, 0.0)
    vector: tuple = (0.0, 0.0)
    lo: float | None = None
    hi: float | None = None
    radius: float = 0.0
    vertices: tuple = ()


def _xy(value) -> tuple:
    if isinstance(value, dict):
        return (value['x'], value['y'])
    return (value[0], value[1])


def _term(expr: str, value: dict, args: dict) -> tuple:
    expr = expr.strip()
    if expr.startswith('mid(') and expr.endswith(')'):
        inner = expr[4:-1]
        depth = 0
        for i, ch in enumerate(inner):
            depth += (ch == '(') - (ch == ')')
            if ch == ',' and depth == 0:
                break
        else:
            raise ValueError(f'mid() needs two terms in frame expression {expr!r}')
        x1, y1 = _term(inner[:i], value, args)
        x2, y2 = _term(inner[i + 1:], value, args)
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    source, _, field = expr.partition('.')
    if source == 'value':
        return _xy(value[field])
    if source == 'args':
        return _xy(args[field])
    raise ValueError(f'unknown frame source {expr!r}')


def _expr(expr: str, value: dict, args: dict) -> tuple:
    """A term or ``"<term> - <term>"``; a term is ``<src>.<field>`` (``src`` is
    ``value`` or ``args``) or ``mid(<term>, <term>)``, ``((x1 + x2)/2, (y1 + y2)/2)``."""
    left, minus, right = expr.partition(' - ')
    x, y = _term(left, value, args)
    if not minus:
        return (x, y)
    rx, ry = _term(right, value, args)
    return (x - rx, y - ry)


def frame(type_: str, value: dict, producer_op: str | None = None, producer_args: dict | None = None) -> Frame:
    """The frame of a defined path element of ``type_`` with ``value``.

    ``producer_args`` maps the producer's argument slots to the values of the
    elements they reference (a list for a list slot).
    """
    spec = registry().paths.get(type_)
    if spec is None:
        raise ValueError(f'{type_!r} is not a path type')
    kind = spec['kind']
    if kind == 'affine':
        frames = spec['frames']
        rule = frames.get(producer_op) if producer_op in frames and producer_args is not None else frames['*']
        origin = _expr(rule['origin'], value, producer_args or {})
        vector = _expr(rule['vector'], value, producer_args or {})
        lo = spec['min'] if spec.get('outside') == 'clamp' else None
        hi = spec['max'] if spec.get('outside') == 'clamp' else None
        return Frame('affine', origin, vector, lo, hi)
    if kind == 'angle':
        return Frame('angle', (value['c'][0], value['c'][1]), radius=value['r'])
    if kind == 'perimeter':
        return Frame('perimeter', vertices=tuple((v[0], v[1]) for v in value['vertices']))
    if kind in ('arc', 'sector'):
        return Frame(kind, (value['c'][0], value['c'][1]), lo=value['a0'], hi=value['a1'], radius=value['r'])
    if kind == 'polyline':
        return Frame('polyline', vertices=tuple((v[0], v[1]) for v in value['vertices']))
    raise ValueError(f'unknown path kind {kind!r}')


def _clamp(t: float, lo, hi) -> float:
    if lo is not None and t < lo:
        return float(lo)
    if hi is not None and t > hi:
        return float(hi)
    return t


def _wrap(t: float, n: int) -> float:
    w = t - n * math.floor(t / n)
    if w < 0:
        w += n
    if w >= n:
        w = 0.0
    return w


def _arc_xy(f: Frame, frac: float) -> tuple:
    phi = f.lo + frac * (f.hi - f.lo)
    return (f.origin[0] + f.radius * math.cos(phi), f.origin[1] + f.radius * math.sin(phi))


def _sector_ends(f: Frame) -> tuple:
    return _arc_xy(f, 0.0), _arc_xy(f, 1.0)


def parameter_range(f: Frame) -> tuple:
    """``(lo, hi)`` of the parameter of frame ``f`` (``None`` — unbounded)."""
    if f.kind == 'affine':
        return f.lo, f.hi
    if f.kind == 'angle':
        return 0.0, TWO_PI
    if f.kind == 'perimeter':
        return 0.0, float(len(f.vertices))
    if f.kind == 'arc':
        return 0.0, 1.0
    if f.kind == 'sector':
        return 0.0, 3.0
    return 0.0, float(len(f.vertices) - 1)


def point_at(f: Frame, t: float) -> dict:
    """``P(t)`` as an encoded point ``{x, y}``."""
    if f.kind == 'affine':
        s = _clamp(t, f.lo, f.hi)
        return {'x': f.origin[0] + s * f.vector[0], 'y': f.origin[1] + s * f.vector[1]}
    if f.kind == 'angle':
        return {'x': f.origin[0] + f.radius * math.cos(t), 'y': f.origin[1] + f.radius * math.sin(t)}
    if f.kind == 'arc':
        x, y = _arc_xy(f, _clamp(t, 0.0, 1.0))
        return {'x': x, 'y': y}
    if f.kind == 'sector':
        w = _wrap(t, 3)
        if w <= 1:
            x, y = _arc_xy(f, w)
            return {'x': x, 'y': y}
        s0, s1 = _sector_ends(f)
        cx, cy = f.origin
        if w <= 2:
            g = w - 1
            return {'x': s1[0] + g * (cx - s1[0]), 'y': s1[1] + g * (cy - s1[1])}
        g = w - 2
        return {'x': cx + g * (s0[0] - cx), 'y': cy + g * (s0[1] - cy)}
    if f.kind == 'polyline':
        n = len(f.vertices)
        w = _clamp(t, 0.0, float(n - 1))
        k = min(math.floor(w), n - 2)
        frac = w - k
        ax, ay = f.vertices[k]
        bx, by = f.vertices[k + 1]
        return {'x': ax + frac * (bx - ax), 'y': ay + frac * (by - ay)}
    n = len(f.vertices)
    w = _wrap(t, n)
    k = math.floor(w)
    frac = w - k
    ax, ay = f.vertices[k]
    bx, by = f.vertices[(k + 1) % n]
    return {'x': ax + frac * (bx - ax), 'y': ay + frac * (by - ay)}


def _segment_param(x, y, ax, ay, bx, by) -> tuple:
    """``(f, distance)``: clamped projection of ``(x, y)`` onto ``ab``; ``f = 0`` when ``a = b``."""
    vx = bx - ax
    vy = by - ay
    vv = vx * vx + vy * vy
    f = 0.0
    if vv > 0:
        f = ((x - ax) * vx + (y - ay) * vy) / vv
        f = 0.0 if f < 0 else (1.0 if f > 1 else f)
    return f, math.hypot(x - (ax + f * vx), y - (ay + f * vy))


def arc_fraction(cx, cy, r, a0, a1, x, y, tol) -> tuple:
    """``(fraction, distance)`` of the point of the arc nearest to ``(x, y)``:
    inside the sweep the radial projection, else the nearer end (ties to the
    start); the centre and a zero sweep give the start."""
    dx = x - cx
    dy = y - cy
    d = math.hypot(dx, dy)
    sweep = a1 - a0
    sx0, sy0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    if d <= tol or sweep <= 0:
        return 0.0, (r if d <= tol else math.hypot(x - sx0, y - sy0))
    theta = math.atan2(dy, dx)
    if theta < 0:
        theta += TWO_PI
    phi = theta - a0
    phi -= TWO_PI * math.floor(phi / TWO_PI)
    if phi <= sweep:
        return phi / sweep, abs(d - r)
    sx1, sy1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    d0 = math.hypot(x - sx0, y - sy0)
    d1 = math.hypot(x - sx1, y - sy1)
    if d1 < d0 - tol:
        return 1.0, d1
    return 0.0, d0


def _sector_candidates(f: Frame, x: float, y: float, tol: float) -> list:
    cx, cy = f.origin
    frac, dist = arc_fraction(cx, cy, f.radius, f.lo, f.hi, x, y, tol)
    s0, s1 = _sector_ends(f)
    g1, d1 = _segment_param(x, y, s1[0], s1[1], cx, cy)
    g0, d0 = _segment_param(x, y, cx, cy, s0[0], s0[1])
    return [(dist, frac), (d1, 1 + g1), (d0, 2 + g0)]


def project(f: Frame, x: float, y: float, tol: float) -> float:
    """The parameter of the point of the path nearest to ``(x, y)``.

    ``tol`` is the decide length tolerance: a degenerate frame vector
    (``|v|² ≤ tol²``) and a point within ``tol`` of the centre give ``0``;
    polygon sides within ``tol`` of the nearest one compete by parameter.
    """
    if f.kind == 'affine':
        vx, vy = f.vector
        vv = vx * vx + vy * vy
        if vv <= tol * tol:
            return 0.0
        t = ((x - f.origin[0]) * vx + (y - f.origin[1]) * vy) / vv
        return _clamp(t, f.lo, f.hi)
    if f.kind == 'angle':
        dx = x - f.origin[0]
        dy = y - f.origin[1]
        if math.hypot(dx, dy) <= tol:
            return 0.0
        theta = math.atan2(dy, dx)
        if theta < 0:
            theta += TWO_PI
        if theta >= TWO_PI:
            theta = 0.0
        return theta
    if f.kind == 'arc':
        return arc_fraction(f.origin[0], f.origin[1], f.radius, f.lo, f.hi, x, y, tol)[0]
    if f.kind == 'sector':
        cands = _sector_candidates(f, x, y, tol)
        dmin = min(d for d, _ in cands)
        best = min(t for d, t in cands if d <= dmin + tol)
        return 0.0 if best >= 3 else best
    n = len(f.vertices)
    links = n if f.kind == 'perimeter' else n - 1
    sides = []
    for k in range(links):
        ax, ay = f.vertices[k]
        bx, by = f.vertices[(k + 1) % n]
        frac, dist = _segment_param(x, y, ax, ay, bx, by)
        sides.append((dist, k + frac))
    dmin = min(d for d, _ in sides)
    best = min(t for d, t in sides if d <= dmin + tol)
    if f.kind == 'perimeter':
        return 0.0 if best >= n else best
    return best


def distance_to_path(x: float, y: float, type_: str, value: dict) -> float:
    """Distance from ``(x, y)`` to the point set of a path element (the clamped
    part for a segment and a ray, the sides for a polygon, the links for a
    polyline, the arc itself, the boundary of a sector)."""
    if type_ == 'circle':
        return abs(math.hypot(x - value['c'][0], y - value['c'][1]) - value['r'])
    if type_ == 'segment':
        return _segment_param(x, y, *value['a'], *value['b'])[1]
    if type_ in ('line', 'ray'):
        px, py = value['p'] if type_ == 'line' else value['origin']
        dx, dy = value['dir']
        s = (x - px) * dx + (y - py) * dy
        if type_ == 'ray' and s < 0:
            return math.hypot(x - px, y - py)
        return abs((x - px) * dy - (y - py) * dx)
    if type_ == 'polygon':
        vs = value['vertices']
        n = len(vs)
        return min(_segment_param(x, y, *vs[k], *vs[(k + 1) % n])[1] for k in range(n))
    if type_ == 'polyline':
        vs = value['vertices']
        return min(_segment_param(x, y, *vs[k], *vs[k + 1])[1] for k in range(len(vs) - 1))
    if type_ == 'arc':
        return arc_fraction(value['c'][0], value['c'][1], value['r'], value['a0'], value['a1'], x, y, 0.0)[1]
    if type_ == 'sector':
        f = Frame('sector', (value['c'][0], value['c'][1]), lo=value['a0'], hi=value['a1'], radius=value['r'])
        return min(d for d, _t in _sector_candidates(f, x, y, 0.0))
    raise ValueError(f'{type_!r} is not a path type')
