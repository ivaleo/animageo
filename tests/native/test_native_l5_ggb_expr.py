"""The expressions of numbers of a ``.ggb`` the import reads itself
(``animageo.native.convert.ggb_expr``, 1.10.0a3, decision 3 of the tech lead:
the classic parser is not changed) and the names a text refers to."""
from __future__ import annotations

import math
import random
import time

import pytest

from animageo.native.convert.ggb_expr import MAX_CHARS, ExprError, names_in, parse_number, strip_strings
from animageo.native.expr.evaluate import ExprError as EvalError, evaluate
from animageo.native.expr.printer import to_text
from animageo.native.expr.validate import problems

KINDS = {'a': 'numeric', 'b': 'numeric', 'r': 'numeric', 'α': 'angle', "a'": 'numeric', 'a_1': 'numeric',
         't_{AB}': 'numeric', 'A': 'point', 's': 'segment', 'f': 'function', 'L': 'list', 'text1': 'text'}
VALUES = {'a': 4.0, 'b': 3.0, 'r': 2.5, 'α': 0.5, "a'": 1.5, 'a_1': 7.0, 't_{AB}': 0.25}


def _value(text):
    ast, labels = parse_number(text, KINDS)
    assert problems(ast, len(labels)) == []
    return evaluate(ast, [VALUES[n] for n in labels])


@pytest.mark.parametrize('text, value', [
    ('sqrt(a)', 2.0), ('sin(a)', math.sin(4.0)), ('cos(a)', math.cos(4.0)), ('tan(α)', math.tan(0.5)),
    ('asin(α)', math.asin(0.5)), ('arcsin(α)', math.asin(0.5)), ('acos(α)', math.acos(0.5)),
    ('arctan(a)', math.atan(4.0)), ('exp(r)', math.exp(2.5)), ('ln(a)', math.log(4.0)), ('log(a)', math.log(4.0)),
    ('lg(a)', math.log10(4.0)), ('log(2, a)', 2.0), ('cot(a)', 1 / math.tan(4.0)), ('sec(a)', 1 / math.cos(4.0)),
    ('csc(a)', 1 / math.sin(4.0)), ('abs(a - 7)', 3.0), ('abs(a) + 1', 5.0), ('Min(a, b)', 3.0),
    ('Max(a, b)', 4.0),
    # the implicit product, left to right with · and /
    ('2a', 8.0), ('2 a', 8.0), ('a b', 12.0), ('2(a + b)', 14.0), ('(a + b)(a - b)', 7.0), ('a(b + 1)', 16.0),
    ('2sqrt(a)', 4.0), ('sqrt(a)b - 4', 2.0), ('1/2a', 2.0), ('a / b r', 4.0 / 3.0 * 2.5), ('2a²', 32.0),
    ('3a_1', 21.0), ("2a'", 3.0), ('4t_{AB}', 1.0), ('2π', 2 * math.pi), ('π a', 4 * math.pi), ('pi', math.pi),
    # powers: superscripts, ^ right-associative, the unary minus below ^
    ('a²', 16.0), ('a³', 64.0), ('a⁻¹', 0.25), ('a^2', 16.0), ('a^-1', 0.25), ('2^3^2', 512.0), ('-a²', -16.0),
    ('-a^2', -16.0), ('(-a)²', 16.0), ('a^(1/2)', 2.0), ('a^b', 64.0), ('2^-a', 2.0 ** -4),
    # GeoGebra's signs and degrees
    ('a·b', 12.0), ('a⋅b', 12.0), ('a×b', 12.0), ('a÷b', 4.0 / 3.0), ('a − b', 1.0), ('30°', math.pi / 6),
    ('a°', 4.0 * math.pi / 180), ('2.5E2', 250.0), ('.5a', 2.0), ('+a', 4.0), ('-(-a)', 4.0),
    ('sin(30°)', 0.5), ('ℯ', math.e),
])
def test_an_expression_reads_as_geogebra_computes_it(text, value):
    assert _value(text) == pytest.approx(value, rel=1e-12)


def test_the_tree_and_the_references():
    assert parse_number('sqrt(a)', KINDS) == ({'fn': 'sqrt', 'args': [{'ref': 0}]}, ['a'])
    assert parse_number('2a', KINDS) == ({'op': '*', 'args': [{'num': 2.0}, {'ref': 0}]}, ['a'])
    assert parse_number('a²', KINDS) == ({'op': '^', 'args': [{'ref': 0}, {'num': 2.0}]}, ['a'])
    assert parse_number('b a + a', KINDS) == (
        {'op': '+', 'args': [{'op': '*', 'args': [{'ref': 0}, {'ref': 1}]}, {'ref': 1}]}, ['b', 'a'])
    assert parse_number('2^-1', KINDS)[0] == {'op': '^', 'args': [{'num': 2.0}, {'num': -1.0}]}
    assert parse_number('-a', KINDS)[0] == {'op': 'neg', 'args': [{'ref': 0}]}
    assert parse_number('2π', KINDS) == ({'op': '*', 'args': [{'num': 2.0}, {'const': 'pi'}]}, [])
    # every tree is a fresh object
    one, _ = parse_number('30°', KINDS)
    one['args'][1]['args'][0]['const'] = 'x'
    assert parse_number('30°', KINDS)[0]['args'][1]['args'][0] == {'const': 'pi'}


@pytest.mark.parametrize('text, reason, detail', [
    ('floor(a)', 'formula_unsupported', 'функции floor нет в формулах'),
    ('round(a, 2)', 'formula_unsupported', 'функции round нет в формулах'),
    ('random()', 'formula_unsupported', 'функции random нет в формулах'),
    ('x(A)', 'formula_unsupported', 'координаты точек пока не переносятся в формулы'),
    ('Distance(A, B)', 'formula_unsupported', 'в выражении есть команда, которой нет в формулах'),
    ('s / 2', 'formula_unsupported', 'в выражении s — не число: в формулу входят только числа и углы'),
    ('f(2)', 'formula_unsupported', 'в выражении f — функция: в формулу входят только числа и углы'),
    ('L + 1', 'formula_unsupported', 'в выражении L — не число: в формулу входят только числа и углы'),
    ('Min(a, b, 1)', 'formula_unsupported', 'Min не двух чисел не входит в формулы'),
    ('a^100', 'formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)'),
    ('1E400', 'formula_unsupported', 'число 1E400 вне формул'),
    ('(' * 40 + 'a' + ')' * 40, 'formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)'),
    ('-' * 40 + 'a', 'formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)'),
    ('+'.join(['a'] * 200), 'formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)'),
    ('a' + ' + a' * MAX_CHARS, 'formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)'),
    ('q + 1', 'parse_error', 'неизвестное имя q'),
    ('2 3', 'parse_error', 'два числа подряд'),
    ('a² 2', 'parse_error', 'два числа подряд'),
    ('a +', 'parse_error', 'ожидалось число или имя, а не конец'),
    ('(a', 'parse_error', 'ожидалось «)», а не конец'),
    ('a)', 'parse_error', "лишнее в выражении: ')'"),
    ('sqrt(a, b)', 'parse_error', 'у sqrt один аргумент'),
    ('a = 2', 'parse_error', "знак '=' не входит в выражения чисел"),
    ('"a"', 'parse_error', 'строка в выражении числа'),
    ('a; b', 'parse_error', "знак ';' не входит в выражения чисел"),
    ('', 'parse_error', 'ожидалось число или имя, а не конец'),
])
def test_what_is_not_read_says_why(text, reason, detail):
    with pytest.raises(ExprError) as exc:
        parse_number(text, KINDS)
    assert (exc.value.reason, exc.value.detail) == (reason, detail)


@pytest.mark.parametrize('texts, found', [
    # a string literal names nothing: a LaTeX formula of a fixed text
    (['"$S = \\frac{1}{2} a \\cdot h_a$"'], []),
    (['"a = " + a'], ['a']),
    (['"$" + a + "\\cdot b$" + r'], ['a', 'r']),
    (['"a \\" b " + b'], ['b']),                     # an escaped quote inside the literal
    (['t_{AB} + 1', 'a'], ['t_{AB}', 'a']),
    (['a² + a_1'], ['a', 'a_1']),
    (["a' + a"], ["a'", 'a']),
    (['A'], ['A']),                                  # an input that is a label as is
    (['"unclosed a'], []),
])
def test_names_outside_the_string_literals(texts, found):
    assert names_in(texts, set(KINDS) | {'h_a'}) == found


def test_strip_strings():
    assert strip_strings('"a" + b + "c\\"d"') == '  + b +  '
    assert strip_strings('no strings') == 'no strings'


def _random_tree(rng, depth=0):
    roll = rng.random()
    if depth > 4 or roll < 0.3:
        leaf = rng.randrange(3)
        if leaf == 0:
            return {'num': rng.choice([0.5, 1.0, 2.0, 3.0, 10.0, 0.25, 7.0])}
        if leaf == 1:
            return {'const': 'pi'}
        return {'ref': rng.randrange(3)}
    if roll < 0.45:
        fn = rng.choice(['sqrt', 'abs', 'sin', 'cos', 'tan', 'atan', 'exp', 'ln', 'lg', 'min', 'max'])
        n = 2 if fn in ('min', 'max') else 1
        return {'fn': fn, 'args': [_random_tree(rng, depth + 1) for _ in range(n)]}
    if roll < 0.55:
        return {'op': 'neg', 'args': [_random_tree(rng, depth + 1)]}
    op = rng.choice(['+', '-', '*', '/', '^'])
    if op == '^':
        return {'op': '^', 'args': [_random_tree(rng, depth + 1), {'num': float(rng.randrange(-3, 4))}]}
    return {'op': op, 'args': [_random_tree(rng, depth + 1), _random_tree(rng, depth + 1)]}


def _same(x, y):
    if math.isnan(x) or math.isnan(y):
        return math.isnan(x) and math.isnan(y)
    return x == pytest.approx(y, rel=1e-9, abs=1e-12)


def _value_or_error(ast, refs):
    try:
        return evaluate(ast, refs)
    except EvalError as exc:
        return exc.reason


@pytest.mark.parametrize('seed', range(5))
def test_a_tree_reads_back_from_its_text(seed):
    """The text of a valid tree (``native.expr.to_text``, what «Команды»
    show) reads back as a tree of the same value."""
    rng = random.Random(seed)
    names = ['a', 'b', 'r']
    refs = [VALUES[n] for n in names]
    for _ in range(200):
        ast = _random_tree(rng)
        text = to_text(ast, names)
        got, labels = parse_number(text, KINDS)
        want = _value_or_error(ast, refs)
        back = _value_or_error(got, [VALUES[n] for n in labels])
        assert isinstance(want, str) == isinstance(back, str), text
        if not isinstance(want, str):
            assert _same(back, want), text


_ALPHABET = list('ab r()[],+-*/^·°²⁻.0123456789E" ') + ['sqrt', 'sin', 'abs', 'floor', 'x', 'Min', 'π', 'α', 'A',
                                                         's', 'f', 'q', 't_{AB}', '_{', '}', 'log']


@pytest.mark.fuzz
@pytest.mark.parametrize('seed', range(3))
def test_any_text_is_read_or_refused_quickly(seed):
    """Random texts: a tree within the limits of AST v1 or :class:`ExprError`
    — never another exception; the slow series runs more."""
    _fuzz(seed, 300)


@pytest.mark.fuzz
@pytest.mark.slow
@pytest.mark.parametrize('seed', range(20))
def test_any_text_is_read_or_refused_series(seed):
    _fuzz(1000 + seed, 2000)


def _fuzz(seed, count):
    rng = random.Random(seed)
    start = time.perf_counter()
    for _ in range(count):
        text = ''.join(rng.choice(_ALPHABET) for _ in range(rng.randrange(0, 60)))
        try:
            ast, labels = parse_number(text, KINDS)
        except ExprError as exc:
            assert exc.reason in ('parse_error', 'formula_unsupported') and exc.detail, text
            continue
        assert problems(ast, len(labels)) == [], text
        assert all(KINDS[n] in ('numeric', 'angle') for n in labels), text
        names_in([text], KINDS)
    assert time.perf_counter() - start < count * 0.01


def test_long_inputs_take_linear_time():
    for text in ('a' * 100_000, '(' * 100_000, '_{' * 50_000, 'a_{' + 'b' * 100_000, '2' * 100_000,
                 'a²' * 50_000):
        start = time.perf_counter()
        names_in([text], KINDS)
        with pytest.raises(ExprError):
            parse_number(text, KINDS)
        assert time.perf_counter() - start < 1.0, text[:10]
