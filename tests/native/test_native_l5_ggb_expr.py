"""The names an expression of a ``.ggb`` refers to: none inside its string
literals (``animageo.native.convert.ggb_expr``, 1.10.0a3)."""
from __future__ import annotations

import pytest

from animageo.native.convert.ggb_expr import names_in, strip_strings

KINDS = {'a': 'numeric', 'b': 'numeric', 'r': 'numeric', 'α': 'angle', "a'": 'numeric', 'a_1': 'numeric',
         't_{AB}': 'numeric', 'A': 'point', 's': 'segment', 'f': 'function', 'L': 'list', 'text1': 'text'}


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


def test_long_inputs_take_linear_time():
    import time
    for text in ('a' * 100_000, '(' * 100_000, '_{' * 50_000, 'a_{' + 'b' * 100_000, 'a²' * 50_000):
        start = time.perf_counter()
        names_in([text], KINDS)
        assert time.perf_counter() - start < 1.0, text[:10]
