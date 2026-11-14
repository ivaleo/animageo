"""Finite conic elements in the canonical frame shared with tangency.

Positive exponent scaling keeps normals and offsets usable without squares
of world coordinates, overflow of axis squares, or an absolute zero test.
"""
import math

from .tangency_conic import ConicTangencyError, _finite, _frame, _unit


def _ratio(numerators, denominators=()):
    """A product/quotient as a signed mantissa and an unbounded exponent."""
    m, e = 1.0, 0
    for v in numerators:
        mv, ev = math.frexp(v)
        m, e = m*mv, e+ev
    for v in denominators:
        mv, ev = math.frexp(v)
        m, e = m/mv, e-ev
    m, shift = math.frexp(m)
    return m, e+shift


def _normal(first, second):
    exponent = max(e for m, e in (first, second) if m)
    x, y = (math.ldexp(m, e-exponent) if m else 0.0 for m, e in (first, second))
    if (first[0] and not x) or (second[0] and not y):
        raise ConicTangencyError('non_finite')
    length = math.hypot(x, y)
    return (x/length, y/length), (length, exponent)


def _scaled_sum(terms):
    """Sum exact binary significands before the final binary64 rounding.

    A common floating scale can erase a small term before larger terms
    cancel. Integer significands retain it, with bounded size for binary64
    inputs (about 4200 bits). A third term component is a binary exponent.
    """
    products = []
    for term in terms:
        a, b = term[:2]
        an, ad = float(a).as_integer_ratio()
        bn, bd = float(b).as_integer_ratio()
        if an and bn:
            exponent = (term[2] if len(term) == 3 else 0)-ad.bit_length()-bd.bit_length()+2
            products.append((an*bn, exponent))
    if not products:
        return 0.0, 0
    exponent = min(e for _, e in products)
    total = sum(n << (e-exponent) for n, e in products)
    sign = -1 if total < 0 else 1
    total = abs(total)
    shift = max(0, total.bit_length()-53)
    head = total >> shift
    if shift:
        remainder = total-(head << shift)
        halfway = 1 << (shift-1)
        if remainder > halfway or (remainder == halfway and head & 1):
            head += 1
    m, e = math.frexp(float(sign*head))
    return m, e+exponent+shift


def _local(frame, point, origin):
    x, y = point
    cx, cy = origin
    ux, uy = frame.axis
    return (_scaled_sum(((x, ux), (y, uy), (-cx, ux), (-cy, uy))),
            _scaled_sum(((x, -uy), (y, ux), (cx, uy), (-cy, ux))))


def _divide(value, denominators):
    m, e = _ratio((value[0],), denominators)
    return m, e+value[1]


def _line(frame, normal, offset=(0.0, 0)):
    """Project the world origin onto n·(X-origin)=offset.

    The world offset may exceed binary64 even when both components of its
    projection are finite. Scale before summing and apply the normal before
    restoring the exponent, retaining compensated cancellation.
    """
    nx, ny = _unit(*normal)
    cx, cy = frame.origin
    h, exponent = _scaled_sum(((nx, cx), (ny, cy), (offset[0], 1.0, offset[1])))
    mx, ex = _ratio((nx, h))
    my, ey = _ratio((ny, h))
    px, py = math.ldexp(mx, ex+exponent), math.ldexp(my, ey+exponent)
    _finite(px, py)
    if h and px == py == 0:
        raise ConicTangencyError('non_finite')
    return {'p': [px+0.0, py+0.0], 'dir': [-ny+0.0, nx+0.0]}


def from_circle(value):
    f = _frame(value)
    return {'kind': 'ellipse', 'c': list(f.origin), 'axis': [1.0, 0.0], 'a': f.a, 'b': f.a}


def directrices(value):
    f = _frame(value)
    if f.kind == 'parabola':
        return [_line(f, f.axis, _ratio((-f.a,), (2.0,)))]
    if f.kind == 'ellipse':
        if f.a == f.b:
            raise ConicTangencyError('no_directrix')
        if f.b > f.a:
            raise ConicTangencyError('degenerate_conic')
        eccentricity = math.sqrt((f.a-f.b)/f.a)*math.sqrt(1+f.b/f.a)
        offset = _ratio((f.a,), (eccentricity,))
    else:
        scale = max(f.a, f.b)
        offset = _ratio((f.a, f.a), (scale, math.hypot(f.a/scale, f.b/scale)))
    m, e = offset
    # Build the full set before the adapter applies output capacity.
    out = [_line(f, f.axis, (m, e)), _line(f, f.axis, (-m, e))]
    if out[0]['p'] == out[1]['p']:
        raise ConicTangencyError('non_finite')
    return out


def asymptotes(value):
    f = _frame(value)
    if f.kind != 'hyperbola':
        raise ConicTangencyError('no_asymptote')
    scale = max(f.a, f.b)
    a, b = f.a/scale, f.b/scale
    if not a or not b:
        raise ConicTangencyError('non_finite')
    out = []
    for sign in (1, -1):
        dx, dy = _unit(*f.vector(sign*a, b))
        out.append(_line(f, (dy, -dx)))
    first, second = out[0]['dir'], out[1]['dir']
    if first == second or first == [-v for v in second]:
        raise ConicTangencyError('non_finite')
    return out


def polar(value, point):
    f = _frame(value)
    _finite(*point)
    u, v = _local(f, point, f.origin)
    if f.kind == 'parabola':
        local, norm = _normal(_ratio((-f.a,)), v)
        rhs = _ratio((f.a, u[0]), (norm[0],))
        rhs = rhs[0], rhs[1]+u[1]-norm[1]
    else:
        if u[0] == v[0] == 0:
            raise ConicTangencyError('no_finite_line')
        sign = 1 if f.kind == 'ellipse' else -1
        local, norm = _normal(_divide(u, (f.a, f.a)),
                              _divide((sign*v[0], v[1]), (f.b, f.b)))
        rhs = _ratio((1.0,), (norm[0],))
        rhs = rhs[0], rhs[1]-norm[1]
    return _line(f, f.vector(*local), rhs)


def conjugate_diameter(value, direction, scalar_tol, start=(0.0, 0.0)):
    f = _frame(value)
    _finite(*direction)
    _finite(*start)
    if tuple(direction) == tuple(start):
        raise ConicTangencyError('invalid_parameter')
    # Do not normalize d: a small component can disappear before a later
    # axis ratio makes it significant. Only its sign and ratio matter.
    du, dv = _local(f, direction, start)
    if f.kind == 'parabola':
        if dv[0] == 0:
            raise ConicTangencyError('no_finite_line')
        normal = f.vector(0.0, math.copysign(1.0, dv[0]))
        rhs = _ratio((f.a, du[0]), (abs(dv[0]),))
        rhs = rhs[0], rhs[1]+du[1]-dv[1]
    else:
        sign = 1 if f.kind == 'ellipse' else -1
        local, _ = _normal(_divide(du, (f.a, f.a)),
                           _divide((sign*dv[0], dv[1]), (f.b, f.b)))
        normal, rhs = f.vector(*local), (0.0, 0)
    nx, ny = normal
    sign = nx if abs(nx) > scalar_tol else ny
    if sign < 0:
        normal = -nx, -ny
        rhs = -rhs[0], rhs[1]
    return _line(f, normal, rhs)
