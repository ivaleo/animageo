"""``number.free``, ``number.angle``, ``number.expression`` (docs/native/ops/number.*.md)."""
from __future__ import annotations

from ...expr import ExprError, evaluate
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


@op('number.expression')
def expression(args, ctx):
    refs = [item.value['value'] for item in args['refs']]
    try:
        value = evaluate(args['expr'].value, refs)
    except ExprError as exc:
        return {'number': Undefined(exc.reason)}
    return {'number': {'value': value, 'unit': 'scalar'}}
