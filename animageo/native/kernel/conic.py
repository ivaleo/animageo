"""Conics without manim (registry 1.6; docs/native/ops/conic.*.md).

A value of the type ``conic`` carries the geometry, not the coefficients:

- ``{kind: 'ellipse', c: [x, y], axis: [ux, uy], a, b}`` — ``a >= b > 0``,
  ``a`` along the unit vector ``axis``; a circle is an ellipse with
  ``a == b`` and ``axis = [1, 0]``;
- ``{kind: 'hyperbola', c, axis, a, b}`` — ``a`` the transverse semi-axis
  along ``axis``, ``b`` the conjugate one;
- ``{kind: 'parabola', vertex: [x, y], axis: [ux, uy], p}`` — ``axis`` from
  the vertex towards the focus, ``p`` the distance from the focus to the
  directrix (``v² = 2·p·u`` in the frame of the vertex).

``n = [-uy, ux]`` (the axis turned by +90°) is the second axis of the frame.
A degenerate conic (a pair of lines, a point, no real points) has no value:
the operations give ``degenerate_conic``.

:func:`from_coeffs` classifies ``A x² + B xy + C y² + D x + E y + F = 0`` in
a frame ``x = x0 + s·x'`` where the coordinates are about one; its decisions
are dimensionless and run in the order ``degenerate`` (the determinant),
``parabola`` (the discriminant), ``circle``, ``axis_orientation``.
"""
from __future__ import annotations

import math

from .numeric import decision_margin
from .values import Undefined

__all__ = [
    'equation_coeffs', 'five_point_coeffs', 'foci', 'from_coeffs', 'label_anchor', 'line_params',
    'matrix', 'normal', 'residual', 'vertices',
]

# Points of the equation reading (frame units): six give the coefficients,
# four more check that the expression is a polynomial of degree two.
EQUATION_SAMPLES = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1))
EQUATION_CHECKS = ((2, 1), (-1, 2), (-1, -1), (1, -2))


def normal(axis) -> tuple:
    """The axis turned by +90°."""
    return -axis[1], axis[0]


def _central(value) -> bool:
    return value['kind'] != 'parabola'


def foci(value) -> list:
    """``[[x, y], …]``: ellipse and hyperbola ``c ∓ e·axis`` (``e`` the
    focal half-distance), parabola ``[vertex + (p/2)·axis]``."""
    ux, uy = value['axis']
    if value['kind'] == 'parabola':
        vx, vy = value['vertex']
        h = value['p'] / 2
        return [[vx + h * ux, vy + h * uy]]
    a = value['a']
    b = value['b']
    e = math.sqrt((a - b) * (a + b)) if value['kind'] == 'ellipse' else math.hypot(a, b)
    cx, cy = value['c']
    return [[cx - e * ux, cy - e * uy], [cx + e * ux, cy + e * uy]]


def vertices(value) -> list:
    """Ellipse ``[c − a·axis, c + a·axis, c − b·n, c + b·n]``, hyperbola the
    first two, parabola ``[vertex]``."""
    if value['kind'] == 'parabola':
        return [list(value['vertex'])]
    ux, uy = value['axis']
    nx, ny = normal(value['axis'])
    cx, cy = value['c']
    a = value['a']
    out = [[cx - a * ux, cy - a * uy], [cx + a * ux, cy + a * uy]]
    if value['kind'] == 'ellipse':
        b = value['b']
        out += [[cx - b * nx, cy - b * ny], [cx + b * nx, cy + b * ny]]
    return out


def label_anchor(value) -> tuple:
    """The point of the curve a label hangs from: ellipse ``c + b·n``,
    hyperbola ``c + a·axis``, parabola the vertex."""
    if value['kind'] == 'parabola':
        return tuple(value['vertex'])
    cx, cy = value['c']
    if value['kind'] == 'hyperbola':
        ux, uy = value['axis']
        return cx + value['a'] * ux, cy + value['a'] * uy
    nx, ny = normal(value['axis'])
    return cx + value['b'] * nx, cy + value['b'] * ny


def matrix(value) -> list:
    """The symmetric 3×3 matrix ``M`` of the conic (``[x, y, 1] M [x, y, 1]ᵀ = 0``):
    central ``(X − c)ᵀ Q (X − c) − 1``, ``Q = u uᵀ/a² ± n nᵀ/b²``; parabola
    ``((X − V)·n)² − 2p·(X − V)·u``."""
    ux, uy = value['axis']
    nx, ny = normal(value['axis'])
    if value['kind'] == 'parabola':
        vx, vy = value['vertex']
        p = value['p']
        q = [[nx * nx, nx * ny], [nx * ny, ny * ny]]
        lx = -(q[0][0] * vx + q[0][1] * vy) - p * ux
        ly = -(q[1][0] * vx + q[1][1] * vy) - p * uy
        k = (vx * nx + vy * ny) ** 2 + 2 * p * (vx * ux + vy * uy)
        return [[q[0][0], q[0][1], lx], [q[1][0], q[1][1], ly], [lx, ly, k]]
    sign = 1.0 if value['kind'] == 'ellipse' else -1.0
    ia = 1 / (value['a'] * value['a'])
    ib = sign / (value['b'] * value['b'])
    q = [[ux * ux * ia + nx * nx * ib, ux * uy * ia + nx * ny * ib],
         [ux * uy * ia + nx * ny * ib, uy * uy * ia + ny * ny * ib]]
    cx, cy = value['c']
    lx = -(q[0][0] * cx + q[0][1] * cy)
    ly = -(q[1][0] * cx + q[1][1] * cy)
    k = cx * (q[0][0] * cx + q[0][1] * cy) + cy * (q[1][0] * cx + q[1][1] * cy) - 1
    return [[q[0][0], q[0][1], lx], [q[1][0], q[1][1], ly], [lx, ly, k]]


def residual(value, x: float, y: float) -> float:
    """A length that is zero on the curve, by the focal definition: ellipse
    ``| |XF1| + |XF2| − 2a |``, hyperbola ``| ||XF1| − |XF2|| − 2a |``,
    parabola ``| |XF| − distance to the directrix |``."""
    fs = foci(value)
    if value['kind'] == 'parabola':
        fx, fy = fs[0]
        ux, uy = value['axis']
        vx, vy = value['vertex']
        h = value['p'] / 2
        to_directrix = (x - (vx - h * ux)) * ux + (y - (vy - h * uy)) * uy
        return abs(math.hypot(x - fx, y - fy) - abs(to_directrix))
    d1 = math.hypot(x - fs[0][0], y - fs[0][1])
    d2 = math.hypot(x - fs[1][0], y - fs[1][1])
    if value['kind'] == 'ellipse':
        return abs(d1 + d2 - 2 * value['a'])
    return abs(abs(d1 - d2) - 2 * value['a'])


# ── classification ─────────────────────────────────────────────────────

def _oriented(ux: float, uy: float, ctx) -> tuple:
    """The canonical sign of an axis without a direction: ``u_y > 0``, on
    the x axis (``|u_y| <= tol.decide_scalar``) ``u_x > 0``."""
    tol = ctx.tol.decide_scalar
    ctx.decide('axis_orientation', uy, tol)
    if uy < -tol or (abs(uy) <= tol and ux < 0):
        return -ux, -uy
    return ux, uy


def _eigenvector(a: float, h: float, c: float, half: float) -> tuple:
    """The unit eigenvector of ``mean + half`` of ``[[a, h], [h, c]]``
    without cancellation: ``((a − c)/2 + half, h)`` for ``a >= c``, else
    ``(h, (c − a)/2 + half)``; ``[1, 0]`` when ``half = 0`` (a multiple of
    the identity). Exact for a diagonal matrix."""
    if half == 0:
        return 1.0, 0.0
    if a >= c:
        vx, vy = (a - c) / 2 + half, h
    else:
        vx, vy = h, (c - a) / 2 + half
    norm = math.hypot(vx, vy)
    return vx / norm, vy / norm


def from_coeffs(coeffs, frame, ctx):
    """The value of ``A x'² + B x'y' + C y'² + D x' + E y' + F = 0`` written
    in the frame ``(x0, y0, s)`` (``x = x0 + s·x'``), or
    ``Undefined('degenerate_conic')``.

    The coefficients are divided by the largest of their moduli; then
    ``det M`` (``degenerate``), ``δ = λ_small / λ_big`` of the quadratic part
    (``parabola``: ``|δ| <= tol.decide_scalar``), for an ellipse
    ``(λ_big − λ_small) / λ_big`` (``circle``) and the sign of the axis
    (``axis_orientation``), all against ``tol.decide_scalar``.
    """
    x0, y0, s = frame
    n = max(abs(float(c)) for c in coeffs)
    if n == 0:
        return Undefined('degenerate_conic')
    a, b, c, d, e, f = (float(v) / n for v in coeffs)
    tol = ctx.tol.decide_scalar
    det = a * (c * f - e * e / 4) - (b / 2) * (b * f / 2 - e * d / 4) + (d / 2) * (b * e / 4 - c * d / 2)
    ctx.decide('degenerate', det, tol)
    if abs(det) <= tol:
        return Undefined('degenerate_conic')
    mean = (a + c) / 2
    half = math.hypot((a - c) / 2, b / 2)
    plus = _eigenvector(a, b / 2, c, half)               # of mean + half
    minus = (-plus[1], plus[0])                          # of mean − half
    if mean >= 0:
        big, e_big, e_small = mean + half, plus, minus
    else:
        big, e_big, e_small = mean - half, minus, plus
    detq = a * c - b * b / 4
    small = detq / big
    delta = small / big
    ctx.decide('parabola', delta, tol)
    if abs(delta) <= tol:
        return _parabola(big, e_big, e_small, d, e, f, frame)
    cx = (b * e / 4 - c * d / 2) / detq
    cy = (b * d / 4 - a * e / 2) / detq
    k = f + (d * cx + e * cy) / 2
    centre = [x0 + s * cx, y0 + s * cy]
    if delta > 0:
        if k * big > 0:                                  # no real points
            return Undefined('degenerate_conic')
        ctx.decide('circle', (big - small) / big, tol)
        if abs((big - small) / big) <= tol:
            r = s * math.sqrt(-k / big)
            return {'kind': 'ellipse', 'c': centre, 'axis': [1.0, 0.0], 'a': r, 'b': r}
        ux, uy = _oriented(e_small[0], e_small[1], ctx)
        return {'kind': 'ellipse', 'c': centre, 'axis': [ux, uy],
                'a': s * math.sqrt(-k / small), 'b': s * math.sqrt(-k / big)}
    if -k / big > 0:
        transverse, at, bt = e_big, -k / big, k / small
    else:
        transverse, at, bt = e_small, -k / small, k / big
    ux, uy = _oriented(transverse[0], transverse[1], ctx)
    return {'kind': 'hyperbola', 'c': centre, 'axis': [ux, uy], 'a': s * math.sqrt(at), 'b': s * math.sqrt(bt)}


def _parabola(lam, w, u, d, e, f, frame):
    """``λ s² + Lw·s + Lu·t + F = 0`` in the eigenframe (``s`` along ``w``,
    ``t`` along the kernel direction ``u``)."""
    x0, y0, s = frame
    lw = d * w[0] + e * w[1]
    lu = d * u[0] + e * u[1]
    if lu == 0:
        return Undefined('degenerate_conic')
    s0 = -lw / (2 * lam)
    t0 = (lw * lw / (4 * lam) - f) / lu
    sign = 1.0 if -lam / lu > 0 else -1.0
    vx = s0 * w[0] + t0 * u[0]
    vy = s0 * w[1] + t0 * u[1]
    return {'kind': 'parabola', 'vertex': [x0 + s * vx, y0 + s * vy], 'axis': [sign * u[0], sign * u[1]],
            'p': s * abs(lu) / (2 * abs(lam))}


def five_point_coeffs(points, ctx):
    """``(coeffs, frame)`` of the conic through five points, or
    :class:`Undefined`.

    Frame: the centroid and ``s`` the largest distance from it
    (``coincident_points`` at ``s <= tol.decide_length``). The 5×6 system of
    ``[x², xy, y², x, y, 1]`` is solved by Gaussian elimination with full
    pivoting (the first largest modulus in row-major order); the fifth pivot
    ``<= tol.decide_scalar`` (decision ``degenerate``) leaves more than one
    conic: ``degenerate_conic``.
    """
    x0 = sum(p[0] for p in points) / 5
    y0 = sum(p[1] for p in points) / 5
    s = max(math.hypot(p[0] - x0, p[1] - y0) for p in points)
    ctx.decide('coincident_points', s, ctx.tol.decide_length)
    if s <= ctx.tol.decide_length:
        return Undefined('coincident_points')
    rows = []
    for px, py in points:
        x = (px - x0) / s
        y = (py - y0) / s
        rows.append([x * x, x * y, y * y, x, y, 1.0])
    cols = list(range(6))
    tol = ctx.tol.decide_scalar
    for k in range(5):
        best, bi, bj = -1.0, k, k
        for i in range(k, 5):
            for j in range(k, 6):
                m = abs(rows[i][j])
                if m > best:
                    best, bi, bj = m, i, j
        rows[k], rows[bi] = rows[bi], rows[k]
        for row in rows:
            row[k], row[bj] = row[bj], row[k]
        cols[k], cols[bj] = cols[bj], cols[k]
        if k == 4 or best == 0:
            ctx.decide('degenerate', best, tol)
            if best <= tol:
                return Undefined('degenerate_conic')
        pivot = rows[k][k]
        for i in range(k + 1, 5):
            factor = rows[i][k] / pivot
            if factor != 0:
                for j in range(k, 6):
                    rows[i][j] -= factor * rows[k][j]
    z = [0.0] * 6
    z[5] = 1.0
    for k in range(4, -1, -1):
        acc = 0.0
        for j in range(k + 1, 6):
            acc += rows[k][j] * z[j]
        z[k] = -acc / rows[k][k]
    coeffs = [0.0] * 6
    for k in range(6):
        coeffs[cols[k]] = z[k]
    return coeffs, (x0, y0, s)


def equation_coeffs(q, ctx):
    """``(coeffs, frame)`` of the equation ``q(x, y) = 0`` read at points, or
    :class:`Undefined`.

    Frame ``(0, 0, S)``: ``q`` is evaluated at ``(S·x', S·y')`` for the six
    points :data:`EQUATION_SAMPLES` (``F = q(0, 0)``, ``A, D`` from
    ``(±1, 0)``, ``C, E`` from ``(0, ±1)``, ``B`` from ``(1, 1)``) and the
    four :data:`EQUATION_CHECKS`; the largest misfit there, divided by the
    largest coefficient, above ``tol.decide_scalar`` (decision
    ``not_quadratic``) or a point where ``q`` has no value is
    ``not_quadratic``. A coefficient that is rounding noise of the largest
    one (``|v| ≤ N · tol.decide_scalar / decisionMargin``, the noise rule
    of ``numeric.json``) is ``0`` (1.11.0rc7: ``B`` of ``x²/9 + y²/4 = 1``
    read ``1.4e-14`` against ``N = 100`` and turned the axis by ``1e-16``).
    """
    scale = ctx.tol.scale

    def at(x, y):
        return q(scale * x, scale * y)
    values = [at(x, y) for x, y in EQUATION_SAMPLES]
    if any(v is None for v in values):
        return Undefined('not_quadratic')
    q00, q10, qm0, q01, q0m, q11 = values
    f = q00
    a = (q10 + qm0) / 2 - f
    d = (q10 - qm0) / 2
    c = (q01 + q0m) / 2 - f
    e = (q01 - q0m) / 2
    b = q11 - a - c - d - e - f
    coeffs = [a, b, c, d, e, f]
    misfit = 0.0
    for x, y in EQUATION_CHECKS:
        v = at(x, y)
        if v is None:
            return Undefined('not_quadratic')
        misfit = max(misfit, abs(v - (a * x * x + b * x * y + c * y * y + d * x + e * y + f)))
    n = max(abs(v) for v in coeffs)
    if n == 0:
        return Undefined('not_quadratic' if misfit > 0 else 'degenerate_conic')
    ctx.decide('not_quadratic', misfit / n, ctx.tol.decide_scalar)
    if misfit / n > ctx.tol.decide_scalar:
        return Undefined('not_quadratic')
    noise = n * ctx.tol.decide_scalar / decision_margin()
    coeffs = [0.0 if abs(v) <= noise else v for v in coeffs]
    return coeffs, (0.0, 0.0, scale)


# ── a line and a conic ────────────────────────────────────────────────

def line_params(value, c, ctx):
    """``[(t, double), …]`` along the carrier ``c`` (``t`` ascending), or a
    reason (``no_intersection``).

    ``g(t) = α t² + 2β t + γ`` is the canonical equation on the line,
    scaled to lengths²: ellipse ``u² + (a/b)² v² − a²``, hyperbola
    ``u² − (a/b)² v² − a²``, parabola ``v² − 2p u`` (``u`` along the axis
    from the centre or vertex, ``v`` along ``n``). With ``Δ = β² − αγ`` the
    decision ``tangent`` is ``m = Δ / (2a|α|)`` (``2p|α|`` for a parabola)
    against ``tol.decide_length``. A hyperbola with
    ``|α| / (du² + (a/b)² dv²) <= tol.decide_scalar`` (``asymptote``) or a
    parabola with ``|dv| <= tol.decide_scalar`` (``parallel``) has one
    point ``t = −γ / (2β)``; an asymptote itself
    (``|β| / √(du² + (a/b)² dv²) <= tol.decide_length``) none.
    """
    ux, uy = value['axis']
    nx, ny = normal(value['axis'])
    tol = ctx.tol.decide_length
    du = c.dx * ux + c.dy * uy
    dv = c.dx * nx + c.dy * ny
    if value['kind'] == 'parabola':
        vx, vy = value['vertex']
        ox = c.px - vx
        oy = c.py - vy
        pu = ox * ux + oy * uy
        pv = ox * nx + oy * ny
        p = value['p']
        alpha = dv * dv
        beta = pv * dv - p * du
        gamma = pv * pv - 2 * p * pu
        ctx.decide('parallel', dv, ctx.tol.decide_scalar)
        if abs(dv) <= ctx.tol.decide_scalar:
            return [(-gamma / (2 * beta), False)]
        unit = 2 * p
    else:
        cx, cy = value['c']
        ox = c.px - cx
        oy = c.py - cy
        pu = ox * ux + oy * uy
        pv = ox * nx + oy * ny
        r = value['a'] / value['b']
        k = r * r if value['kind'] == 'ellipse' else -r * r
        alpha = du * du + k * dv * dv
        beta = pu * du + k * pv * dv
        gamma = pu * pu + k * pv * pv - value['a'] * value['a']
        if value['kind'] == 'hyperbola':
            norm = du * du + r * r * dv * dv
            ctx.decide('asymptote', alpha / norm, ctx.tol.decide_scalar)
            if abs(alpha / norm) <= ctx.tol.decide_scalar:
                m = beta / math.sqrt(norm)
                ctx.decide('asymptote', m, tol)
                if abs(m) <= tol:
                    return 'no_intersection'
                return [(-gamma / (2 * beta), False)]
        unit = 2 * value['a']
    disc = beta * beta - alpha * gamma
    m = disc / (unit * abs(alpha))
    ctx.decide('tangent', m, tol)
    if m < -tol:
        return 'no_intersection'
    if m <= tol:
        t = -beta / alpha
        return [(t, True), (t, True)]
    root = math.sqrt(disc)
    t1 = (-beta - root) / alpha
    t2 = (-beta + root) / alpha
    return [(t1, False), (t2, False)] if t1 <= t2 else [(t2, False), (t1, False)]
