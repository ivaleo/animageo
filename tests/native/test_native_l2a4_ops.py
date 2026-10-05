"""Operations of registry 1.4 (L2 stage 4): points, lines, circles, arcs and
sectors, polygons, the arc filter, the free angle input and the new path frames."""
import math

import pytest

from animageo import native
from animageo.native.kernel import paths
from animageo.native.kernel import ops as kernel_ops
from animageo.native.registry import FREE_INPUT_DEFAULTS, REPEAT_MAX, free_slot, registry, repeat_count
from tests.native.conftest import DocBuilder, num, number_input, point_input, ref, ref_list

PI = math.pi
SQ2 = math.sqrt(2)


def B(name='l2a4'):
    return DocBuilder(name, registry_version='1.4')


def ev(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements


def value(record):
    assert record['state'] == 'defined', record
    return record['value']


def reason(record):
    assert record['state'] != 'defined', record
    return record['reason']


def xy(record):
    v = value(record)
    return v['x'], v['y']


def close(a, b, eps=1e-12):
    a = list(a)
    b = list(b)
    return len(a) == len(b) and all(abs(p - q) <= eps for p, q in zip(a, b))


def all_passed(doc, inputs=None):
    results = native.check(doc, inputs=inputs).results
    assert results and set(results.values()) == {'passed'}, results


def _patched(monkeypatch, op_name, shift):
    original = kernel_ops.IMPLEMENTATIONS[op_name]
    monkeypatch.setitem(kernel_ops.IMPLEMENTATIONS, op_name, lambda args, ctx: shift(original(args, ctx)))


# ── registry: repeat by a param, the free slot, the angle default ────────

class TestRegistry:
    @pytest.mark.parametrize('v, n', [(3, 3), (3.0, 3), (1, 1), (REPEAT_MAX, REPEAT_MAX), (REPEAT_MAX + 1, 0),
                                      (0, 0), (2.5, 0), (-3, 0), (True, 0), ('3', 0), (None, 0),
                                      (math.nan, 0), (math.inf, 0)])
    def test_repeat_count(self, v, n):
        assert repeat_count(v) == n

    def args(self, n):
        return {'a': ref('A'), 'b': ref('Q'), 'n': num(n)}

    def test_regular_slots_follow_n(self):
        reg = registry()
        record = reg.get('polygon.regular')
        assert reg.output_slots(record, self.args(5)) == \
            ['polygon'] + [f'side.{i}' for i in range(1, 6)] + [f'vertex.{i}' for i in range(1, 6)]
        assert reg.output_slots(record, self.args(2.5)) == ['polygon']
        assert reg.output_slots(record, self.args(2)) == ['polygon', 'side.1', 'side.2', 'vertex.1', 'vertex.2']
        assert reg.output_type(record, 'vertex.5', self.args(5)) == 'point'
        assert reg.output_type(record, 'vertex.6', self.args(5)) is None
        assert reg.output_type(record, 'side.9') == 'segment'          # no args: any index

    def test_a_slot_beyond_n_is_a_type_mismatch(self):
        b = B().free('A', 0, 0).free('Q', 1, 0)
        b.op('op_p', 'polygon.regular', self.args(3), [('polygon', 'p', 'polygon'), ('vertex.4', 'V4', 'point')])
        codes = {i.code for i in native.validate(b.doc)}
        assert 'producer_mismatch' in codes or 'type_mismatch' in codes or 'unknown_slot' in codes

    def test_free_slot(self):
        reg = registry()
        assert free_slot(reg.get('segment.from_point_length')) == 'segment'
        assert free_slot(reg.get('point.on_path')) == 'point'
        assert free_slot(reg.get('point.midpoint')) is None
        assert FREE_INPUT_DEFAULTS == {'angle': {'kind': 'angle', 'value': 0.0}}

    def test_ray_by_vector_is_beta(self):
        assert registry().get('ray.by_vector')['status'] == 'beta'


# ── the free angle input ─────────────────────────────────────────────────

class TestAngleInput:
    def doc(self, theta=None):
        b = B('angle_input').free('A', 1, 2)
        b.number('len', 5)
        b.op('op_s', 'segment.from_point_length', {'start': ref('A'), 'length': ref('len')},
             [('segment', 's', 'segment'), ('end', 'E', 'point')])
        if theta is not None:
            b.doc['inputs']['s'] = {'kind': 'angle', 'value': theta}
        return b.doc

    def test_absent_input_is_zero(self):
        e = ev(self.doc())
        assert xy(e['E']) == (6.0, 2.0)
        assert value(e['s']) == {'a': [1.0, 2.0], 'b': [6.0, 2.0], 'length': 5.0}
        assert native.validate(self.doc()) == []

    def test_given_input_turns_the_segment(self):
        assert close(xy(ev(self.doc(PI / 2))['E']), (1.0, 7.0))
        assert close(xy(ev(self.doc(), {'s': {'kind': 'angle', 'value': PI}})['E']), (-4.0, 2.0))

    def test_zero_and_negative_length(self):
        doc = self.doc(0.3)
        assert xy(ev(doc, {'len': number_input(0)})['E']) == (1.0, 2.0)
        assert reason(ev(doc, {'len': number_input(-1)})['s']) == 'invalid_parameter'

    def test_only_the_first_slot_takes_the_input(self):
        doc = self.doc()
        with pytest.raises(ValueError, match='not a free input'):
            native.evaluate(doc, inputs={'E': {'kind': 'angle', 'value': 1.0}})
        doc['inputs']['E'] = {'kind': 'angle', 'value': 1.0}
        assert [i.code for i in native.validate(doc)] == ['input_not_free']

    def test_wrong_kind_and_shape(self):
        with pytest.raises(ValueError, match='input of'):
            native.evaluate(self.doc(), inputs={'s': number_input(1.0)})
        with pytest.raises(ValueError, match='input of'):
            native.evaluate(self.doc(), inputs={'s': {'kind': 'angle', 'value': math.inf}})
        doc = self.doc()
        doc['inputs']['s'] = {'kind': 'number', 'value': 1.0}
        assert [i.code for i in native.validate(doc)] == ['type_mismatch']

    def test_schema_takes_an_angle_input(self):
        doc = self.doc(0.25)
        assert native.validate(doc) == []
        doc['inputs']['s'] = {'kind': 'angle', 'value': 'up'}
        assert [i.code for i in native.validate(doc)] == ['schema']
        doc['inputs']['s'] = {'kind': 'angle', 'value': 1.0, 'branch': 1}
        assert [i.code for i in native.validate(doc)] == ['schema']

    def test_check(self):
        all_passed(self.doc(1.1))

    def test_commands_print_and_parse_the_angle(self):
        from animageo.native.commands import parse_commands, print_commands
        printed = print_commands(self.doc())
        assert printed.issues == [] or all(i.code == 'ambiguous_name' for i in printed.issues)
        assert 'segment.from_point_length(A, len, 0)' in printed.text
        parsed = parse_commands('A = (1, 2)\ns, E = segment.from_point_length(A, 5, 0.6)', document_id='doc')
        assert parsed.issues == []
        angles = [v for v in parsed.document.inputs.values() if v['kind'] == 'angle']
        assert angles == [{'kind': 'angle', 'value': 0.6}]
        parsed = parse_commands('A = (1, 2)\ns, E = segment.from_point_length(A, 5)', document_id='doc')
        assert [v for v in parsed.document.inputs.values() if v['kind'] == 'angle'] == \
            [{'kind': 'angle', 'value': 0.0}]


# ── points ───────────────────────────────────────────────────────────────

class TestPoints:
    def divide_doc(self):
        b = B('divide').free('A', 0, 0).free('Q', 6, 3)
        b.number('m', 2).number('n', 1)
        b.op('op_P', 'point.divide', {'a': ref('A'), 'b': ref('Q'), 'm': ref('m'), 'n': ref('n')},
             [('point', 'P', 'point')])
        return b.doc

    @pytest.mark.parametrize('m, n, expected', [(2, 1, (4.0, 2.0)), (1, 1, (3.0, 1.5)), (0, 1, (0.0, 0.0)),
                                                (1, 0, (6.0, 3.0)), (1, 2, (2.0, 1.0))])
    def test_divide(self, m, n, expected):
        e = ev(self.divide_doc(), {'m': number_input(m), 'n': number_input(n)})
        assert close(xy(e['P']), expected)

    @pytest.mark.parametrize('m, n', [(-1, 1), (1, -1), (0, 0)])
    def test_divide_invalid(self, m, n):
        assert reason(ev(self.divide_doc(), {'m': number_input(m), 'n': number_input(n)})['P']) == 'invalid_parameter'

    def test_center_of_round_elements(self):
        b = B('center').free('O', 1, -1).free('R', 4, 3).free('A', -3, 0).free('Q', 3, 2)
        b.circle('c', 'O', 'R')
        b.op('op_s', 'arc.semicircle', {'a': ref('A'), 'b': ref('Q')}, [('arc', 's', 'arc')])
        b.op('op_t', 'sector.center_two_points', {'center': ref('O'), 'a': ref('R'), 'b': ref('Q')},
             [('sector', 't', 'sector')])
        for el, of in (('Kc', 'c'), ('Ks', 's'), ('Kt', 't')):
            b.op('op_' + el, 'point.center', {'of': ref(of)}, [('center', el, 'point')])
        e = ev(b.doc)
        assert xy(e['Kc']) == (1.0, -1.0) and xy(e['Kt']) == (1.0, -1.0)
        assert xy(e['Ks']) == (0.0, 1.0)
        all_passed(b.doc)

    def closest_doc(self, p):
        b = B('closest').free('P', *p).free('A', -4, 0).free('Q', 4, 0).free('O', 0, 0).free('U', 0, 4)
        b.segment('s', 'A', 'Q').circle('c', 'O', 'Q')
        b.op('op_k', 'arc.center_two_points', {'center': ref('O'), 'a': ref('Q'), 'b': ref('U')}, [('arc', 'k', 'arc')])
        b.op('op_w', 'polyline.by_points', {'points': ref_list('A', 'U', 'Q')}, [('polyline', 'w', 'polyline')])
        for el, path in (('Fs', 's'), ('Fc', 'c'), ('Fk', 'k'), ('Fw', 'w')):
            b.op('op_' + el, 'point.closest', {'point': ref('P'), 'path': ref(path)}, [('foot', el, 'point')])
        return b.doc

    def test_closest(self):
        e = ev(self.closest_doc((6, 3)))
        assert xy(e['Fs']) == (4.0, 0.0)                         # clamped to the end
        assert close(xy(e['Fc']), (8 / math.sqrt(5), 4 / math.sqrt(5)))
        assert close(xy(e['Fk']), (8 / math.sqrt(5), 4 / math.sqrt(5)))
        assert close(xy(e['Fw']), (3.5, 0.5))                      # on the link U → Q
        all_passed(self.closest_doc((6, 3)))

    def test_closest_on_an_arc_off_the_sweep_takes_the_nearer_end(self):
        e = ev(self.closest_doc((-1, -5)))
        assert close(xy(e['Fk']), (4.0, 0.0))
        e = ev(self.closest_doc((-5, 1)))
        assert close(xy(e['Fk']), (0.0, 4.0), 1e-12)

    def test_closest_from_the_centre(self):
        e = ev(self.closest_doc((0, 0)))
        assert close(xy(e['Fc']), (4.0, 0.0))                     # θ = 0
        assert close(xy(e['Fk']), (4.0, 0.0))                     # the start of the arc

    def at_distance_doc(self):
        b = B('at_distance').free('A', 0, 0).free('Q', 3, 4)
        b.number('d', 10)
        b.op('op_P', 'point.at_distance', {'a': ref('A'), 'b': ref('Q'), 'distance': ref('d')},
             [('point', 'P', 'point'), ('segment', 's', 'segment')])
        return b.doc

    def test_at_distance(self):
        e = ev(self.at_distance_doc())
        assert close(xy(e['P']), (6.0, 8.0))
        assert value(e['s'])['length'] == 10.0
        e = ev(self.at_distance_doc(), {'d': number_input(-5)})
        assert close(xy(e['P']), (-3.0, -4.0))
        assert value(e['s'])['length'] == 5.0
        e = ev(self.at_distance_doc(), {'Q': point_input(0, 0)})
        assert reason(e['P']) == reason(e['s']) == 'coincident_points'
        all_passed(self.at_distance_doc())


# ── lines ────────────────────────────────────────────────────────────────

class TestLines:
    def bisectors_doc(self):
        b = B('bisectors').free('A', -1, 0).free('Q', 1, 0).free('C', 0, 0).free('D', 1, 1)
        b.line('l', 'A', 'Q').line('m', 'C', 'D')
        b.op('op_b', 'line.angle_bisectors_of_lines', {'first': ref('l'), 'second': ref('m')},
             [('internal', 'bi', 'line'), ('external', 'be', 'line')])
        return b.doc

    def test_bisectors_of_crossing_lines(self):
        e = ev(self.bisectors_doc())
        bi, be = value(e['bi']), value(e['be'])
        assert close(bi['dir'], (math.cos(PI / 8), math.sin(PI / 8)))
        assert close(be['dir'], (-math.sin(PI / 8), math.cos(PI / 8)))
        assert close(bi['p'], (0.0, 0.0)) and close(be['p'], (0.0, 0.0))
        all_passed(self.bisectors_doc())

    def test_bisectors_of_an_obtuse_pair(self):
        # directions 0 and 3π/4 (q < 0): the internal bisector still halves the angle of the directions
        e = ev(self.bisectors_doc(), {'D': point_input(-1, 1)})
        assert close(value(e['bi'])['dir'], (math.cos(3 * PI / 8), math.sin(3 * PI / 8)))
        assert close(value(e['be'])['dir'], (-math.sin(3 * PI / 8), math.cos(3 * PI / 8)))

    def test_parallel_lines(self):
        e = ev(self.bisectors_doc(), {'C': point_input(-3, 2), 'D': point_input(3, 2)})
        assert close(value(e['bi'])['p'], (0.0, 1.0)) and close(value(e['bi'])['dir'], (1.0, 0.0))
        assert reason(e['be']) == 'parallel'
        e = ev(self.bisectors_doc(), {'C': point_input(3, 2), 'D': point_input(-3, 2)})
        assert reason(e['bi']) == 'parallel'
        assert close(value(e['be'])['p'], (0.0, 1.0))

    def test_coincident_lines(self):
        e = ev(self.bisectors_doc(), {'C': point_input(-5, 0), 'D': point_input(5, 0)})
        assert close(value(e['bi'])['p'], (0.0, 0.0))
        assert reason(e['be']) == 'coincident'

    def test_external_bisector(self):
        b = B('external').free('A', 1, 0).free('V', 0, 0).free('C', 0, 1)
        b.op('op_e', 'line.external_bisector', {'a': ref('A'), 'vertex': ref('V'), 'b': ref('C')},
             [('line', 'e', 'line')])
        e = ev(b.doc)
        assert close(value(e['e'])['dir'], (-1 / SQ2, 1 / SQ2))
        assert reason(ev(b.doc, {'A': point_input(0, 0)})['e']) == 'coincident_points'
        all_passed(b.doc)

    def test_ray_at_angle(self):
        b = B('at_angle').free('V', 1, 1).free('A', 3, 1)
        b.number('alpha', PI / 2)
        b.op('op_r', 'ray.at_angle', {'vertex': ref('V'), 'a': ref('A'), 'size': ref('alpha')},
             [('ray', 'r', 'ray'), ('point', 'P', 'point')])
        e = ev(b.doc)
        assert close(value(e['r'])['dir'], (0.0, 1.0)) and value(e['r'])['origin'] == [1.0, 1.0]
        assert close(xy(e['P']), (1.0, 3.0))
        e = ev(b.doc, {'alpha': number_input(-PI / 2)})
        assert close(value(e['r'])['dir'], (0.0, -1.0))
        assert reason(ev(b.doc, {'A': point_input(1, 1)})['r']) == 'coincident_points'
        all_passed(b.doc)

    def test_ray_by_vector(self):
        b = B('by_vector').free('O', 1, 2).free('A', 0, 0).free('Q', 3, 4)
        b.vector('v', 'A', 'Q')
        b.op('op_r', 'ray.by_vector', {'origin': ref('O'), 'vector': ref('v')}, [('ray', 'r', 'ray')])
        assert value(ev(b.doc)['r']) == {'origin': [1.0, 2.0], 'dir': [0.6, 0.8]}
        assert reason(ev(b.doc, {'Q': point_input(0, 0)})['r']) == 'zero_length'

    def tangents_doc(self, p=(10, 0)):
        b = B('tangents').free('O', 0, 0).free('R', 5, 0).free('P', *p)
        b.circle('c', 'O', 'R')
        b.op('op_t', 'line.tangents_from_point', {'point': ref('P'), 'circle': ref('c')},
             [('tangent.1', 't1', 'line'), ('tangent.2', 't2', 'line'), ('touch.1', 'T1', 'point'),
              ('touch.2', 'T2', 'point')])
        return b.doc

    def test_tangents_from_an_outside_point(self):
        e = ev(self.tangents_doc())
        h = 5 * math.sqrt(3) / 2
        assert close(xy(e['T1']), (2.5, -h), 1e-12) and close(xy(e['T2']), (2.5, h), 1e-12)
        d1 = value(e['t1'])['dir']
        assert close(d1, ((2.5 - 10) / math.hypot(7.5, h), -h / math.hypot(7.5, h)))
        all_passed(self.tangents_doc())

    def test_tangents_from_a_point_on_the_circle(self):
        e = ev(self.tangents_doc((3, 4)))
        assert value(e['t1'])['dir'] == [0.8, -0.6] and value(e['t2'])['dir'] == [-0.8, 0.6]
        assert xy(e['T1']) == xy(e['T2']) == (3.0, 4.0)
        assert e['t1']['detail'] == e['T2']['detail'] == {'multiplicity': 2}

    def test_tangent_one_is_continuous_onto_the_circle(self):
        on = value(ev(self.tangents_doc((3, 4)))['t1'])['dir']
        near = value(ev(self.tangents_doc((3 * 1.000001, 4 * 1.000001)))['t1'])['dir']
        assert close(on, near, 1e-2)

    def test_tangents_from_inside(self):
        e = ev(self.tangents_doc((1, 1)))
        assert {reason(e[k]) for k in ('t1', 't2', 'T1', 'T2')} == {'point_inside'}

    def test_tangent_at(self):
        b = B('tangent_at').free('O', 0, 0).free('R', 5, 0).free('P', 3, 4)
        b.circle('c', 'O', 'R')
        b.op('op_t', 'line.tangent_at', {'point': ref('P'), 'circle': ref('c')}, [('line', 't', 'line')])
        assert close(value(ev(b.doc)['t'])['dir'], (-0.8, 0.6))
        assert reason(ev(b.doc, {'P': point_input(3, 5)})['t']) == 'not_on_curve'
        all_passed(b.doc)

    def test_midline(self):
        b = B('midline').free('A', 0, 0).free('Q', 4, 0).free('C', 0, 6)
        b.segment('ab', 'A', 'Q').segment('ac', 'A', 'C')
        b.op('op_m', 'segment.midline', {'first': ref('ab'), 'second': ref('ac')},
             [('segment', 'm', 'segment'), ('mid.1', 'M1', 'point'), ('mid.2', 'M2', 'point')])
        e = ev(b.doc)
        assert value(e['m']) == {'a': [2.0, 0.0], 'b': [0.0, 3.0], 'length': math.hypot(2, 3)}
        assert xy(e['M1']) == (2.0, 0.0) and xy(e['M2']) == (0.0, 3.0)
        all_passed(b.doc)


# ── circles ──────────────────────────────────────────────────────────────

class TestCircles:
    def test_diameter(self):
        b = B('diameter').free('A', -3, 1).free('Q', 3, 1)
        b.op('op_d', 'circle.diameter', {'a': ref('A'), 'b': ref('Q')},
             [('circle', 'd', 'circle'), ('center', 'M', 'point')])
        e = ev(b.doc)
        assert value(e['d']) == {'c': [0.0, 1.0], 'r': 3.0} and xy(e['M']) == (0.0, 1.0)
        assert reason(ev(b.doc, {'Q': point_input(-3, 1)})['d']) == 'coincident_points'

    def test_center_segment(self):
        b = B('center_segment').free('O', 1, 1).free('A', 0, 0).free('Q', 3, 4)
        b.segment('s', 'A', 'Q')
        b.op('op_k', 'circle.center_segment', {'center': ref('O'), 'radius': ref('s')}, [('circle', 'k', 'circle')])
        assert value(ev(b.doc)['k']) == {'c': [1.0, 1.0], 'r': 5.0}
        assert reason(ev(b.doc, {'Q': point_input(0, 0)})['k']) == 'nonpositive_radius'

    def excircle_doc(self):
        b = B('excircle').free('A', 0, 0).free('Q', 4, 0).free('C', 0, 3)
        b.op('op_e', 'circle.excircle', {'a': ref('A'), 'b': ref('Q'), 'c': ref('C')},
             [('circle', 'e', 'circle'), ('center', 'I', 'point'), ('touch', 'T', 'point')])
        return b.doc

    def test_excircle_opposite_a(self):
        e = ev(self.excircle_doc())
        assert close(value(e['e'])['c'], (6.0, 6.0)) and abs(value(e['e'])['r'] - 6.0) < 1e-12
        assert close(xy(e['T']), (2.4, 1.2), 1e-12)               # on the side bc
        all_passed(self.excircle_doc())

    def test_excircle_of_collinear_points(self):
        e = ev(self.excircle_doc(), {'C': point_input(8, 0)})
        assert {reason(e[k]) for k in ('e', 'I', 'T')} == {'collinear_points'}


# ── arcs and sectors ─────────────────────────────────────────────────────

def _arc(e):
    v = value(e)
    return v['c'], v['r'], v['a0'], v['a1']


class TestArcs:
    def doc(self):
        b = B('arcs').free('O', 0, 0).free('A', 4, 0).free('Q', 0, 8).free('C', -4, 0)
        b.op('op_a', 'arc.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')}, [('arc', 'a', 'arc')])
        b.op('op_s', 'sector.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')},
             [('sector', 's', 'sector')])
        b.op('op_h', 'arc.semicircle', {'a': ref('C'), 'b': ref('A')}, [('arc', 'h', 'arc')])
        return b.doc

    def test_center_two_points(self):
        e = ev(self.doc())
        assert _arc(e['a']) == ([0.0, 0.0], 4.0, 0.0, PI / 2)       # b gives the direction only
        assert value(e['s']) == value(e['a'])
        e = ev(self.doc(), {'Q': point_input(0, -1)})
        assert _arc(e['a'])[3] == 1.5 * PI
        e = ev(self.doc(), {'A': point_input(0, -4), 'Q': point_input(4, 0)})
        assert _arc(e['a'])[2:] == (1.5 * PI, 2 * PI)
        assert reason(ev(self.doc(), {'Q': point_input(0, 0)})['a']) == 'coincident_points'

    def test_semicircle_is_left_of_a_to_b(self):
        assert _arc(ev(self.doc())['h']) == ([0.0, 0.0], 4.0, 0.0, PI)
        assert reason(ev(self.doc(), {'C': point_input(4, 0)})['h']) == 'coincident_points'

    def three_doc(self, a, q, c):
        b = B('three').free('A', *a).free('Q', *q).free('C', *c)
        b.op('op_a', 'arc.three_points', {'a': ref('A'), 'b': ref('Q'), 'c': ref('C')},
             [('arc', 'k', 'arc'), ('center', 'K', 'point')])
        b.op('op_s', 'sector.three_points', {'a': ref('A'), 'b': ref('Q'), 'c': ref('C')},
             [('sector', 's', 'sector')])
        return b.doc

    @pytest.mark.parametrize('a, q, c', [((4, 0), (0, 4), (-4, 0)), ((-4, 0), (0, 4), (4, 0)),
                                         ((4, 0), (0, -4), (-4, 0)), ((3, 1), (-2, 5), (1, -6))])
    def test_three_points_passes_through_b(self, a, q, c):
        doc = self.three_doc(a, q, c)
        e = ev(doc)
        center, r, a0, a1 = _arc(e['k'])
        assert 0 <= a0 < 2 * PI and a0 <= a1 <= a0 + 2 * PI
        assert paths.distance_to_path(*q, 'arc', value(e['k'])) < 1e-9
        assert value(e['s']) == value(e['k'])
        all_passed(doc)

    def test_three_points_order(self):
        assert close(_arc(ev(self.three_doc((4, 0), (0, 4), (-4, 0)))['k'])[2:], (0.0, PI))
        assert close(_arc(ev(self.three_doc((-4, 0), (0, 4), (4, 0)))['k'])[2:], (0.0, PI))
        assert close(_arc(ev(self.three_doc((4, 0), (0, -4), (-4, 0)))['k'])[2:], (PI, 2 * PI))

    def test_three_collinear_points(self):
        assert reason(ev(self.three_doc((0, 0), (1, 1), (2, 2)))['k']) == 'collinear_points'

    def on_circle_doc(self):
        b = B('on_circle').free('O', 1, 1).free('R', 4, 5).free('A', 1, 9).free('Q', 9, 1)
        b.circle('c', 'O', 'R')
        b.op('op_a', 'arc.on_circle', {'circle': ref('c'), 'a': ref('A'), 'b': ref('Q')}, [('arc', 'k', 'arc')])
        b.op('op_s', 'sector.on_circle', {'circle': ref('c'), 'a': ref('A'), 'b': ref('Q')},
             [('sector', 's', 'sector')])
        return b.doc

    def test_on_circle_keeps_the_radius(self):
        e = ev(self.on_circle_doc())
        assert _arc(e['k']) == ([1.0, 1.0], 5.0, PI / 2, 2 * PI)
        assert reason(ev(self.on_circle_doc(), {'A': point_input(1, 1)})['k']) == 'coincident_points'
        all_passed(self.on_circle_doc())

    def from_angle_doc(self):
        b = B('from_angle').free('O', 0, 0).free('A', 0, 2)
        b.number('alpha', 1.0)
        b.op('op_s', 'sector.from_angle', {'center': ref('O'), 'a': ref('A'), 'size': ref('alpha')},
             [('sector', 's', 'sector')])
        return b.doc

    @pytest.mark.parametrize('alpha, a0, a1', [(1.0, PI / 2, PI / 2 + 1), (-1.0, PI / 2 - 1, PI / 2),
                                               (9.0, PI / 2, PI / 2 + 2 * PI), (-9.0, PI / 2, PI / 2 + 2 * PI),
                                               (0.0, PI / 2, PI / 2)])
    def test_from_angle(self, alpha, a0, a1):
        _c, r, got0, got1 = _arc(ev(self.from_angle_doc(), {'alpha': number_input(alpha)})['s'])
        assert r == 2.0 and close((got0, got1), (a0, a1), 1e-12)


# ── path frames of arcs, sectors and polylines ───────────────────────────

ARC = {'c': [1.0, 1.0], 'r': 2.0, 'a0': 0.0, 'a1': PI / 2}
POLY = {'vertices': [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0]], 'length': 7.0}


class TestPaths:
    def test_parameter_ranges(self):
        assert paths.parameter_range(paths.frame('arc', ARC)) == (0.0, 1.0)
        assert paths.parameter_range(paths.frame('sector', ARC)) == (0.0, 3.0)
        assert paths.parameter_range(paths.frame('polyline', POLY)) == (0.0, 2.0)
        assert paths.parameter_range(paths.frame('circle', {'c': [0, 0], 'r': 1})) == (0.0, 2 * PI)

    @pytest.mark.parametrize('t, expected', [(0.0, (3.0, 1.0)), (1.0, (1.0, 3.0)), (0.5, (1 + SQ2, 1 + SQ2)),
                                             (-1.0, (3.0, 1.0)), (2.0, (1.0, 3.0))])
    def test_arc_point_at(self, t, expected):
        p = paths.point_at(paths.frame('arc', ARC), t)
        assert close((p['x'], p['y']), expected, 1e-12)

    @pytest.mark.parametrize('t, expected', [(0.0, (3.0, 1.0)), (1.0, (1.0, 3.0)), (1.5, (1.0, 2.0)), (2.0, (1.0, 1.0)),
                                             (2.5, (2.0, 1.0)), (3.0, (3.0, 1.0)), (-0.5, (2.0, 1.0))])
    def test_sector_point_at_wraps(self, t, expected):
        p = paths.point_at(paths.frame('sector', ARC), t)
        assert close((p['x'], p['y']), expected, 1e-12)

    @pytest.mark.parametrize('t, expected', [(0.0, (0.0, 0.0)), (0.5, (2.0, 0.0)), (1.0, (4.0, 0.0)),
                                             (1.5, (4.0, 1.5)), (2.0, (4.0, 3.0)), (5.0, (4.0, 3.0)), (-1, (0.0, 0.0))])
    def test_polyline_point_at_clamps(self, t, expected):
        p = paths.point_at(paths.frame('polyline', POLY), t)
        assert (p['x'], p['y']) == expected

    @pytest.mark.parametrize('type_, value, t', [('arc', ARC, 0.3), ('sector', ARC, 0.7), ('sector', ARC, 1.25),
                                                 ('sector', ARC, 2.6), ('polyline', POLY, 0.4), ('polyline', POLY, 1.8)])
    def test_project_inverts_point_at(self, type_, value, t):
        f = paths.frame(type_, value)
        p = paths.point_at(f, t)
        assert abs(paths.project(f, p['x'], p['y'], 1e-12) - t) < 1e-12
        assert paths.distance_to_path(p['x'], p['y'], type_, value) < 1e-12

    def test_project_ties_and_corners(self):
        f = paths.frame('sector', ARC)
        assert paths.project(f, 1.0, 1.0, 1e-9) == 2.0              # the centre: end of radius 1, start of radius 2
        assert paths.project(f, 3.0, 1.0, 1e-9) == 0.0              # S0: the arc start, not t = 3
        g = paths.frame('polyline', POLY)
        assert paths.project(g, 5.0, -1.0, 1e-9) == 1.0

    def test_distances(self):
        assert abs(paths.distance_to_path(1.0, -2.0, 'arc', ARC) - math.hypot(2, 3)) < 1e-12   # nearer end S0
        assert paths.distance_to_path(1.5, 1.5, 'sector', ARC) == pytest.approx(0.5)            # to a radius
        assert paths.distance_to_path(2.0, 2.0, 'polyline', POLY) == 2.0
        assert paths.distance_to_path(1.0, 1.0, 'arc', ARC) == 2.0                              # the centre

    def test_arc_fraction(self):
        assert paths.arc_fraction(1, 1, 2, 0.0, PI / 2, 1, 1, 1e-9) == (0.0, 2.0)
        frac, d = paths.arc_fraction(1, 1, 2, 0.0, PI / 2, 1 + 3 / SQ2, 1 + 3 / SQ2, 1e-9)
        assert abs(frac - 0.5) < 1e-12 and abs(d - 1.0) < 1e-12
        # a full arc from 3π/2: the direction 0 is at a quarter of the sweep
        frac, _ = paths.arc_fraction(0, 0, 1, 1.5 * PI, 3.5 * PI, 1, 0, 1e-9)
        assert abs(frac - 0.25) < 1e-12

    def test_on_path_of_an_arc_sector_and_polyline(self):
        b = B('on_path').free('O', 1, 1).free('A', 3, 1).free('Q', 1, 5)
        b.op('op_k', 'arc.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')}, [('arc', 'k', 'arc')])
        b.op('op_t', 'sector.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')},
             [('sector', 't', 'sector')])
        b.op('op_w', 'polyline.by_points', {'points': ref_list('O', 'A', 'Q')}, [('polyline', 'w', 'polyline')])
        b.on_path('P', 'k', 0.5).on_path('S', 't', 1.5).on_path('W', 'w', 1.5)
        e = ev(b.doc)
        assert close(xy(e['P']), (1 + SQ2, 1 + SQ2)) and close(xy(e['S']), (1.0, 2.0))
        assert close(xy(e['W']), (2.0, 3.0))
        all_passed(b.doc)


# ── the arc filter and intersect.line_sector ─────────────────────────────

class TestArcFilter:
    def doc(self):
        b = B('filter').free('O', 0, 0).free('A', 4, 0).free('Q', 0, 4).free('L1', -5, 1).free('L2', 5, 1)
        b.free('O2', 4, 4).free('R2', 4, 0)
        b.op('op_k', 'arc.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')}, [('arc', 'k', 'arc')])
        b.line('l', 'L1', 'L2').line_circle('X1', 'X2', 'l', 'k')
        b.circle('c2', 'O2', 'R2').circle_circle('Y1', 'Y2', 'k', 'c2')
        return b.doc

    def test_line_circle_keeps_the_slots_of_the_carrier(self):
        e = ev(self.doc())
        assert e['X1'] == {'state': 'undefined', 'type': 'point', 'reason': 'outside_part', 'detail': {'slot': 'circle'}}
        assert close(xy(e['X2']), (math.sqrt(15), 1.0))
        all_passed(self.doc())

    def test_circle_circle(self):
        e = ev(self.doc())
        assert sorted([xy(e['Y1']), xy(e['Y2'])]) == [(0.0, 4.0), (4.0, 0.0)] or \
            all(close(p, q, 1e-12) for p, q in zip(sorted([xy(e['Y1']), xy(e['Y2'])]), [(0.0, 4.0), (4.0, 0.0)]))
        e = ev(self.doc(), {'O2': point_input(-4, -4), 'R2': point_input(-4, 0)})
        assert {e['Y1']['reason'], e['Y2']['reason']} == {'outside_part'}
        assert {e['Y1']['detail']['slot'], e['Y2']['detail']['slot']} <= {'first', 'second'}

    def sector_doc(self, l1, l2, segment=False, q=(0, 4)):
        b = B('line_sector').free('O', 0, 0).free('A', 4, 0).free('Q', *q).free('L1', *l1).free('L2', *l2)
        b.op('op_t', 'sector.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')},
             [('sector', 't', 'sector')])
        if segment:
            b.segment('l', 'L1', 'L2')
        else:
            b.line('l', 'L1', 'L2')
        b.op('op_x', 'intersect.line_sector', {'line': ref('l'), 'sector': ref('t')},
             [('arc.1', 'X1', 'point'), ('arc.2', 'X2', 'point'), ('side.1', 'Y1', 'point'), ('side.2', 'Y2', 'point')])
        return b.doc

    def test_crossing(self):
        doc = self.sector_doc((-5, 1), (5, 1))
        e = ev(doc)
        assert e['X1']['reason'] == 'outside_part' and e['X1']['detail'] == {'slot': 'sector'}
        assert close(xy(e['X2']), (math.sqrt(15), 1.0))
        assert e['Y1']['reason'] == 'parallel'
        assert close(xy(e['Y2']), (0.0, 1.0))
        all_passed(doc)

    def test_through_the_centre(self):
        # both radii meet the line at the centre (s = 0 exactly: not a fixture case)
        e = ev(self.sector_doc((-4, -4), (4, 4)))
        assert e['X1']['reason'] == 'outside_part'
        assert close(xy(e['X2']), (2 * SQ2, 2 * SQ2), 1e-12)
        assert close(xy(e['Y1']), (0.0, 0.0)) and close(xy(e['Y2']), (0.0, 0.0))

    def test_along_a_radius_and_outside(self):
        e = ev(self.sector_doc((-2, 0), (6, 0)))
        assert e['Y1']['reason'] == 'coincident'
        e = ev(self.sector_doc((-5, -1), (5, -1)))
        assert e['Y2']['reason'] == 'outside_part' and e['Y2']['detail'] == {'slot': 'sector'}

    def test_four_points_of_a_reflex_sector(self):
        doc = self.sector_doc((5, 3), (-3, -5), q=(0, -4))
        e = ev(doc)
        r7 = math.sqrt(7)
        assert close(xy(e['X1']), (1 + r7, -1 + r7), 1e-12) and close(xy(e['X2']), (1 - r7, -1 - r7), 1e-12)
        assert close(xy(e['Y1']), (2.0, 0.0), 1e-12) and close(xy(e['Y2']), (0.0, -2.0), 1e-12)
        all_passed(doc)
        assert 'op_x:incident_both' in native.check(doc).results

    def test_a_short_segment(self):
        e = ev(self.sector_doc((1, 1), (2, 1.5), segment=True))
        assert {e[k]['reason'] for k in ('X1', 'X2', 'Y1', 'Y2')} == {'outside_part'}
        assert e['Y2']['detail'] == {'slot': 'line'}


# ── polygons and polylines ───────────────────────────────────────────────

class TestPolygons:
    def vertex_doc(self):
        b = B('vertex').free('A', 0, 0).free('Q', 4, 0).free('C', 4, 3)
        b.polygon('g', 'A', 'Q', 'C').segment('s', 'A', 'C')
        b.op('op_w', 'polyline.by_points', {'points': ref_list('C', 'Q', 'A')}, [('polyline', 'w', 'polyline')])
        for el, of, k in (('G3', 'g', 3), ('G4', 'g', 4), ('G0', 'g', 0), ('Gh', 'g', 1.5), ('S2', 's', 2),
                          ('S3', 's', 3), ('W1', 'w', 1)):
            b.op('op_' + el, 'polygon.vertex', {'of': ref(of), 'k': num(k)}, [('vertex', el, 'point')])
        return b.doc

    def test_vertex(self):
        e = ev(self.vertex_doc())
        assert xy(e['G3']) == (4.0, 3.0) and xy(e['S2']) == (4.0, 3.0) and xy(e['W1']) == (4.0, 3.0)
        assert reason(e['G4']) == reason(e['S3']) == 'index_out_of_range'
        assert reason(e['G0']) == reason(e['Gh']) == 'invalid_parameter'
        all_passed(self.vertex_doc())

    def regular_doc(self, n=4, center=False):
        b = B('regular').free('A', 0, 0).free('Q', 1, 0).free('O', 0, 0)
        count = repeat_count(n)
        outs = [('polygon', 'p', 'polygon')] + [(f'side.{i}', f's{i}', 'segment') for i in range(1, count + 1)]
        outs += [(f'vertex.{i}', f'v{i}', 'point') for i in range(1, count + 1)]
        args = {'center': ref('O'), 'a': ref('Q')} if center else {'a': ref('A'), 'b': ref('Q')}
        args['n'] = num(n)
        b.op('op_p', 'polygon.regular_center' if center else 'polygon.regular', args, outs)
        return b.doc

    def test_regular_square(self):
        e = ev(self.regular_doc())
        vs = value(e['p'])['vertices']
        assert vs[0] == [0.0, 0.0] and vs[1] == [1.0, 0.0]            # vertex 1 and 2 exactly a and b
        assert close([c for v in vs for c in v], (0, 0, 1, 0, 1, 1, 0, 1), 1e-12)
        assert abs(value(e['p'])['area'] - 1.0) < 1e-12
        assert xy(e['v3']) == tuple(vs[2]) and value(e['s4'])['b'] == [0.0, 0.0]
        all_passed(self.regular_doc())

    def test_regular_clockwise_input_keeps_the_area_unsigned(self):
        e = ev(self.regular_doc(), {'A': point_input(1, 0), 'Q': point_input(0, 0)})
        vs = value(e['p'])['vertices']
        assert close([c for v in vs for c in v], (1, 0, 0, 0, 0, -1, 1, -1), 1e-12)
        assert value(e['p'])['area'] > 0

    def test_regular_center(self):
        e = ev(self.regular_doc(center=True))
        vs = value(e['p'])['vertices']
        assert close([c for v in vs for c in v], (1, 0, 0, 1, -1, 0, 0, -1), 1e-12)
        assert reason(ev(self.regular_doc(center=True), {'Q': point_input(0, 0)})['p']) == 'coincident_points'

    @pytest.mark.parametrize('n', [2, 101, 2.5, 0])
    def test_regular_invalid_n(self, n):
        doc = self.regular_doc(n)
        e = ev(doc)
        assert {reason(r) for k, r in e.items() if k in ('p',) or k[0] in 'sv' and k[1:].isdigit()} == \
            {'invalid_parameter'}
        assert native.validate(doc) == []

    def test_regular_coincident(self):
        e = ev(self.regular_doc(5), {'Q': point_input(0, 0)})
        assert reason(e['p']) == reason(e['v5']) == 'coincident_points'

    def test_parallelogram_and_centroid(self):
        b = B('parallelogram').free('A', 0, 0).free('Q', 4, 0).free('C', 5, 2)
        b.op('op_p', 'polygon.parallelogram', {'a': ref('A'), 'b': ref('Q'), 'c': ref('C')},
             [('polygon', 'p', 'polygon'), ('side.4', 'p4', 'segment'), ('vertex', 'D', 'point')])
        b.op('op_G', 'polygon.centroid', {'polygon': ref('p')}, [('centroid', 'G', 'point')])
        e = ev(b.doc)
        assert xy(e['D']) == (1.0, 2.0) and value(e['p'])['area'] == 8.0
        assert value(e['p4']) == {'a': [1.0, 2.0], 'b': [0.0, 0.0], 'length': math.sqrt(5)}
        assert close(xy(e['G']), (2.5, 1.0))
        all_passed(b.doc)
        assert reason(ev(b.doc, {'C': point_input(8, 0)})['G']) == 'collinear_points'

    def test_centroid_of_a_concave_polygon(self):
        b = B('centroid').free('A', 0, 0).free('Q', 2, 0).free('C', 2, 1).free('D', 1, 1).free('E', 1, 2).free('F', 0, 2)
        b.polygon('g', 'A', 'Q', 'C', 'D', 'E', 'F')
        b.op('op_G', 'polygon.centroid', {'polygon': ref('g')}, [('centroid', 'G', 'point')])
        assert close(xy(ev(b.doc)['G']), (5 / 6, 5 / 6), 1e-12)     # an L of three unit squares
        all_passed(b.doc)

    def test_polyline(self):
        b = B('polyline').free('A', 0, 0).free('Q', 3, 4).free('C', 3, 0)
        b.op('op_w', 'polyline.by_points', {'points': ref_list('A', 'Q', 'C')}, [('polyline', 'w', 'polyline')])
        assert value(ev(b.doc)['w']) == {'vertices': [[0.0, 0.0], [3.0, 4.0], [3.0, 0.0]], 'length': 9.0}
        all_passed(b.doc)


# ── checks catch a wrong value ───────────────────────────────────────────

def _moved(r, slot, dx=0.5):
    return dict(r, **{slot: {'x': r[slot]['x'] + dx, 'y': r[slot]['y']}})


@pytest.mark.parametrize('make, op_name, key, shift', [
    (lambda: TestPoints().divide_doc(), 'point.divide', 'op_P:ratio', lambda r: _moved(r, 'point')),
    (lambda: TestLines().tangents_doc(), 'line.tangents_from_point', 'op_t:tangent',
     lambda r: dict(r, **{'tangent.1': dict(r['tangent.1'], dir=[1.0, 0.0])})),
    (lambda: TestPolygons().regular_doc(5), 'polygon.regular', 'op_p:regular', lambda r: _moved(r, 'vertex.3')),
    (lambda: TestArcs().three_doc((4, 0), (0, 4), (-4, 0)), 'arc.three_points', 'op_a:through_all',
     lambda r: dict(r, arc=dict(r['arc'], a1=r['arc']['a1'] - 0.5))),
    (lambda: TestArcFilter().sector_doc((5, 3), (-3, -5), q=(0, -4)), 'intersect.line_sector', 'op_x:incident_both',
     lambda r: _moved(r, 'side.2')),
    (lambda: TestCircles().excircle_doc(), 'circle.excircle', 'op_e:tangent_sides',
     lambda r: dict(r, circle=dict(r['circle'], r=r['circle']['r'] + 0.5))),
])
def test_a4_checks_catch_a_wrong_value(monkeypatch, make, op_name, key, shift):
    doc = make()
    assert native.check(doc).results[key] == 'passed'
    _patched(monkeypatch, op_name, shift)
    assert native.check(doc).results[key] == 'failed'


# ── bridge values of the new types ───────────────────────────────────────

class TestBridge:
    @pytest.mark.parametrize('type_, v', [
        ('arc', {'c': [1.0, 2.0], 'r': 3.0, 'a0': 1.5, 'a1': 1.5 + 2 * PI}),
        ('sector', {'c': [0.0, 0.0], 'r': 1.0, 'a0': 6.0, 'a1': 7.0}),
        ('polyline', {'vertices': [[0.0, 0.0], [3.0, 4.0]], 'length': 5.0}),
    ])
    def test_round_trip(self, type_, v):
        pytest.importorskip('numpy')
        from animageo.native.kernel import bridge
        obj = bridge.to_classic(type_, v)
        assert bridge.from_classic(type_, obj) == v
        obj._native = None                     # without the cache: from the classic fields
        back = bridge.from_classic(type_, obj)
        assert back.keys() == v.keys()
        if type_ != 'polyline':
            assert close(back['c'], v['c']) and abs(back['r'] - v['r']) < 1e-12
            assert abs(back['a0'] - v['a0']) < 1e-12 and abs(back['a1'] - v['a1']) < 1e-12
        else:
            assert back == v

    def test_angle_input_reaches_the_command(self):
        pytest.importorskip('numpy')
        from animageo.native.kernel import bridge
        doc = TestAngleInput().doc(PI / 2)
        construction, names = bridge.build_construction(doc)
        construction.rebuild(full=True)
        end = construction.objectByName(names.by_id['E']).data
        assert close(end.coords, (1.0, 7.0))
        construction, names = bridge.build_construction(TestAngleInput().doc())
        construction.rebuild(full=True)
        assert close(construction.objectByName(names.by_id['E']).data.coords, (6.0, 2.0))
