"""Analytical fixtures for finite-piece, interval and near-root searches."""
import math


def scenes():
    from .curves_fixtures import _Doc, _num, _ref, X, n, o, r, sq, call
    from .function_analysis_fixtures import _point, _absent, _set

    def condition(sign):
        return {'cmp': sign, 'args': [X, n(0)]}

    def choose(cond, then, other=None):
        return {'if': [cond, then] + ([] if other is None else [other])}

    def argument(v):
        return _ref(v) if isinstance(v, str) else _num(v)

    def near(d, f, key, start=0):
        d.op('op_result_' + key, 'function.root_near', {'function': _ref(f), 'start': argument(start)},
             [('root', key, 'point')])

    def interval(d, f, key, name='roots_interval', a=-2, b=2, count=3):
        single = name == 'root_interval'
        base = 'extremum' if name == 'extrema_interval' else 'root'
        args = {'function': _ref(f), 'a': argument(a), 'b': argument(b)}
        if not single:
            args['count'] = _num(count)
        outputs = [('root', key, 'point')] if single else [
            (f'{base}.{k}', f'{key}{k}', 'point') for k in range(1, count + 1)]
        d.op('op_result_' + key, 'function.' + name, args, outputs)

    def one(d, answers):
        return d, [{'name': 'analytic'}], {'analytic': answers}

    out = []
    d = _Doc('function_root_near').number('start', 1)
    d.function('f', o('-', sq(X), n(2)))
    d.function('hole', o('/', o('-', X, n(1)), X))
    d.function('cubic', o('+', o('-', o('^', X, n(3)), o('*', n(2), X)), n(2)))
    near(d, 'f', 'N', 'start')
    near(d, 'hole', 'Hole')
    near(d, 'cubic', 'Cycle')
    cbrt = lambda v: math.copysign(abs(v) ** (1 / 3), v)
    cubic_root = cbrt(-1 + math.sqrt(19 / 27)) + cbrt(-1 - math.sqrt(19 / 27))
    cases, answers = [], {}
    for name, start, x in [('positive', 1, math.sqrt(2)), ('negative', -1, -math.sqrt(2)),
                            ('zero_slope', 0, math.sqrt(2))]:
        cases.append({'name': name, 'inputs': {'start': _num(start)}})
        answers[name] = {'N': _point(x), 'Hole': _point(1), 'Cycle': _point(cubic_root)}
    out.append((d, cases, answers))

    d = _Doc('function_root_interval').number('a', 0).number('b', 1.5)
    p = o('*', o('-', X, n(1)), o('-', X, n(3)))
    d.function('p', p).function('square', sq(X))
    d.function('cubic', o('*', o('*', o('-', X, n(1)), o('-', X, n(2))), o('-', X, n(4))))
    d.function('partial', choose(condition('>'), o('-', X, n(1))))
    d.function('pole', o('/', o('-', X, n(1)), X))
    d.function('jump', choose(condition('<'), o('+', X, n(1)), o('-', X, n(1))))
    interval(d, 'p', 'Live', 'root_interval', 'a', 'b')
    interval(d, 'square', 'Touch', 'root_interval', -1, 1)
    interval(d, 'p', 'Fallback', 'root_interval', 0, 4)
    interval(d, 'cubic', 'Bisected', 'root_interval', 0, 5)
    interval(d, 'partial', 'Partial', 'root_interval', 0, 2)
    interval(d, 'pole', 'Pole', 'root_interval')
    interval(d, 'jump', 'Jump', 'root_interval')
    cases, answers = [], {}
    for name, a, b, x in [('left', 0, 1.5, 1), ('right', 2.5, 4, 3), ('fallback', 0, 4, 1),
                          ('reversed', 4, 0, None)]:
        cases.append({'name': name, 'inputs': {'a': _num(a), 'b': _num(b)}})
        answers[name] = {'Live': _point(x) if x is not None else _absent('empty_range', stage='pieces'),
                         'Touch': _point(0), 'Fallback': _point(1), 'Bisected': _point(4),
                         'Partial': _point(1), 'Pole': _point(1), 'Jump': _point(-1)}
    out.append((d, cases, answers))

    d = _Doc('function_roots_interval')
    answer = {}
    for f, tree, key, a, b, roots, count in [
        ('sine', call('sin', X), 'Sine', -4, 4, [-math.pi, 0, math.pi], 1),
        ('touch', sq(call('sin', X)), 'Touch', -4, 4, [-math.pi, 0, math.pi], 5),
        ('tangent', call('tan', X), 'Tan', -4, 4, [-math.pi, 0, math.pi], 3),
        ('partial', choose(condition('>'), o('-', X, n(1))), 'Partial', -2, 2, [1], 3),
        ('pole', o('/', o('-', X, n(1)), X), 'Pole', -2, 2, [1], 3),
        ('jump', choose(condition('<'), o('+', X, n(1)), o('-', X, n(1))), 'Jump', -2, 2, [-1, 1], 3),
        ('reciprocal', o('/', n(1), X), 'Missing', -2, 2, [], 3),
        ('open_edge', choose(condition('>'), X), 'Open', -2, 2, [], 3)]:
        d.function(f, tree)
        interval(d, f, key, a=a, b=b, count=count)
        answer.update(_set(key, roots, count))
    out.append(one(d, answer))

    d = _Doc('function_extrema_interval')
    answer = {}
    for f, tree, key, a, b, expected, count in [
        ('sine', call('sin', X), 'Sine', 0, 2 * math.pi,
         [(math.pi / 2, 1, 'max'), (3 * math.pi / 2, -1, 'min')], 3),
        ('cusp', call('abs', X), 'Cusp', -1, 1, [(0, 0, 'min')], 3),
        ('partial', choose(condition('>'), sq(o('-', X, n(1)))), 'Partial', -2, 2, [(1, 0, 'min')], 3),
        ('continuous_join', choose(condition('<'), o('neg', X), X), 'Join', -1, 1, [(0, 0, 'min')], 3),
        ('tangent', call('tan', X), 'Tan', -4, 4, [], 3),
        ('reciprocal', o('/', n(1), X), 'Pole', -2, 2, [], 3),
        ('monotone', X, 'Monotone', -2, 2, [], 3),
        ('plateau', n(1), 'Plateau', -2, 2, [], 3),
        ('endpoint', sq(X), 'Endpoint', 0, 2, [], 3)]:
        d.function(f, tree)
        interval(d, f, key, 'extrema_interval', a, b, count)
        answer.update(_set(key, expected, count, extrema=True))
    interval(d, 'sine', 'One', 'extrema_interval', 0, 2 * math.pi, 1)
    answer.update(_set('One', [(math.pi / 2, 1, 'max'), (3 * math.pi / 2, -1, 'min')], 1, extrema=True))
    out.append(one(d, answer))

    d = _Doc('function_search_constants').number('c', 1).function('f', r(0), 'c')
    near(d, 'f', 'Near')
    interval(d, 'f', 'Single', 'root_interval')
    interval(d, 'f', 'Roots')
    interval(d, 'f', 'Ext', 'extrema_interval')
    cases, answers = [], {}
    for name, c in [('zero', 0), ('nonzero', 1), ('tiny', 1e-30)]:
        reason = 'coincident' if c == 0 else 'no_root'
        cases.append({'name': name, 'inputs': {'c': _num(c)}})
        answers[name] = {'Near': _absent(reason, stage='newton'), 'Single': _absent(reason, stage='pieces'),
                         **{f'Roots{k}': _absent(reason, stage='pieces' if c == 0 else None) for k in range(1, 4)},
                         **_set('Ext', [], 3, extrema=True)}
    out.append((d, cases, answers))

    d = _Doc('function_search_limits')
    answer = {}
    for f, tree, reason in [
        ('overflow', o('*', n(1e308), o('*', n(1e308), X)), 'non_finite'),
        ('degree', o('*', o('^', X, n(64)), X), 'limit_exceeded')]:
        d.function(f, tree)
        near(d, f, f + '_near')
        interval(d, f, f + '_single', 'root_interval')
        interval(d, f, f + '_roots', count=1)
        interval(d, f, f + '_ext', 'extrema_interval', count=1)
        for key in (f + '_near', f + '_single', f + '_roots1', f + '_ext1'):
            answer[key] = _absent(reason, stage='isolation')
    d.function('unresolved', o('-', o('*', n(1e-100), sq(X)), n(1)))
    near(d, 'unresolved', 'UnresolvedNear')
    interval(d, 'unresolved', 'UnresolvedSingle', 'root_interval', -1, 1)
    interval(d, 'unresolved', 'UnresolvedRoots', a=-1, b=1, count=1)
    d.function('unresolved_ext', o('-', o('*', n(1e-200), o('^', X, n(3))), X))
    interval(d, 'unresolved_ext', 'UnresolvedExt', 'extrema_interval', -1, 1, 1)
    answer['UnresolvedNear'] = _absent('no_convergence', stage='bracket')
    for key in ('UnresolvedSingle', 'UnresolvedRoots1', 'UnresolvedExt1'):
        answer[key] = _absent('no_convergence', stage='isolation')
    d.function('linear', X)
    for name, key in [('root_interval', 'EmptySingle'), ('roots_interval', 'EmptyRoots'), ('extrema_interval', 'EmptyExt')]:
        interval(d, 'linear', key, name, 2, -2, 1)
        answer[key if name == 'root_interval' else key + '1'] = _absent('empty_range', stage='pieces')
    d.function('zero_branch', choose(condition('>'), n(0)))
    interval(d, 'zero_branch', 'ZeroBranch', count=1)
    interval(d, 'zero_branch', 'ZeroBranchSingle', 'root_interval')
    answer['ZeroBranch1'] = _absent('coincident', stage='pieces')
    answer['ZeroBranchSingle'] = _absent('coincident', stage='pieces')
    d.function('uncertain_zero', call('sin', o('*', o('*', n(1e-200), X), o('*', n(1e-200), X))))
    interval(d, 'uncertain_zero', 'Uncertain', count=1)
    answer['Uncertain1'] = _absent('no_convergence', stage='pieces')
    d.function('many', call('sin', o('*', n(128), X)))
    interval(d, 'many', 'ManyRoots', a=-3.7, b=3.7, count=1)
    interval(d, 'many', 'ManyExt', 'extrema_interval', -3.7, 3.7, 1)
    answer['ManyRoots1'] = _absent('limit_exceeded', stage='isolation')
    answer['ManyExt1'] = _absent('limit_exceeded', stage='isolation')
    out.append(one(d, answer))

    d = _Doc('function_search_recovery').number('a', 1)
    d.op('op_b', 'number.expression', {'expr': {'kind': 'expr', 'ast': call('sqrt', r(0))},
                                     'refs': {'kind': 'list', 'items': [_ref('a')]}}, [('number', 'b', 'number')])
    d.function('f', o('-', sq(X), r(0)), 'b')
    near(d, 'f', 'Near')
    interval(d, 'f', 'Single', 'root_interval')
    interval(d, 'f', 'Roots')
    interval(d, 'f', 'Ext', 'extrema_interval')
    cases, answers = [], {}
    for name, a in [('defined', 1), ('changed', 4), ('undefined', -1), ('recovered', 1)]:
        cases.append({'name': name, 'inputs': {'a': _num(a)}})
        if a > 0:
            root = a ** .25
            answers[name] = {'Near': _point(root), 'Single': _point(-root),
                             **_set('Roots', [-root, root], 3),
                             **_set('Ext', [(0, -math.sqrt(a), 'min')], 3, extrema=True)}
        else:
            answers[name] = {key: _absent('upstream', cause='b') for key in
                             ('Near', 'Single', 'Roots1', 'Roots2', 'Roots3', 'Ext1', 'Ext2', 'Ext3')}
    out.append((d, cases, answers))
    d = _Doc('function_search_boundaries')
    d.function('zero_join', choose(condition('<'), X, n(0)))
    d.function('open_edge', choose(condition('<'), X, n(1)))
    d.function('exact_edge', choose(condition('<'), o('+', X, n(1e-6)), n(1)))
    plateau = call('max', o('-', call('abs', X), n(.001)), n(0))
    d.function('wrapped_plateau', o('+', plateau, n(1)))
    d.function('edge_plateau', call('max', call('max', o('neg', X), o('-', X, n(.001))), n(0)))
    near(d, 'zero_join', 'ZeroNear', -1)
    near(d, 'open_edge', 'OpenNear', -1)
    near(d, 'exact_edge', 'ExactNear', -1)
    interval(d, 'wrapped_plateau', 'Wrapped', 'extrema_interval', -1, 1)
    interval(d, 'edge_plateau', 'Edge', 'extrema_interval', -1, 1)
    out.append(one(d, {'ZeroNear': _absent('coincident', stage='pieces'),
                       'OpenNear': _absent('no_convergence', stage='bracket'),
                       'ExactNear': _point(-1e-6),
                       **_set('Wrapped', [], 3, extrema=True), **_set('Edge', [], 3, extrema=True)}))
    return out
