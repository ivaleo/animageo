"""Operations of registry 1.4 added in 1.8.1a5: angles and numbers, measures."""
import math

import pytest

from animageo import native
from animageo.native.kernel import ops as kernel_ops
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, num, number_input, point_input, ref, ref_list

PI = math.pi


def B(name='l2a5'):
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


def angle_number(b, el_id, value=None, **params):
    b.op('op_' + el_id, 'number.angle', {k: num(v) for k, v in params.items()}, [('number', el_id, 'number')])
    if value is not None:
        b.doc['inputs'][el_id] = {'kind': 'angle', 'value': value}
    return b


def measure(b, el_id, op, **args):
    return b.op('op_' + el_id, 'measure.' + op, {k: ref(v) for k, v in args.items()},
                [('number', el_id, 'number')])


# ── contract ─────────────────────────────────────────────────────────────

def test_contract_table():
    reg = registry()

    def summary(op):
        r = reg.get(op)
        return ([(i['slot'], i['type']) for i in r['inputs']],
                [(p['slot'], p.get('unit'), p.get('optional', False)) for p in r['params']],
                [(o['slot'], o['type']) for o in r['outputs']],
                r['undefined'], [c['id'] for c in r['checks']], r.get('free'), r['orientation'], r['status'])

    assert summary('angle.between_lines') == (
        [('first', 'linear'), ('second', 'linear')], [], [('angle', 'angle')],
        ['zero_length', 'parallel', 'coincident', 'upstream'], ['sides'], None, 'convex', 'stable')
    assert summary('angle.between_vectors') == (
        [('first', 'vector'), ('second', 'vector')], [], [('angle', 'angle')],
        ['zero_length', 'upstream'], ['sides'], None, 'ccw_first_to_second', 'beta')
    assert summary('angle.by_size') == (
        [('vertex', 'point'), ('a', 'point'), ('size', 'number')], [], [('angle', 'angle'), ('point', 'point')],
        ['coincident_points', 'upstream'], ['rotation'], None, 'ccw_from_a', 'stable')
    assert summary('number.angle') == (
        [], [('min', 'angle', True), ('max', 'angle', True), ('step', 'angle', True)], [('number', 'number')],
        ['invalid_parameter', 'upstream'], [], {'kind': 'angle'}, None, 'stable')
    inputs = {'length': [('of', 'measurable')], 'distance': [('point', 'point'), ('to', 'figure')],
              'area': [('of', 'bounded')], 'perimeter': [('of', 'bounded')], 'angle': [('angle', 'angle')],
              'radius': [('of', 'round')], 'circumference': [('circle', 'circle')]}
    for name, ins in inputs.items():
        assert summary('measure.' + name) == (ins, [], [('number', 'number')], ['upstream'], [], None, None,
                                              'stable')
    assert reg.families['measurable'] == ['segment', 'vector', 'polyline', 'arc']
    assert reg.families['bounded'] == ['polygon', 'circle', 'sector']
    assert reg.families['figure'] == ['point'] + reg.families['path'][:5] + ['arc', 'sector', 'polyline']


# ── angles ───────────────────────────────────────────────────────────────

class TestAngleBetweenLines:
    def doc(self, a=(-4, 0), q=(4, 0), c=(0, -3), d=(3, 3), second='segment'):
        b = B().free('A', *a).free('Q', *q).free('C', *c).free('D', *d)
        b.line('l', 'A', 'Q')
        if second == 'segment':
            b.segment('s', 'C', 'D')
        else:
            b.ray('s', 'C', 'D')
        b.op('op_t', 'angle.between_lines', {'first': ref('l'), 'second': ref('s')}, [('angle', 't', 'angle')])
        b.op('op_u', 'angle.between_lines', {'first': ref('s'), 'second': ref('l')}, [('angle', 'u', 'angle')])
        return b.doc

    def test_counterclockwise_from_the_first(self):
        e = ev(self.doc())
        t = value(e['t'])
        size = math.atan2(2, 1)                      # d2 = (3, 6) / |…|
        assert close(t['vertex'], [1.5, 0.0]) and abs(t['size'] - size) < 1e-12
        assert t['a0'] == 0.0 and abs(t['a1'] - size) < 1e-12
        assert value(e['u']) == t                    # the same convex angle, from the clockwise side

    def test_obtuse_runs_from_the_other_line(self):
        e = ev(self.doc(d=(-3, 3)))                  # d2 = (−1, 2)/√5: d1 × d2 > 0, obtuse
        t = value(e['t'])
        assert abs(t['size'] - math.atan2(2, -1)) < 1e-12 and t['a0'] == 0.0
        e = ev(self.doc(c=(0, 3), d=(3, -3)))        # d2 = (1, −2)/√5: d1 × d2 < 0 → from d2
        t = value(e['t'])
        assert abs(t['size'] - math.atan2(2, 1)) < 1e-12
        assert abs(t['a0'] - (2 * PI - math.atan2(2, 1))) < 1e-12 and abs(t['a1'] - 2 * PI) < 1e-12

    def test_vertex_on_the_carriers(self):
        e = ev(self.doc(c=(6, 2), d=(7, 5), second='ray'))   # the ray points away from the line
        t = value(e['t'])
        assert abs(t['vertex'][1]) < 1e-12 and abs(t['vertex'][0] - (6 - 2 / 3)) < 1e-12
        all_passed(self.doc(c=(6, 2), d=(7, 5), second='ray'))

    @pytest.mark.parametrize('c, d, why', [((-4, -2), (4, -2), 'parallel'), ((-1, 0), (2, 0), 'coincident'),
                                           ((1, 1), (1, 1), 'zero_length')])
    def test_degenerate(self, c, d, why):
        e = ev(self.doc(c=c, d=d))
        assert reason(e['t']) == why and reason(e['u']) == why

    def test_checks(self):
        all_passed(self.doc())
        all_passed(self.doc(c=(0, 3), d=(3, -3)))


class TestAngleBetweenVectors:
    def doc(self, a=(0, 0), q=(4, 0), c=(1, 1), d=(1, 4)):
        b = B().free('A', *a).free('Q', *q).free('C', *c).free('D', *d)
        b.vector('u', 'A', 'Q')
        b.vector('w', 'C', 'D')
        b.op('op_t', 'angle.between_vectors', {'first': ref('u'), 'second': ref('w')}, [('angle', 't', 'angle')])
        b.op('op_r', 'angle.between_vectors', {'first': ref('w'), 'second': ref('u')}, [('angle', 'r', 'angle')])
        return b.doc

    def test_counterclockwise_at_the_start(self):
        e = ev(self.doc())
        t = value(e['t'])
        assert t == {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': PI / 2, 'size': PI / 2}
        r = value(e['r'])
        assert r['vertex'] == [1.0, 1.0] and abs(r['size'] - 3 * PI / 2) < 1e-12 and abs(r['a0'] - PI / 2) < 1e-12

    def test_opposite_and_zero(self):
        assert abs(value(ev(self.doc(c=(1, 1), d=(-3, 1)))['t'])['size'] - PI) < 1e-12
        e = ev(self.doc(d=(1, 1)))
        assert reason(e['t']) == 'zero_length' and reason(e['r']) == 'zero_length'

    def test_checks(self):
        all_passed(self.doc(d=(5, -2)))


class TestAngleBySize:
    def doc(self, size=0.8, v=(0, 0), a=(3, 0)):
        b = B().free('V', *v).free('A', *a)
        b.number('alpha', size)
        b.op('op_t', 'angle.by_size', {'vertex': ref('V'), 'a': ref('A'), 'size': ref('alpha')},
             [('angle', 't', 'angle'), ('point', 'T', 'point')])
        return b.doc

    def test_positive(self):
        e = ev(self.doc(PI / 2))
        assert close(xy(e['T']), (0, 3), 1e-15)
        assert value(e['t']) == {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': PI / 2, 'size': PI / 2}

    def test_negative_runs_from_the_image(self):
        e = ev(self.doc(-PI / 2))
        assert close(xy(e['T']), (0, -3), 1e-15)
        t = value(e['t'])
        assert abs(t['a0'] - 3 * PI / 2) < 1e-12 and abs(t['size'] - PI / 2) < 1e-12
        assert abs(t['a1'] - 2 * PI) < 1e-12

    @pytest.mark.parametrize('alpha, size', [(4.0, 4.0), (7.0, 7.0 - 2 * PI), (-7.0, 7.0 - 2 * PI),
                                             (2 * PI, 0.0)])
    def test_reduced_into_a_turn(self, alpha, size):
        t = value(ev(self.doc(alpha))['t'])
        assert abs(t['size'] - size) < 1e-12 and 0 <= t['size'] < 2 * PI

    def test_literal_size_and_coincident(self):
        b = B().free('V', 1, 1).free('A', 1, 1)
        b.op('op_t', 'angle.by_size', {'vertex': ref('V'), 'a': ref('A'), 'size': num(1.0)},
             [('angle', 't', 'angle'), ('point', 'T', 'point')])
        e = ev(b.doc)
        assert reason(e['t']) == 'coincident_points' and reason(e['T']) == 'coincident_points'
        assert value(ev(b.doc, {'A': point_input(3, 1)})['T'])['y'] > 1

    @pytest.mark.parametrize('alpha', [0.8, -1.2, 4.0, -5.0])
    def test_checks(self, alpha):
        all_passed(self.doc(alpha, v=(-1, 2), a=(3, 3)))


class TestNumberAngle:
    def doc(self, value=None, **params):
        return angle_number(B(), 'n', value, **params).doc

    def test_input_and_default(self):
        assert value(ev(self.doc(1.25))['n']) == {'value': 1.25, 'unit': 'angle'}
        doc = self.doc()                                  # the angle input is optional
        assert native.validate(doc) == []
        assert value(ev(doc)['n']) == {'value': 0.0, 'unit': 'angle'}

    def test_clamp_and_invalid(self):
        assert value(ev(self.doc(3.0, max=PI / 2))['n'])['value'] == PI / 2
        assert value(ev(self.doc(-1.0, min=0.0))['n'])['value'] == 0.0
        assert reason(ev(self.doc(1.0, min=2.0, max=1.0))['n']) == 'invalid_parameter'
        assert reason(ev(self.doc(1.0, step=0.0))['n']) == 'invalid_parameter'

    def test_a_number_input_is_refused(self):
        doc = self.doc()
        doc['inputs']['n'] = number_input(1.0)
        assert [i.code for i in native.validate(doc)] == ['type_mismatch']

    def test_drives_a_rotation(self):
        b = angle_number(B().free('V', 0, 0).free('A', 2, 0), 'n', PI)
        b.op('op_t', 'angle.by_size', {'vertex': ref('V'), 'a': ref('A'), 'size': ref('n')},
             [('angle', 't', 'angle'), ('point', 'T', 'point')])
        assert close(xy(ev(b.doc)['T']), (-2, 0), 1e-15)


# ── measures ─────────────────────────────────────────────────────────────

class TestMeasures:
    def doc(self):
        b = B().free('A', 0, 0).free('Q', 3, 0).free('C', 3, 4).free('O', 0, 0).free('R', 2, 0).free('S', 0, 2)
        b.segment('s', 'A', 'C')
        b.vector('v', 'Q', 'C')
        b.op('op_w', 'polyline.by_points', {'points': ref_list('A', 'Q', 'C')}, [('polyline', 'w', 'polyline')])
        b.op('op_k', 'arc.center_two_points', {'center': ref('O'), 'a': ref('R'), 'b': ref('S')},
             [('arc', 'k', 'arc')])
        b.op('op_t', 'sector.center_two_points', {'center': ref('O'), 'a': ref('R'), 'b': ref('S')},
             [('sector', 't', 'sector')])
        b.polygon('g', 'A', 'Q', 'C')
        b.circle('c', 'O', 'R')
        b.angle('ang', 'R', 'O', 'S')
        for el, of in (('Ls', 's'), ('Lv', 'v'), ('Lw', 'w'), ('Lk', 'k')):
            measure(b, el, 'length', of=of)
        for el, of in (('Sg', 'g'), ('Sc', 'c'), ('St', 't')):
            measure(b, el, 'area', of=of)
        for el, of in (('Pg', 'g'), ('Pc', 'c'), ('Pt', 't')):
            measure(b, el, 'perimeter', of=of)
        for el, of in (('Rc', 'c'), ('Rk', 'k'), ('Rt', 't')):
            measure(b, el, 'radius', of=of)
        measure(b, 'Cc', 'circumference', circle='c')
        measure(b, 'Ma', 'angle', angle='ang')
        return b.doc

    def test_values_and_units(self):
        e = ev(self.doc())
        expected = {
            'Ls': (5.0, 'length'), 'Lv': (4.0, 'length'), 'Lw': (7.0, 'length'), 'Lk': (PI, 'length'),
            'Sg': (6.0, 'area'), 'Sc': (4 * PI, 'area'), 'St': (PI, 'area'),
            'Pg': (12.0, 'length'), 'Pc': (4 * PI, 'length'), 'Pt': (PI + 4, 'length'),
            'Rc': (2.0, 'length'), 'Rk': (2.0, 'length'), 'Rt': (2.0, 'length'),
            'Cc': (4 * PI, 'length'), 'Ma': (PI / 2, 'angle'),
        }
        for el, (v, unit) in expected.items():
            got = value(e[el])
            assert got['unit'] == unit and abs(got['value'] - v) < 1e-12, el

    def test_upstream(self):
        e = ev(self.doc(), {'R': point_input(0, 0)})
        for el in ('Lk', 'St', 'Pc', 'Rc', 'Cc', 'Ma'):
            assert reason(e[el]) == 'upstream'
        assert value(e['Ls'])['value'] == 5.0

    def test_type_mismatch(self):
        b = B().free('A', 0, 0).free('Q', 1, 0)
        b.line('l', 'A', 'Q')
        measure(b, 'm', 'length', of='l')
        assert reason(ev(b.doc)['m']) == 'type_mismatch'

    def test_no_checks(self):
        results = native.check(self.doc()).results
        assert not any(key.split(':')[0].startswith('op_') and key.split(':')[0][3:] in
                       ('Ls', 'Sg', 'Pg', 'Rc', 'Cc', 'Ma') for key in results)


class TestDistance:
    def doc(self, p=(2, 3)):
        b = B().free('P', *p).free('A', -4, -2).free('Q', 3, -2).free('C', 0, 4).free('O', -1, 0)
        b.line('l', 'A', 'Q')
        b.segment('s', 'A', 'Q')
        b.ray('r', 'Q', 'C')
        b.circle('c', 'O', 'A')
        b.polygon('g', 'A', 'Q', 'C')
        for el, to in (('Dp', 'C'), ('Dl', 'l'), ('Ds', 's'), ('Dr', 'r'), ('Dc', 'c'), ('Dg', 'g')):
            measure(b, el, 'distance', point='P', to=to)
        return b.doc

    def test_point_line_and_parts(self):
        e = ev(self.doc((7, -6)))
        assert abs(value(e['Dp'])['value'] - math.hypot(7, 10)) < 1e-12
        assert abs(value(e['Dl'])['value'] - 4) < 1e-12
        assert abs(value(e['Ds'])['value'] - math.hypot(4, 4)) < 1e-12      # to the end Q
        assert abs(value(e['Dr'])['value'] - math.hypot(4, 4)) < 1e-12      # to the origin Q
        rc = math.hypot(3, 2)
        assert abs(value(e['Dc'])['value'] - (math.hypot(8, 6) - rc)) < 1e-12

    def test_inside_the_circle_and_on_the_polygon(self):
        e = ev(self.doc((-1, 0)))
        assert abs(value(e['Dc'])['value'] - math.hypot(3, 2)) < 1e-12
        e = ev(self.doc((0, -2)))
        assert value(e['Dg'])['value'] == 0.0 and value(e['Ds'])['value'] == 0.0


# ── checks catch a wrong value ───────────────────────────────────────────

@pytest.mark.parametrize('make, op_name, key, shift', [
    (lambda: TestAngleBetweenLines().doc(), 'angle.between_lines', 'op_t:sides',
     lambda r: dict(r, angle=dict(r['angle'], a0=r['angle']['a0'] + 0.3))),
    (lambda: TestAngleBetweenLines().doc(), 'angle.between_lines', 'op_t:sides',
     lambda r: dict(r, angle=dict(r['angle'], vertex=[r['angle']['vertex'][0], 0.5]))),
    (lambda: TestAngleBetweenVectors().doc(d=(5, -2)), 'angle.between_vectors', 'op_t:sides',
     lambda r: dict(r, angle=dict(r['angle'], a1=r['angle']['a1'] + 0.3))),
    (lambda: TestAngleBySize().doc(0.8), 'angle.by_size', 'op_t:rotation',
     lambda r: dict(r, point={'x': r['point']['x'] + 0.5, 'y': r['point']['y']})),
    (lambda: TestAngleBySize().doc(-0.8), 'angle.by_size', 'op_t:rotation',
     lambda r: dict(r, angle=dict(r['angle'], a0=r['angle']['a0'] + 0.3, a1=r['angle']['a1'] + 0.3))),
])
def test_a5_checks_catch_a_wrong_value(monkeypatch, make, op_name, key, shift):
    doc = make()
    assert native.check(doc).results[key] == 'passed'
    _patched(monkeypatch, op_name, shift)
    assert native.check(doc).results[key] == 'failed'


def test_bridge_numbers_of_measures():
    pytest.importorskip('numpy')
    from animageo.native.kernel import bridge
    for v in ({'value': 2.5, 'unit': 'length'}, {'value': 6.0, 'unit': 'area'}, {'value': 1.0, 'unit': 'angle'}):
        assert bridge.from_classic('number', bridge.to_classic('number', v)) == v


# ── registry: like outputs and the structural repeat ─────────────────────

class TestStructuralRepeat:
    def doc(self):
        b = B().free('A', 0, 0).free('Q', 4, 0).free('C', 0, 3).free('M', 1, 1)
        b.polygon('g', 'A', 'Q', 'C')
        b.op('op_h', 'transform.reflect_point', {'obj': ref('g'), 'point': ref('M')},
             [('image', 'h', 'polygon'), ('vertex.3', 'H3', 'point')])
        b.op('op_j', 'transform.reflect_point', {'obj': ref('h'), 'point': ref('A')},
             [('image', 'j', 'polygon'), ('side.2', 'J2', 'segment')])
        b.op('op_s', 'transform.reflect_point', {'obj': ref('A'), 'point': ref('M')}, [('image', 'S', 'point')])
        return b.doc

    def test_slots_and_types(self):
        reg = registry()
        doc = native.load(self.doc())
        record = reg.get('transform.reflect_point')
        args = doc.operations['op_j']['args']
        assert reg.output_slots(record, args, doc) == ['image', 'side.1', 'side.2', 'side.3', 'vertex.1',
                                                       'vertex.2', 'vertex.3']
        assert reg.output_type(record, 'image', args, doc) == 'polygon'
        assert reg.output_type(record, 'vertex.4', args, doc) is None
        assert reg.output_type(record, 'image', doc.operations['op_s']['args'], doc) == 'point'
        assert reg.output_slots(record, doc.operations['op_s']['args'], doc) == ['image']
        assert reg.output_type(record, 'image') == 'transformable'          # no arguments: the declared type
        assert reg.vertex_count(doc, 'g') == 3 and reg.vertex_count(doc, 'j') == 3
        assert reg.vertex_count(doc, 'A') == 0 and reg.vertex_count(doc, 'nope') == 0
        assert reg.vertex_count(None, 'g') == 0
        assert reg.vertex_count({'operations': doc.operations, 'elements': doc.elements}, 'h') == 3

    def test_evaluate_and_validate(self):
        doc = self.doc()
        assert native.validate(doc) == []
        e = ev(doc)
        assert close(xy(e['H3']), (2, -1)) and value(e['J2'])['a'] == [2.0, -2.0]
        doc['operations']['op_h']['outputs'].append({'slot': 'vertex.4', 'elementId': 'H4'})
        doc['elements']['H4'] = {'id': 'H4', 'type': 'point', 'displayName': 'H4',
                                 'producer': {'operationId': 'op_h', 'slot': 'vertex.4'}}
        assert [i.code for i in native.validate(doc)] == ['unknown_slot']
        assert reason(ev(doc)['H4']) == 'schema'

    def test_image_type_must_match(self):
        doc = self.doc()
        doc['elements']['S']['type'] = 'segment'
        assert 'type_mismatch' in [i.code for i in native.validate(doc)]
        assert reason(ev(doc)['S']) == 'type_mismatch'

    def test_a_cycle_counts_nothing(self):
        doc = self.doc()
        doc['operations']['op_h']['args']['obj'] = ref('j')              # h ← j ← h
        loaded = native.load(doc, strict=False)
        assert registry().vertex_count(loaded, 'j') == 0
        assert reason(ev(doc)['j']) in ('cycle', 'schema')

    def test_like_stays_out_of_older_hashes(self):
        from animageo.native.registry import signature, signature_hash
        record = registry().get('transform.translate')
        assert signature(record)['outputs'][0] == {'slot': 'image', 'type': 'transformable', 'repeat': None,
                                                   'like': 'obj'}
        assert 'like' not in signature(registry().get('polygon.by_points'))['outputs'][0]
        plain = dict(record, outputs=[dict(o) for o in record['outputs']])
        del plain['outputs'][0]['like']
        assert signature_hash(plain) != record['signatureHash']


# ── transformations ──────────────────────────────────────────────────────

OBJECTS = (('A', 'point'), ('s', 'segment'), ('r', 'ray'), ('l', 'line'), ('v', 'vector'), ('c', 'circle'),
           ('k', 'arc'), ('t', 'sector'), ('g', 'polygon'))


def transform_doc(op, extra_args, setup, free=()):
    b = B().free('A', 1, 0).free('Q', 3, 0).free('C', 1, 2).free('O', 0, 0)
    for el, x, y in free:
        b.free(el, x, y)
    b.segment('s', 'A', 'Q')
    b.ray('r', 'A', 'C')
    b.line('l', 'Q', 'C')
    b.vector('v', 'A', 'C')
    b.circle('c', 'O', 'A')
    b.op('op_k', 'arc.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('C')}, [('arc', 'k', 'arc')])
    b.op('op_t', 'sector.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('C')},
         [('sector', 't', 'sector')])
    b.polygon('g', 'A', 'Q', 'C')
    setup(b)
    for obj, type_ in OBJECTS:
        outs = [('image', obj + '1', type_)]
        if type_ == 'polygon':
            outs += [(f'side.{j}', f'p{j}', 'segment') for j in (1, 2, 3)]
            outs += [(f'vertex.{j}', f'P{j}', 'point') for j in (1, 2, 3)]
        b.op('op_' + obj + '1', op, dict(extra_args, obj=ref(obj)), outs)
    return b.doc


class TestTransforms:
    def translate(self):
        return transform_doc('transform.translate', {'vector': ref('u')}, lambda b: b.vector('u', 'U1', 'U2'),
                             free=(('U1', 0, 0), ('U2', 2, 1)))

    def rotate(self, alpha=PI / 2):
        return transform_doc('transform.rotate', {'angle': num(alpha), 'center': ref('O')}, lambda b: None)

    def mirror(self):
        return transform_doc('transform.reflect_line', {'line': ref('m')}, lambda b: b.line('m', 'O', 'X'),
                             free=(('X', 1, 0),))

    def half_turn(self):
        return transform_doc('transform.reflect_point', {'point': ref('M')}, lambda b: None, free=(('M', 2, 2),))

    def dilate(self, k=2.0):
        return transform_doc('transform.dilate', {'factor': num(k), 'center': ref('O')}, lambda b: None)

    def test_translate(self):
        e = ev(self.translate())
        assert xy(e['A1']) == (3.0, 1.0)
        assert value(e['s1']) == {'a': [3.0, 1.0], 'b': [5.0, 1.0], 'length': 2.0}
        assert value(e['c1']) == {'c': [2.0, 1.0], 'r': 1.0}
        assert value(e['k1'])['a0'] == value(e['k'])['a0'] and value(e['k1'])['c'] == [2.0, 1.0]
        assert value(e['g1'])['vertices'] == [[3.0, 1.0], [5.0, 1.0], [3.0, 3.0]]
        assert value(e['p2'])['a'] == [5.0, 1.0] and xy(e['P3']) == (3.0, 3.0)

    def test_rotate_quarter_turn(self):
        e = ev(self.rotate())
        assert close(xy(e['A1']), (0, 1), 1e-15)
        assert close(value(e['r1'])['dir'], (-1, 0), 1e-15)
        line = value(e['l1'])                   # the line through (0, 3) and (−2, 1)
        assert close(line['dir'], (-1 / math.sqrt(2), -1 / math.sqrt(2)), 1e-15)
        assert close(line['p'], (-1.5, 1.5), 1e-12)
        k = value(e['k1'])
        assert abs(k['a0'] - PI / 2) < 1e-12 and abs((k['a1'] - k['a0']) - (value(e['k'])['a1'] - value(e['k'])['a0'])) < 1e-15

    def test_reflect_line_reverses(self):
        e = ev(self.mirror())                   # the x axis
        assert close(xy(e['C1']) if 'C1' in e else xy(e['P3']), (1, -2), 1e-15)
        g = value(e['g1'])
        assert close(g['vertices'][2], (1, -2), 1e-15) and g['area'] == 2.0       # clockwise, area unsigned
        k, k0 = value(e['k1']), value(e['k'])
        # the arc from 0 to atan2(2, 1) reflects to the arc from −atan2(2, 1) to 0, counterclockwise
        assert abs(k['a0'] - (2 * PI - k0['a1'])) < 1e-12 and abs(k['a1'] - 2 * PI) < 1e-12
        assert close(value(e['v1'])['b'], (1, -2), 1e-15)

    def test_reflect_point_and_dilate(self):
        e = ev(self.half_turn())
        assert close(xy(e['A1']), (3, 4), 1e-15) and close(value(e['r1'])['dir'], (0, -1), 1e-15)
        assert abs(value(e['t1'])['a0'] - PI) < 1e-12
        e = ev(self.dilate(-2.0))
        assert close(xy(e['A1']), (-2, 0), 1e-15) and value(e['c1'])['r'] == 2.0
        assert value(e['s1'])['length'] == 4.0 and close(value(e['r1'])['dir'], (0, -1), 1e-15)
        assert value(e['g1'])['area'] == 8.0
        e = ev(self.dilate(0.0))
        assert {reason(e[el]) for el in ('A1', 'g1', 'p1', 'P3', 'k1')} == {'invalid_parameter'}

    def test_zero_length_mirror(self):
        e = ev(self.mirror(), {'X': point_input(0, 0)})
        assert reason(e['A1']) == 'coincident_points' or reason(e['A1']) == 'upstream'
        b = B().free('A', 1, 1).free('L', 0, 0)
        b.segment('m', 'L', 'L')
        b.op('op_A1', 'transform.reflect_line', {'obj': ref('A'), 'line': ref('m')}, [('image', 'A1', 'point')])
        assert reason(ev(b.doc)['A1']) == 'zero_length'

    @pytest.mark.parametrize('name', ['translate', 'rotate', 'mirror', 'half_turn', 'dilate'])
    def test_checks(self, name):
        all_passed(getattr(self, name)())

    def test_rotate_checks_any_angle(self):
        for alpha in (-2.5, 0.3, 4.0, 9.0):
            all_passed(self.rotate(alpha))
        all_passed(self.dilate(-0.5))


class TestPolygonAngles:
    def doc(self, pts):
        b = B()
        names = []
        for i, (x, y) in enumerate(pts):
            b.free(f'V{i}', x, y)
            names.append(f'V{i}')
        b.polygon('g', *names)
        b.op('op_w', 'measure.polygon_angles', {'polygon': ref('g')},
             [(f'angle.{k}', f'W{k}', 'angle') for k in range(1, len(pts) + 1)])
        return b.doc

    def sizes(self, pts):
        e = ev(self.doc(pts))
        return [value(e[f'W{k}'])['size'] for k in range(1, len(pts) + 1)]

    def test_square_either_way(self):
        ccw = [(0, 0), (2, 0), (2, 2), (0, 2)]
        assert close(self.sizes(ccw), [PI / 2] * 4)
        assert close(self.sizes(ccw[::-1]), [PI / 2] * 4)
        w1 = value(ev(self.doc(ccw))['W1'])
        assert w1['vertex'] == [0.0, 0.0] and w1['a0'] == 0.0      # from the side to vertex 2

    def test_concave_and_sum(self):
        pts = [(0, 0), (4, 0), (1, 1), (0, 4)]
        sizes = self.sizes(pts)
        assert sizes[2] > PI and abs(sum(sizes) - 2 * PI) < 1e-12
        sizes = self.sizes(pts[::-1])
        assert sizes[1] > PI and abs(sum(sizes) - 2 * PI) < 1e-12

    def test_degenerate(self):
        e = ev(self.doc([(0, 0), (1, 0), (2, 0)]))
        assert {reason(e[f'W{k}']) for k in (1, 2, 3)} == {'collinear_points'}
        e = ev(self.doc([(0, 0), (2, 0), (2, 0), (0, 2)]))
        assert [e[f'W{k}']['state'] for k in (1, 2, 3, 4)] == ['defined', 'undefined', 'undefined', 'defined']

    def test_slots_follow_the_polygon(self):
        doc = self.doc([(0, 0), (2, 0), (0, 2)])
        doc['operations']['op_w']['outputs'].append({'slot': 'angle.4', 'elementId': 'W4'})
        doc['elements']['W4'] = {'id': 'W4', 'type': 'angle', 'displayName': 'W4',
                                 'producer': {'operationId': 'op_w', 'slot': 'angle.4'}}
        assert [i.code for i in native.validate(doc)] == ['unknown_slot']

    def test_checks(self):
        all_passed(self.doc([(0, 0), (4, 0), (1, 1), (0, 4)]))
        all_passed(self.doc([(0, 4), (1, 1), (4, 0), (0, 0)]))


@pytest.mark.parametrize('make, op_name, key, shift', [
    (lambda: TestTransforms().rotate(0.7), 'transform.rotate', 'op_g1:image',
     lambda r: dict(r, **{'vertex.2': {'x': r['vertex.2']['x'] + 0.5, 'y': r['vertex.2']['y']}})),
    (lambda: TestTransforms().mirror(), 'transform.reflect_line', 'op_k1:image',
     lambda r: dict(r, image=dict(r['image'], a0=r['image']['a0'] + 0.3, a1=r['image']['a1'] + 0.3))),
    (lambda: TestTransforms().dilate(), 'transform.dilate', 'op_l1:image',
     lambda r: dict(r, image=dict(r['image'], p=[r['image']['p'][0] + 0.5, r['image']['p'][1]]))),
    (lambda: TestPolygonAngles().doc([(0, 0), (4, 0), (1, 1), (0, 4)]), 'measure.polygon_angles', 'op_w:interior',
     lambda r: dict(r, **{'angle.3': dict(r['angle.3'], a1=r['angle.3']['a1'] + 0.3)})),
])
def test_a5_transform_checks_catch_a_wrong_value(monkeypatch, make, op_name, key, shift):
    doc = make()
    assert native.check(doc).results[key] == 'passed'
    _patched(monkeypatch, op_name, shift)
    assert native.check(doc).results[key] == 'failed'
