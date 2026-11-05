"""Common points of conics (registry 1.8; docs/native/ops/intersect.conic_conic.md,
intersect.function_conic.md).

``intersect.conic_conic`` meets two inputs of the family ``conical``
(``conic``, ``circle``, ``arc``) by :mod:`..conic_meet`; the slots follow
the policy ``first_curve_order`` (:func:`..conic_meet.order_key`). Two
circular inputs give exactly the points of ``intersect.circle_circle``.
``intersect.function_conic`` searches ``measure(x, f(x))`` of the conic on
the grid of the graphs (policy ``roots_ascending``).
"""
from __future__ import annotations

from ..conic_meet import curve_meet, curve_of, measure, order_key
from ..function import evaluator, find_roots, search_interval
from ..values import Detailed, Undefined
from . import op
from .function import _count, _domain, _fill, _slots, function_window
from .intersect import _filter_both, arc_filter, circle_circle_points

__all__ = ['CONIC_SLOTS', 'conic_points', 'graph_conic_roots']

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
        y = f(item[0])
        if y is None:
            return Undefined('non_finite')
        return arc_filter({'x': item[0], 'y': y}, conic, ctx, 'conic')
    return _fill('point', count, found, point_of)      # a slot off the arc has no multiplicity
