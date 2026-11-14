"""Fixed-capacity conic elements and the explicit owned circle adapter."""
from ...registry import repeat_count
from .. import conic_elements as geometry
from ..tangency_conic import ConicTangencyError
from ..values import Detailed, Undefined
from . import op
from .mark import direction


def _single(slot, fn, *args):
    try:
        return {slot: fn(*args)}
    except ConicTangencyError as exc:
        return {slot: Undefined(exc.reason)}
    except (ArithmeticError, ValueError):
        return {slot: Undefined('non_finite')}


@op('conic.from_circle')
def from_circle(args, ctx):
    return _single('conic', geometry.from_circle, args['circle'].value)


def _multiple(args, base, fn):
    count = repeat_count(args.get('count', 2))
    slots = [f'{base}.{k}' for k in range(1, count+1)]
    try:
        found = fn(args['conic'].value)
    except ConicTangencyError as exc:
        return dict.fromkeys(slots, Undefined(exc.reason))
    except (ArithmeticError, ValueError):
        return dict.fromkeys(slots, Undefined('non_finite'))
    return {slot: Detailed(found[k], {'found': len(found)}) if k < len(found)
            else Undefined('branch_absent') for k, slot in enumerate(slots)}


@op('conic.directrices')
def directrices(args, ctx):
    return _multiple(args, 'directrix', geometry.directrices)


@op('conic.asymptotes')
def asymptotes(args, ctx):
    return _multiple(args, 'asymptote', geometry.asymptotes)


@op('line.polar_conic')
def polar(args, ctx):
    p = args['point'].value
    return _single('line', geometry.polar, args['conic'].value, (p['x'], p['y']))


@op('line.conjugate_diameter')
def conjugate_diameter(args, ctx):
    d = args['direction']
    if d.type in ('segment', 'vector'):
        return _single('line', geometry.conjugate_diameter, args['conic'].value,
                       d.value['b'], ctx.tol.decide_scalar, d.value['a'])
    return _single('line', geometry.conjugate_diameter, args['conic'].value,
                   direction(d.type, d.value), ctx.tol.decide_scalar)
