"""Anonymous GGB arguments keep private, live dependency graphs (IMP-1)."""
import copy

import pytest

from animageo import native
from animageo.native.document import iter_refs
from tests.native.ggb_synth import command, element, expression, ggb_bytes, point
from tests.native.test_native_l5_ggb import NS, _check


def vector_body():
    return (point('A', 1., 2.) + point('B', 3., 4.) + point('C', 2., 0.)
            + command('Vector', ['B', 'C'], ['u']) + element('vector', 'u')
            + element('numeric', 'a', extra='<value val="2"/>'))


def imported(body):
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, report)
    return doc, {e['ggb_name']: e for e in report['elements']}


def eid(items, name):
    return items[name]['native_ids'][0]


@pytest.mark.parametrize('argument, expected', [
    ('Vector[A, B]', (3., 4.)), ('Vector[(-u)]', (2., 6.)),
    ('Vector[(a * u)]', (-1., -6.)), ('Vector[(u * a)]', (-1., -6.)),
    ('Vector[((a + 1) * u)]', (-2., -10.)),
])
def test_translate_argument_matches_saved_point_and_moves(argument, expected):
    doc, items = imported(vector_body() + command('Translate', ['A', argument], ['T']) + point('T', *expected))
    assert all(e['category'] == 'editable' for e in items.values())
    assert items['T']['native_value']['value'] == list(expected)
    moved = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [2., 3.]}})
    # Vector[A,B] also changes with A; all other displacements depend on B,C.
    xy = (3., 4.) if argument == 'Vector[A, B]' else (expected[0] + 1, expected[1] + 1)
    assert moved.elements[eid(items, 'T')]['value'] == pytest.approx(dict(x=xy[0], y=xy[1]))


def test_scaled_vector_remains_defined_at_zero_negative_factor_and_zero_vector():
    doc, items = imported(vector_body() + command('Translate', ['A', 'Vector[(a * u)]'], ['T'])
                          + point('T', -1., -6.))
    for factor in (-3., 0., 0.25, 4.):
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': factor}})
        assert ev.elements[eid(items, 'T')]['state'] == 'defined'
        assert ev.elements[eid(items, 'T')]['value'] == pytest.approx(dict(x=1 - factor, y=2 - 4 * factor))
    ev = native.evaluate(doc, inputs={eid(items, 'C'): {'kind': 'point', 'value': [3., 4.]}})
    assert ev.elements[eid(items, 'T')]['value'] == dict(x=1., y=2.)


def test_nested_transform_chain_is_live():
    body = (point('A', 0., 0.) + point('B', 2., 0.)
            + command('Vector', ['A', 'B'], ['v']) + element('vector', 'v')
            + command('Translate', ['Dilate[Rotate[B, 90°, A], 2, A]', 'v'], ['T']) + point('T', 2., 4.))
    doc, items = imported(body)
    assert items['T']['category'] == 'editable'
    ev = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [3., 0.]}})
    assert ev.elements[eid(items, 'T')]['value'] == pytest.approx(dict(x=3., y=6.))


@pytest.mark.parametrize('name, inputs, coords', [
    ('Segment', ['(0, 0)', '(1, 2)'], (-2, 1, 0)),
    ('Line', ['(0, 0)', '(1, 2)'], (-2, 1, 0)),
    ('OrthogonalLine', ['A', 'Line[(0, 0), (0, 1)]'], (0, 1, -2)),
    ('Line', ['A', 'Line[B, C]'], (4, -1, -2)),
])
def test_coordinate_literals_and_nested_lines(name, inputs, coords):
    body = point('A', 1., 2.) + point('B', 3., 4.) + point('C', 2., 0.)
    typ = 'segment' if name == 'Segment' else 'line'
    doc, items = imported(body + command(name, inputs, ['g']) + element(typ, 'g', extra=
                          f'<coords x="{coords[0]}" y="{coords[1]}" z="{coords[2]}"/>'))
    assert items['g']['category'] == 'editable'
    owned = {nid for item in items.values() for nid in item['native_ids']}
    helpers = set(doc['elements']) - owned
    assert helpers
    assert all(doc['appearance'][h]['visible'] is False for h in helpers)
    assert all(doc['appearance'][h]['locked'] is True for h in helpers)
    assert all(doc['appearance'][h]['label']['mode'] == 'none' for h in helpers)
    assert doc == native.from_ggb(ggb_bytes(body + command(name, inputs, ['g']) + element(typ, 'g', extra=
                  f'<coords x="{coords[0]}" y="{coords[1]}" z="{coords[2]}"/>')), id_namespace=NS)[0]


def test_helper_ownership_survives_selecting_one_of_two_objects():
    body = vector_body()
    for name in ('T', 'U'):
        body += command('Translate', ['A', 'Vector[(-u)]'], [name]) + point(name, 2., 6.)
    doc, items = imported(body)
    assert set(items['T']['native_ids']).isdisjoint(items['U']['native_ids'])
    # Model the downstream selection: discard all IDs owned by T.
    selected = copy.deepcopy(doc)
    discard = set(items['T']['native_ids'])
    for oid, op in list(selected['operations'].items()):
        if all(out['elementId'] in discard for out in op['outputs']):
            del selected['operations'][oid]
    for table in ('elements', 'appearance', 'inputs'):
        for item in discard:
            selected[table].pop(item, None)
    selected['bindings']['legacyNames'].pop(eid(items, 'T'))
    assert native.validate(selected) == []
    assert native.evaluate(selected).elements[eid(items, 'U')]['value'] == dict(x=2., y=6.)
    owned = {nid for item in items.values() for nid in item['native_ids']}
    helpers = set(doc['elements']) - owned
    assert helpers and all(doc['appearance'][h]['visible'] is False for h in helpers)
    assert all(ref in doc['elements'] for op in doc['operations'].values() for arg in op['args'].values()
               for ref in iter_refs(arg))


def test_unsupported_nested_command_does_not_become_a_free_editable_copy():
    doc, items = imported(vector_body() + command('Translate', ['A', 'Vector[UnitVector[u]]'], ['T'])
                          + point('T', 1., 1.))
    assert items['T']['category'] != 'editable'
    assert items['T']['native_ids'] == []


def test_literal_vector_expression_keeps_its_hidden_endpoints():
    body = (point('A', 1., 2.) + expression('u', 'Vector[(0, 0), (1, 0)]') + element('vector', 'u')
            + command('Translate', ['A', 'Vector[(-u)]'], ['T']) + point('T', 0., 2.))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    assert native.validate(doc) == []


@pytest.mark.parametrize('constant', ['pi', 'π', ' pi '])
def test_bare_pi_argument_is_a_number_literal(constant):
    body = (point('B', 1., 0.) + point('O', 0., 0.)
            + command('Rotate', ['B', constant, 'O'], ['B_1']) + point('B_1', -1., 0.))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    assert items['B_1']['value_check'] == 'passed'
    moved = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [0., 2.]}})
    assert moved.elements[eid(items, 'B_1')]['value'] == pytest.approx(dict(x=0., y=-2.))
