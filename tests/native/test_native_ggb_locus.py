"""Import a glider and an explicitly parameterized point on a locus."""
import pytest

from animageo import native
from tests.native.ggb_synth import command, element, point
from tests.native.test_native_ggb_inline import eid, imported


def locus_body():
    return (point('A', 0., 0.) + point('B', 4., 0.) + point('C', 0., 2.)
            + command('Segment', ['A', 'B'], ['s']) + element('segment', 's')
            + command('Point', ['s'], ['P']) + point('P', 1., 0.)
            + command('Midpoint', ['P', 'C'], ['T']) + point('T', .5, 1.)
            + command('Locus', ['T', 'P'], ['g']) + element('locus', 'g'))


def locus_scene():
    return (locus_body() + command('Point', ['g'], ['Q']) + point('Q', .75, 1.)
            + command('Segment', ['C', 'Q'], ['h']) + element('segment', 'h'))


def test_point_on_locus_and_its_dependent_segment_are_editable():
    doc, items = imported(locus_scene())
    assert all(e['category'] == 'editable' for n, e in items.items() if n != 'g'), items
    q = eid(items, 'Q')
    assert items['Q']['value_check'] == 'passed'
    assert doc['inputs'][q] == pytest.approx({'kind': 'pathParameter', 'value': .375})
    assert doc['operationRegistryVersion'] == '1.10'
    moved = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [8., 0.]}})
    assert moved.elements[q]['value'] == pytest.approx({'x': 1.5, 'y': 1})
    assert moved.elements[eid(items, 'h')]['value']['b'] == pytest.approx([1.5, 1])


@pytest.mark.parametrize('parameter,x', [('0.375', .75), ('-2', 0), ('2', 2)])
def test_point_on_locus_with_an_explicit_parameter(parameter, x):
    doc, items = imported(locus_body() + command('Point', ['g', parameter], ['Q']) + point('Q', x, 1.))
    assert items['Q']['category'] == 'editable', items['Q']
    assert items['Q']['value_check'] == 'passed'
    assert native.evaluate(doc).elements[eid(items, 'Q')]['value'] == pytest.approx({'x': x, 'y': 1})


def test_point_on_locus_parameter_keeps_a_number_dependency():
    body = (locus_body() + element('numeric', 't', extra='<value val="0.375"/>')
            + command('Point', ['g', 't'], ['Q']) + point('Q', .75, 1.))
    doc, items = imported(body)
    assert items['Q']['category'] == 'editable', items['Q']
    assert 't' in items['Q']['depends_on']
    moved = native.evaluate(doc, inputs={eid(items, 't'): {'kind': 'number', 'value': .625}})
    assert moved.elements[eid(items, 'Q')]['value'] == pytest.approx({'x': 1.25, 'y': 1})


def test_describe_names_the_locus_and_its_explicit_parameter():
    body = (locus_body() + element('numeric', 't', extra='<value val="0.375"/>')
            + command('Point', ['g', 't'], ['Q']) + point('Q', .75, 1.))
    doc, _items = imported(body)
    assert 'Отмечаем точку Q на g с параметром t' in native.describe(doc)[-1]


@pytest.mark.parametrize('parameter,xy', [(None, (.75, 2)), ('0.375', (1.25, 1))])
def test_saved_point_off_the_locus_or_at_another_parameter_differs(parameter, xy):
    args = ['g'] + ([parameter] if parameter else [])
    doc, items = imported(locus_body() + command('Point', args, ['Q']) + point('Q', *xy))
    assert items['Q']['category'] == 'differs' and items['Q']['reason'] == 'value_mismatch', items['Q']
