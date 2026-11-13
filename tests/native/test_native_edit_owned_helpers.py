"""``native.edit.delete`` and the helpers an operation owns (``origin: {kind: auto, source: <operation>}``):
they go with the operation; a helper another operation still reads moves to it (the rule of the
helpers of marks of the web 1.0.55, its cases ``patch/mark-helpers-delete`` and ``mark-helpers-shared``)."""
import copy
import json
import math
from pathlib import Path

import pytest

from animageo import native
from animageo.native.edit import delete
from tests.native.ggb_synth import command, element, point
from tests.native.test_native_ggb_inline import eid, imported

CASES = json.loads((Path(__file__).with_name('fixtures') / 'owned_helpers_delete.json').read_text(encoding='utf-8'))


def _changed(before, after):
    out = set()
    for section in ('operations', 'elements'):
        a, b = before.get(section) or {}, after.get(section) or {}
        out |= {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    return out


@pytest.mark.parametrize('case', CASES['cases'], ids=lambda c: c['name'])
def test_the_cases_of_the_web(case):
    result = delete(case['document'], case['delete'])
    assert result.document.data == case['expect']['document']
    assert _changed(case['document'], result.document.data) == set(case['expect']['affected'])
    removed = set(case['document']['elements']) - set(case['expect']['document']['elements'])
    assert set(result.effects['removed']['elements']) == removed


def test_a_moved_helper_is_a_modified_element():
    [shared] = [c for c in CASES['cases'] if c['name'] == 'mark-helpers-shared']
    result = delete(shared['document'], shared['delete'])
    assert result.document.elements['h1']['origin'] == {'kind': 'auto', 'source': 'op_mk2'}
    assert 'h1' in result.effects['modified']['elements']
    assert {'X', 'h2', 'mk'} <= set(result.effects['removed']['elements'])


def test_helpers_of_an_operation_that_stays_stay():
    [shared] = [c for c in CASES['cases'] if c['name'] == 'mark-helpers-shared']
    result = delete(shared['document'], ['mk2'])
    assert set(result.document.elements) == set(shared['document']['elements']) - {'mk2'}
    for helper in ('h1', 'h2', 'X'):
        assert result.document.elements[helper]['origin'] == {'kind': 'auto', 'source': 'op_mk'}


def test_a_document_without_owned_helpers_is_unchanged_by_the_rule():
    doc = copy.deepcopy(CASES['cases'][0]['document'])
    for el in doc['elements'].values():
        el.pop('origin', None)
    result = delete(doc, ['mk'])
    assert set(result.document.elements) == set(doc['elements']) - {'mk'}


def test_a_helper_named_by_a_condition_stays_as_it_is():
    [case] = [c for c in CASES['cases'] if c['name'] == 'mark-helpers-delete']
    doc = copy.deepcopy(case['document'])
    doc['conditions'] = [{'id': 'c1', 'mode': 'check',
                          'statement': {'kind': 'parallel', 'a': {'ref': 'h2'}, 'b': {'ref': 'c'}}}]
    result = delete(doc, ['mk'])
    els = result.document.elements
    assert 'mk' not in els and 'h1' not in els
    assert els['h2']['origin'] == {'kind': 'auto', 'source': 'op_mk'}       # named: left as it is
    assert els['X']['origin'] == {'kind': 'auto', 'source': 'op_h2'}        # read by the helper that stays
    assert result.document.data['conditions'] == doc['conditions']


# -- the helpers of an import ---------------------------------------------

THETA = math.pi / 6


def test_deleting_an_imported_rotation_removes_its_formula_helpers():
    from tests.native.test_native_ggb_rotate_angle import figure_body
    doc, items = imported(figure_body())
    rotate = doc['elements'][eid(items, "I'")]['producer']['operationId']
    helpers = {h for h, el in doc['elements'].items() if (el.get('origin') or {}).get('source') == rotate}
    assert len(helpers) == 2                                    # measure.angle + number.expression
    result = delete(doc, [eid(items, "I'")])
    assert not helpers & set(result.document.elements)
    assert set(result.document.elements) == set(doc['elements']) - helpers - {eid(items, "I'")}
    assert native.validate(result.document) == []


def test_an_imported_helper_shared_by_two_objects_moves_to_the_survivor():
    # two points on the x-axis share its hidden helpers; the first owns them
    body = (command('Point', ['xAxis'], ['P']) + point('P', 3., 0.)
            + command('Point', ['xAxis'], ['R']) + point('R', -1., 0.))
    doc, items = imported(body)
    first = doc['elements'][eid(items, 'P')]['producer']['operationId']
    second = doc['elements'][eid(items, 'R')]['producer']['operationId']
    owned = {h for h, el in doc['elements'].items() if (el.get('origin') or {}).get('source') == first}
    assert owned and not any((el.get('origin') or {}).get('source') == second for el in doc['elements'].values())
    result = delete(doc, [eid(items, 'P')])
    assert eid(items, 'R') in result.document.elements
    sources = {(result.document.elements[h].get('origin') or {}).get('source') for h in owned
               if h in result.document.elements}
    assert sources and sources <= {second} | {
        op for op in result.document.operations if op != first}
    assert native.validate(result.document) == []
    assert native.evaluate(result.document).elements[eid(items, 'R')]['state'] == 'defined'
