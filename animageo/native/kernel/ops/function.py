"""Functions y = f(x) (registry 1.6; docs/native/ops/function.*.md).

``function.expr`` makes the value; ``function.root``, ``function.extremum``,
``intersect.function_function`` and ``intersect.function_line`` search it on
the grid of :mod:`..function`; ``point.on_function`` puts a free point on
the graph by its ``x``. Repeated outputs (``root.k``, ``extremum.k``,
``point.k``) follow the policy ``roots_ascending``: by ``x``, a double root
fills two slots.
"""
from __future__ import annotations

from ...registry import repeat_count
from ..function import evaluator, find_extrema, find_roots, search_interval
from ..numeric import default_bounds
from ..values import Detailed, Undefined
from . import op
from .intersect import carrier
from .locus import window

__all__ = ['DOUBLE', 'function_window']

DOUBLE = {'multiplicity': 2}


def _domain(value):
    lo, hi = value['domain']
    return lo, hi


def function_window(ctx) -> tuple:
    """``(x0, x1)`` of the window ``B4`` of the document bounds (the search
    range of the intersections of functions)."""
    box = window(ctx.bounds or default_bounds())
    return box[0], box[2]


def _slots(base: str, count: int, value) -> dict:
    return {f'{base}.{k}': value for k in range(1, count + 1)}


def _count(args, ctx):
    """:func:`~animageo.native.registry.repeat_count` of the ``count`` param
    (``0`` — not a whole number in ``[1, 100]``: the operation has no slots)."""
    return repeat_count(args.get('count'))


def _fill(base: str, count: int, found, point_of) -> dict:
    """Slots ``base.1 … base.count`` from ``found`` ``[(x, multiplicity, …)]``:
    a double root fills two slots; missing slots are ``branch_absent``;
    nothing found is ``no_root_in_window``."""
    if not found:
        return _slots(base, count, Undefined('no_root_in_window'))
    out = {}
    k = 1
    for item in found:
        point = point_of(item)
        times = item[1]
        for _ in range(times):
            if k > count:
                break
            out[f'{base}.{k}'] = Detailed(point, DOUBLE) if times == 2 and not isinstance(point, Undefined) \
                else point
            k += 1
    for j in range(k, count + 1):
        out[f'{base}.{j}'] = Undefined('branch_absent')
    return out


@op('function.expr')
def expr(args, ctx):
    refs = [float(r.value['value']) for r in args.get('refs') or []]
    lo = args.get('min')
    hi = args.get('max')
    if lo is not None and hi is not None:
        tol = ctx.tol.decide_length
        ctx.decide('empty_range', hi - lo, tol)
        if hi - lo <= tol:
            return {'function': Undefined('empty_range')}
    return {'function': {'expr': args['expr'].value, 'refs': refs, 'domain': [lo, hi]}}


def _interval(args, ctx, *values):
    a = float(args['a'].value['value'])
    b = float(args['b'].value['value'])
    cut = search_interval(a, b, *(_domain(v) for v in values))
    tol = ctx.tol.decide_length
    if cut is not None:
        ctx.decide('empty_range', cut[1] - cut[0], tol)
    if cut is None or cut[1] - cut[0] <= tol:
        return None
    return cut


@op('function.root')
def root(args, ctx):
    count = _count(args, ctx)
    if not count:
        return {}
    value = args['function'].value
    cut = _interval(args, ctx, value)
    if cut is None:
        return _slots('root', count, Undefined('empty_range'))
    found = find_roots(evaluator(value), cut[0], cut[1], ctx)
    if found is None:
        return _slots('root', count, Undefined('coincident'))
    return _fill('root', count, found, lambda item: {'x': item[0], 'y': 0.0})


@op('function.extremum')
def extremum(args, ctx):
    count = _count(args, ctx)
    if not count:
        return {}
    value = args['function'].value
    cut = _interval(args, ctx, value)
    if cut is None:
        return _slots('extremum', count, Undefined('empty_range'))
    found = find_extrema(evaluator(value), cut[0], cut[1], ctx)
    out = {}
    for k in range(1, count + 1):
        if k <= len(found):
            x, y, kind = found[k - 1]
            out[f'extremum.{k}'] = Detailed({'x': x, 'y': y}, {'kind': kind})
        else:
            out[f'extremum.{k}'] = Undefined('branch_absent' if found else 'no_root_in_window')
    return out


@op('intersect.function_function')
def function_function(args, ctx):
    count = _count(args, ctx)
    if not count:
        return {}
    first = args['first'].value
    second = args['second'].value
    x0, x1 = function_window(ctx)
    cut = search_interval(x0, x1, _domain(first), _domain(second))
    if cut is None:
        return _slots('point', count, Undefined('no_intersection'))
    f = evaluator(first)
    g = evaluator(second)

    def h(x):
        fx = f(x)
        if fx is None:
            return None
        gx = g(x)
        return None if gx is None else fx - gx
    found = find_roots(h, cut[0], cut[1], ctx)
    if found is None:
        return _slots('point', count, Undefined('coincident'))
    if not found:
        return _slots('point', count, Undefined('no_intersection'))

    def point_of(item):
        y = f(item[0])
        return Undefined('non_finite') if y is None else {'x': item[0], 'y': y}
    return _fill('point', count, found, point_of)


def _part(c, x, y, ctx):
    """``Undefined('outside_part')`` when ``(x, y)`` leaves the segment or ray ``c``, else ``None``."""
    tol = ctx.tol.decide_length
    s = (x - c.px) * c.dx + (y - c.py) * c.dy
    if c.ray:
        ctx.decide('outside_part', s, tol)
        return Undefined('outside_part', {'slot': 'line'}) if s < -tol else None
    if c.length is None:
        return None
    ctx.decide('outside_part', s, tol)
    ctx.decide('outside_part', s - c.length, tol)
    if s < -tol or s > c.length + tol:
        return Undefined('outside_part', {'slot': 'line'})
    return None


@op('intersect.function_line')
def function_line(args, ctx):
    count = _count(args, ctx)
    if not count:
        return {}
    value = args['function'].value
    c = carrier(args['line'], ctx)
    if isinstance(c, Undefined):
        return _slots('point', count, c)
    f = evaluator(value)
    ctx.decide('vertical', c.dx, ctx.tol.decide_scalar)
    if abs(c.dx) <= ctx.tol.decide_scalar:            # a vertical line: at most one point
        x = c.px
        y = f(x)
        if y is None:
            return _slots('point', count, Undefined('no_intersection'))
        point = _part(c, x, y, ctx) or {'x': x, 'y': y}
        return _fill('point', count, [(x, 1)], lambda item: point)
    x0, x1 = function_window(ctx)
    cut = search_interval(x0, x1, _domain(value))
    if cut is None:
        return _slots('point', count, Undefined('no_intersection'))
    slope = c.dy / c.dx

    def h(x):
        fx = f(x)
        return None if fx is None else fx - (c.py + (x - c.px) * slope)
    found = find_roots(h, cut[0], cut[1], ctx)
    if found is None:
        return _slots('point', count, Undefined('coincident'))
    if not found:
        return _slots('point', count, Undefined('no_intersection'))

    def point_of(item):
        x = item[0]
        y = c.py + (x - c.px) * slope
        return _part(c, x, y, ctx) or {'x': x, 'y': y}
    return _fill('point', count, found, point_of)    # a slot outside the part has no multiplicity


@op('point.on_function')
def on_function(args, ctx):
    value = args['function'].value
    x = float(ctx.input['value'])
    lo, hi = _domain(value)
    if lo is not None and x < lo:
        x = lo
    if hi is not None and x > hi:
        x = hi
    y = evaluator(value)(x)
    if y is None:
        return {'point': Undefined('out_of_domain')}
    return {'point': {'x': x, 'y': y}}
