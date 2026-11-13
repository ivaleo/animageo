"""Source formulas retain ordered, typed operands without evaluating text."""
import pytest

from animageo.native.convert.ggb_expr import ExprError, parse_number, parse_typed

KINDS = {'A': 'point', 'B': 'point', 'v': 'vector', 'a': 'numeric', 'α': 'angle', 'f': 'function'}


@pytest.mark.parametrize('text, result, ast, refs', [
    ('A + v', 'vec', {'op': '+', 'args': [{'ref': 0}, {'ref': 1}]}, ['A', 'v']),
    ('A + B', 'vec', {'op': '+', 'args': [{'ref': 0}, {'ref': 1}]}, ['A', 'B']),
    ('(a, -2)', 'vec', {'pair': [{'ref': 0}, {'num': -2.}]}, ['a']),
    ('2A − B', 'vec', {'op': '-', 'args': [{'op': '*', 'args': [{'num': 2.}, {'ref': 0}]}, {'ref': 1}]}, ['A', 'B']),
    ('x(A)', 'num', {'fn': 'x', 'args': [{'ref': 0}]}, ['A']),
    ('(f(a), y(A))', 'vec', {'pair': [{'call': 0, 'args': [{'ref': 1}]}, {'fn': 'y', 'args': [{'ref': 2}]}]}, ['f', 'a', 'A']),
    ('f(a) + f(1)', 'num', {'op': '+', 'args': [{'call': 0, 'args': [{'ref': 1}]}, {'call': 0, 'args': [{'num': 1.}]}]}, ['f', 'a']),
])
def test_canonical_tree(text, result, ast, refs):
    assert parse_typed(text, KINDS, result=result) == (ast, refs)


@pytest.mark.parametrize('text, result', [
    ('A / B', 'vec'), ('a / A', 'vec'), ('A + 1', 'vec'), ('A^2', 'vec'),
    ('sin(A)', 'vec'), ('f', 'num'), ('f(A)', 'num'), ('x(A)', 'vec'),
    ('(a, 2, 3)', 'vec'), ('(a; α)', 'vec'), ('{A, B}', 'vec'),
    ('(x(Midpoint[A, B]), 0)', 'vec'), ('floor(a)', 'num'),
    ('+' * 950 + 'A', 'vec'), ('A' + '⁹' * 400, 'vec'),
])
def test_outside_the_language_is_explicit(text, result):
    with pytest.raises(ExprError) as error:
        parse_typed(text, KINDS, result=result)
    assert error.value.reason == 'formula_unsupported'
    assert text[:100] in error.value.detail


def test_number_reader_keeps_its_language():
    for text in ('x(A)', '(a, 2)', 'f(a)'):
        with pytest.raises(ExprError):
            parse_number(text, KINDS)
    assert parse_number('2a', KINDS)[1] == ['a']
