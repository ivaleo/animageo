"""``mark.equal_segments``, ``mark.equal_angles``, ``mark.right_angle``,
``mark.parallel`` (docs/native/ops/mark.*.md).

A mark carries only its kind and the number of ticks (chevrons); its
geometry is that of its arguments. Whether the marked relation holds is the
mandatory check of the op (``checks.py``): a ``failed`` check is a warning,
the mark stays defined.
"""
from __future__ import annotations

from ..values import Undefined
from . import op
from .angle import unit_sides

COUNTS = (1.0, 2.0, 3.0)


def _count_mark(kind, count):
    if count not in COUNTS:
        return {'mark': Undefined('invalid_parameter')}
    return {'mark': {'kind': kind, 'count': int(count)}}


@op('mark.equal_segments')
def equal_segments(args, ctx):
    return _count_mark('equal_segments', args['count'])


@op('mark.equal_angles')
def equal_angles(args, ctx):
    return _count_mark('equal_angles', args['count'])


@op('mark.parallel')
def parallel(args, ctx):
    return _count_mark('parallel', args['count'])


def direction(type_, value):
    """The direction of a straight element along which its chevrons point
    (not normalised): a segment or a vector from ``a`` to ``b``, a line or
    a ray its ``dir``."""
    if type_ in ('line', 'ray'):
        return float(value['dir'][0]), float(value['dir'][1])
    return float(value['b'][0]) - float(value['a'][0]), float(value['b'][1]) - float(value['a'][1])


def parallel_directions(items) -> list:
    """``parallel_direction`` of each item ``(type, value)`` of a parallel
    mark (``value`` ``None`` — not defined): ``'backward'`` where its
    direction makes a negative dot product with that of the reference — the
    first item of a direction of non-zero length — else ``'forward'``. The
    chevrons of every target then point the same way."""
    reference = None
    out = []
    for type_, value in items:
        d = direction(type_, value) if value is not None else (0.0, 0.0)
        if reference is None and (d[0] != 0.0 or d[1] != 0.0):
            reference = d
        dot = 0.0 if reference is None else d[0] * reference[0] + d[1] * reference[1]
        out.append('backward' if dot < 0 else 'forward')
    return out


@op('mark.right_angle')
def right_angle(args, ctx):
    sides = unit_sides(args['a'].value, args['vertex'].value, args['b'].value, ctx)
    if isinstance(sides, Undefined):
        return {'mark': sides}
    return {'mark': {'kind': 'right_angle', 'count': 1}}
