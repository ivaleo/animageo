"""1.9.0a2: automatic marks (plan L3 §3.7)."""
import pytest

from animageo import native
from animageo.native.conditions.apply import apply_condition
from animageo.native.conditions.marks import add_auto_marks, auto_marks, auto_sources, mark_table
from animageo.native.sampling import check_general
from tests.native.conftest import DocBuilder

BOUNDS = (-6, -4, 6, 4)


def R(x):
    return {'kind': 'ref', 'elementId': x}


def tri():
    b = DocBuilder('marks', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2)
    b.segment('s', 'A', 'B')
    return b


def marks_of(result):
    return [op for op in result.operations if op['op'].startswith('mark.')]


def _args(op):
    if op['op'] == 'mark.right_angle':
        return tuple(op['args'][k]['elementId'] for k in ('a', 'vertex', 'b'))
    slot = 'segments' if op['op'] == 'mark.equal_segments' else 'angles'
    return [i['elementId'] for i in op['args'][slot]['items']], op['args']['count']['value']


def _clean(result):
    assert [i for i in native.validate(result.document) if i.severity == 'error'] == []
    data = result.document.data
    for el_id in result.elements:
        origin = data['elements'][el_id]['origin']
        assert origin['kind'] == 'auto'
        op = data['operations'][data['elements'][el_id]['producer']['operationId']]
        hidden = data.get('appearance', {}).get(el_id) == {'visible': False, 'role': 'aux'}
        assert hidden == (not op['op'].startswith('mark.'))
    statuses = check_general(result.document, [m['id'] for m in marks_of(result)])
    assert all(v['status'] == 'passed' for v in statuses.values()), statuses


def test_table():
    table = mark_table()
    assert table['format'] == 'animageo-auto-marks/v1'
    assert set(table['ops']) == {'triangle.altitude', 'point.projection', 'line.perpendicular', 'circle.diameter',
                                 'line.tangents_from_point', 'point.midpoint', 'triangle.median',
                                 'triangle.bisector', 'line.angle_bisector'}


def test_altitude_marks_the_far_end():
    b = tri()
    b.op('op_h', 'triangle.altitude', {'vertex': R('C'), 'side': R('s')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    r = add_auto_marks(b.doc, ['op_h'])
    (mark,) = marks_of(r)
    assert _args(mark) == ('C', 'H', 'A')          # H is at x = 0.5: A is farther
    assert mark['seq'] == 1 and r.document.data['elements'][mark['outputs'][0]['elementId']]['origin'] == \
        {'kind': 'auto', 'source': 'op_h'}
    _clean(r)


def test_altitude_tie_takes_b():
    b = DocBuilder('marks', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0, 2).segment('s', 'A', 'B')
    b.op('op_h', 'triangle.altitude', {'vertex': R('C'), 'side': R('s')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    assert _args(marks_of(add_auto_marks(b.doc, ['op_h']))[0]) == ('C', 'H', 'B')


def test_projection_needs_a_visible_segment():
    b = tri()
    b.projection('H', 'C', 's')
    assert auto_marks(b.doc, ['op_H']) == []
    b.segment('ch', 'C', 'H')
    r = add_auto_marks(b.doc, ['op_H'])
    assert _args(marks_of(r)[0]) == ('C', 'H', 'A')
    _clean(r)
    b.doc['appearance'] = {'ch': {'visible': False}}
    assert auto_marks(b.doc, ['op_H']) == []


def test_perpendicular_needs_a_visible_intersection():
    b = tri()
    b.perpendicular('p', 'C', 's')
    assert auto_marks(b.doc, ['op_p']) == []
    b.intersect('H', 'p', 's')
    r = add_auto_marks(b.doc, ['op_p'])
    assert _args(marks_of(r)[0]) == ('C', 'H', 'A')
    _clean(r)


def test_perpendicular_through_a_point_of_the_base_has_no_mark():
    b = tri()
    b.on_path('P', 's', 0.4).perpendicular('p', 'P', 's').intersect('H', 'p', 's')
    assert auto_marks(b.doc, ['op_p']) == []


def test_thales_circle_marks_every_point_on_it():
    b = tri()
    b.op('op_k', 'circle.diameter', {'a': R('A'), 'b': R('B')}, [('circle', 'k', 'circle'), ('center', 'O', 'point')])
    b.on_path('P', 'k', 1.0).on_path('Q', 'k', 2.0)
    b.doc['appearance'] = {'Q': {'visible': False}}
    r = add_auto_marks(b.doc, ['op_k'])
    assert [_args(m) for m in marks_of(r)] == [('A', 'P', 'B')]
    _clean(r)


def test_tangents_need_a_visible_center():
    b = tri()
    b.free('O', 3, 2).circle_radius('w', 'O', 1.0).free('P', -2, 2)
    b.op('op_t', 'line.tangents_from_point', {'point': R('P'), 'circle': R('w')},
         [('tangent.1', 't1', 'line'), ('tangent.2', 't2', 'line'), ('touch.1', 'T1', 'point'), ('touch.2', 'T2', 'point')])
    r = add_auto_marks(b.doc, ['op_t'])
    assert [_args(m) for m in marks_of(r)] == [('P', 'T1', 'O'), ('P', 'T2', 'O')]
    _clean(r)
    b.doc['appearance'] = {'O': {'visible': False}}
    assert auto_marks(b.doc, ['op_t']) == []


def test_midpoint_and_median_mark_halves():
    b = tri()
    b.midpoint('M', 'A', 'B').segment('am', 'A', 'M')
    r = add_auto_marks(b.doc, ['op_M'])
    (mark,) = marks_of(r)
    segs, count = _args(mark)
    assert segs[0] == 'am' and count == 1                 # an existing segment is reused
    assert r.document.data['appearance'][segs[1]] == {'visible': False, 'role': 'aux'}
    _clean(r)
    b = tri()
    b.op('op_m', 'triangle.median', {'vertex': R('C'), 'side': R('s')},
         [('median', 'm', 'segment'), ('midpoint', 'K', 'point')])
    r = add_auto_marks(b.doc, ['op_m'])
    assert len(marks_of(r)) == 1
    _clean(r)


def test_bisectors_mark_equal_angles():
    b = tri()
    b.op('op_b', 'triangle.bisector', {'vertex': R('C'), 'side': R('s')},
         [('bisector', 'l', 'segment'), ('foot', 'F', 'point')])
    r = add_auto_marks(b.doc, ['op_b'])
    (mark,) = marks_of(r)
    assert len(_args(mark)[0]) == 2
    _clean(r)
    ev = native.evaluate(r.document)
    for angle_id in _args(mark)[0]:
        assert ev.elements[angle_id]['value']['size'] < 3.15   # convex now
    b = tri()
    b.angle_bisector('l', 'A', 'C', 'B')
    r = add_auto_marks(b.doc, ['op_l'])
    assert len(marks_of(r)) == 1
    _clean(r)


def test_count_classes():
    b = tri()
    b.free('D', -3, 3).free('E', 1, 3)          # |DE| = 4 ≠ |AB| = 6
    b.midpoint('M', 'A', 'B').midpoint('N', 'D', 'E')
    b.free('F', -5, -3).free('G', 1, -3).midpoint('K', 'F', 'G')      # |FG| = 6 = |AB|
    r = add_auto_marks(b.doc, ['op_M', 'op_N', 'op_K'])
    assert [_args(m)[1] for m in marks_of(r)] == [1, 2, 1]
    b.free('P', -5, 0).free('Q', -4, 0).midpoint('L', 'P', 'Q')
    b.free('U', -5, 1).free('V', -2, 1).midpoint('W', 'U', 'V')
    r = add_auto_marks(b.doc, ['op_M', 'op_N', 'op_L', 'op_W'])
    assert [_args(m)[1] for m in marks_of(r)] == [1, 2, 3, 3]
    assert r.warnings == ['mark_classes_exhausted']


def test_suppressed_and_idempotent():
    b = tri()
    b.midpoint('M', 'A', 'B')
    b.doc['suppressedMarks'] = [{'source': 'op_M', 'kind': 'equal_segments'}]
    assert auto_marks(b.doc, ['op_M']) == []
    del b.doc['suppressedMarks']
    r = add_auto_marks(b.doc, ['op_M'])
    assert auto_marks(r.document, ['op_M']) == []
    with pytest.raises(ValueError):
        auto_marks(b.doc, ['nope'])


def test_id_factory():
    b = tri()
    b.midpoint('M', 'A', 'B')
    names = iter(['o1', 'e1', 'o2', 'e2', 'o3', 'e3'])
    ops = auto_marks(b.doc, ['op_M'], id_factory=lambda kind, hint: next(names))
    assert [op['id'] for op in ops] == ['o1', 'o2', 'o3']


CONDITIONS = [
    ({'kind': 'eq', 'left': {'len': {'pair': ['A', 'B']}}, 'right': {'len': {'pair': ['A', 'C']}}},
     'mark.equal_segments'),
    ({'kind': 'eq', 'left': {'angle': [{'ref': 'A'}, {'ref': 'C'}, {'ref': 'B'}]}, 'right': {'deg': 90}},
     'mark.right_angle'),
    ({'kind': 'perpendicular', 'a': {'pair': ['A', 'C']}, 'b': {'pair': ['A', 'B']}}, 'mark.right_angle'),
    ({'kind': 'eq', 'left': {'angle': [{'ref': 'B'}, {'ref': 'A'}, {'ref': 'C'}]},
      'right': {'angle': [{'ref': 'A'}, {'ref': 'B'}, {'ref': 'D'}]}}, 'mark.equal_angles'),
    ({'kind': 'parallel', 'a': {'pair': ['A', 'B']}, 'b': {'pair': ['C', 'D']}}, None),
]


@pytest.mark.parametrize('statement, mark', CONDITIONS)
def test_conditions_get_their_marks(statement, mark):
    b = tri()
    b.free('D', -2, 1.5)
    r = apply_condition(b.doc, {'statement': statement, 'mode': 'construct'})
    assert r.refusal is None
    data = r.document.data
    auto = [e for e, el in data['elements'].items() if el.get('origin', {}).get('source') == r.condition['id']]
    ops = [data['operations'][data['elements'][e]['producer']['operationId']]['op'] for e in auto]
    assert [o for o in ops if o.startswith('mark.')] == ([mark] if mark else [])
    assert set(auto) <= set(r.effects['added']['elements'])
    assert all(v['status'] == 'passed' for v in check_general(r.document).values())
    assert r.condition['id'] in auto_sources(r.document) or mark is None
    plain = apply_condition(b.doc, {'statement': statement, 'mode': 'construct'}, marks=False)
    assert not any(el.get('origin') for el in plain.document.data['elements'].values())


# ── steps and describe with conditions and marks ───────────────────────────

def test_condition_step_and_marks_in_the_step_of_their_source():
    from animageo.native.conditions.apply import shape_conditions
    b = DocBuilder('steps', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2).polygon('T', 'A', 'B', 'C')
    doc = b.doc
    for item in shape_conditions(doc, 'T', 'isosceles'):
        doc = apply_condition(doc, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                    'shapeId': 'T'}, receiver=item['receiver']).document
    steps = native.steps(doc)
    assert [(s.id, s.kind) for s in steps] == [('given', 'given'), ('condition:c1', 'condition'), ('op:op_T', 'op')]
    cond = steps[1]
    assert cond.conditionIds == ['c1'] and 'op_C' in cond.operationIds and 'op_mark_c1' in cond.operationIds
    assert 'mark_c1' in cond.elementIds and 'c1_m' in cond.auxElementIds
    lines = native.describe(doc)
    assert lines == ['1. Дано: точки A, B.',
                     '2. Ставим C на серединном перпендикуляре к AB: |CA| = |CB|; отмечаем равные отрезки CA и CB.',
                     '3. Строим треугольник ABC.']
    valued = native.describe(doc, values=True)
    assert valued[1].startswith('2. Ставим C на серединном перпендикуляре к AB: |CA| = |CB| (|CA| = 5; |CB| = 5)')


def test_marks_of_an_operation_join_its_step_and_values():
    b = tri()
    b.op('op_h', 'triangle.altitude', {'vertex': R('C'), 'side': R('s')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    doc = add_auto_marks(b.doc, ['op_h']).document
    step = next(s for s in native.steps(doc) if 'op_h' in s.operationIds)
    assert step.operationIds == ['op_h', 'op_mark_op_h']
    lines = native.describe(doc, values=True, precision=1)
    assert lines[-1] == '3. Проводим высоту h из вершины C к стороне s (|CH| = 4); отмечаем прямой угол CHA.'


def test_a_mark_that_needs_a_later_point_stays_a_step():
    b = tri()
    b.op('op_k', 'circle.diameter', {'a': R('A'), 'b': R('B')}, [('circle', 'k', 'circle'), ('center', 'O', 'point')])
    b.on_path('P', 'k', 1.0)
    doc = add_auto_marks(b.doc, ['op_k']).document
    ids = [s.id for s in native.steps(doc)]
    assert ids.index('op:op_mark_op_k') > ids.index('op:op_P')


def test_describe_values_of_angles_and_numbers():
    b = tri()
    b.angle('g', 'B', 'A', 'C').number('n', 1.25)
    lines = native.describe(b.doc, values=True)
    assert any('∠BAC = ' in line and '°' in line for line in lines)
    assert any('n = 1,25' in line for line in lines)
