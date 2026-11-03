"""Right-angle auto marks reuse a persisted presentation owner, not its check."""
import copy
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from animageo import native
from animageo.native.conditions.apply import apply_condition, release_condition
from animageo.native.conditions.marks import add_auto_marks
from tests.native.conftest import DocBuilder, point_input, ref


STATEMENT = {'kind': 'eq', 'left': {'angle': [{'ref': 'A'}, {'ref': 'V'}, {'ref': 'B'}]},
             'right': {'deg': 90}}


def drawing(*, angle=True, manual=False, true=False):
    b = DocBuilder('right_angle_owners', registry_version='1.5', bounds=(-4, -3, 4, 3))
    b.free('A', -2, 0).free('V', 0 if true else .5, 2 if true else 1).free('B', 2, 0)
    if angle:
        b.angle('g', 'A', 'V', 'B')
    if manual:
        b.right_mark('m', 'A', 'V', 'B')
    b.doc['appearance'] = {el: {'label': {'mode': 'none'}} for el in b.doc['elements']}
    return b


def quick(doc, *, marks=True):
    result = apply_condition(doc, {'statement': STATEMENT, 'mode': 'construct', 'source': 'panel'},
                             receiver='V', marks=marks)
    assert result.refusal is None
    assert result.condition['recipe'] == 'right_angle.vertex'
    return result


def right_marks(doc):
    data = doc.data if hasattr(doc, 'data') else doc
    return [el for el, record in data['elements'].items()
            if data['operations'][record['producer']['operationId']]['op'] == 'mark.right_angle']


def test_quick_condition_reuses_angle_and_keeps_constraint():
    b = drawing()
    before = copy.deepcopy(b.doc)
    result = quick(b.doc)
    assert right_marks(result.document) == []
    assert b.doc == before
    assert result.document.elements['g'] == before['elements']['g']
    assert result.document.data['appearance']['g'] == before['appearance']['g']
    assert native.measure_statement(result.document, STATEMENT, native.evaluate(result.document))[0] == 'passed'
    assert native.resolve_paint(result.document)['elements']['g']['angle']['right'] is True


def test_combined_plain_reflex_forced_square_owns():
    b = drawing()
    b.doc['appearance']['g']['overrides'] = {'angle_range': 'reflex', 'right_angle_marker': True}
    result = quick(b.doc)
    assert native.resolve_paint(result.document)['elements']['g']['angle']['right'] is True
    assert right_marks(result.document) == []


def test_combined_failed_right_mark_false_reflex_owns():
    b = drawing(angle=False, manual=True)
    b.doc['appearance']['m']['overrides'] = {'angle_range': 'reflex', 'right_angle_marker': False}
    assert native.check(b.doc).results['op_m:right'] == 'failed'
    result = quick(b.doc)
    paint = native.resolve_paint(result.document)['elements']['m']['angle']
    assert paint['right'] is False and paint['shownSize'] == pytest.approx(3 * 3.141592653589793 / 2)
    assert native.check(result.document).results['op_m:right'] == 'passed'
    assert right_marks(result.document) == ['m']


FIXTURE = Path(native.__file__).parent / 'parity/v1/marks/owners/right_angle.json'
CASES = json.loads(FIXTURE.read_text())['cases']


@pytest.mark.parametrize('case', CASES, ids=[c['name'] for c in CASES])
def test_shared_owner_semantics(case):
    before = copy.deepcopy(case['document'])
    ev = native.evaluate(before)
    result = add_auto_marks(before, case['sources'], ev=ev)
    projected = [{'op': op['op'], 'args': op['args'],
                  'originSource': result.document.elements[op['outputs'][0]['elementId']]['origin']['source']}
                 for op in result.operations]
    assert projected == case['expect']['newOperations'], case['reason']
    assert before == case['document']
    for group in ('elements', 'operations', 'appearance', 'conditions', 'inputs'):
        old, new = before.get(group), result.document.data.get(group)
        if isinstance(old, dict):
            assert {key: new[key] for key in old} == old
        else:
            assert new == old
    assert not [i for i in native.validate(result.document) if i.severity == 'error']
    checks = native.check(result.document).results
    for key, status in case['expect']['invariants']['assertionChecks'].items():
        assert checks[key] == status


@pytest.mark.parametrize('degenerate', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_same_call_uses_only_defined_fresh_owner(degenerate, reverse):
    result = quick(drawing(angle=False).doc, marks=False)
    doc = copy.deepcopy(result.document.data)
    circle = next(oid for oid in result.condition['operationIds']
                  if doc['operations'][oid]['op'] == 'circle.diameter')
    if degenerate:
        doc['inputs']['V']['value'] = 0.0  # V coincides with B on the diameter circle.
    sources = [result.condition['id'], circle] if reverse else [circle, result.condition['id']]
    ev = native.evaluate(doc)
    marked = add_auto_marks(doc, sources, ev=ev)
    assert len(marked.operations) == (2 if degenerate else 1)
    assert all(el not in ev.elements for el in marked.elements)
    states = native.evaluate(marked.document).elements
    assert {states[el]['state'] for el in marked.elements} == ({'undefined'} if degenerate else {'defined'})
    assert marked.document.elements[marked.elements[0]]['origin']['source'] == sources[0]


@pytest.mark.parametrize('alias_slot', ['a', 'vertex', 'b'])
def test_equal_coordinates_in_one_slot_do_not_alias_ids(alias_slot):
    b = drawing(true=True)
    original = {'a': 'A', 'vertex': 'V', 'b': 'B'}[alias_slot]
    xy = b.doc['inputs'][original]['value']
    b.free('alias', *xy)
    b.doc['operations']['op_g']['args'][alias_slot] = ref('alias')
    result = quick(b.doc)
    assert len(right_marks(result.document)) == 1


def test_nested_refs_and_other_angle_producers_do_not_claim_identity():
    doc = copy.deepcopy(next(c['document'] for c in CASES if c['name'] == 'minor'))
    ev = native.evaluate(doc)
    # Even a supplied defined record cannot turn a nested reference into a
    # direct-ref identity. add_auto_marks does not edit/revalidate the owner.
    doc['operations']['op_g']['args']['a'] = {'kind': 'list', 'items': [ref('A')]}
    assert len(add_auto_marks(doc, ['c1'], ev=ev).operations) == 1
    b = drawing()
    b.vector('u', 'V', 'A').vector('w', 'V', 'B')
    b.doc['operations']['op_g'].update(op='angle.between_vectors', args={'first': ref('u'), 'second': ref('w')})
    assert len(right_marks(quick(b.doc).document)) == 1


@pytest.mark.parametrize('owner', ['angle', 'manual', 'none'])
def test_release_and_document_undo_equivalent_preserve_owners(owner):
    before = drawing(angle=owner == 'angle', manual=owner == 'manual').doc
    undo = copy.deepcopy(before)
    result = quick(before)
    released = release_condition(result.document, result.condition['id'], ev=native.evaluate(result.document))
    assert set(released.document.elements) == set(before['elements'])
    for el in before['elements']:
        assert released.document.elements[el] == before['elements'][el]
    assert 'conditions' not in released.document.data
    assert released.document.operations['op_V']['op'] == 'point.free'
    assert native.evaluate(undo).elements == native.evaluate(before).elements
    assert quick(undo).document.data == result.document.data  # Restore document, redo the public action.


def test_other_auto_origin_and_source_precedence_survive_release():
    result = quick(drawing(angle=False).doc, marks=False)
    circle = next(oid for oid in result.condition['operationIds']
                  if result.document.operations[oid]['op'] == 'circle.diameter')
    other = add_auto_marks(result.document, [circle])
    marked = add_auto_marks(other.document, [result.condition['id']])
    assert marked.operations == []
    original = other.document.elements[other.elements[0]]
    released = release_condition(marked.document, result.condition['id'], ev=native.evaluate(marked.document))
    assert released.document.elements[other.elements[0]] == original
    hidden = copy.deepcopy(other.document.data)
    hidden.setdefault('appearance', {})[other.elements[0]] = {'visible': False}
    assert add_auto_marks(hidden, [circle]).operations == []  # Same-source before eligibility.
    hidden['suppressedMarks'] = [{'source': result.condition['id'], 'kind': 'right_angle'}]
    assert add_auto_marks(hidden, [result.condition['id']]).operations == []


def test_motion_and_equal_angle_decoration_keep_user_overrides():
    b = drawing()
    b.angle('h', 'A', 'V', 'B').equal_angles('e', 'g', 'h', count=2)
    b.doc['appearance']['g']['overrides'] = {'tick_count': 3, 'stroke': '#123456'}
    b.doc['appearance']['e'] = {'overrides': {'stroke': '#9933cc', 'tick_count': 2}}
    control = quick(b.doc, marks=False).document
    result = quick(b.doc)
    assert right_marks(result.document) == []
    for t in (0.8, 1.1):
        inputs = {'V': {'kind': 'pathParameter', 'value': t}}
        ev = native.evaluate(result.document, inputs=inputs)
        assert native.measure_statement(result.document, STATEMENT, ev)[0] == 'passed'
        paint = native.resolve_paint(result.document, inputs=inputs)['elements']['g']
        assert paint == native.resolve_paint(control, inputs=inputs)['elements']['g']
        assert paint['angle']['arcs'] == 3 and paint['angle']['right'] is False
        assert paint['decoration']['owner'] == 'e'
        assert paint['decoration']['color'] == '#9933cc'
        assert paint['stroke']['color'] == '#123456'
    assert native.evaluate(result.document, inputs={'V': {'kind': 'pathParameter', 'value': .8}}).elements['V'] != ev.elements['V']


@pytest.mark.manim
def test_label_free_svg_and_tikz_have_one_decoration_contribution(tmp_path):
    pytest.importorskip('manim')
    b = drawing()
    for point in ('A', 'V', 'B'):
        b.doc['appearance'][point]['visible'] = False
    control = quick(b.doc, marks=False).document
    candidate = quick(b.doc).document

    def strokes(doc, name):
        path = tmp_path / (name + '.svg')
        native.render(doc, fmt='svg', out=path, report=False)
        # All points/helpers/labels are hidden: these are only the corner's
        # visible stroke paths. The marks-off control contributes one corner.
        paths = []
        for node in ET.parse(path).iter():
            if node.tag.endswith('path') and node.get('stroke', 'none') != 'none' \
                    and float(node.get('stroke-opacity', '1')) > 0:
                paths.append((node.get('d'), node.get('stroke'), node.get('stroke-width')))
        return sorted(paths)

    one_corner = strokes(control, 'control')
    assert one_corner
    assert strokes(candidate, 'candidate') == one_corner
    for name, doc in [('control', control), ('candidate', candidate)]:
        path = tmp_path / (name + '.tex')
        native.render(doc, fmt='tikz', out=path, report=False)
        commands = re.findall(r'^[ \t]*\\draw\[.*$', path.read_text(), re.MULTILINE)
        assert len(commands) == 1  # One three-vertex right-angle polyline, no labels/TeX compile.
