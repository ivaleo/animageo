"""Independent analytic constructions for finite conic elements."""
import copy
import math
from decimal import Decimal, localcontext

import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS, classify, run_checks
from animageo.native.kernel.numeric import tolerances
from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
from animageo.native.kernel.values import Detailed, Input, Undefined
from animageo.native.kernel.conic import from_coeffs
from tests.native.conftest import DocBuilder, num, ref
from tests.native.function_analysis_helpers import X, n, o, power

Y = {'var': 'y'}
ELLIPSE = {'kind': 'ellipse', 'c': [0, 0], 'axis': [1, 0], 'a': 3, 'b': 2}
HYPERBOLA = dict(ELLIPSE, kind='hyperbola', a=2, b=3)
PARABOLA = {'kind': 'parabola', 'vertex': [0, 0], 'axis': [1, 0], 'p': 2}


def call(name, value, *, point=(1, 0), direction=(1, 1), count=2, scale=20):
    assert name in IMPLEMENTATIONS, name
    args = {'conic': Input('conic' if 'kind' in value else 'circle', value), 'count': count,
            'point': Input('point', dict(zip(('x', 'y'), point))),
            'direction': Input('line', {'p': [0, 0], 'dir': direction})}
    return IMPLEMENTATIONS[name](args, OpContext(tolerances(scale)))


def line(result, slot='line'):
    v = result[slot]
    assert not isinstance(v, Undefined), v
    return v.value if isinstance(v, Detailed) else v


def assert_line(v, normal, offset, *, direction=None):
    nx, ny = normal
    length = math.hypot(nx, ny)
    nx, ny, h = nx/length, ny/length, offset/length
    assert v['p'] == pytest.approx([nx*h, ny*h], rel=2e-14, abs=0)
    assert abs(nx*v['dir'][0]+ny*v['dir'][1]) < 1e-14
    assert math.hypot(*v['dir']) == pytest.approx(1)
    if direction is not None:
        assert v['dir'] == pytest.approx(direction, abs=1e-14)


@pytest.mark.parametrize('value,h,found', [(ELLIPSE, 9/math.sqrt(5), 2),
    (HYPERBOLA, 4/math.sqrt(13), 2), (PARABOLA, -1, 1)])
def test_directrices_order_capacity_and_orientation(value, h, found):
    for count in (1, 2, 4):
        r = call('conic.directrices', value, count=count)
        for k in range(1, count+1):
            if k <= found:
                assert r[f'directrix.{k}'].detail == {'found': found}
                assert_line(line(r, f'directrix.{k}'), (1, 0), h if k == 1 else -h, direction=[0, 1])
            else:
                assert r[f'directrix.{k}'] == Undefined('branch_absent')


def test_rotated_translated_elements_and_reverse_parabola():
    v = dict(ELLIPSE, c=[5, -7], axis=[.6, .8])
    h = 9/math.sqrt(5)
    r = call('conic.directrices', v)
    for k, sign in [(1, 1), (2, -1)]:
        assert_line(line(r, f'directrix.{k}'), (.6, .8), -2.6+sign*h, direction=[-.8, .6])
    r = call('conic.directrices', dict(PARABOLA, axis=[-1, 0]))
    assert_line(line(r, 'directrix.1'), (1, 0), 1, direction=[0, -1])


def test_asymptotes_order_and_empty_sets():
    r = call('conic.asymptotes', HYPERBOLA, count=4)
    for k, dx in [(1, 2), (2, -2)]:
        assert_line(line(r, f'asymptote.{k}'), (-3, dx), 0,
                    direction=[dx/math.sqrt(13), 3/math.sqrt(13)])
        assert r[f'asymptote.{k}'].detail == {'found': 2}
    assert r['asymptote.4'] == Undefined('branch_absent')
    for value in (ELLIPSE, PARABOLA, {'c': [0, 0], 'r': 3}):
        assert all(v == Undefined('no_asymptote') for v in call('conic.asymptotes', value, count=4).values())
    assert all(v == Undefined('no_directrix') for v in call('conic.directrices', {'c': [0, 0], 'r': 3}, count=4).values())


@pytest.mark.parametrize('value,point,normal,h', [
    (ELLIPSE, (1, 2), (1/9, .5), 1), (ELLIPSE, (3, 0), (1, 0), 3),
    (HYPERBOLA, (2, 3), (.5, -1/3), 1),
    (PARABOLA, (2, 3), (-2, 3), 4), (PARABOLA, (2, 0), (-1, 0), 2),
    ({'c': [1, -2], 'r': 3}, (2, -2), (1, 0), 10),
])
def test_polar_bilinear_equation(value, point, normal, h):
    v = line(call('line.polar_conic', value, point=point))
    length = math.hypot(*normal)
    assert_line(v, normal, h, direction=[-normal[1]/length, normal[0]/length])


@pytest.mark.parametrize('epsilon', [1e-12, -1e-12, 1e-200, -1e-200])
def test_near_center_polar_remains_finite(epsilon):
    assert_line(line(call('line.polar_conic', ELLIPSE, point=(epsilon, 0))), (1, 0), 9/epsilon)


def test_exact_center_and_unrepresentable_polar():
    assert call('line.polar_conic', ELLIPSE, point=(0, 0))['line'] == Undefined('no_finite_line')
    assert call('line.polar_conic', ELLIPSE, point=(1e-310, 0))['line'] == Undefined('non_finite')


@pytest.mark.parametrize('direction', [(1, 1), (1, -1), (2, 3), (2, -3), (1e-200, 1e-200)])
def test_conjugate_diameter_direction_and_sign(direction):
    dx, dy = direction
    r = line(call('line.conjugate_diameter', HYPERBOLA, direction=direction))
    assert_line(r, (dx/4, -dy/9), 0)
    other = line(call('line.conjugate_diameter', HYPERBOLA, direction=(-dx, -dy)))
    assert r == other


@pytest.mark.parametrize('dv', [1e-12, -1e-12, 1e-200, -1e-200])
def test_parabola_diameter_small_nonzero_component(dv):
    assert_line(line(call('line.conjugate_diameter', PARABOLA, direction=(1, dv))), (0, 1), 2/dv)


def test_parabola_axis_and_zero_direction():
    assert call('line.conjugate_diameter', PARABOLA, direction=(1, 0))['line'] == Undefined('no_finite_line')
    assert call('line.conjugate_diameter', PARABOLA, direction=(0, 0))['line'] == Undefined('invalid_parameter')
    assert call('line.conjugate_diameter', PARABOLA, direction=(1, 1e-310))['line'] == Undefined('non_finite')


@pytest.mark.parametrize('radius', [3, 1e150, 1e-150])
def test_circle_adapter_never_uses_a_world_matrix(radius):
    assert 'conic.from_circle' in IMPLEMENTATIONS
    r = IMPLEMENTATIONS['conic.from_circle']({'circle': Input('circle', {'c': [1e150, -1e150], 'r': radius})}, OpContext(tolerances(20)))
    assert r == {'conic': {'kind': 'ellipse', 'c': [1e150, -1e150], 'axis': [1, 0], 'a': radius, 'b': radius}}
    r = IMPLEMENTATIONS['conic.from_circle']({'circle': Input('circle', {'c': [0, 0], 'r': 0})}, OpContext(tolerances(20)))
    assert r == {'conic': Undefined('degenerate_conic')}


@pytest.mark.parametrize('a', [1.5, 1e150])
def test_nearly_circular_directrix_uses_exact_axis_difference(a):
    b = math.nextafter(a, 0)
    with localcontext() as ctx:
        ctx.prec = 100
        da, db = Decimal(a), Decimal(b)
        h = float(da*da/(da*da-db*db).sqrt())
    r = call('conic.directrices', dict(ELLIPSE, a=a, b=b), scale=a)
    assert line(r, 'directrix.1')['p'][0] == pytest.approx(h, rel=4e-16)


def test_large_axes_normals_and_atomic_overflow():
    v = dict(ELLIPSE, a=3e150, b=2e150)
    assert_line(line(call('line.polar_conic', v, point=(1e150, 0), scale=1e151)), (1, 0), 9e150)
    v = dict(ELLIPSE, a=3e-150, b=2e-150)
    assert_line(line(call('line.polar_conic', v, point=(1e-150, 0))), (1, 0), 9e-150)
    v = dict(ELLIPSE, a=1e308, b=math.nextafter(1e308, 0))
    assert all(v == Undefined('non_finite') for v in call('conic.directrices', v, count=1).values())
    v = dict(ELLIPSE, c=[-1.2e308, 0], a=7e307, b=1e307)
    assert all(v == Undefined('non_finite') for v in call('conic.directrices', v, count=1).values())


def equation_document(coeff=1, point=(3, 0)):
    d = DocBuilder('conic_elements', registry_version='1.13').free('P', *point)
    tree = o('*', n(coeff), o('-', o('+', o('/', power(X, 2), n(9)), o('/', power(Y, 2), n(4))), n(1)))
    d.op('op_c', 'conic.equation', {'expr': {'kind': 'expr', 'ast': tree}, 'refs': {'kind': 'list', 'items': []}}, [('conic', 'c', 'conic')])
    d.op('op_polar', 'line.polar_conic', {'point': ref('P'), 'conic': ref('c')}, [('line', 'polar', 'line')])
    d.op('op_tangent', 'line.tangent_conic_at', {'point': ref('P'), 'conic': ref('c')}, [('line', 'tangent', 'line')])
    d.op('op_directrices', 'conic.directrices', {'conic': ref('c'), 'count': num(4)}, [(f'directrix.{k}', f'd{k}', 'line') for k in range(1, 5)])
    return d


@pytest.mark.parametrize('coeff', [1, -1, 1e12, -1e12, 1e-12, -1e-12])
def test_matrix_sign_scale_tangent_equivalence_checks_and_reload(coeff):
    d = equation_document(coeff)
    assert native.validate(d.doc) == []
    before = copy.deepcopy(d.doc)
    ev = native.evaluate(d.doc)
    assert not ev.diagnostics
    assert ev.elements['polar']['value']['dir'] == ev.elements['tangent']['value']['dir']
    assert ev.elements['polar']['value']['p'] == pytest.approx(ev.elements['tangent']['value']['p'])
    assert_line(ev.elements['d1']['value'], (1, 0), 9/math.sqrt(5))
    assert run_checks(ev).ok
    assert 'op_directrices:focus_directrix' in run_checks(ev).results
    assert native.evaluate(native.load(native.dumps(d.doc))).elements == ev.elements
    assert d.doc == before


def test_finite_polar_despite_overflow_of_local_displacement():
    v = dict(ELLIPSE, c=[-1e308, 0], a=1e308, b=1e308)
    # (P-C)=2e308, a²/(P-C)=5e307; the world line is x=-5e307.
    assert_line(line(call('line.polar_conic', v, point=(1e308, 0))), (1, 0), -5e307)


def test_rotated_large_direction_does_not_overflow_before_normalizing():
    v = dict(ELLIPSE, axis=[.6, .8])
    a = line(call('line.conjugate_diameter', v, direction=(1.5e308, 1.5e308)))
    b = line(call('line.conjugate_diameter', v, direction=(1, 1)))
    assert a['dir'] == pytest.approx(b['dir'], abs=1e-14)


def test_world_projection_can_be_finite_when_its_normal_offset_overflows():
    v = dict(HYPERBOLA, c=[1.4e308, 1.4e308], a=1, b=1)
    r = call('conic.asymptotes', v)
    assert line(r, 'asymptote.2')['p'] == pytest.approx([1.4e308, 1.4e308])


@pytest.mark.parametrize('kind', ['line', 'ray', 'segment', 'vector'])
def test_straight_diameter_inputs_ignore_position(kind):
    value = {'p': [7, 8], 'dir': [1, 1]} if kind == 'line' else {'origin': [7, 8], 'dir': [1, 1]} if kind == 'ray' else {'a': [7, 8], 'b': [8, 9], 'length': math.sqrt(2)}
    args = {'conic': Input('conic', ELLIPSE), 'direction': Input(kind, value)}
    r = IMPLEMENTATIONS['line.conjugate_diameter'](args, OpContext(tolerances(20)))
    assert_line(line(r), (1/9, 1/4), 0)


def test_transition_and_return_preserve_slots_and_document():
    d = DocBuilder('elements_transition', registry_version='1.13')
    d.op('op_e', 'number.free', {}, [('number', 'e', 'number')])
    d.doc['inputs']['e'] = num(.5)
    tree = o('-', o('+', o('*', o('-', n(1), power({'ref': 0}, 2)), power(X, 2)), power(Y, 2)), o('*', n(4), X))
    d.op('op_c', 'conic.equation', {'expr': {'kind': 'expr', 'ast': tree}, 'refs': {'kind': 'list', 'items': [ref('e')]}}, [('conic', 'c', 'conic')])
    d.op('op_d', 'conic.directrices', {'conic': ref('c')}, [('directrix.1', 'D1', 'line'), ('directrix.2', 'D2', 'line')])
    initial = native.dumps(d.doc)
    first = None
    for e in (.5, .99, 1, 1.01, 1.5, 1.01, 1, .99, .5):
        ev = native.evaluate(d.doc, inputs={'e': num(e)})
        assert not ev.diagnostics
        assert ev.elements['c']['value']['kind'] == ('ellipse' if e < 1 else 'parabola' if e == 1 else 'hyperbola')
        near_slot = 'D2' if e < 1 else 'D1'
        assert ev.elements[near_slot]['value']['p'][0] == pytest.approx(-2/(e*(1+e)), abs=1e-9)
        if e == 1:
            assert ev.elements['D2']['reason'] == 'branch_absent'
        if first is None:
            first = ev.elements
    assert ev.elements == first
    assert native.dumps(d.doc) == initial
    assert native.evaluate(native.load(initial)).elements == first


@pytest.mark.parametrize('e', [.999999, 1, 1.000001])
def test_close_to_parabola_uses_the_existing_classification(e):
    v = from_coeffs((1-e*e, 0, 1, -4, 0, 0), (0, 0, 1), OpContext(tolerances(20)))
    r = call('conic.directrices', v)
    key = 'directrix.2' if e < 1 else 'directrix.1'
    assert line(r, key)['p'][0] == pytest.approx(-2/(e*(1+e)), abs=1e-9)


def test_each_defined_directrix_is_checked_with_absent_neighbors():
    ev = native.evaluate(equation_document().doc)
    _, args, result = ev.computed['op_directrices']
    corrupted = copy.deepcopy(result)
    corrupted['directrix.2']['p'][0] += .1
    ev.computed['op_directrices'] = ('conic.directrices', args, corrupted)
    assert run_checks(ev).results['op_directrices:focus_directrix'] == 'failed'


def test_describe_does_not_name_absent_directrices_as_found():
    lines = native.describe(equation_document().doc)
    text = next(v for v in lines if 'директрис' in v)
    assert 'd1' in text and 'd2' in text
    assert 'd3' not in text and 'd4' not in text


def decimal_polar(value, point):
    """Exact binary64 inputs, evaluated independently at high precision."""
    with localcontext() as context:
        context.prec = 800
        x, y = map(Decimal, point)
        cx, cy = map(Decimal, value['vertex'] if value['kind'] == 'parabola' else value['c'])
        ux, uy = map(Decimal, value['axis'])
        s, t = (x-cx)*ux+(y-cy)*uy, -(x-cx)*uy+(y-cy)*ux
        if value['kind'] == 'parabola':
            # The independent polar equation is -p*s + t0*t = p*s0.
            gu, gv, rhs = -Decimal(value['p']), t, Decimal(value['p'])*s
        else:
            a, b = Decimal(value['a']), Decimal(value['b'])
            gu, gv, rhs = s/(a*a), t/(b*b)*(1 if value['kind'] == 'ellipse' else -1), Decimal(1)
        gx, gy = gu*ux-gv*uy, gu*uy+gv*ux
        norm2 = gx*gx+gy*gy
        h = rhs+gx*cx+gy*cy
        return {'p': [float(gx*h/norm2), float(gy*h/norm2)],
                'dir': [float(-gy/norm2.sqrt()), float(gx/norm2.sqrt())]}


def test_small_displacement_survives_exact_cancellation_of_large_translation():
    value = dict(ELLIPSE, c=[1e308, 0], axis=[.6, .8], a=1e-100, b=.5e-100)
    point = (1e308, 1e-200)
    got = line(call('line.polar_conic', value, point=point))
    expected = decimal_polar(value, point)
    assert got['p'] == pytest.approx(expected['p'], rel=2e-14, abs=0)
    assert got['dir'] == pytest.approx(expected['dir'], abs=2e-14)


@pytest.mark.parametrize('factor', [1e16, 1e150])
def test_polar_normal_keeps_compensated_local_residual(factor):
    value = dict(HYPERBOLA, axis=[.6, .8], a=1, b=1e8)
    point = (float(.8*factor), float(-.6*factor))
    got = line(call('line.polar_conic', value, point=point))
    expected = decimal_polar(value, point)
    assert got['dir'] == pytest.approx(expected['dir'], abs=2e-14)
    assert got['p'] == pytest.approx(expected['p'], rel=2e-14, abs=0)


@pytest.mark.parametrize('a,b', [(1e308, 1e-308), (1e-308, 1e308)])
def test_unrepresentable_asymptote_pair_is_atomically_non_finite(a, b):
    r = call('conic.asymptotes', dict(HYPERBOLA, a=a, b=b), count=1)
    assert r == {'asymptote.1': Undefined('non_finite')}


def test_focus_directrix_check_preserves_local_distances_at_large_translation():
    v = dict(ELLIPSE, c=[1e150, 1e150])
    args = {'conic': Input('conic', v)}
    collapsed = {'directrix.1': {'p': [1e150, 0], 'dir': [0, 1]},
                 'directrix.2': {'p': [1e150, 0], 'dir': [0, 1]}}
    error = CHECKS[('conic.directrices', 'focus_directrix')](args, collapsed, tolerances(1e150))
    assert error == pytest.approx(3)


@pytest.mark.parametrize('slot', ['asymptote.1', 'asymptote.2'])
def test_asymptote_check_measures_angle_in_length_units(slot):
    args = {'conic': Input('conic', dict(HYPERBOLA, a=1e5, b=1))}
    bad = {slot: {'p': [0, 0], 'dir': [1 if slot.endswith('1') else -1, 0]}}
    error = CHECKS[('conic.asymptotes', 'asymptotic_direction')](args, bad, tolerances(20))
    assert error == pytest.approx(2e-4, rel=1e-9)


@pytest.mark.parametrize('scale', [1e-6, 1, 1e6])
def test_rotated_translated_elements_scale_with_the_scene(scale):
    value = dict(ELLIPSE, c=[5*scale, -7*scale], axis=[.6, .8], a=3*scale, b=2*scale)
    r = call('conic.directrices', value, scale=20*scale)
    for k, sign in [(1, 1), (2, -1)]:
        assert_line(line(r, f'directrix.{k}'), (.6, .8), scale*(-2.6+sign*9/math.sqrt(5)))
    polar = line(call('line.polar_conic', value, point=(6.8*scale, -4.6*scale), scale=20*scale))
    assert_line(polar, (.6, .8), .4*scale, direction=[-.8, .6])


@pytest.mark.parametrize('value,point', [
    (ELLIPSE, (3/math.sqrt(2), 2/math.sqrt(2))),
    (HYPERBOLA, (2*math.sqrt(2), 3)),
    (PARABOLA, (2, 2*math.sqrt(2))),
    (dict(ELLIPSE, c=[1, -2], a=3, b=3), (1+3/math.sqrt(2), -2+3/math.sqrt(2))),
    (dict(ELLIPSE, c=[5, -7], axis=[.6, .8]), (6.8, -4.6)),
])
def test_polar_agrees_with_tangent_at_nonaxial_curve_points(value, point):
    p = line(call('line.polar_conic', value, point=point))
    t = line(call('line.tangent_conic_at', value, point=point))
    assert p['p'] == pytest.approx(t['p'], rel=2e-14, abs=1e-14)
    assert p['dir'] == pytest.approx(t['dir'], abs=2e-14)


@pytest.mark.parametrize('name', ['conic.directrices', 'conic.asymptotes', 'line.polar_conic', 'line.conjugate_diameter'])
def test_canonical_degenerate_values_are_rejected(name):
    assert all(v == Undefined('degenerate_conic') for v in call(name, {'kind': 'pair_of_lines'}).values())


def test_circle_adapter_rejects_nonfinite_canonical_data():
    r = IMPLEMENTATIONS['conic.from_circle']({'circle': Input('circle', {'c': [0, 0], 'r': math.inf})}, OpContext(tolerances(20)))
    assert r == {'conic': Undefined('non_finite')}


@pytest.mark.parametrize('value,point', [
    (dict(PARABOLA, axis=[.6, .8], p=1e150), (1e-200, 0)),
    (dict(ELLIPSE, a=1e150, b=1e-150), (1e-200, 1e-200)),
])
def test_polar_rounds_unrepresentable_unit_normal_component(value, point):
    result = call('line.polar_conic', value, point=point)
    actual = line(result)
    expected = decimal_polar(value, point)
    assert actual['p'] == pytest.approx(expected['p'], rel=2e-14, abs=0)
    assert actual['dir'] == pytest.approx(expected['dir'], abs=2e-15)
    args = {'conic': Input('conic', value),
            'point': Input('point', dict(zip(('x', 'y'), point)))}
    tol = tolerances(20)
    error = CHECKS[('line.polar_conic', 'polar_incidence')](args, result, tol)
    assert classify(error, tol) == 'passed'


def test_parabola_diameter_with_tiny_direction_keeps_finite_offset_and_checks():
    value = dict(PARABOLA, axis=[.6, .8], p=1e150)
    direction = (1e-200, 0)
    result = call('line.conjugate_diameter', value, direction=direction, scale=1e150)
    actual = line(result)
    # dv*t=p*du gives t=-3*p/4, so its nearest point is -3*p*n/4.
    assert actual['p'] == pytest.approx([6e149, -4.5e149], rel=2e-14, abs=0)
    assert actual['dir'] == pytest.approx([.6, .8], abs=2e-15)
    args = {'conic': Input('conic', value),
            'direction': Input('line', {'p': [0, 0], 'dir': direction})}
    tol = tolerances(1e150)
    for check in ('conjugacy', 'through_center'):
        error = CHECKS[('line.conjugate_diameter', check)](args, result, tol)
        assert classify(error, tol) == 'passed'


def test_ellipse_diameter_rounds_unrepresentable_unit_normal_component():
    value = dict(ELLIPSE, a=1e150, b=1e-150)
    direction = (math.sqrt(.5), math.sqrt(.5))
    result = call('line.conjugate_diameter', value, direction=direction)
    # Qd has component ratio b²/a²=1e-600; its rounded unit normal is (0,1).
    assert line(result) == {'p': [0, 0], 'dir': [-1, 0]}
    args = {'conic': Input('conic', value),
            'direction': Input('line', {'p': [0, 0], 'dir': direction})}
    tol = tolerances(20)
    for check in ('conjugacy', 'through_center'):
        error = CHECKS[('line.conjugate_diameter', check)](args, result, tol)
        assert classify(error, tol) == 'passed'


def test_circle_polar_accuracy_stays_within_input_coordinate_ulps():
    radius, point = 1e16, (1, 0)
    value = {'c': [-radius, 0], 'r': radius}
    result = call('line.polar_conic', value, point=point, scale=radius)
    actual = line(result)
    # x=-r+r²/(r+1)=-r/(r+1); evaluate before binary64 cancellation.
    with localcontext() as context:
        context.prec = 80
        true_x = float(-Decimal(radius)/(Decimal(radius)+1))
    input_size = max(abs(v) for v in (*value['c'], radius, *point))
    assert abs(actual['p'][0]-true_x) <= 2*math.ulp(input_size)
    assert actual['p'][1] == 0
    assert actual['dir'] == [0, 1]
    args = {'conic': Input('circle', value), 'point': Input('point', {'x': 1, 'y': 0})}
    tol = tolerances(radius)
    error = CHECKS[('line.polar_conic', 'polar_incidence')](args, result, tol)
    assert classify(error, tol) == 'passed'
