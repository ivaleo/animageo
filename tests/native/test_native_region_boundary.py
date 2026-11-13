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
    """Graphs and conics as carriers come later: ``unsupported_signature``."""
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
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', 1e-9, 3).free('K', 0, 3)
    d.segment('s', 'A', 'B').line('a', 'B', 'K').line('b', 'K', 'A')
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


# ── empty, simple, nested ───────────────────────────────────────────────

def segments_triangle(c=(0, 3)):
    """Segments AB, BC, CA of the free points A (0, 0), B (4, 0), C."""
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', *c)
    d.segment('ab', 'A', 'B').segment('bc', 'B', 'C').segment('ca', 'C', 'A')
    return d.boundary('R', ['ab', 'bc', 'ca'], ['A', 'B', 'C'], ['B', 'C', 'A'])


def reason(doc, el_id='R'):
    _e, rec = evaluated(doc, el_id)
    return rec['state'], rec['reason']


def test_collinear_vertices_are_an_empty_region():
    assert reason(segments_triangle(c=(2, 0))) == ('undefined', 'empty_region')


def test_vertex_across_the_opposite_side_is_flipped():
    assert reason(segments_triangle(c=(1, -2))) == ('undefined', 'flipped')


def concurrent(shift):
    """Lines y = 0, x = 0 and x + y = shift; the vertices are their intersections."""
    d = Doc().free('P1', -1, 0).free('P2', 1, 0).free('Q1', 0, -1).free('Q2', 0, 1)
    d.free('S1', shift + 1, -1).free('S2', shift - 1, 1)
    d.line('c', 'P1', 'P2').line('b', 'Q1', 'Q2').line('a', 'S1', 'S2')
    d.intersect('X', 'b', 'c').intersect('Y', 'c', 'a').intersect('Z', 'a', 'b')
    return d.boundary('R', ['c', 'a', 'b'], ['X', 'Y', 'Z'], ['Y', 'Z', 'X'])


def test_third_line_through_a_vertex():
    """The triangle shrinks to the point X and grows on the other side, walked the same
    way: empty at the instant, defined (the opposite face) beyond."""
    _e, v = defined(concurrent(3))
    assert v['area'] == pytest.approx(4.5, abs=1e-12)
    assert reason(concurrent(0)) == ('undefined', 'empty_region')
    _e, v = defined(concurrent(-2))
    assert v['area'] == pytest.approx(2.0, abs=1e-12)


def test_bow_tie_is_a_boundary_crossing():
    """An uneven bow tie: a symmetric one has zero area and is empty first."""
    d = Doc().free('A', 0, 0).free('B', 4, 0).free('C', 0, 4).free('D', 6, 4)
    d.segment('ab', 'A', 'B').segment('bc', 'B', 'C').segment('cd', 'C', 'D').segment('da', 'D', 'A')
    d.boundary('R', ['ab', 'bc', 'cd', 'da'], ['A', 'B', 'C', 'D'], ['B', 'C', 'D', 'A'])
    assert reason(d) == ('undefined', 'boundary_crossing')


def test_a_vertex_visited_twice_is_a_boundary_crossing():
    """A figure eight through V: the pieces meet at V away from their own joints."""
    d = Doc().free('V', 0, 0).free('A', 2, -1).free('B', 2, 1).free('C', -2, 1).free('D', -2, -1)
    for a, b in (('V', 'A'), ('A', 'B'), ('B', 'V'), ('V', 'C'), ('C', 'D'), ('D', 'V')):
        d.segment(a.lower() + b.lower(), a, b)
    d.boundary('R', ['va', 'ab', 'bv', 'vc', 'cd', 'dv'], ['V', 'A', 'B', 'V', 'C', 'D'],
               ['A', 'B', 'V', 'C', 'D', 'V'])
    assert reason(d) == ('undefined', 'boundary_crossing')


def rings(holes, r_out=5.0, inside_extra=()):
    """``inside`` the circle of r_out about the origin; ``outside`` circles ``(cx, cy, r)``."""
    d = Doc().free('O', 0, 0).free('T', r_out, 0).circle('big', 'O', 'T')
    names = []
    for k, (cx, cy, r) in enumerate(holes):
        d.free(f'H{k}', cx, cy).free(f'U{k}', cx + r, cy).circle(f'h{k}', f'H{k}', f'U{k}')
        names.append(f'h{k}')
    extra = []
    for k, (cx, cy, r) in enumerate(inside_extra):
        d.free(f'I{k}', cx, cy).free(f'J{k}', cx + r, cy).circle(f'i{k}', f'I{k}', f'J{k}')
        extra.append(f'i{k}')
    return d.boundary('R', inside=['big'] + extra, outside=names)


def test_a_hole_inside():
    _e, v = defined(rings([(1, 0, 2)]))
    assert v['area'] == pytest.approx(21 * math.pi, abs=1e-12)


def test_a_hole_crossing_its_ring():
    assert reason(rings([(4, 0, 2)])) == ('undefined', 'boundary_crossing')


def test_a_hole_touching_its_ring():
    assert reason(rings([(3, 0, 2)])) == ('undefined', 'boundary_crossing')


def test_a_hole_out_of_its_ring():
    assert reason(rings([(9, 0, 2)])) == ('undefined', 'boundary_crossing')


def test_an_island_in_a_hole():
    _e, v = defined(rings([(0, 0, 3)], inside_extra=[(0, 0, 1)]))
    assert v['area'] == pytest.approx((25 - 9 + 1) * math.pi, abs=1e-12)
    assert v['shape'] == [[['ccw', 'inside.0']], [['ccw', 'inside.1']], [['cw', 'outside.0']]]


def test_an_inside_contour_in_its_ring_is_a_boundary_crossing():
    assert reason(rings([], inside_extra=[(0, 0, 1)])) == ('undefined', 'boundary_crossing')


def test_a_chain_hole_walked_clockwise():
    """A triangle walked clockwise inside a contour is a hole."""
    d = segments_triangle()
    d.free('O', 1, 1).free('T', 7, 1).circle('big', 'O', 'T')
    d.boundary('R', ['ca', 'bc', 'ab'], ['A', 'C', 'B'], ['C', 'B', 'A'], inside=['big'])
    _e, v = defined(d)
    assert v['shape'] == [[['line', 'curves.0'], ['line', 'curves.1'], ['line', 'curves.2']], [['ccw', 'inside.0']]]
    assert v['area'] == pytest.approx(36 * math.pi - 6, abs=1e-12)


def test_a_chain_walked_clockwise_alone_is_flipped():
    d = segments_triangle().boundary('R', ['ca', 'bc', 'ab'], ['A', 'C', 'B'], ['C', 'B', 'A'])
    assert reason(d) == ('undefined', 'flipped')


def lune(dx):
    """c1 r = 5 about the origin, c2 r = 3 about (dx, 0); the part of c2 outside c1."""
    d = Doc().free('O1', 0, 0).free('T1', 5, 0).free('O2', dx, 0).free('T2', dx + 3, 0)
    d.circle('c1', 'O1', 'T1').circle('c2', 'O2', 'T2').circle_circle('P', 'Q', 'c1', 'c2')
    return d.boundary('R', ['c2', 'c1'], ['Q', 'Q'], ['P', 'P'])


def test_lune_at_internal_tangency():
    _e, v = defined(lune(4))
    assert v['shape'] == [[['ccw', 'curves.0'], ['cw', 'curves.1']]]
    assert 0 < v['area'] < 9 * math.pi
    assert reason(lune(2)) == ('undefined', 'empty_region')
    assert reason(lune(1)) == ('undefined', 'upstream')


def chord(h):
    """The part of the disc r = 5 above the chord y = h (a circle segment by a chain)."""
    d = Doc().free('O', 0, 0).free('T', 5, 0).circle('k', 'O', 'T')
    d.free('L1', -6, h).free('L2', 6, h).segment('s', 'L1', 'L2').line_circle('P', 'Q', 's', 'k')
    return d.boundary('R', ['k', 's'], ['Q', 'P'], ['P', 'Q'])


def test_chord_touching_its_circle():
    _e, v = defined(chord(3))
    assert v['area'] == pytest.approx(25 * math.acos(3 / 5) - 3 * 4, abs=1e-12)
    assert reason(chord(5)) == ('undefined', 'empty_region')
    assert reason(chord(5.5)) == ('undefined', 'upstream')


def test_too_many_pieces_is_an_error():
    d = Doc()
    names = []
    for k in range(257):
        t = 2 * math.pi * k / 257
        d.free(f'V{k}', round(5 * math.cos(t), 6), round(5 * math.sin(t), 6))
        names.append(f'V{k}')
    d.polygon('poly', *names).boundary('R', inside=['poly'])
    assert reason(d) == ('error', 'limit_exceeded')


def test_the_check_passes():
    from animageo.native.kernel.checks import run_checks
    e, _v = defined(chord(3))
    assert run_checks(e, ['op_R:on_carriers']).results == {'op_R:on_carriers': 'passed'}


def test_a_stadium_joins_lines_and_arcs_at_tangents():
    d = Doc().free('A', -2, -1).free('B', 2, -1).free('C', 2, 1).free('D', -2, 1)
    d.free('E', 2, 0).free('F', -2, 0)
    d.segment('bottom', 'A', 'B').segment('top', 'C', 'D').circle('right', 'E', 'B').circle('left', 'F', 'D')
    d.boundary('R', ['bottom', 'right', 'top', 'left'], ['A', 'B', 'C', 'D'], ['B', 'C', 'D', 'A'])
    _e, v = defined(d)
    assert v['area'] == pytest.approx(8 + math.pi, abs=1e-12)


def test_a_circle_in_two_arcs():
    d = Doc().free('O', 0, 0).free('T', 2, 0).circle('k', 'O', 'T')
    d.free('P', 0, 2).free('Q', 0, -2)
    d.boundary('R', ['k', 'k'], ['P', 'Q'], ['Q', 'P'])
    _e, v = defined(d)
    assert v['area'] == pytest.approx(4 * math.pi, abs=1e-12)
    assert reason(d.boundary('R', ['k', 'k'], ['P', 'P'], ['Q', 'Q'])) == ('undefined', 'empty_region')


def test_a_hole_sharing_a_vertex_with_its_ring():
    d = Doc().free('A', 0, 0).free('B', 6, 0).free('C', 0, 6).free('D', 2, 1).free('E', 1, 2)
    for a, b in (('A', 'B'), ('B', 'C'), ('C', 'A'), ('A', 'E'), ('E', 'D'), ('D', 'A')):
        d.segment(a.lower() + b.lower(), a, b)
    d.boundary('R', ['ab', 'bc', 'ca', 'ae', 'ed', 'da'], ['A', 'B', 'C', 'A', 'E', 'D'],
               ['B', 'C', 'A', 'E', 'D', 'A'])
    assert reason(d) == ('undefined', 'boundary_crossing')
    d.free('A2', 1, 1).segment('a2e', 'A2', 'E').segment('da2', 'D', 'A2')
    d.boundary('R', ['ab', 'bc', 'ca', 'a2e', 'ed', 'da2'], ['A', 'B', 'C', 'A2', 'E', 'D'],
               ['B', 'C', 'A', 'E', 'D', 'A2'])
    _e, v = defined(d)
    assert v['area'] == pytest.approx(18 - 0.5, abs=1e-12)
    assert v['shape'][1] == [['line', 'curves.3'], ['line', 'curves.4'], ['line', 'curves.5']]
