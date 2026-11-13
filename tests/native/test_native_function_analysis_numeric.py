"""Piecewise finite search and roots selected from an initial abscissa."""
import math

import pytest

from animageo import native
from animageo.native.kernel.numeric import tolerances
from animageo.native.kernel.ops import OpContext
from tests.native.function_analysis_helpers import Doc, X, n, o, power, fn


def cond(sign, a=X, b=None):
    return {'cmp': sign, 'args': [a, n(0) if b is None else b]}


def conditional(condition, then, other=None):
    return {'if': [condition, then] + ([] if other is None else [other])}


def near(tree, start=0, **domain):
    d = Doc().function(tree, **domain).near(start)
    assert native.validate(d.doc) == []
    ev = native.evaluate(d.doc)
    assert not ev.diagnostics
    return ev.elements['P']


@pytest.mark.parametrize('tree,start,expected', [
    (o('-', power(X, 2), n(2)), 1, math.sqrt(2)),
    (o('-', power(X, 2), n(2)), -1, -math.sqrt(2)),
    (o('-', power(X, 2), n(2)), 0, math.sqrt(2)),
    (o('-', X, n(1000)), 0, 1000),
    (o('-', X, n(3)), 3, 3),
    (power(o('-', X, n(.37)), 2), 0, .37),
    (o('/', o('-', X, n(1)), X), 0, 1),
    (fn('ln', X), -1, 1),
    (o('-', fn('sqrt', X), n(1)), 0, 1),
    (fn('atan', o('*', n(1e100), X)), 0, 0),
    (conditional(cond('<'), o('/', n(1), n(0)), o('-', power(X, 2), n(2))), 1, math.sqrt(2)),
])
def test_root_near_newton_and_right_first_fallback(tree, start, expected):
    rec = near(tree, start)
    assert rec['state'] == 'defined', rec
    assert rec['value'] == pytest.approx({'x': expected, 'y': 0}, abs=1e-9)
    assert 'found' not in rec.get('detail', {})


def test_root_near_damped_cycle_falls_back_to_the_unique_real_root():
    tree = o('+', o('-', power(X, 3), o('*', n(2), X)), n(2))
    cbrt = lambda v: math.copysign(abs(v) ** (1 / 3), v)
    expected = cbrt(-1 + math.sqrt(19 / 27)) + cbrt(-1 - math.sqrt(19 / 27))
    assert near(tree)['value']['x'] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize('tree,reason', [
    (n(0), 'coincident'), (n(2), 'no_root'), (n(1e-30), 'no_root'),
    (o('+', power(X, 2), n(1)), 'no_convergence'),
    (o('/', n(1), X), 'no_convergence'),
    (conditional(cond('<'), n(-1), n(1)), 'no_convergence'),
    (conditional(cond('<'), n(-1), conditional(cond('>'), n(1), n(0))), 'no_convergence'),
])
def test_root_near_absence_is_not_a_fabricated_zero(tree, reason):
    rec = near(tree)
    assert rec['reason'] == reason, rec
    assert rec['state'] == 'undefined'


def test_root_near_expansion_limits_and_budget_are_shared(monkeypatch):
    profile = native.registry().numeric['functionAnalysis']
    monkeypatch.setitem(profile, 'newtonSteps', 0)
    monkeypatch.setitem(profile, 'bracketMaxStep', 2)
    monkeypatch.setitem(profile, 'bracketMaxDoublings', 1)
    assert near(o('-', X, n(4)))['reason'] == 'no_convergence'
    monkeypatch.setitem(profile, 'maxEvaluations', 1)
    rec = near(o('-', power(X, 2), n(2)))
    assert rec['reason'] == 'limit_exceeded' and rec['state'] == 'error'


def test_root_near_expands_beyond_the_view_without_newton(monkeypatch):
    monkeypatch.setitem(native.registry().numeric['functionAnalysis'], 'newtonSteps', 0)
    assert near(o('-', X, n(1000)))['value'] == {'x': 1000, 'y': 0}


@pytest.mark.parametrize('tree,pieces_count', [
    (power(X, 2), 1), (fn('atan', o('*', n(1e100), X)), 1),
    (o('/', o('-', X, n(1)), X), 2),
    (conditional(cond('<'), o('+', X, n(1)), o('-', X, n(1))), 2),
    (conditional(cond('>'), o('-', X, n(1))), 1),
    (fn('sqrt', X), 1), (fn('tan', X), 3),
])
def test_finite_pieces_preserve_open_defects_and_closed_domain_ends(tree, pieces_count):
    from animageo.native.kernel.function_analysis_numeric import Search

    value = {'expr': tree, 'refs': [], 'domain': [None, None]}
    search = Search(value, OpContext(tolerances(1)))
    pieces = search.pieces(-4, 4)
    assert len(pieces) == pieces_count
    for left, right in zip(pieces, pieces[1:]):
        assert left.hi <= right.lo
        assert not left.right_closed and not right.left_closed
    if tree == fn('sqrt', X):
        assert pieces[0].lo == 0 and pieces[0].left_closed
    if tree == conditional(cond('>'), o('-', X, n(1))):
        assert pieces[0].lo > 0 and not pieces[0].left_closed


def test_continuity_iteration_exhaustion_is_not_a_proven_discontinuity(monkeypatch):
    from animageo.native.kernel.function_analysis import AnalysisError
    from animageo.native.kernel.function_analysis_numeric import Search

    monkeypatch.setitem(native.registry().numeric['functionAnalysis'], 'continuitySteps', 0)
    search = Search({'expr': o('/', n(1), X), 'refs': [], 'domain': [None, None]},
                    OpContext(tolerances(1)))
    with pytest.raises(AnalysisError) as error:
        search.pieces(-1, 1)
    assert error.value.reason == 'no_convergence'


def test_root_near_rechecks_a_zero_branch_discovered_by_continuity():
    rec = near(conditional(cond('<'), X, n(0)), -1)
    assert rec['reason'] == 'coincident'


def test_root_near_does_not_converge_to_an_open_edge_without_a_root():
    rec = near(conditional(cond('<'), X, n(1)), -1)
    assert rec['reason'] == 'no_convergence'


def test_exact_root_near_a_jump_is_retained_inside_its_piece():
    rec = near(conditional(cond('<'), o('+', X, n(1e-12)), n(1)), -1)
    assert rec['value'] == {'x': -1e-12, 'y': 0}
