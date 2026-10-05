"""1.9.0a2: recipes v1, apply_condition, release_condition,
condition_candidates, shape_conditions (plan L3 §3.5–§3.6)."""
import copy

import pytest

from animageo import native
from animageo.native.conditions.apply import (SHAPES, apply_condition, condition_candidates, release_condition,
                                              shape_conditions)
from animageo.native.conditions.recipes import forms, recipes
from animageo.native.sampling import check_general
from tests.native.conftest import DocBuilder

BOUNDS = (-6, -4, 6, 4)


def P(x):
    return {'ref': x}


def pr(p, q):
    return {'pair': [p, q]}


def L(p, q):
    return {'len': pr(p, q)}


def angle(a, b, c):
    return {'angle': [P(a), P(b), P(c)]}


def base():
    b = DocBuilder('recipes', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2).free('D', 1, -0.5)
    b.circle('k', 'A', 'B').number('n', 2.0, min=1, max=4)
    b.free('O', 4, 2.5)
    b.circle_radius('w', 'O', 0.8)
    return b.doc


CASES = [
    ('on_object', {'kind': 'on', 'point': P('C'), 'object': P('k')}, 'C'),
    ('on_line', {'kind': 'on', 'point': P('C'), 'object': pr('A', 'B')}, 'C'),
    ('length.value', {'kind': 'eq', 'left': L('A', 'C'), 'right': {'num': 5}}, 'C'),
    ('length.value', {'kind': 'eq', 'left': {'ref': 'n'}, 'right': L('C', 'A')}, 'C'),
    ('equal_length.vertex', {'kind': 'eq', 'left': L('A', 'B'), 'right': L('A', 'C')}, 'C'),
    ('equal_length.free', {'kind': 'eq', 'left': L('A', 'B'), 'right': L('C', 'D')}, 'D'),
    ('equal_length.apex', {'kind': 'eq', 'left': L('D', 'A'), 'right': L('D', 'B')}, 'D'),
    ('parallel', {'kind': 'parallel', 'a': pr('A', 'B'), 'b': pr('C', 'D')}, 'D'),
    ('perpendicular', {'kind': 'perpendicular', 'a': pr('D', 'C'), 'b': pr('B', 'A')}, 'D'),
    ('right_angle.vertex', {'kind': 'eq', 'left': angle('A', 'D', 'B'), 'right': {'deg': 90}}, 'D'),
    ('right_angle.side', {'kind': 'eq', 'left': angle('B', 'A', 'D'), 'right': {'deg': 90}}, 'D'),
    ('angle.value', {'kind': 'eq', 'left': angle('B', 'A', 'D'), 'right': {'deg': 40}}, 'D'),
    ('angle.value', {'kind': 'eq', 'left': {'deg': 125}, 'right': angle('D', 'A', 'B')}, 'D'),
    ('angle.equal', {'kind': 'eq', 'left': angle('B', 'A', 'C'), 'right': angle('A', 'B', 'D')}, 'D'),
    ('tangent', {'kind': 'tangent', 'a': pr('C', 'D'), 'b': P('w')}, 'D'),
]


def test_thirteen_recipes():
    names = [r['recipe'] for r in recipes()]
    assert len(names) == 13 and len(set(names)) == 13
    assert {c[0] for c in CASES} == set(names)


@pytest.mark.parametrize('recipe, statement, receiver', CASES, ids=[f'{c[0]}-{i}' for i, c in enumerate(CASES)])
def test_recipe_applies_and_holds_in_general(recipe, statement, receiver):
    doc = base()
    before = copy.deepcopy(doc)
    result = apply_condition(doc, {'statement': statement, 'mode': 'construct', 'source': 'panel'})
    assert result.refusal is None
    assert doc == before
    entry = result.condition
    assert entry['recipe'] == recipe and entry['receiver'] == receiver
    assert entry['receiverOrigin'] == {'op': 'point.free', 'args': {}, 'input': {'point': doc['inputs'][receiver]['value']}}
    data = result.document.data
    assert data['conditions'][-1] == entry
    assert entry['operationIds'][-1] == data['elements'][receiver]['producer']['operationId']
    for op_id in entry['operationIds'][:-1]:
        for out in data['operations'][op_id]['outputs']:
            assert data['appearance'][out['elementId']] == {'visible': False, 'role': 'aux'}
    assert native.measure_statement(result.document, statement, native.evaluate(result.document))[0] == 'passed'
    general = check_general(result.document, [entry['id']])[entry['id']]
    assert general['status'] == 'passed', general
    shift = result.effects['shift']
    assert shift['elementId'] == receiver and shift['distance'] >= 0
    # releasing gives the free point back and removes the places
    released = release_condition(result.document, entry['id'], ev=native.evaluate(result.document))
    rdata = released.document.data
    assert sorted(rdata['elements']) == sorted(doc['elements'])
    assert 'conditions' not in rdata
    assert rdata['operations'][rdata['elements'][receiver]['producer']['operationId']]['op'] == 'point.free'
    assert rdata['inputs'][receiver]['value'] == pytest.approx(shift['to'])
    assert [i for i in native.validate(released.document) if i.severity == 'error'] == []


def test_forms_cover_symmetries():
    st = {'kind': 'eq', 'left': angle('A', 'B', 'C'), 'right': {'deg': 30}}
    assert len(forms(st)) == 4
    st = {'kind': 'parallel', 'a': pr('A', 'B'), 'b': pr('C', 'D')}
    assert len(forms(st)) == 8 and forms(st)[0] == st


def test_refusals():
    b = DocBuilder('refuse', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2)
    b.midpoint('M', 'A', 'B')
    doc = b.doc
    st = {'kind': 'collinear', 'points': [P('A'), P('B'), P('C')]}
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'})
    assert r.refusal.code == 'unsupported_condition' and r.document.data == doc and r.condition is None
    assert r.refusal.options == [{'kind': 'keep_as_check'}, {'kind': 'manual'}]
    st = {'kind': 'eq', 'left': L('A', 'M'), 'right': {'num': 2}}
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'}, receiver='M')
    assert r.refusal.code == 'receiver_not_free'
    assert r.refusal.options[0] == {'kind': 'make_free', 'elementId': 'M'}
    st = {'kind': 'eq', 'left': L('A', 'M'), 'right': L('M', 'B')}
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'})
    assert r.refusal.code == 'receiver_is_ancestor'
    # three constraints on one point
    st1 = {'kind': 'eq', 'left': L('A', 'C'), 'right': {'num': 4}}
    st2 = {'kind': 'eq', 'left': L('B', 'C'), 'right': {'num': 4}}
    st3 = {'kind': 'on', 'point': P('C'), 'object': pr('A', 'B')}
    d1 = apply_condition(doc, {'statement': st1, 'mode': 'construct'}, receiver='C').document
    d2 = apply_condition(d1, {'statement': st2, 'mode': 'construct'}, receiver='C')
    assert d2.refusal is None
    assert d2.document.data['operations']['op_C']['op'] == 'intersect.circle_circle'
    assert check_general(d2.document)['c2']['status'] == 'passed'
    r = apply_condition(d2.document, {'statement': st3, 'mode': 'construct'}, receiver='C')
    assert r.refusal.code == 'too_many_conditions'
    # two places that do not meet now
    st4 = {'kind': 'eq', 'left': L('B', 'C'), 'right': {'num': 0.5}}
    r = apply_condition(d1, {'statement': st4, 'mode': 'construct'}, receiver='C')
    assert r.refusal.code == 'no_intersection_now'


def test_point_on_a_path_plus_a_condition_and_release_of_one_of_two():
    b = DocBuilder('two', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).segment('s', 'A', 'B').on_path('C', 's', 0.3)
    b.free('E', 0, 3)
    doc = b.doc
    st = {'kind': 'eq', 'left': L('E', 'C'), 'right': {'num': 5.5}}
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'}, receiver='C')
    assert r.refusal is None
    assert r.document.data['operations']['op_C']['op'] == 'intersect.line_circle'
    assert r.condition['receiverOrigin']['op'] == 'point.on_path'
    back = release_condition(r.document, r.condition['id'], ev=native.evaluate(r.document))
    op = back.document.data['operations']['op_C']
    assert op['op'] == 'point.on_path' and op['args']['path']['elementId'] == 's'


def test_release_without_values_restores_the_origin():
    doc = base()
    st = {'kind': 'eq', 'left': L('A', 'C'), 'right': {'num': 5}}
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'})
    back = release_condition(r.document, r.condition['id'])
    assert 'restored_origin' in back.effects['warnings']
    assert back.document.data['inputs']['C'] == doc['inputs']['C']
    assert back.effects['removed']['conditions'] == ['c1']


def test_default_receiver_is_the_last_created_candidate():
    doc = base()
    st = {'kind': 'eq', 'left': L('B', 'A'), 'right': L('B', 'C')}
    cands = condition_candidates(doc, st)
    assert [c['elementId'] for c in cands] == ['B', 'A', 'C']
    assert [c['ok'] for c in cands] == [True, True, True]
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'})
    assert r.condition['receiver'] == 'C' and r.condition['recipe'] == 'equal_length.vertex'
    r = apply_condition(doc, {'statement': st, 'mode': 'construct'}, receiver='B')
    assert r.condition['recipe'] == 'equal_length.apex'


@pytest.mark.parametrize('shape', sorted(SHAPES))
def test_shapes_hold_in_general(shape):
    n = SHAPES[shape][0]
    b = DocBuilder('shape', registry_version='1.5', bounds=BOUNDS)
    pts = [('A', -3, -2), ('B', 3, -1.5), ('C', 2.5, 2.2), ('D', -2.2, 1.8)][:n]
    for name, x, y in pts:
        b.free(name, x, y)
    b.polygon('T', *[p[0] for p in pts])
    doc = b.doc
    items = shape_conditions(doc, 'T', shape)
    assert items
    for item in items:
        r = apply_condition(doc, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                  'shapeId': 'T'}, receiver=item['receiver'])
        assert r.refusal is None, (shape, item, r.refusal)
        doc = r.document
    results = check_general(doc)
    assert all(v['status'] == 'passed' for v in results.values()), results
    assert all(c['shapeId'] == 'T' and c['source'] == 'shape' for c in doc.data['conditions'])


def test_shape_of_the_wrong_polygon_is_empty():
    b = DocBuilder('shape', registry_version='1.5', bounds=BOUNDS)
    b.free('A', 0, 0).free('B', 1, 0).free('C', 0, 1)
    b.polygon('T', 'A', 'B', 'C')
    assert shape_conditions(b.doc, 'T', 'square') == []
    assert shape_conditions(b.doc, 'A', 'isosceles') == []
    assert shape_conditions(b.doc, 'T', 'circle') == []
