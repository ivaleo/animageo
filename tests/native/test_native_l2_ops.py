"""Operations of registry 1.2 (L2 stage 1): formulas, degeneracies, checks."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import CHECKS, classify
from animageo.native.kernel.evaluate import evaluate
from tests.native.conftest import DocBuilder, number_input, point_input


def ev(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements


def xy(record):
    assert record['state'] == 'defined', record
    return record['value']['x'], record['value']['y']


def close(a, b, eps=1e-12):
    return len(a) == len(b) and all(abs(p - q) <= eps for p, q in zip(a, b))


def B(name='l2'):
    return DocBuilder(name, registry_version='1.2')


def undefined(type_, reason, **extra):
    return dict({'state': 'undefined', 'type': type_, 'reason': reason}, **extra)


def line_through(rec, x, y, eps=1e-12):
    """The line record passes through (x, y)."""
    (px, py), (dx, dy) = rec['value']['p'], rec['value']['dir']
    return abs((x - px) * dy - (y - py) * dx) <= eps


def all_checks_pass(doc, inputs=None):
    report = native.check(doc, inputs=inputs)
    assert report.results and all(v == 'passed' for v in report.results.values()), report.results
    return report


# ── point.projection ─────────────────────────────────────────────────────

class TestProjection:
    def doc(self, base='line', p=(1, 3), a=(0, 0), b=(4, 0), strict=None):
        bld = B('proj').free('P', *p).free('A', *a).free('Q', *b)
        getattr(bld, {'line': 'line', 'segment': 'segment', 'ray': 'ray'}[base])('m', 'A', 'Q')
        return bld.projection('H', 'P', 'm', strict=strict).doc

    def test_on_a_line(self):
        assert ev(self.doc())['H'] == {'state': 'defined', 'type': 'point', 'value': {'x': 1.0, 'y': 0.0}}

    def test_slanted(self):
        assert close(xy(ev(self.doc(p=(5, 0), b=(3, 4)))['H']), (1.8, 2.4))

    def test_segment_without_flag_uses_the_carrier(self):
        assert xy(ev(self.doc('segment', p=(6, 3)))['H']) == (6.0, 0.0)
        assert xy(ev(self.doc('segment', p=(6, 3), strict=0))['H']) == (6.0, 0.0)

    @pytest.mark.parametrize('p, state', [((6, 3), 'undefined'), ((-1, 3), 'undefined'),
                                          ((4, 3), 'defined'), ((0, -2), 'defined'), ((2, 1), 'defined')])
    def test_strict_segment(self, p, state):
        rec = ev(self.doc('segment', p=p, strict=1))['H']
        assert rec['state'] == state
        if state == 'undefined':
            assert rec == undefined('point', 'outside_part', detail={'slot': 'base'})

    def test_strict_ray(self):
        assert ev(self.doc('ray', p=(-2, 1), strict=1))['H'] == undefined(
            'point', 'outside_part', detail={'slot': 'base'})
        assert xy(ev(self.doc('ray', p=(-2, 1)))['H']) == (-2.0, 0.0)
        assert xy(ev(self.doc('ray', p=(9, 1), strict=1))['H']) == (9.0, 0.0)

    def test_strict_line_has_no_filter(self):
        assert xy(ev(self.doc('line', p=(-7, 1), strict=1))['H']) == (-7.0, 0.0)

    def test_zero_segment(self):
        assert ev(self.doc('segment', b=(0, 0)))['H'] == undefined('point', 'zero_length')

    def test_invalid_strict_comes_first(self):
        assert ev(self.doc('segment', b=(0, 0), strict=2))['H'] == undefined('point', 'invalid_parameter')
        assert ev(self.doc(strict=0.5))['H'] == undefined('point', 'invalid_parameter')

    def test_checks(self):
        all_checks_pass(self.doc(p=(5, 0), b=(3, 4)))
        all_checks_pass(self.doc('segment', p=(6, 3)))


# ── line.parallel, line.perpendicular ────────────────────────────────────

class TestParallelPerpendicular:
    def doc(self, kind='parallel', base='line', p=(1, 2), a=(0, 0), b=(3, 4)):
        bld = B('pp').free('P', *p).free('A', *a).free('Q', *b)
        getattr(bld, base)('m', 'A', 'Q')
        return getattr(bld, kind)('l', 'P', 'm').doc

    def test_parallel_value(self):
        rec = ev(self.doc())['l']
        assert rec['type'] == 'line' and rec['state'] == 'defined'
        dx, dy = 0.6, 0.8
        k = 1 * dx + 2 * dy
        assert rec['value'] == {'p': [1 - k * dx, 2 - k * dy], 'dir': [dx, dy]}

    def test_perpendicular_value(self):
        rec = ev(self.doc('perpendicular'))['l']
        dx, dy = -0.8, 0.6
        k = 1 * dx + 2 * dy
        assert rec['value'] == {'p': [1 - k * dx, 2 - k * dy], 'dir': [dx, dy]}

    def test_axis_aligned(self):
        assert ev(self.doc(p=(3, 5), b=(2, 0)))['l']['value'] == {'p': [0.0, 5.0], 'dir': [1.0, 0.0]}
        rec = ev(self.doc('perpendicular', p=(3, 5), b=(2, 0)))['l']
        assert rec['value'] == {'p': [3.0, 0.0], 'dir': [0.0, 1.0]}

    @pytest.mark.parametrize('kind', ['parallel', 'perpendicular'])
    def test_point_on_the_base(self, kind):
        rec = ev(self.doc(kind, p=(3, 4)))['l']
        assert line_through(rec, 3, 4)

    @pytest.mark.parametrize('kind', ['parallel', 'perpendicular'])
    def test_ray_and_segment_bases(self, kind):
        for base in ('ray', 'segment'):
            rec = ev(self.doc(kind, base=base))['l']
            assert rec['state'] == 'defined'
            assert line_through(rec, 1, 2)

    @pytest.mark.parametrize('kind', ['parallel', 'perpendicular'])
    def test_zero_segment(self, kind):
        assert ev(self.doc(kind, base='segment', b=(0, 0)))['l'] == undefined('line', 'zero_length')

    @pytest.mark.parametrize('kind', ['parallel', 'perpendicular'])
    def test_checks(self, kind):
        all_checks_pass(self.doc(kind))


# ── line.perpendicular_bisector ──────────────────────────────────────────

class TestPerpendicularBisector:
    def doc(self, a=(0, 0), b=(4, 2)):
        return B('pb').free('A', *a).free('Q', *b).perp_bisector('l', 'A', 'Q').doc

    def test_value(self):
        rec = ev(self.doc(a=(1, 1), b=(5, 1)))['l']
        assert rec['value'] == {'p': [3.0, 0.0], 'dir': [0.0, 1.0]}

    def test_orientation_is_ab_rotated(self):
        rec = ev(self.doc(a=(5, 1), b=(1, 1)))['l']
        assert rec['value']['dir'] == [-0.0, -1.0]

    def test_general(self):
        rec = ev(self.doc())['l']
        assert line_through(rec, 2, 1)
        dx, dy = rec['value']['dir']
        assert abs(dx * 4 + dy * 2) <= 1e-15

    def test_coincident(self):
        assert ev(self.doc(b=(0, 0)))['l'] == undefined('line', 'coincident_points')

    def test_checks(self):
        all_checks_pass(self.doc())


# ── line.angle_bisector ──────────────────────────────────────────────────

class TestAngleBisector:
    def doc(self, a=(4, 0), v=(0, 0), b=(0, 3)):
        return B('ab').free('A', *a).free('V', *v).free('C', *b).angle_bisector('l', 'A', 'V', 'C').doc

    def test_right_angle(self):
        rec = ev(self.doc())['l']
        h = math.sqrt(0.5)
        assert close(rec['value']['dir'], (h, h), 1e-15)
        assert line_through(rec, 0, 0)

    def test_obtuse_into_the_angle(self):
        rec = ev(self.doc(a=(1, 0), b=(-1, math.sqrt(3))))['l']   # 120°
        assert close(rec['value']['dir'], (0.5, math.sqrt(3) / 2), 1e-15)

    def test_clockwise_order_still_into_the_angle(self):
        rec = ev(self.doc(a=(0, 3), b=(4, 0)))['l']
        h = math.sqrt(0.5)
        assert close(rec['value']['dir'], (h, h), 1e-15)
        rec = ev(self.doc(a=(-1, math.sqrt(3)), b=(1, 0)))['l']
        assert close(rec['value']['dir'], (0.5, math.sqrt(3) / 2), 1e-15)

    def test_straight_angle(self):
        rec = ev(self.doc(a=(2, 0), b=(-3, 0)))['l']
        assert rec['value'] == {'p': [0.0, 0.0], 'dir': [-0.0, 1.0]}
        rec = ev(self.doc(a=(-3, 0), b=(2, 0)))['l']
        assert rec['value']['dir'] == [0.0, -1.0]

    def test_vertex_elsewhere(self):
        rec = ev(self.doc(a=(5, 1), v=(1, 1), b=(1, 4)))['l']
        assert line_through(rec, 1, 1) and line_through(rec, 2, 2)

    @pytest.mark.parametrize('a, b', [((0, 0), (0, 3)), ((4, 0), (0, 0))])
    def test_coincident(self, a, b):
        assert ev(self.doc(a=a, b=b))['l'] == undefined('line', 'coincident_points')

    def test_checks(self):
        all_checks_pass(self.doc())
        all_checks_pass(self.doc(a=(1, 0), b=(-1, math.sqrt(3))))
        all_checks_pass(self.doc(a=(2, 0), b=(-3, 0)))


# ── vector.by_points ─────────────────────────────────────────────────────

class TestVector:
    def test_value(self):
        doc = B('v').free('A', 1, 2).free('Q', 4, 6).vector('v', 'A', 'Q').doc
        assert ev(doc)['v'] == {'state': 'defined', 'type': 'vector',
                                'value': {'a': [1.0, 2.0], 'b': [4.0, 6.0], 'length': 5.0}}
        all_checks_pass(doc)

    def test_zero_vector_is_defined(self):
        doc = B('v').free('A', 1, 2).free('Q', 1, 2).vector('v', 'A', 'Q').doc
        assert ev(doc)['v']['value'] == {'a': [1.0, 2.0], 'b': [1.0, 2.0], 'length': 0.0}


# ── circle.center_radius ─────────────────────────────────────────────────

class TestCenterRadius:
    def test_literal(self):
        doc = B('cr').free('O', 1, -1).circle_radius('c', 'O', 2.5).doc
        assert ev(doc)['c']['value'] == {'c': [1.0, -1.0], 'r': 2.5}
        all_checks_pass(doc)

    def test_number(self):
        doc = B('cr').free('O', 1, -1).number('r', 4).circle_radius('c', 'O', 'r').doc
        assert ev(doc)['c']['value'] == {'c': [1.0, -1.0], 'r': 4.0}
        assert ev(doc, {'r': number_input(1.5)})['c']['value']['r'] == 1.5
        all_checks_pass(doc)

    @pytest.mark.parametrize('r', [0, -2])
    def test_nonpositive(self, r):
        doc = B('cr').free('O', 1, -1).circle_radius('c', 'O', r).doc
        assert ev(doc)['c'] == undefined('circle', 'nonpositive_radius')


# ── circle.three_points ──────────────────────────────────────────────────

class TestThreePoints:
    def doc(self, a=(0, 0), b=(4, 0), c=(0, 3)):
        return B('c3').free('A', *a).free('Q', *b).free('C', *c).circle3('w', 'A', 'Q', 'C', center='O').doc

    def test_right_triangle(self):
        out = ev(self.doc())
        assert out['w']['value'] == {'c': [2.0, 1.5], 'r': 2.5}
        assert out['O'] == {'state': 'defined', 'type': 'point', 'value': {'x': 2.0, 'y': 1.5}}

    def test_general(self):
        a, b, c = (1, 1), (5, 2), (2, 6)
        out = ev(self.doc(a, b, c))
        (cx, cy), r = out['w']['value']['c'], out['w']['value']['r']
        for x, y in (a, b, c):
            assert abs(math.hypot(x - cx, y - cy) - r) <= 1e-12
        assert xy(out['O']) == (cx, cy)
        all_checks_pass(self.doc(a, b, c))

    def test_order_does_not_move_the_circle(self):
        v1 = ev(self.doc((1, 1), (5, 2), (2, 6)))['w']['value']
        v2 = ev(self.doc((5, 2), (2, 6), (1, 1)))['w']['value']
        assert close(v1['c'], v2['c']) and abs(v1['r'] - v2['r']) <= 1e-12

    @pytest.mark.parametrize('pts', [((0, 0), (1, 1), (3, 3)), ((0, 0), (2, 0), (2, 0)),
                                     ((1, 1), (1, 1), (1, 1))])
    def test_collinear(self, pts):
        out = ev(self.doc(*pts))
        assert out['w'] == undefined('circle', 'collinear_points')
        assert out['O'] == undefined('point', 'collinear_points')


# ── number.free ──────────────────────────────────────────────────────────

class TestNumberFree:
    def value(self, v, **params):
        return ev(B('n').number('r', v, **params).doc)['r']

    def test_plain(self):
        assert self.value(2.5) == {'state': 'defined', 'type': 'number', 'value': {'value': 2.5, 'unit': 'scalar'}}
        assert self.value(-1e6)['value']['value'] == -1e6

    def test_clamp(self):
        assert self.value(7, min=0, max=5)['value']['value'] == 5.0
        assert self.value(-1, min=0, max=5)['value']['value'] == 0.0
        assert self.value(3, min=0, max=5, step=0.5)['value']['value'] == 3.0
        assert self.value(3.3, min=0, max=5, step=0.5)['value']['value'] == 3.3     # not snapped
        assert self.value(-9, max=5)['value']['value'] == -9.0
        assert self.value(-9, min=-2)['value']['value'] == -2.0
        assert self.value(4, min=4, max=4)['value']['value'] == 4.0

    @pytest.mark.parametrize('params', [{'min': 3, 'max': 1}, {'step': 0}, {'step': -1}])
    def test_invalid(self, params):
        assert self.value(2, **params) == undefined('number', 'invalid_parameter')

    def test_no_checks(self):
        assert native.check(B('n').number('r', 2).doc).results == {}


# ── checks catch a forged result ─────────────────────────────────────────

FORGED = [
    ('point.projection', 'on_carrier', lambda r: dict(r, foot={'x': r['foot']['x'], 'y': r['foot']['y'] + 1e-3})),
    ('point.projection', 'perpendicular', lambda r: dict(r, foot={'x': r['foot']['x'] + 1e-3, 'y': r['foot']['y']})),
    ('line.parallel', 'parallel', lambda r: dict(r, line={'p': r['line']['p'], 'dir': [0.0, 1.0]})),
    ('line.perpendicular', 'through_point', lambda r: dict(r, line={'p': [9.0, 9.0], 'dir': r['line']['dir']})),
    ('line.perpendicular_bisector', 'perpendicular', lambda r: dict(r, line={'p': r['line']['p'], 'dir': [1.0, 0.0]})),
    ('line.angle_bisector', 'equal_angles', lambda r: dict(r, line={'p': [0.0, 0.0], 'dir': [1.0, 0.0]})),
    ('vector.by_points', 'ends', lambda r: dict(r, vector=dict(r['vector'], b=[0.0, 0.0]))),
    ('circle.center_radius', 'matches', lambda r: dict(r, circle=dict(r['circle'], r=r['circle']['r'] + 1e-3))),
    ('circle.three_points', 'through_all', lambda r: dict(r, center={'x': 0.0, 'y': 0.0})),
]


def _forged_doc(op):
    b = B('forge').free('A', 1, 1).free('Q', 5, 2).free('C', 2, 6).free('P', 3, -1)
    b.line('m', 'A', 'Q')
    return {
        'point.projection': lambda: b.projection('X', 'P', 'm'),
        'line.parallel': lambda: b.parallel('X', 'P', 'm'),
        'line.perpendicular': lambda: b.perpendicular('X', 'P', 'm'),
        'line.perpendicular_bisector': lambda: b.perp_bisector('X', 'A', 'Q'),
        'line.angle_bisector': lambda: b.angle_bisector('X', 'Q', 'A', 'C'),
        'vector.by_points': lambda: b.vector('X', 'A', 'Q'),
        'circle.center_radius': lambda: b.circle_radius('X', 'A', 3),
        'circle.three_points': lambda: b.circle3('X', 'A', 'Q', 'C', center='Y'),
    }[op]().doc


@pytest.mark.parametrize('op, check_id, forge', FORGED, ids=[f'{o}:{c}' for o, c, _ in FORGED])
def test_check_fails_on_a_forged_result(op, check_id, forge):
    evaluated = evaluate(_forged_doc(op))
    (name, args, result), = [v for v in evaluated.computed.values() if v[0] == op]
    fn = CHECKS[(op, check_id)]
    assert classify(fn(args, result, evaluated.tolerances), evaluated.tolerances) == 'passed'
    assert classify(fn(args, forge(result), evaluated.tolerances), evaluated.tolerances) == 'failed'
