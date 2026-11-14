"""Independent distance and bilinear checks of every defined conic element."""
import math

from .checks import register_check
from .conic_elements import _divide, _local, _normal, _ratio, _scaled_sum
from .ops.mark import direction
from .tangency_conic import ConicTangencyError, _dot, _frame, _sum_products, line_distance
from .values import Detailed


def _lines(result):
    for slot, value in result.items():
        if isinstance(value, Detailed):
            value = value.value
        if isinstance(value, dict) and 'dir' in value:
            yield slot, value


def _guard(fn):
    def check(args, result, tol):
        try:
            return fn(args, result, tol)
        except (ConicTangencyError, ArithmeticError, ValueError):
            return math.inf
    return check


@register_check('conic.from_circle', 'same_circle')
def same_circle(args, result, tol):
    c, v = args['circle'].value, result['conic']
    return max(math.hypot(c['c'][0]-v['c'][0], c['c'][1]-v['c'][1]),
               abs(c['r']-v['a']), abs(c['r']-v['b']),
               math.hypot(v['axis'][0]-1, v['axis'][1])*tol.scale)


@register_check('conic.directrices', 'focus_directrix')
@_guard
def focus_directrix(args, result, tol):
    f = _frame(args['conic'].value)
    if f.kind == 'parabola':
        c, e = f.a/2, 1.0
        samples = [(0, 0), (f.a/2, f.a), (f.a/2, -f.a)]
    else:
        c = (f.a*math.sqrt((f.a-f.b)/f.a)*math.sqrt(1+f.b/f.a)
             if f.kind == 'ellipse' else math.hypot(f.a, f.b))
        e = c/f.a
        samples = [(f.a, 0), (-f.a, 0), (0, f.b)] if f.kind == 'ellipse' else [(f.a, 0), (-f.a, 0), (f.a*math.sqrt(2), f.b)]
    error = 0.0
    for slot, line in _lines(result):
        sign = -1 if slot.endswith('.2') else 1
        for u, v in samples:
            dx, dy = line['dir']
            nu, nv = _dot(dy, -dx, *f.axis), _dot(dy, -dx, -f.axis[1], f.axis[0])
            h, exponent = _scaled_sum(((dy, line['p'][0]), (-dx, line['p'][1]),
                                       (-dy, f.origin[0]), (dx, f.origin[1])))
            h = math.ldexp(h, exponent)
            distance = math.hypot(u-sign*c, v)
            off_line = abs(_sum_products(((nu, u), (nv, v), (-1.0, h))))
            # Both variants measure a distance, avoiding e*distance overflow.
            residual = abs(distance/e-off_line) if e > 1 else abs(distance-e*off_line)
            error = max(error, residual)
        dx, dy = line['dir']
        error = max(error, math.hypot(dx+f.axis[1], dy-f.axis[0])*tol.scale)
    return error


@_guard
def through_center(args, result, tol):
    f = _frame(args['conic'].value)
    return 0.0 if f.kind == 'parabola' else max((line_distance(f.origin, line) for _, line in _lines(result)), default=0.0)


@register_check('conic.asymptotes', 'asymptotic_direction')
@_guard
def asymptotic_direction(args, result, tol):
    f = _frame(args['conic'].value)
    scale = max(f.a, f.b)
    a, b = f.a/scale, f.b/scale
    length = math.hypot(a, b)
    a, b = a/length, b/length
    error = 0.0
    for slot, line in _lines(result):
        dx, dy = line['dir']
        u = _dot(dx, dy, *f.axis)
        v = _dot(dx, dy, -f.axis[1], f.axis[0])
        expected_u = -a if slot.endswith('.2') else a
        error = max(error, math.hypot(u-expected_u, v-b)*tol.scale,
                    abs(math.hypot(dx, dy)-1)*tol.scale)
    return error


def _bilinear(args, result, tol, diameter=False):
    f = _frame(args['conic'].value)
    if diameter:
        d = args['direction']
        if d.type in ('segment', 'vector'):
            u, v = _local(f, d.value['b'], d.value['a'])
        else:
            u, v = _local(f, direction(d.type, d.value), (0, 0))
    else:
        p = args['point'].value
        u, v = _local(f, (p['x'], p['y']), f.origin)
    if f.kind == 'parabola':
        first, second = ((0.0, 0), v) if diameter else (_ratio((-f.a,)), v)
        rhs = _ratio((f.a, u[0]))
        rhs = rhs[0], rhs[1]+u[1]
    else:
        sign = 1 if f.kind == 'ellipse' else -1
        first, second = _divide(u, (f.a, f.a)), _divide((sign*v[0], v[1]), (f.b, f.b))
        rhs = (0.0, 0) if diameter else _ratio((1.0,))
    normal, norm = _normal(first, second)
    target = rhs[0]/norm[0], rhs[1]-norm[1]
    error = 0.0
    for _, line in _lines(result):
        s, t = _local(f, line['p'], f.origin)
        residual, exponent = _scaled_sum(((normal[0], s[0], s[1]), (normal[1], t[0], t[1]), (-target[0], 1.0, target[1])))
        residual = math.ldexp(abs(residual), exponent)
        nx, ny = f.vector(*normal)
        dx, dy = line['dir']
        angular = abs(_sum_products(((nx, dx), (ny, dy))))*tol.scale
        if not diameter:
            angular = max(angular, math.hypot(dx+ny, dy-nx)*tol.scale)
        error = max(error, residual, angular, abs(math.hypot(dx, dy)-1)*tol.scale)
    return error


@register_check('line.polar_conic', 'polar_incidence')
@_guard
def polar_incidence(args, result, tol):
    return _bilinear(args, result, tol)


@register_check('line.conjugate_diameter', 'conjugacy')
@_guard
def conjugacy(args, result, tol):
    return _bilinear(args, result, tol, diameter=True)


for _op in ('conic.asymptotes', 'line.conjugate_diameter'):
    register_check(_op, 'through_center')(through_center)
