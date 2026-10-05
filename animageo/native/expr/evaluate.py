"""The interpreter of AST v1 (docs/native/expr.md §3): one IEEE operation per node."""
from __future__ import annotations

import math

from .validate import integer_power

__all__ = ['ExprError', 'evaluate']


class ExprError(Exception):
    """The tree has no value: ``reason`` is ``out_of_domain``, ``non_finite``
    or ``formula`` (a tree :func:`~animageo.native.expr.problems` refuses)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _power(base: float, n: int) -> float:
    """``base ** n`` for an integer literal ``n`` by binary exponentiation."""
    r = 1.0
    b = base
    m = abs(n)
    while m:
        if m & 1:
            r = r * b
        b = b * b
        m >>= 1
    if n < 0:
        if r == 0.0:
            raise ExprError('non_finite')
        return 1.0 / r
    return r


def _pow(a: float, b: float) -> float:
    if a == 0.0 and b < 0.0:
        raise ExprError('non_finite')
    if a < 0.0 and not b.is_integer():
        raise ExprError('out_of_domain')
    try:
        return math.pow(a, b)
    except OverflowError:
        raise ExprError('non_finite') from None


def _fn(name: str, a: float) -> float:
    if name == 'sqrt':
        if a < 0.0:
            raise ExprError('out_of_domain')
        return math.sqrt(a)
    if name == 'abs':
        return abs(a)
    if name in ('ln', 'lg'):
        if a <= 0.0:
            raise ExprError('out_of_domain')
        return math.log(a) if name == 'ln' else math.log10(a)
    if name in ('asin', 'acos'):
        if a < -1.0 or a > 1.0:
            raise ExprError('out_of_domain')
        return math.asin(a) if name == 'asin' else math.acos(a)
    if name == 'exp':
        try:
            return math.exp(a)
        except OverflowError:
            raise ExprError('non_finite') from None
    return {'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'atan': math.atan}[name](a)


def _eval(node, refs) -> float:
    if not isinstance(node, dict):
        raise ExprError('formula')
    if 'num' in node:
        v = float(node['num'])
    elif 'const' in node:
        v = math.pi
    elif 'ref' in node:
        v = float(refs[int(node['ref'])])
    elif 'op' in node:
        name = node['op']
        args = node['args']
        if name == 'neg':
            v = -_eval(args[0], refs)
        elif name == '^':
            a = _eval(args[0], refs)
            n = integer_power(node)
            v = _power(a, n) if n is not None else _pow(a, _eval(args[1], refs))
        else:
            a = _eval(args[0], refs)
            b = _eval(args[1], refs)
            if name == '+':
                v = a + b
            elif name == '-':
                v = a - b
            elif name == '*':
                v = a * b
            else:
                if b == 0.0:
                    raise ExprError('out_of_domain')
                v = a / b
    elif 'fn' in node:
        name = node['fn']
        args = node['args']
        if name in ('min', 'max'):
            a = _eval(args[0], refs)
            b = _eval(args[1], refs)
            if name == 'min':
                v = b if b < a else a
            else:
                v = b if b > a else a
        else:
            v = _fn(name, _eval(args[0], refs))
    else:
        raise ExprError('formula')
    if not math.isfinite(v):
        raise ExprError('non_finite')
    return v


def evaluate(ast, refs=()) -> float:
    """The value of a valid tree ``ast`` for the numbers ``refs`` (the values
    of the items of the input ``refs``); raises :class:`ExprError`.

    Order: post-order, left to right; the first node without a finite value
    decides the reason (a domain check before the operation, a non-finite
    result after it). ``-0`` comes out as ``0``.
    """
    from .validate import problems

    if problems(ast, len(refs)):
        raise ExprError('formula')
    return _eval(ast, list(refs)) + 0.0
