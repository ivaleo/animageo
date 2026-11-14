"""Geometric checks for every defined conic tangent/contact pair."""
import math

from .checks import register_check
from .tangency_conic import ConicTangencyError, curve_residual, gradient, line_distance
from .values import Detailed


def _value(value):
    return value.value if isinstance(value, Detailed) else value


def _pairs(args, result):
    if 'line' in result:
        line = _value(result['line'])
        if isinstance(line, dict):
            point = args['point'].value
            yield line, (point['x'], point['y'])
        return
    for slot in result:
        if not slot.startswith('tangent.'):
            continue
        line = _value(result[slot])
        point = _value(result.get('touch.'+slot.split('.')[1]))
        if isinstance(line, dict) and isinstance(point, dict):
            yield line, (point['x'], point['y'])


def through_point(args, result, tol):
    p = args['point'].value
    return max((line_distance((p['x'], p['y']), line) for line, q in _pairs(args, result)), default=0.0)


def on_curve(args, result, tol):
    try:
        return max((curve_residual(args['conic'].value, q) for line, q in _pairs(args, result)), default=0.0)
    except (ConicTangencyError, ArithmeticError, ValueError):
        return math.inf


def tangent(args, result, tol):
    error = 0.0
    try:
        for line, q in _pairs(args, result):
            nx, ny = gradient(args['conic'].value, q)
            dx, dy = line['dir']
            error = max(error, line_distance(q, line), abs(nx*dx+ny*dy)*tol.scale,
                        abs(math.hypot(dx, dy)-1)*tol.scale)
    except (ConicTangencyError, ArithmeticError, ValueError):
        return math.inf
    return error


def parallel(args, result, tol):
    dx, dy = args['base'].value['dir']
    return max((abs(dx*line['dir'][1]-dy*line['dir'][0])*tol.scale
                for line, q in _pairs(args, result)), default=0.0)


for _op in ('line.tangent_conic_at', 'line.tangents_from_point_conic', 'line.tangents_parallel_conic'):
    register_check(_op, 'on_curve')(on_curve)
    register_check(_op, 'tangent')(tangent)
    if _op == 'line.tangents_parallel_conic':
        register_check(_op, 'parallel')(parallel)
    else:
        register_check(_op, 'through_point')(through_point)
