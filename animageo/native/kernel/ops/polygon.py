"""``polygon.by_points`` (docs/native/ops/polygon.by_points.md)."""
from __future__ import annotations

import math

from . import op


@op('polygon.by_points')
def by_points(args, ctx):
    pts = [(v.value['x'], v.value['y']) for v in args['vertices']]
    n = len(pts)
    acc = 0.0
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[(i + 1) % n]
        acc = acc + (xi * yj - xj * yi)
    out = {'polygon': {'vertices': [[x, y] for x, y in pts], 'area': abs(acc) / 2}}
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out[f'side.{i + 1}'] = {'a': [ax, ay], 'b': [bx, by], 'length': math.hypot(bx - ax, by - ay)}
    return out
