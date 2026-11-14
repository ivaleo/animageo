"""Independent saved coefficients and analytical tangency fixture coverage."""
import json
import math

import pytest

from animageo import native
from animageo.native import curves_fixtures, parity
from animageo.native._fixture_compare import same_fixture
from animageo.native.convert.ggb import parse_xml, read_ggb, scan
from animageo.native.convert.values import line_coefficients, native_report_value
from tests.native import ggb_tangency_fixtures as ggb
from tests.native.test_native_l5_ggb import NS


@pytest.mark.parametrize('name', ggb.NAMES)
def test_source_and_parity_fixtures_reproduce_and_verify(name):
    raw, scene, fixture = ggb.build(name)
    assert ggb.same_archive((ggb.SOURCE_DIR / f'{name}.ggb').read_bytes(), raw)
    assert scene == json.loads((ggb.ROOT / 'tests/native/import/scenes' / f'{name}.json').read_text())
    saved = json.loads((ggb.ROOT / 'animageo/native/parity/v1/ggb' / f'{name}.json').read_text())
    assert same_fixture(saved, fixture) and parity.verify_fixture(saved) == []


@pytest.mark.parametrize('name', ['abscissa', 'parameter', 'external', 'vertical', 'parallel', 'hyperbola', 'parabola', 'slope'])
def test_saved_geogebra_coefficients_are_independent_line_evidence(name):
    path = ggb.SOURCE_DIR / f'ggb_tangency_saved_{name}.ggb'
    doc, report = native.from_ggb(path, id_namespace=NS)
    ev = native.evaluate(doc)
    items = {e['ggb_name']: e for e in report['elements']}
    checked = 0
    for info in scan(parse_xml(read_ggb(path).xml))['elements']:
        if info['type'] != 'line' or info.get('command') != 'Tangent':
            continue
        item = items[info['label']]
        assert item['category'] == 'editable'
        state = ev.elements[item['native_ids'][0]]
        coords = info['coords']
        if None in coords.values():
            assert state['state'] == 'undefined'
        else:
            expected = line_coefficients(coords['x'], coords['y'], coords['z'])
            actual = native_report_value('line', state['value'])['value']
            assert actual == pytest.approx(expected, abs=1e-6)
        checked += 1
    assert checked > 0


def test_inline_point_fixture_checks_saved_coefficients_and_live_abscissas():
    raw, scene, fixture = ggb.build('ggb_tangency_inline_points')
    doc = scene['document']
    items = {e['ggb_name']: e for e in fixture['import']['elements']}
    saved = native.evaluate(doc)
    checked = 0
    for info in scan(parse_xml(read_ggb(raw).xml))['elements']:
        if info.get('command') != 'Tangent':
            continue
        item = items[info['label']]
        assert item['category'] == 'editable' and item['value_check'] == 'passed'
        coords = info['coords']
        expected = line_coefficients(coords['x'], coords['y'], coords['z'])
        value = saved.elements[item['native_ids'][0]]['value']
        assert native_report_value('line', value)['value'] == pytest.approx(expected, abs=1e-9)
        checked += 1
    assert checked == 4
    for case, shifted_x in zip(scene['cases'], (2, 2, 4, -1), strict=True):
        ev = native.evaluate(doc, inputs=case.get('inputs'))
        for name in ('literal', 'ordinate', 'shifted', 'numeric'):
            x = 1 if name in ('literal', 'ordinate') else shifted_x
            value = ev.elements[items[name]['native_ids'][0]]['value']
            actual = native_report_value('line', value)['value']
            assert actual == pytest.approx(line_coefficients(-2*x, 1, x*x), abs=1e-9)


def test_saved_multiplicity_refuses_both_labels_and_jump_is_honestly_different():
    _, _, fixture = ggb.build('ggb_tangency_saved_multiplicity')
    items = {e['ggb_name']: e for e in fixture['import']['elements']}
    for name in ('f', 'g'):
        assert items[name]['reason'] == 'unsupported_signature' and items[name]['native_ids'] == []
        assert 'multiplicity' in items[name]['detail']
    _, _, fixture = ggb.build('ggb_tangency_saved_corner')
    items = {e['ggb_name']: e for e in fixture['import']['elements']}
    assert items['e']['category'] == 'differs' and items['e']['reason'] == 'value_mismatch'


def test_analytical_curves_cover_the_five_tangency_operations():
    fixtures = {n: f for n, f in curves_fixtures.build_fixtures().items()
                if n.startswith(('graph_tangent_', 'line_slope_', 'conic_tangent_'))}
    seen = set()
    for fixture in fixtures.values():
        assert parity.verify_fixture(fixture) == []
        seen.update(o['op'] for o in fixture['document']['operations'].values() if 'tangent' in o['op'] or o['op'] == 'line.slope')
    assert seen == {'line.tangent_function_at', 'line.tangent_conic_at', 'line.tangents_from_point_conic',
                    'line.tangents_parallel_conic', 'line.slope'}
