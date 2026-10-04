"""Operations of registry 1.3 (L2 stage 2): angles, marks, the incircle."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS, classify
from animageo.native.kernel.evaluate import evaluate
from animageo.native.kernel.ops.angle import convex_measure, normalize_angle, wrap_angle
from tests.native.conftest import DocBuilder, point_input

PI = math.pi


def ev(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements


def B(name='l2a2'):
    return DocBuilder(name, registry_version='1.3')


def undefined(type_, reason, **extra):
    return dict({'state': 'undefined', 'type': type_, 'reason': reason}, **extra)


def value(record):
    assert record['state'] == 'defined', record
    return record['value']


def close(a, b, eps=1e-12):
    return len(a) == len(b) and all(abs(p - q) <= eps for p, q in zip(a, b))


def decisions_of(doc, op_id):
    found = []
    evaluate(doc, _decisions=found)
    return [d[1] for d in found if d[0] == op_id]


def check_results(doc, inputs=None):
    return native.check(doc, inputs=inputs).results


# ── helpers ──────────────────────────────────────────────────────────────

class TestAngleHelpers:
    @pytest.mark.parametrize('theta, expected', [(0.0, 0.0), (-0.0, 0.0), (1.0, 1.0), (-PI / 2, 1.5 * PI),
                                                 (PI, PI), (-1e-20, 0.0)])
    def test_normalize(self, theta, expected):
        got = normalize_angle(theta)
        assert got == expected and math.copysign(1.0, got) == 1.0

    def test_normalize_rounding_to_two_pi_gives_zero(self):
        # -1e-20 + 2 pi rounds to 2 pi in floating point; the result must stay in [0, 2 pi)
        assert -1e-20 + 2 * PI == 2 * PI
        assert normalize_angle(-1e-20) == 0.0

    @pytest.mark.parametrize('size, m', [(0.0, 0.0), (PI / 3, PI / 3), (PI, PI), (1.5 * PI, PI / 2)])
    def test_convex(self, size, m):
        assert math.isclose(convex_measure(size), m, abs_tol=1e-15)

    @pytest.mark.parametrize('d, w', [(0.0, 0.0), (PI, -PI), (-PI, -PI), (1.5 * PI, -PI / 2), (-1.5 * PI, PI / 2),
                                      (2 * PI, 0.0), (0.1, 0.1)])
    def test_wrap(self, d, w):
        assert math.isclose(wrap_angle(d), w, abs_tol=1e-15)


# ── angle.by_points ──────────────────────────────────────────────────────

class TestAngleByPoints:
    def doc(self, a=(4, 0), v=(0, 0), b=(0, 3)):
        return B('ang').free('A', *a).free('V', *v).free('C', *b).angle('g', 'A', 'V', 'C').doc

    def test_right_angle(self):
        assert value(ev(self.doc())['g']) == {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': PI / 2, 'size': PI / 2}

    def test_orientation_is_counterclockwise_from_a(self):
        g = value(ev(self.doc(a=(0, 3), b=(4, 0)))['g'])
        assert (g['a0'], g['size']) == (PI / 2, 1.5 * PI)
        assert g['a1'] == g['a0'] + g['size'] == 2 * PI

    def test_vertex_elsewhere(self):
        g = value(ev(self.doc(a=(3, 2), v=(1, 2), b=(1, 5)))['g'])
        assert g['vertex'] == [1.0, 2.0] and close((g['a0'], g['size']), (0.0, PI / 2))

    def test_slanted(self):
        g = value(ev(self.doc(a=(1, 1), b=(-1, 1)))['g'])
        assert close((g['a0'], g['a1'], g['size']), (PI / 4, 3 * PI / 4, PI / 2))

    def test_a0_in_lower_half_plane(self):
        g = value(ev(self.doc(a=(0, -2), b=(2, 0)))['g'])
        assert close((g['a0'], g['size']), (1.5 * PI, PI / 2))
        assert 0 <= g['a0'] < 2 * PI

    def test_straight_angle(self):
        g = value(ev(self.doc(a=(2, 0), b=(-3, 0)))['g'])
        assert close((g['a0'], g['size']), (0.0, PI))

    def test_zero_angle(self):
        g = value(ev(self.doc(a=(2, 0), b=(5, 0)))['g'])
        assert (g['a0'], g['size']) == (0.0, 0.0)

    @pytest.mark.parametrize('a, b', [((0, 0), (0, 3)), ((4, 0), (0, 0)), ((0, 0), (0, 0))])
    def test_coincident_points(self, a, b):
        assert ev(self.doc(a=a, b=b))['g'] == undefined('angle', 'coincident_points')

    def test_upstream(self):
        b = B('up').free('P', 0, 0).free('Q', 0, 0).free('R', 2, 2).line('l', 'P', 'Q')
        b.free('V', 0, 0).free('A', 1, 0).intersect('X', 'l', 'l').angle('g', 'A', 'V', 'X')
        assert ev(b.doc)['g'] == undefined('angle', 'upstream', cause='l')

    def test_decisions(self):
        assert decisions_of(self.doc(a=(4, 1)), 'op_g') == ['coincident_points', 'coincident_points', 'angle_wrap',
                                                            'zero_angle']
        # an exactly right angle has q = 0: no zero_angle decision
        assert decisions_of(self.doc(), 'op_g') == ['coincident_points', 'coincident_points', 'angle_wrap']
        # a side with a negative x has no wrap decision; an obtuse angle has no zero_angle decision
        assert decisions_of(self.doc(a=(-1, 1), b=(1, -2)), 'op_g') == ['coincident_points', 'coincident_points']

    def test_check_passes(self):
        assert check_results(self.doc(a=(3, 1), v=(-1, 2), b=(-4, -1))) == {'op_g:sides': 'passed'}

    def test_zero_angle_noise_is_a_boundary(self):
        # just below the a side the size is close to 2 pi: the decision zero_angle marks the jump
        g = value(ev(self.doc(a=(2, 0), b=(5, -1e-9)))['g'])
        assert g['size'] > 2 * PI - 1e-9


# ── mark.equal_segments / mark.equal_angles ──────────────────────────────

class TestEqualSegments:
    def doc(self, count=None, c=(0, 3)):
        b = B('es').free('A', 0, 0).free('Q', 3, 0).free('C', *c)
        b.segment('s', 'A', 'Q').segment('t', 'A', 'C')
        return b.equal_segments('m', 's', 't', count=count).doc

    def test_default_count(self):
        assert ev(self.doc())['m'] == {'state': 'defined', 'type': 'mark',
                                       'value': {'kind': 'equal_segments', 'count': 1}}

    @pytest.mark.parametrize('count', [1, 2, 3])
    def test_counts(self, count):
        assert value(ev(self.doc(count))['m']) == {'kind': 'equal_segments', 'count': count}

    @pytest.mark.parametrize('count', [0, 4, 1.5, -1, 2.0000001])
    def test_invalid_count(self, count):
        assert ev(self.doc(count))['m'] == undefined('mark', 'invalid_parameter')

    def test_three_segments(self):
        b = B('es3').free('A', 0, 0).free('Q', 3, 0).free('C', 0, 3).free('D', -3, 0)
        b.segment('s', 'A', 'Q').segment('t', 'A', 'C').segment('u', 'A', 'D').equal_segments('m', 's', 't', 'u')
        assert value(ev(b.doc)['m'])['count'] == 1
        assert check_results(b.doc)['op_m:equal'] == 'passed'

    def test_check(self):
        assert check_results(self.doc())['op_m:equal'] == 'passed'
        assert check_results(self.doc(c=(0, 4)))['op_m:equal'] == 'failed'
        # a failed check is a warning: the mark stays defined
        assert ev(self.doc(c=(0, 4)))['m']['state'] == 'defined'

    def test_upstream(self):
        b = B('esu').free('A', 0, 0).free('Q', 3, 0).free('P', 1, 1).free('R', 1, 1).line('l', 'P', 'R')
        b.intersect('X', 'l', 'l').segment('s', 'A', 'Q').segment('t', 'A', 'X').equal_segments('m', 's', 't')
        assert ev(b.doc)['m'] == undefined('mark', 'upstream', cause='l')

    def test_wrong_item_type(self):
        b = B('est').free('A', 0, 0).free('Q', 3, 0).free('C', 0, 3).segment('s', 'A', 'Q').line('l', 'A', 'C')
        b.equal_segments('m', 's', 'l')
        assert ev(b.doc)['m'] == {'state': 'error', 'type': 'mark', 'reason': 'type_mismatch'}

    def test_no_decisions(self):
        assert decisions_of(self.doc(), 'op_m') == []


class TestEqualAngles:
    def doc(self, d=(0, 3), count=None):
        b = B('ea').free('A', 4, 0).free('V', 0, 0).free('C', 0, 3).free('W', 5, 5).free('E', 8, 5).free('D', *d)
        b.angle('g', 'A', 'V', 'C').angle('h', 'E', 'W', 'D')
        return b.equal_angles('m', 'g', 'h', count=count).doc

    def test_defined(self):
        assert value(ev(self.doc(d=(5, 9), count=3))['m']) == {'kind': 'equal_angles', 'count': 3}

    def test_convex_measure_is_compared(self):
        # the reflex angle (size 3 pi / 2) and the right angle have equal convex measures
        assert value(ev(self.doc(d=(5, 1)))['h'])['size'] == pytest.approx(1.5 * PI)
        assert check_results(self.doc(d=(5, 1)))['op_m:equal'] == 'passed'
        assert check_results(self.doc(d=(5, 9)))['op_m:equal'] == 'passed'
        assert check_results(self.doc(d=(7, 9)))['op_m:equal'] == 'failed'

    def test_invalid_count(self):
        assert ev(self.doc(count=5))['m'] == undefined('mark', 'invalid_parameter')

    def test_upstream(self):
        b = B('eau').free('A', 4, 0).free('V', 0, 0).free('C', 0, 3).free('W', 1, 1)
        b.angle('g', 'A', 'V', 'C').angle('h', 'A', 'V', 'V').equal_angles('m', 'g', 'h')
        assert ev(b.doc)['m'] == undefined('mark', 'upstream', cause='h')


# ── mark.right_angle ─────────────────────────────────────────────────────

class TestRightMark:
    def doc(self, a=(4, 0), v=(0, 0), b=(0, 3)):
        return B('rm').free('A', *a).free('V', *v).free('C', *b).right_mark('m', 'A', 'V', 'C').doc

    def test_defined(self):
        assert ev(self.doc())['m'] == {'state': 'defined', 'type': 'mark',
                                       'value': {'kind': 'right_angle', 'count': 1}}

    def test_orientation_does_not_matter(self):
        assert check_results(self.doc(a=(0, 3), b=(4, 0))) == {'op_m:right': 'passed'}

    def test_check(self):
        assert check_results(self.doc(a=(2, 1), v=(1, 1), b=(1, 7))) == {'op_m:right': 'passed'}
        assert check_results(self.doc(b=(1, 3))) == {'op_m:right': 'failed'}
        assert ev(self.doc(b=(1, 3)))['m']['state'] == 'defined'

    @pytest.mark.parametrize('a, b', [((0, 0), (0, 3)), ((4, 0), (0, 0))])
    def test_coincident_points(self, a, b):
        assert ev(self.doc(a=a, b=b))['m'] == undefined('mark', 'coincident_points')

    def test_upstream(self):
        b = B('rmu').free('P', 1, 1).free('R', 1, 1).line('l', 'P', 'R').intersect('X', 'l', 'l')
        b.free('A', 4, 0).free('V', 0, 0).right_mark('m', 'A', 'V', 'X')
        assert ev(b.doc)['m'] == undefined('mark', 'upstream', cause='l')

    def test_decisions(self):
        assert decisions_of(self.doc(), 'op_m') == ['coincident_points', 'coincident_points']


# ── circle.incircle ──────────────────────────────────────────────────────

class TestIncircle:
    def doc(self, a=(0, 0), b=(4, 0), c=(0, 3), touches=('T1', 'T2', 'T3')):
        bld = B('inc').free('A', *a).free('Q', *b).free('C', *c)
        return bld.incircle('k', 'A', 'Q', 'C', center='I', touches=touches).doc

    def test_right_triangle(self):
        out = ev(self.doc())
        assert value(out['k']) == {'c': [1.0, 1.0], 'r': 1.0}
        assert value(out['I']) == {'x': 1.0, 'y': 1.0}
        # touch_a on BC (opposite A), touch_b on CA, touch_c on AB
        assert close(tuple(value(out['T1']).values()), (1.6, 1.8))
        assert close(tuple(value(out['T2']).values()), (0.0, 1.0))
        assert close(tuple(value(out['T3']).values()), (1.0, 0.0))

    def test_equilateral(self):
        h = math.sqrt(3)
        out = ev(self.doc(a=(0, 0), b=(2, 0), c=(1, h)))
        k = value(out['k'])
        assert close(k['c'], (1.0, h / 3)) and math.isclose(k['r'], h / 3, rel_tol=1e-15)
        assert close(tuple(value(out['T3']).values()), (1.0, 0.0))

    def test_orientation_does_not_matter(self):
        cw = ev(self.doc(b=(0, 3), c=(4, 0)))
        assert close(value(cw['k'])['c'], (1.0, 1.0)) and value(cw['k'])['r'] == 1.0
        assert close(tuple(value(cw['T1']).values()), (1.6, 1.8))
        assert close(tuple(value(cw['T2']).values()), (1.0, 0.0))
        assert close(tuple(value(cw['T3']).values()), (0.0, 1.0))

    def test_unbound_outputs(self):
        out = ev(self.doc(touches=('T1',)))
        assert set(out) == {'A', 'Q', 'C', 'k', 'I', 'T1'}

    @pytest.mark.parametrize('a, b, c', [((0, 0), (2, 0), (5, 0)), ((0, 0), (0, 0), (0, 0)),
                                         ((1, 1), (1, 1), (3, 2)), ((0, 0), (4, 4), (2, 2))])
    def test_collinear(self, a, b, c):
        out = ev(self.doc(a=a, b=b, c=c))
        assert out['k'] == undefined('circle', 'collinear_points')
        assert out['I'] == out['T1'] == undefined('point', 'collinear_points')

    def test_upstream(self):
        b = B('incu').free('P', 1, 1).free('R', 1, 1).line('l', 'P', 'R').intersect('X', 'l', 'l')
        b.free('A', 4, 0).free('V', 0, 0).incircle('k', 'A', 'V', 'X', center='I')
        out = ev(b.doc)
        assert out['k'] == undefined('circle', 'upstream', cause='l')
        assert out['I'] == undefined('point', 'upstream', cause='l')

    def test_decisions(self):
        assert decisions_of(self.doc(), 'op_k') == ['collinear_points', 'collinear_points']

    def test_check_passes(self):
        assert check_results(self.doc(a=(-2, 1), b=(5, -3), c=(1, 6))) == {'op_k:tangent_sides': 'passed'}

    def test_inputs_move_the_circle(self):
        out = ev(self.doc(), inputs={'A': point_input(1, 1)})
        assert value(out['k'])['r'] < 1.0


# ── checks fail on forged results ────────────────────────────────────────

def _shift(p, dx=1e-3, dy=0.0):
    return {'x': p['x'] + dx, 'y': p['y'] + dy}


FORGED = [
    ('angle.by_points', 'sides', lambda r: dict(r, angle=dict(r['angle'], vertex=[r['angle']['vertex'][0] + 1e-3,
                                                                               r['angle']['vertex'][1]]))),
    ('angle.by_points', 'sides', lambda r: dict(r, angle=dict(r['angle'], a0=r['angle']['a0'] + 1e-3))),
    ('angle.by_points', 'sides', lambda r: dict(r, angle=dict(r['angle'], a1=r['angle']['a1'] - 1e-3))),
    ('circle.incircle', 'tangent_sides', lambda r: dict(r, circle=dict(r['circle'], r=r['circle']['r'] + 1e-3))),
    ('circle.incircle', 'tangent_sides', lambda r: dict(r, center=_shift(r['center']))),
    ('circle.incircle', 'tangent_sides', lambda r: dict(r, touch_a=_shift(r['touch_a'], 0.0, 1e-3))),
    ('circle.incircle', 'tangent_sides', lambda r: dict(r, touch_c=_shift(r['touch_c'], 1e-3))),
]


def _forged_doc(op):
    b = B('forge').free('A', 1, 1).free('Q', 5, 2).free('C', 2, 6)
    return {
        'angle.by_points': lambda: b.angle('X', 'Q', 'A', 'C'),
        'circle.incircle': lambda: b.incircle('X', 'A', 'Q', 'C', center='Y', touches=('T1', 'T2', 'T3')),
    }[op]().doc


@pytest.mark.parametrize('op, check_id, forge', FORGED, ids=[f'{o}:{c}:{i}' for i, (o, c, _) in enumerate(FORGED)])
def test_check_fails_on_a_forged_result(op, check_id, forge):
    evaluated = evaluate(_forged_doc(op))
    (name, args, result), = [v for v in evaluated.computed.values() if v[0] == op]
    fn = CHECKS[(op, check_id)]
    assert classify(fn(args, result, evaluated.tolerances), evaluated.tolerances) == 'passed'
    assert classify(fn(args, forge(result), evaluated.tolerances), evaluated.tolerances) == 'failed'


def test_angle_check_survives_the_wrap_boundary():
    """a0 = 2 pi - tiny and atan2 = -tiny are the same direction: the wrapped difference is tiny."""
    evaluated = evaluate(B('w').free('A', 2, -1e-12).free('V', 0, 0).free('C', 0, 3).angle('g', 'A', 'V', 'C').doc)
    (name, args, result), = [v for v in evaluated.computed.values() if v[0] == 'angle.by_points']
    assert result['angle']['a0'] > 6.28
    fn = CHECKS[('angle.by_points', 'sides')]
    assert classify(fn(args, result, evaluated.tolerances), evaluated.tolerances) == 'passed'


def test_mark_checks_ignore_the_mark_value():
    """The equality checks read the arguments only: forging the mark changes nothing."""
    b = B('mk').free('A', 0, 0).free('Q', 3, 0).free('C', 0, 3).segment('s', 'A', 'Q').segment('t', 'A', 'C')
    evaluated = evaluate(b.equal_segments('m', 's', 't').doc)
    (name, args, result), = [v for v in evaluated.computed.values() if v[0] == 'mark.equal_segments']
    fn = CHECKS[('mark.equal_segments', 'equal')]
    forged = {'mark': {'kind': 'equal_segments', 'count': 3}}
    assert fn(args, result, evaluated.tolerances) == fn(args, forged, evaluated.tolerances) == 0.0
