"""``number.free`` (docs/native/ops/number.free.md)."""
from __future__ import annotations

from ..values import Undefined
from . import op


@op('number.free')
def free(args, ctx):
    lo = args['min']
    hi = args['max']
    step = args['step']
    if lo is not None and hi is not None and lo > hi:
        return {'number': Undefined('invalid_parameter')}
    if step is not None and step <= 0:
        return {'number': Undefined('invalid_parameter')}
    v = float(ctx.input['value'])
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return {'number': {'value': v, 'unit': 'scalar'}}


@op('number.angle')
def angle(args, ctx):
    lo = args['min']
    hi = args['max']
    step = args['step']
    if lo is not None and hi is not None and lo > hi:
        return {'number': Undefined('invalid_parameter')}
    if step is not None and step <= 0:
        return {'number': Undefined('invalid_parameter')}
    v = float(ctx.input['value'])
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return {'number': {'value': v, 'unit': 'angle'}}
