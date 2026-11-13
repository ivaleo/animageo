"""Saved XML components, rather than classic formula results, check vectors."""
import pytest

from animageo.native.convert.values import compare
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import imported


@pytest.mark.parametrize('kind', ['point', 'vector'])
@pytest.mark.parametrize('wrong', [False, True])
def test_source_formula_checks_saved_coords(kind, wrong):
    z = 2 if kind == 'point' else 0
    x, y = (12., 16.) if kind == 'point' else (6., 8.)
    if wrong:
        x += 2
    body = (point('A', 3., 4.) + expression('P', '2A', kind)
            + element(kind, 'P', extra=f'<coords x="{x}" y="{y}" z="{z}"/>'))
    _, items = imported(body)
    item = items['P']
    assert item['category'] == ('differs' if wrong else 'editable'), item
    assert item['value_check'] == ('failed' if wrong else 'passed')
    if wrong:
        assert item['reason'] == 'value_mismatch'
        assert item['delta'] > 0


def test_xml_vector_checks_displacement_with_a_nonzero_start():
    body = (point('A', 10., 20.) + point('B', 13., 24.) + command('Vector', ['A', 'B'], ['u'])
            + element('vector', 'u', extra='<coords x="3" y="4" z="0"/>'))
    _, items = imported(body)
    assert items['u']['value_check'] == 'passed'
    assert items['u']['ggb_value'] == {'kind': 'vector', 'value': [[0., 0.], [3., 4.]], 'components': True}


def test_classic_vector_comparison_still_checks_endpoints():
    expected = {'kind': 'vector', 'value': [[0., 0.], [3., 4.]]}
    actual = {'kind': 'vector', 'value': [[10., 20.], [13., 24.]]}
    assert compare(expected, actual, 1.)[0] == 'failed'
