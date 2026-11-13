"""Common points of conics (registry 1.8; docs/native/ops/intersect.conic_conic.md,
intersect.function_conic.md).

``intersect.conic_conic`` meets two inputs of the family ``conical``
(``conic``, ``circle``, ``arc``) by :mod:`..conic_meet`; the slots follow
the policy ``first_curve_order`` (:func:`..conic_meet.order_key`). Two
circular inputs give exactly the points of ``intersect.circle_circle``.
``intersect.function_conic`` searches ``measure(x, f(x))`` of the conic on
the grid of the graphs (policy ``roots_ascending``). :func:`pair_roots`
gives the solutions of a conic or a graph in a ``curve`` slot of
``intersect.nearest`` and ``intersect.other_than``.
"""
from __future__ import annotations

from ..conic_meet import curve_meet, curve_of, measure, order_key
from ..function import evaluator, find_roots, search_interval
from ..values import Detailed, Undefined
from . import op
from .conic import line_conic_points
from .function import (_count, _domain, _fill, _slots, function_function_roots, function_line_roots,
                       function_window)
from .intersect import _LINEAR, _filter_both, arc_filter, circle_circle_points

__all__ = ['CONIC_SLOTS', 'conic_points', 'graph_conic_roots', 'pair_roots']

CONIC_SLOTS = ('first', 'second', 'third', 'fourth')
DOUBLE = {'multiplicity': 2}
_CIRCULAR = ('circle', 'arc')


def conic_points(first, second, ctx) -> list:
    """Four values of the slots before the part filter: points (a tangency
    point twice as :class:`Detailed` with ``multiplicity 2``) in the order
    ``first_curve_order``, then ``branch_absent``; four equal reasons when
    there is no point (``no_intersection``, ``coincident``; ``concentric``
    for two circular inputs, as ``intersect.circle_circle``)."""
    if first.type in _CIRCULAR and second.type in _CIRCULAR:
        pair = circle_circle_points(first, second, ctx)
        if isinstance(pair[0], Undefined) and isinstance(pair[1], Undefined):
            return pair + [pair[0], pair[0]]
        return pair + [Undefined('branch_absent'), Undefined('branch_absent')]
    a = curve_of(first)
    b = curve_of(second)
    found = curve_meet(a, b, ctx)
    if found is None:
        return [Undefined('coincident')] * 4
    if not found:
        return [Undefined('no_intersection')] * 4
    key = order_key(first, a, b, ctx)
    ranked = sorted(((key(point), k) for k, (point, _) in enumerate(found)))
    out = []
    for _, k in ranked:
        point, mult = found[k]
        for _ in range(mult):
            out.append(Detailed(point, dict(DOUBLE)) if mult == 2 else point)
    out = out[:4]
    while len(out) < 4:
        out.append(Undefined('branch_absent'))
    return out


@op('intersect.conic_conic')
def conic_conic(args, ctx):
    first = args['first']
    second = args['second']
    values = _filter_both(conic_points(first, second, ctx), first, second, ctx)
    return dict(zip(CONIC_SLOTS, values))


def graph_conic_roots(value, inp, ctx):
    """``(found, f)`` of a graph and a ``conical`` input: ``found`` the roots
    ``[(x, multiplicity)]`` of ``measure(x, f(x))`` on the x-range of ``B4``
    cut by the domain, ascending; ``Undefined`` (``no_intersection``,
    ``coincident``) when there is none."""
    x0, x1 = function_window(ctx)
    cut = search_interval(x0, x1, _domain(value))
    if cut is None:
        return Undefined('no_intersection'), None
    curve = curve_of(inp)
    f = evaluator(value)

    def h(x):
        y = f(x)
        return None if y is None else measure(curve, x, y)
    found = find_roots(h, cut[0], cut[1], ctx)
    if found is None:
        return Undefined('coincident'), f
    if not found:
        return Undefined('no_intersection'), f
    return found, f


def _graph_point(f, x):
    y = f(x)
    return Undefined('non_finite') if y is None else {'x': x, 'y': y}


@op('intersect.function_conic')
def function_conic(args, ctx):
    count = _count(args, ctx)
    if not count:
        return {}
    conic = args['conic']
    found, f = graph_conic_roots(args['function'].value, conic, ctx)
    if isinstance(found, Undefined):
        return _slots('point', count, found)

    def point_of(item):
        return arc_filter(_graph_point(f, item[0]), conic, ctx, 'conic')
    return _fill('point', count, found, point_of)      # a slot off the arc has no multiplicity


def _expand(got) -> list:
    """The values of ``(found, point_of)`` in order, a double root twice; a
    single ``Undefined`` as ``[it]``."""
    if isinstance(got, Undefined):
        return [got]
    found, point_of = got
    out = []
    for item in found:
        out.extend([point_of(item)] * item[1])
    return out


def pair_roots(first, second, ctx) -> list:
    """The solutions of two ``curve`` inputs, at least one a conic or a graph
    (registry 1.8), before the arc filter, in the order of the pair's
    operation: graph × graph and graph × linear as
    ``intersect.function_function`` / ``intersect.function_line``, graph ×
    conic, circle or arc as ``intersect.function_conic`` (all by ``x``),
    linear × conic as ``intersect.line_conic`` (``line_param_order``), conic ×
    conic, circle or arc as ``intersect.conic_conic`` (``first_curve_order``).
    ``detail.slot`` of an ``outside_part`` names ``first`` or ``second``."""
    if first.type == 'function' and second.type == 'function':
        return _expand(function_function_roots(first.value, second.value, ctx))
    if first.type == 'function' or second.type == 'function':
        fn, other, slot = (first, second, 'second') if first.type == 'function' else (second, first, 'first')
        if other.type in _LINEAR:
            return _expand(function_line_roots(fn.value, other, ctx, slot))
        found, f = graph_conic_roots(fn.value, other, ctx)
        if isinstance(found, Undefined):
            return [found]
        return _expand((found, lambda item: _graph_point(f, item[0])))
    if first.type in _LINEAR:
        return line_conic_points(first, second, ctx, 'first')
    if second.type in _LINEAR:
        return line_conic_points(second, first, ctx, 'second')
    return conic_points(first, second, ctx)
