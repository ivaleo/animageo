"""Op formulas and degeneracy decisions (plan §5, docs/native/ops)."""
import math

import pytest

from animageo import native
from animageo.native.kernel.numeric import scene_scale, tolerances
from animageo.native.kernel.ops import IMPLEMENTATIONS, OpContext
from animageo.native.kernel.values import Input, Undefined
from tests.native.conftest import DocBuilder

TOL = tolerances(20.0)


def P(x, y):
    return Input('point', {'x': float(x), 'y': float(y)})


def run(op, args, decisions=None, free_input=None):
    ctx = OpContext(TOL, input=free_input, operation_id='op', decisions=decisions)
    return IMPLEMENTATIONS[op](args, ctx)


def line_value(a, b):
    return run('line.by_points', {'a': P(*a), 'b': P(*b)})['line']


def segment_value(a, b):
    return run('segment.by_points', {'a': P(*a), 'b': P(*b)})['segment']


def approx(a, b, eps=1e-12):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


class TestPoint:
    def test_free(self):
        assert run('point.free', {}, free_input={'kind': 'point', 'value': [1, -2.5]}) == \
            {'point': {'x': 1.0, 'y': -2.5}}

    def test_midpoint(self):
        assert run('point.midpoint', {'a': P(1, 2), 'b': P(5, -3)}) == {'point': {'x': 3.0, 'y': -0.5}}
        assert run('point.midpoint', {'a': P(2, 2), 'b': P(2, 2)}) == {'point': {'x': 2.0, 'y': 2.0}}


class TestSegment:
    def test_value(self):
        assert segment_value((1, 1), (4, 5)) == {'a': [1.0, 1.0], 'b': [4.0, 5.0], 'length': 5.0}

    def test_zero_length_is_defined(self):
        assert segment_value((2, 2), (2, 2)) == {'a': [2.0, 2.0], 'b': [2.0, 2.0], 'length': 0.0}


class TestLine:
    def test_value_and_orientation(self):
        v = line_value((1, 1), (4, 5))
        assert approx(v['dir'], [0.6, 0.8])
        assert approx(v['p'], [0.16, -0.12])
        back = line_value((4, 5), (1, 1))
        assert approx(back['dir'], [-0.6, -0.8])
        assert approx(back['p'], v['p'])

    def test_projection_of_origin(self):
        v = line_value((2, -3), (2, 4))
        assert v == {'p': [2.0, 0.0], 'dir': [0.0, 1.0]}
        assert line_value((3, 1), (-5, 1)) == {'p': [0.0, 1.0], 'dir': [-1.0, 0.0]}

    def test_coincident_points(self):
        decisions = []
        out = run('line.by_points', {'a': P(2.5, -1), 'b': P(2.5, -1)}, decisions)
        assert out == {'line': Undefined('coincident_points')}
        assert decisions == [('op', 'coincident_points', 0.0, TOL.decide_length)]

    def test_within_tolerance_is_coincident(self):
        out = run('line.by_points', {'a': P(0, 0), 'b': P(TOL.decide_length / 2, 0)})
        assert out['line'] == Undefined('coincident_points')
        assert isinstance(run('line.by_points', {'a': P(0, 0), 'b': P(TOL.decide_length * 2, 0)})['line'], dict)


class TestCircle:
    def test_value(self):
        out = run('circle.center_point', {'center': P(0, 0), 'through': P(3, 4)})
        assert out == {'circle': {'c': [0.0, 0.0], 'r': 5.0}}

    def test_zero_radius(self):
        decisions = []
        out = run('circle.center_point', {'center': P(1, 1), 'through': P(1, 1)}, decisions)
        assert out == {'circle': Undefined('nonpositive_radius')}
        assert decisions[0][1:3] == ('nonpositive_radius', 0.0)


class TestIntersect:
    def L(self, a, b):
        return Input('line', line_value(a, b))

    def S(self, a, b):
        return Input('segment', segment_value(a, b))

    def test_lines(self):
        out = run('intersect.line_line', {'first': self.L((-5, 1), (5, 1)), 'second': self.L((2, -5), (2, 5))})
        assert approx([out['point']['x'], out['point']['y']], [2, 1])

    def test_parallel_and_coincident(self):
        decisions = []
        out = run('intersect.line_line', {'first': self.L((0, 0), (2, 0)), 'second': self.L((0, 1), (3, 1))},
                  decisions)
        assert out == {'point': Undefined('parallel')}
        assert [d[1] for d in decisions] == ['parallel', 'coincident']
        out = run('intersect.line_line', {'first': self.L((0, 0), (2, 0)), 'second': self.L((5, 0), (1, 0))})
        assert out == {'point': Undefined('coincident')}

    def test_parallel_threshold_is_dimensionless(self):
        # sin of the angle 5e-11 < 1e-10: parallel; the lines are 1 apart, not coincident
        tiny = 5e-11
        first = Input('line', {'p': [0.0, 0.0], 'dir': [1.0, 0.0]})
        second = Input('line', {'p': [0.0, 1.0], 'dir': [math.sqrt(1 - tiny * tiny), tiny]})
        assert run('intersect.line_line', {'first': first, 'second': second})['point'] == Undefined('parallel')

    def test_segments(self):
        out = run('intersect.line_line', {'first': self.S((-4, 0), (4, 0)), 'second': self.S((0, -3), (0, 3))})
        assert out == {'point': {'x': 0.0, 'y': 0.0}}

    def test_outside_part_reports_the_first_slot(self):
        out = run('intersect.line_line', {'first': self.S((-4, 0), (-1, 0)), 'second': self.S((2, 3), (2, 5))})
        assert out == {'point': Undefined('outside_part', {'slot': 'first'})}
        out = run('intersect.line_line', {'first': self.S((-4, 0), (4, 0)), 'second': self.S((1, 1), (1, 5))})
        assert out == {'point': Undefined('outside_part', {'slot': 'second'})}
        out = run('intersect.line_line', {'first': self.L((-4, 0), (-1, 0)), 'second': self.S((2, -3), (2, 3))})
        assert out == {'point': {'x': 2.0, 'y': 0.0}}

    def test_endpoint_is_inside(self):
        decisions = []
        out = run('intersect.line_line', {'first': self.S((0, 0), (4, 0)), 'second': self.S((4, -2), (4, 2))},
                  decisions)
        assert out == {'point': {'x': 4.0, 'y': 0.0}}
        outside = [d[2] for d in decisions if d[1] == 'outside_part']
        assert outside == [4.0, 0.0, 2.0, -2.0]

    def test_zero_length(self):
        out = run('intersect.line_line', {'first': self.S((0, 0), (4, 0)), 'second': self.S((1, 1), (1, 1))})
        assert out == {'point': Undefined('zero_length')}
        out = run('intersect.line_line', {'first': self.S((1, 1), (1, 1)), 'second': self.L((0, 0), (0, 1))})
        assert out == {'point': Undefined('zero_length')}


class TestPolygon:
    def test_triangle(self):
        out = run('polygon.by_points', {'vertices': [P(0, 0), P(4, 0), P(0, 3)]})
        assert out['polygon'] == {'vertices': [[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]], 'area': 6.0}
        assert out['side.1'] == {'a': [0.0, 0.0], 'b': [4.0, 0.0], 'length': 4.0}
        assert out['side.2'] == {'a': [4.0, 0.0], 'b': [0.0, 3.0], 'length': 5.0}
        assert out['side.3'] == {'a': [0.0, 3.0], 'b': [0.0, 0.0], 'length': 3.0}
        assert set(out) == {'polygon', 'side.1', 'side.2', 'side.3'}

    def test_unsigned_area(self):
        cw = run('polygon.by_points', {'vertices': [P(0, 0), P(0, 3), P(4, 0)]})
        assert cw['polygon']['area'] == 6.0

    def test_nonconvex_and_self_intersecting(self):
        dart = run('polygon.by_points', {'vertices': [P(0, 0), P(4, 2), P(0, 4), P(1, 2)]})
        assert dart['polygon']['area'] == 6.0
        bowtie = run('polygon.by_points', {'vertices': [P(0, 0), P(2, 2), P(2, 0), P(0, 2)]})
        assert bowtie['polygon']['area'] == 0.0


class TestScale:
    def test_bounds_and_points(self):
        assert scene_scale([-10, -10, 10, 10], []) == 20.0
        assert scene_scale([-8, -6, 8, 6], [(0, 0)]) == 16.0
        assert scene_scale(None, []) == 20.0
        assert scene_scale([-1, -1, 1, 1], [(1000, -2000), (3000, 500)]) == math.hypot(2000, 2500)

    def test_tolerances(self):
        tol = tolerances(20.0)
        assert tol.decide_length == 1e-10 * 20.0 and tol.decide_scalar == 1e-10
        assert tol.check_passed == 1e-9 * 20.0 and tol.check_failed == 1e-6 * 20.0
        assert tol.parity('length') == 1e-9 * 20.0
        assert tol.parity('area') == 1e-9 * 20.0 * 20.0
        assert tol.parity('scalar') == 1e-9

    def test_case_scale_uses_case_inputs(self):
        doc = DocBuilder('s').free('A', 0, 0).free('B', 1, 1).doc
        assert native.evaluate(doc).scale == 20.0
        far = {'A': {'kind': 'point', 'value': [0, 0]}, 'B': {'kind': 'point', 'value': [30, 40]}}
        assert native.evaluate(doc, inputs=far).scale == 50.0
