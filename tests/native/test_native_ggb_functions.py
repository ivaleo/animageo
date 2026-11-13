"""Source function grammar: independent AST and mathematical expectations."""
import math
import copy
import json
from pathlib import Path

import pytest

from animageo.native.convert.ggb_expr import ExprError, MAX_CHARS, parse_number
from animageo.native.expr.evaluate import ExprError as EvaluationError
from animageo.native.expr.function import compile_function


def parsed(text, kinds=None, *, label='f'):
    # Import inside the test call: a missing implementation fails each test,
    # without preventing collection of the independent refusal controls.
    from animageo.native.convert.ggb_function import parse_function
    return parse_function(text, kinds or {}, label=label)


@pytest.mark.parametrize('text', ['a*x²', 'f(x) = a*x²', 'f(t) = a*t²', 'y = a*x²'])
def test_function_header_and_formal_variable(text):
    spec = parsed(text, {'a': 'numeric'})
    assert spec.ast == {'op': '*', 'args': [
        {'ref': 0}, {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]}
    assert spec.refs == ['a']
    assert list(spec.domain) == [None, None]
    f = compile_function(spec.ast, [3.0])
    assert [f(x) for x in (-2.0, 0.0, 4.0)] == [12.0, 0.0, 48.0]


def test_function_definition_does_not_rename_object_names():
    spec = parsed('f(t) = t_1*t² + t_10', {'t_1': 'numeric', 't_10': 'numeric'})
    assert spec.refs == ['t_1', 't_10']
    assert spec.ast == {'op': '+', 'args': [
        {'op': '*', 'args': [
            {'ref': 0}, {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]},
        {'ref': 1}]}
    assert compile_function(spec.ast, [2.0, 5.0])(3.0) == 23.0


def test_function_refs_keep_first_appearance_and_source_identity():
    spec = parsed('b*x + a + b', {'a': 'numeric', 'b': 'numeric'})
    assert spec.refs == ['b', 'a']
    assert spec.ast == {'op': '+', 'args': [
        {'op': '+', 'args': [
            {'op': '*', 'args': [{'ref': 0}, {'var': 'x'}]}, {'ref': 1}]},
        {'ref': 0}]}
    # Equal current values do not permit merging a and b into one reference.
    assert compile_function(spec.ast, [2.0, 2.0])(3.0) == 10.0
    assert compile_function(spec.ast, [2.0, 5.0])(3.0) == 13.0


def test_function_formal_scope_does_not_hide_other_numeric_names():
    spec = parsed('f(x) = t*x', {'t': 'numeric'})
    assert spec.refs == ['t']
    assert spec.ast == {'op': '*', 'args': [{'ref': 0}, {'var': 'x'}]}


@pytest.mark.parametrize('text, ast, x, expected', [
    ('1/2x', {'op': '*', 'args': [
        {'op': '/', 'args': [{'num': 1.0}, {'num': 2.0}]}, {'var': 'x'}]}, 4.0, 2.0),
    ('-x^2', {'op': 'neg', 'args': [
        {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]}, 3.0, -9.0),
    ('x^2^3', {'op': '^', 'args': [
        {'var': 'x'}, {'op': '^', 'args': [{'num': 2.0}, {'num': 3.0}]}]}, 2.0, 256.0),
])
def test_function_arithmetic_preserves_source_evaluation_order(text, ast, x, expected):
    spec = parsed(text)
    assert spec.ast == ast
    assert compile_function(spec.ast)(x) == expected


@pytest.mark.parametrize('text', [
    'If(x < 0, sqrt(-x), sqrt(x))',
    'If[x < 0, sqrt(-x), sqrt(x)]',
])
def test_if_is_lazy_and_preserves_conditions(text):
    spec = parsed(text)
    assert spec.ast == {'if': [
        {'cmp': '<', 'args': [{'var': 'x'}, {'num': 0.0}]},
        {'fn': 'sqrt', 'args': [{'op': 'neg', 'args': [{'var': 'x'}]}]},
        {'fn': 'sqrt', 'args': [{'var': 'x'}]}]}
    f = compile_function(spec.ast)
    assert [f(x) for x in (-9.0, 0.0, 16.0)] == [3.0, 0.0, 4.0]


def test_if_without_else_stays_undefined_outside_condition():
    spec = parsed('If(x >= 0, sqrt(x))')
    assert spec.ast == {'if': [
        {'cmp': '>=', 'args': [{'var': 'x'}, {'num': 0.0}]},
        {'fn': 'sqrt', 'args': [{'var': 'x'}]}]}
    f = compile_function(spec.ast)
    assert f(4.0) == 2.0
    with pytest.raises(EvaluationError) as exc:
        f(-1.0)
    assert exc.value.reason == 'out_of_domain'


def test_if_chained_comparisons_and_logical_precedence():
    spec = parsed('If(-1 ≤ x ≤ 1 || x > 4 && !(x ≥ 6), x, 0)')
    assert spec.ast == {'if': [
        {'or': [
            {'and': [
                {'cmp': '<=', 'args': [{'num': -1.0}, {'var': 'x'}]},
                {'cmp': '<=', 'args': [{'var': 'x'}, {'num': 1.0}]}]},
            {'and': [
                {'cmp': '>', 'args': [{'var': 'x'}, {'num': 4.0}]},
                {'not': [{'cmp': '>=', 'args': [{'var': 'x'}, {'num': 6.0}]}]}]}]},
        {'var': 'x'}, {'num': 0.0}]}
    f = compile_function(spec.ast)
    assert [f(x) for x in (-2.0, -1.0, 1.0, 4.0, 5.0, 6.0)] == [0.0, -1.0, 1.0, 0.0, 5.0, 0.0]


def test_if_nested_and_grouped_arithmetic_condition():
    spec = parsed('If(((x + 1) < 0), -1, If[x > 0, 1, 0])')
    assert spec.ast == {'if': [
        {'cmp': '<', 'args': [
            {'op': '+', 'args': [{'var': 'x'}, {'num': 1.0}]}, {'num': 0.0}]},
        {'num': -1.0}, {'if': [
            {'cmp': '>', 'args': [{'var': 'x'}, {'num': 0.0}]}, {'num': 1.0}, {'num': 0.0}]}]}
    f = compile_function(spec.ast)
    assert [f(x) for x in (-2.0, -1.0, 0.0, 2.0)] == [-1.0, 0.0, 0.0, 1.0]


@pytest.mark.parametrize('text, x, expected', [
    ('If(x < 0 || sqrt(x) > 1, 7, 0)', -1.0, 7.0),
    ('If(x > 0 && 1/x > 0, 7, 0)', 0.0, 0.0),
    ('If(x < 0, 1/0, 5)', 1.0, 5.0),
])
def test_if_does_not_evaluate_unchosen_branch_or_condition(text, x, expected):
    assert compile_function(parsed(text).ast)(x) == expected


def test_function_numeric_angle_ref_remains_a_reference():
    spec = parsed('sin(α) + x', {'α': 'angle'})
    assert spec.refs == ['α']
    assert spec.ast == {'op': '+', 'args': [
        {'fn': 'sin', 'args': [{'ref': 0}]}, {'var': 'x'}]}
    assert compile_function(spec.ast, [math.pi / 2])(2.0) == 3.0


@pytest.mark.parametrize('text', [
    'g(x) = x²', 'f(x,y) = x+y', 'x+y = 1', 'x = y', 'y = x = 1',
    'If(x = 0, 1, 2)', 'If(x == 0, 1, 2)', 'If(x != 0, 1, 2)',
    'If(x ≤ 0, x < 1, 2)', 'x < 1', 'If(x, 1, 2)',
    'If(x < 0, 1, 2, 3)', 'If(x < 0)',
    'g(x)', 'h(x)', 'x(A)', 'A + x', 'f(x)', 'Derivative(x²)',
    'Solve(x² = 1)', 'floor(x)', 'random()', '{x,1}', '[x,1]',
    '"x"', "'x'", '__import__(x)', 'x.__class__', 'x;1', 'x\nimport os',
])
def test_function_parser_rejects_unsupported_source_forms(text):
    with pytest.raises(ExprError) as exc:
        parsed(text, {'g': 'function', 'A': 'point'})
    assert exc.value.reason in ('formula_unsupported', 'parse_error')


@pytest.mark.parametrize('text', [
    'x' * (MAX_CHARS + 1), '(' * 40 + 'x' + ')' * 40,
    '+' * 200 + 'x', '-' * 40 + 'x', 'x^65', 'x⁶⁵',
    '+'.join(['(' + '+'.join(['x'] * 8) + ')'] * 17),
    'If(x < 0, ' * 40 + 'x' + ', 0)' * 40,
])
def test_function_parser_rejects_bounded_work_overflow(text):
    with pytest.raises(ExprError) as exc:
        parsed(text)
    assert exc.value.reason == 'formula_unsupported'


@pytest.mark.parametrize('text', ['If(a < 0, 1, 2)', 'a < 0', 'a && b'])
def test_number_parser_default_does_not_gain_conditions(text):
    with pytest.raises(ExprError):
        parse_number(text, {'a': 'numeric', 'b': 'numeric'})


# Task 3: the importer, not a handwritten native document, must create these.
from animageo import native
from animageo.native.kernel.function import evaluator
from tests.native.ggb_synth import command, element, expression, ggb_bytes, ggb_xml, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_l5_ggb import NS, _check


def number(label, value):
    return element('numeric', label, extra=f'<value val="{value}"/>')


def function_source(body, label='f', *, type_=None):
    return expression(label, body, type_) + element('function', label)


def operation(doc, items, name):
    el = doc['elements'][eid(items, name)]
    return doc['operations'][el['producer']['operationId']]


def function_value(doc, items, name='f', *, inputs=None):
    state = native.evaluate(doc, inputs=inputs).elements[eid(items, name)]
    assert state['state'] == 'defined', state
    return state['value']


@pytest.mark.parametrize('type_', [None, 'function'])
@pytest.mark.parametrize('body', ['a*x²', 'f(t) = a*t²'])
def test_numeric_reference_moves_function_without_freezing(type_, body):
    doc, items = imported(number('a', 2) + function_source(body, type_=type_))
    assert items['f']['category'] == 'editable'
    assert items['f']['value_check'] == 'passed'
    assert items['f']['depends_on'] == ['a']
    op = operation(doc, items, 'f')
    assert op['op'] == 'function.expr'
    assert op['args']['expr']['ast'] == {'op': '*', 'args': [
        {'ref': 0}, {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]}
    assert op['args']['refs'] == {'kind': 'list', 'items': [{'kind': 'ref', 'elementId': eid(items, 'a')}]}
    assert eid(items, 'f') not in doc['inputs']
    assert items['f']['ggb_value'] == {'kind': 'function', 'value': {
        'expr': op['args']['expr']['ast'], 'refs': [2.0], 'domain': [None, None]}}
    for value, want in [(3.0, 12.0), (-1.0, -4.0), (0.0, 0.0), (2.0, 8.0)]:
        fn = function_value(doc, items, inputs={eid(items, 'a'): {'kind': 'number', 'value': value}})
        assert evaluator(fn)(2.0) == want


def test_equal_numeric_values_keep_distinct_references():
    doc, items = imported(number('a', 2) + number('b', 2) + function_source('b*x + a'))
    assert items['f']['category'] == 'editable'
    assert items['f']['depends_on'] == ['b', 'a']
    assert operation(doc, items, 'f')['args']['refs']['items'] == [
        {'kind': 'ref', 'elementId': eid(items, 'b')}, {'kind': 'ref', 'elementId': eid(items, 'a')}]
    assert evaluator(function_value(doc, items))(3.0) == 8.0
    assert evaluator(function_value(doc, items, inputs={
        eid(items, 'a'): {'kind': 'number', 'value': 5.0}}))(3.0) == 11.0
    assert evaluator(function_value(doc, items, inputs={
        eid(items, 'b'): {'kind': 'number', 'value': 5.0}}))(3.0) == 17.0


def test_plain_function_is_unbounded_and_view_independent():
    source = ggb_xml(function_source('x²'))
    docs = []
    for scale, zero in [(50, 400), (1, 20), (900, 600)]:
        xml = source.replace(b'scale="50"', f'scale="{scale}"'.encode()).replace(
            b'xZero="400"', f'xZero="{zero}"'.encode())
        doc, rep = native.from_ggb(ggb_bytes(xml=xml), id_namespace=NS)
        _check(doc, rep)
        items = {e['ggb_name']: e for e in rep['elements']}
        assert items['f']['category'] == 'editable'
        op = operation(doc, items, 'f')
        assert 'min' not in op['args'] and 'max' not in op['args']
        fn = function_value(doc, items)
        assert fn['domain'] == [None, None]
        assert [evaluator(fn)(x) for x in (-10000., 10000.)] == [100000000., 100000000.]
        docs.append(op['args'])
    assert docs[0] == docs[1] == docs[2]


def test_function_depends_on_live_number_expression():
    body = (number('a', 4) + expression('b', 'sqrt(a)') + number('b', 2)
            + function_source('b*x'))
    doc, items = imported(body)
    assert items['b']['category'] == items['f']['category'] == 'editable'
    assert operation(doc, items, 'b')['op'] == 'number.expression'
    assert operation(doc, items, 'f')['args']['refs']['items'] == [
        {'kind': 'ref', 'elementId': eid(items, 'b')}]
    assert evaluator(function_value(doc, items, inputs={
        eid(items, 'a'): {'kind': 'number', 'value': 9.0}}))(3.0) == 9.0


def test_if_undefined_branch_and_upstream():
    body = (number('a', 4) + expression('b', 'sqrt(a)') + number('b', 2)
            + function_source('If(x >= 0, b*sqrt(x))'))
    doc, items = imported(body)
    assert items['f']['category'] == 'editable'
    assert evaluator(function_value(doc, items))(-1.0) is None
    assert evaluator(function_value(doc, items))(9.0) == 6.0
    bad = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': -1.0}})
    assert bad.elements[eid(items, 'b')]['state'] == 'undefined'
    assert bad.elements[eid(items, 'f')]['state'] == 'undefined'
    assert bad.elements[eid(items, 'f')]['reason'] == 'upstream'
    assert 'value' not in bad.elements[eid(items, 'f')]
    recovered = function_value(doc, items, inputs={eid(items, 'a'): {'kind': 'number', 'value': 9.0}})
    assert evaluator(recovered)(9.0) == 9.0


def test_inline_literal_restriction_preserves_domain():
    body = (number('a', 2) + command('Function', ['a*x²', '-sqrt(4)', '2π'], ['f'])
            + element('function', 'f'))
    doc, items = imported(body)
    assert items['f']['category'] == 'editable'
    assert items['f']['depends_on'] == ['a']
    op = operation(doc, items, 'f')
    assert op['args']['min'] == {'kind': 'number', 'value': -2.0}
    assert op['args']['max']['value'] == pytest.approx(2 * math.pi)
    fn = function_value(doc, items)
    assert fn['domain'] == pytest.approx([-2.0, 2 * math.pi])
    assert evaluator(fn)(-3.0) is None
    assert evaluator(fn)(0.0) == 0.0
    assert evaluator(fn)(7.0) is None
    moved = function_value(doc, items, inputs={eid(items, 'a'): {'kind': 'number', 'value': 3.0}})
    assert moved['domain'] == fn['domain']
    assert evaluator(moved)(2.0) == 12.0


@pytest.mark.parametrize('inputs', [
    ['x²', 'a', '3'], ['x²', '-1', 'a'], ['x²', 'a-a-1', '3'],
    ['g', '-1', '3'], ['x²', '1/0', '3'], ['x²', '-1', '1E309'],
])
def test_dynamic_domain_and_function_reference_are_refused(inputs):
    body = (number('a', 2) + function_source('x²', 'g') + command('Function', inputs, ['f'])
            + element('function', 'f'))
    doc, items = imported(body)
    assert items['g']['category'] == 'editable'
    assert items['f']['category'] == 'unsupported'
    assert items['f']['reason'] in ('formula_unsupported', 'unsupported_signature', 'parse_error')
    assert items['f']['native_ids'] == []


def test_non_numeric_angle_element_is_not_coerced_to_number():
    body = (point('A', 1., 0.) + point('B', 0., 0.) + point('C', 0., 1.)
            + command('Angle', ['A', 'B', 'C'], ['α'])
            + element('angle', 'α', extra=f'<value val="{math.pi / 2}"/>')
            + function_source('sin(α) + x'))
    doc, items = imported(body)
    assert items['α']['category'] == 'editable'
    assert items['f']['category'] == 'unsupported'
    assert items['f']['reason'] == 'formula_unsupported'
    assert items['f']['native_ids'] == []


def test_function_report_requires_source_verified_bindings():
    from animageo.native.convert.ggb_function import FunctionSpec, verify_function
    ast = {'if': [{'cmp': '<', 'args': [{'var': 'x'}, {'num': 0.0}]}, {'ref': 0}, {'ref': 1}]}
    spec = FunctionSpec(copy.deepcopy(ast), ['a', 'b'], [-2.0, 3.0])
    value = {'expr': copy.deepcopy(ast), 'refs': [2.0, 2.0], 'domain': [-2.0, 3.0]}
    args = (spec, value, ['id-a', 'id-b'], ['id-a', 'id-b'], [2.0, 2.0], 10.0)
    assert verify_function(*args) == ('passed', 0.0)
    for key, replacement in [
        ('expr', {'ref': 0}),  # lose the source If condition
        ('expr', {'if': [{'cmp': '>', 'args': [{'var': 'x'}, {'num': 0.0}]}, {'ref': 0}, {'ref': 1}]}),
        ('expr', {'if': [{'cmp': '<', 'args': [{'var': 't'}, {'num': 0.0}]}, {'ref': 0}, {'ref': 1}]}),
        ('domain', [None, None]), ('domain', [-2.0, 4.0]),
        ('refs', [2.0]), ('refs', [2.0, 3.0]),
    ]:
        changed = {**copy.deepcopy(value), key: replacement}
        assert verify_function(spec, changed, *args[2:])[0] == 'failed', (key, replacement)
    for wrong_ids in (['id-b', 'id-a'], ['id-a', 'id-a'], ['id-a'], ['id-a', 'id-other']):
        assert verify_function(spec, value, wrong_ids, *args[3:])[0] == 'failed'
    for index in (0, 3, 4):  # missing source spec, source mapping, source numeric values
        missing = list(args)
        missing[index] = None
        assert verify_function(*missing) == ('not_checked', None)
    assert verify_function(spec, value, args[2], args[3], [2.0, None], 10.0) == ('not_checked', None)
    assert verify_function(spec, None, *args[2:])[0] == 'failed'
    # Reuse the existing import tolerance for numbers; structure has no tolerance.
    almost = {**value, 'refs': [2.0 + 1e-8, 2.0]}
    assert verify_function(spec, almost, *args[2:])[0] == 'passed'


def test_unchecked_function_source_remains_differs(monkeypatch):
    from animageo.native.convert import ggb_function
    original = ggb_function.read_functions

    def without_numeric_source(infos, norm, ctx):
        original(infos, norm, ctx)
        ctx.expected.pop(norm['a'], None)

    monkeypatch.setattr(ggb_function, 'read_functions', without_numeric_source)
    _doc, items = imported(number('a', 2) + function_source('a*x'))
    assert items['f']['category'] == 'differs'
    assert items['f']['reason'] == 'value_unchecked'
    assert items['f']['value_check'] == 'not_checked'


def test_from_construction_does_not_claim_ggb_function_support():
    from animageo.geo.construction import Construction
    from animageo.parsers import dsl
    constr = Construction()
    dsl.run(constr, 'f = Function("y = x^2")')
    _doc, report = native.from_construction(constr, mode='partial', id_namespace=NS)
    item = next(e for e in report['elements'] if e['display'] == 'f')
    assert item['category'] == 'unsupported'
    assert item['native_ids'] == []


def test_formal_parameter_is_not_a_dependency_on_same_named_object():
    doc, items = imported(number('t', 99) + number('t_1', 3) + function_source('f(t) = t_1*t²'))
    assert items['f']['category'] == 'editable'
    assert items['f']['depends_on'] == ['t_1']
    assert operation(doc, items, 'f')['args']['refs']['items'] == [
        {'kind': 'ref', 'elementId': eid(items, 't_1')}]
    assert evaluator(function_value(doc, items))(2.0) == 12.0


FUNCTION_FIXTURE = Path(__file__).with_name('import') / 'scenes' / 'ggb_functions.json'


def function_fixture():
    """Actual importer document + anonymous source + independent expectations.

    Regenerate only this file, explicitly, after a successful targeted test:
    import this helper and JSON-serialize its return value to FUNCTION_FIXTURE.
    Existing curve/expr fixtures are unrelated and must not be regenerated.
    """
    body = (number('a', 2) + number('b', 2) + function_source('f(t) = a*t² + b')
            + function_source('If(x < 0, sqrt(-x), sqrt(x))', 'p')
            + function_source('If(x >= 0, sqrt(x))', 'q')
            + command('Function', ['a*x', '-2', '3'], ['r']) + element('function', 'r')
            + expression('u', 'sqrt(a)') + number('u', math.sqrt(2)) + function_source('u*x', 'h')
            + function_source('1/(x-a)', 'g')
            + command('Point', ['f'], ['P']) + point('P', 3., 20.)
            + point('A', 0., 0.) + command('Midpoint', ['P', 'A'], ['M']) + point('M', 1.5, 10.)
            + command('Point', ['g'], ['G']) + point('G', 3., 1.)
            + command('Point', ['h'], ['H']) + point('H', 1., math.sqrt(2)))
    source = ggb_xml(body)
    doc, report = native.from_ggb(ggb_bytes(xml=source), id_namespace=NS)
    _check(doc, report)
    assert all(e['category'] == 'editable' for e in report['elements'])
    ids = {e['ggb_name']: e['native_ids'][0] for e in report['elements']}
    f_ast = {'op': '+', 'args': [
        {'op': '*', 'args': [{'ref': 0}, {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]},
        {'ref': 1}]}
    return {'format': 'animageo-parity/v1', 'id': 'ggb_functions', 'document': doc,
            'source': {'xml': source.decode(), 'namespace': str(NS)}, 'sourceIds': ids,
            'expectedDefinitions': {
                'f': {'expr': f_ast, 'refs': ['a', 'b'], 'domain': [None, None]},
                'p': {'expr': {'if': [
                    {'cmp': '<', 'args': [{'var': 'x'}, {'num': 0.0}]},
                    {'fn': 'sqrt', 'args': [{'op': 'neg', 'args': [{'var': 'x'}]}]},
                    {'fn': 'sqrt', 'args': [{'var': 'x'}]}]}, 'refs': [], 'domain': [None, None]},
                'q': {'expr': {'if': [
                    {'cmp': '>=', 'args': [{'var': 'x'}, {'num': 0.0}]},
                    {'fn': 'sqrt', 'args': [{'var': 'x'}]}]}, 'refs': [], 'domain': [None, None]},
                'r': {'expr': {'op': '*', 'args': [{'ref': 0}, {'var': 'x'}]},
                      'refs': ['a'], 'domain': [-2.0, 3.0]},
                'h': {'expr': {'op': '*', 'args': [{'ref': 0}, {'var': 'x'}]},
                      'refs': ['u'], 'domain': [None, None]},
                'g': {'expr': {'op': '/', 'args': [
                    {'num': 1.0}, {'op': '-', 'args': [{'var': 'x'}, {'ref': 0}]}]},
                      'refs': ['a'], 'domain': [None, None]}},
            'cases': [
                {'name': 'saved', 'samples': {
                    'f': [[-10000., 200000002.], [0., 2.], [10000., 200000002.]],
                    'p': [[-4., 2.], [0., 0.], [9., 3.]], 'q': [[-1., None], [4., 2.]],
                    'r': [[-3., None], [-2., -4.], [2., 4.], [4., None]], 'h': [[2., 2 * math.sqrt(2)]]},
                 'expectedStates': {
                     'P': {'state': 'defined', 'value': {'x': 3., 'y': 20.}},
                     'M': {'state': 'defined', 'value': {'x': 1.5, 'y': 10.}},
                     'G': {'state': 'defined', 'value': {'x': 3., 'y': 1.}},
                     'H': {'state': 'defined', 'value': {'x': 1., 'y': math.sqrt(2)}}}},
                {'name': 'numeric-refs', 'inputs': {ids['a']: {'kind': 'number', 'value': 3.},
                                                    ids['b']: {'kind': 'number', 'value': 5.}},
                 'samples': {'f': [[2., 17.]], 'r': [[2., 6.]], 'h': [[3., 3 * math.sqrt(3)]]},
                 'expectedStates': {
                     'P': {'state': 'defined', 'value': {'x': 3., 'y': 32.}},
                     'M': {'state': 'defined', 'value': {'x': 1.5, 'y': 16.}},
                     'G': {'state': 'undefined', 'reason': 'out_of_domain'},
                     'H': {'state': 'defined', 'value': {'x': 1., 'y': math.sqrt(3)}}}},
                {'name': 'upstream', 'inputs': {ids['a']: {'kind': 'number', 'value': -1.}},
                 'expectedStates': {'u': {'state': 'undefined', 'reason': 'out_of_domain'},
                                    'h': {'state': 'undefined', 'reason': 'upstream'},
                                    'H': {'state': 'undefined', 'reason': 'upstream'},
                                    'P': {'state': 'defined', 'value': {'x': 3., 'y': -7.}},
                                    'G': {'state': 'defined', 'value': {'x': 3., 'y': .25}}},
                 'samples': {'f': [[2., -2.]]}},
                {'name': 'glider-x', 'inputs': {ids['P']: {'kind': 'pathParameter', 'value': -2.},
                                              ids['G']: {'kind': 'pathParameter', 'value': 2.}},
                 'expectedStates': {'P': {'state': 'defined', 'value': {'x': -2., 'y': 10.}},
                                    'M': {'state': 'defined', 'value': {'x': -1., 'y': 5.}},
                                    'G': {'state': 'undefined', 'reason': 'out_of_domain'}}},
                {'name': 'recover', 'inputs': {ids['G']: {'kind': 'pathParameter', 'value': 4.}},
                 'expectedStates': {'G': {'state': 'defined', 'value': {'x': 4., 'y': .5}}}},
            ]}


def test_python_emitted_function_fixture_matches_source_and_independent_values():
    scene = json.loads(FUNCTION_FIXTURE.read_text())
    assert scene == function_fixture()
    doc, ids = scene['document'], scene['sourceIds']
    for name, expected in scene['expectedDefinitions'].items():
        op = doc['operations'][doc['elements'][ids[name]]['producer']['operationId']]
        assert op['args']['expr']['ast'] == expected['expr']
        assert [r['elementId'] for r in op['args']['refs']['items']] == [ids[n] for n in expected['refs']]
        assert [op['args'].get(k, {}).get('value') for k in ('min', 'max')] == expected['domain']
    for case in scene['cases']:
        ev = native.evaluate(doc, inputs=case.get('inputs'))
        for name, expected in case.get('expectedStates', {}).items():
            state = ev.elements[ids[name]]
            assert {k: state[k] for k in expected} == expected
            if state['state'] != 'defined':
                assert 'value' not in state
        for name, samples in case.get('samples', {}).items():
            fn = evaluator(ev.elements[ids[name]]['value'])
            for x, expected in samples:
                actual = fn(x)
                assert actual is None if expected is None else actual == pytest.approx(expected)


def test_free_graph_glider_preserves_x_and_follows_refs():
    body = (number('a', 2) + function_source('a*x²') + command('Point', ['f'], ['P'])
            + point('P', 3., 18.))
    doc, items = imported(body)
    assert items['P']['category'] == 'editable' and items['P']['value_check'] == 'passed'
    assert items['P']['depends_on'] == ['f']
    assert operation(doc, items, 'P')['op'] == 'point.on_function'
    assert operation(doc, items, 'P')['args'] == {'function': {'kind': 'ref', 'elementId': eid(items, 'f')}}
    assert doc['inputs'][eid(items, 'P')] == {'kind': 'pathParameter', 'value': 3.0}
    changes = [({'a': ('number', -1.)}, {'x': 3., 'y': -9.}),
               ({'P': ('pathParameter', -2.)}, {'x': -2., 'y': 8.}),
               ({'a': ('number', 3.), 'P': ('pathParameter', 2.)}, {'x': 2., 'y': 12.})]
    for change, expected in changes:
        ev = native.evaluate(doc, inputs={eid(items, n): {'kind': kind, 'value': value}
                                          for n, (kind, value) in change.items()})
        assert ev.elements[eid(items, 'P')]['value'] == expected


def test_graph_glider_undefined_recovers_without_last_value():
    body = (number('a', 1) + function_source('1/(x-a)') + command('Point', ['f'], ['P'])
            + point('P', 2., 1.) + point('A', 0., 0.)
            + command('Midpoint', ['P', 'A'], ['M']) + point('M', 1., .5))
    doc, items = imported(body)
    assert items['P']['category'] == items['M']['category'] == 'editable'
    for a in (2., 1., 2., 0.):
        ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': a}})
        p, m = (ev.elements[eid(items, name)] for name in ('P', 'M'))
        if a == 2.:
            assert p['state'] == m['state'] == 'undefined'
            assert p['reason'] == 'out_of_domain' and m['reason'] == 'upstream'
            assert 'value' not in p and 'value' not in m
        else:
            assert p['value'] == {'x': 2., 'y': 1 / (2 - a)}
            assert m['value'] == {'x': 1., 'y': .5 / (2 - a)}
    bad_x = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'pathParameter', 'value': 1.}})
    assert bad_x.elements[eid(items, 'P')]['reason'] == 'out_of_domain'
    recovered = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'pathParameter', 'value': 3.}})
    assert recovered.elements[eid(items, 'P')]['value'] == {'x': 3., 'y': .5}


def test_graph_glider_saved_mismatch_is_differs():
    doc, items = imported(function_source('x²') + command('Point', ['f'], ['P']) + point('P', 2., 999.))
    assert items['f']['category'] == 'editable'
    assert items['P']['category'] == 'differs'
    assert items['P']['reason'] == 'value_mismatch' and items['P']['value_check'] == 'failed'
    assert operation(doc, items, 'P')['op'] == 'point.on_function'
    assert native.evaluate(doc).elements[eid(items, 'P')]['value'] == {'x': 2., 'y': 4.}


@pytest.mark.parametrize('definition', [
    command('Point', ['f', 'a'], ['P']), command('Point', ['f', '0.5'], ['P']),
])
def test_number_driven_path_parameter_is_not_frozen(definition):
    doc, items = imported(number('a', 1) + function_source('x²') + definition + point('P', 1., 1.))
    assert items['f']['category'] == 'editable'
    assert items['P']['category'] in ('picture', 'unsupported', 'closure')
    assert items['P']['reason'] in ('formula_unsupported', 'unsupported_signature', 'depends_on_unsupported',
                                   'no_registry_op', 'parse_error')
    assert items['P']['native_ids'] == []
    assert all(el.get('displayName') != 'P' for el in doc['elements'].values())


@pytest.mark.parametrize('formula, moved', [('(a, f(a))', (3., 36.)), ('(1, f(1))', (1., 4.))])
def test_function_coordinate_tuple_is_an_editable_live_expression(formula, moved):
    # A coordinate tuple is a formula, unlike Point(f, t)'s path parameter.
    doc, items = imported(number('a', 1) + number('b', 2) + function_source('b*x²')
                          + expression('P', formula) + point('P', 1., 2.))
    assert items['P']['category'] == 'editable'
    assert items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.expression'
    assert eid(items, 'P') not in doc['inputs']
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 3.},
                                      eid(items, 'b'): {'kind': 'number', 'value': 4.}})
    assert ev.elements[eid(items, 'P')]['value'] == dict(zip(('x', 'y'), moved))


@pytest.mark.parametrize('formula', ['(a, f(A))', '(1, f(1, 2))', '(1, Midpoint[A, A])'])
def test_unsupported_function_tuple_is_an_import_report_refusal(formula):
    doc, items = imported(number('a', 1) + point('A', 0., 0.) + function_source('x²')
                          + expression('P', formula) + point('P', 1., 1.))
    assert items['P']['category'] == 'picture'
    assert items['P']['reason'] == 'formula_unsupported'
    assert formula in items['P']['detail']
    assert items['P']['native_ids'] == []
    assert all(el.get('displayName') != 'P' for el in doc['elements'].values())


@pytest.mark.parametrize('source, saved', [
    (function_source('If(x >= 0, x²)'), (.5, .25)),
    (function_source('If(x < 0, -x, x)'), (.5, .5)),
    (command('Function', ['x²', '-1', '1'], ['f']) + element('function', 'f'), (.5, .25)),
])
def test_if_and_bounded_graph_gliders_are_checked_by_their_saved_point(source, saved):
    # registry 1.9: a domain clamps x and an If has no value in its gaps, as in GeoGebra
    doc, items = imported(source + command('Point', ['f'], ['P']) + point('P', *saved))
    assert items['f']['category'] == 'editable'
    assert items['P']['category'] == 'editable' and items['P']['value_check'] == 'passed'
    assert operation(doc, items, 'P')['op'] == 'point.on_function'


@pytest.mark.parametrize('coords', [
    '<coords x="NaN" y="NaN" z="1"/>', '<coords x="1" y="1" z="0"/>', '',
])
def test_undefined_glider_without_source_x_is_not_invented(coords):
    doc, items = imported(function_source('x²') + command('Point', ['f'], ['P'])
                          + element('point', 'P', extra=coords))
    assert items['f']['category'] == 'editable'
    assert items['P']['category'] == 'unsupported'
    assert items['P']['reason'] == 'unsupported_signature'
    assert items['P']['native_ids'] == []
    assert not any(op['op'] == 'point.on_function' for op in doc['operations'].values())


def test_undefined_glider_with_finite_source_x_can_recover():
    doc, items = imported(number('a', 2) + function_source('1/(x-a)') + command('Point', ['f'], ['P'])
                          + element('point', 'P', extra='<coords x="2" y="NaN" z="1"/>'))
    assert items['P']['category'] == 'editable' and items['P']['value_check'] == 'passed'
    assert doc['inputs'][eid(items, 'P')]['value'] == 2.
    assert native.evaluate(doc).elements[eid(items, 'P')]['reason'] == 'out_of_domain'
    ev = native.evaluate(doc, inputs={eid(items, 'a'): {'kind': 'number', 'value': 1.}})
    assert ev.elements[eid(items, 'P')]['value'] == {'x': 2., 'y': 1.}


def test_function_closure_source_restores_whole_live_chain():
    path = Path(__file__).with_name('import') / 'synthetic' / 'function_closure.ggb'
    doc, report = native.from_ggb(path, id_namespace=NS)
    _check(doc, report)
    items = {e['ggb_name']: e for e in report['elements']}
    assert all(e['category'] == 'editable' and e['value_check'] == 'passed' for e in items.values())
    ev = native.evaluate(doc, inputs={eid(items, 'P'): {'kind': 'pathParameter', 'value': 2.}})
    assert ev.elements[eid(items, 'P')]['value'] == {'x': 2., 'y': 4.}
    assert ev.elements[eid(items, 'M')]['value'] == {'x': 1., 'y': 2.}
    from animageo.native.convert.corpus import expectation
    expected = path.parent.parent / 'expected' / (report['source']['sha256'] + '.json')
    assert json.loads(expected.read_text()) == expectation(path, name='function_closure.ggb')


@pytest.mark.parametrize('body', ['x' + '⁹' * 309, 'x' + '⁹' * 999], ids=['float-overflow', 'max-chars'])
def test_function_superscript_attack_is_graceful_parser_refusal(body):
    assert len(body) <= MAX_CHARS
    with pytest.raises(ExprError) as exc:
        parsed(body)
    assert exc.value.reason == 'formula_unsupported'


@pytest.mark.parametrize('power', ['⁶⁴', '⁻⁶⁴', '⁺⁶⁴'])
def test_function_superscript_limit_boundary_remains_supported(power):
    spec = parsed('x' + power)
    assert spec.ast == {'op': '^', 'args': [{'var': 'x'}, {'num': -64.0 if '⁻' in power else 64.0}]}


@pytest.mark.parametrize('power', ['⁶⁵', '⁻⁶⁵', '⁺⁶⁵'])
def test_function_superscript_over_limit_is_formula_unsupported(power):
    with pytest.raises(ExprError) as exc:
        parsed('x' + power)
    assert exc.value.reason == 'formula_unsupported'


@pytest.fixture(params=[
    ('body-superscript-overflow', function_source('x' + '⁹' * 309)),
    ('lower-unary-plus-at-char-limit', command('Function', ['x', '+' * 999 + '1', '2'], ['f'])
     + element('function', 'f')),
    ('upper-unary-plus-at-char-limit', command('Function', ['x', '0', '+' * 999 + '1'], ['f'])
     + element('function', 'f')),
    ('lower-exponent-plus-at-char-limit', command('Function', ['x', '1^' + '+' * 997 + '1', '2'], ['f'])
     + element('function', 'f')),
    ('upper-exponent-plus-at-char-limit', command('Function', ['x', '0', '1^' + '+' * 997 + '1'], ['f'])
     + element('function', 'f')),
    ('lower-superscript-overflow', command('Function', ['x', '1' + '⁹' * 309, '2'], ['f'])
     + element('function', 'f')),
], ids=lambda case: case[0])
def function_limit_attack(request):
    """Anonymous real XML source fixtures; never a replacement native document."""
    return request.param[1]


def test_function_limit_attack_is_graceful_import_refusal(function_limit_attack):
    doc, items = imported(function_limit_attack)
    assert items['f']['category'] == 'unsupported'
    assert items['f']['reason'] == 'formula_unsupported'
    assert items['f']['native_ids'] == []
    assert doc is None


@pytest.mark.parametrize('lower, upper', [
    ('+' * 32 + '1', '2'), ('0', '+' * 32 + '1'),
    ('1^' + '+' * 31 + '1', '2'), ('0', '1^' + '+' * 31 + '1'),
    ('1⁶⁴', '2'), ('0', '1⁻⁶⁴'),
])
def test_function_literal_domain_depth_and_exponent_boundary_is_supported(lower, upper):
    doc, items = imported(command('Function', ['x', lower, upper], ['f']) + element('function', 'f'))
    assert items['f']['category'] == 'editable'
    assert items['f']['value_check'] == 'passed'
    assert function_value(doc, items)['domain'] == ([0.0, 1.0] if lower == '0' else [1.0, 2.0])


@pytest.mark.parametrize('lower, upper', [
    ('+' * 33 + '1', '2'), ('0', '+' * 33 + '1'),
    ('1^' + '+' * 32 + '1', '2'), ('0', '1^' + '+' * 32 + '1'),
    ('1⁶⁵', '2'), ('0', '1⁻⁶⁵'),
])
def test_function_literal_domain_over_limit_is_graceful_refusal(lower, upper):
    doc, items = imported(command('Function', ['x', lower, upper], ['f']) + element('function', 'f'))
    assert items['f']['category'] == 'unsupported'
    assert items['f']['reason'] == 'formula_unsupported'
    assert items['f']['native_ids'] == []
    assert doc is None


def test_function_domain_guard_does_not_change_default_number_parser():
    assert parse_number('+' * 40 + '1', {}) == ({'num': 1.0}, [])
    assert parse_number('1^' + '+' * 40 + '1', {}) == (
        {'op': '^', 'args': [{'num': 1.0}, {'num': 1.0}]}, [])


@pytest.mark.parametrize('text', ['+' * 40 + '1', '1^' + '+' * 40 + '1'])
def test_typed_source_depth_guard_is_opt_in(text):
    from animageo.native.convert.ggb_expr import parse_typed
    with pytest.raises(ExprError) as exc:
        parse_typed(text, {}, result='num')
    assert exc.value.reason == 'formula_unsupported'


# GeoGebra saves a graph with its label in front, ``i: y = (-abs(x)) + 4``.
@pytest.mark.parametrize('text', ['f: y = a*x²', 'f : y = a*x²', 'f: a*x²', 'f: f(x) = a*x²', 'f: f(t) = a*t²'])
def test_function_label_header_is_read(text):
    spec = parsed(text, {'a': 'numeric'})
    assert spec.ast == {'op': '*', 'args': [
        {'ref': 0}, {'op': '^', 'args': [{'var': 'x'}, {'num': 2.0}]}]}
    assert spec.refs == ['a']


def test_function_label_header_with_an_indexed_label():
    spec = parsed('f_{1}: y = 2x', label='f_{1}')
    assert compile_function(spec.ast, [])(3.0) == 6.0


@pytest.mark.parametrize('text', ['g: y = x²', 'f: g(x) = x²', 'f: g: y = x²', ': y = x²', 'f:= x²', 'f :: x'])
def test_function_label_header_of_another_object_is_refused(text):
    with pytest.raises(ExprError) as exc:
        parsed(text, {'g': 'function'})
    assert exc.value.reason in ('formula_unsupported', 'parse_error')


def test_imported_graph_with_label_header_is_editable_and_live():
    doc, items = imported(number('a', 4) + function_source('i: y = (-abs(x)) + a', 'i', type_='function'))
    assert items['i']['category'] == 'editable'
    assert items['i']['value_check'] == 'passed'
    assert items['i']['depends_on'] == ['a']
    assert operation(doc, items, 'i')['op'] == 'function.expr'
    assert [evaluator(function_value(doc, items, 'i'))(x) for x in (-2.0, 0.0, 3.0)] == [2.0, 4.0, 1.0]
    moved = function_value(doc, items, 'i', inputs={eid(items, 'a'): {'kind': 'number', 'value': 1.0}})
    assert evaluator(moved)(-2.0) == -1.0


if __name__ == '__main__':
    FUNCTION_FIXTURE.write_text(json.dumps(function_fixture(), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
