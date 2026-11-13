"""``point.expression``, ``vector.expression`` (registry 1.10;
docs/native/ops/point.expression.md, docs/native/ops/vector.expression.md).

The typed tree of ``expr`` (docs/native/expr.md §6) over the items of
``refs`` — numbers, points, vectors (their components) and functions —
gives a pair ``(x, y)``: a point at it, or a vector from the origin to it.
"""
from __future__ import annotations

import math

from ...expr import ExprError, evaluate_typed
from ..values import Undefined
from . import op


def _pair(args):
    try:
        x, y = evaluate_typed(args['expr'].value, list(args['refs']), 'vec')
    except ExprError as exc:
        return Undefined(exc.reason)
    return x + 0.0, y + 0.0


@op('point.expression')
def point(args, ctx):
    v = _pair(args)
    if isinstance(v, Undefined):
        return {'point': v}
    return {'point': {'x': v[0], 'y': v[1]}}


@op('vector.expression')
def vector(args, ctx):
    v = _pair(args)
    if isinstance(v, Undefined):
        return {'vector': v}
    return {'vector': {'a': [0.0, 0.0], 'b': [v[0], v[1]], 'length': math.hypot(v[0], v[1])}}
