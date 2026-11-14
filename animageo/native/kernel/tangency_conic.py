"""Finite conic contacts in a canonical frame, without coefficient matrices.

Central conics use ``X² ± Y² = 1`` and the polar of the input point.
Parabolas use ``u = p*t²/2, v = p*t``. All quadratic coefficients are
scaled before solving; the linear limit excludes contacts at infinity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ['ConicTangencyError', 'contact', 'from_point', 'parallel',
           'tangent_at', 'curve_residual', 'gradient', 'line_distance']


class ConicTangencyError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _finite(*values):
    if not all(math.isfinite(v) for v in values):
        raise ConicTangencyError('non_finite')


def _dot(x, y, ux, uy):
    scale = max(abs(x), abs(y))
    return ((x / scale) * ux + (y / scale) * uy) * scale if scale else 0.0


def _product(a, b):
    """Rounded product and its low part, using bounded Dekker splits.

    Splitting the mantissas keeps the splitter multiplication finite even
    at large scene scales. This also works on Python versions without
    ``math.fma`` and has a binary64-only counterpart for other kernels.
    """
    product = a*b
    if not product or not math.isfinite(product):
        return product, 0.0
    ma, ea = math.frexp(a)
    mb, eb = math.frexp(b)
    splitter = 134217729.0  # 2**27 + 1, for the 53-bit binary64 mantissa
    ca, cb = splitter*ma, splitter*mb
    ah, bh = ca-(ca-ma), cb-(cb-mb)
    al, bl = ma-ah, mb-bh
    high = ma*mb
    low = ((ah*bh-high)+ah*bl+al*bh)+al*bl
    return product, math.ldexp(low, ea+eb)


def _sum_products(terms):
    parts = []
    for a, b in terms:
        parts.extend(_product(a, b))
    try:
        return math.fsum(parts)
    except (OverflowError, ValueError):
        return math.inf


def line_distance(point, line):
    """Compensated distance to a unit carrier, without subtracting points.

    Large contacts can hide a significant error in a rounded determinant
    (including a false zero). Sum both high and low product parts before
    taking its absolute value, retaining the error in scene length units.
    """
    x, y = point
    px, py = line['p']
    dx, dy = line['dir']
    return abs(_sum_products(((x, dy), (-y, dx), (-px, dy), (py, dx))))


@dataclass(frozen=True)
class _Frame:
    kind: str
    origin: tuple
    axis: tuple
    a: float
    b: float

    def local(self, point):
        x, y = point[0] - self.origin[0], point[1] - self.origin[1]
        _finite(x, y)
        ux, uy = self.axis
        return _dot(x, y, ux, uy), _dot(x, y, -uy, ux)

    def world(self, u, v):
        ux, uy = self.axis
        cx, cy = self.origin
        scale = max(abs(cx), abs(cy), abs(u), abs(v))
        if not scale:
            return 0.0, 0.0
        x = (cx / scale + ux * (u / scale) - uy * (v / scale)) * scale
        y = (cy / scale + uy * (u / scale) + ux * (v / scale)) * scale
        _finite(x, y)
        return x + 0.0, y + 0.0

    def vector(self, u, v):
        ux, uy = self.axis
        return ux*u - uy*v, uy*u + ux*v


def _frame(value):
    try:
        if 'kind' not in value and 'r' in value:
            kind, origin, axis = 'ellipse', value['c'], (1.0, 0.0)
            a = b = float(value['r'])
        else:
            kind = value['kind']
            if kind not in ('ellipse', 'hyperbola', 'parabola'):
                raise ConicTangencyError('degenerate_conic')
            origin = value['vertex' if kind == 'parabola' else 'c']
            axis = value['axis']
            a = float(value['p'] if kind == 'parabola' else value['a'])
            b = 1.0 if kind == 'parabola' else float(value['b'])
        if len(origin) != 2 or len(axis) != 2:
            raise ConicTangencyError('degenerate_conic')
        origin = tuple(float(v) for v in origin)
        axis = tuple(float(v) for v in axis)
        _finite(*origin, *axis, a, b)
        length = math.hypot(*axis)
        if a <= 0 or b <= 0 or abs(length - 1) > 1e-8:
            raise ConicTangencyError('degenerate_conic')
        return _Frame(kind, origin, (axis[0]/length, axis[1]/length), a, b)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise ConicTangencyError('degenerate_conic') from exc


def _residual(frame, point):
    """Scaled implicit residual divided by the geometric gradient norm.

    This measures first-order normal displacement in length units. Focal
    residuals can saturate near a hyperbola's asymptote, even in exact
    arithmetic, and subtracting focal distances loses off-curve evidence
    on a distant parabola axis. Compensated polynomial products preserve
    that evidence without squaring large world coordinates.
    """
    u, v = frame.local(point)
    if frame.kind == 'parabola':
        scale = max(frame.a, abs(u), abs(v))
        x, y, p = u/scale, v/scale, frame.a/scale
        polynomial = _sum_products(((y, y), (-2*p, x)))
        norm = 2*math.hypot(p, y)
        if norm == 0:
            raise ConicTangencyError('non_finite')
        error = (abs(polynomial)/norm)*scale
    else:
        x, y = u/frame.a, v/frame.b
        _finite(x, y)
        if x == y == 0:
            return min(frame.a, frame.b) if frame.kind == 'ellipse' else frame.a
        scale = max(abs(x), abs(y), 1.0)
        x, y, inverse = x/scale, y/scale, 1/scale
        sign = 1 if frame.kind == 'ellipse' else -1
        polynomial = _sum_products(((x, x), (sign*y, y), (-inverse, inverse)))
        h = min(frame.a, frame.b)
        norm = 2*math.hypot(x*(h/frame.a), y*(h/frame.b))
        if norm == 0:
            raise ConicTangencyError('non_finite')
        error = ((abs(polynomial)*scale)/norm)*h
    _finite(error)
    return error


def curve_residual(value, point):
    """First-order normal displacement in a scaled canonical frame."""
    return _residual(_frame(value), point)


def _unit(x, y):
    scale = max(abs(x), abs(y))
    if not scale:
        raise ConicTangencyError('degenerate_conic')
    _finite(scale)
    x, y = x/scale, y/scale
    length = math.hypot(x, y)
    return x/length, y/length


def _gradient(frame, point):
    u, v = frame.local(point)
    if frame.kind == 'parabola':
        gu, gv = _unit(-frame.a, v)
    else:
        # A common positive factor leaves the canonical gradient direction
        # unchanged and avoids both squares of the semi-axes.
        x, y = u/frame.a, v/frame.b
        _finite(x, y)
        scale = max(abs(x), abs(y))
        if not scale:
            raise ConicTangencyError('degenerate_conic')
        h = min(frame.a, frame.b)
        gu, gv = _unit((x/scale)*(h/frame.a),
                       (y/scale)*(h/frame.b)*(1 if frame.kind == 'ellipse' else -1))
    return frame.vector(gu, gv)


def gradient(value, point):
    """Unit gradient of the canonical-sign conic, for geometric checks."""
    return _gradient(_frame(value), point)


def _line(point, direction):
    dx, dy = _unit(*direction)
    x, y = point
    scale = max(abs(x), abs(y))
    offset = dy*(x/scale) - dx*(y/scale) if scale else 0.0
    p = [(dy*offset)*scale, (-dx*offset)*scale]
    _finite(*p, dx, dy)
    return {'p': [v + 0.0 for v in p], 'dir': [dx + 0.0, dy + 0.0]}


def _pair(frame, point, direction=None, anchor=None):
    _finite(*point)
    if direction is None:
        nx, ny = _gradient(frame, point)
        direction = -ny, nx
    return _line(point if anchor is None else anchor, direction), point


def _validated(frame, pair, ctx, through=None):
    """Refuse a whole search when a finite candidate cannot be represented.

    A finite contact alone does not guarantee a usable binary64 carrier:
    near a hyperbola asymptote its unit normal can round to the direction
    at infinity. Such failures are numerical, not empty geometric sets.
    """
    line, point = pair
    dx, dy = line['dir']
    nx, ny = _gradient(frame, point)
    errors = [_residual(frame, point), line_distance(point, line),
              abs(_sum_products(((nx, dx), (ny, dy))))*ctx.tol.scale,
              abs(math.hypot(dx, dy)-1)*ctx.tol.scale]
    if through is not None:
        errors.append(line_distance(through, line))
    if any(not math.isfinite(error) or error > ctx.tol.check_passed for error in errors):
        raise ConicTangencyError('non_finite')
    if frame.kind == 'hyperbola':
        nu = _dot(dy, -dx, *frame.axis)
        nv = _dot(dy, -dx, -frame.axis[1], frame.axis[0])
        ha, hb = abs(frame.a*nu), abs(frame.b*nv)
        _finite(ha, hb)
        # Do not apply decide.scalar here: this tests representability of
        # an already found finite candidate, not existence of a solution.
        if ha <= hb:
            raise ConicTangencyError('non_finite')
    return pair


def tangent_at(value, point, ctx):
    frame = _frame(value)
    _finite(*point)
    error = _residual(frame, point)
    ctx.decide('off_carrier', error, ctx.tol.decide_length)
    if error > ctx.tol.decide_length:
        raise ConicTangencyError('not_on_curve')
    return _validated(frame, _pair(frame, point), ctx)[0]


def _roots(a, b, c, ctx, *, linear=True):
    """Stable real quadratic roots, with an explicit linear limit."""
    _finite(a, b, c)
    tol = ctx.tol.decide_scalar
    # A small nonzero quadratic coefficient still has a second finite
    # root. Only the exact linear limit has a contact at infinity; losing
    # an unrepresentable finite root must fail the whole set instead.
    is_linear = linear and a == 0.0
    if linear:
        ctx.decide('tangent_linear', a, tol)
    scale = max(abs(a), abs(b), abs(c))
    if not scale:
        return []
    a, b, c = a/scale, b/scale, c/scale
    if is_linear:
        return [] if b == 0 else [-c/b]
    disc = b*b - 4*a*c
    disc_tol = tol*(b*b + abs(4*a*c))
    ctx.decide('tangent', disc, disc_tol)
    if disc < -disc_tol:
        return []
    if abs(disc) <= disc_tol:
        return [-b/(2*a)]
    q = -.5*(b + math.copysign(math.sqrt(disc), b))
    return [q/a, c/q]


def _same(first, second, tol):
    line, q = first
    other, r = second
    dx, dy = line['dir']
    ux, uy = other['dir']
    if math.hypot(dx-ux, dy-uy) > math.hypot(dx+ux, dy+uy):
        ux, uy = -ux, -uy
    if math.hypot(dx-ux, dy-uy) > tol.decide_scalar:
        return False
    # Contacts can be distant when nearly coincident tangent lines are
    # ill-conditioned. Distinctness belongs to the normalized carrier.
    px, py = line['p']
    rx, ry = other['p']
    offset = abs(_dot(px-rx, py-ry, dy, -dx))
    close_contact = math.hypot(q[0]-r[0], q[1]-r[1]) <= tol.decide_length
    return close_contact or offset <= tol.decide_length


def _ordered(pairs, frame, vector, ctx, descending=True):
    distinct = []
    for pair in pairs:
        if not any(_same(pair, old, ctx.tol) for old in distinct):
            distinct.append(pair)
    # Translation is common to all projections. Removing it prevents a
    # distant centre from erasing the difference between two ranks.
    ranks = [(pair, _dot(pair[1][0]-frame.origin[0], pair[1][1]-frame.origin[1], *vector))
             for pair in distinct]
    ranks.sort(key=lambda item: item[1], reverse=descending)
    out = []
    i = 0
    while i < len(ranks):
        j = i+1
        while j < len(ranks) and abs(ranks[j][1]-ranks[i][1]) <= ctx.tol.decide_length:
            j += 1
        out.extend(pair for pair, rank in sorted(ranks[i:j], key=lambda item: item[0][1]))
        i = j
    return out


def from_point(value, point, ctx):
    """All distinct finite tangents through a point, before slot capacity."""
    frame = _frame(value)
    _finite(*point)
    error = _residual(frame, point)
    ctx.decide('off_carrier', error, ctx.tol.decide_length)
    if error <= ctx.tol.decide_length:
        return [_validated(frame, _pair(frame, point), ctx, through=point)]
    u, v = frame.local(point)
    if frame.kind == 'parabola':
        roots = _roots(frame.a/2, -v, u, ctx, linear=False)
        points = [frame.world((frame.a*t/2)*t, frame.a*t) for t in roots]
    else:
        x, y = u/frame.a, v/frame.b
        _finite(x, y)
        if frame.kind == 'ellipse' and math.hypot(x, y) < 1:
            raise ConicTangencyError('point_inside')
        sign = 1 if frame.kind == 'ellipse' else -1
        scale = max(abs(x), abs(y), 1.0)
        alpha, beta, gamma = x/scale, sign*y/scale, 1/scale
        if abs(alpha) >= abs(beta) and alpha:
            x0, y0, dx, dy = gamma/alpha, 0.0, -beta/alpha, 1.0
        elif beta:
            x0, y0, dx, dy = 0.0, gamma/beta, 1.0, -alpha/beta
        else:
            raise ConicTangencyError('no_tangent')
        radius = max(abs(x0), abs(y0), 1.0)
        x0, y0 = x0/radius, y0/radius
        roots = _roots(dx*dx+sign*dy*dy, 2*(x0*dx+sign*y0*dy),
                       x0*x0+sign*y0*y0-(1/radius)**2, ctx)
        points = [frame.world(frame.a*((x0+dx*t)*radius), frame.b*((y0+dy*t)*radius)) for t in roots]
    if not points:
        raise ConicTangencyError('no_tangent')
    nx, ny = _gradient(frame, point)
    pairs = [_validated(frame, _pair(frame, q, anchor=point), ctx, through=point) for q in points]
    return _ordered(pairs, frame, (-ny, nx), ctx)


def _parallel_points(frame, normal, scalar_tol):
    """Solve the dual equation without materializing an adjugate.

    In a central frame the line offset ``h`` satisfies the centred
    quadratic ``h² = (a*nu)² ± (b*nv)²``; its two signs give the support
    contacts. For ``v² = 2*p*u`` the dual equation is linear in the
    offset when ``nu != 0``, and its contact is ``v = -p*nv/nu``.
    ``nu == 0`` is the parabola's contact at infinity. A nonpositive
    hyperbola radicand likewise has no finite contact.
    """
    nu, nv = _dot(*normal, *frame.axis), _dot(*normal, -frame.axis[1], frame.axis[0])
    if frame.kind == 'parabola':
        if abs(nu) <= scalar_tol:
            return []
        v = -frame.a*(nv/nu)
        return [frame.world((v/2)*(v/frame.a), v)]
    ha, hb = frame.a*nu, frame.b*nv
    scale = max(abs(ha), abs(hb))
    _finite(scale)
    if not scale:
        return []
    ha, hb = ha/scale, hb/scale
    if frame.kind == 'ellipse':
        den = math.hypot(ha, hb)
        sign = 1
    else:
        disc = (abs(ha)-abs(hb))*(abs(ha)+abs(hb))
        if disc <= scalar_tol:
            return []
        den, sign = math.sqrt(disc), -1
    u, v = frame.a*(ha/den), sign*frame.b*(hb/den)
    return [frame.world(u, v), frame.world(-u, -v)]


def parallel(value, direction, ctx):
    """All finite tangents with the oriented direction of the base line."""
    frame = _frame(value)
    dx, dy = _unit(*direction)
    normal = dy, -dx
    points = _parallel_points(frame, normal, ctx.tol.decide_scalar)
    if not points:
        raise ConicTangencyError('no_tangent')
    pairs = [_validated(frame, _pair(frame, q, (dx, dy)), ctx) for q in points]
    return _ordered(pairs, frame, normal, ctx,
                    descending=frame.kind != 'hyperbola')


def contact(value, line):
    """Recover a tangent's finite contact, including unbound touch outputs.

    Return ``None`` when the conic or carrier has no recoverable finite
    contact. This does not search for, or create, construction elements.
    """
    try:
        frame = _frame(value)
        dx, dy = _unit(*line['dir'])
        points = _parallel_points(frame, (dy, -dx), 0.0)
        if len(points) < 2:
            return points[0] if points else None
        px, py = line['p']
        return min(points, key=lambda q: abs(_dot(q[0]-px, q[1]-py, dy, -dx)))
    except (ConicTangencyError, KeyError, TypeError, ValueError, OverflowError):
        return None
