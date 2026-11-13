"""Analytical curves fixtures for the implemented function-analysis operations.

The shared generator supplies graph samples and upstream element records.
Answers for the new operations are written from the formulas below, then
replayed independently; they are never copied from evaluated coordinates.
"""
import math


def _point(x, y=0, *, found=None, kind=None):
    rec = {'state': 'defined', 'type': 'point', 'value': {'x': x, 'y': y}}
    if found is not None:
        rec['detail'] = {'found': found}
        if kind is not None:
            rec['detail']['kind'] = kind
    return rec


def _number(value):
    return {'state': 'defined', 'type': 'number', 'value': {'value': value, 'unit': 'scalar'}}


def _absent(reason, type_='point', *, cause=None, stage=None):
    rec = {'state': 'error' if reason == 'limit_exceeded' else 'undefined', 'type': type_, 'reason': reason}
    if cause:
        rec['cause'] = cause
    if stage:
        rec['detail'] = {'stage': stage}
    return rec


def _set(prefix, solutions, count, *, extrema=False):
    """Analytic fixed slots, with full cardinality before limiting capacity."""
    out = {}
    for k in range(1, count + 1):
        if k <= len(solutions):
            item = solutions[k - 1]
            out[f'{prefix}{k}'] = (_point(*item[:2], found=len(solutions), kind=item[2]) if extrema
                                    else _point(item, found=len(solutions)))
        else:
            out[f'{prefix}{k}'] = _absent('branch_absent' if solutions else
                                          'no_extremum' if extrema else 'no_root')
    return out


def scenes():
    """(document builder, cases, independent answers by case name)."""
    from .curves_fixtures import _Doc, _ref, _num, X, n, o, r, sq, call

    def search(d, f, prefix, count=3, *, extrema=False):
        base = 'extremum' if extrema else 'root'
        name = 'extrema_polynomial' if extrema else 'roots_polynomial'
        return d.op('op_analysis_' + prefix, 'function.' + name, {'function': _ref(f), 'count': _num(count)},
                    [(f'{base}.{k}', f'{prefix}{k}', 'point') for k in range(1, count + 1)])

    def value(d, f='f', key='v', arg='a'):
        return d.op('op_' + key, 'function.value', {'function': _ref(f), 'x': _ref(arg)},
                    [('number', key, 'number')])

    def point_call(d, key, f, x):
        literal = not isinstance(x, str)
        refs = [f] if literal else [x, f]
        arg = n(x) if literal else r(0)
        tree = {'pair': [arg, {'call': 0 if literal else 1, 'args': [arg]}]}
        return d.op('op_' + key, 'point.expression', {
            'expr': {'kind': 'expr', 'ast': tree},
            'refs': {'kind': 'list', 'items': [_ref(key) for key in refs]}}, [('point', key, 'point')])

    def one(d, answers):
        return d, [{'name': 'analytic'}], {'analytic': answers}

    out = []
    d = _Doc('function_roots_poly')
    d.function('p', o('+', o('-', sq(X), o('*', n(4), X)), n(3)))
    d.function('q', o('*', sq(X), o('^', o('-', X, n(2)), n(3))))
    d.function('far', o('-', X, n(1000)))
    answer = {}
    for f, prefix, roots in [('p', 'A', [1, 3]), ('q', 'B', [0, 2]), ('far', 'Far', [1000])]:
        search(d, f, prefix)
        answer.update(_set(prefix, roots, 3))
    for f, tree, reason in [('constant', n(1), 'no_root'), ('tiny', n(1e-30), 'no_root'),
                             ('zero', n(0), 'coincident')]:
        d.function(f, tree)
        search(d, f, f, 1)
        answer[f + '1'] = _absent(reason, stage='isolation' if reason == 'coincident' else None)
    out.append(one(d, answer))

    d = _Doc('function_extrema_poly')
    answer = {}
    for f, tree, prefix, solutions in [
        ('cubic', o('-', o('^', X, n(3)), o('*', n(3), X)), 'E', [(-1, 2, 'max'), (1, -2, 'min')]),
        ('inflection', o('^', X, n(3)), 'I', []), ('quartic', o('^', X, n(4)), 'Q', [(0, 0, 'min')]),
        ('linear', X, 'Linear', []), ('constant', n(3), 'Const', [])]:
        d.function(f, tree)
        search(d, f, prefix, extrema=True)
        answer.update(_set(prefix, solutions, 3, extrema=True))
    out.append(one(d, answer))

    d = _Doc('function_poly_close_roots', bounds=(0, 0, 1, 1))
    answer = {}
    for scale_name, scale in [('unit_', 1), ('scaled_', 1e6)]:
        for name, tree, roots in [
            ('square', sq(o('-', X, n(1))), [1]),
            ('mixed', o('*', sq(o('-', X, n(1))), o('+', X, n(2))), [-2, 1]),
            ('close', o('*', o('-', X, n(1)), o('-', o('-', X, n(1)), n(1e-6))), [1, 1 + 1e-6]),
            # Rounded coefficients lose this pair's discriminant. Pin that
            # double-arithmetic limit, not an algebraic claim of multiplicity.
            ('unresolved', o('*', o('-', X, n(1)), o('-', o('-', X, n(1)), n(1e-9))), [1 + .5e-9])]:
            prefix = scale_name + name
            d.function(prefix, o('*', n(scale), tree))
            search(d, prefix, prefix)
            answer.update(_set(prefix, roots, 3))
    out.append(one(d, answer))

    d = _Doc('function_poly_limits')
    answer = {}
    for f, tree, prefix, roots, domain in [
        ('degree64', o('-', o('^', X, n(64)), n(1)), 'D', [-1, 1], {}),
        ('tiny_leading', o('-', o('*', n(1e-12), X), n(1)), 'T', [1e12], {}),
        ('scaled', o('*', n(1e20), o('-', sq(X), n(2))), 'S', [-math.sqrt(2), math.sqrt(2)], {}),
        ('domain', o('-', sq(X), n(1)), 'F', [1], {'lo': 0, 'hi': 1})]:
        d.function(f, tree, **domain)
        search(d, f, prefix)
        answer.update(_set(prefix, roots, 3))
    for f, tree, reason in [
        ('degree65', o('*', o('^', X, n(64)), X), 'limit_exceeded'),
        ('conditional', {'if': [{'cmp': '>', 'args': [X, n(0)]}, X]}, 'not_polynomial'),
        ('hole', o('/', X, X), 'not_polynomial'),
        ('overflow', o('*', n(1e308), o('*', n(1e308), X)), 'non_finite'),
        ('unresolved', o('-', o('*', n(1e-100), sq(X)), n(1)), 'no_convergence')]:
        d.function(f, tree)
        search(d, f, f, 1)
        answer[f + '1'] = _absent(reason, stage='isolation')
        # Every declared extremum failure is also exercised independently.
        search(d, f, f + '_ext', 1, extrema=True)
        if f == 'unresolved':
            # Its derivative is linear and resolvable: the minimum is at 0.
            answer[f + '_ext1'] = _point(0, -1, found=1, kind='min')
        else:
            answer[f + '_ext1'] = _absent(reason, stage='isolation')
    d.function('unresolved_extrema', o('-', o('*', n(1e-200), o('^', X, n(3))), X))
    search(d, 'unresolved_extrema', 'U', 1, extrema=True)
    answer['U1'] = _absent('no_convergence', stage='isolation')
    out.append(one(d, answer))

    d = _Doc('function_found_slots')
    d.function('p', o('*', X, o('-', sq(X), n(1))))
    d.function('empty', o('+', sq(X), n(1)))
    d.function('cubic', o('-', o('^', X, n(3)), o('*', n(3), X)))
    search(d, 'p', 'R', 1)
    search(d, 'p', 'All', 5)
    search(d, 'empty', 'N')
    search(d, 'cubic', 'M', 1, extrema=True)
    out.append(one(d, {**_set('R', [-1, 0, 1], 1), **_set('All', [-1, 0, 1], 5),
                        **_set('N', [], 3), **_set('M', [(-1, 2, 'max'), (1, -2, 'min')], 1, extrema=True)}))

    d = _Doc('function_poly_rank_changes').number('k', 1)
    d.function('f', o('-', sq(X), r(0)), 'k')
    search(d, 'f', 'R')
    cases, answers = [], {}
    for name, k, roots in [('two', 1, [-1, 1]), ('merged', 0, [0]), ('empty', -1, []), ('recovered', 1, [-1, 1])]:
        cases.append({'name': name, 'inputs': {'k': _num(k)}})
        answers[name] = _set('R', roots, 3)
    out.append((d, cases, answers))

    d = _Doc('function_poly_upstream').number('a', 1)
    d.op('op_b', 'number.expression', {'expr': {'kind': 'expr', 'ast': call('sqrt', r(0))},
                                     'refs': {'kind': 'list', 'items': [_ref('a')]}}, [('number', 'b', 'number')])
    d.function('f', o('-', sq(X), r(0)), 'b')
    search(d, 'f', 'R')
    search(d, 'f', 'E', extrema=True)
    value(d, arg='b')
    cases, answers = [], {}
    for name, a in [('defined', 1), ('upstream', -1), ('recovered', 1)]:
        cases.append({'name': name, 'inputs': {'a': _num(a)}})
        answers[name] = ({**_set('R', [-1, 1], 3), **_set('E', [(0, -1, 'min')], 3, extrema=True), 'v': _number(0)}
                         if a > 0 else {**{key: _absent('upstream', cause='b')
                                                          for key in ('R1', 'R2', 'R3', 'E1', 'E2', 'E3')},
                                        'v': _absent('upstream', 'number', cause='b')})
    out.append((d, cases, answers))

    d = _Doc('function_value').number('a', 2).number('c', 3)
    d.function('f', o('*', r(0), sq(X)), 'c')
    value(d)
    point_call(d, 'Y', 'f', 0)
    point_call(d, 'P', 'f', 'a')
    cases, answers = [], {}
    for name, a, c in [('initial', 2, 3), ('argument', 4, 3), ('coefficient', 4, -2)]:
        cases.append({'name': name, 'inputs': {'a': _num(a), 'c': _num(c)}})
        answers[name] = {'v': _number(c * a * a), 'Y': _point(0), 'P': _point(a, c * a * a)}
    out.append((d, cases, answers))

    d = _Doc('function_value_domain').number('a', 1).function('f', sq(X), lo=0, hi=2)
    value(d)
    point_call(d, 'P', 'f', 'a')
    cases, answers = [], {}
    for name, a in [('left', 0), ('right', 2), ('outside', -1), ('recovered', 1)]:
        cases.append({'name': name, 'inputs': {'a': _num(a)}})
        answers[name] = ({'v': _number(a * a), 'P': _point(a, a * a)} if a >= 0 else
                         {'v': _absent('out_of_domain', 'number'), 'P': _absent('out_of_domain')})
    out.append((d, cases, answers))

    d = _Doc('function_value_branches').number('a', 0)
    d.function('f', {'if': [{'cmp': '<', 'args': [X, n(0)]}, o('/', n(1), X), n(2)]})
    d.function('pole', o('/', n(1), X)).function('exponential', call('exp', X))
    value(d)
    value(d, 'pole', 'pole_value')
    value(d, 'exponential', 'exp_value')
    cases, answers = [], {}
    for name, a in [('negative', -1), ('boundary', 0), ('overflow', 1000)]:
        cases.append({'name': name, 'inputs': {'a': _num(a)}})
        answers[name] = {'v': _number(-1 if a < 0 else 2),
                         'pole_value': _number(1 / a) if a else _absent('out_of_domain', 'number'),
                         'exp_value': _number(math.exp(a)) if a < 1000 else _absent('out_of_domain', 'number')}
    out.append((d, cases, answers))
    return out


def build_fixtures():
    from .curves_fixtures import _fixture, _rounded
    from .parity import verify_fixture

    out = {}
    for d, cases, answers in scenes():
        fixture = _fixture(d.doc, cases)
        # Rounding geometric expectations must never round an AST coefficient
        # to zero: it changes degree, the root set and even the operation state.
        fixture['document'] = d.doc
        for case in fixture['cases']:
            for key, rec in case['expect'].items():
                if rec['state'] == 'defined' and rec['type'] == 'function':
                    producer = d.doc['elements'][key]['producer']['operationId']
                    rec['value']['expr'] = d.doc['operations'][producer]['args']['expr']['ast']
            case['expect'].update(_rounded(answers[case['name']]))
        problems = verify_fixture(fixture)
        if problems:
            raise ValueError(f"{fixture['id']}: analytical answers differ: {problems}")
        out[fixture['id'] + '.json'] = fixture
    return out
