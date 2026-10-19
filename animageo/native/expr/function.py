"""Functions of one variable (registry 1.6, docs/native/expr.md §5).

:func:`compile_function` turns a tree with the variable ``x`` into a Python
function ``f(x) -> float`` that raises :class:`ExprError` where the tree has
no value. Each node does the IEEE operation of :func:`~.evaluate.evaluate`
in the same order (left before right) and the same checks; ``if`` takes only
its chosen branch, ``and``/``or`` stop at the first operand that decides.
"""
from __future__ import annotations

import math

from .evaluate import ExprError, _fn, _pow, _power
from .validate import integer_power, problems

__all__ = ['compile_function']

_isfinite = math.isfinite


def _checked(v: float) -> float:
    if not _isfinite(v):
        raise ExprError('non_finite')
    return v


def _divide(a, b):
    def f(x):
        av = a(x)
        bv = b(x)
        if bv == 0.0:
            raise ExprError('out_of_domain')
        return _checked(av / bv)
    return f


def _value(node, refs):
    if 'num' in node:
        v = float(node['num'])
        return lambda x: v
    if 'const' in node:
        v = math.pi
        return lambda x: v
    if 'ref' in node:
        v = float(refs[int(node['ref'])])
        return lambda x: v
    if 'var' in node:
        return lambda x: x
    if 'if' in node:
        items = node['if']
        cond = _condition(items[0], refs)
        then = _value(items[1], refs)
        other = _value(items[2], refs) if len(items) == 3 else None

        def choose(x):
            if cond(x):
                return then(x)
            if other is None:
                raise ExprError('out_of_domain')
            return other(x)
        return choose
    if 'op' in node:
        name = node['op']
        args = node['args']
        a = _value(args[0], refs)
        if name == 'neg':
            return lambda x: -a(x)
        if name == '^':
            n = integer_power(node)
            if n is not None:
                return lambda x: _checked(_power(a(x), n))
            b = _value(args[1], refs)
            return lambda x: _checked(_pow(a(x), b(x)))
        b = _value(args[1], refs)
        if name == '+':
            return lambda x: _checked(a(x) + b(x))
        if name == '-':
            return lambda x: _checked(a(x) - b(x))
        if name == '*':
            return lambda x: _checked(a(x) * b(x))
        return _divide(a, b)
    name = node['fn']
    args = node['args']
    a = _value(args[0], refs)
    if name in ('min', 'max'):
        b = _value(args[1], refs)
        if name == 'min':
            def low(x):
                av = a(x)
                bv = b(x)
                return bv if bv < av else av
            return low

        def high(x):
            av = a(x)
            bv = b(x)
            return bv if bv > av else av
        return high
    return lambda x: _checked(_fn(name, a(x)))


def _condition(node, refs):
    if 'cmp' in node:
        a = _value(node['args'][0], refs)
        b = _value(node['args'][1], refs)
        sign = node['cmp']
        if sign == '<':
            return lambda x: a(x) < b(x)
        if sign == '<=':
            return lambda x: a(x) <= b(x)
        if sign == '>':
            return lambda x: a(x) > b(x)
        return lambda x: a(x) >= b(x)
    if 'not' in node:
        c = _condition(node['not'][0], refs)
        return lambda x: not c(x)
    kind = 'and' if 'and' in node else 'or'
    left = _condition(node[kind][0], refs)
    right = _condition(node[kind][1], refs)
    if kind == 'and':
        return lambda x: left(x) and right(x)
    return lambda x: left(x) or right(x)


def compile_function(ast, refs=(), var: str = 'x'):
    """``f(x)`` of the tree ``ast`` with the variable ``var`` and the numbers
    ``refs``; ``f`` raises :class:`ExprError` (``out_of_domain``,
    ``non_finite``) where the tree has no value and returns ``+0`` for
    ``-0``. A tree :func:`~.validate.problems` refuses raises
    ``ExprError('formula')`` here."""
    refs = [float(v) for v in refs]
    if problems(ast, len(refs), (var,)):
        raise ExprError('formula')
    body = _value(ast, refs)

    def f(x):
        return body(float(x)) + 0.0
    return f
