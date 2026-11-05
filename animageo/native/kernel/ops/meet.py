"""Common points of conics (registry 1.8; docs/native/ops/intersect.conic_conic.md).

``intersect.conic_conic`` meets two inputs of the family ``conical``
(``conic``, ``circle``, ``arc``) by :mod:`..conic_meet`; the slots follow
the policy ``first_curve_order`` (:func:`..conic_meet.order_key`). Two
circular inputs give exactly the points of ``intersect.circle_circle``.
"""
from __future__ import annotations

from ..conic_meet import curve_meet, curve_of, order_key
from ..values import Detailed, Undefined
from . import op
from .intersect import _filter_both, circle_circle_points

__all__ = ['CONIC_SLOTS', 'conic_points']

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
