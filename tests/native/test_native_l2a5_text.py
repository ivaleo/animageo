"""text.free and its templates (docs/native/ops/text.free.md, registry 1.4, 1.8.1a5)."""
import math

import pytest

import animageo.native as native
from animageo.native.commands import parse_commands, print_commands
from animageo.native.expr import MAX_TEMPLATE_LENGTH, format_value, split_template, template_problems
from tests.native.conftest import DocBuilder, num, number_input, point_input, ref, ref_list


class TestTemplate:
    def test_split(self):
        assert split_template('a = {0}, b = {1}') == [('text', 'a = '), ('ref', 0), ('text', ', b = '), ('ref', 1)]
        assert split_template('{{x}} {12}{0}') == [('text', '{x} '), ('ref', 12), ('ref', 0)]
        assert split_template('') == []
        assert split_template('Дано: {{ABC}}') == [('text', 'Дано: {ABC}')]

    @pytest.mark.parametrize('template, text', [
        ('a {', 'column 3: an unclosed {'),
        ('a } b', 'column 3: a lone }'),
        ('{x}', 'column 1: an insert is {k}'),
        ('{ 0}', 'an insert is {k}'),
        ('{-1}', 'an insert is {k}'),
        ('{01}', 'an insert is {k}'),
        ('{}', 'an insert is {k}'),
        ('{٣}', 'an insert is {k}'),            # not an ASCII digit
        ('{0}{1}{2}', 'insert {2} is outside refs (2 items)'),
        (7, 'a template must be a string'),
        ('я' * (MAX_TEMPLATE_LENGTH + 1), 'longer than 1000'),
    ])
    def test_problems(self, template, text):
        found = template_problems(template, 2)
        assert len(found) == 1 and text in found[0], found

    def test_valid(self):
        assert template_problems('я' * MAX_TEMPLATE_LENGTH, 0) == []
        assert template_problems('{0}{1}', 2) == []
        assert template_problems('{5}') == []                   # no ref count: no range check

    @pytest.mark.parametrize('value, decimals, text', [
        (0.125, 2, '0.12'),            # an exact tie: half to even
        (0.375, 2, '0.38'),
        (2.5, 0, '2'),
        (-2.5, 0, '-2'),
        (3.5, 0, '4'),
        (1.005, 2, '1'),               # the binary value of 1.005 is below the tie
        (2.0, 2, '2'),
        (1.5, 3, '1.5'),
        (-0.004, 2, '0'),
        (-0.0, 2, '0'),
        (123456.789, 1, '123456.8'),
        (1e15, 2, '1e+15'),
        (-2.5e20, 2, '-2.5e+20'),
        (999999999999999.9, 0, '1000000000000000'),
    ])
    def test_format_value(self, value, decimals, text):
        assert format_value(value, decimals) == text


def text_doc(template, *refs, decimals=None, anchor='A'):
    b = DocBuilder('text_doc', registry_version='1.4')
    b.free('A', 1, 2).free('V', 0, 0).free('C', 4, 0)
    b.number('a', 0.125)
    b.angle('ang', 'C', 'V', 'A')
    b.op('op_m', 'measure.angle', {'angle': ref('ang')}, [('number', 'm', 'number')])
    args = {'text': {'kind': 'template', 'value': template}, 'anchor': ref(anchor), 'refs': ref_list(*refs)}
    if decimals is not None:
        args['decimals'] = num(decimals)
    b.op('op_t', 'text.free', args, [('text', 't', 'text')])
    return b


class TestTextFree:
    def test_value(self):
        doc = text_doc('a = {0}, угол = {1}, A{2} {{x}}', 'a', 'm', 'A').doc
        assert native.validate(doc) == []
        t = native.evaluate(doc).elements['t']
        size = math.degrees(math.atan2(2, 1))
        assert t['value'] == {
            'anchor': [1.0, 2.0],
            'text': f'a = 0.12, угол = {size:.2f}°, A(1, 2) {{x}}',
            'parts': [{'text': 'a = '}, {'ref': 0, 'text': '0.12'}, {'text': ', угол = '},
                      {'ref': 1, 'text': f'{size:.2f}°'}, {'text': ', A'}, {'ref': 2, 'text': '(1, 2)'},
                      {'text': ' {x}'}],
        }

    def test_the_text_follows_the_construction(self):
        doc = text_doc('{0} at {1}', 'a', 'A', anchor='V').doc
        t = native.evaluate(doc, inputs={'a': number_input(3.14159), 'A': point_input(-1, 0.5),
                                         'V': point_input(5, 5)}).elements['t']
        assert t['value']['text'] == '3.14 at (-1, 0.5)' and t['value']['anchor'] == [5.0, 5.0]

    @pytest.mark.parametrize('decimals, ok', [(0, True), (10, True), (2.0, True), (-1, False), (11, False),
                                              (1.5, False)])
    def test_decimals(self, decimals, ok):
        t = native.evaluate(text_doc('{0}', 'a', decimals=decimals).doc).elements['t']
        assert (t['state'] == 'defined') == ok
        if not ok:
            assert t['reason'] == 'invalid_parameter'

    def test_a_bad_template(self):
        doc = text_doc('a = {1}', 'a').doc
        issues = native.validate(doc)
        assert [(i.code, i.path) for i in issues] == [('formula', '/operations/op_t/args/text/value')]
        t = native.evaluate(doc).elements['t']
        assert (t['state'], t['reason']) == ('error', 'formula')

    def test_kinds_and_types(self):
        b = text_doc('x', 'a')
        b.doc['operations']['op_t']['args']['text'] = {'kind': 'number', 'value': 1}
        assert [i.code for i in native.validate(b.doc)] == ['type_mismatch']
        assert native.evaluate(b.doc).elements['t']['reason'] == 'type_mismatch'
        b = text_doc('{0}', 'ang')                     # an angle element is not insertable
        assert [i.code for i in native.validate(b.doc)] == ['type_mismatch']
        b = text_doc('x')
        b.doc['operations']['op_m']['args']['angle'] = {'kind': 'template', 'value': 'x'}
        assert 'type_mismatch' in [i.code for i in native.validate(b.doc)]

    def test_upstream(self):
        b = text_doc('{0}', 'a')
        b.doc['inputs']['a'] = {'kind': 'number', 'value': 1}
        b.doc['operations']['op_a']['args'] = {'min': num(2), 'max': num(1)}
        t = native.evaluate(b.doc).elements['t']
        assert (t['state'], t['reason'], t['cause']) == ('undefined', 'upstream', 'a')

    def test_commands_print_and_keep(self):
        doc = text_doc('a = "{0}"', 'a').doc
        printed = print_commands(doc)
        assert printed.text.splitlines()[-1] == 't = Текст("a = \\"{0}\\"", A, a)'
        assert [i.code for i in printed.issues] == ['unprintable_operation']
        result = parse_commands(printed.text, base=doc)
        assert [i.code for i in result.issues] == ['syntax']
        assert native.canonical_json(result.document.data) == native.canonical_json(doc)
