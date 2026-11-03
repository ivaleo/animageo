"""Source function grammar: independent AST and mathematical expectations."""
import math

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
