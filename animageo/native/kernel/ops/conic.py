"""Conics (registry 1.6; docs/native/ops/conic.*.md).

Constructions: ``conic.ellipse_foci_point``, ``conic.hyperbola_foci_point``,
``conic.parabola_focus_directrix``, ``conic.five_points``, ``conic.equation``;
parts: ``conic.center``, ``conic.foci``, ``conic.vertices``, ``conic.axes``;
``intersect.line_conic``. The value and the classification are
:mod:`..conic`.
"""
from __future__ import annotations

import math

from ...expr import ExprError, compile_function
from .. import conic as geo
from ..values import Detailed, Undefined
from . import op
from .intersect import carrier
from .line import line_through

DOUBLE = {'multiplicity': 2}


def _xy(inp) -> tuple:
    v = inp.value
    return float(v['x']), float(v['y'])


def _point(xy) -> dict:
    return {'x': xy[0], 'y': xy[1]}


@op('conic.ellipse_foci_point')
def ellipse_foci_point(args, ctx):
    x1, y1 = _xy(args['f1'])
    x2, y2 = _xy(args['f2'])
    px, py = _xy(args['through'])
    tol = ctx.tol.decide_length
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    half = dist / 2
    a = (math.hypot(px - x1, py - y1) + math.hypot(px - x2, py - y2)) / 2
    ctx.decide('degenerate', a - half, tol)
    if a - half <= tol:
        return {'conic': Undefined('degenerate_conic')}
    centre = [(x1 + x2) / 2, (y1 + y2) / 2]
    ctx.decide('circle', dist, tol)
    if dist <= tol:
        return {'conic': {'kind': 'ellipse', 'c': centre, 'axis': [1.0, 0.0], 'a': a, 'b': a}}
    b = math.sqrt((a - half) * (a + half))
    return {'conic': {'kind': 'ellipse', 'c': centre, 'axis': [dx / dist, dy / dist], 'a': a, 'b': b}}


@op('conic.hyperbola_foci_point')
def hyperbola_foci_point(args, ctx):
    x1, y1 = _xy(args['f1'])
    x2, y2 = _xy(args['f2'])
    px, py = _xy(args['through'])
    tol = ctx.tol.decide_length
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    ctx.decide('coincident_points', dist, tol)
    if dist <= tol:
        return {'conic': Undefined('coincident_points')}
    half = dist / 2
    a = abs(math.hypot(px - x1, py - y1) - math.hypot(px - x2, py - y2)) / 2
    ctx.decide('degenerate', a, tol)
    ctx.decide('degenerate', half - a, tol)
    if a <= tol or half - a <= tol:
        return {'conic': Undefined('degenerate_conic')}
    b = math.sqrt((half - a) * (half + a))
    return {'conic': {'kind': 'hyperbola', 'c': [(x1 + x2) / 2, (y1 + y2) / 2], 'axis': [dx / dist, dy / dist],
                      'a': a, 'b': b}}


@op('conic.parabola_focus_directrix')
def parabola_focus_directrix(args, ctx):
    fx, fy = _xy(args['focus'])
    c = carrier(args['directrix'], ctx)
    if isinstance(c, Undefined):
        return {'conic': c}
    tol = ctx.tol.decide_length
    side = (fx - c.px) * c.dy - (fy - c.py) * c.dx          # signed distance, + to the right of dir
    ctx.decide('degenerate', side, tol)
    if abs(side) <= tol:
        return {'conic': Undefined('degenerate_conic')}
    p = abs(side)
    ux = c.dy if side > 0 else -c.dy                         # the normal from the directrix to the focus
    uy = -c.dx if side > 0 else c.dx
    return {'conic': {'kind': 'parabola', 'vertex': [fx - (p / 2) * ux, fy - (p / 2) * uy], 'axis': [ux, uy],
                      'p': p}}


@op('conic.five_points')
def five_points(args, ctx):
    points = [_xy(args[slot]) for slot in ('a', 'b', 'c', 'd', 'e')]
    solved = geo.five_point_coeffs(points, ctx)
    if isinstance(solved, Undefined):
        return {'conic': solved}
    coeffs, frame = solved
    return {'conic': geo.from_coeffs(coeffs, frame, ctx)}


def equation_function(ast, refs):
    """``q(x, y)`` of the tree, ``None`` where it has no value."""
    body = compile_function(ast, refs, vars=('x', 'y'))

    def q(x, y):
        try:
            return body(x, y)
        except ExprError:
            return None
    return q


@op('conic.equation')
def equation(args, ctx):
    refs = [float(r.value['value']) for r in args.get('refs') or []]
    try:
        q = equation_function(args['expr'].value, refs)
    except ExprError:
        return {'conic': Undefined('not_quadratic')}
    read = geo.equation_coeffs(q, ctx)
    if isinstance(read, Undefined):
        return {'conic': read}
    coeffs, frame = read
    return {'conic': geo.from_coeffs(coeffs, frame, ctx)}


@op('conic.center')
def center(args, ctx):
    value = args['conic'].value
    if value['kind'] == 'parabola':
        return {'center': Undefined('not_central')}
    return {'center': _point(value['c'])}


@op('conic.foci')
def conic_foci(args, ctx):
    fs = geo.foci(args['conic'].value)
    if len(fs) == 1:
        return {'first': _point(fs[0]), 'second': Undefined('branch_absent')}
    return {'first': _point(fs[0]), 'second': _point(fs[1])}


VERTEX_SLOTS = ('first', 'second', 'third', 'fourth')


@op('conic.vertices')
def conic_vertices(args, ctx):
    vs = geo.vertices(args['conic'].value)
    return {slot: _point(vs[k]) if k < len(vs) else Undefined('branch_absent') for k, slot in enumerate(VERTEX_SLOTS)}


@op('conic.axes')
def axes(args, ctx):
    value = args['conic'].value
    ux, uy = value['axis']
    nx, ny = geo.normal(value['axis'])
    if value['kind'] == 'parabola':
        vx, vy = value['vertex']
        return {'focal': line_through(vx, vy, ux, uy), 'conjugate': Undefined('branch_absent')}
    cx, cy = value['c']
    return {'focal': line_through(cx, cy, ux, uy), 'conjugate': line_through(cx, cy, nx, ny)}


@op('intersect.line_conic')
def line_conic(args, ctx):
    c = carrier(args['line'], ctx)
    if isinstance(c, Undefined):
        return {'first': c, 'second': c}
    found = geo.line_params(args['conic'].value, c, ctx)
    if isinstance(found, str):
        return {'first': Undefined(found), 'second': Undefined(found)}
    tol = ctx.tol.decide_length
    out = []
    for t, double in found:
        if c.ray or c.length is not None:
            ctx.decide('outside_part', t, tol)
            if c.length is not None:
                ctx.decide('outside_part', t - c.length, tol)
            if t < -tol or (c.length is not None and t > c.length + tol):
                out.append(Undefined('outside_part', {'slot': 'line'}))
                continue
        point = {'x': c.px + t * c.dx, 'y': c.py + t * c.dy}
        out.append(Detailed(point, dict(DOUBLE)) if double else point)
    if len(out) == 1:
        out.append(Undefined('branch_absent'))
    return {'first': out[0], 'second': out[1]}
