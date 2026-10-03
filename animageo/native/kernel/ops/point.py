"""``point.free``, ``point.midpoint``, ``point.on_path`` (docs/native/ops/point.*.md)."""
from __future__ import annotations

from ..paths import frame, point_at
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


@op('point.on_path')
def on_path(args, ctx):
    path = args['path']
    f = path.frame if path.frame is not None else frame(path.type, path.value)
    return {'point': point_at(f, float(ctx.input['value']))}
