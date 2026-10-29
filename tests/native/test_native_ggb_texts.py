"""Ordinary GGB TeX remains editable; unknown macros keep an explicit fallback."""
import pytest

from animageo import native
from tests.native.ggb_synth import command, element, expression, point
from tests.native.test_native_ggb_inline import eid, imported


def text(label, exp, *, latex=True, anchor='<startPoint x="1" y="2" z="1"/>', show=True):
    return expression(label, exp) + element('text', label, show=show,
        extra=anchor + f'<isLaTeX val="{str(latex).lower()}"/>')


def text_body():
    return (point('A', 1., 2.) + element('numeric', 'n', extra='<value val="3"/>')
            + text('t', r'"\[\dfrac{\alpha_1}{2} = " + n + "\]"', anchor='<startPoint exp="A"/>', show=False))


@pytest.mark.parametrize('source, expected', [
    (r'\frac{1}{2}+\sqrt{3}', r'$\frac{1}{2}+\sqrt{3}$'),
    (r'\[\dfrac{1}{2}\]', r'$\displaystyle \dfrac{1}{2}$'),
    (r'\(x_1^2\)', r'$x_1^2$'),
    ('Value $x_1$ is positive', 'Value $x_1$ is positive'),
    (r'\text{Value}\;\beta', r'$\text{Value}\;\beta$'),
])
def test_standard_tex_preserves_math_and_literal_braces(source, expected):
    doc, items = imported(text('t', '"' + source + '"'))
    t = items['t']
    assert t['category'] == 'editable' and t['value_check'] == 'passed'
    assert native.evaluate(doc).elements[eid(items, 't')]['value']['text'] == expected
    assert t['native_value']['text'] == expected
    helpers = set(doc['elements']) - {eid(items, 't')}
    assert len(helpers) == 1
    assert all(doc['appearance'][h]['visible'] is False and doc['appearance'][h]['locked'] for h in helpers)


def test_dynamic_math_keeps_refs_hidden_visibility_and_moving_anchor():
    doc, items = imported(text_body())
    assert all(i['category'] == 'editable' for i in items.values())
    assert set(items['t']['depends_on']) == {'n', 'A'}
    assert items['t']['hidden'] is True and doc['appearance'][eid(items, 't')]['visible'] is False
    ev = native.evaluate(doc, inputs={eid(items, 'n'): {'kind': 'number', 'value': 4.25},
                                     eid(items, 'A'): {'kind': 'point', 'value': [-2., 5.]}})
    t = ev.elements[eid(items, 't')]['value']
    assert t['text'] == r'$\displaystyle \dfrac{\alpha_1}{2} = 4.25$'
    assert t['anchor'] == [-2., 5.]
    op = doc['operations'][doc['elements'][eid(items, 't')]['producer']['operationId']]
    assert op['args']['refs']['items'] == [{'kind': 'ref', 'elementId': eid(items, 'n')}]


def test_dynamic_segment_length_uses_live_measure():
    body = (point('A', 0., 0.) + point('B', 3., 4.) + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's') + text('t', '"length = " + s', latex=False))
    doc, items = imported(body)
    assert items['t']['category'] == 'editable'
    assert native.evaluate(doc).elements[eid(items, 't')]['value']['text'] == 'length = 5'
    moved = native.evaluate(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [0., 6.]}})
    assert moved.elements[eid(items, 't')]['value']['text'] == 'length = 6'
    assert any(op['op'] == 'measure.length' for op in doc['operations'].values())


@pytest.mark.parametrize('source', [r'\myMacro{x}', r'\def\x{1}\x', r'\input{file}', r'\frac{1}{2', '$$x$$', '$x',
                                    'a & b', r'x % y', '#1', r'\frac{1}{2} \\ x', '\u202e', 'a\u200bb'])
def test_unknown_or_malformed_tex_has_reason_and_no_editable_copy(source):
    doc, items = imported(text('t', '"' + source + '"'))
    assert doc is None
    assert items['t']['category'] == 'picture' and items['t']['reason'] == 'latex_macros'
    assert items['t']['detail'] and items['t']['native_ids'] == []


def test_plain_text_with_control_characters_stays_a_picture():
    doc, items = imported(text('t', '"right\u202eleft"', latex=False))
    assert items['t']['category'] == 'picture' and items['t']['reason'] == 'fixed_text'
    assert items['t']['detail'] and items['t']['native_ids'] == []


@pytest.mark.parametrize('exp', ['"unterminated', '"x" + Unknown[n]', '"x" n'])
def test_unknown_text_expression_is_not_promoted(exp):
    doc, items = imported(text('t', exp))
    assert items['t']['category'] != 'editable'
    assert items['t']['native_ids'] == []


def test_stale_numeric_insert_is_not_declared_editable():
    body = (element('numeric', 'a', extra='<value val="2"/>') + expression('n', 'a+1')
            + element('numeric', 'n', extra='<value val="8"/>') + text('t', '"n=" + n'))
    doc, items = imported(body)
    assert items['n']['reason'] == 'value_mismatch'
    assert items['t']['category'] == 'picture' and items['t']['native_ids'] == []
    assert 'не совпадает' in items['t']['detail']


def test_script_on_text_keeps_script_refusal():
    body = text('t', '"x"').replace('</element>', '<ggbscript val="SetValue[n,1]"/></element>')
    _doc, items = imported(body)
    assert items['t']['category'] != 'editable' and items['t']['native_ids'] == []
