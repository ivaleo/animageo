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
  ``k = min(floor(t'), n − 2)``, ``P = V[k] + (t' − k)(V[k+1] − V[k])``;
- ``conic`` (conic, registry 1.9) in the frame of the conic, ``u`` the axis,
  ``n = (−u_y, u_x)``: ellipse ``P = c + a·cos t·u + b·sin t·n``; hyperbola
  ``P = c + β·a·cosh t·u + b·sinh t·n`` with the branch ``β = ±1`` of the
  input; parabola ``P = V + (p t²/2)·u + p t·n``;
- ``graph`` (function, registry 1.9): ``x = clamp(t, domain)``,
  ``P = (x, f(x))``, no point where ``f`` has no value.

``project`` is the inverse: the parameter of the nearest point of the path,
ties to the smallest parameter; ``locate`` also gives the branch of a
hyperbola (the nearest one) and takes the window of a graph (registry 1.9).
"""
from __future__ import annotations

import math
from typing import NamedTuple

from ..registry import registry
from .conic import residual
from .function import evaluator

__all__ = ['Frame', 'frame', 'point_at', 'project', 'locate', 'nearest_input', 'nearest_on_graph', 'distance_to_path',
           'parameter_range', 'outside', 'parameter_unit', 'arc_fraction', 'ROOT_HALVINGS']

TWO_PI = 2 * math.pi
ROOT_HALVINGS = 1100        # halvings of a projection root at most: to the resolution of a double


class Frame(NamedTuple):
    """The frame of a path element.

    ``kind`` ``affine``: ``origin``, ``vector``, ``lo``/``hi`` (``None`` — no
    bound); ``angle``: ``origin`` = centre, ``radius``; ``perimeter``:
    ``vertices``; ``conic``: ``curve`` = the conic value; ``graph``:
    ``curve`` = the function value, ``lo``/``hi`` its domain.
    """

    kind: str
    origin: tuple = (0.0, 0.0)
    vector: tuple = (0.0, 0.0)
    lo: float | None = None
    hi: float | None = None
    radius: float = 0.0
    vertices: tuple = ()
    curve: dict | None = None
    gap: float = math.inf


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


def frame(type_: str, value: dict, producer_op: str | None = None, producer_args: dict | None = None,
          *, scale: float = 1.0) -> Frame:
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
    if kind in ('arc', 'sector', 'circlesegment'):
        return Frame(kind, (value['c'][0], value['c'][1]), lo=value['a0'], hi=value['a1'], radius=value['r'])
    if kind == 'polyline':
        return Frame('polyline', vertices=tuple((v[0], v[1]) for v in value['vertices']))
    if kind == 'conic':
        return Frame('conic', curve=value)
    if kind == 'graph':
        lo, hi = value['domain']
        return Frame('graph', lo=lo, hi=hi, curve=value)
    if kind == 'locus':
        points = tuple(None if p is None else (p[0], p[1]) for p in value['points'])
        if value['closed'] and points:
            points += (points[0],)
        return Frame('locus', lo=0.0, hi=1.0, vertices=points, gap=0.25 * scale)
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
    if f.kind in ('affine', 'graph', 'locus'):
        return f.lo, f.hi
    if f.kind == 'conic':
        return (0.0, TWO_PI) if f.curve['kind'] == 'ellipse' else (None, None)
    if f.kind == 'angle':
        return 0.0, TWO_PI
    if f.kind == 'perimeter':
        return 0.0, float(len(f.vertices))
    if f.kind == 'arc':
        return 0.0, 1.0
    if f.kind == 'sector':
        return 0.0, 3.0
    if f.kind == 'circlesegment':
        return 0.0, 2.0
    return 0.0, float(len(f.vertices) - 1)


_WRAPPED = ('angle', 'perimeter', 'sector', 'circlesegment')


def outside(f: Frame) -> str:
    """What a parameter outside :func:`parameter_range` does: ``wrap``,
    ``clamp`` or ``none`` (``_types.json`` → ``paths.<type>.outside``; a
    conic by the kind of its value, ``byKind``; a graph clamps to its
    domain, ``none`` without one)."""
    if f.kind in _WRAPPED:
        return 'wrap'
    if f.kind == 'conic':
        return 'wrap' if f.curve['kind'] == 'ellipse' else 'none'
    if f.kind in ('affine', 'graph'):
        return 'none' if f.lo is None and f.hi is None else 'clamp'
    return 'clamp'                      # arc, polyline


def parameter_unit(f: Frame) -> float:
    """Length per unit of the parameter near its origin (``0`` — none): ``|v|``
    of an affine frame, ``b`` of a hyperbola, ``p`` of a parabola, ``1`` of a
    graph (the abscissa)."""
    if f.kind == 'affine':
        return math.hypot(*f.vector)
    if f.kind == 'graph':
        return 1.0
    if f.kind == 'conic' and f.curve['kind'] != 'ellipse':
        return f.curve['b'] if f.curve['kind'] == 'hyperbola' else f.curve['p']
    return 0.0


def _big(fn, t: float) -> float:
    """``cosh``/``sinh`` that overflow to ``±inf`` (as in JavaScript), not an error."""
    try:
        return fn(t)
    except OverflowError:
        return math.copysign(math.inf, t) if fn is math.sinh else math.inf


def _conic_xy(value: dict, t: float, branch: int) -> tuple:
    """``(x, y)`` of the point ``t`` of a conic value (the branch ``±1`` of a hyperbola)."""
    ux, uy = value['axis']
    nx, ny = -uy, ux
    kind = value['kind']
    if kind == 'parabola':
        ox, oy = value['vertex']
        p = value['p']
        s, r = p * t * t / 2, p * t
    else:
        ox, oy = value['c']
        a, b = value['a'], value['b']
        if kind == 'ellipse':
            s, r = a * math.cos(t), b * math.sin(t)
        else:
            s, r = (-a if branch == -1 else a) * _big(math.cosh, t), b * _big(math.sinh, t)
    return ox + s * ux + r * nx, oy + s * uy + r * ny


def point_at(f: Frame, t: float, branch: int = 1) -> dict | None:
    """``P(t)`` as an encoded point ``{x, y}``; ``branch`` (``±1``) picks the
    branch of a hyperbola, other paths ignore it. A graph gives ``None``
    where its function has no value."""
    if f.kind == 'locus':
        if locus_reason(f) is not None:
            return None
        w = _clamp(t, 0.0, 1.0) * (len(f.vertices) - 1)
        k = min(math.floor(w), len(f.vertices) - 2)
        frac = w - k
        a, b = f.vertices[k:k + 2]
        if frac == 0 and a is not None:
            return {'x': a[0], 'y': a[1]}
        if frac == 1 and b is not None:
            return {'x': b[0], 'y': b[1]}
        if a is None or b is None or math.dist(a, b) > f.gap:
            return None
        return {'x': a[0] + frac * (b[0] - a[0]), 'y': a[1] + frac * (b[1] - a[1])}
    if f.kind == 'conic':
        x, y = _conic_xy(f.curve, t, branch)
        return {'x': x, 'y': y}
    if f.kind == 'graph':
        x = _clamp(t, f.lo, f.hi)
        y = evaluator(f.curve)(x)
        return None if y is None else {'x': x, 'y': y}
    if f.kind == 'affine':
        s = _clamp(t, f.lo, f.hi)
        return {'x': f.origin[0] + s * f.vector[0], 'y': f.origin[1] + s * f.vector[1]}
    if f.kind == 'angle':
        return {'x': f.origin[0] + f.radius * math.cos(t), 'y': f.origin[1] + f.radius * math.sin(t)}
    if f.kind == 'arc':
        x, y = _arc_xy(f, _clamp(t, 0.0, 1.0))
        return {'x': x, 'y': y}
    if f.kind == 'circlesegment':
        w = _wrap(t, 2)
        if w <= 1:
            x, y = _arc_xy(f, w)
            return {'x': x, 'y': y}
        s0, s1 = _sector_ends(f)
        return {'x': s1[0] + (w - 1) * (s0[0] - s1[0]),
                'y': s1[1] + (w - 1) * (s0[1] - s1[1])}
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


def locus_reason(f: Frame, tol: float = 0.0) -> str | None:
    """Why a locus cannot carry a point; repeated samples alone have no path."""
    if not any(p is not None for p in f.vertices):
        return 'empty_locus'
    if not any(a is not None and b is not None and tol < math.dist(a, b) <= f.gap
               for a, b in zip(f.vertices, f.vertices[1:])):
        return 'degenerate_locus'
    return None


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
    if f.kind == 'circlesegment':
        g, d = _segment_param(x, y, s1[0], s1[1], s0[0], s0[1])
        return [(dist, frac), (d, 1 + g)]
    g1, d1 = _segment_param(x, y, s1[0], s1[1], cx, cy)
    g0, d0 = _segment_param(x, y, cx, cy, s0[0], s0[1])
    return [(dist, frac), (d1, 1 + g1), (d0, 2 + g0)]


def _root(g, lo: float, hi: float) -> float:
    """The root of ``g`` in ``(lo, hi)`` where ``g > 0`` left of it: halve
    while ``lo < m < hi`` (``m = lo + (hi − lo)/2``, at most
    :data:`ROOT_HALVINGS` times), ``g(m) > 0`` → ``lo = m``, else ``hi = m``;
    the last ``m``."""
    m = lo + (hi - lo) / 2
    for _ in range(ROOT_HALVINGS):
        if not (lo < m < hi):
            break
        if g(m) > 0:
            lo = m
        else:
            hi = m
        m = lo + (hi - lo) / 2
    return m


def _conic_frame_xy(value: dict, x: float, y: float) -> tuple:
    """``(X, Y)``: ``(x, y)`` in the frame of a conic value (from its centre or vertex along ``u``, ``n``)."""
    ux, uy = value['axis']
    ox, oy = value['vertex'] if value['kind'] == 'parabola' else value['c']
    dx, dy = x - ox, y - oy
    return dx * ux + dy * uy, dy * ux - dx * uy


def _ellipse_t(a: float, b: float, X: float, Y: float) -> float:
    """The nearest point of the ellipse ``(a cos t, b sin t)``, ``a ≥ b``, to
    ``(X, Y)`` (Eberly, *Distance from a point to an ellipse*): in the first
    quadrant ``(y0, y1) = (|X|, |Y|)``, then the signs back; ``Y = 0`` (the
    major axis) takes the side ``+n``."""
    y0, y1 = abs(X), abs(Y)
    if y1 > 0:
        if y0 > 0:
            z0, z1 = y0 / a, y1 / b
            g = z0 * z0 + z1 * z1 - 1
            if g == 0:
                x0, x1 = y0, y1
            else:
                r0 = (a / b) ** 2
                n0 = r0 * z0
                s = _root(lambda s: (n0 / (s + r0)) ** 2 + (z1 / (s + 1)) ** 2 - 1,
                          z1 - 1, 0.0 if g < 0 else math.hypot(n0, z1) - 1)
                x0, x1 = r0 * y0 / (s + r0), y1 / (s + 1)
        else:
            x0, x1 = 0.0, b
    else:
        numer, denom = a * y0, a * a - b * b
        if numer < denom:
            q = numer / denom
            x0, x1 = a * q, b * math.sqrt(1 - q * q)
        else:
            x0, x1 = a, 0.0
    if X < 0:
        x0 = -x0
    if Y < 0:
        x1 = -x1
    t = math.atan2(x1 / b, x0 / a)
    if t < 0:
        t += TWO_PI
    return 0.0 if t >= TWO_PI else t


def _hyperbola_t(a: float, b: float, X: float, Y: float) -> float:
    """The nearest point of the branch ``(a cosh t, b sinh t)`` to ``(X, Y)``,
    ``X ≥ 0``: for ``Y ≠ 0`` the root ``λ`` of the decreasing
    ``F(λ) = (aX/(a² + λ))² − (b|Y|/(b² − λ))² − 1`` on ``(−a², b²)``,
    ``y = b²|Y|/(b² − λ)``, ``t = ±asinh(y/b)`` by the sign of ``Y``; on
    the axis the vertex, or past the centre of curvature ``(a² + b²)/a`` the
    foot with ``t < 0`` (ties to the smallest parameter)."""
    if Y == 0:
        if X > (a * a + b * b) / a:
            return -math.acosh(a * X / (a * a + b * b))
        return 0.0
    y1 = abs(Y)
    lam = _root(lambda m: (a * X / (a * a + m)) ** 2 - (b * y1 / (b * b - m)) ** 2 - 1, -a * a, b * b)
    t = math.asinh(b * y1 / (b * b - lam))
    return t if Y > 0 else -t


def _parabola_t(p: float, X: float, Y: float) -> float:
    """The nearest point of ``(p t²/2, p t)`` to ``(X, Y)``: for ``Y ≠ 0`` the
    positive root ``s`` of ``s³ + P s + Q``, ``P = 2(1 − X/p)``,
    ``Q = −2|Y|/p``, in ``(0, max(1, √(|P| + |Q|)))``, ``t = ±s`` by the
    sign of ``Y``; on the axis the vertex, or past ``X = p`` the foot with
    ``t < 0``."""
    if Y == 0:
        return -math.sqrt(2 * (X / p - 1)) if X > p else 0.0
    P, Q = 2 * (1 - X / p), -2 * abs(Y) / p
    s = _root(lambda s: -(s * s * s + P * s + Q), 0.0, max(1.0, math.sqrt(abs(P) + abs(Q))))
    return s if Y > 0 else -s


def _locate_conic(value: dict, x: float, y: float, tol: float, decide) -> tuple:
    X, Y = _conic_frame_xy(value, x, y)
    if decide is not None:
        decide('closest_axis', Y, tol)
    if abs(Y) <= tol:
        Y = 0.0
    kind = value['kind']
    if kind == 'parabola':
        return _parabola_t(value['p'], X, Y), 1
    if kind == 'ellipse':
        if decide is not None:
            decide('closest_axis', X, tol)
        if abs(X) <= tol:                   # the centre of a circle conic gives 0, as on a circle
            X = 0.0
        return _ellipse_t(value['a'], value['b'], X, Y), 1
    if decide is not None:
        decide('closest_branch', X, tol)
    branch = -1 if X < -tol else 1
    return _hyperbola_t(value['a'], value['b'], branch * X, Y), branch


GRAPH_CELLS = 512            # cells of the grid of a graph projection (as the searches of a function)


def graph_window(bounds) -> tuple:
    """``(x0, x1)`` of the window ``B4`` of ``bounds`` (default bounds when ``None``)."""
    from .numeric import default_bounds
    from .ops.locus import window
    box = window(bounds or default_bounds())
    return box[0], box[2]


def _locate_graph(f: Frame, x: float, y: float, bounds):
    """The abscissa of the nearest point of the graph (:func:`nearest_on_graph`)."""
    return nearest_on_graph(evaluator(f.curve), f.lo, f.hi, x, y, bounds)


def nearest_on_graph(fx, lo, hi, x: float, y: float, bounds=None):
    """The abscissa of the nearest point to ``(x, y)`` of the graph of ``fx``
    (``fx(u)`` — a number, ``None`` where there is no value) with the domain
    ``[lo, hi]`` (``None`` — open): a grid of :data:`GRAPH_CELLS` cells over
    ``[min(x0, x), max(x1, x)]`` (the window ``B4`` of ``bounds``) brought
    into the domain, the best node by ``d²`` (the first on a tie), then the
    golden-section search over its two cells; ``None`` when no node has a
    value."""
    from .function import golden_min, grid
    x0, x1 = graph_window(bounds)
    a0, a1 = min(x0, x), max(x1, x)
    if lo is not None:
        a0, a1 = max(a0, lo), max(a1, lo)
    if hi is not None:
        a0, a1 = min(a0, hi), min(a1, hi)

    def d2(u):
        v = fx(u)
        return None if v is None else (u - x) ** 2 + (v - y) ** 2

    nodes = grid(a0, a1, GRAPH_CELLS)
    best, k_best = None, None
    for k, u in enumerate(nodes):
        d = d2(u)
        if d is not None and (best is None or d < best):
            best, k_best = d, k
    if k_best is None:
        return None
    u, d = golden_min(d2, nodes[max(k_best - 1, 0)], nodes[min(k_best + 1, GRAPH_CELLS)])
    return u if d < best else nodes[k_best]


def locate(f: Frame, x: float, y: float, tol: float, bounds=None, decide=None):
    """``(t, branch)`` of the point of the path nearest to ``(x, y)``: the
    parameter of :func:`project`, ``branch`` ``±1`` the nearest branch of a
    hyperbola (``+1`` on other paths); ``None`` when a graph has no point to
    search. ``bounds`` gives the window of a graph; ``decide(name, value,
    tol)`` records the near decisions (``closest_axis``, ``closest_branch``)."""
    if f.kind == 'conic':
        return _locate_conic(f.curve, x, y, tol, decide)
    if f.kind == 'graph':
        u = _locate_graph(f, x, y, bounds)
        return None if u is None else (u, 1)
    t = project(f, x, y, tol)
    return None if t is None else (t, 1)


def nearest_input(f: Frame, x: float, y: float, tol: float, bounds=None) -> dict | None:
    """The ``pathParameter`` input of ``point.on_path`` at the point of the
    path nearest to ``(x, y)``: ``{"kind", "value"}``, on a conic also
    ``pathKind`` (its kind now) and on a hyperbola ``branch`` (the nearest
    one); ``None`` when a graph has no point."""
    found = locate(f, x, y, tol, bounds)
    if found is None:
        return None
    t, branch = found
    out = {'kind': 'pathParameter', 'value': t}
    if f.kind == 'conic':
        if f.curve['kind'] == 'hyperbola':
            out['branch'] = branch
        out['pathKind'] = f.curve['kind']
    return out


def project(f: Frame, x: float, y: float, tol: float, bounds=None) -> float | None:
    """The parameter of the point of the path nearest to ``(x, y)``.

    ``tol`` is the decide length tolerance: a degenerate frame vector
    (``|v|² ≤ tol²``) and a point within ``tol`` of the centre give ``0``;
    polygon sides within ``tol`` of the nearest one compete by parameter.
    Registry 1.9: a conic and a graph by :func:`locate` (``None`` when a
    graph has no point; the branch of a hyperbola is that of ``locate``).
    """
    if f.kind == 'locus':
        if locus_reason(f, tol) is not None:
            return None
        sides = []
        n = len(f.vertices) - 1
        for k, a in enumerate(f.vertices):
            if a is not None:
                sides.append((math.hypot(x - a[0], y - a[1]), k / n))
            if k == n:
                continue
            b = f.vertices[k + 1]
            if a is None or b is None or math.dist(a, b) > f.gap:
                continue
            frac, dist = _segment_param(x, y, *a, *b)
            sides.append((dist, (k + frac) / n))
        dmin = min(d for d, _ in sides)
        return min(t for d, t in sides if d <= dmin + tol)
    if f.kind in ('conic', 'graph'):
        found = locate(f, x, y, tol, bounds)
        return None if found is None else found[0]
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
    if f.kind in ('sector', 'circlesegment'):
        cands = _sector_candidates(f, x, y, tol)
        dmin = min(d for d, _ in cands)
        best = min(t for d, t in cands if d <= dmin + tol)
        period = 2 if f.kind == 'circlesegment' else 3
        return 0.0 if best >= period else best
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


def distance_to_path(x: float, y: float, type_: str, value: dict, *, scale: float = 1.0) -> float:
    """Distance from ``(x, y)`` to the point set of a path element (the clamped
    part for a segment and a ray, the sides for a polygon, the links for a
    polyline, the arc itself, the boundary of a sector). Registry 1.9: a
    conic gives its focal residual (``kernel/conic.py`` ``residual``, zero
    exactly on the curve, as the checks of registry 1.8), a graph
    ``|y − f(x)|`` (``∞`` where ``f`` has no value)."""
    if type_ == 'locus':
        f = frame(type_, value, scale=scale)
        t = project(f, x, y, 0.0)
        at = None if t is None else point_at(f, t)
        return math.inf if at is None else math.hypot(x - at['x'], y - at['y'])
    if type_ == 'conic':
        return residual(value, x, y)
    if type_ == 'function':
        fx = evaluator(value)(x)
        return math.inf if fx is None else abs(y - fx)
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
    if type_ in ('sector', 'circlesegment'):
        f = Frame(type_, (value['c'][0], value['c'][1]), lo=value['a0'], hi=value['a1'], radius=value['r'])
        return min(d for d, _t in _sector_candidates(f, x, y, 0.0))
    raise ValueError(f'{type_!r} is not a path type')
