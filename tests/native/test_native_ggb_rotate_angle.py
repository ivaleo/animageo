"""C0: the angle of ``Rotate(P, <expression>, O)`` — angle arithmetic of a ``.ggb`` — is a hidden
``number.expression``; a figure angle in it is a hidden ``measure.angle``. Every helper of the import
has no name, ``role: aux`` and ``origin: {kind: auto, source: <host operation>}``."""
import math

import pytest

from animageo import native
from tests.native.ggb_synth import command, element, point
from tests.native.test_native_ggb_inline import eid, imported

THETA = math.pi / 6
ALPHA = math.radians(100)
DEG = {'op': '/', 'args': [{'const': 'pi'}, {'num': 180.0}]}


def rot(x, y, a, cx=0., cy=0.):
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)


def slider_body(argument='(-theta)', angle=-THETA, kind='angle'):
    return (point('A', 1., 0.) + point('O', 0., 0.) + element(kind, 'theta', extra=f'<value val="{THETA!r}"/>')
            + command('Rotate', ['A', argument, 'O'], ['Q']) + point('Q', *rot(1., 0., angle)))


def figure_body(argument='(4 * (α_{2} - 90°))', angle=4 * (ALPHA - math.pi / 2)):
    return (point('A', 1., 0.) + point('B', 2., 0.) + point('C', 0., 0.)
            + point('D', 2 * math.cos(ALPHA), 2 * math.sin(ALPHA))
            + command('Angle', ['B', 'C', 'D'], ['α_{2}']) + element('angle', 'α_{2}', extra=f'<value val="{ALPHA!r}"/>')
            + command('Rotate', ['A', argument, 'C'], ["I'"]) + point("I'", *rot(1., 0., angle)))


def producer(doc, element_id):
    return doc['operations'][doc['elements'][element_id]['producer']['operationId']]


def helper_chain(doc, host):
    """The operations behind the angle of the rotation ``host`` (element ID), angle first."""
    rotate = producer(doc, host)
    assert rotate['op'] == 'transform.rotate'
    angle = rotate['args']['angle']['elementId']
    formula = producer(doc, angle)
    measures = [producer(doc, r['elementId']) for r in formula['args']['refs']['items']
                if doc['elements'][r['elementId']]['type'] == 'number'
                and producer(doc, r['elementId'])['op'] == 'measure.angle']
    return rotate, angle, formula, measures


def assert_helper(doc, element_id, host_op):
    el = doc['elements'][element_id]
    assert el['displayName'] == ''
    assert el['origin'] == {'kind': 'auto', 'source': host_op}
    assert doc['appearance'][element_id] == {'visible': False, 'locked': True, 'role': 'aux',
                                             'label': {'mode': 'none'}}
    assert element_id not in doc['inputs']


def test_negated_angle_slider_is_a_hidden_formula():
    doc, items = imported(slider_body())
    assert items['Q']['category'] == 'editable'
    assert items['Q']['value_check'] == 'passed'
    assert items['Q']['depends_on'] == ['A', 'theta', 'O']
    rotate, angle, formula, measures = helper_chain(doc, eid(items, 'Q'))
    assert formula['op'] == 'number.expression' and measures == []
    assert formula['args']['expr']['ast'] == {'op': 'neg', 'args': [{'ref': 0}]}
    assert formula['args']['refs']['items'] == [{'kind': 'ref', 'elementId': eid(items, 'theta')}]
    assert all(e['native_ids'] != [angle] for e in items.values())
    assert_helper(doc, angle, rotate['id'])
    assert native.validate(doc) == []
    moved = native.evaluate(doc, inputs={eid(items, 'theta'): {'kind': 'angle', 'value': math.pi / 2}})
    assert moved.elements[eid(items, 'Q')]['value'] == pytest.approx(dict(x=0., y=-1.), abs=1e-12)


def test_figure_angle_operand_is_a_hidden_measure():
    doc, items = imported(figure_body())
    assert items["I'"]['category'] == 'editable'
    assert items["I'"]['value_check'] == 'passed'
    rotate, angle, formula, measures = helper_chain(doc, eid(items, "I'"))
    assert formula['args']['expr']['ast'] == {'op': '*', 'args': [
        {'num': 4.0}, {'op': '-', 'args': [{'ref': 0}, {'op': '*', 'args': [{'num': 90.0}, DEG]}]}]}
    [measure] = measures
    assert measure['args'] == {'angle': {'kind': 'ref', 'elementId': eid(items, 'α_{2}')}}
    for helper in (angle, measure['outputs'][0]['elementId']):
        assert_helper(doc, helper, rotate['id'])
    assert doc['operationRegistryVersion'] == '1.4'
    assert native.validate(doc) == []
    beta = math.radians(120)
    moved = native.evaluate(doc, inputs={eid(items, 'D'): {'kind': 'point', 'value': [math.cos(beta), math.sin(beta)]}})
    x, y = rot(1., 0., 4 * (beta - math.pi / 2))
    assert moved.elements[eid(items, "I'")]['value'] == pytest.approx(dict(x=x, y=y), abs=1e-12)


@pytest.mark.parametrize('argument, angle', [
    ('(-theta + 30°)', -THETA + math.pi / 6), ('(2 * theta)', 2 * THETA), ('(theta / 2)', THETA / 2),
    ('(theta - 10°)', THETA - math.pi / 18), ('(180° - theta)', math.pi - THETA),
])
def test_angle_arithmetic_of_a_slider(argument, angle):
    doc, items = imported(slider_body(argument, angle))
    assert items['Q']['category'] == 'editable', items['Q']
    assert items['Q']['value_check'] == 'passed'


def test_saved_image_is_the_value_check():
    doc, items = imported(slider_body(angle=THETA))          # the file saved the image of +θ
    assert items['Q']['category'] == 'differs'
    assert items['Q']['value_check'] == 'failed'


@pytest.mark.parametrize('argument', ['(floor(theta))', '(theta * A)', '(x(A) * 1°)'])
def test_an_expression_outside_the_formulas_is_refused_explicitly(argument):
    doc, items = imported(slider_body(argument))
    assert items['Q']['category'] != 'editable'
    assert items['Q']['reason'] == 'formula_unsupported'
    assert items['Q']['native_ids'] == [] or items['Q']['category'] == 'picture'
    assert not any(op['op'] == 'transform.rotate' for op in (doc or {'operations': {}})['operations'].values())


def test_a_numeric_slider_keeps_its_translation_and_gets_the_helper_rule():
    doc, items = imported(slider_body(kind='numeric'))
    assert items['Q']['category'] == 'editable'
    rotate, angle, formula, measures = helper_chain(doc, eid(items, 'Q'))
    assert formula['args']['expr']['ast'] == {'op': 'neg', 'args': [{'ref': 0}]}
    assert_helper(doc, angle, rotate['id'])
