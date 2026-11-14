"""Geometric residuals for graph tangents, independent of line construction."""
import math

from .checks import _distance_to_line, register_check
from .function import evaluator
from .tangency import TangencyError, direction, graph_derivative


@register_check('line.tangent_function_at', 'on_curve')
def on_curve(args, result, tol):
    q = result['touch']
    x = args['x'].value['value']
    y = evaluator(args['function'].value)(q['x'])
    return math.inf if y is None else math.hypot(q['x'] - x, q['y'] - y)


@register_check('line.tangent_function_at', 'tangent')
def tangent(args, result, tol):
    q, line = result['touch'], result['line']
    try:
        y, slope = graph_derivative(args['function'].value, q['x'])
    except TangencyError:
        return math.inf
    dx, dy = direction(slope)
    ux, uy = line['dir']
    return max(_distance_to_line(q['x'], q['y'], line), abs(dx*uy - dy*ux)*tol.scale)
