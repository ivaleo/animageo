"""Independent analytic expectations for graph tangents, normals and slope."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import run_checks
from tests.native.conftest import DocBuilder, num, ref
from tests.native.function_analysis_helpers import X, n, o, power, fn


def graph(tree, x=1, *, lo=None, hi=None, coefficient=None):
    d = DocBuilder('graph_tangent', registry_version='1.12')
    refs = []
    if coefficient is not None:
        d.number('a', coefficient)
        refs = [ref('a')]
    args = {'expr': {'kind': 'expr', 'ast': tree}, 'refs': {'kind': 'list', 'items': refs}}
    if lo is not None:
        args['min'] = num(lo)
    if hi is not None:
        args['max'] = num(hi)
    d.number('x', x).op('op_f', 'function.expr', args, [('function', 'f', 'function')])
    d.op('op_t', 'line.tangent_function_at', {'function': ref('f'), 'x': ref('x')},
         [('line', 't', 'line'), ('touch', 'Q', 'point')])
    return d


def evaluate(d):
    assert native.validate(d.doc) == []
    ev = native.evaluate(d.doc)
    assert ev.diagnostics == []
    return ev


def assert_line(rec, x, y, slope):
    assert rec['state'] == 'defined', rec
    p, direction = rec['value']['p'], rec['value']['dir']
    length = math.hypot(1, slope)
    assert direction == pytest.approx([1 / length, slope / length], abs=1e-9)
    assert (x - p[0]) * direction[1] - (y - p[1]) * direction[0] == pytest.approx(0, abs=1e-8)
    assert p[0] * direction[0] + p[1] * direction[1] == pytest.approx(0, abs=1e-8)


@pytest.mark.parametrize('tree,x,y,slope', [
    (power(X, 2), 1, 1, 2), (power(X, 3), -2, -8, 12),
    (power(X, 3), 0, 0, 0), (fn('sin', X), 0, 0, 1),
    (fn('sin', X), math.pi / 2, 1, 0), (fn('sqrt', X), 1, 1, .5),
    (fn('abs', X), -1, 1, -1), (n(3), 2, 3, 0),
])
def test_analytic_graph_tangents(tree, x, y, slope):
    ev = evaluate(graph(tree, x))
    assert ev.elements['Q']['value'] == pytest.approx({'x': x, 'y': y})
    assert_line(ev.elements['t'], x, y, slope)
    assert run_checks(ev).ok


def conditional(then, other=None, comparison='<'):
    return {'if': [{'cmp': comparison, 'args': [X, n(0)]}, then] +
            ([] if other is None else [other])}


@pytest.mark.parametrize('tree,x,reason', [
    (fn('abs', X), 0, 'not_differentiable'), (fn('sqrt', X), 0, 'not_differentiable'),
    (o('+', n(1), fn('sqrt', X)), 0, 'not_differentiable'),
    (fn('tan', X), math.pi/2, 'out_of_domain'),
    (power(fn('abs', X), 2/3), 0, 'not_differentiable'),
    (o('/', o('-', power(X, 2), n(1)), o('-', X, n(1))), 1, 'out_of_domain'),
    (o('/', n(1), X), 0, 'out_of_domain'), (fn('sqrt', X), -1, 'out_of_domain'),
    (conditional(X, o('+', X, n(1))), 0, 'not_differentiable'),
    (conditional(n(0), n(2)), 0, 'not_differentiable'),
])
def test_undefined_geometry_is_shared_by_line_and_touch(tree, x, reason):
    ev = evaluate(graph(tree, x))
    for key in ('t', 'Q'):
        assert ev.elements[key]['state'] == 'undefined'
        assert ev.elements[key]['reason'] == reason


@pytest.mark.parametrize('tree,slope', [
    (conditional(power(X, 2), o('+', power(X, 2), power(X, 3))), 0),
    (power(fn('abs', X), 2), 0),
    (conditional(X, X), 1),
    (fn('min', power(X, 2), o('*', n(2), power(X, 2))), 0),
])
def test_smooth_joins_use_bounded_confirmation(tree, slope):
    ev = evaluate(graph(tree, 0))
    assert_line(ev.elements['t'], 0, 0, slope)
    assert run_checks(ev).ok


@pytest.mark.parametrize('x,reason', [(0, None), (2, None), (-1, 'out_of_domain'), (3, 'out_of_domain')])
def test_explicit_domain_includes_ends_without_clamping(x, reason):
    ev = evaluate(graph(power(X, 2), x, lo=0, hi=2))
    if reason:
        assert ev.elements['t']['reason'] == reason
    else:
        assert_line(ev.elements['t'], x, x*x, 2*x)


def test_open_end_is_not_replaced_by_a_nearby_value():
    assert evaluate(graph(conditional(power(X, 2), comparison='>'), 0)).elements['t']['reason'] == 'out_of_domain'


def test_live_parameter_and_abscissa_recovery_with_composed_normal():
    d = graph(o('*', {'ref': 0}, power(X, 2)), coefficient=1)
    d.op('op_normal', 'line.perpendicular', {'point': ref('Q'), 'base': ref('t')}, [('line', 'normal', 'line')])
    d.op('op_slope', 'line.slope', {'line': ref('t')}, [('number', 'slope', 'number')])
    for coefficient, x in [(1, 1), (0, 1), (-1, 2), (1, 1)]:
        d.doc['inputs'].update(a=num(coefficient), x=num(x))
        ev = evaluate(d)
        assert_line(ev.elements['t'], x, coefficient*x*x, 2*coefficient*x)
        assert ev.elements['slope']['value']['value'] == 2*coefficient*x
        p, direction = ev.elements['normal']['value']['p'], ev.elements['normal']['value']['dir']
        assert (x-p[0])*direction[1] - (coefficient*x*x-p[1])*direction[0] == pytest.approx(0, abs=1e-8)
        assert sum(a*b for a,b in zip(direction, ev.elements['t']['value']['dir'])) == pytest.approx(0)


def test_upstream_preserves_cause_and_recovers():
    d = graph(power(X, 2), lo=2, hi=1)
    ev = native.evaluate(d.doc)
    for key in ('t', 'Q'):
        assert ev.elements[key]['reason'] == 'upstream'
        assert ev.elements[key]['cause'] == 'f'
    d.doc['operations']['op_f']['args'].update(min=num(0), max=num(2))
    assert evaluate(d).elements['t']['state'] == 'defined'


@pytest.mark.parametrize('dx,dy,expected', [(1, 2, 2), (1, -2, -2), (-1, -2, 2), (1, 0, 0), (0, 1, None)])
def test_slope_and_vertical_line(dx, dy, expected):
    d = DocBuilder('slope', registry_version='1.12').free('A', 0, 0).free('B', dx, dy).line('l', 'A', 'B')
    d.op('op_s', 'line.slope', {'line': ref('l')}, [('number', 's', 'number')])
    rec = evaluate(d).elements['s']
    if expected is None:
        assert rec['reason'] == 'vertical_line'
    else:
        assert rec['value'] == {'value': expected, 'unit': 'scalar'}
        if expected == 0:
            assert math.copysign(1, rec['value']['value']) == 1


def test_numeric_exhaustion_does_not_invent_a_tangent(monkeypatch):
    monkeypatch.setitem(native.registry().numeric['tangency'], 'maxRefinements', 2)
    assert evaluate(graph(conditional(X, X), 0)).elements['t']['reason'] == 'no_convergence'


def test_graph_checks_detect_changed_touch_and_direction():
    ev = evaluate(graph(power(X, 2)))
    name, args, result = ev.computed['op_t']
    result['touch'] = {'x': 1, 'y': 2}
    assert run_checks(ev).results['op_t:on_curve'] == 'failed'
    result['touch'] = {'x': 1, 'y': 1}
    result['line'] = {'p': [0, 0], 'dir': [1, 0]}
    assert run_checks(ev).results['op_t:tangent'] == 'failed'


@pytest.mark.parametrize('literal', [False, True])
def test_point_on_tangent_uses_contact_as_its_parameter_origin(literal):
    d = graph(power(X, 2), 1)
    if literal:
        d.doc['operations']['op_t']['args']['x'] = num(1)
    d.on_path('P', 't', 0)
    assert evaluate(d).elements['P']['value'] == pytest.approx({'x': 1, 'y': 1})
    assert native.project(d.doc, 't', [1, 1]) == pytest.approx(0)


def test_smooth_nonzero_join_and_closed_conditional_endpoint():
    tree = {'if': [{'cmp': '<=', 'args': [X, n(1)]}, power(X, 2),
                    o('+', power(X, 2), power(o('-', X, n(1)), 3))]}
    assert_line(evaluate(graph(tree, 1)).elements['t'], 1, 1, 2)
    tree = conditional(power(X, 2), comparison='>=')
    assert_line(evaluate(graph(tree, 0)).elements['t'], 0, 0, 0)


def test_steep_finite_derivative_is_not_a_vertical_graph_tangent():
    tree = o('*', n(1e300), X)
    ev = evaluate(graph(tree, 0))
    assert ev.elements['t']['state'] == 'defined'
    assert ev.elements['t']['value']['dir'] == [1e-300, 1.0]


def test_nonfinite_derivative_and_single_point_domain():
    tree = o('*', n(1e308), o('*', n(2), X))
    assert evaluate(graph(tree, 0)).elements['t']['reason'] == 'non_finite'
    assert evaluate(graph(power(X, 2), 0, lo=0, hi=0)).elements['t']['cause'] == 'f'


def test_missing_interior_side_and_budget_are_not_one_sided_proofs(monkeypatch):
    tree = conditional(o('/', n(1), n(0)), power(X, 2))
    assert evaluate(graph(tree, 0)).elements['t']['reason'] == 'no_convergence'
    monkeypatch.setitem(native.registry().numeric['tangency'], 'maxEvaluations', 1)
    assert evaluate(graph(conditional(X, X), 0)).elements['t']['reason'] == 'no_convergence'


def test_slope_zero_sign_overflow_and_upstream():
    from dataclasses import replace
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import OpContext
    from animageo.native.kernel.ops.tangency import slope
    from animageo.native.kernel.values import Input, Undefined

    ctx = OpContext(replace(tolerances(1), decide_scalar=0))
    def result(dx, dy):
        return slope({'line': Input('line', {'p': [0, 0], 'dir': [dx, dy]})}, ctx)['number']
    assert math.copysign(1, result(1, -0.0)['value']) == 1
    assert isinstance(result(1e-320, 1), Undefined)
    assert result(1e-320, 1).reason == 'non_finite'
    d = DocBuilder('slope_upstream', registry_version='1.12').free('A', 0, 0).free('B', 0, 0).line('l', 'A', 'B')
    d.op('op_s', 'line.slope', {'line': ref('l')}, [('number', 's', 'number')])
    assert evaluate(d).elements['s']['cause'] == 'l'


def test_steps_phrases_and_registry_version_validation():
    d = graph(power(X, 2))
    d.op('op_s', 'line.slope', {'line': ref('t')}, [('number', 's', 'number')])
    text = '\n'.join(native.describe(d.doc))
    assert 'при абсциссе x' in text and 'точка касания — Q' in text
    assert 'наклон прямой t' in text
    assert any('op_t' in step.operationIds for step in native.steps(d.doc))
    d.doc['operationRegistryVersion'] = '1.11'
    assert native.validate(d.doc)


def test_analytical_curves_are_shared_and_replayable():
    from animageo.native.tangency_fixtures import build_fixtures
    from animageo.native.parity import verify_fixture
    fixtures = build_fixtures()
    assert len(fixtures) == 7
    assert sum(len(f['cases']) for f in fixtures.values()) == 29
    for fixture in fixtures.values():
        assert verify_fixture(fixture) == []
    first = fixtures['graph_tangent_abscissa.json']['cases'][0]['expect']
    assert first['square_t_touch']['value'] == {'x': 1, 'y': 1}
    assert first['square_t']['value']['p'] == [0.4, -0.2]


def test_nested_condition_jump_is_not_an_analytic_branch_tangent():
    switch = {'if': [{'cmp': '<', 'args': [X, n(0)]}, n(-1), n(1)]}
    tree = {'if': [{'cmp': '>', 'args': [switch, n(0)]}, n(1), n(0)]}
    assert evaluate(graph(tree, 0)).elements['t']['reason'] == 'not_differentiable'


def test_tangent_projection_does_not_overflow_for_large_finite_contacts():
    ev = evaluate(graph(X, 1.5e308))
    assert ev.elements['t']['state'] == 'defined'
    assert ev.elements['t']['value']['p'] == [0, 0]
    assert ev.elements['t']['value']['dir'] == pytest.approx([math.sqrt(.5)]*2)


@pytest.mark.parametrize('offset', [1e10, 1e12])
def test_join_confirmation_preserves_resolvable_small_differences(offset):
    tree = o('+', n(offset), X)
    rec = evaluate(graph(conditional(tree, tree), 0)).elements['t']
    assert rec['state'] == 'defined'
    assert rec['value']['dir'] == pytest.approx([math.sqrt(.5)]*2, abs=1e-10)
    assert rec['value']['p'] == pytest.approx([-offset/2, offset/2])


def test_unresolvable_samples_are_not_a_proven_horizontal_tangent():
    tree = o('+', n(1e20), X)
    assert evaluate(graph(conditional(tree, tree), 0)).elements['t']['reason'] == 'no_convergence'


def test_normal_inherits_undefined_tangent_and_recovers():
    d = graph(fn('sqrt', X), 0)
    d.op('op_normal', 'line.perpendicular', {'point': ref('Q'), 'base': ref('t')}, [('line', 'normal', 'line')])
    rec = evaluate(d).elements['normal']
    assert rec['reason'] == 'upstream' and rec['cause'] in ('Q', 't')
    d.doc['inputs']['x'] = num(1)
    assert evaluate(d).elements['normal']['state'] == 'defined'


def test_commands_printer_reports_the_deferred_operations():
    from animageo.native.commands import print_commands
    d = graph(power(X, 2))
    d.op('op_s', 'line.slope', {'line': ref('t')}, [('number', 's', 'number')])
    printed = print_commands(d.doc)
    assert printed.text.count('line.tangent_function_at') == 1
    assert printed.text.count('line.slope') == 1
    assert [i.code for i in printed.issues] == ['unprintable_operation']*3
