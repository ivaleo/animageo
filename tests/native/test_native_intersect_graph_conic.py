"""Common points of a graph and a conic (registry 1.8; docs/native/ops/intersect.function_conic.md)."""
import math

from animageo.native.registry import registry
from tests.native.conftest import ref
from tests.native.test_native_intersect_conics import X, Doc, checks_pass, close, evaluate, n, op, points


def test_record():
    record = registry().get('intersect.function_conic')
    assert record['since'] == '1.8' and record['status'] == 'beta'
    assert [(i['slot'], i['type']) for i in record['inputs']] == [('function', 'function'), ('conic', 'conical')]
    assert record['branch']['policy'] == 'roots_ascending'


# ── graph and conic ───────────────────────────────────────────────────────

def test_a_parabola_graph_and_a_circle():
    # y = x²/4 and the circle about (0, 5) of radius √20: x = ±2, ±2√5
    d = Doc().graph('f', op('/', op('^', X, n(2)), n(4))).round_('c', 0, 5, math.sqrt(20)).graph_conic('P', 'f', 'c')
    s = 2 * math.sqrt(5)
    close(points(evaluate(d), 'P'), [(-s, 5), (-2, 1), (2, 1), (s, 5)])
    checks_pass(d)


def test_a_line_graph_tangent_to_an_ellipse():
    d = Doc().graph('f', n(2)).wide('E').graph_conic('P', 'f', 'E', count=3)
    e = evaluate(d)
    # the touching point by the golden section of |h| (as intersect.function_function): x to ~√ε
    close(points(e, 'P', 3), [(0, 2), (0, 2), 'branch_absent'], tol=1e-6)
    assert e.elements['P1']['detail'] == {'multiplicity': 2}
    checks_pass(d)


def test_a_graph_on_the_conic_is_coincident():
    d = Doc().graph('f', {'fn': 'sqrt', 'args': [op('-', n(4), op('^', X, n(2)))]}).round_('c', 0, 0, 2).graph_conic('P', 'f', 'c')
    assert points(evaluate(d), 'P') == ['coincident'] * 4


def test_graph_misses_the_conic_and_recovers():
    d = Doc().graph('f', n(5)).round_('c', 0, 0, 2).graph_conic('P', 'f', 'c', count=2)
    assert points(evaluate(d), 'P', 2) == ['no_intersection'] * 2
    d.doc['inputs']['c_p'] = {'kind': 'point', 'value': [0.0, 6.0]}
    got = points(evaluate(d), 'P', 2)
    assert got[0][0] < 0 < got[1][0]
    checks_pass(d)


def test_a_graph_and_an_arc():
    d = Doc().graph('f', n(1)).round_('O', 0, 0, 2)
    d.at('A', 2, 0).at('B', 0, 2)
    d.op('op_k', 'arc.center_two_points', {'center': ref('O_c'), 'a': ref('A'), 'b': ref('B')}, [('arc', 'k', 'arc')])
    d.graph_conic('P', 'f', 'k', count=2)
    e = evaluate(d)
    close(points(e, 'P', 2), ['outside_part', (math.sqrt(3), 1)])
    assert e.elements['P1']['detail'] == {'slot': 'conic'}


def test_a_graph_and_a_hyperbola_in_the_window():
    d = Doc().graph('f', op('*', n(0.5), X)).hyperbola('H').graph_conic('P', 'f', 'H', count=2)
    x = 1 / math.sqrt(1 / 9 - 1 / 64)
    close(points(evaluate(d), 'P', 2), [(-x, -x / 2), (x, x / 2)])
    checks_pass(d)
