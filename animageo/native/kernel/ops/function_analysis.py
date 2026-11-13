"""Fixed-slot adapters for function analysis (registry 1.11)."""
from ...registry import repeat_count
from ..function_analysis import AnalysisError, polynomial_points
from ..values import Detailed, Undefined
from . import op


def _polynomial(args, ctx, extrema=False):
    count = repeat_count(args.get('count'))
    if not count:
        return {}
    base = 'extremum' if extrema else 'root'
    try:
        found = polynomial_points(args['function'].value, ctx, extrema=extrema)
    except AnalysisError as exc:
        failure = Undefined(exc.reason, {'stage': exc.stage})
        return {f'{base}.{k}': failure for k in range(1, count + 1)}
    out = {}
    for k in range(1, count + 1):
        if k > len(found):
            out[f'{base}.{k}'] = Undefined('branch_absent' if found else
                                          'no_extremum' if extrema else 'no_root')
        else:
            x, y, kind = found[k - 1]
            detail = {'found': len(found)}
            if kind is not None:
                detail['kind'] = kind
            out[f'{base}.{k}'] = Detailed({'x': x, 'y': y}, detail)
    return out


@op('function.roots_polynomial')
def roots_polynomial(args, ctx):
    return _polynomial(args, ctx)


@op('function.extrema_polynomial')
def extrema_polynomial(args, ctx):
    return _polynomial(args, ctx, extrema=True)


@op('function.value')
def value(args, ctx):
    from ..function import evaluator

    y = evaluator(args['function'].value)(float(args['x'].value['value']))
    return {'number': Undefined('out_of_domain') if y is None else
            {'value': y + 0.0, 'unit': 'scalar'}}
