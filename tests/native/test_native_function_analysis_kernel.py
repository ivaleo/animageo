"""Independent analytical regressions for global polynomial analysis."""
import math

import pytest

from animageo import native
from tests.native.function_analysis_helpers import Doc, X, n, o, power, fn


def result(tree, name='roots_polynomial', count=3, **domain):
    d = Doc().function(tree, **domain).search(name, count)
    assert native.validate(d.doc) == []
    return native.evaluate(d.doc)


def point(ev, k, x, y=0, found=None, kind=None):
    rec = ev.elements[f'P{k}']
    assert rec['state'] == 'defined', rec
    assert rec['value'] == pytest.approx({'x': x, 'y': y}, abs=1e-9)
    detail = {'found': found} if found is not None else {}
    if kind:
        detail['kind'] = kind
    assert rec.get('detail', {}) == detail


@pytest.mark.parametrize('tree,roots', [
    (o('+', o('-', power(X, 2), o('*', n(4), X)), n(3)), [1, 3]),
    (o('*', power(X, 2), power(o('-', X, n(2)), 3)), [0, 2]),
    (o('-', X, n(1000)), [1000]), (power(X, 2), [0]),
    (power(X, 3), [0]), (power(X, 4), [0]),
    (o('-', power(X, 64), n(1)), [-1, 1]),
    (o('-', o('*', n(1e-12), X), n(1)), [1e12]),
    (o('*', n(1e20), o('-', power(X, 2), n(2))), [-math.sqrt(2), math.sqrt(2)]),
    (o('/', o('-', power(X, 2), n(2)), fn('sqrt', n(2))), [-math.sqrt(2), math.sqrt(2)]),
    (o('-', power(X, 2), n(1e-12)), [-1e-6, 1e-6]),
])
def test_polynomial_roots_are_global_distinct_and_sorted(tree, roots):
    ev = result(tree)
    for k, x in enumerate(roots, 1):
        point(ev, k, x, found=len(roots))
    for k in range(len(roots) + 1, 4):
        assert ev.elements[f'P{k}']['reason'] == 'branch_absent'


@pytest.mark.parametrize('tree,reason', [
    (n(1), 'no_root'), (n(1e-30), 'no_root'), (n(0), 'coincident'),
    (o('+', power(X, 2), n(1)), 'no_root'), (fn('sin', X), 'not_polynomial'),
    (o('/', X, X), 'not_polynomial'),
    ({'if': [{'cmp': '>', 'args': [X, n(0)]}, X]}, 'not_polynomial'),
    (o('*', power(X, 64), X), 'limit_exceeded'),
    (o('*', n(1e308), o('*', n(1e308), X)), 'non_finite'),
    (o('-', o('*', n(1e-320), X), n(1)), 'non_finite'),
    (o('*', n(0), fn('sqrt', n(-1))), 'not_polynomial'),
])
def test_polynomial_failures_do_not_fabricate_points(tree, reason):
    ev = result(tree)
    assert not ev.diagnostics
    for rec in (ev.elements[f'P{k}'] for k in range(1, 4)):
        assert rec['reason'] == reason, rec
        assert rec['state'] == ('error' if reason == 'limit_exceeded' else 'undefined')
        assert 'found' not in rec.get('detail', {})


@pytest.mark.parametrize('tree,expected', [
    (o('-', power(X, 3), o('*', n(3), X)), [(-1, 2, 'max'), (1, -2, 'min')]),
    (power(X, 3), []), (power(X, 4), [(0, 0, 'min')]),
    (o('neg', power(X, 4)), [(0, 0, 'max')]), (n(0), []), (X, []),
    (power(o('-', X, n(2)), 6), [(2, 0, 'min')]),
])
def test_polynomial_extrema_require_derivative_sign_change(tree, expected):
    ev = result(tree, 'extrema_polynomial')
    for k, (x, y, kind) in enumerate(expected, 1):
        point(ev, k, x, y, found=len(expected), kind=kind)
    for k in range(len(expected) + 1, 4):
        assert ev.elements[f'P{k}']['reason'] == ('branch_absent' if expected else 'no_extremum')


def test_polynomial_domain_filters_after_global_search():
    ev = result(o('-', power(X, 2), n(1)), lo=0, hi=1)
    point(ev, 1, 1, found=1)
    assert result(power(X, 2), lo=1).elements['P1']['reason'] == 'no_root'
    assert result(power(X, 2), 'extrema_polynomial', lo=0).elements['P1']['reason'] == 'no_extremum'


def test_polynomial_degree_and_rank_recover_without_changing_elements():
    tree = o('-', o('*', {'ref': 0}, power(X, 2)), n(1))
    d = Doc().number('a', 1).function(tree, 'a').search(count=3)
    ids = set(d.doc['elements'])
    for a, roots, reason in [(1, [-1, 1], 'branch_absent'), (0, [], 'no_root'),
                              (-1, [], 'no_root'), (1, [-1, 1], 'branch_absent')]:
        ev = native.evaluate(d.doc, inputs={'a': {'kind': 'number', 'value': a}})
        assert set(ev.elements) == ids
        for k, x in enumerate(roots, 1):
            point(ev, k, x, found=len(roots))
        assert ev.elements['P3']['reason'] == reason


def test_polynomial_count_limits_binding_without_limiting_found():
    tree = o('*', X, o('-', power(X, 2), n(1)))
    point(result(tree, count=1), 1, -1, found=3)
    d = Doc().function(tree).search(count=5, slots=[3, 5])
    ev = native.evaluate(d.doc)
    point(ev, 3, 1, found=3)
    assert ev.elements['P5']['reason'] == 'branch_absent'
    assert len(native.registry().output_slots(native.registry().get('function.roots_polynomial'),
                                             {'function': {'kind': 'ref', 'elementId': 'f'}})) == 100


@pytest.mark.parametrize('count', [0, -1, 1.5, 101])
def test_polynomial_invalid_count_declares_no_slots(count):
    d = Doc().function(X).search(count=count, slots=[1])
    assert native.registry().output_slots(native.registry().get('function.roots_polynomial'),
                                         d.doc['operations']['op_result']['args']) == []
    assert native.validate(d.doc)


def test_polynomial_isolation_limits_are_explicit(monkeypatch):
    profile = native.registry().numeric['functionAnalysis']
    monkeypatch.setitem(profile, 'maxEvaluations', 1)
    assert result(o('-', power(X, 2), n(2))).elements['P1']['reason'] == 'limit_exceeded'


def test_polynomial_unfinished_isolation_is_not_an_empty_set(monkeypatch):
    monkeypatch.setitem(native.registry().numeric['functionAnalysis'], 'bisectionSteps', 1)
    assert result(o('-', power(X, 2), n(2))).elements['P1']['reason'] == 'no_convergence'


@pytest.mark.parametrize('scale', [1, 1e6])
@pytest.mark.parametrize('tree,roots', [
    (power(o('-', X, n(1)), 2), [1]),
    (o('*', power(o('-', X, n(1)), 2), o('+', X, n(2))), [-2, 1]),
    (o('*', o('-', X, n(1)), o('-', o('-', X, n(1)), n(1e-6))), [1, 1 + 1e-6]),
])
def test_polynomial_tangencies_and_resolvable_close_pair_at_unit_scale(tree, roots, scale):
    d = Doc(bounds=(0, 0, 1, 1)).function(o('*', n(scale), tree)).search(count=3)
    ev = native.evaluate(d.doc)
    assert ev.scale == 1
    for k, x in enumerate(roots, 1):
        point(ev, k, x, found=len(roots))
    assert ev.elements[f'P{len(roots) + 1}']['reason'] == 'branch_absent'


@pytest.mark.parametrize('scale', [1, 1e6])
def test_polynomial_sub_resolution_pair_collapses_during_double_expansion(scale):
    from animageo.native.kernel.function_analysis import Budget, coefficients, _normalized

    # The pair and a shifted square expand to identical double coefficients;
    # the coefficient profile cannot reconstruct which AST supplied them.
    tree = o('*', n(scale), o('*', o('-', X, n(1)), o('-', o('-', X, n(1)), n(1e-9))))
    d = Doc(bounds=(0, 0, 1, 1)).function(tree).search(count=3)
    ev = native.evaluate(d.doc)
    c = _normalized(coefficients(ev.elements['f']['value'], Budget()))
    assert c[1] * c[1] - 4 * c[0] * c[2] == 0
    square = Doc().function(o('*', n(scale), power(o('-', X, n(1 + .5e-9)), 2)))
    square_value = native.evaluate(square.doc).elements['f']['value']
    assert coefficients(ev.elements['f']['value'], Budget()) == coefficients(square_value, Budget())
    point(ev, 1, 1 + 0.5e-9, found=1)
    assert ev.elements['P2']['reason'] == 'branch_absent'


@pytest.mark.parametrize('tree', [
    o('-', o('*', o('*', n(1e-200), X), o('*', n(1e-200), X)), n(1)),
    o('-', o('/', o('*', n(1e-200), X), n(1e200)), n(1)),
])
@pytest.mark.parametrize('name', ['roots_polynomial', 'extrema_polynomial'])
def test_polynomial_unrepresentable_coefficients_are_not_silently_zeroed(tree, name):
    ev = result(tree, name)
    assert ev.elements['P1']['reason'] == 'non_finite'
    assert not ev.diagnostics
