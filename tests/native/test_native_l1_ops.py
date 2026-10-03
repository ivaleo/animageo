"""Operations of registry 1.1: rays and the intersections with branch policies."""
import math

import pytest

from animageo import native
from tests.native.conftest import DocBuilder, point_input


def ev(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements


def xy(record):
    assert record['state'] == 'defined', record
    return record['value']['x'], record['value']['y']


def close(a, b, eps=1e-12):
    return all(abs(p - q) <= eps for p, q in zip(a, b))


# ---------------------------------------------------------------- rays

class TestRay:
    def doc(self, o=(1, 2), t=(4, 6)):
        return DocBuilder('ray', registry_version='1.1').free('O', *o).free('T', *t).ray('r', 'O', 'T').doc

    def test_value(self):
        rec = ev(self.doc())['r']
        assert rec == {'state': 'defined', 'type': 'ray',
                       'value': {'origin': [1.0, 2.0], 'dir': [0.6, 0.8]}}

    def test_coincident_points(self):
        rec = ev(self.doc(t=(1, 2)))['r']
        assert rec == {'state': 'undefined', 'type': 'ray', 'reason': 'coincident_points'}

    def test_checks(self):
        assert native.check(self.doc()).results == {'op_r:origin': 'passed', 'op_r:through': 'passed'}

    @pytest.mark.parametrize('line, expected', [
        (((1, -3), (1, 3)), ('defined', None)),
        (((-1, -3), (-1, 3)), ('undefined', 'outside_part')),
        (((0, -3), (0, 3)), ('defined', None)),          # exactly at the origin
    ])
    def test_ray_line_intersection(self, line, expected):
        b = DocBuilder('rl', registry_version='1.1').free('O', 0, 0).free('T', 2, 1).ray('r', 'O', 'T')
        b.free('P', *line[0]).free('Q', *line[1]).line('l', 'P', 'Q')
        b.intersect('X', 'r', 'l').intersect('Y', 'l', 'r')
        out = ev(b.doc)
        for name, slot in (('X', 'first'), ('Y', 'second')):
            assert out[name]['state'] == expected[0]
            if expected[1]:
                assert out[name]['reason'] == expected[1]
                assert out[name]['detail'] == {'slot': slot}
        if expected[0] == 'defined':
            assert close(xy(out['X']), (line[0][0], line[0][0] / 2))

    def test_ray_segment(self):
        b = DocBuilder('rs', registry_version='1.1').free('O', 0, 0).free('T', 1, 0).ray('r', 'O', 'T')
        b.free('A', 3, -1).free('B', 3, 1).segment('s', 'A', 'B').intersect('X', 'r', 's')
        assert xy(ev(b.doc)['X']) == (3.0, 0.0)
        out = ev(b.doc, {'A': point_input(3, 1), 'B': point_input(3, 2)})
        assert out['X']['detail'] == {'slot': 'second'}


# ---------------------------------------------------------------- line × circle

def line_circle_doc(p=(-6, 3), q=(6, 3), centre=(0, 0), through=(0, 5), kind='line'):
    b = DocBuilder('lc', registry_version='1.1')
    b.free('P', *p).free('Q', *q).free('C', *centre).free('R', *through)
    getattr(b, kind)('l', 'P', 'Q')
    b.circle('c', 'C', 'R').line_circle('X1', 'X2', 'l', 'c')
    return b.doc


class TestLineCircle:
    def test_order_along_the_line(self):
        out = ev(line_circle_doc())
        assert xy(out['X1']) == (-4.0, 3.0) and xy(out['X2']) == (4.0, 3.0)
        assert 'detail' not in out['X1']

    def test_reversed_line_swaps_slots(self):
        out = ev(line_circle_doc(p=(6, 3), q=(-6, 3)))
        assert xy(out['X1']) == (4.0, 3.0) and xy(out['X2']) == (-4.0, 3.0)

    def test_exact_tangency_fills_both_slots(self):
        out = ev(line_circle_doc(p=(-3, 2), q=(3, 2), through=(0, 2)))
        for name in ('X1', 'X2'):
            assert out[name] == {'state': 'defined', 'type': 'point', 'value': {'x': 0.0, 'y': 2.0},
                                 'detail': {'multiplicity': 2}}

    def test_no_intersection(self):
        out = ev(line_circle_doc(p=(-6, 7), q=(6, 7)))
        for name in ('X1', 'X2'):
            assert out[name] == {'state': 'undefined', 'type': 'point', 'reason': 'no_intersection'}

    def test_slot_two_stays_slot_two(self):
        out = ev(line_circle_doc(p=(0, 3), q=(10, 3), kind='segment'))
        assert out['X1'] == {'state': 'undefined', 'type': 'point', 'reason': 'outside_part',
                             'detail': {'slot': 'line'}}
        assert xy(out['X2']) == (4.0, 3.0)
        out = ev(line_circle_doc(p=(-10, 3), q=(0, 3), kind='segment'))
        assert xy(out['X1']) == (-4.0, 3.0)
        assert out['X2']['reason'] == 'outside_part'

    def test_segment_end_on_the_circle_is_inside(self):
        out = ev(line_circle_doc(p=(4, 3), q=(10, 3), kind='segment'))
        assert out['X1']['reason'] == 'outside_part'
        assert xy(out['X2']) == (4.0, 3.0)

    def test_zero_length_segment(self):
        out = ev(line_circle_doc(p=(1, 1), q=(1, 1), kind='segment'))
        assert out['X1']['reason'] == out['X2']['reason'] == 'zero_length'

    def test_ray_from_inside(self):
        out = ev(line_circle_doc(p=(0, 0), q=(1, 0), kind='ray'))
        assert out['X1']['reason'] == 'outside_part' and out['X1']['detail'] == {'slot': 'line'}
        assert xy(out['X2']) == (5.0, 0.0)

    def test_tangent_slot_outside_loses_multiplicity(self):
        out = ev(line_circle_doc(p=(1, 2), q=(3, 2), through=(0, 2), kind='segment'))
        for name in ('X1', 'X2'):
            assert out[name] == {'state': 'undefined', 'type': 'point', 'reason': 'outside_part',
                                 'detail': {'slot': 'line'}}

    def test_general_position_and_check(self):
        doc = line_circle_doc(p=(-5, -1), q=(4, 2), centre=(1, 0.5), through=(3, 4))
        out = ev(doc)
        x1, x2 = xy(out['X1']), xy(out['X2'])
        d = (4 - -5, 2 - -1)
        assert (x2[0] - x1[0]) * d[0] + (x2[1] - x1[1]) * d[1] > 0
        assert native.check(doc).results['op_X1_X2:on_both'] == 'passed'

    def test_upstream(self):
        out = ev(line_circle_doc(through=(0, 0)))
        assert out['X1'] == {'state': 'undefined', 'type': 'point', 'reason': 'upstream', 'cause': 'c'}


# ---------------------------------------------------------------- circle × circle

def circles_doc(c1=(0, 0), p1=(5, 0), c2=(8, 0), p2=(3, 0)):
    b = DocBuilder('cc', registry_version='1.1')
    b.free('C1', *c1).free('P1', *p1).free('C2', *c2).free('P2', *p2)
    b.circle('a', 'C1', 'P1').circle('b', 'C2', 'P2')
    b.circle_circle('X1', 'X2', 'a', 'b').circle_circle('Y1', 'Y2', 'b', 'a')
    return b.doc


class TestCircleCircle:
    def test_sides(self):
        out = ev(circles_doc())
        assert xy(out['X1']) == (4.0, 3.0) and xy(out['X2']) == (4.0, -3.0)
        assert xy(out['Y1']) == (4.0, -3.0) and xy(out['Y2']) == (4.0, 3.0)

    def test_external_tangency(self):
        out = ev(circles_doc(p1=(1, 0), c2=(3, 0), p2=(5, 0)))
        for name in ('X1', 'X2', 'Y1', 'Y2'):
            assert out[name]['value'] == {'x': 1.0, 'y': 0.0}
            assert out[name]['detail'] == {'multiplicity': 2}

    def test_internal_tangency(self):
        out = ev(circles_doc(p1=(3, 0), c2=(1, 0), p2=(3, 0)))
        for name in ('X1', 'X2', 'Y1', 'Y2'):
            assert out[name]['value'] == {'x': 3.0, 'y': 0.0}
            assert out[name]['detail'] == {'multiplicity': 2}

    @pytest.mark.parametrize('args', [
        dict(c2=(20, 0), p2=(21, 0)),                 # apart
        dict(p1=(5, 0), c2=(1, 0), p2=(2, 0)),        # nested
    ])
    def test_no_intersection(self, args):
        out = ev(circles_doc(**args))
        assert {out[n]['reason'] for n in ('X1', 'X2', 'Y1', 'Y2')} == {'no_intersection'}

    def test_concentric_and_coincident(self):
        out = ev(circles_doc(c2=(0, 0), p2=(2, 0)))
        assert {out[n]['reason'] for n in ('X1', 'X2')} == {'concentric'}
        out = ev(circles_doc(c2=(0, 0), p2=(0, 5)))
        assert {out[n]['reason'] for n in ('X1', 'X2')} == {'coincident'}

    def test_left_is_first_in_general_position(self):
        doc = circles_doc(c1=(-1, 2), p1=(2, 3), c2=(3, -1), p2=(1, 1))
        out = ev(doc)
        x1 = xy(out['X1'])
        cross = (3 - -1) * (x1[1] - 2) - (-1 - 2) * (x1[0] - -1)
        assert cross > 0
        assert native.check(doc).results['op_X1_X2:on_both'] == 'passed'


# ---------------------------------------------------------------- other than

class TestOtherThan:
    def test_line_circle_both_orders(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('A', -4, 3).free('B', 6, 3)
        b.circle('c', 'C', 'A').line('l', 'A', 'B')
        b.other_than('X', 'l', 'c', 'A').other_than('Y', 'c', 'l', 'A')
        out = ev(b.doc)
        assert xy(out['X']) == (4.0, 3.0) and xy(out['Y']) == (4.0, 3.0)
        assert 'detail' not in out['X']
        assert native.check(b.doc).results == {'op_X:on_both': 'passed', 'op_Y:on_both': 'passed',
                                               'op_c:through_on_circle': 'passed',
                                               'op_l:through_a': 'passed', 'op_l:through_b': 'passed'}

    def test_known_second_gives_first(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('A', 4, 3).free('B', -6, 3).free('R', 0, 5)
        b.circle('c', 'C', 'R').line('l', 'B', 'A').other_than('X', 'l', 'c', 'A')
        assert xy(ev(b.doc)['X']) == (-4.0, 3.0)

    def test_tangency_at_known_gives_known(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('K', 0, 2).free('Q', 3, 2)
        b.circle('c', 'C', 'K').line('l', 'K', 'Q').other_than('X', 'l', 'c', 'K')
        assert ev(b.doc)['X'] == {'state': 'defined', 'type': 'point', 'value': {'x': 0.0, 'y': 2.0}}

    def test_second_point_of_two_circles(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('A', 4, 3).free('C1', 0, 0).free('C2', 8, 0)
        b.circle('a', 'C1', 'A').circle('b', 'C2', 'A')
        b.other_than('X', 'a', 'b', 'A').other_than('Y', 'b', 'a', 'A')
        out = ev(b.doc)
        assert xy(out['X']) == (4.0, -3.0) and xy(out['Y']) == (4.0, -3.0)

    def test_branch_absent(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('A', -4, 3).free('B', 6, 3).free('K', 1, 1)
        b.circle('c', 'C', 'A').line('l', 'A', 'B').other_than('X', 'l', 'c', 'K')
        b.free('D', 0, -1).free('E', 0, 1).line('m', 'D', 'E')
        b.other_than('Y', 'l', 'm', 'K').other_than('Z', 'l', 'm', 'A')
        out = ev(b.doc)
        assert out['X']['reason'] == 'branch_absent'
        assert out['Y']['reason'] == 'branch_absent'
        out = ev(b.doc, {'K': point_input(0, 3)})           # the line crossing itself
        assert out['Y']['reason'] == 'branch_absent'

    def test_reason_of_the_pair(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('R', 0, 5).free('A', -4, 7).free('B', 6, 7)
        b.circle('c', 'C', 'R').line('l', 'A', 'B').other_than('X', 'c', 'l', 'A')
        assert ev(b.doc)['X'] == {'state': 'undefined', 'type': 'point', 'reason': 'no_intersection'}

    def test_other_point_outside_the_segment(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('C', 0, 0).free('A', -4, 3).free('B', 1, 3)
        b.circle('c', 'C', 'A').segment('s', 'A', 'B')
        b.other_than('X', 's', 'c', 'A').other_than('Y', 'c', 's', 'A')
        out = ev(b.doc)
        assert out['X'] == {'state': 'undefined', 'type': 'point', 'reason': 'outside_part',
                            'detail': {'slot': 'first'}}
        assert out['Y']['detail'] == {'slot': 'second'}

    def test_polygon_is_not_a_curve(self):
        b = DocBuilder('ot', registry_version='1.1')
        b.free('A', 0, 0).free('B', 4, 0).free('C', 0, 4).polygon('t', 'A', 'B', 'C')
        b.line('l', 'A', 'B').other_than('X', 't', 'l', 'A')
        assert ev(b.doc)['X'] == {'state': 'error', 'type': 'point', 'reason': 'type_mismatch'}


def test_line_line_formula_order_for_segments_is_unchanged():
    """Rays reuse the carrier; a segment input keeps the L0 decisions in order."""
    b = DocBuilder('ll').free('A', 0, 0).free('B', 4, 0).free('C', 2, -1).free('D', 2, 1)
    b.segment('s', 'A', 'B').segment('t', 'C', 'D').intersect('X', 's', 't')
    decisions = []
    from animageo.native.kernel.evaluate import evaluate
    evaluate(b.doc, _decisions=decisions)
    names = [d[1] for d in decisions if d[0] == 'op_X']
    assert names == ['zero_length', 'zero_length', 'parallel', 'outside_part', 'outside_part',
                     'outside_part', 'outside_part']
    assert math.isclose(evaluate(b.doc).elements['X']['value']['x'], 2.0)
