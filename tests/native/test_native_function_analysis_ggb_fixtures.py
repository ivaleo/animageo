"""Independent analytical checks for saved GGB imports and changed inputs."""
import functools
import json
import math

import pytest

from animageo import native
from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from tests.native.ggb_function_analysis_fixtures import NAMES, ROOT, SOURCE_DIR, build, same_archive


@functools.lru_cache(maxsize=None)
def imported(suffix):
    _, scene, fixture = build('ggb_function_' + suffix)
    entries = {e['ggb_name']: e for e in fixture['import']['elements']}
    return scene, entries


def frame(suffix, case='saved'):
    scene, entries = imported(suffix)
    inputs = next(c for c in scene['cases'] if c['name'] == case).get('inputs')
    ev = native.evaluate(scene['document'], inputs=inputs)
    return {name: ev.elements[e['native_ids'][0]] for name, e in entries.items() if e.get('native_ids')}


def point_is(states, name, x, y=0, *, found=None, kind=None):
    state = states[name]
    assert state['state'] == 'defined', state
    assert state['value']['x'] == pytest.approx(x, abs=2e-7)
    assert state['value']['y'] == pytest.approx(y, abs=2e-7)
    if found is not None:
        assert state['detail']['found'] == found
    if kind is not None:
        assert state['detail']['kind'] == kind


def undefined(states, name, reason):
    assert states[name]['state'] == 'undefined', states[name]
    assert states[name]['reason'] == reason


@pytest.mark.parametrize('name', NAMES)
def test_generated_source_scene_and_parity_are_current(name):
    raw, scene, fixture = build(name)
    assert same_archive((SOURCE_DIR / f'{name}.ggb').read_bytes(), raw)
    assert json.loads((ROOT / 'tests/native/import/scenes' / f'{name}.json').read_text()) == scene
    saved = json.loads((ROOT / 'animageo/native/parity/v1/ggb' / f'{name}.json').read_text())
    assert same_fixture(saved, fixture)
    assert parity.verify_fixture(saved) == []


def test_empty_output_ordinal_by_value_and_fixed_root_capacity():
    scene, entries = imported('roots')
    doc = scene['document']
    assert '' not in entries
    ids = {n: entries[n]['native_ids'][0] for n in ('Left', 'Right', 'Spare')}
    producers = {n: doc['elements'][i]['producer'] for n, i in ids.items()}
    assert {p['operationId'] for p in producers.values()} == {producers['Left']['operationId']}
    assert {n: p['slot'] for n, p in producers.items()} == {'Left': 'root.1', 'Right': 'root.2', 'Spare': 'root.4'}
    op = doc['operations'][producers['Left']['operationId']]
    assert op['op'] == 'function.roots_polynomial'
    assert op['args']['count']['value'] == 4
    for case, root in [('saved', 1), ('restored', 2)]:
        states = frame('roots', case)
        point_is(states, 'Left', -root, found=2)
        point_is(states, 'Right', root, found=2)
        undefined(states, 'Spare', 'branch_absent')
    merged = frame('roots', 'merged')
    point_is(merged, 'Left', 0, found=1)
    undefined(merged, 'Right', 'branch_absent')
    for label in ids:
        undefined(frame('roots', 'absent'), label, 'no_root')
    assert len(doc['elements']) == 5


@pytest.mark.parametrize('case,k', [('saved', 1), ('wider', 4)])
def test_extrema_change_with_coefficients(case, k):
    states = frame('extrema', case)
    x = math.sqrt(k)
    point_is(states, 'Maximum', -x, 2*k*x, found=2, kind='max')
    point_is(states, 'Minimum', x, -2*k*x, found=2, kind='min')


@pytest.mark.parametrize('case', ['stationary', 'monotone'])
def test_no_isolated_extremum_is_not_a_saved_vertex(case):
    for label in ('Minimum', 'Maximum'):
        undefined(frame('extrema', case), label, 'no_extremum')


def test_interval_modes_live_bounds_start_and_recovery():
    states = frame('intervals')
    for label, x in [('L', -math.pi), ('M', 0), ('R', math.pi)]:
        point_is(states, label, x, found=3)
    point_is(states, 'Near', 0)
    point_is(states, 'Single', 0)
    point_is(states, 'Low', -math.pi/2, -1, found=2, kind='min')
    point_is(states, 'High', math.pi/2, 1, found=2, kind='max')
    for case, root, extremum, y in [('positive', math.pi, math.pi/2, 1),
                                    ('negative', -math.pi, -math.pi/2, -1)]:
        states = frame('intervals', case)
        point_is(states, 'Near', root)
        point_is(states, 'Single', root)
        point_is(states, 'L', root, found=1)
        undefined(states, 'M', 'branch_absent')
        undefined(states, 'R', 'branch_absent')
        point_is(states, 'Low', extremum, y, found=1, kind='max' if y == 1 else 'min')
        undefined(states, 'High', 'branch_absent')
    for label in ('L', 'M', 'R', 'Single', 'Low', 'High'):
        undefined(frame('intervals', 'reversed'), label, 'empty_range')
    point_is(frame('intervals', 'recovered'), 'Near', 2*math.pi)


def test_import_preserves_analysis_modes_and_live_argument_ids():
    scene, entries = imported('intervals')
    doc = scene['document']
    for label, mode, args in [
        ('L', 'roots_interval', {'a': 'a', 'b': 'b'}),
        ('Near', 'root_near', {'start': 's'}),
        ('Single', 'root_interval', {'a': 'a', 'b': 'b'}),
        ('Low', 'extrema_interval', {'a': 'a', 'b': 'b'}),
    ]:
        producer = doc['elements'][entries[label]['native_ids'][0]]['producer']
        op = doc['operations'][producer['operationId']]
        assert op['op'] == 'function.' + mode
        assert op['args']['function'] == {'kind': 'ref', 'elementId': entries['f']['native_ids'][0]}
        for arg, name in args.items():
            assert op['args'][arg] == {'kind': 'ref', 'elementId': entries[name]['native_ids'][0]}


def test_axis_intersections_index_normalized_z_and_rank():
    scene, entries = imported('axes')
    doc = scene['document']
    indexed = doc['elements'][entries['Indexed']['native_ids'][0]]['producer']
    assert indexed['slot'] == 'root.2'
    for case, k in [('saved', 1), ('wider', 4)]:
        states = frame('axes', case)
        point_is(states, 'Indexed', math.sqrt(k))
        point_is(states, 'Left', -math.sqrt(k))
        point_is(states, 'Right', math.sqrt(k))
        point_is(states, 'Ordinate', 0, -k)
    point_is(frame('axes', 'merged'), 'Left', 0)
    undefined(frame('axes', 'merged'), 'Indexed', 'branch_absent')
    undefined(frame('axes', 'absent'), 'Indexed', 'no_root')
    assert entries['Ordinate']['value_check'] == 'passed'


@pytest.mark.parametrize('case,a,c', [('saved', 3, 2), ('abscissa', -2, 2),
                                     ('coefficient', 3, -1), ('both', 100, 0)])
def test_function_value_and_tuple_follow_abscissa_and_coefficient(case, a, c):
    states = frame('value', case)
    y = c*a*a - 1
    point_is(states, 'P', a, y)
    assert states['v']['state'] == 'defined'
    assert states['v']['value'] == {'value': y, 'unit': 'scalar'}
    scene, entries = imported('value')
    producer = scene['document']['elements'][entries['v']['native_ids'][0]]['producer']
    assert scene['document']['operations'][producer['operationId']]['op'] == 'function.value'


def test_inline_function_numeric_helpers_and_deletion():
    scene, entries = imported('helpers')
    doc = scene['document']
    helpers = {i: el for i, el in doc['elements'].items() if el.get('origin', {}).get('kind') == 'auto'}
    assert any(el['type'] == 'function' for el in helpers.values())
    assert any(el['type'] == 'number' for el in helpers.values())
    assert all(doc['appearance'][i]['role'] == 'aux' and not el.get('displayName')
               for i, el in helpers.items())
    for i, el in helpers.items():
        assert el['origin']['source'] in doc['operations']
    point_is(frame('helpers'), 'Single', -1)
    point_is(frame('helpers', 'wider'), 'Single', -2)
    undefined(frame('helpers', 'empty'), 'Single', 'empty_range')
    point_is(frame('helpers', 'recovered'), 'Single', -1)
    from animageo.native.edit import delete
    result = delete(doc, [entries[n]['native_ids'][0] for n in ('L', 'R', 'Single')], mode='operation')
    assert not (set(helpers) & set(result.document.elements))
    assert entries['k']['native_ids'][0] in result.document.elements


def test_unexpressible_modes_are_explicit_refusals():
    _, entries = imported('refused')
    for name in ('Unbounded', 'DynamicIndex', 'MissingOrdinate', 'NonPolynomial'):
        assert entries[name]['category'] != 'editable'
        assert entries[name]['reason'] == 'unsupported_signature', entries[name]
    assert entries['UnknownFormula']['reason'] == 'formula_unsupported'
    assert all(not entries[n].get('native_ids') for n in ('Unbounded', 'DynamicIndex', 'MissingOrdinate',
                                                        'NonPolynomial', 'UnknownFormula'))


def test_real_saved_archive_coordinates_and_multiplicity():
    point_is(frame('saved_multiplicity'), 'A', 0, found=2)
    point_is(frame('saved_multiplicity'), 'B', 2, found=2)
    point_is(frame('saved_quartic'), 'A', 0, 0, found=1, kind='min')
    for suffix in ('saved_multiplicity', 'saved_quartic', 'saved_rank', 'saved_ordinate', 'saved_point_value'):
        _, entries = imported(suffix)
        assert all(e['category'] == 'editable' and e.get('value_check') == 'passed'
                   for e in entries.values()), entries


def test_real_saved_rank_changes_keep_structure_and_producer():
    scene, entries = imported('saved_rank')
    assert len(scene['document']['elements']) == 5
    for case, roots in [('saved', [-1, 1, 5]), ('merged', [0, 5]),
                         ('absent_pair', [5]), ('restored', [-2, 2, 5])]:
        states = frame('saved_rank', case)
        for rank, label in enumerate(('A', 'B', 'C')):
            if rank < len(roots):
                point_is(states, label, roots[rank], found=len(roots))
            else:
                undefined(states, label, 'branch_absent')


def test_real_saved_ordinate_point_and_number_remain_live():
    for case, a in [('saved', 2), ('coefficient', 5), ('zero', 0)]:
        point_is(frame('saved_ordinate', case), 'A', 0, -a)
    for case, a in [('saved', 2), ('negative', -2), ('zero', 0), ('larger', 3)]:
        states = frame('saved_point_value', case)
        point_is(states, 'P', a, a*a-1)
        assert states['v']['value']['value'] == a*a-1


def test_known_saved_differences_are_not_frozen_or_relabelled():
    _, entries = imported('saved_touching_difference')
    assert entries['A']['category'] == 'differs'
    assert entries['A']['reason'] == 'value_mismatch'
    assert entries['A']['value_check'] == 'failed'
    point_is(frame('saved_touching_difference'), 'A', 0, found=1)
    _, entries = imported('saved_constant_difference')
    for label in ('B', 'C'):
        assert entries[label]['category'] == 'differs'
        assert entries[label]['value_check'] == 'failed'
        undefined(frame('saved_constant_difference'), label, 'coincident')
    _, entries = imported('saved_near_difference')
    assert entries['A']['category'] == 'differs'
    assert entries['A']['reason'] == 'value_mismatch'
    point_is(frame('saved_near_difference'), 'A', 1.01)
    point_is(frame('saved_near_difference', 'middle'), 'A', 1.01)
    point_is(frame('saved_near_difference', 'right'), 'A', 1.02)
