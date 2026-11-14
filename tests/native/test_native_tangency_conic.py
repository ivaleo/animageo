"""Analytic contacts, orientations and fixed slots of conic tangents."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import run_checks
from tests.native.conftest import DocBuilder, num, ref
from tests.native.function_analysis_helpers import X, n, o as op, power

Y = {'var': 'y'}


def sq(a):
    return power(a, 2)


ELLIPSE = op('-', op('+', op('/', sq(X), n(4)), sq(Y)), n(1))
CIRCLE = op('-', op('+', sq(X), sq(Y)), n(4))
PARABOLA = op('-', sq(X), Y)
HYPERBOLA = op('-', op('-', sq(X), sq(Y)), n(1))


def document(tree=ELLIPSE, point=(4, 0)):
    d = DocBuilder('conic_tangents', registry_version='1.12').free('P', *point)
    d.op('op_c', 'conic.equation', {'expr': {'kind': 'expr', 'ast': tree},
         'refs': {'kind': 'list', 'items': []}}, [('conic', 'c', 'conic')])
    return d


def tangents(d, *, count=2, strict=False, parallel=False, bind_touch=True):
    name = 'tangent_conic_at' if strict else 'tangents_parallel_conic' if parallel else 'tangents_from_point_conic'
    args = {'conic': ref('c'), 'base' if parallel else 'point': ref('base' if parallel else 'P')}
    if strict:
        outputs = [('line', 't', 'line')]
    else:
        if count is not None:
            args['count'] = num(count)
        capacity = count or 2
        outputs = [(f'tangent.{k}', f't{k}', 'line') for k in range(1, capacity+1)]
        if bind_touch:
            outputs += [(f'touch.{k}', f'Q{k}', 'point') for k in range(1, capacity+1)]
    return d.op('op_t', 'line.'+name, args, outputs)


def evaluate(d):
    assert native.validate(d.doc) == []
    result = native.evaluate(d.doc)
    assert result.diagnostics == []
    return result


def line_coefficients(rec):
    assert rec['state'] == 'defined', rec
    p, (dx, dy) = rec['value']['p'], rec['value']['dir']
    return -dy, dx, dy*p[0]-dx*p[1]


def assert_line(rec, coefficients):
    actual = line_coefficients(rec)
    length = math.hypot(*coefficients[:2])
    expected = [v/length for v in coefficients]
    if sum(a*b for a, b in zip(actual[:2], expected[:2])) < 0:
        expected = [-v for v in expected]
    assert actual == pytest.approx(expected, abs=1e-8)


def assert_contacts(ev, points, count=2):
    for k, (x, y) in enumerate(points, 1):
        assert ev.elements[f'Q{k}']['value'] == pytest.approx({'x': x, 'y': y}, abs=1e-8)
        assert ev.elements[f't{k}']['detail'] == ev.elements[f'Q{k}']['detail'] == {'found': len(points)}
    for k in range(len(points)+1, count+1):
        for key in (f't{k}', f'Q{k}'):
            assert ev.elements[key]['reason'] == 'branch_absent'
            assert 'detail' not in ev.elements[key]
    assert run_checks(ev).ok


@pytest.mark.parametrize('tree,point,coefficients', [
    (ELLIPSE, (2, 0), (1, 0, -2)), (ELLIPSE, (0, 1), (0, 1, -1)),
    (CIRCLE, (0, 2), (0, 1, -2)), (PARABOLA, (1, 1), (2, -1, -1)),
    (HYPERBOLA, (1, 0), (1, 0, -1)),
])
def test_strict_tangent_and_gradient_orientation(tree, point, coefficients):
    ev = evaluate(tangents(document(tree, point), strict=True))
    assert_line(ev.elements['t'], coefficients)
    if tree == ELLIPSE and point == (2, 0):
        assert ev.elements['t']['value']['dir'] == [0, 1]
    assert run_checks(ev).ok


def test_strict_tangent_does_not_turn_into_external_search():
    ev = evaluate(tangents(document(point=(4, 0)), strict=True))
    assert ev.elements['t']['reason'] == 'not_on_curve'


@pytest.mark.parametrize('tree,point,contacts,lines', [
    (ELLIPSE, (4, 0), [(1, math.sqrt(3)/2), (1, -math.sqrt(3)/2)],
     [(1/4, math.sqrt(3)/2, -1), (1/4, -math.sqrt(3)/2, -1)]),
    (ELLIPSE, (-4, 0), [(-1, -math.sqrt(3)/2), (-1, math.sqrt(3)/2)],
     [(-1/4, -math.sqrt(3)/2, -1), (-1/4, math.sqrt(3)/2, -1)]),
    (CIRCLE, (4, 0), [(1, math.sqrt(3)), (1, -math.sqrt(3))],
     [(1, math.sqrt(3), -4), (1, -math.sqrt(3), -4)]),
    (PARABOLA, (0, -1), [(1, 1), (-1, 1)], [(2, -1, -1), (-2, -1, -1)]),
    (HYPERBOLA, (0, 2), [(math.sqrt(5)/2, -.5), (-math.sqrt(5)/2, -.5)],
     [(math.sqrt(5)/2, .5, -1), (-math.sqrt(5)/2, .5, -1)]),
])
def test_external_contacts_use_the_polar_rank(tree, point, contacts, lines):
    ev = evaluate(tangents(document(tree, point)))
    assert_contacts(ev, contacts)
    for k, coefficients in enumerate(lines, 1):
        assert_line(ev.elements[f't{k}'], coefficients)


@pytest.mark.parametrize('tree,point,reason', [
    (ELLIPSE, (0, 0), 'point_inside'), (PARABOLA, (0, 1), 'no_tangent'),
    (HYPERBOLA, (0, 0), 'no_tangent'),
])
def test_empty_sets_have_a_geometric_reason(tree, point, reason):
    ev = evaluate(tangents(document(tree, point)))
    assert all(ev.elements[key]['reason'] == reason for key in ('t1', 't2', 'Q1', 'Q2'))


@pytest.mark.parametrize('tree,point,contact', [
    (ELLIPSE, (2, 0), (2, 0)), (PARABOLA, (0, 0), (0, 0)),
    (HYPERBOLA, (1, 1), (1, 0)), (HYPERBOLA, (1, 0), (1, 0)),
])
def test_distinct_single_contact_excludes_infinite_hyperbola_contact(tree, point, contact):
    ev = evaluate(tangents(document(tree, point)))
    assert_contacts(ev, [contact])


def parallel_document(tree, direction):
    d = document(tree).free('A', 0, 0).free('B', *direction).line('base', 'A', 'B')
    return tangents(d, parallel=True)


@pytest.mark.parametrize('tree,direction,contacts', [
    (CIRCLE, (-1, 0), [(0, 2), (0, -2)]),
    (CIRCLE, (1, 0), [(0, -2), (0, 2)]),
    (ELLIPSE, (0, 1), [(2, 0), (-2, 0)]),
    (HYPERBOLA, (0, 1), [(-1, 0), (1, 0)]),
    (PARABOLA, (-1, 0), [(0, 0)]),
    (PARABOLA, (1, 2), [(1, 1)]),
])
def test_parallel_contacts_keep_the_oriented_base_normal(tree, direction, contacts):
    ev = evaluate(parallel_document(tree, direction))
    assert_contacts(ev, contacts)
    length = math.hypot(*direction)
    for k in range(1, len(contacts)+1):
        assert ev.elements[f't{k}']['value']['dir'] == pytest.approx([v/length for v in direction])


@pytest.mark.parametrize('tree,direction', [(PARABOLA, (0, 1)), (HYPERBOLA, (1, 1)), (HYPERBOLA, (1, 0))])
def test_parallel_empty_and_asymptotic_directions(tree, direction):
    ev = evaluate(parallel_document(tree, direction))
    assert ev.elements['t1']['reason'] == ev.elements['Q2']['reason'] == 'no_tangent'


def test_rotated_ellipse_preserves_exact_polar_order():
    u, v = (.6, .8), (-.8, .6)
    U = op('+', op('*', n(.6), X), op('*', n(.8), Y))
    V = op('+', op('*', n(-.8), X), op('*', n(.6), Y))
    tree = op('-', op('+', op('/', sq(U), n(4)), sq(V)), n(1))
    ev = evaluate(tangents(document(tree, (2.4, 3.2))))
    assert_contacts(ev, [(u[0]+sign*math.sqrt(3)/2*v[0], u[1]+sign*math.sqrt(3)/2*v[1]) for sign in (1, -1)])


def test_capacity_is_independent_of_found_and_has_no_implicit_elements():
    d = tangents(document(PARABOLA, (0, -1)), count=1)
    ev = evaluate(d)
    assert ev.elements['t1']['detail'] == ev.elements['Q1']['detail'] == {'found': 2}
    assert set(ev.elements) == set(d.doc['elements'])
    assert_contacts(evaluate(tangents(document(PARABOLA, (0, -1)), count=4)), [(1, 1), (-1, 1)], count=4)


def test_default_capacity_and_invalid_count_validation():
    assert_contacts(evaluate(tangents(document(PARABOLA, (0, -1)), count=None)), [(1, 1), (-1, 1)])
    for bad in (0, -1, 1.5, 101):
        d = tangents(document())
        d.doc['operations']['op_t']['args']['count'] = num(bad)
        assert native.validate(d.doc)


@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('bind_touch', [False, True])
def test_line_parameter_zero_is_its_slot_contact(parallel, bind_touch):
    d = document(PARABOLA, (0, -1))
    if parallel:
        d.free('A', 0, 0).free('B', 1, 2).line('base', 'A', 'B')
    tangents(d, parallel=parallel, bind_touch=bind_touch)
    d.on_path('Z', 't1', 0)
    assert evaluate(d).elements['Z']['value'] == pytest.approx({'x': 1, 'y': 1})


@pytest.mark.parametrize('tree', [op('*', X, Y), sq(X), op('+', sq(X), sq(Y)), op('+', op('+', sq(X), sq(Y)), n(1))])
def test_degenerate_source_propagates_original_cause(tree):
    d = tangents(document(tree))
    ev = evaluate(d)
    assert ev.elements['c']['reason'] == 'degenerate_conic'
    assert ev.elements['t1']['reason'] == 'upstream' and ev.elements['t1']['cause'] == 'c'


def test_existing_circle_tangents_keep_their_frozen_multiplicity_and_side():
    d = DocBuilder('circle_tangents', registry_version='1.12').free('O', 0, 0).free('R', 2, 0).free('P', 4, 0)
    d.circle('c', 'O', 'R').op('op_old', 'line.tangents_from_point', {'point': ref('P'), 'circle': ref('c')},
         [('tangent.1', 't1', 'line'), ('tangent.2', 't2', 'line'), ('touch.1', 'Q1', 'point'), ('touch.2', 'Q2', 'point')])
    assert evaluate(d).elements['Q1']['value'] == pytest.approx({'x': 1, 'y': -math.sqrt(3)})
    d.doc['inputs']['P']['value'] = [2, 0]
    ev = evaluate(d)
    for key in ('t1', 't2', 'Q1', 'Q2'):
        assert ev.elements[key]['state'] == 'defined'
        assert ev.elements[key]['detail']['multiplicity'] == 2


def test_distant_parabola_point_retains_both_finite_contacts():
    ev = evaluate(tangents(document(PARABOLA, (1e12, 0))))
    if ev.elements['t1']['state'] == 'defined':
        assert_contacts(ev, [(2e12, 4e24), (0, 0)])
    else:
        assert all(ev.elements[k]['reason'] == 'non_finite' for k in ('t1', 't2', 'Q1', 'Q2'))
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
    from animageo.native.kernel.values import Input
    args = {'conic': Input('conic', {'kind': 'parabola', 'vertex': [0, 0], 'axis': [0, 1], 'p': .5}),
            'point': Input('point', {'x': 1e12, 'y': 0}), 'count': 2}
    result = IMPLEMENTATIONS['line.tangents_from_point_conic'](args, OpContext(tolerances(1e12)))
    assert result['touch.1'].value == pytest.approx({'x': 2e12, 'y': 4e24})
    assert result['touch.2'].value == {'x': 0, 'y': 0}
    assert result['touch.1'].detail == {'found': 2}


@pytest.mark.parametrize('scale', [1e-80, 1e-6, 1, 1e6, 1e80])
def test_canonical_tangents_scale_without_squaring_semiaxes(scale):
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
    from animageo.native.kernel.values import Input
    value = {'kind': 'ellipse', 'c': [0, 0], 'axis': [1, 0], 'a': 2*scale, 'b': scale}
    ctx = OpContext(tolerances(scale))
    result = IMPLEMENTATIONS['line.tangents_from_point_conic']({
        'conic': Input('conic', value), 'point': Input('point', {'x': 4*scale, 'y': 0}), 'count': 2}, ctx)
    for k, sign in [(1, 1), (2, -1)]:
        rec = result[f'touch.{k}']
        assert rec.value['x']/scale == pytest.approx(1)
        assert rec.value['y']/scale == pytest.approx(sign*math.sqrt(3)/2)
        assert rec.detail == {'found': 2}


def test_checks_validate_defined_pairs_when_another_slot_is_absent():
    ev = evaluate(tangents(document(PARABOLA, (0, 0))))
    assert ev.elements['t2']['reason'] == 'branch_absent'
    name, args, result = ev.computed['op_t']
    result['touch.1'] = {'x': 0, 'y': 1}
    assert run_checks(ev).results['op_t:on_curve'] == 'failed'
    result['touch.1'] = {'x': 0, 'y': 0}
    result['tangent.1'] = {'p': [0, 0], 'dir': [0, 1]}
    assert run_checks(ev).results['op_t:tangent'] == 'failed'


def test_conic_fixtures_have_independent_contacts_and_replay():
    from animageo.native.conic_tangency_fixtures import build_fixtures
    from animageo.native.parity import verify_fixture
    fixtures = build_fixtures()
    assert set(fixtures) == {name+'.json' for name in ('conic_tangent_at', 'conic_tangents_from_point',
        'conic_tangents_parallel', 'conic_tangent_degeneracy', 'conic_tangent_infinite_contact',
        'conic_tangent_numeric_limits', 'tangent_slot_changes', 'tangent_found_capacity')}
    for fixture in fixtures.values():
        assert verify_fixture(fixture) == []


@pytest.mark.parametrize('name', ['tangent_conic_at', 'tangents_from_point_conic', 'tangents_parallel_conic'])
def test_defensive_degenerate_values_are_refused_by_each_adapter(name):
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
    from animageo.native.kernel.values import Input, Undefined
    args = {'conic': Input('conic', {'kind': 'point'}), 'count': 2,
            'point': Input('point', {'x': 1, 'y': 0}),
            'base': Input('line', {'p': [0, 0], 'dir': [1, 0]})}
    result = IMPLEMENTATIONS['line.'+name](args, OpContext(tolerances(1)))
    assert result and all(isinstance(v, Undefined) and v.reason == 'degenerate_conic' for v in result.values())


def test_nonfinite_strict_projection_and_parallel_contact_are_refused():
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
    from animageo.native.kernel.values import Input, Undefined
    ctx = OpContext(tolerances(1e308))
    nx, ny = math.cos(math.pi/8), math.sin(math.pi/8)
    circle = {'kind': 'ellipse', 'c': [1.45e308]*2, 'axis': [1, 0], 'a': 1e307, 'b': 1e307}
    result = IMPLEMENTATIONS['line.tangent_conic_at']({
        'conic': Input('conic', circle),
        'point': Input('point', {'x': 1.45e308+nx*1e307, 'y': 1.45e308+ny*1e307})}, ctx)
    assert isinstance(result['line'], Undefined) and result['line'].reason == 'non_finite'
    parabola = {'kind': 'parabola', 'vertex': [0, 0], 'axis': [0, 1], 'p': 1e308}
    result = IMPLEMENTATIONS['line.tangents_parallel_conic']({
        'conic': Input('conic', parabola), 'base': Input('line', {'p': [0, 0], 'dir': [1e-9, 1]}), 'count': 2}, ctx)
    assert all(isinstance(v, Undefined) and v.reason == 'non_finite' for v in result.values())


@pytest.mark.parametrize('bind_touch', [False, True])
def test_near_asymptote_path_frame_uses_the_original_slot_contact(bind_touch):
    d = tangents(document(HYPERBOLA, (1, .99999)), bind_touch=bind_touch)
    d.on_path('Z', 't1', 0)
    ev = evaluate(d)
    result = ev.computed['op_t'][2]['touch.1']
    assert ev.elements['Z']['value'] == result


@pytest.mark.parametrize('delta', [1e-8, 1e-10])
def test_unrepresentable_hyperbola_tangent_does_not_return_an_asymptote(delta):
    ev = evaluate(tangents(document(HYPERBOLA, (1, 1-delta))))
    if ev.elements['t1']['state'] == 'defined':
        assert run_checks(ev).ok
        assert ev.elements['t1']['value']['p'] != [0, 0]
    else:
        assert ev.elements['t1']['reason'] == 'non_finite'


def test_distant_rotated_parabola_never_returns_failed_geometric_checks():
    U = op('+', op('*', n(.6), op('-', X, n(3))), op('*', n(.8), op('+', Y, n(2))))
    V = op('+', op('*', n(-.8), op('-', X, n(3))), op('*', n(.6), op('+', Y, n(2))))
    tree = op('-', sq(V), U)
    ev = evaluate(tangents(document(tree, (3-.8e6, -2+.6e6))))
    if ev.elements['t1']['state'] == 'defined':
        assert run_checks(ev).ok
    else:
        assert ev.elements['t1']['reason'] == 'non_finite'


@pytest.mark.parametrize('tree,point', [
    (PARABOLA, (0, 1e16)),
    (HYPERBOLA, (1e16, 1e16-8)),
    (ELLIPSE, (1e16, 0)),
])
def test_distant_points_are_not_contacts_of_a_strict_tangent(tree, point):
    ev = evaluate(tangents(document(tree, point), strict=True))
    assert ev.elements['t']['reason'] == 'not_on_curve'


@pytest.mark.parametrize('tree,point', [
    (PARABOLA, (0, 1e16)),
    (HYPERBOLA, (1e16, 1e16-8)),
])
def test_distant_noncontact_points_do_not_bypass_the_tangent_search(tree, point):
    ev = evaluate(tangents(document(tree, point)))
    assert all(ev.elements[key]['reason'] == 'no_tangent' for key in ('t1', 't2', 'Q1', 'Q2'))


@pytest.mark.parametrize('tree,point', [
    (PARABOLA, (0, 1e16)),
    (HYPERBOLA, (1e16, 1e16-8)),
    (ELLIPSE, (1e16, 0)),
])
def test_on_curve_check_rejects_distant_corrupted_contacts(tree, point):
    source = (0, 0) if tree == PARABOLA else (1, 0) if tree == HYPERBOLA else (2, 0)
    ev = evaluate(tangents(document(tree, source)))
    ev.computed['op_t'][2]['touch.1'] = {'x': point[0], 'y': point[1]}
    assert run_checks(ev).results['op_t:on_curve'] == 'failed'


@pytest.mark.parametrize('scale', [1e-80, 1, 1e80])
@pytest.mark.parametrize('kind', ['parabola', 'hyperbola', 'ellipse'])
def test_contact_membership_and_checks_use_length_units_at_extreme_coordinates(kind, scale):
    from animageo.native.kernel.checks import CHECKS, classify
    from animageo.native.kernel.numeric import tolerances
    from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
    from animageo.native.kernel.values import Input, Undefined
    if kind == 'parabola':
        conic = {'kind': kind, 'vertex': [0, 0], 'axis': [0, 1], 'p': .5*scale}
        point = {'x': 0, 'y': 1e16*scale}
    else:
        conic = {'kind': kind, 'c': [0, 0], 'axis': [1, 0],
                 'a': (2 if kind == 'ellipse' else 1)*scale, 'b': scale}
        point = {'x': 1e16*scale, 'y': (1e16-8)*scale if kind == 'hyperbola' else 0}
    args = {'conic': Input('conic', conic), 'point': Input('point', point), 'count': 2}
    tol = tolerances(scale)
    strict = IMPLEMENTATIONS['line.tangent_conic_at'](args, OpContext(tol))
    assert isinstance(strict['line'], Undefined) and strict['line'].reason == 'not_on_curve'
    # This carrier is deliberately corrupt: on_curve must independently
    # reject the contact even when the producer result is supplied directly.
    result = {'tangent.1': {'p': [0, 0], 'dir': [1, 0]}, 'touch.1': point}
    error = CHECKS[('line.tangents_from_point_conic', 'on_curve')](args, result, tol)
    assert classify(error, tol) == 'failed'
    if kind != 'ellipse':
        found = IMPLEMENTATIONS['line.tangents_from_point_conic'](args, OpContext(tol))
        assert all(isinstance(value, Undefined) and value.reason == 'no_tangent' for value in found.values())


@pytest.mark.parametrize('side', [-1, 1])
def test_small_nonzero_hyperbola_quadratic_keeps_the_distant_finite_branch(side):
    ev = evaluate(tangents(document(HYPERBOLA, (1, 1+side*1e-12))))
    records = [ev.elements[key] for key in ('t1', 't2', 'Q1', 'Q2')]
    if records[0]['state'] == 'defined':
        assert all(record['state'] == 'defined' and record['detail'] == {'found': 2} for record in records)
        assert run_checks(ev).ok
    else:
        assert all(record['reason'] == 'non_finite' for record in records)


def test_exact_hyperbola_linear_limit_still_has_one_finite_contact():
    ev = evaluate(tangents(document(HYPERBOLA, (1, 1))))
    assert_contacts(ev, [(1, 0)])
