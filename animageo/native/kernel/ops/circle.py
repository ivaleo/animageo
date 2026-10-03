"""``circle.center_point`` (docs/native/ops/circle.center_point.md)."""
from __future__ import annotations

import math

from ..values import Undefined
from . import op


@op('circle.center_point')
def center_point(args, ctx):
    c = args['center'].value
    t = args['through'].value
    cx, cy = c['x'], c['y']
    r = math.hypot(t['x'] - cx, t['y'] - cy)
    tol = ctx.tol.decide_length
    ctx.decide('nonpositive_radius', r, tol)
    if r <= tol:
        return {'circle': Undefined('nonpositive_radius')}
    return {'circle': {'c': [cx, cy], 'r': r}}
