"""Reproducible source scenes and independent saved conic-element evidence."""
import json
import math

import pytest

from animageo import native
from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from animageo.native._fixture_registry import fixture_version
from animageo.native.convert.ggb import parse_xml, read_ggb, scan
from animageo.native.convert.values import line_coefficients, native_report_value
from tests.native import ggb_conic_elements_fixtures as ggb
from tests.native.test_native_l5_ggb import NS


@pytest.mark.parametrize('name', ggb.NAMES)
def test_source_scene_and_parity_reproduce_without_relabeling_history(name):
    raw, scene, fixture = ggb.build(name)
    assert ggb.same_archive((ggb.SOURCE_DIR/(name+'.ggb')).read_bytes(), raw)
    assert scene == json.loads((ggb.ROOT/'tests/native/import/scenes'/(name+'.json')).read_text())
    saved = json.loads((ggb.ROOT/'animageo/native/parity/v1/ggb'/(name+'.json')).read_text())
    assert same_fixture(saved, fixture) and parity.verify_fixture(saved) == []
    assert fixture['registry'] == fixture_version(scene['document'])


@pytest.mark.parametrize('name', ['pairing', 'pairing_rotated', 'parts', 'circle', 'hyperbola',
                                'asymptotes', 'diameter_line', 'diameter_vector', 'polar'])
def test_saved_coordinates_independently_check_points_and_lines(name):
    path = ggb.SOURCE_DIR/f'ggb_conic_elements_saved_{name}.ggb'
    doc, report = native.from_ggb(path, id_namespace=NS)
    ev = native.evaluate(doc)
    items = {e['ggb_name']: e for e in report['elements']}
    count = 0
    for info in scan(parse_xml(read_ggb(path).xml))['elements']:
        if info.get('command') not in ('Focus', 'Vertex', 'Axes', 'Directrix', 'Asymptote', 'Diameter', 'Polar'):
            continue
        item = items[info['label']]
        if info.get('command') == 'Polar' and info['type'] == 'point':
            assert item['reason'] == 'unsupported_signature' and item['native_ids'] == []
            continue
        if info.get('command') == 'Asymptote' and info['type'] == 'list':
            assert item['reason'] == 'unsupported_signature' and item['native_ids'] == []
            continue
        assert item['category'] == 'editable', item
        state = ev.elements[item['native_ids'][0]]
        coords = info['coords']
        if None in coords.values():
            assert state['state'] == 'undefined'
        elif info['type'] == 'point':
            assert state['value'] == pytest.approx({'x': coords['x']/coords['z'], 'y': coords['y']/coords['z']}, abs=1e-7)
        else:
            expected = line_coefficients(coords['x'], coords['y'], coords['z'])
            assert native_report_value('line', state['value'])['value'] == pytest.approx(expected, abs=1e-7)
        count += 1
    assert count > 0


def test_synthetic_circle_and_sparse_scenes_keep_fixed_slots_and_recovery():
    _, scene, fixture = ggb.build('ggb_conic_elements_circle')
    ids = {e['ggb_name']: e['native_ids'][0] for e in fixture['import']['elements']}
    ev = native.evaluate(scene['document'])
    assert ev.elements[ids['F']]['value'] == ev.elements[ids['G']]['value'] == {'x': 1., 'y': -2.}
    assert scene['document']['elements'][ids['F']]['producer']['slot'] == 'first'
    assert scene['document']['elements'][ids['G']]['producer']['slot'] == 'second'
    _, scene, fixture = ggb.build('ggb_conic_elements_sparse')
    ids = {e['ggb_name']: e['native_ids'][0] for e in fixture['import']['elements']}
    assert '' not in ids
    assert scene['document']['elements'][ids['G']]['producer']['slot'] == 'second'
    assert scene['document']['elements'][ids['R']]['producer']['slot'] == 'third'
    circle = next(case for case in scene['cases'] if case['name'] == 'circle')
    ev = native.evaluate(scene['document'], inputs=circle['inputs'])
    assert ev.elements[ids['G']]['state'] == ev.elements[ids['R']]['state'] == 'defined'


def test_saved_finite_coefficients_preserve_near_center_and_far_diameter_lines():
    for suffix in ('polar_near_center', 'diameter_far'):
        _, scene, fixture = ggb.build('ggb_conic_elements_saved_'+suffix)
        items = {e['ggb_name']: e for e in fixture['import']['elements']}
        ev = native.evaluate(scene['document'])
        item = items['f']
        assert item['category'] == 'editable' and item['value_check'] == 'passed'
        state = ev.elements[item['native_ids'][0]]
        assert state['state'] == 'defined' and math.hypot(*state['value']['p']) > 1e12
