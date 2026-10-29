"""GGB intersection outputs are assigned together, including undefined ones."""
import math
import json

import pytest

from animageo import native
from tests.native.ggb_synth import command, element, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.conftest import NATIVE_DIR, REPO_ROOT, SCENES_DIR


def circle(label, radius):
    return command('Circle', ['O', str(radius)], [label]) + element('conic', label, extra=
            f'<matrix A0="1" A1="1" A2="{-radius ** 2}" A3="0" A4="0" A5="0"/>')


def segment_circle_body():
    return (point('O', 0., 0.) + point('A', 0., 0.) + point('B', 3., 0.)
            + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', extra='<coords x="0" y="1" z="0"/>') + circle('k', 2))


def undefined(label):
    return element('point', label, extra='<coords x="NaN" y="NaN" z="NaN"/>')


def slots(doc, items, *names):
    return [doc['elements'][eid(items, name)]['producer']['slot'] for name in names]


@pytest.mark.parametrize('outputs', [('P', 'U'), ('U', 'P')])
def test_defined_and_undefined_outputs_get_distinct_slots_and_recover(outputs):
    doc, items = imported(segment_circle_body() + command('Intersect', ['s', 'k'], outputs)
                          + ''.join(point(name, 2., 0.) if name == 'P' else undefined(name) for name in outputs)
                          + command('Midpoint', ['P', 'U'], ['M']) + undefined('M'))
    assert all(e['category'] == 'editable' for e in items.values())
    assert slots(doc, items, 'P', 'U') == ['second', 'first']
    ev = native.evaluate(doc)
    assert ev.elements[eid(items, 'U')]['state'] == 'undefined'
    assert ev.elements[eid(items, 'M')]['state'] == 'undefined'
    # The missing branch becomes visible as the segment extends to the left.
    ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [-3., 0.]}})
    assert ev.elements[eid(items, 'P')]['value'] == dict(x=2., y=0.)
    assert ev.elements[eid(items, 'U')]['value'] == dict(x=-2., y=0.)
    assert ev.elements[eid(items, 'M')]['value'] == dict(x=0., y=0.)


def test_empty_first_output_preserves_second_slot_when_both_are_undefined():
    cmd = '<command name="Intersect"><input a0="s" a1="k"/><output a0="" a1="P"/></command>'
    body = (point('O', 0., 0.) + point('A', 0., 3.) + point('B', 3., 3.)
            + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', extra='<coords x="0" y="1" z="-3"/>') + circle('k', 2))
    doc, items = imported(body + cmd + undefined('P'))
    assert items['P']['category'] == 'editable'
    assert slots(doc, items, 'P') == ['second']
    ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [0., 0.]},
                                      eid(items, 'B'): {'kind': 'point', 'value': [3., 0.]}})
    assert ev.elements[eid(items, 'P')]['value'] == dict(x=2., y=0.)


def test_output_without_element_is_not_invented_or_made_editable():
    doc, items = imported(segment_circle_body() + command('Intersect', ['s', 'k'], ['ghost', 'P'])
                          + point('P', 2., 0.))
    assert 'ghost' not in items
    assert items['P']['category'] == 'editable'
    assert slots(doc, items, 'P') == ['second']
    assert len(doc['elements']) == sum(len(e['native_ids']) for e in items.values())


@pytest.mark.parametrize('undefined_sibling', [False, True])
def test_tangency_does_not_duplicate_slots_or_hide_a_value_mismatch(undefined_sibling):
    body = (point('O', 0., 0.) + point('A', -3., 2.) + point('B', 3., 2.)
            + command('Line', ['A', 'B'], ['g'])
            + element('line', 'g', extra='<coords x="0" y="1" z="-2"/>') + circle('k', 2)
            + command('Intersect', ['g', 'k'], ['P', 'Q']) + point('P', 0., 2.)
            + (undefined('Q') if undefined_sibling else point('Q', 0., 2.)))
    doc, items = imported(body)
    assert slots(doc, items, 'P', 'Q') == ['first', 'second']
    assert items['P']['category'] == 'editable'
    assert items['Q']['category'] == ('differs' if undefined_sibling else 'editable')
    if undefined_sibling:
        assert items['Q']['reason'] == 'value_mismatch'
    for y in (1., 1.999, 2.001, 1.):
        ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [-3., y]},
                                          eid(items, 'B'): {'kind': 'point', 'value': [3., y]}})
        p, q = (ev.elements[eid(items, n)] for n in ('P', 'Q'))
        if y > 2:
            assert p['state'] == q['state'] == 'undefined'
        else:
            assert p['value']['x'] < q['value']['x']


def chain_body():
    return (point('O', 0., 0.) + point('A', -4., 0.) + point('B', 4., 0.) + point('C', 2., 4.)
            + command('Line', ['A', 'B'], ['g'])
            + element('line', 'g', extra='<coords x="0" y="1" z="0"/>') + circle('k', 2) + circle('c', 3)
            + command('Intersect', ['g', 'k'], ['P', 'N']) + point('P', 2., 0.) + point('N', -2., 0.)
            + command('Line', ['P', 'C'], ['h'])
            + element('line', 'h', extra='<coords x="1" y="0" z="-2"/>')
            + command('Intersect', ['h', 'c'], ['E', 'F'])
            + point('E', 2., math.sqrt(5)) + point('F', 2., -math.sqrt(5)))


def test_downstream_intersection_is_probed_after_upstream_slots_are_resolved():
    doc, items = imported(chain_body())
    assert all(e['category'] == 'editable' for e in items.values())
    assert slots(doc, items, 'P', 'N') == ['second', 'first']
    for offset in (0., 0.1, -0.2, 0.):
        ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [-4., offset]},
                                          eid(items, 'B'): {'kind': 'point', 'value': [4., offset]}})
        p, e, f = (ev.elements[eid(items, name)]['value'] for name in ('P', 'E', 'F'))
        assert p['x'] > 0 and e['y'] > f['y']
        assert math.hypot(e['x'], e['y']) == pytest.approx(3.)
        assert (e['x'] - p['x']) * (4 - p['y']) == pytest.approx((e['y'] - p['y']) * (2 - p['x']))


def test_wrong_saved_coordinate_is_reported_as_differs():
    doc, items = imported(segment_circle_body() + command('Intersect', ['s', 'k'], ['P', 'U'])
                          + point('P', 1.5, 0.) + undefined('U'))
    assert items['P']['category'] == 'differs'
    assert items['P']['reason'] == 'value_mismatch'
    assert len(set(slots(doc, items, 'P', 'U'))) == 2


def test_out_of_range_index_is_not_rebound_to_an_existing_branch():
    _doc, items = imported(segment_circle_body() + command('Intersect', ['s', 'k', '3'], ['P'])
                           + point('P', 2., 0.))
    assert items['P']['category'] != 'editable'
    assert items['P']['native_ids'] == []


@pytest.mark.parametrize('name', ['ggb_inline_arguments', 'ggb_intersect_outputs', 'ggb_intersect_chain'])
def test_parity_scene_reproduces_imported_xml(name):
    from tests.native.test_native_ggb_inline import vector_body
    bodies = {
        'ggb_inline_arguments': vector_body() + command('Translate', ['A', 'Vector[(a * u)]'], ['T'])
                                + point('T', -1., -6.),
        'ggb_intersect_outputs': segment_circle_body() + command('Intersect', ['s', 'k'], ['P', 'U'])
                                + point('P', 2., 0.) + undefined('U')
                                + command('Midpoint', ['P', 'U'], ['M']) + undefined('M'),
        'ggb_intersect_chain': chain_body(),
    }
    doc, _items = imported(bodies[name])
    doc['documentId'] = name
    scene_dir = REPO_ROOT / 'tests/native/import/scenes' if name == 'ggb_inline_arguments' else SCENES_DIR
    assert doc == json.loads((scene_dir / f'{name}.json').read_text())['document']


def test_import_formula_fixture_reproduces_and_verifies():
    from animageo.native import parity
    from animageo.native._fixture_compare import same_fixture
    scene = json.loads((REPO_ROOT / 'tests/native/import/scenes/ggb_inline_arguments.json').read_text())
    fixture = json.loads((NATIVE_DIR / 'parity/v1/ggb/ggb_inline_arguments.json').read_text())
    assert same_fixture(fixture, parity.generate_scene(scene))
    assert parity.verify_fixture(fixture) == []
