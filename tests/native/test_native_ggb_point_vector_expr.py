"""Live source point/vector formulas and private Vector arguments."""
import math

import pytest

from animageo import native
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_rotate_angle import assert_helper, producer


def operands():
    return (point('A', 1., 2.) + point('B', 3., -1.) + point('O', 0., 0.)
            + element('numeric', 'a', extra='<value val="2"/>')
            + element('angle', 'α', extra=f'<value val="{math.pi / 3}"/>')
            + command('Vector', ['O', 'B'], ['v'])
            + element('vector', 'v', extra='<coords x="3" y="-1" z="0"/>')
            + expression('f', 'a*x^2', 'function') + element('function', 'f'))


@pytest.mark.parametrize('text, saved, moved', [
    ('A + v', (4., 1.), (7., 4.)), ('A + B', (4., 1.), (7., 4.)),
    ('(a, 4)', (2., 4.), (5., 4.)), ('2A − B', (-1., 5.), (5., 11.)),
    ('(x(A), y(v))', (1., -1.), (4., -1.)),
    ('(cos(α), sin(α))', (.5, math.sqrt(3) / 2), (.5, math.sqrt(3) / 2)),
    ('(1, f(2))', (1., 8.), (1., 20.)),
])
@pytest.mark.parametrize('kind', ['point', 'vector'])
def test_source_expression_and_dependencies_stay_live(kind, text, saved, moved):
    coords = f'<coords x="{saved[0]}" y="{saved[1]}" z="{1 if kind == "point" else 0}"/>'
    doc, items = imported(operands() + expression('P', text, kind) + element(kind, 'P', extra=coords))
    assert items['P']['category'] in (('editable',) if kind == 'point' else ('editable', 'differs')), items['P']
    assert producer(doc, eid(items, 'P'))['op'] == kind + '.expression'
    assert doc['operationRegistryVersion'] == '1.10'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 5.},
                                    eid(items, 'A'): {'kind': 'point', 'value': [4., 5.]}})
    value = ev.elements[eid(items, 'P')]['value']
    if kind == 'point':
        assert value == pytest.approx(dict(zip(('x', 'y'), moved)))
    else:
        assert value['a'] == [0., 0.]
        assert value['b'] == pytest.approx(moved)


@pytest.mark.parametrize('text', ['A / B', 'A + 1', '(a, 1, 2)', '(a; α)', '{A, B}',
                                  '(x(Midpoint[A, B]), 0)', 'x(A)'])
def test_unsupported_point_formula_has_source_and_no_free_copy(text):
    doc, items = imported(operands() + expression('P', text, 'point') + point('P', 1., 2.))
    assert items['P']['category'] != 'editable'
    assert items['P']['reason'] == 'formula_unsupported'
    assert text in items['P']['detail']
    assert not items['P']['native_ids']


def test_vector_coordinate_argument_is_owned_by_rotation():
    body = (operands() + command('Rotate', ['Vector[(a, 0)]', '90°', 'O'], ['u'])
            + element('vector', 'u', extra='<coords x="0" y="2" z="0"/>'))
    doc, items = imported(body)
    assert items['u']['category'] == 'editable', items['u']
    rotate = producer(doc, eid(items, 'u'))
    helper = rotate['args']['obj']['elementId']
    assert producer(doc, helper)['op'] == 'vector.expression'
    assert_helper(doc, helper, rotate['id'])
    changed = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': -3.}})
    assert changed.elements[eid(items, 'u')]['value']['b'] == pytest.approx([0., -3.])
    from animageo.native.edit import delete
    deleted = delete(doc, [eid(items, 'u')])
    assert helper not in deleted.document.elements


def test_constant_point_keeps_old_registry_and_saved_value():
    doc, items = imported(expression('P', '(sqrt(2), 0)', 'point') + point('P', math.sqrt(2), 0.))
    assert items['P']['category'] == 'editable'
    assert producer(doc, eid(items, 'P'))['op'] == 'point.free'
    assert doc['operationRegistryVersion'] == '1.0'
