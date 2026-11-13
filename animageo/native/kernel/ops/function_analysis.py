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


@op('function.root_near')
def root_near(args, ctx):
    from ..function_analysis_numeric import Search

    try:
        x = Search(args['function'].value, ctx).near(float(args['start'].value['value']))
        return {'root': {'x': x, 'y': 0.0}}
    except AnalysisError as exc:
        return {'root': Undefined(exc.reason, {'stage': exc.stage})}


def _interval(args, ctx, mode):
    from ..function_analysis_numeric import Search

    single = mode == 'root_interval'
    extrema = mode == 'extrema_interval'
    count = 1 if single else repeat_count(args.get('count'))
    if not count:
        return {}
    base = 'extremum' if extrema else 'root'
    slots = ['root'] if single else [f'{base}.{k}' for k in range(1, count + 1)]
    try:
        function = args['function'].value
        a = float(args['a'].value['value'])
        b = float(args['b'].value['value'])
        lo, hi = function['domain']
        a = max(a, lo) if lo is not None else a
        b = min(b, hi) if hi is not None else b
        ctx.decide('empty_range', b - a, ctx.tol.decide_length)
        if b - a <= ctx.tol.decide_length:
            raise AnalysisError('empty_range', 'pieces')
        search = Search(function, ctx)
        if single:
            return {'root': {'x': search.root_interval(a, b), 'y': 0.0}}
        found = search.extrema(a, b) if extrema else search.roots(a, b)
    except AnalysisError as exc:
        return {slot: Undefined(exc.reason, {'stage': exc.stage}) for slot in slots}
    out = {}
    for k, slot in enumerate(slots):
        if k >= len(found):
            out[slot] = Undefined('branch_absent' if found else 'no_extremum' if extrema else 'no_root')
        else:
            x, y, kind = found[k]
            detail = {'found': len(found)}
            if extrema:
                detail['kind'] = kind
            out[slot] = Detailed({'x': x, 'y': y}, detail)
    return out


@op('function.root_interval')
def root_interval(args, ctx):
    return _interval(args, ctx, 'root_interval')


@op('function.roots_interval')
def roots_interval(args, ctx):
    return _interval(args, ctx, 'roots_interval')


@op('function.extrema_interval')
def extrema_interval(args, ctx):
    return _interval(args, ctx, 'extrema_interval')
