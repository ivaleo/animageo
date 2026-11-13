"""The region bounded by a chain of pieces and contours, registry 1.9
(docs/native/ops/region.by_boundary.md, docs/native/kernel.md §16)."""
import math

import pytest

from animageo import native
from animageo.native.kernel import region as R
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, point_input, ref_list


class Doc(DocBuilder):
    def __init__(self, bounds=(-10, -10, 10, 10)):
        super().__init__('boundary', bounds, registry_version='1.9')

    def boundary(self, el_id, curves=(), froms=(), tos=(), inside=(), outside=()):
        args = {'curves': ref_list(*curves), 'from': ref_list(*froms), 'to': ref_list(*tos),
                'inside': ref_list(*inside), 'outside': ref_list(*outside)}
        return self.op('op_' + el_id, 'region.by_boundary', args, [('region', el_id, 'region')])

    def arc(self, el_id, center, a, b):
        return self.op('op_' + el_id, 'arc.center_two_points',
                       {'center': {'kind': 'ref', 'elementId': center}, 'a': {'kind': 'ref', 'elementId': a},
                        'b': {'kind': 'ref', 'elementId': b}}, [('arc', el_id, 'arc')])


def evaluated(doc, el_id='R'):
    e = native.evaluate(doc.doc)
    return e, e.elements[el_id]


def defined(doc, el_id='R'):
    e, rec = evaluated(doc, el_id)
    assert rec['state'] == 'defined', rec
    return e, rec['value']


def flat(x):
    return [v for item in x for v in flat(item)] if isinstance(x, list) else [x]


def same(a, b, tol=1e-12):
    """Nested lists equal up to ``tol``."""
    return flat(a) == pytest.approx(flat(b), abs=tol) and len(flat(a)) == len(flat(b))


def signed(ring, kinds):
    total = 0.0
    for piece, (kind, _source) in zip(ring, kinds):
        total += R.line_area(*piece) if kind == 'line' else R.arc_area(piece, kind)
    return total


def triangle(doc=None):
    """Three lines through (0, 0), (4, 0), (0, 3), the vertices their intersections."""
    d = doc or Doc()
    d.free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
    d.line('a', 'B', 'C').line('b', 'C', 'A').line('c', 'A', 'B')
    d.intersect('X', 'b', 'c').intersect('Y', 'c', 'a').intersect('Z', 'a', 'b')
    return d


def two_circles(doc=None, dx=6.0):
    """Circles of radius 5 about (0, 0) and (dx, 0); P below, Q above (line_param_order)."""
    d = doc or Doc()
    d.free('O1', 0, 0).free('T1', 5, 0).free('O2', dx, 0).free('T2', dx + 5, 0)
    d.circle('c1', 'O1', 'T1').circle('c2', 'O2', 'T2')
    d.circle_circle('P', 'Q', 'c1', 'c2')
    return d


# ── the chain (by IDs only) ─────────────────────────────────────────────

def test_chain_forward_and_backward():
    rings, problem = R.boundary_chain(['c', 'a', 'b'], ['X', 'Y', 'X'], ['Y', 'Z', 'Z'])
    assert problem is None
    assert rings == [[(0, True), (1, True), (2, False)]]


def test_chain_several_rings_and_a_whole_circle():
    rings, problem = R.boundary_chain(['k', 'c', 'a', 'b'], ['K', 'X', 'Y', 'Z'], ['K', 'Y', 'Z', 'X'],
                                      [True, False, False, False])
    assert problem is None
    assert rings == [[(0, True)], [(1, True), (2, True), (3, True)]]


@pytest.mark.parametrize('curves, froms, tos, round_, contours, text', [
    (['a', 'b'], ['X'], ['Y', 'X'], None, 0, 'equal'),
    ([], [], [], None, 0, 'no ring'),
    (['a', 'b'], ['X', 'Y'], ['Y', 'Z'], None, 0, 'not closed'),
    (['a', 'b', 'c'], ['X', 'W', 'Z'], ['Y', 'Z', 'X'], None, 0, 'neither starts nor ends'),
    (['a'], ['X'], ['X'], [False], 0, 'not a circle'),
    (['a', 'k', 'b'], ['X', 'K', 'Y'], ['Y', 'K', 'X'], [False, True, False], 0, 'of its own'),
])
def test_chain_problems(curves, froms, tos, round_, contours, text):
    rings, problem = R.boundary_chain(curves, froms, tos, round_, contours)
    assert rings is None and text in problem


def test_contours_alone_are_a_ring():
    assert R.boundary_chain([], [], [], [], 1) == ([], None)


def test_broken_chain_is_an_issue_and_a_schema_error():
    d = triangle().boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'Z'], ['Y', 'Z', 'Y'])
    issues = [i for i in native.validate(d.doc) if i.code == 'region_chain']
    assert len(issues) == 1
    assert issues[0].path == '/operations/op_R/args' and issues[0].operationId == 'op_R'
    _e, rec = evaluated(d)
    assert rec['state'] == 'error' and rec['reason'] == 'schema'


def test_good_chain_has_no_issue():
    d = triangle().boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'Z'], ['Y', 'Z', 'X'])
    assert [i for i in native.validate(d.doc) if i.severity == 'error'] == []


def test_two_point_elements_at_one_spot_break_the_chain():
    d = triangle().free('Y2', 4, 0).boundary('R', ['c', 'a', 'b'], ['X', 'Y2', 'Z'], ['Y', 'Z', 'X'])
    assert any(i.code == 'region_chain' for i in native.validate(d.doc))


# ── the value ───────────────────────────────────────────────────────────

def test_record():
    rec = registry().get('region.by_boundary')
    assert rec['since'] == '1.9' and rec['status'] == 'beta'
    assert [(i['slot'], i['type']) for i in rec['inputs']] == [
        ('curves', 'curve'), ('from', 'point'), ('to', 'point'), ('inside', 'contour'), ('outside', 'contour')]
    assert rec['outputs'] == [{'slot': 'region', 'type': 'region'}]


def test_triangle_of_three_lines():
    d = triangle().boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'Z'], ['Y', 'Z', 'X'])
    _e, v = defined(d)
    assert v['shape'] == [[['line', 'curves.0'], ['line', 'curves.1'], ['line', 'curves.2']]]
    assert same(v['rings'], [[[[0, 0], [4, 0]], [[4, 0], [0, 3]], [[0, 3], [0, 0]]]])
    assert v['area'] == pytest.approx(6.0, abs=1e-12)


def test_backward_piece_walks_from_its_end():
    d = triangle().boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'X'], ['Y', 'Z', 'Z'])
    _e, v = defined(d)
    assert same(v['rings'][0][2], [[0, 3], [0, 0]])
    assert v['area'] == pytest.approx(6.0, abs=1e-12)


LENS = 2 * (25 * math.acos(3 / 5) - 3 * 4)               # two circular segments of chord 8, r = 5


def test_lens_of_two_circles():
    """P (3, 4) is the first common point, Q (3, −4) the second; both arcs ccw."""
    d = two_circles().boundary('R', ['c1', 'c2'], ['Q', 'P'], ['P', 'Q'])
    _e, v = defined(d)
    assert v['shape'] == [[['ccw', 'curves.0'], ['ccw', 'curves.1']]]
    (first, second), = v['rings']
    assert same(first, [[3, -4], [3, 4], [0, 0, 5]])
    assert same(second, [[3, 4], [3, -4], [6, 0, 5]])
    assert v['area'] == pytest.approx(LENS, abs=1e-12)
    assert signed(v['rings'][0], v['shape'][0]) == pytest.approx(v['area'], abs=1e-12)


def test_lune_walks_an_arc_back():
    """c1 ccw from P to Q is its left arc; c2 from P to Q (its left arc) walked back, clockwise."""
    d = two_circles().boundary('R', ['c1', 'c2'], ['P', 'P'], ['Q', 'Q'])
    _e, v = defined(d)
    assert v['shape'] == [[['ccw', 'curves.0'], ['cw', 'curves.1']]]
    (first, second), = v['rings']
    assert same(first, [[3, 4], [3, -4], [0, 0, 5]])
    assert same(second, [[3, -4], [3, 4], [6, 0, 5]])
    assert v['area'] == pytest.approx(25 * math.pi - LENS, abs=1e-12)


def test_whole_circle_from_a_point_to_itself():
    d = Doc().free('O', 0, 0).free('T', 2, 0).circle('k', 'O', 'T').on_path('K', 'k', 0.25)
    d.boundary('R', ['k'], ['K'], ['K'])
    _e, v = defined(d)
    assert v['shape'] == [[['ccw', 'curves.0']]]
    assert v['area'] == pytest.approx(4 * math.pi, abs=1e-12)


def test_annulus_of_two_contours():
    d = Doc().free('O', 1, 1).free('T', 4, 1).free('U', 2, 1)
    d.circle('big', 'O', 'T').circle('small', 'O', 'U')
    d.boundary('R', inside=['big'], outside=['small'])
    _e, v = defined(d)
    assert v['shape'] == [[['ccw', 'inside.0']], [['cw', 'outside.0']]]
    assert v['rings'][0] == [[[4, 1], [4, 1], [1, 1, 3]]]
    assert v['rings'][1] == [[[2, 1], [2, 1], [1, 1, 1]]]
    assert v['area'] == pytest.approx(8 * math.pi, abs=1e-12)


def test_polygon_contours_are_oriented_by_their_slot():
    d = Doc().free('A', 0, 0).free('B', 0, 4).free('C', 4, 4).free('D', 4, 0)   # clockwise
    d.free('E', 1, 1).free('F', 3, 1).free('G', 2, 3)                          # counterclockwise
    d.polygon('sq', 'A', 'B', 'C', 'D').polygon('tr', 'E', 'F', 'G')
    d.boundary('R', inside=['sq'], outside=['tr'])
    _e, v = defined(d)
    assert v['rings'][0] == [[[0, 0], [4, 0]], [[4, 0], [4, 4]], [[4, 4], [0, 4]], [[0, 4], [0, 0]]]
    assert v['rings'][1] == [[[1, 1], [2, 3]], [[2, 3], [3, 1]], [[3, 1], [1, 1]]]
    assert v['shape'] == [[['line', 'inside.0']] * 4, [['line', 'outside.0']] * 3]
    assert v['area'] == pytest.approx(16 - 2, abs=1e-12)


def test_sector_and_circle_segment_contours():
    d = Doc().free('O', 0, 0).free('A', 2, 0).free('B', 0, 2)
    d.op('op_s', 'sector.center_two_points', {'center': {'kind': 'ref', 'elementId': 'O'},
                                              'a': {'kind': 'ref', 'elementId': 'A'},
                                              'b': {'kind': 'ref', 'elementId': 'B'}}, [('sector', 's', 'sector')])
    d.boundary('R', inside=['s'])
    _e, v = defined(d)
    assert v['shape'] == [[['line', 'inside.0'], ['ccw', 'inside.0'], ['line', 'inside.0']]]
    assert v['area'] == pytest.approx(math.pi, abs=1e-12)


def test_conic_carrier_is_unsupported():
    """Graphs and conics as carriers come later (2c): ``unsupported_signature``."""
    circle = {'op': '-', 'args': [{'op': '+', 'args': [{'op': '^', 'args': [{'var': 'x'}, {'num': 2}]},
                                                       {'op': '^', 'args': [{'var': 'y'}, {'num': 2}]}]},
                                  {'num': 4}]}
    d = Doc().free('A', -2, 0).free('B', 2, 0).segment('s', 'A', 'B')
    d.op('op_k', 'conic.equation', {'expr': {'kind': 'expr', 'ast': circle}, 'refs': ref_list()},
         [('conic', 'k', 'conic')])
    d.boundary('R', ['s', 'k'], ['A', 'A'], ['B', 'B'])
    _e, rec = evaluated(d)
    assert rec['state'] == 'unsupported' and rec['reason'] == 'unsupported_signature', rec


def test_the_bridge_reruns_the_chain_by_ids():
    """The classic construction re-runs the operation with the element IDs of its inputs."""
    from animageo.native.kernel.bridge import build_construction, from_classic
    d = two_circles().boundary('R', ['c1', 'c2'], ['P', 'P'], ['Q', 'Q'])
    construction, names = build_construction(d.doc)
    construction.rebuild(full=True)
    _e, v = defined(d)
    assert from_classic('region', construction.element(names.by_id['R']).data) == v


# ── incidence and the part of the carrier ──────────────────────────────

def quarter(doc=None):
    """The arc of radius 5 about O from E (5, 0) to F (0, 5) and the segments FO, OE."""
    d = doc or Doc()
    d.free('O', 0, 0).free('E', 5, 0).free('F', 0, 5).arc('k', 'O', 'E', 'F')
    d.segment('fo', 'F', 'O').segment('oe', 'O', 'E')
    return d


def test_quarter_disc_on_an_arc():
    d = quarter().boundary('R', ['k', 'fo', 'oe'], ['E', 'F', 'O'], ['F', 'O', 'E'])
    _e, v = defined(d)
    assert v['shape'] == [[['ccw', 'curves.0'], ['line', 'curves.1'], ['line', 'curves.2']]]
    assert v['area'] == pytest.approx(25 * math.pi / 4, abs=1e-12)


def test_vertex_off_its_line_is_not_on_curve():
    d = triangle(Doc().free('G', 0.5, 3))
    d.boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'G'], ['Y', 'G', 'X'])
    _e, rec = evaluated(d)
    assert (rec['state'], rec['reason'], rec.get('detail')) == ('undefined', 'not_on_curve', {'slot': 'to.1'})


def test_vertex_off_its_circle_is_not_on_curve():
    d = quarter().free('H', 0, 4).segment('ho', 'H', 'O')
    d.boundary('R', ['k', 'ho', 'oe'], ['E', 'H', 'O'], ['H', 'O', 'E'])
    _e, rec = evaluated(d)
    assert (rec['reason'], rec.get('detail')) == ('not_on_curve', {'slot': 'to.0'})


def test_vertex_within_the_incidence_tolerance():
    d = triangle(Doc().free('G', 1e-9, 3))
    d.boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'Z'], ['Y', 'G', 'X'])
    _e, rec = evaluated(d)
    assert rec['reason'] == 'schema'                       # G is not Z: the chain breaks by IDs
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', 1e-9, 3).free('C0', 0, 3)
    d.segment('s', 'A', 'B').line('a', 'B', 'C0').line('b', 'C0', 'A')
    d.boundary('R', ['s', 'a', 'b'], ['A', 'B', 'C'], ['B', 'C', 'A'])
    defined(d)


def test_piece_beyond_its_segment_is_outside_part():
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', 0, 3).free('D', 5, 0)
    d.segment('s', 'A', 'B').line('a', 'D', 'C').line('b', 'C', 'A')
    d.boundary('R', ['s', 'a', 'b'], ['A', 'D', 'C'], ['D', 'C', 'A'])
    _e, rec = evaluated(d)
    assert (rec['reason'], rec.get('detail')) == ('outside_part', {'slot': 'curves.0'})


def test_piece_behind_its_ray_is_outside_part():
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', 0, 3).free('D', 5, 0)
    d.ray('s', 'B', 'A').line('a', 'D', 'C').line('b', 'C', 'A')
    d.boundary('R', ['s', 'a', 'b'], ['A', 'D', 'C'], ['D', 'C', 'A'])
    _e, rec = evaluated(d)
    assert (rec['reason'], rec.get('detail')) == ('outside_part', {'slot': 'curves.0'})
    d.doc['inputs']['D'] = point_input(3, 0)
    defined(d)


def test_piece_around_the_rest_of_an_arc_is_outside_part():
    d = quarter().boundary('R', ['k', 'oe', 'fo'], ['F', 'E', 'O'], ['E', 'O', 'F'])
    _e, rec = evaluated(d)
    assert (rec['reason'], rec.get('detail')) == ('outside_part', {'slot': 'curves.0'})


def test_whole_circle_on_a_part_of_an_arc_is_outside_part():
    d = quarter().boundary('R', ['k'], ['E'], ['E'])
    _e, rec = evaluated(d)
    assert (rec['reason'], rec.get('detail')) == ('outside_part', {'slot': 'curves.0'})


def test_upstream_vertex():
    d = two_circles(dx=12.0).boundary('R', ['c1', 'c2'], ['Q', 'P'], ['P', 'Q'])
    _e, rec = evaluated(d)
    assert rec['reason'] == 'upstream'
