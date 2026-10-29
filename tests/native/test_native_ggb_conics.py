"""Anonymous conics, branch identities and regular-polygon dependencies."""
import json
import math

import pytest

from animageo import native
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_output_slots import circle


def matrix(label, coefficients):
    return element('conic', label, extra='<matrix ' + ' '.join(
        f'A{i}="{v}"' for i, v in enumerate(coefficients)) + '/>')


def conic_body(kind='Ellipse'):
    if kind == 'Parabola':
        return (point('F', 0., 1.) + point('U', -4., -1.) + point('V', 4., -1.)
                + command('Line', ['U', 'V'], ['d']) + element('line', 'd')
                + command('Parabola', ['F', 'd'], ['q']) + matrix('q', [1, 0, 0, 0, 0, -2]))
    f = math.sqrt(5 if kind == 'Ellipse' else 13)
    return (point('F', -f, 0.) + point('G', f, 0.) + point('T', 0., 2.) if kind == 'Ellipse' else
            point('F', -f, 0.) + point('G', f, 0.) + point('T', 3., 0.)) + (
            command(kind, ['F', 'G', 'T'], ['q'])
            + matrix('q', [4, 9 if kind == 'Ellipse' else -9, -36, 0, 0, 0]))


def conic_branch_body(kind='Ellipse', reverse=False, indexed=False):
    y = 1. if kind == 'Parabola' else 0.
    x = 2. if kind == 'Parabola' else 3.
    args = ['q', 'g'] if reverse else ['g', 'q']
    return (conic_body(kind) + point('A', -5., y) + point('B', 5., y)
            + command('Line', ['A', 'B'], ['g']) + element('line', 'g')
            + command('Intersect', args + (['1'] if indexed else []), ['P'] if indexed else ['P', 'Q'])
            + point('P', x, y) + ('' if indexed else point('Q', -x, y)))


@pytest.mark.parametrize('kind', ['Ellipse', 'Hyperbola', 'Parabola'])
@pytest.mark.parametrize('reverse,indexed', [(False, False), (True, False), (False, True), (True, True)])
def test_conic_intersection_keeps_chosen_branch_under_motion(kind, reverse, indexed):
    doc, items = imported(conic_branch_body(kind, reverse, indexed))
    assert all(e['category'] == 'editable' and e['value_check'] == 'passed' for e in items.values())
    chosen = doc['elements'][eid(items, 'P')]['producer']['slot']
    for y in (0.5, 1., 1.5, 0.5):
        ev = native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [-5., y]},
                                         eid(items, 'B'): {'kind': 'point', 'value': [5., y]}})
        x = 2 * math.sqrt(y) if kind == 'Parabola' else 3 * math.sqrt(1 + (-1 if kind == 'Ellipse' else 1) * y*y/4)
        assert ev.elements[eid(items, 'P')]['value'] == pytest.approx(dict(x=x, y=y))
        assert doc['elements'][eid(items, 'P')]['producer']['slot'] == chosen
        if not indexed:
            assert ev.elements[eid(items, 'Q')]['value'] == pytest.approx(dict(x=-x, y=y))


def test_circle_circle_reversed_saved_outputs_remain_distinct():
    body = (point('O', 0., 0.) + point('C', 2., 0.) + circle('k', 2)
            + command('Circle', ['C', '2'], ['c']) + matrix('c', [1, 1, 0, 0, -2, 0])
            + command('Intersect', ['k', 'c'], ['P', 'Q'])
            + point('P', 1., -math.sqrt(3)) + point('Q', 1., math.sqrt(3)))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    for x in (2.1, 3.9, 4.1, 2.):
        ev = native.evaluate(doc, inputs={eid(items, 'C'): {'kind': 'point', 'value': [x, 0.]}})
        p, q = (ev.elements[eid(items, n)] for n in ('P', 'Q'))
        if x > 4:
            assert p['state'] == q['state'] == 'undefined'
        else:
            assert p['value']['y'] < q['value']['y']


def equation_body():
    return (element('numeric', 'a', extra='<value val="1"/>') + expression('q', 'y = a*x^2')
            + matrix('q', [-1, 0, 0, 0, 0, .5]) + point('A', -3., 1.) + point('B', 3., 1.)
            + command('Line', ['A', 'B'], ['g']) + element('line', 'g')
            + command('Intersect', ['q', 'g'], ['P', 'Q']) + point('P', 1., 1.) + point('Q', -1., 1.))


def test_equation_keeps_numeric_refs_and_checks_saved_matrix():
    doc, items = imported(equation_body())
    assert all(e['category'] == 'editable' for e in items.values())
    for a in (0.25, 2., 1.):
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': a}})
        assert ev.elements[eid(items, 'P')]['value'] == pytest.approx(dict(x=1/math.sqrt(a), y=1.))
    stale = equation_body().replace('A0="-1"', 'A0="-2"')
    _doc, bad = imported(stale)
    assert bad['q']['category'] == 'differs' and bad['q']['reason'] == 'value_mismatch'


def test_conic_matrix_compares_up_to_nonzero_scale():
    for factor in (-7, .25, 1e8):
        body = conic_body().replace('<matrix A0="4" A1="9" A2="-36" A3="0" A4="0" A5="0"/>',
                  '<matrix ' + ' '.join(f'A{i}="{v*factor}"' for i,v in enumerate([4,9,-36,0,0,0])) + '/>')
        assert imported(body)[1]['q']['category'] == 'editable'


def test_five_points_and_conic_parts_are_live():
    coords = [(3., 0.), (0., 2.), (-3., 0.), (0., -2.), (1.8, 1.6)]
    body = ''.join(point(n, *xy) for n, xy in zip('ABCDE', coords))
    body += command('Conic', list('ABCDE'), ['q']) + matrix('q', [4, 9, -36, 0, 0, 0])
    body += command('Center', ['q'], ['O']) + point('O', 0., 0.)
    body += command('Focus', ['q'], ['F', 'G']) + point('F', math.sqrt(5), 0.) + point('G', -math.sqrt(5), 0.)
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    moved = native.evaluate(doc, inputs={eid(items, 'E'): {'kind': 'point', 'value': [2., 1.5]}})
    assert moved.elements[eid(items, 'q')]['state'] == 'defined'
    assert moved.elements[eid(items, 'F')]['value'] != native.evaluate(doc).elements[eid(items, 'F')]['value']


def regular_body(sparse=False):
    out = ('<output a0="p" a3="s3" a5="C" a6="D"/>' if sparse
           else '<output a0="p" a1="s1" a2="s2" a3="s3" a4="s4" a5="C" a6="D"/>')
    return (point('A', 0., 0.) + point('B', 2., 0.)
            + '<command name="Polygon"><input a0="A" a1="B" a2="4"/>' + out + '</command>'
            + element('polygon', 'p') + ('' if sparse else element('segment', 's1') + element('segment', 's2'))
            + element('segment', 's3', extra='<coords x="0" y="1" z="-2"/>')
            + ('' if sparse else element('segment', 's4'))
            + point('C', 2., 2.) + point('D', 0., 2.)
            + command('Midpoint', ['s3'], ['M']) + point('M', 1., 2.))


@pytest.mark.parametrize('sparse', [False, True])
def test_regular_polygon_outputs_sides_vertices_and_dependencies(sparse):
    doc, items = imported(regular_body(sparse))
    assert all(e['category'] == 'editable' for e in items.values())
    assert doc['elements'][eid(items, 'C')]['producer']['slot'] == 'vertex.3'
    assert doc['elements'][eid(items, 's3')]['producer']['slot'] == 'side.3'
    ev = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [3., 0.]}})
    assert ev.elements[eid(items, 'M')]['value'] == pytest.approx(dict(x=1.5, y=3.))


def test_regular_polygon_side_with_unreported_vertices_keeps_hidden_helpers():
    body = (regular_body(True).replace(' a5="C" a6="D"', '')
            .replace(point('C', 2., 2.), '').replace(point('D', 0., 2.), ''))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    helpers = set(doc['elements']) - {e for item in items.values() for e in item['native_ids']}
    assert len(helpers) == 2 and all(doc['appearance'][h]['visible'] is False for h in helpers)


@pytest.mark.parametrize('axis,xy,moved', [('xAxis', (3., 0.), (5., 0.)), ('yAxis', (0., -2.), (0., 4.))])
def test_point_on_implicit_axis_preserves_path_and_hidden_helpers(axis, xy, moved):
    doc, items = imported(command('Point', [axis], ['P']) + point('P', *xy))
    assert items['P']['category'] == 'editable'
    t = native.project(doc, eid(items, 'P'), moved)
    ev = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'pathParameter', 'value': t}})
    assert ev.elements[eid(items, 'P')]['value'] == pytest.approx(dict(zip(('x', 'y'), moved)))


def test_point_on_circle_is_projected_after_center_intersection_binding():
    body = (point('O', 0., 0.) + point('A', -3., 0.) + point('B', 3., 0.) + circle('k', 2)
            + command('Line', ['A', 'B'], ['g']) + element('line', 'g')
            + command('Intersect', ['g', 'k'], ['C', 'D']) + point('C', 2., 0.) + point('D', -2., 0.)
            + command('Circle', ['C', '1'], ['c']) + matrix('c', [1, 1, 3, 0, -2, 0])
            + command('Point', ['c'], ['P']) + point('P', 2., 1.))
    doc, items = imported(body)
    assert all(e['category'] == 'editable' for e in items.values())
    assert native.evaluate(doc).elements[eid(items, 'P')]['value'] == pytest.approx(dict(x=2., y=1.))
