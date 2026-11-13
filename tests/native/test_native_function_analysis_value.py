"""Scalar function calls, independent checks and existing typed point calls."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS, classify
from animageo.native.kernel.numeric import tolerances
from animageo.native.kernel.values import Input, Undefined
from tests.native.conftest import num, ref
from tests.native.function_analysis_helpers import Doc, X, n, o, power, fn


def value_doc(tree, x=2, **domain):
    d = Doc().number('a', x).function(tree, **domain)
    return d.op('op_value', 'function.value', {'function': ref('f'), 'x': ref('a')},
                [('number', 'v', 'number')])


@pytest.mark.parametrize('x,want', [(-2, 4), (0, 0), (3, 9)])
def test_value_is_a_scalar_number_at_the_requested_abscissa(x, want):
    d = value_doc(power(X, 2), x)
    assert native.validate(d.doc) == []
    ev = native.evaluate(d.doc)
    assert ev.elements['v'] == {'state': 'defined', 'type': 'number',
                                'value': {'value': want, 'unit': 'scalar'}}
    assert native.check(d.doc).results == {}


@pytest.mark.parametrize('tree,x,domain,want', [
    (power(X, 2), -1, {'lo': 0}, None), (power(X, 2), 0, {'lo': 0}, 0),
    (o('/', n(1), X), 0, {}, None), (fn('exp', X), 1000, {}, None),
    ({'if': [{'cmp': '<', 'args': [X, n(0)]}, o('/', n(1), n(0)), n(2)]}, 0, {}, 2),
    ({'if': [{'cmp': '<=', 'args': [X, n(0)]}, n(1), n(2)]}, 0, {}, 1),
    ({'if': [{'cmp': '>', 'args': [X, n(0)]}, X]}, 0, {}, None),
])
def test_value_respects_closed_domain_lazy_branches_and_nonfinite_calls(tree, x, domain, want):
    ev = native.evaluate(value_doc(tree, x, **domain).doc)
    rec = ev.elements['v']
    if want is None:
        assert rec['state'] == 'undefined' and rec['reason'] == 'out_of_domain'
    else:
        assert rec['value']['value'] == want


def test_value_normalizes_negative_zero_and_accepts_literal_x():
    d = value_doc(o('neg', X), 0)
    d.doc['operations']['op_value']['args']['x'] = num(0)
    rec = native.evaluate(d.doc).elements['v']
    assert rec['value']['unit'] == 'scalar'
    assert math.copysign(1, rec['value']['value']) == 1


def test_value_and_polynomial_outputs_preserve_upstream_cause_and_recover():
    d = Doc().number('a', 1)
    d.op('op_b', 'number.expression', {'expr': {'kind': 'expr', 'ast': fn('sqrt', {'ref': 0})},
                                      'refs': {'kind': 'list', 'items': [ref('a')]}},
         [('number', 'b', 'number')])
    d.function(o('-', power(X, 2), {'ref': 0}), 'b').search()
    d.op('op_value', 'function.value', {'function': ref('f'), 'x': ref('b')}, [('number', 'v', 'number')])
    for a in (1, -1, 1):
        ev = native.evaluate(d.doc, inputs={'a': num(a)})
        for key in ('f', 'P1', 'v'):
            rec = ev.elements[key]
            if a < 0:
                assert rec['reason'] == 'upstream' and rec['cause'] == 'b', rec
            else:
                assert rec['state'] == 'defined'
    # An undefined x alone also propagates, independently of the function.
    d.doc['operations']['op_f']['args']['refs']['items'] = []
    d.doc['operations']['op_f']['args']['expr']['ast'] = X
    assert native.evaluate(d.doc, inputs={'a': num(-1)}).elements['v']['cause'] == 'b'


def test_value_recomputes_function_coefficients_and_abscissa_independently():
    d = Doc().number('a', 2).number('c', 3).function(o('*', {'ref': 0}, power(X, 2)), 'c')
    d.op('op_value', 'function.value', {'function': ref('f'), 'x': ref('a')}, [('number', 'v', 'number')])
    for a, c, want in [(2, 3, 12), (4, 3, 48), (4, -2, -32)]:
        ev = native.evaluate(d.doc, inputs={'a': num(a), 'c': num(c)})
        assert ev.elements['v']['value'] == {'value': want, 'unit': 'scalar'}


@pytest.mark.parametrize('name,base,tree,expected', [
    ('roots_polynomial', 'root', o('-', power(X, 2), n(2)), True),
    ('roots_polynomial', 'root', o('+', power(X, 2), n(1)), False),
    ('extrema_polynomial', 'extremum', power(X, 2), True),
    ('extrema_polynomial', 'extremum', X, False),
])
def test_checks_run_for_defined_slots_despite_absent_slots(name, base, tree, expected):
    d = Doc().function(tree).search(name, count=3)
    ev = native.evaluate(d.doc)
    checks = native.check(d.doc).results
    assert checks == ({'op_result:on_graph': 'passed'} if expected else {})
    assert ('function.' + name, 'on_graph') in __import__(
        'animageo.native.kernel.checks', fromlist=['CHECKS']).CHECKS
    for k in range(1, 4):
        rec = ev.elements[f'P{k}']
        if rec['state'] == 'defined':
            assert rec['detail']['found'] >= 1
            assert ('kind' in rec['detail']) == (base == 'extremum')
        else:
            assert rec['reason'] == ('branch_absent' if expected else
                                     'no_root' if base == 'root' else 'no_extremum')
            assert 'found' not in rec.get('detail', {})


def test_root_check_normalizes_a_large_vertical_residual_and_remains_independent():
    tree = o('*', n(1e20), o('-', power(X, 2), n(2)))
    d = Doc().function(tree).search(count=3)
    ev = native.evaluate(d.doc)
    assert native.check(d.doc).results == {'op_result:on_graph': 'passed'}
    # A displaced claimed root must fail even when all other slots are absent.
    args = {'function': Input('function', ev.elements['f']['value'])}
    error = CHECKS[('function.roots_polynomial', 'on_graph')](
        args, {'root.1': {'x': math.sqrt(2) + .01, 'y': 0},
               'root.2': Undefined('branch_absent')}, tolerances(1))
    assert classify(error, tolerances(1)) == 'failed'


def test_root_check_uses_one_sided_secants_at_domain_boundary():
    from animageo.native.kernel.checks import CHECKS
    value = {'expr': fn('sqrt', X), 'refs': [], 'domain': [0, 1]}
    args = {'function': Input('function', value)}
    check = CHECKS[('function.roots_polynomial', 'on_graph')]
    assert check(args, {'root.1': {'x': 0, 'y': 1}}, tolerances(1)) == pytest.approx(1e-5)


def test_existing_y_axis_and_tuple_points_follow_live_inputs_without_clamp():
    d = Doc().number('a', 2).number('c', 3).function(o('*', {'ref': 0}, power(X, 2)), 'c', lo=0)
    refs = {'kind': 'list', 'items': [ref('a'), ref('f')]}
    for key, ast in [('Y', {'pair': [n(0), {'call': 1, 'args': [n(0)]}]}),
                     ('P', {'pair': [{'ref': 0}, {'call': 1, 'args': [{'ref': 0}]}]})]:
        d.op('op_' + key, 'point.expression', {'expr': {'kind': 'expr', 'ast': ast}, 'refs': refs},
             [('point', key, 'point')])
    for a, c in [(2, 3), (4, -2), (-1, 3), (2, 3)]:
        ev = native.evaluate(d.doc, inputs={'a': num(a), 'c': num(c)})
        assert ev.elements['Y']['value'] == {'x': 0, 'y': 0}
        rec = ev.elements['P']
        if a < 0:
            assert rec['reason'] == 'out_of_domain'
        else:
            assert rec['value'] == {'x': a, 'y': c * a * a}


def test_complete_analysis_has_dedicated_step_phrases():
    from animageo.native.describe import phrase_table

    d = value_doc(power(X, 2)).search(count=2)
    lines = native.describe(d.doc)
    assert any('значение функции' in line for line in lines)
    assert any('действительные корни многочлена' in line for line in lines)
    for name in ('roots_polynomial', 'extrema_polynomial', 'value'):
        assert 'function_' + name in phrase_table()['steps']
    assert native.has('function_analysis')
