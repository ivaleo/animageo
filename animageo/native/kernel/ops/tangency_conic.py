"""Fixed-capacity adapters for finite conic tangents (registry 1.12)."""
from ...registry import repeat_count
from ..tangency_conic import ConicTangencyError, from_point, parallel, tangent_at
from ..values import Detailed, Undefined
from . import op


@op('line.tangent_conic_at')
def tangent_conic_at(args, ctx):
    point = args['point'].value
    try:
        return {'line': tangent_at(args['conic'].value, (point['x'], point['y']), ctx)}
    except ConicTangencyError as exc:
        return {'line': Undefined(exc.reason)}
    except (ArithmeticError, ValueError):
        return {'line': Undefined('non_finite')}


def _multiple(args, ctx, parallel_mode=False):
    count = repeat_count(args.get('count', 2))
    if not count:
        return {}
    slots = [f'{base}.{k}' for k in range(1, count+1) for base in ('tangent', 'touch')]
    try:
        value = args['conic'].value
        if parallel_mode:
            found = parallel(value, args['base'].value['dir'], ctx)
        else:
            point = args['point'].value
            found = from_point(value, (point['x'], point['y']), ctx)
    except ConicTangencyError as exc:
        return dict.fromkeys(slots, Undefined(exc.reason))
    except (ArithmeticError, ValueError):
        return dict.fromkeys(slots, Undefined('non_finite'))
    out = {}
    for k in range(1, count+1):
        if k > len(found):
            out[f'tangent.{k}'] = out[f'touch.{k}'] = Undefined('branch_absent')
        else:
            line, (x, y) = found[k-1]
            out[f'tangent.{k}'] = Detailed(line, {'found': len(found)})
            out[f'touch.{k}'] = Detailed({'x': x, 'y': y}, {'found': len(found)})
    return out


@op('line.tangents_from_point_conic')
def tangents_from_point_conic(args, ctx):
    return _multiple(args, ctx)


@op('line.tangents_parallel_conic')
def tangents_parallel_conic(args, ctx):
    return _multiple(args, ctx, parallel_mode=True)
