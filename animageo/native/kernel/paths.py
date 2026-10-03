"""Path parameters (``ops/v1/_types.json`` → ``paths``; docs/native/ops/point.on_path.md).

A point on a path is ``P(t)`` in the frame of the path element:

- ``affine`` (segment, line, ray): ``P = o + t'·v``, ``t' = t`` clamped to
  ``[min, max]`` when ``outside`` is ``clamp``; ``o`` and ``v`` come from
  ``frames[<producer op>]``, else ``frames["*"]``: a line through ``a`` and
  ``b`` has ``o = a``, ``v = b − a``, so the point moves with ``a`` and ``b``;
- ``angle`` (circle): ``P = c + r·(cos t, sin t)``;
- ``perimeter`` (polygon, ``n`` vertices ``V``): ``t' = t − n·floor(t/n)``,
  ``t' < 0 → t' + n``, ``t' ≥ n → 0``; ``k = floor(t')``, ``f = t' − k``,
  ``P = V[k] + f·(V[(k+1) mod n] − V[k])``.

``project`` is the inverse: the parameter of the nearest point of the path,
ties to the smallest parameter.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from ..registry import registry

__all__ = ['Frame', 'frame', 'point_at', 'project', 'distance_to_path']

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
    source, _, field = expr.strip().partition('.')
    if source == 'value':
        return _xy(value[field])
    if source == 'args':
        return _xy(args[field])
    raise ValueError(f'unknown frame source {expr!r}')


def _expr(expr: str, value: dict, args: dict) -> tuple:
    """``"<src>.<field>"`` or ``"<src>.<f> - <src>.<g>"``; ``src`` is ``value`` or ``args``."""
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


def point_at(f: Frame, t: float) -> dict:
    """``P(t)`` as an encoded point ``{x, y}``."""
    if f.kind == 'affine':
        s = _clamp(t, f.lo, f.hi)
        return {'x': f.origin[0] + s * f.vector[0], 'y': f.origin[1] + s * f.vector[1]}
    if f.kind == 'angle':
        return {'x': f.origin[0] + f.radius * math.cos(t), 'y': f.origin[1] + f.radius * math.sin(t)}
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
    n = len(f.vertices)
    sides = []
    for k in range(n):
        ax, ay = f.vertices[k]
        bx, by = f.vertices[(k + 1) % n]
        frac, dist = _segment_param(x, y, ax, ay, bx, by)
        sides.append((dist, k + frac))
    dmin = min(d for d, _ in sides)
    best = min(t for d, t in sides if d <= dmin + tol)
    return 0.0 if best >= n else best


def distance_to_path(x: float, y: float, type_: str, value: dict) -> float:
    """Distance from ``(x, y)`` to the point set of a path element (the clamped
    part for a segment and a ray, the sides for a polygon)."""
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
    raise ValueError(f'{type_!r} is not a path type')
