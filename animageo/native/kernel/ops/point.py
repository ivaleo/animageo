"""``point.free``, ``point.midpoint`` (docs/native/ops/point.*.md)."""
from __future__ import annotations

from . import op


@op('point.free')
def free(args, ctx):
    x, y = ctx.input['value']
    return {'point': {'x': float(x), 'y': float(y)}}


@op('point.midpoint')
def midpoint(args, ctx):
    a = args['a'].value
    b = args['b'].value
    return {'point': {'x': (a['x'] + b['x']) / 2, 'y': (a['y'] + b['y']) / 2}}
