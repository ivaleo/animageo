"""1.9.0a2: edits around conditions (plan L3 §3.6 «Правка») and the default
of an optional free input in ``redefine``."""
import pytest

from animageo import native
from animageo.native.edit import EditError
from tests.native.conftest import DocBuilder


def _segment_doc():
    b = DocBuilder('defaults', registry_version='1.4')
    b.free('A', 0, 0).free('B', 4, 0)
    b.op('op_s', 'segment.from_point_length',
         {'start': {'kind': 'ref', 'elementId': 'A'}, 'length': {'kind': 'number', 'value': 3}},
         [('segment', 's', 'segment'), ('end', 'E', 'point')])
    return b.doc


def test_redefine_takes_the_default_of_an_optional_input():
    doc = _segment_doc()
    assert [i for i in native.validate(doc) if i.severity == 'error'] == []
    new_op = {'op': 'segment.from_point_length',
              'args': {'start': {'kind': 'ref', 'elementId': 'B'}, 'length': {'kind': 'number', 'value': 2}}}
    result = native.redefine(doc, 'op_s', new_op)
    assert 's' not in result.document.data['inputs']          # no record: the default applies
    assert result.document.data['operations']['op_s']['args'] == new_op['args']
    ev = native.evaluate(result.document)
    assert ev.elements['E']['state'] == 'defined'


def test_redefine_still_refuses_an_input_on_another_output():
    doc = _segment_doc()
    new_op = {'op': 'segment.from_point_length',
              'args': {'start': {'kind': 'ref', 'elementId': 'A'}, 'length': {'kind': 'number', 'value': 3}}}
    with pytest.raises(EditError) as err:
        native.redefine(doc, 'op_s', new_op, inputs={'E': {'kind': 'angle', 'value': 1}})
    assert [i.code for i in err.value.issues] == ['input_not_free']


# ── delete and redefine around conditions ───────────────────────────────

from animageo.native.conditions.apply import apply_condition  # noqa: E402

BOUNDS = (-6, -4, 6, 4)


def _with_condition():
    b = DocBuilder('edit', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -3, -2).free('B', 3, -2).free('C', 0.5, 2).free('D', 2, 3)
    b.segment('ac', 'A', 'C').midpoint('M', 'B', 'C')
    st = {'kind': 'eq', 'left': {'len': {'pair': ['A', 'B']}}, 'right': {'len': {'pair': ['A', 'C']}}}
    r = apply_condition(b.doc, {'statement': st, 'mode': 'construct'}, receiver='C')
    assert r.refusal is None
    return b.doc, r.document


def _errors(doc):
    return [i for i in native.validate(doc) if i.severity == 'error']


def test_deleting_a_participant_restores_the_receiver():
    before, doc = _with_condition()
    result = native.delete(doc, ['B'])
    data = result.document.data
    assert 'conditions' not in data
    assert data['operations']['op_C']['op'] == 'point.free'
    assert data['inputs']['C'] == before['inputs']['C']           # from receiverOrigin
    assert 'ac' in data['elements'] and 'M' not in data['elements']   # M used B
    assert result.effects['removed']['conditions'] == ['c1']
    assert result.effects['modified']['restoredFrom'] == ['C']
    assert not any(e.startswith(('c1_', 'mark_c1', 'aux_c1')) for e in data['elements'])
    assert _errors(result.document) == []


def test_deleting_the_receiver_removes_the_condition():
    _before, doc = _with_condition()
    result = native.delete(doc, ['C'])
    data = result.document.data
    assert 'conditions' not in data and 'C' not in data['elements']
    assert not any(e.startswith(('c1_', 'mark_c1', 'aux_c1')) for e in data['elements'])
    assert result.effects['removed']['conditions'] == ['c1']
    assert _errors(result.document) == []


def test_deleting_something_else_keeps_the_condition():
    _before, doc = _with_condition()
    result = native.delete(doc, ['D'])
    assert [c['id'] for c in result.document.data['conditions']] == ['c1']
    assert result.effects['removed']['conditions'] == []


def test_a_check_condition_goes_with_its_participant():
    b = DocBuilder('edit', registry_version='1.5', bounds=BOUNDS)
    b.free('A', 0, 0).free('B', 1, 0).free('C', 0, 1)
    b.doc['conditions'] = [{'id': 'k1', 'mode': 'check',
                            'statement': {'kind': 'collinear', 'points': [{'ref': 'A'}, {'ref': 'B'}, {'ref': 'C'}]}}]
    result = native.delete(b.doc, ['C'])
    assert 'conditions' not in result.document.data
    assert result.effects['removed']['conditions'] == ['k1']


def test_redefining_the_receiver_removes_its_conditions():
    _before, doc = _with_condition()
    result = native.redefine(doc, 'op_C', {'op': 'point.free', 'args': {}}, slot_map={'point': 'point'},
                             inputs={'C': {'kind': 'point', 'value': [1, 1]}})
    data = result.document.data
    assert 'conditions' not in data and data['operations']['op_C']['op'] == 'point.free'
    assert result.effects['removed']['conditions'] == ['c1']
    assert not any(e.startswith(('c1_', 'mark_c1', 'aux_c1')) for e in data['elements'])
    assert _errors(result.document) == []


def test_condition_cycle():
    b = DocBuilder('edit', registry_version='1.5', bounds=BOUNDS)
    b.free('A', 0, 0).free('B', 1, 0).free('C', 0, 1).free('E', 2, 2)
    b.op('op_N', 'point.free', {}, [('point', 'N', 'point')])
    b.doc['inputs']['N'] = {'kind': 'point', 'value': [3, 3]}
    # a saved construct condition whose places do not use N (made by hand)
    st = {'kind': 'eq', 'left': {'len': {'pair': ['A', 'C']}}, 'right': {'len': {'pair': ['A', 'B']}}}
    r = apply_condition(b.doc, {'statement': st, 'mode': 'construct'}, receiver='C')
    doc = r.document.data
    doc['conditions'][0]['statement'] = {'kind': 'eq', 'left': {'len': {'pair': ['A', 'C']}},
                                         'right': {'len': {'pair': ['N', 'E']}}}
    with pytest.raises(EditError) as err:
        native.redefine(doc, 'op_N', {'op': 'point.midpoint', 'args': {'a': {'kind': 'ref', 'elementId': 'C'},
                                                                      'b': {'kind': 'ref', 'elementId': 'E'}}},
                        slot_map={'point': 'point'})
    assert [i.code for i in err.value.issues] == ['condition_cycle']
