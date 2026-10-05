"""Registry 1.5 (1.9.0a1): the ``triangle.*`` operations and ``locus.of_point``
(plan L3 §2.1, §2.2; docs/native/ops/triangle.*.md, locus.of_point.md)."""
import copy
import math
import time

import pytest

from animageo import native
from animageo.native.kernel import bridge
from animageo.native.kernel.checks import CHECKS, run_checks
from animageo.native.kernel.ops import locus as locus_ops
from tests.native.conftest import DocBuilder, num, number_input, path_input, ref


def doc_of(build):
    b = DocBuilder(registry_version='1.5')
    build(b)
    return b.doc


def values(doc, inputs=None):
    ev = native.evaluate(doc, inputs=inputs)
    return ev, {e: (r['value'] if r['state'] == 'defined' else r.get('reason')) for e, r in ev.elements.items()}


def triangle(b, a=(1, 3), bb=(0, 0), c=(4, 0)):
    b.free('A', *a).free('B', *bb).free('C', *c)
    return b


def altitude(b, side, el='h', foot='H', ext='x', vertex='A'):
    return b.op('op_' + el, 'triangle.altitude', {'vertex': ref(vertex), 'side': ref(side)},
                [('altitude', el, 'segment'), ('foot', foot, 'point'), ('extension', ext, 'segment')])


# ── triangle.altitude ────────────────────────────────────────────────────

def test_altitude_acute_foot_is_the_projection_bit_for_bit():
    def build(b):
        triangle(b, a=(1.3, 2.7), c=(4.1, 0.4)).segment('s', 'B', 'C')
        altitude(b, 's')
        b.op('op_P', 'point.projection', {'point': ref('A'), 'base': ref('s')}, [('foot', 'P', 'point')])
    ev, v = values(doc_of(build))
    assert v['H'] == v['P']
    assert v['x'] == 'branch_absent'
    assert v['h']['a'] == [1.3, 2.7] and v['h']['b'] == [v['H']['x'], v['H']['y']]
    report = run_checks(ev)
    assert report.results['op_h:perpendicular'] == 'passed' and report.results['op_h:on_carrier'] == 'passed'


@pytest.mark.parametrize('a, end, foot', [((-2, 3), 'B', (-2, 0)), ((6, 3), 'C', (6, 0))])
def test_altitude_obtuse_extension_from_the_nearer_end(a, end, foot):
    def build(b):
        triangle(b, a=a).segment('s', 'B', 'C')
        altitude(b, 's')
    _ev, v = values(doc_of(build))
    assert v['H'] == {'x': float(foot[0]), 'y': float(foot[1])}
    ends = {'B': [0.0, 0.0], 'C': [4.0, 0.0]}
    assert v['x']['a'] == ends[end] and v['x']['b'] == [float(foot[0]), float(foot[1])]


def test_altitude_right_angle_foot_at_the_vertex_has_no_extension():
    def build(b):
        triangle(b, a=(0, 3)).segment('s', 'B', 'C')
        altitude(b, 's')
    _ev, v = values(doc_of(build))
    assert v['H'] == {'x': 0.0, 'y': 0.0} and v['x'] == 'branch_absent'


def test_altitude_vertex_on_the_side_is_zero_length_with_a_foot():
    def build(b):
        triangle(b, a=(2, 0)).segment('s', 'B', 'C')
        altitude(b, 's')
    _ev, v = values(doc_of(build))
    assert v['h'] == 'zero_length' and v['H'] == {'x': 2.0, 'y': 0.0}


def test_altitude_line_side_ends_come_from_line_by_points_only():
    def build(b):
        triangle(b, a=(-2, 3)).line('l', 'B', 'C')
        b.op('op_m', 'line.parallel', {'point': ref('B'), 'base': ref('l')}, [('line', 'm', 'line')])
        altitude(b, 'l')
        altitude(b, 'm', el='g', foot='G', ext='y')
    _ev, v = values(doc_of(build))
    assert v['x']['a'] == [0.0, 0.0] and v['x']['b'] == [-2.0, 0.0]      # the ends of line.by_points
    assert v['y'] == 'branch_absent'                                      # line.parallel has no ends
    assert v['G'] == v['H']


def test_altitude_check_catches_a_wrong_foot():
    def build(b):
        triangle(b).segment('s', 'B', 'C')
        altitude(b, 's')
    ev = native.evaluate(doc_of(build))
    _name, args, result = ev.computed['op_h']
    bad = dict(result, foot={'x': result['foot']['x'] + 0.1, 'y': result['foot']['y'] + 0.1})
    tol = ev.tolerances
    assert CHECKS[('triangle.altitude', 'on_carrier')](args, bad, tol) > tol.check_failed


# ── triangle.median, triangle.bisector ───────────────────────────────────

def test_median_midpoint_is_point_midpoint_bit_for_bit():
    def build(b):
        triangle(b, a=(0.7, 2.9), c=(3.3, 0.1)).segment('s', 'B', 'C')
        b.op('op_m', 'triangle.median', {'vertex': ref('A'), 'side': ref('s')},
             [('median', 'm', 'segment'), ('midpoint', 'M', 'point')])
        b.midpoint('N', 'B', 'C')
    ev, v = values(doc_of(build))
    assert v['M'] == v['N'] and v['m']['b'] == [v['M']['x'], v['M']['y']]
    assert run_checks(ev).results['op_m:midpoint'] == 'passed'


def test_median_from_the_midpoint_is_zero_length():
    def build(b):
        triangle(b, a=(2, 0)).segment('s', 'B', 'C')
        b.op('op_m', 'triangle.median', {'vertex': ref('A'), 'side': ref('s')},
             [('median', 'm', 'segment'), ('midpoint', 'M', 'point')])
    _ev, v = values(doc_of(build))
    assert v['m'] == 'zero_length' and v['M'] == {'x': 2.0, 'y': 0.0}


def bisector(b, vertex='A'):
    return b.op('op_w', 'triangle.bisector', {'vertex': ref(vertex), 'side': ref('s')},
                [('bisector', 'w', 'segment'), ('foot', 'L', 'point')])


def test_bisector_foot_divides_the_side_in_the_ratio_of_the_sides():
    def build(b):
        triangle(b, a=(0, 3), c=(4, 0)).segment('s', 'B', 'C')
        bisector(b)
    ev, v = values(doc_of(build))
    lb, lc = 3.0, 5.0              # |AB|, |AC|
    assert v['L']['x'] == pytest.approx(4 * lb / (lb + lc)) and v['L']['y'] == 0.0
    report = run_checks(ev)
    assert report.results['op_w:equal_angles'] == 'passed' and report.results['op_w:on_side'] == 'passed'


@pytest.mark.parametrize('a, reason', [((0, 0), 'coincident_points'), ((-3, 0), 'collinear_points')])
def test_bisector_degenerate(a, reason):
    def build(b):
        triangle(b, a=a).segment('s', 'B', 'C')
        bisector(b)
    _ev, v = values(doc_of(build))
    assert v['w'] == reason and v['L'] == reason


def test_bisector_check_catches_a_wrong_foot():
    def build(b):
        triangle(b, a=(0, 3)).segment('s', 'B', 'C')
        bisector(b)
    ev = native.evaluate(doc_of(build))
    _name, args, result = ev.computed['op_w']
    bad = dict(result, foot={'x': result['foot']['x'] + 0.3, 'y': 0.0})
    assert CHECKS[('triangle.bisector', 'equal_angles')](args, bad, ev.tolerances) > ev.tolerances.check_failed


# ── the centres ──────────────────────────────────────────────────────────

def centres(b):
    abc = {'a': ref('A'), 'b': ref('B'), 'c': ref('C')}
    for name in ('centroid', 'incenter', 'circumcenter', 'orthocenter'):
        b.op('op_' + name, 'triangle.' + name, dict(abc), [('point', name, 'point')])
    b.op('op_ex', 'triangle.excenters', dict(abc), [('center', 'ex', 'point')])
    b.op('op_ic', 'circle.incircle', dict(abc), [('circle', 'ic', 'circle'), ('center', 'icc', 'point')])
    b.op('op_cc', 'circle.three_points', dict(abc), [('circle', 'cc', 'circle'), ('center', 'ccc', 'point')])
    b.op('op_ec', 'circle.excircle', dict(abc), [('circle', 'ec', 'circle'), ('center', 'ecc', 'point')])
    return b


@pytest.mark.parametrize('a, bb, c', [((1.3, 2.7), (0, 0), (4.1, 0.4)), ((-1.7, 0.3), (2.2, -1.9), (0.4, 5.3)),
                                      ((0, 0), (10, 0.01), (5, 0.2))])
def test_centres_are_bitwise_the_centres_of_the_circle_ops(a, bb, c):
    _ev, v = values(doc_of(lambda b: centres(triangle(b, a=a, bb=bb, c=c))))
    assert v['incenter'] == v['icc']
    assert v['circumcenter'] == v['ccc']
    assert v['ex'] == v['ecc']


def test_centroid_and_orthocenter_formulas():
    _ev, v = values(doc_of(lambda b: centres(triangle(b, a=(1, 3)))))
    assert v['centroid'] == {'x': ((1 + 0) + 4) / 3, 'y': ((3 + 0) + 0) / 3}
    o = v['circumcenter']
    assert v['orthocenter'] == {'x': ((1 + 0) + 4) - 2 * o['x'], 'y': ((3 + 0) + 0) - 2 * o['y']}


def test_orthocenter_of_a_right_triangle_is_the_vertex():
    _ev, v = values(doc_of(lambda b: centres(triangle(b, a=(0, 3)))))
    assert v['orthocenter']['x'] == pytest.approx(0.0, abs=1e-12)
    assert v['orthocenter']['y'] == pytest.approx(0.0, abs=1e-12)


def test_collinear_centres_are_undefined_but_the_centroid():
    _ev, v = values(doc_of(lambda b: centres(triangle(b, a=(2, 0)))))
    assert v['centroid'] == {'x': 2.0, 'y': 0.0}
    for name in ('incenter', 'circumcenter', 'orthocenter', 'ex'):
        assert v[name] == 'collinear_points', name


@pytest.mark.parametrize('op_name, check, slot', [
    ('triangle.centroid', 'medians', 'point'), ('triangle.incenter', 'equidistant_sides', 'point'),
    ('triangle.circumcenter', 'equidistant', 'point'), ('triangle.orthocenter', 'perpendicular', 'point'),
    ('triangle.excenters', 'equidistant_lines', 'center')])
def test_centre_checks_pass_and_catch_a_wrong_value(op_name, check, slot):
    ev = native.evaluate(doc_of(lambda b: centres(triangle(b, a=(1.3, 2.7)))))
    op_id = {'triangle.excenters': 'op_ex'}.get(op_name, 'op_' + op_name.split('.')[1])
    _name, args, result = ev.computed[op_id]
    tol = ev.tolerances
    assert CHECKS[(op_name, check)](args, result, tol) <= tol.check_passed
    p = result[slot]
    bad = dict(result, **{slot: {'x': p['x'] + 0.2, 'y': p['y'] - 0.1}})
    assert CHECKS[(op_name, check)](args, bad, tol) > tol.check_failed


# ── locus.of_point ───────────────────────────────────────────────────────

def midpoint_locus(b, path_op, path_args, path_type, t=0.25):
    b.free('A', 3, 1)
    b.op('op_path', path_op, path_args, [(path_type, 'path', path_type)])
    b.op('op_P', 'point.on_path', {'path': ref('path')}, [('point', 'P', 'point')])
    b.doc['inputs']['P'] = path_input(t)
    b.midpoint('M', 'A', 'P')
    b.op('op_g', 'locus.of_point', {'trace': ref('M'), 'mover': ref('P')}, [('locus', 'g', 'locus')])
    return b


def segment_locus(b):
    b.free('B', -2, -1).free('C', 4, 2)
    return midpoint_locus(b, 'segment.by_points', {'a': ref('B'), 'b': ref('C')}, 'segment')


def test_locus_on_a_segment_samples_the_definition_range():
    doc = doc_of(segment_locus)
    ev, v = values(doc)
    g = v['g']
    assert g['range'] == [0.0, 1.0] and g['closed'] is False and len(g['points']) == locus_ops.SAMPLES
    assert g['points'][0] == [(3 + -2) / 2, (1 + -1) / 2] and g['points'][-1] == [(3 + 4) / 2, (1 + 2) / 2]
    assert run_checks(ev).results['op_g:on_trace'] == 'passed'


def test_locus_samples_equal_full_evaluations_bit_for_bit():
    doc = doc_of(segment_locus)
    _ev, v = values(doc)
    ts = locus_ops.sample_parameters(0.0, 1.0, False)
    for k in (0, 37, 128, 255):
        _e, w = values(doc, {'P': path_input(ts[k])})
        assert v['g']['points'][k] == [w['M']['x'], w['M']['y']]


def test_locus_leaves_the_document_and_the_mover_unchanged():
    doc = doc_of(segment_locus)
    before = copy.deepcopy(doc)
    _ev, v = values(doc)
    assert doc == before
    plain = copy.deepcopy(doc)
    del plain['operations']['op_g'], plain['elements']['g']
    _e, w = values(plain)
    assert all(v[e] == w[e] for e in w)


def test_locus_on_a_circle_is_closed_over_two_pi():
    def build(b):
        b.free('O', 0, 0).free('R', 2, 0)
        midpoint_locus(b, 'circle.center_point', {'center': ref('O'), 'through': ref('R')}, 'circle')
    _ev, v = values(doc_of(build))
    g = v['g']
    assert g['closed'] is True and g['range'] == [0.0, 2 * math.pi]
    assert g['points'][1] != g['points'][0] and len(g['points']) == locus_ops.SAMPLES


def test_locus_on_a_polygon_runs_over_n_sides():
    def build(b):
        b.free('B', 0, 0).free('C', 4, 0).free('D', 4, 4).free('E', 0, 4)
        b.op('op_q', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref(e) for e in 'BCDE']}},
             [('polygon', 'q', 'polygon')])
        b.free('A', 2, 2)
        b.op('op_P', 'point.on_path', {'path': ref('q')}, [('point', 'P', 'point')])
        b.doc['inputs']['P'] = path_input(0.5)
        b.midpoint('M', 'A', 'P')
        b.op('op_g', 'locus.of_point', {'trace': ref('M'), 'mover': ref('P')}, [('locus', 'g', 'locus')])
    _ev, v = values(doc_of(build))
    assert v['g']['range'] == [0.0, 4.0] and v['g']['closed'] is True
    assert v['g']['points'][64] == [(2 + 4) / 2, (2 + 0) / 2]       # t = 1: the vertex C


def test_locus_on_a_line_is_clipped_to_the_window_b4():
    def build(b):
        b.free('B', 0, 0).free('C', 1, 0)
        midpoint_locus(b, 'line.by_points', {'a': ref('B'), 'b': ref('C')}, 'line')
    _ev, v = values(doc_of(build))
    assert v['g']['range'] == [-40.0, 40.0]        # bounds ±10 scaled 4 times, frame v = C − B


def test_locus_of_a_number_and_an_empty_range():
    def build(b):
        b.free('B', 0, 0).free('C', 1, 0)
        b.op('op_k', 'number.free', {'min': num(0.5), 'max': num(3)}, [('number', 'k', 'number')])
        b.doc['inputs']['k'] = number_input(1)
        b.op('op_j', 'number.free', {'min': num(2), 'max': num(2)}, [('number', 'j', 'number')])
        b.doc['inputs']['j'] = number_input(2)
        b.segment('s', 'B', 'C')
        for n in ('k', 'j'):
            b.op('op_X' + n, 'point.on_path', {'path': ref('s')}, [('point', 'X' + n, 'point')])
        b.op('op_d', 'segment.from_point_length', {'start': ref('B'), 'length': ref('k')},
             [('segment', 'd', 'segment'), ('end', 'D', 'point')])
        b.op('op_e', 'segment.from_point_length', {'start': ref('B'), 'length': ref('j')},
             [('segment', 'e', 'segment'), ('end', 'E', 'point')])
        b.op('op_g', 'locus.of_point', {'trace': ref('D'), 'mover': ref('k')}, [('locus', 'g', 'locus')])
        b.op('op_h', 'locus.of_point', {'trace': ref('E'), 'mover': ref('j')}, [('locus', 'h', 'locus')])
    _ev, v = values(doc_of(build))
    assert v['g']['range'] == [0.5, 3.0] and v['g']['points'][0] == [0.5, 0.0]
    assert v['h'] == 'empty_range'


def test_locus_reasons():
    def build(b):
        segment_locus(b)
        b.free('F', 1, 1)
        b.midpoint('N', 'A', 'F')
        b.op('op_f', 'locus.of_point', {'trace': ref('N'), 'mover': ref('F')}, [('locus', 'f', 'locus')])
        b.op('op_n', 'locus.of_point', {'trace': ref('A'), 'mover': ref('P')}, [('locus', 'n', 'locus')])
        b.op('op_u', 'number.free', {}, [('number', 'u', 'number')])
        b.doc['inputs']['u'] = number_input(1)
        b.op('op_z', 'locus.of_point', {'trace': ref('M'), 'mover': ref('u')}, [('locus', 'z', 'locus')])
    ev = native.evaluate(doc_of(build))
    assert (ev.elements['f']['state'], ev.elements['f']['reason']) == ('unsupported', 'unsupported_signature')
    assert (ev.elements['n']['state'], ev.elements['n']['reason']) == ('undefined', 'not_dependent')
    assert (ev.elements['z']['state'], ev.elements['z']['reason']) == ('unsupported', 'unsupported_signature')


def test_locus_null_samples_and_classic_breaks():
    def build(b):
        b.free('O', 0, 0).free('R', 2, 0).free('B', -3, -1).free('C', 3, -1)
        b.circle('c', 'O', 'R').segment('s', 'B', 'C')
        b.op('op_P', 'point.on_path', {'path': ref('s')}, [('point', 'P', 'point')])
        b.doc['inputs']['P'] = path_input(0.5)
        b.op('op_v', 'line.perpendicular', {'point': ref('P'), 'base': ref('s')}, [('line', 'v', 'line')])
        b.op('op_X', 'intersect.line_circle', {'line': ref('v'), 'circle': ref('c')},
             [('first', 'X', 'point')])
        b.op('op_g', 'locus.of_point', {'trace': ref('X'), 'mover': ref('P')}, [('locus', 'g', 'locus')])
    doc = doc_of(build)
    _ev, v = values(doc)
    pts = v['g']['points']
    assert pts[0] is None and pts[-1] is None and pts[128] is not None
    construction, names = bridge.build_construction(doc)
    construction.rebuild(full=True)
    curve = construction.objectByName(names.by_id['g']).data
    assert curve.breaks is None and len(curve.points) == sum(p is not None for p in pts)


def test_locus_runs_break_on_nulls_and_far_neighbours_and_close():
    value = {'points': [[0, 0], [0.1, 0], None, [0.3, 0], [5, 0], [5.1, 0]], 'closed': False}
    points, breaks = bridge.locus_runs(value, 1.0)
    assert breaks == [2, 3] and len(points) == 5
    ring = {'points': [[1, 0], [0, 1], [-1, 0], [0, -1]], 'closed': True}
    points, breaks = bridge.locus_runs(ring, 10.0)
    assert breaks == [] and points[-1] == points[0] and len(points) == 5


def test_locus_is_deterministic_and_fast():
    doc = doc_of(segment_locus)
    first = native.canonical_json(native.evaluate(doc).elements)
    start = time.perf_counter()
    again = native.canonical_json(native.evaluate(doc).elements)
    elapsed = time.perf_counter() - start
    assert first == again
    assert elapsed < 0.15


# ── «Команды»: a pair in the side slot ───────────────────────────────────

def test_altitude_of_a_pair_through_commands():
    from animageo.native.commands import parse_commands
    result = parse_commands('A = (-2, 3)\nB = (0, 0)\nC = (4, 0)\nh, H, x = Высота(A, BC)', document_id='doc')
    assert [i.code for i in result.issues if i.severity == 'error'] == []
    data = result.document.data
    hidden = [o for o in data['operations'].values() if o['op'] == 'line.by_points']
    assert len(hidden) == 1
    ev = native.evaluate(data)
    by_name = {e['displayName']: e['id'] for e in data['elements'].values() if e.get('displayName')}
    assert ev.elements[by_name['x']]['value']['a'] == [0.0, 0.0]
