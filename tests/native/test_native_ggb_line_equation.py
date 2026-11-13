"""Free GeoGebra line equations retain formulas, refs and signed coefficients."""
import pytest

from animageo import native
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported


def line(label, formula, coords):
    return expression(label, formula, type_='line') + element('line', label,
        extra='<coords ' + ' '.join(f'{k}="{v}"' for k, v in zip('xyz', coords)) + '/>')


def scene_body():
    return (element('numeric', 'a', extra='<value val="2"/>')
            + line('g', 'y = a*x + 1', (-2, 1, -1))
            + line('v', 'x = 4', (1, 0, -4))
            + line('h', 'y = -1', (0, 1, 1))
            + command('Intersect', ['g', 'v'], ['P']) + point('P', 4., 9.))


def test_formula_refs_and_intersections_are_live():
    doc, items = imported(scene_body())
    assert all(e['category'] == 'editable' and e['value_check'] == 'passed' for e in items.values()), items
    assert doc['operationRegistryVersion'] == '1.10'
    for name in ('g', 'h', 'v'):
        producer = doc['elements'][eid(items, name)]['producer']['operationId']
        assert doc['operations'][producer]['op'] == 'line.equation'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': -1}})
    assert ev.elements[eid(items, 'P')]['value'] == pytest.approx({'x': 4, 'y': -3})
    assert ev.elements[eid(items, 'v')]['value']['dir'] == [0, -1]


@pytest.mark.parametrize('coords', [(-2, 1, -2), (2, -1, 1)])
def test_mismatched_coefficients_or_orientation_are_differs(coords):
    _doc, items = imported(line('g', 'y = 2*x + 1', coords))
    assert items['g']['category'] == 'differs', items
    assert items['g']['reason'] == 'value_mismatch'


@pytest.mark.parametrize('formula', ['y = floor(x)', 'y = {1, 2}', 'y = x(A)', 'bad equation'])
def test_unsupported_formula_has_explicit_detail(formula):
    _doc, items = imported(point('A', 1., 2.) + line('g', formula, (0, 1, 0)))
    assert items['g']['reason'] == 'formula_unsupported', items
    assert items['g']['detail']


def test_positive_scaling_of_saved_coefficients_is_allowed():
    assert imported(line('g', 'x = 4', (7, 0, -28)))[1]['g']['category'] == 'editable'


def test_numeric_ref_order_preserves_left_minus_right():
    body = (element('numeric', 'a', extra='<value val="2"/>')
            + element('numeric', 'b', extra='<value val="1"/>')
            + line('g', 'b + y = a*x', (-2, 1, 1)))
    doc, items = imported(body)
    g = doc['operations'][doc['elements'][eid(items, 'g')]['producer']['operationId']]
    assert g['args']['refs']['items'] == [{'kind': 'ref', 'elementId': eid(items, k)} for k in ('b', 'a')]
    assert g['args']['expr']['ast'] == {'op': '-', 'args': [
        {'op': '+', 'args': [{'ref': 0}, {'var': 'y'}]},
        {'op': '*', 'args': [{'ref': 1}, {'var': 'x'}]}]}
