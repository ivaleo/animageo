"""``mark.equal_segments``, ``mark.equal_angles``, ``mark.right_angle`` (docs/native/ops/mark.*.md).

A mark carries only its kind and the number of ticks; its geometry is that
of its arguments. Whether the marked equality holds is the mandatory check
of the op (``checks.py``): a ``failed`` check is a warning, the mark stays
defined.
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


@op('mark.right_angle')
def right_angle(args, ctx):
    sides = unit_sides(args['a'].value, args['vertex'].value, args['b'].value, ctx)
    if isinstance(sides, Undefined):
        return {'mark': sides}
    return {'mark': {'kind': 'right_angle', 'count': 1}}
