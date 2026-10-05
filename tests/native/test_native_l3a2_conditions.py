"""1.9.0a2: conditions in the document, statements, the new predicates and
the general case (plan L3 §3.1–§3.4)."""
import copy
import hashlib
import math

import pytest

from animageo import native
from animageo.native.kernel import relations as rel
from animageo.native.sampling import check_general, seed_of, trial_inputs
from tests.native.conftest import DocBuilder, path_input, ref

BOUNDS = (-6, -4, 6, 4)


def tri(doc_id='cond'):
    b = DocBuilder(doc_id, registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2)
    return b


def codes(doc):
    return sorted((i.code, i.severity) for i in native.validate(native.load(doc, strict=False)))


def P(el_id):
    return {'ref': el_id}


def pair(p, q):
    return {'pair': [p, q]}


def length(p, q):
    return {'len': pair(p, q)}


# ── document ─────────────────────────────────────────────────────────────

def test_a_document_with_conditions_marks_and_auto_marks_is_valid():
    b = tri()
    b.midpoint('M', 'A', 'B')
    b.right_mark('r', 'A', 'M', 'C')
    doc = b.doc
    doc['elements']['r']['origin'] = {'kind': 'auto', 'source': 'op_M'}
    doc['conditions'] = [{'id': 'c1', 'seq': 4, 'mode': 'check', 'source': 'panel',
                          'statement': {'kind': 'eq', 'left': length('A', 'M'), 'right': length('M', 'B')}},
                         {'id': 'c2', 'mode': 'construct', 'receiver': 'C', 'operationIds': ['op_C'],
                          'recipe': 'on_object', 'receiverOrigin': None, 'source': 'command', 'shapeId': None,
                          'statement': {'kind': 'on', 'point': P('C'), 'object': pair('A', 'B')}}]
    doc['suppressedMarks'] = [{'source': 'op_M', 'kind': 'equal_segments'}]
    doc['viewDefaults']['autoMarks'] = {'rightAngles': True, 'equalities': False}
    assert codes(doc) == []
    native.load(doc)          # strict: no schema issue


@pytest.mark.parametrize('change, expected', [
    (lambda d: d['conditions'][0]['statement'].update(left=length('A', 'Z')),
     [('condition_unknown_element', 'error')]),
    (lambda d: d['conditions'][0].update(operationIds=['op_C', 'nope']),
     [('condition_unknown_operation', 'error')]),
    (lambda d: d['conditions'][0].update(operationIds=[]), [('condition_receiver_mismatch', 'error')]),
    (lambda d: d['conditions'][0].update(statement={'kind': 'eq', 'left': {'len': P('A')}, 'right': {'num': 1}}),
     [('condition_bad_statement', 'error')]),
    (lambda d: d['conditions'][0].update(statement={'kind': 'between'}), [('condition_bad_statement', 'error')]),
    (lambda d: d['conditions'].extend(copy.deepcopy(d['conditions'][0]) | {'id': f'c{k}'} for k in (2, 3)),
     [('condition_too_many', 'error')]),
    (lambda d: d['conditions'].append(copy.deepcopy(d['conditions'][0])), [('condition_duplicate_id', 'error')]),
    (lambda d: d.update(suppressedMarks=[{'source': 'op_A', 'kind': 'circles'}]),
     [('suppressed_mark_unknown_kind', 'warning')]),
    (lambda d: d['elements']['A'].update(origin={'kind': 'auto', 'source': 'gone'}),
     [('mark_origin_unknown', 'warning')]),
])
def test_condition_issues(change, expected):
    doc = tri().doc
    doc['conditions'] = [{'id': 'c1', 'mode': 'construct', 'receiver': 'C', 'operationIds': ['op_C'],
                          'statement': {'kind': 'eq', 'left': length('A', 'C'), 'right': length('B', 'C')}}]
    assert codes(doc) == []
    change(doc)
    assert codes(doc) == expected


@pytest.mark.parametrize('bad', [
    {'conditions': {}}, {'conditions': [{'id': 'c1', 'mode': 'prove', 'statement': {}}]},
    {'conditions': [{'id': 'c1', 'mode': 'check'}]}, {'conditions': [{'id': 'c1', 'mode': 'check', 'statement': {},
                                                                      'extra': 1}]},
    {'suppressedMarks': [{'source': 'op_A'}]}, {'viewDefaults': {'bounds': list(BOUNDS), 'autoMarks': {'x': 1}}},
])
def test_condition_structure_is_a_schema_issue(bad):
    doc = tri().doc
    doc.update(bad)
    with pytest.raises(native.LoadError):
        native.load(doc)


# ── statements ───────────────────────────────────────────────────────────

def doc_ev(b):
    doc = native.load(b.doc)
    return doc, native.evaluate(doc)


def measure(b, statement):
    doc, ev = doc_ev(b)
    assert native.statement_problems(statement, doc) == []
    return native.measure_statement(doc, statement, ev)


def test_equal_value_units_and_not():
    b = tri()
    b.midpoint('M', 'A', 'B')
    assert measure(b, {'kind': 'eq', 'left': length('A', 'M'), 'right': length('M', 'B')})[0] == 'passed'
    assert measure(b, {'kind': 'eq', 'left': length('A', 'B'), 'right': {'num': 6}})[0] == 'passed'
    status, error, _ = measure(b, {'kind': 'eq', 'left': length('A', 'B'), 'right': {'num': 5}})
    assert status == 'failed' and error == pytest.approx(1.0)
    assert measure(b, {'kind': 'ne', 'left': length('A', 'B'), 'right': {'num': 5}})[0] == 'passed'
    assert measure(b, {'kind': 'ne', 'left': length('A', 'M'), 'right': length('M', 'B')})[0] == 'failed'
    # an angle: |∠ − 90°|·S
    doc, ev = doc_ev(b)
    st = {'kind': 'eq', 'left': {'angle': [P('A'), P('C'), P('B')]}, 'right': {'deg': 90}}
    status, error, _ = native.measure_statement(doc, st, ev)
    a, bb, c = (-3, -2), (3, -2), (0.5, 2)
    u, v = (a[0] - c[0], a[1] - c[1]), (bb[0] - c[0], bb[1] - c[1])
    angle = math.atan2(abs(u[0] * v[1] - u[1] * v[0]), u[0] * v[0] + u[1] * v[1])
    assert error == pytest.approx(abs(angle - math.pi / 2) * ev.tolerances.scale)
    # an expression: |AB| = 2·|AM|
    expr = {'op': '*', 'args': [{'num': 2}, length('A', 'M')]}
    assert measure(b, {'kind': 'eq', 'left': length('A', 'B'), 'right': expr})[0] == 'passed'


def test_object_statements_with_pairs_and_elements():
    b = tri()
    b.midpoint('M', 'A', 'B').line('l', 'A', 'B').circle('k', 'M', 'A')
    b.op('op_h', 'triangle.altitude', {'vertex': ref('C'), 'side': ref('l')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    assert measure(b, {'kind': 'perpendicular', 'a': P('h'), 'b': pair('A', 'B')})[0] == 'passed'
    assert measure(b, {'kind': 'parallel', 'a': P('l'), 'b': pair('B', 'A')})[0] == 'passed'
    assert measure(b, {'kind': 'on', 'point': P('H'), 'object': P('l')})[0] == 'passed'
    assert measure(b, {'kind': 'on', 'point': P('C'), 'object': P('k')})[0] == 'failed'
    assert measure(b, {'kind': 'collinear', 'points': [P('A'), P('H'), P('B')]})[0] == 'passed'
    assert measure(b, {'kind': 'tangent', 'a': pair('A', 'C'), 'b': P('k')})[0] == 'failed'
    assert measure(b, {'kind': 'coincident', 'points': [P('M'), P('M')]})[0] == 'passed'
    assert measure(b, {'kind': 'coincident', 'points': [P('H'), P('M')]})[0] == 'failed'
    assert measure(b, {'kind': 'concurrent', 'lines': [pair('A', 'B'), pair('B', 'C'), pair('C', 'A')]})[0] == 'failed'
    assert measure(b, {'kind': 'concyclic', 'points': [P('A'), P('B'), P('C'), P('M')]})[0] == 'failed'
    # a statement on undefined elements is inconclusive; a wrong type unsupported
    doc, ev = doc_ev(b)
    assert native.measure_statement(doc, {'kind': 'parallel', 'a': P('A'), 'b': P('l')}, ev)[0] == 'unsupported'


def test_congruent():
    b = tri()
    b.free('D', 0, 0).free('E', 6, 0).free('F', 3.5, 4)
    b.segment('s', 'A', 'B').segment('t', 'D', 'E')
    b.polygon('T', 'A', 'B', 'C').polygon('U', 'F', 'E', 'D')      # same triangle, moved, other order
    b.circle('k', 'A', 'B').circle('m', 'D', 'E')
    assert measure(b, {'kind': 'congruent', 'a': P('s'), 'b': P('t')})[0] == 'passed'
    assert measure(b, {'kind': 'congruent', 'a': pair('A', 'B'), 'b': pair('D', 'E')})[0] == 'passed'
    assert measure(b, {'kind': 'congruent', 'a': P('k'), 'b': P('m')})[0] == 'passed'
    assert measure(b, {'kind': 'congruent', 'a': P('T'), 'b': P('U')})[0] == 'passed'
    b.free('G', 1, 1)
    b.polygon('V', 'D', 'E', 'G')
    assert measure(b, {'kind': 'congruent', 'a': P('T'), 'b': P('V')})[0] == 'failed'
    b.free('J', 0, 3)
    b.polygon('Q', 'D', 'E', 'F', 'J')
    assert measure(b, {'kind': 'congruent', 'a': P('T'), 'b': P('Q')})[0] == 'failed'


def test_statement_problems_and_compiler():
    doc = native.load(tri().doc)
    assert native.statement_problems({'kind': 'on', 'point': P('A'), 'object': pair('A', 'A')}, doc)
    assert native.statement_problems({'kind': 'eq', 'left': {'ref': 'A'}, 'right': {'num': 1}}, doc)
    assert native.statement_problems({'kind': 'collinear', 'points': [P('A'), P('B')]}, doc)
    assert native.statement_problems({'kind': 'eq', 'left': {'fn': 'sqrt', 'args': []}, 'right': {'num': 1}}, doc)
    assert native.statement_checks(doc, {'kind': 'ne', 'left': {'num': 1}, 'right': {'num': 2}}) == \
        [{'predicate': 'not', 'args': [{'predicate': 'equal_value', 'args': [{'num': 1}, {'num': 2}]}]}]
    assert native.statement_checks(doc, {'kind': 'on', 'point': P('A'), 'object': pair('B', 'C')}) == \
        [{'predicate': 'incident', 'args': ['A', {'pair': ['B', 'C']}]}]


def test_relation_lists_what_holds():
    b = tri()
    b.line('l', 'A', 'B').free('D', -1, 1).free('E', 5, 1).line('m', 'D', 'E')
    doc, ev = doc_ev(b)
    assert native.relation(doc, 'l', 'm', ev) == ['parallel']
    assert native.relation(doc, 'A', 'l', ev) == ['incident']
    assert native.relation(doc, 'A', 'A', ev) == ['coincident']


def test_new_predicates_in_relations():
    b = tri()
    b.segment('s', 'A', 'B').midpoint('M', 'A', 'B')
    report = native.check(b.doc, relations=[{'id': 'x', 'predicate': 'on_object', 'args': ['M', 's']},
                                            {'id': 'y', 'predicate': 'coincident', 'args': ['M', 'M']},
                                            {'id': 'z', 'predicate': 'congruent', 'args': ['s', 's']}])
    assert [report.results[f'relation:{k}'] for k in 'xyz'] == ['passed'] * 3


# ── the general case ─────────────────────────────────────────────────────

def test_seed_and_generator_contract():
    digest = hashlib.sha256(b'doc:c1').hexdigest()
    assert seed_of('doc', 'c1') == int(digest[:16], 16)
    rng = rel.SplitMix64(1)
    assert rng.next_u64() == 0x910A2DEC89025CC1          # SplitMix64 reference value of seed 1
    rng = rel.SplitMix64(7)
    specs = [('A', 'point', {}), ('t', 'pathParameter', {'lo': 0.0, 'hi': 1.0}), ('k', 'number', {}),
             ('n', 'number', {'min': 1.0, 'max': 3.0})]
    values = {'A': {'kind': 'point', 'value': [0, 0]}, 't': path_input(0.5), 'k': {'kind': 'number', 'value': 2.0},
              'n': {'kind': 'number', 'value': 2.0}}
    out = trial_inputs(specs, values, rng, 50, 50, 10.0, (-6, -4, 6, 4))
    check = rel.SplitMix64(7)
    rho, phi = math.sqrt(check.random()), 2 * math.pi * check.random()
    assert out['A']['value'] == [5 * rho * math.cos(phi), 5 * rho * math.sin(phi)]
    assert out['t']['value'] == check.random()
    assert out['k']['value'] == 2.0 * (1 + check.random() - 0.5)
    assert out['n']['value'] == 1.0 + check.random() * 2.0


def test_general_case_passed_failed_and_reproducible():
    b = tri('general')
    b.midpoint('M', 'A', 'B')
    doc = b.doc
    doc['conditions'] = [
        {'id': 'half', 'mode': 'check', 'statement': {'kind': 'eq', 'left': length('A', 'M'), 'right': length('M', 'B')}},
        {'id': 'iso', 'mode': 'check', 'statement': {'kind': 'eq', 'left': length('A', 'C'), 'right': length('B', 'C')}},
    ]
    doc['inputs']['C'] = {'kind': 'point', 'value': [0.0, 2.0]}       # isosceles now, not in general
    first = check_general(doc)
    assert first == check_general(copy.deepcopy(doc))
    assert first['half']['status'] == 'passed' and first['half']['passed'] == 50
    iso = first['iso']
    assert iso['status'] == 'failed' and iso['error'] == 0.0
    assert iso['counterexample']['trial'] == 1 and set(iso['counterexample']['inputs']) == {'A', 'B', 'C'}
    assert iso['seed'] == seed_of('general', 'iso')
    # level 1 decides
    doc['inputs']['C'] = {'kind': 'point', 'value': [1.0, 2.0]}
    level1 = check_general(doc, ['iso'])['iso']
    assert level1['status'] == 'failed' and level1['counterexample'] == {'trial': 0, 'inputs': {}}
    assert level1['trials'] == 0 and level1['seed'] is None


def test_general_case_inconclusive_and_marks():
    b = tri('marks')
    b.midpoint('M', 'A', 'B')
    b.segment('s', 'A', 'M').segment('t', 'M', 'B')
    b.equal_segments('q', 's', 't')
    b.number('k', 0.5, min=-1.0, max=1.0)
    b.circle_radius('c', 'C', 'k').on_path('T', 'c', 1.0)
    doc = b.doc
    result = check_general(doc)
    assert result['op_q']['status'] == 'passed'
    r = check_general(doc, [('par', {'kind': 'parallel', 'a': pair('A', 'B'), 'b': pair('A', 'C')})])['par']
    assert r['status'] == 'failed'
    # the circle is undefined whenever k < 0: about half of the trials
    r = check_general(doc, [('on', {'kind': 'on', 'point': P('T'), 'object': P('c')})])['on']
    assert r['undefined'] > 10 and r['failed'] == 0 and r['status'] == 'inconclusive'
    with pytest.raises(ValueError):
        check_general(doc, ['nope'])


def test_general_case_on_a_path_and_a_slider():
    b = tri('path')
    b.segment('s', 'A', 'B')
    b.on_path('P', 's', 0.3)
    b.number('k', 1.0, min=0.5, max=2.0)
    b.circle_radius('c', 'P', 'k')
    doc = b.doc
    st = {'kind': 'on', 'point': P('P'), 'object': P('s')}
    r = check_general(doc, [('on', st)])['on']
    assert r['status'] == 'passed'
    st2 = {'kind': 'eq', 'left': {'ref': 'k'}, 'right': {'num': 1}}
    r2 = check_general(doc, [('k1', st2)])['k1']
    assert r2['status'] == 'failed' and r2['counterexample']['trial'] == 1
