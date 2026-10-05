"""Registry 1.5: the elements of a triangle — ``triangle.altitude``,
``triangle.median``, ``triangle.bisector`` and the centres ``triangle.centroid``,
``triangle.incenter``, ``triangle.circumcenter``, ``triangle.orthocenter``,
``triangle.excenters`` (docs/native/ops/triangle.*.md).

The centres share the kernel functions of the circles: the incentre is the
centre of ``circle.incircle``, the circumcentre that of ``circle.three_points``
(vertex ``a`` first), the excentre that of ``circle.excircle`` — bit for bit
on the same inputs. The foot of an altitude is ``point.projection`` on the
carrier of the side (the same arithmetic).
"""
from __future__ import annotations

import math

from ..values import Input, Undefined
from . import op
from .circle import circumcenter, excircle, incircle
from .intersect import carrier

ALTITUDE_SLOTS = ('altitude', 'foot', 'extension')


def side_ends(side: Input):
    """The ends ``((ax, ay), (bx, by))`` of a side: the ends of a segment; for a
    line or a ray the two defining points of its producer frame
    (``line.by_points``: ``a``, ``b``; ``ray.by_points``: ``origin``,
    ``through``), passed by the evaluator in ``side.frame``; otherwise
    ``None`` (no ends)."""
    if side.type == 'segment':
        return tuple(side.value['a']), tuple(side.value['b'])
    return side.frame


@op('triangle.altitude')
def altitude(args, ctx):
    side = args['side']
    c = carrier(side, ctx)
    if isinstance(c, Undefined):
        return dict.fromkeys(ALTITUDE_SLOTS, c)
    v = args['vertex'].value
    vx, vy = v['x'], v['y']
    t = (vx - c.px) * c.dx + (vy - c.py) * c.dy
    hx = c.px + t * c.dx
    hy = c.py + t * c.dy
    tol = ctx.tol.decide_length
    h = math.hypot(vx - hx, vy - hy)
    ctx.decide('zero_length', h, tol)
    out = {
        'altitude': Undefined('zero_length') if h <= tol else {'a': [vx, vy], 'b': [hx, hy], 'length': h},
        'foot': {'x': hx, 'y': hy},
        'extension': Undefined('branch_absent'),
    }
    ends = side_ends(side)
    if ends is None:
        return out
    (ax, ay), (bx, by) = ends
    length = math.hypot(bx - ax, by - ay)
    if length <= tol:
        return out
    s = ((hx - ax) * (bx - ax) + (hy - ay) * (by - ay)) / length
    ctx.decide('outside_part', s, tol)
    ctx.decide('outside_part', s - length, tol)
    if s < 0 and -s > tol:
        out['extension'] = {'a': [ax, ay], 'b': [hx, hy], 'length': math.hypot(hx - ax, hy - ay)}
    elif s > length and s - length > tol:
        out['extension'] = {'a': [bx, by], 'b': [hx, hy], 'length': math.hypot(hx - bx, hy - by)}
    return out


@op('triangle.median')
def median(args, ctx):
    v = args['vertex'].value
    seg = args['side'].value
    (ax, ay), (bx, by) = seg['a'], seg['b']
    mx = (ax + bx) / 2
    my = (ay + by) / 2
    vx, vy = v['x'], v['y']
    m = math.hypot(vx - mx, vy - my)
    tol = ctx.tol.decide_length
    ctx.decide('zero_length', m, tol)
    return {
        'median': Undefined('zero_length') if m <= tol else {'a': [vx, vy], 'b': [mx, my], 'length': m},
        'midpoint': {'x': mx, 'y': my},
    }


@op('triangle.bisector')
def bisector(args, ctx):
    v = args['vertex'].value
    seg = args['side'].value
    vx, vy = v['x'], v['y']
    (bx, by), (cx, cy) = seg['a'], seg['b']
    lb = math.hypot(vx - bx, vy - by)
    lc = math.hypot(vx - cx, vy - cy)
    tol = ctx.tol.decide_length
    ctx.decide('coincident_points', lb, tol)
    ctx.decide('coincident_points', lc, tol)
    if lb <= tol or lc <= tol:
        none = Undefined('coincident_points')
        return {'bisector': none, 'foot': none}
    la = math.hypot(bx - cx, by - cy)
    longest = max(la, lb, lc)
    ctx.decide('collinear_points', longest, tol)
    cr = (bx - vx) * (cy - vy) - (by - vy) * (cx - vx)
    h = abs(cr) / longest if longest > tol else 0.0
    ctx.decide('collinear_points', h, tol)
    if longest <= tol or h <= tol:
        none = Undefined('collinear_points')
        return {'bisector': none, 'foot': none}
    w = lb + lc
    fx = (lc * bx + lb * cx) / w
    fy = (lc * by + lb * cy) / w
    return {
        'bisector': {'a': [vx, vy], 'b': [fx, fy], 'length': math.hypot(fx - vx, fy - vy)},
        'foot': {'x': fx, 'y': fy},
    }


@op('triangle.centroid')
def centroid(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    return {'point': {'x': ((a['x'] + b['x']) + c['x']) / 3, 'y': ((a['y'] + b['y']) + c['y']) / 3}}


@op('triangle.incenter')
def incenter(args, ctx):
    return {'point': incircle(args, ctx)['center']}


@op('triangle.circumcenter')
def circumcenter_point(args, ctx):
    o = circumcenter(args['a'].value, args['b'].value, args['c'].value, ctx)
    if isinstance(o, Undefined):
        return {'point': o}
    return {'point': {'x': o[0], 'y': o[1]}}


@op('triangle.orthocenter')
def orthocenter(args, ctx):
    a = args['a'].value
    b = args['b'].value
    c = args['c'].value
    o = circumcenter(a, b, c, ctx)
    if isinstance(o, Undefined):
        return {'point': o}
    return {'point': {'x': ((a['x'] + b['x']) + c['x']) - 2 * o[0],
                      'y': ((a['y'] + b['y']) + c['y']) - 2 * o[1]}}


@op('triangle.excenters')
def excenter(args, ctx):
    return {'center': excircle(args, ctx)['center']}
