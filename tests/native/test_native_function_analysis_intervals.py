"""Analytical interval-search selection, distinct slots and partial domains."""
import math

import pytest

from animageo import native
from tests.native.conftest import num
from tests.native.function_analysis_helpers import Doc, X, n, o, power, fn
from tests.native.test_native_function_analysis_numeric import cond, conditional


def evaluate(tree, name='roots_interval', a=-2, b=2, count=3, **domain):
    d = Doc().function(tree, **domain).interval(name, a, b, count)
    assert native.validate(d.doc) == []
    ev = native.evaluate(d.doc)
    assert not ev.diagnostics
    return ev


def points(ev, xs, ys=None, kinds=None):
    ys = [0] * len(xs) if ys is None else ys
    for k, (x, y) in enumerate(zip(xs, ys), 1):
        rec = ev.elements[f'P{k}']
        assert rec['state'] == 'defined', rec
        assert rec['value'] == pytest.approx({'x': x, 'y': y}, abs=1e-9)
        assert rec['detail'] == dict(found=len(xs), **({'kind': kinds[k - 1]} if kinds else {}))
    for k in range(len(xs) + 1, 4):
        assert ev.elements[f'P{k}']['reason'] == 'branch_absent'


@pytest.mark.parametrize('tree,a,b,roots', [
    (fn('sin', X), -4, 4, [-math.pi, 0, math.pi]),
    (fn('tan', X), -4, 4, [-math.pi, 0, math.pi]),
    (o('/', o('-', X, n(1)), X), -2, 2, [1]),
    (conditional(cond('>'), o('-', X, n(1))), -2, 2, [1]),
    (conditional(cond('<'), o('+', X, n(1)), o('-', X, n(1))), -2, 2, [-1, 1]),
    (power(fn('sin', X), 2), -4, 4, [-math.pi, 0, math.pi]),
    (fn('abs', fn('sin', X)), -4, 4, [-math.pi, 0, math.pi]),
    (o('*', power(o('-', X, n(.37)), 2), o('+', X, n(.83))), -1, 1, [-.83, .37]),
    (fn('atan', o('*', n(1e100), X)), -2, 2, [0]),
    (fn('sqrt', X), -1, 1, [0]),
    (power(X, 2), -1, 1, [0]),
])
def test_roots_interval_retains_partial_pieces_and_tangencies(tree, a, b, roots):
    points(evaluate(tree, a=a, b=b), roots)


@pytest.mark.parametrize('tree,reason', [
    (o('/', n(1), X), 'no_root'),
    (conditional(cond('<'), n(-1), n(1)), 'no_root'),
    (conditional(cond('<'), n(-1), conditional(cond('>'), n(1), n(0))), 'no_root'),
    (conditional(cond('>'), o('+', X, n(1))), 'no_root'),
    (conditional(cond('>'), X, n(1)), 'no_root'),
    (fn('sqrt', o('neg', o('+', power(X, 2), n(1)))), 'no_root'),
    (conditional(cond('>'), n(0)), 'coincident'),
    (fn('sin', o('-', X, X)), 'coincident'),
    (fn('sin', o('*', o('*', n(1e-200), X), o('*', n(1e-200), X))), 'no_convergence'),
])
def test_interval_roots_exclude_poles_jumps_open_edges_and_uncertain_zero_sets(tree, reason):
    ev = evaluate(tree)
    for k in range(1, 4):
        rec = ev.elements[f'P{k}']
        assert rec['reason'] == reason, rec
        assert 'found' not in rec.get('detail', {})


@pytest.mark.parametrize('tree,a,b,root', [
    (power(X, 2), -1, 1, 0),
    (o('*', o('-', X, n(1)), o('-', X, n(3))), 0, 4, 1),
    (o('*', o('*', o('-', X, n(1)), o('-', X, n(2))), o('-', X, n(4))), 0, 5, 4),
    (o('+', X, n(2)), -2, 2, -2), (o('-', X, n(2)), -2, 2, 2),
    (o('-', power(X, 2), n(4)), -2, 2, -2),
    (conditional(cond('>'), o('-', X, n(1))), 0, 2, 1),
    (o('/', o('-', X, n(1)), X), -2, 2, 1),
    (conditional(cond('<'), o('+', X, n(1)), o('-', X, n(1))), -2, 2, -1),
])
def test_single_interval_preserves_bisection_priority_then_leftmost_fallback(tree, a, b, root):
    rec = evaluate(tree, 'root_interval', a, b).elements['P']
    assert rec['value'] == pytest.approx({'x': root, 'y': 0}, abs=1e-9)
    assert 'found' not in rec.get('detail', {})


@pytest.mark.parametrize('tree,a,b,xs,ys,kinds', [
    (fn('sin', X), 0, 2 * math.pi, [math.pi / 2, 3 * math.pi / 2], [1, -1], ['max', 'min']),
    (fn('abs', X), -1, 1, [0], [0], ['min']),
    (conditional(cond('<'), o('neg', X), X), -1, 1, [0], [0], ['min']),
    (conditional(cond('>'), power(o('-', X, n(1)), 2)), -2, 2, [1], [0], ['min']),
    (o('-', power(X, 3), o('*', n(3), X)), -2, 2, [-1, 1], [2, -2], ['max', 'min']),
])
def test_interval_extrema_are_isolated_internal_turns(tree, a, b, xs, ys, kinds):
    points(evaluate(tree, 'extrema_interval', a, b), xs, ys, kinds)


@pytest.mark.parametrize('tree,a,b', [
    (X, -1, 1), (n(2), -1, 1), (power(X, 3), -1, 1), (power(X, 2), 0, 1),
    (o('/', n(1), X), -2, 2), (fn('tan', X), -4, 4),
    (conditional(cond('<'), n(0), n(1)), -2, 2),
    (conditional(cond('<', X, n(.001)), n(0), power(o('-', X, n(.001)), 2)), 0, 1),
])
def test_interval_extrema_do_not_invent_plateaus_or_boundary_extrema(tree, a, b):
    ev = evaluate(tree, 'extrema_interval', a, b)
    assert all(ev.elements[f'P{k}']['reason'] == 'no_extremum' for k in range(1, 4))


@pytest.mark.parametrize('name', ['root_near', 'root_interval', 'roots_interval'])
@pytest.mark.parametrize('constant,reason', [(0, 'coincident'), (1, 'no_root'), (1e-30, 'no_root')])
def test_every_root_mode_classifies_constants_before_sample_residuals(name, constant, reason):
    d = Doc().function(n(constant))
    d.near(0) if name == 'root_near' else d.interval(name)
    ev = native.evaluate(d.doc)
    keys = ['P'] if name != 'roots_interval' else ['P1', 'P2', 'P3']
    assert all(ev.elements[key]['reason'] == reason for key in keys)


@pytest.mark.parametrize('name', ['root_interval', 'roots_interval', 'extrema_interval'])
@pytest.mark.parametrize('a,b', [(2, -2), (0, 0), (0, 1e-12)])
def test_interval_range_validation_precedes_search(name, a, b):
    ev = evaluate(X, name, a, b)
    keys = ['P'] if name == 'root_interval' else ['P1', 'P2', 'P3']
    assert all(ev.elements[key]['reason'] == 'empty_range' for key in keys)


def test_interval_counts_and_sparse_binding_do_not_limit_found():
    tree = fn('sin', X)
    d = Doc().function(tree).interval(a=-4, b=4, count=1)
    rec = native.evaluate(d.doc).elements['P1']
    assert rec['detail'] == {'found': 3}
    d = Doc().function(tree).interval(a=-4, b=4, count=5, slots=[3, 5])
    ev = native.evaluate(d.doc)
    assert ev.elements['P3']['value']['x'] == pytest.approx(math.pi, abs=1e-9)
    assert ev.elements['P3']['detail'] == {'found': 3}
    assert ev.elements['P5']['reason'] == 'branch_absent'
    assert native.check(d.doc).results == {'op_result:on_graph': 'passed'}


def test_interval_live_bounds_and_refs_preserve_cause_and_recover():
    d = Doc().number('a', -2).number('b', 2).number('c', 1)
    d.function(o('-', power(X, 2), {'ref': 0}), 'c').interval(a='a', b='b')
    ids = set(d.doc['elements'])
    for a, b, c, first in [(-2, 2, 1, -1), (0, 2, 1, 1), (0, 2, -1, None), (-2, 2, 1, -1)]:
        ev = native.evaluate(d.doc, inputs={'a': num(a), 'b': num(b), 'c': num(c)})
        assert set(ev.elements) == ids
        if first is None:
            assert ev.elements['P1']['reason'] == 'no_root'
        else:
            assert ev.elements['P1']['value']['x'] == pytest.approx(first)


@pytest.mark.parametrize('name', ['roots_interval', 'extrema_interval'])
def test_interval_result_limit_is_global_even_with_count_one(name):
    # Offset endpoints avoid near-zero grid nodes whose tiny initial bracket
    # residual cannot improve at double resolution. The finite search is partial.
    ev = evaluate(fn('sin', o('*', n(128), X)), name, -3.7, 3.7, 1)
    assert ev.elements['P1']['reason'] == 'limit_exceeded'
    assert ev.elements['P1']['state'] == 'error'


def test_empty_interval_is_rejected_before_polynomial_resource_work():
    tree = o('*', power(X, 64), X)
    ev = evaluate(tree, 'roots_interval', 1, -1)
    assert ev.elements['P1']['reason'] == 'empty_range'


@pytest.mark.parametrize('name', ['root_near', 'root_interval', 'roots_interval'])
def test_detected_zero_branch_is_not_represented_by_an_arbitrary_point(name):
    d = Doc().function(conditional(cond('>'), n(0)))
    d.near(1) if name == 'root_near' else d.interval(name)
    ev = native.evaluate(d.doc)
    rec = ev.elements['P1' if name == 'roots_interval' else 'P']
    assert rec['reason'] == 'coincident'


def test_zero_branch_detection_does_not_impose_polynomial_degree_on_general_ast():
    # This is a valid numerical AST, outside the global-polynomial subset.
    tree = conditional(cond('<'), X, o('*', power(X, 64), X))
    rec = evaluate(tree, 'root_interval', -1, 1).elements['P']
    assert rec['state'] == 'defined', rec
    assert rec['value'] == {'x': 0, 'y': 0}


@pytest.mark.parametrize('tree', [
    o('+', fn('max', o('-', fn('abs', X), n(.001)), n(0)), n(1)),
    o('*', n(2), fn('max', o('-', fn('abs', X), n(.001)), n(0))),
    fn('cos', fn('max', o('-', fn('abs', X), n(.001)), n(0))),
    fn('max', fn('max', o('neg', X), o('-', X, n(.001))), n(0)),
])
def test_arithmetic_and_function_wrappers_do_not_turn_plateaus_into_extrema(tree):
    ev = evaluate(tree, 'extrema_interval', -1, 1)
    assert ev.elements['P1']['reason'] == 'no_extremum'


@pytest.mark.parametrize('name', ['root_interval', 'roots_interval'])
def test_zero_branch_outside_requested_interval_does_not_hide_an_endpoint_root(name):
    ev = evaluate(conditional(cond('<'), X, n(0)), name, -1, 0)
    rec = ev.elements['P' if name == 'root_interval' else 'P1']
    assert rec['value'] == {'x': 0, 'y': 0}
