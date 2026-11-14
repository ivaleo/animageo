"""Adapters for the implemented tangency operations (registry 1.12)."""
import math

from ..tangency import TangencyError, direction, graph_derivative
from ..values import Undefined
from . import op


@op('line.tangent_function_at')
def tangent_function_at(args, ctx):
    x = float(args['x'].value['value'])
    try:
        y, slope = graph_derivative(args['function'].value, x)
        dx, dy = direction(slope)
        # Normal projection avoids q dot dir overflowing for a line through
        # a very distant finite contact. Restore scale only per component.
        scale = max(abs(x), abs(y))
        offset = dy*(x/scale) - dx*(y/scale) if scale else 0.0
        line = {'p': [(dy*offset)*scale, (-dx*offset)*scale], 'dir': [dx, dy]}
        if not all(math.isfinite(v) for v in line['p'] + line['dir']):
            raise TangencyError('non_finite')
        return {'line': line, 'touch': {'x': x, 'y': y}}
    except TangencyError as exc:
        failure = Undefined(exc.reason)
        return {'line': failure, 'touch': failure}


@op('line.slope')
def slope(args, ctx):
    dx, dy = args['line'].value['dir']
    if abs(dx) <= ctx.tol.decide_scalar:
        return {'number': Undefined('vertical_line')}
    value = dy / dx
    return {'number': {'value': value + 0.0, 'unit': 'scalar'} if math.isfinite(value)
            else Undefined('non_finite')}
