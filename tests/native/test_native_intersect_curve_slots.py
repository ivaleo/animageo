"""Conics and graphs in the ``curve`` slots of ``intersect.nearest`` and
``intersect.other_than`` (registry 1.8; docs/native/ops/intersect.nearest.md,
intersect.other_than.md)."""
import math

from animageo import native
from animageo.native.registry import registry
from tests.native.conftest import ref
from tests.native.test_native_intersect_conics import X, Doc, checks_pass, close, evaluate, n, op


def nearest(d, el_id, first, second, near):
    return d.op('op_' + el_id, 'intersect.nearest', {'first': ref(first), 'second': ref(second), 'near': ref(near)},
                [('point', el_id, 'point')])


def other(d, el_id, first, second, known):
    return d.op('op_' + el_id, 'intersect.other_than',
                {'first': ref(first), 'second': ref(second), 'known': ref(known)}, [('point', el_id, 'point')])


def value(e, el_id):
    record = e.elements[el_id]
    if record['state'] != 'defined':
        return record['reason'], record.get('detail')
    return record['value']['x'], record['value']['y']


def near(want, got, tol=1e-9):
    close([got], [want], tol)


# ── the family ────────────────────────────────────────────────────────────

def test_the_curve_family_takes_conics_and_graphs_since_1_8():
    reg = registry()
    assert reg.families['curve'] == ['line', 'segment', 'ray', 'circle', 'arc', 'conic', 'function']
    assert reg.member_since('curve', 'conic') == '1.8'
    assert reg.member_since('curve', 'function') == '1.8'
    assert reg.member_since('curve', 'circle') is None
    for name in ('intersect.nearest', 'intersect.other_than'):
        assert registry().get(name)['since'] in ('1.1', '1.4')     # the records keep their contract


def test_a_conic_in_a_curve_slot_needs_registry_1_8():
    d = Doc().wide('E').at('A', -1, 0).at('B', 1, 0).line('l', 'A', 'B').at('N', 3, 1)
    nearest(d, 'P', 'E', 'l', 'N')
    assert native.min_registry_version(d.doc) == '1.8'
    d.doc['operationRegistryVersion'] = '1.7'
    issues = native.validate(d.doc)
    assert [(i.code, i.path, i.elementId) for i in issues] == [
        ('needs_newer_registry', '/operations/op_P/args/first', 'E')]
    d.doc['operationRegistryVersion'] = '1.8'
    assert native.validate(d.doc) == []


def test_lines_and_circles_keep_their_version():
    d = Doc().at('A', -1, 0).at('B', 1, 0).line('l', 'A', 'B').round_('c', 0, 0, 2).at('N', 3, 1)
    nearest(d, 'P', 'l', 'c', 'N')
    assert native.min_registry_version(d.doc) == '1.4'


# ── nearest ───────────────────────────────────────────────────────────────

def test_nearest_of_a_line_and_a_conic_in_either_order():
    d = Doc().wide('E').at('A', -1, 0).at('B', 1, 0).line('l', 'A', 'B').at('N', 3, 1)
    nearest(d, 'P', 'E', 'l', 'N')
    nearest(d, 'Q', 'l', 'E', 'N')
    e = evaluate(d)
    near((4, 0), value(e, 'P'))
    near((4, 0), value(e, 'Q'))
    checks_pass(d)


def test_nearest_of_two_conics():
    # x²/16 + y²/4 = 1 and x²/4 + y²/16 = 1 meet at (±4/√5, ±4/√5)
    d = Doc().wide('E').tall('F').at('N', 2, -3)
    nearest(d, 'P', 'E', 'F', 'N')
    s = 4 / math.sqrt(5)
    near((s, -s), value(evaluate(d), 'P'))
    checks_pass(d)


def test_nearest_of_a_conic_and_a_circle():
    d = Doc().wide('E').round_('c', 0, 0, 3).at('N', -5, -5)
    nearest(d, 'P', 'c', 'E', 'N')
    # x² + y² = 9 on x²/16 + y²/4 = 1: x² = 20/3, y² = 7/3
    near((-math.sqrt(20 / 3), -math.sqrt(7 / 3)), value(evaluate(d), 'P'))
    checks_pass(d)


def test_nearest_of_a_graph_and_a_line():
    d = Doc().graph('f', op('^', X, n(2))).at('A', 0, 1).at('B', 1, 1).line('l', 'A', 'B').at('N', 2, 0)
    nearest(d, 'P', 'f', 'l', 'N')
    nearest(d, 'Q', 'l', 'f', 'N')
    e = evaluate(d)
    near((1, 1), value(e, 'P'))
    near((1, 1), value(e, 'Q'))
    checks_pass(d)


def test_nearest_of_a_graph_and_a_vertical_line():
    d = Doc().graph('f', op('^', X, n(2))).at('A', 2, 0).at('B', 2, 1).line('l', 'A', 'B').at('N', 0, 0)
    nearest(d, 'P', 'l', 'f', 'N')
    near((2, 4), value(evaluate(d), 'P'))
    checks_pass(d)


def test_nearest_of_two_graphs():
    d = Doc().graph('f', op('^', X, n(2))).graph('g', op('+', X, n(2))).at('N', -3, 0)
    nearest(d, 'P', 'f', 'g', 'N')
    near((-1, 1), value(evaluate(d), 'P'), tol=1e-7)
    checks_pass(d)


def test_nearest_of_a_graph_and_a_conic():
    d = Doc().graph('f', op('/', op('^', X, n(2)), n(4))).round_('c', 0, 5, math.sqrt(20)).at('N', 5, 6)
    nearest(d, 'P', 'c', 'f', 'N')
    near((2 * math.sqrt(5), 5), value(evaluate(d), 'P'))
    checks_pass(d)


def test_an_arc_filters_the_points_of_a_graph():
    # y = 1 and the arc of x² + y² = 4 from (2, 0) to (0, 2): only (√3, 1) is on it
    d = Doc().graph('f', n(1)).round_('O', 0, 0, 2)
    d.at('A', 2, 0).at('B', 0, 2)
    d.op('op_k', 'arc.center_two_points', {'center': ref('O_c'), 'a': ref('A'), 'b': ref('B')}, [('arc', 'k', 'arc')])
    d.at('N', -2, 1)
    nearest(d, 'P', 'f', 'k', 'N')
    near((math.sqrt(3), 1), value(evaluate(d), 'P'))
    checks_pass(d)


def test_a_part_names_the_slot_of_the_operation():
    # the segment from (-1, 3) to (1, 3) misses y = x² (|x| = √3)
    d = Doc().graph('f', op('^', X, n(2))).at('A', -1, 3).at('B', 1, 3).segment('s', 'A', 'B').at('N', 0, 0)
    nearest(d, 'P', 'f', 's', 'N')
    nearest(d, 'Q', 's', 'f', 'N')
    e = evaluate(d)
    assert value(e, 'P') == ('outside_part', {'slot': 'second'})
    assert value(e, 'Q') == ('outside_part', {'slot': 'first'})


def test_no_common_point_gives_the_reason_of_the_pair():
    d = Doc().graph('f', n(5)).round_('c', 0, 0, 2).wide('E').tall('F', cx=20).at('N', 0, 0)
    nearest(d, 'P', 'f', 'c', 'N')
    nearest(d, 'Q', 'E', 'F', 'N')
    e = evaluate(d)
    assert value(e, 'P') == ('no_intersection', None)
    assert value(e, 'Q') == ('no_intersection', None)


# ── other_than ────────────────────────────────────────────────────────────

def test_other_than_on_a_line_and_a_conic():
    d = Doc().wide('E').at('A', -4, 0).at('B', 1, 0).line('l', 'A', 'B')
    other(d, 'P', 'E', 'l', 'A')
    other(d, 'Q', 'l', 'E', 'A')
    e = evaluate(d)
    near((4, 0), value(e, 'P'))
    near((4, 0), value(e, 'Q'))
    checks_pass(d)


def test_other_than_a_tangency_is_the_touching_point():
    # y = 2 touches x²/16 + y²/4 = 1 at (0, 2)
    d = Doc().wide('E').at('A', 0, 2).at('B', 1, 2).line('l', 'A', 'B')
    other(d, 'P', 'l', 'E', 'A')
    near((0, 2), value(evaluate(d), 'P'))


def test_other_than_takes_the_first_other_solution_in_the_pair_order():
    # y = x²/4 and the circle about (0, 5) of radius √20: x = −2√5, −2, 2, 2√5 (roots_ascending)
    s = 2 * math.sqrt(5)
    d = Doc().graph('f', op('/', op('^', X, n(2)), n(4))).round_('c', 0, 5, math.sqrt(20)).at('K', 2, 1)
    other(d, 'P', 'f', 'c', 'K')
    d.at('L', -s, 5)
    other(d, 'Q', 'c', 'f', 'L')
    e = evaluate(d)
    near((-s, 5), value(e, 'P'))
    near((-2, 1), value(e, 'Q'))
    checks_pass(d)


def test_other_than_on_two_conics_follows_first_curve_order():
    s = 4 / math.sqrt(5)
    d = Doc().wide('E').tall('F').at('K', s, s).meet('m', 'E', 'F')
    other(d, 'P', 'E', 'F', 'K')
    e = evaluate(d)
    order = [value(e, f'm{k}') for k in range(1, 5)]
    hit = min(range(4), key=lambda k: math.hypot(order[k][0] - s, order[k][1] - s))
    want = order[0] if hit else order[1]                # the first slot of conic_conic that is not K
    near(want, value(e, 'P'))
    checks_pass(d)


def test_other_than_misses_a_known_point_off_the_pair():
    d = Doc().graph('f', op('^', X, n(2))).at('A', 0, 1).at('B', 1, 1).line('l', 'A', 'B').at('K', 5, 5)
    other(d, 'P', 'f', 'l', 'K')
    assert value(evaluate(d), 'P') == ('branch_absent', None)
