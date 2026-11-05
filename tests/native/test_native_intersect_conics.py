"""Common points of two conics and of a graph and a conic (registry 1.8;
docs/native/ops/intersect.conic_conic.md, intersect.function_conic.md)."""
import math

import pytest

from animageo import native
from animageo.native.kernel.checks import run_checks
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, num, ref

SLOTS = ('first', 'second', 'third', 'fourth')
X = {'var': 'x'}


def n(v):
    return {'num': v}


def op(name, *args):
    return {'op': name, 'args': list(args)}


class Doc(DocBuilder):
    def __init__(self, bounds=(-10, -10, 10, 10), shift=(0.0, 0.0)):
        super().__init__('meet', bounds, registry_version='1.8')
        self.shift = shift

    def at(self, el_id, x, y):
        return self.free(el_id, x + self.shift[0], y + self.shift[1])

    def five(self, el_id, *points):
        names = []
        for k, (x, y) in enumerate(points):
            name = f'{el_id}_{k}'
            self.at(name, x, y)
            names.append(name)
        return self.op('op_' + el_id, 'conic.five_points', {k: ref(v) for k, v in zip('abcde', names)},
                       [('conic', el_id, 'conic')])

    def wide(self, el_id, cx=0.0, cy=0.0):
        """x²/16 + y²/4 = 1 about (cx, cy)."""
        return self.five(el_id, *((cx + x, cy + y) for x, y in ((4, 0), (-4, 0), (0, 2), (0, -2), (2.4, 1.6))))

    def tall(self, el_id, cx=0.0, cy=0.0):
        """x²/4 + y²/16 = 1 about (cx, cy)."""
        return self.five(el_id, *((cx + x, cy + y) for x, y in ((2, 0), (-2, 0), (0, 4), (0, -4), (1.6, 2.4))))

    def round_(self, el_id, cx, cy, r):
        self.at(el_id + '_c', cx, cy).at(el_id + '_p', cx + r, cy)
        return self.circle(el_id, el_id + '_c', el_id + '_p')

    def hyperbola(self, el_id):
        """x²/9 − y²/16 = 1: foci (∓5, 0) through (3, 0)."""
        self.at(el_id + '_f1', -5, 0).at(el_id + '_f2', 5, 0).at(el_id + '_p', 3, 0)
        return self.op('op_' + el_id, 'conic.hyperbola_foci_point',
                       {'f1': ref(el_id + '_f1'), 'f2': ref(el_id + '_f2'), 'through': ref(el_id + '_p')},
                       [('conic', el_id, 'conic')])

    def parabola(self, el_id, focus=(0, 1), d1=(-1, -1), d2=(1, -1)):
        """y = x²/4 by default: focus (0, 1), directrix y = −1."""
        self.at(el_id + '_f', *focus).at(el_id + '_d1', *d1).at(el_id + '_d2', *d2)
        self.line(el_id + '_d', el_id + '_d1', el_id + '_d2')
        return self.op('op_' + el_id, 'conic.parabola_focus_directrix',
                       {'focus': ref(el_id + '_f'), 'directrix': ref(el_id + '_d')}, [('conic', el_id, 'conic')])

    def ellipse(self, el_id, f1, f2, through):
        self.at(el_id + '_f1', *f1).at(el_id + '_f2', *f2).at(el_id + '_p', *through)
        return self.op('op_' + el_id, 'conic.ellipse_foci_point',
                       {'f1': ref(el_id + '_f1'), 'f2': ref(el_id + '_f2'), 'through': ref(el_id + '_p')},
                       [('conic', el_id, 'conic')])

    def meet(self, prefix, first, second, name='intersect.conic_conic'):
        return self.op('op_' + prefix, name, {'first': ref(first), 'second': ref(second)},
                       [(slot, f'{prefix}{k}', 'point') for k, slot in enumerate(SLOTS, 1)])

    def graph(self, el_id, ast, lo=None, hi=None):
        args = {'expr': {'kind': 'expr', 'ast': ast}, 'refs': {'kind': 'list', 'items': []}}
        if lo is not None:
            args['min'] = num(lo)
        if hi is not None:
            args['max'] = num(hi)
        return self.op('op_' + el_id, 'function.expr', args, [('function', el_id, 'function')])

    def graph_conic(self, prefix, fn, conic, count=4):
        args = {'function': ref(fn), 'conic': ref(conic)}
        if count != 1:
            args['count'] = num(count)
        return self.op('op_' + prefix, 'intersect.function_conic', args,
                       [(f'point.{k}', f'{prefix}{k}', 'point') for k in range(1, count + 1)])


def evaluate(doc):
    return native.evaluate(doc.doc)


def points(e, prefix, count=4):
    out = []
    for k in range(1, count + 1):
        record = e.elements[f'{prefix}{k}']
        if record['state'] == 'defined':
            out.append((record['value']['x'], record['value']['y']))
        else:
            out.append(record['reason'])
    return out


def close(got, want, tol=1e-9):
    assert len(got) == len(want)
    for g, w in zip(got, want):
        if isinstance(w, str):
            assert g == w
        else:
            assert not isinstance(g, str), (got, want)
            assert g[0] == pytest.approx(w[0], abs=tol) and g[1] == pytest.approx(w[1], abs=tol), (got, want)


def checks_pass(doc):
    report = run_checks(evaluate(doc))
    assert report.ok, report.errors
    return report


# ── the registry ──────────────────────────────────────────────────────────

def test_records():
    reg = registry()
    record = reg.get('intersect.conic_conic')
    assert record['since'] == '1.8' and record['status'] == 'beta'
    assert [i['type'] for i in reg.get('intersect.conic_conic')['inputs']] == ['conical', 'conical']
    assert reg.get('intersect.conic_conic')['branch']['policy'] == 'first_curve_order'
    assert reg.families['conical'] == ['conic', 'circle', 'arc']


def test_a_document_of_registry_1_7_cannot_use_them():
    d = Doc().wide('E').tall('F').meet('P', 'E', 'F')
    d.doc['operationRegistryVersion'] = '1.7'
    assert [i.code for i in native.validate(d.doc)] == ['needs_newer_registry']
    assert native.min_registry_version(d.doc) == '1.8'


# ── conic and conic ───────────────────────────────────────────────────────

R5 = 4 / math.sqrt(5)


def test_two_ellipses_meet_in_four_points_counterclockwise_from_the_axis():
    d = Doc().wide('E').tall('F').meet('P', 'E', 'F')
    close(points(evaluate(d), 'P'), [(R5, R5), (-R5, R5), (-R5, -R5), (R5, -R5)])
    checks_pass(d)


def test_a_circle_and_an_ellipse_take_the_axis_of_the_ellipse_when_concentric():
    d = Doc().round_('c', 0, 0, 3).wide('E').meet('P', 'c', 'E')
    x, y = math.sqrt(20 / 3), math.sqrt(7 / 3)
    close(points(evaluate(d), 'P'), [(x, y), (-x, y), (-x, -y), (x, -y)])
    checks_pass(d)


def test_the_order_starts_at_the_direction_to_the_second_centre():
    # the circle about (0, 0.5): the reference direction from E's centre is +y
    d = Doc().wide('E').round_('c', 0, 0.5, 3.0).meet('P', 'E', 'c')
    got = points(evaluate(d), 'P')
    assert not any(isinstance(p, str) for p in got)
    angles = [math.atan2(p[1], p[0]) for p in got]
    turns = [((a - math.pi / 2) % (2 * math.pi)) for a in angles]
    assert turns == sorted(turns)
    checks_pass(d)


def test_tangency_fills_two_slots_with_multiplicity_two():
    d = Doc().round_('c', 0, 0, 2).wide('E').meet('P', 'c', 'E')
    e = evaluate(d)
    close(points(e, 'P'), [(0, 2), (0, 2), (0, -2), (0, -2)])
    for k in range(1, 5):
        assert e.elements[f'P{k}']['detail'] == {'multiplicity': 2}
    checks_pass(d)


def test_close_roots_stay_apart():
    eps = 1e-5
    d = Doc().round_('c', 0, 0, 2 + eps).wide('E').meet('P', 'c', 'E')
    got = points(evaluate(d), 'P')
    assert not any(isinstance(p, str) for p in got)
    assert got[0][0] > 0 > got[1][0] and got[2][0] < 0 < got[3][0]
    assert abs(got[0][0] - got[1][0]) > 1e-3
    checks_pass(d)


def test_no_common_point_and_recovery():
    d = Doc().round_('c', 0, 0, 1).wide('E').meet('P', 'c', 'E')
    assert points(evaluate(d), 'P') == ['no_intersection'] * 4
    d.doc['inputs']['c_p'] = {'kind': 'point', 'value': [3.0, 0.0]}
    assert not any(isinstance(p, str) for p in points(evaluate(d), 'P'))


def test_coincident_conics():
    d = Doc().wide('E').five('G', (4, 0), (-4, 0), (0, 2), (0, -2), (-2.4, -1.6)).meet('P', 'E', 'G')
    assert points(evaluate(d), 'P') == ['coincident'] * 4


def test_two_common_points_leave_branch_absent():
    d = Doc().wide('E').round_('c', 4, 0, 1).meet('P', 'E', 'c')
    got = points(evaluate(d), 'P')
    assert got[2:] == ['branch_absent', 'branch_absent']
    assert all(not isinstance(p, str) for p in got[:2])
    checks_pass(d)


def test_two_circles_match_circle_circle_slot_for_slot():
    d = Doc().round_('c', 0, 0, 3).round_('k', 2, 1, 2.5).meet('P', 'c', 'k')
    d.circle_circle('Q1', 'Q2', 'c', 'k')
    e = evaluate(d)
    for k in (1, 2):
        p, q = e.elements[f'P{k}'], e.elements[f'Q{k}']
        assert (p['state'], p.get('value'), p.get('detail')) == (q['state'], q.get('value'), q.get('detail'))
    assert points(e, 'P')[2:] == ['branch_absent', 'branch_absent']
    far = Doc().round_('c', 0, 0, 1).round_('k', 5, 0, 1).meet('P', 'c', 'k')
    assert points(evaluate(far), 'P') == ['no_intersection'] * 4
    same = Doc().round_('c', 0, 0, 1).round_('k', 0, 0, 1).meet('P', 'c', 'k')
    assert points(evaluate(same), 'P') == ['coincident'] * 4


def test_a_hyperbola_first_orders_by_branch_then_along_it():
    d = Doc().hyperbola('H').round_('c', 0, 0, 5).meet('P', 'H', 'c')
    x, y = math.sqrt(369) / 5, 3.2
    close(points(evaluate(d), 'P'), [(-x, -y), (-x, y), (x, -y), (x, y)])
    checks_pass(d)


def test_a_parabola_first_orders_by_its_parameter():
    # vertex (0, 0), axis +y, n = (−1, 0): t grows to the left
    d = Doc().parabola('Q').round_('c', 0, 5, math.sqrt(20)).meet('P', 'Q', 'c')
    s = 2 * math.sqrt(5)
    close(points(evaluate(d), 'P'), [(s, 5), (2, 1), (-2, 1), (-s, 5)])
    checks_pass(d)


def test_a_parabola_and_a_hyperbola():
    # y² = 8(x − 2) (focus (4, 0), directrix x = 0) and x²/9 − y²/16 = 1: (4.5, ±√20)
    d = Doc().hyperbola('H').parabola('Q', (4, 0), (0, -1), (0, 1)).meet('P', 'Q', 'H').meet('R', 'H', 'Q')
    e = evaluate(d)
    s = math.sqrt(20)
    close(points(e, 'P'), [(4.5, -s), (4.5, s), 'branch_absent', 'branch_absent'])
    close(points(e, 'R'), [(4.5, -s), (4.5, s), 'branch_absent', 'branch_absent'])
    checks_pass(d)


def test_an_arc_filters_its_slots():
    d = Doc().round_('O', 0, 0, 3).wide('E')
    d.at('A', 3, 0).at('B', -3, 0)
    d.op('op_k', 'arc.center_two_points', {'center': ref('O_c'), 'a': ref('A'), 'b': ref('B')}, [('arc', 'k', 'arc')])
    d.meet('P', 'E', 'k').meet('R', 'k', 'E')
    e = evaluate(d)
    x, y = math.sqrt(20 / 3), math.sqrt(7 / 3)
    close(points(e, 'P'), [(x, y), (-x, y), 'outside_part', 'outside_part'])
    assert e.elements['P3']['detail'] == {'slot': 'second'}
    # the arc first: by the fraction of the arc
    close(points(e, 'R'), [(x, y), (-x, y), 'outside_part', 'outside_part'])
    assert e.elements['R3']['detail'] == {'slot': 'first'}
    checks_pass(d)


@pytest.mark.parametrize('shift', [(1e6, -1e6), (-3.5e5, 2.25e5)])
def test_large_coordinates(shift):
    sx, sy = shift
    bounds = (sx - 10, sy - 10, sx + 10, sy + 10)
    d = Doc(bounds, shift).ellipse('E', (-4, 0), (4, 0), (5, 0)).ellipse('F', (0, -4), (0, 4), (0, 5))
    d.meet('P', 'E', 'F')
    got = points(evaluate(d), 'P')
    r = math.sqrt(225 / 34)
    want = [(sx + r, sy + r), (sx - r, sy + r), (sx - r, sy - r), (sx + r, sy - r)]
    close(got, want, tol=1e-6)
    checks_pass(d)


def _turning(d, phi):
    """The ellipse about (1, 0) with a = 3, b = 1.5, its axis at the angle phi."""
    u = (math.cos(phi), math.sin(phi))
    e = math.sqrt(9 - 2.25)
    for name, k in (('F_f1', -e), ('F_f2', e), ('F_p', 3.0)):
        d.doc['inputs'][name] = {'kind': 'point', 'value': [1 + k * u[0], k * u[1]]}
    return points(evaluate(d), 'P')


def test_slots_follow_the_motion_and_swap_at_the_seam():
    """The circle about the origin first, an ellipse turning about (1, 0):
    the seam is the ray +x. The lower point crosses it near 40.2° (the
    ellipse passes through (3, 0) when sin²φ = 5/12) and the two slots swap;
    otherwise every slot keeps its point."""
    d = Doc().round_('c', 0, 0, 3).ellipse('F', (-1.6, 0), (3.6, 0), (4, 0)).meet('P', 'c', 'F')
    seam = math.degrees(math.asin(math.sqrt(5 / 12)))
    swaps = []
    before = _turning(d, math.radians(20))
    for k in range(1, 17):
        deg = 20 + 2.5 * k
        after = _turning(d, math.radians(deg))
        assert after[2:] == ['branch_absent', 'branch_absent']
        (p1, p2), (q1, q2) = before[:2], after[:2]
        straight = max(math.dist(p1, q1), math.dist(p2, q2))
        crossed = max(math.dist(p1, q2), math.dist(p2, q1))
        assert min(straight, crossed) < 0.3
        if crossed < straight:
            swaps.append(deg)
        before = after
    assert len(swaps) == 1 and swaps[0] - 2.5 < seam < swaps[0]
