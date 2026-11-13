"""The interpreter of AST v1 (docs/native/expr.md §3): one IEEE operation per node.

Registry 1.10 (docs/native/expr.md §6): :func:`evaluate_typed` walks a typed
tree whose values are numbers and pairs ``(x, y)`` (a point, the components
of a vector), with the same order and checks node by node.
"""
from __future__ import annotations

import math

from .validate import integer_power

__all__ = ['ExprError', 'evaluate', 'evaluate_typed', 'operand_value']


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


# ── typed trees (registry 1.10) ──────────────────────────────────────────

def _finite_pair(v):
    if not (math.isfinite(v[0]) and math.isfinite(v[1])):
        raise ExprError('non_finite')
    return v


def operand_value(type_: str, value):
    """The value in a typed tree of an item of ``refs``: a ``number`` — its
    value (a ``{value, unit}`` record or a number); a ``point`` — ``(x, y)``;
    a ``vector`` — its components ``(b.x − a.x, b.y − a.y)``; a ``function``
    — ``f(t) -> float | None`` of :func:`~animageo.native.kernel.function.evaluator`."""
    if type_ == 'number':
        return float(value['value'] if isinstance(value, dict) else value)
    if type_ == 'point':
        return float(value['x']), float(value['y'])
    if type_ == 'vector':                     # checked for finiteness where the tree reads it
        (ax, ay), (bx, by) = value['a'], value['b']
        return float(bx) - float(ax), float(by) - float(ay)
    if type_ == 'function':
        from ..kernel.function import evaluator
        return evaluator(value)
    raise ValueError(f'no operand of type {type_!r}')


def _typed(node, ops):
    """The value of a node of a valid typed tree: a float or a pair."""
    if 'num' in node:
        return float(node['num'])
    if 'const' in node:
        return math.pi
    if 'ref' in node:
        v = ops[int(node['ref'])]
        return _finite_pair(v) if isinstance(v, tuple) else _checked(v)
    if 'pair' in node:
        x = _typed(node['pair'][0], ops)
        y = _typed(node['pair'][1], ops)
        return x, y
    if 'call' in node:
        t = _typed(node['args'][0], ops)
        v = ops[int(node['call'])](t)
        if v is None:
            raise ExprError('out_of_domain')
        return _checked(v)
    if 'fn' in node:
        name = node['fn']
        args = node['args']
        if name in ('min', 'max'):
            a = _typed(args[0], ops)
            b = _typed(args[1], ops)
            if name == 'min':
                return _checked(b if b < a else a)
            return _checked(b if b > a else a)
        a = _typed(args[0], ops)
        if isinstance(a, tuple):
            if name == 'x':
                return a[0]
            if name == 'y':
                return a[1]
            return _checked(math.hypot(a[0], a[1]))          # abs of a vector: its length
        return _checked(_fn(name, a))
    name = node['op']
    args = node['args']
    if name == 'neg':
        a = _typed(args[0], ops)
        return (-a[0], -a[1]) if isinstance(a, tuple) else -a
    if name == '^':
        a = _typed(args[0], ops)
        n = integer_power(node)
        return _checked(_power(a, n) if n is not None else _pow(a, _typed(args[1], ops)))
    a = _typed(args[0], ops)
    b = _typed(args[1], ops)
    va, vb = isinstance(a, tuple), isinstance(b, tuple)
    if name == '+':
        return _finite_pair((a[0] + b[0], a[1] + b[1])) if va else _checked(a + b)
    if name == '-':
        return _finite_pair((a[0] - b[0], a[1] - b[1])) if va else _checked(a - b)
    if name == '*':
        if va and vb:                                          # the dot product
            p = a[0] * b[0]
            q = a[1] * b[1]
            return _checked(p + q)
        if va:
            return _finite_pair((a[0] * b, a[1] * b))
        if vb:
            return _finite_pair((a * b[0], a * b[1]))
        return _checked(a * b)
    if b == 0.0:
        raise ExprError('out_of_domain')
    if va:
        return _finite_pair((a[0] / b, a[1] / b))
    return _checked(a / b)


def _checked(v: float) -> float:
    if not math.isfinite(v):
        raise ExprError('non_finite')
    return v


def evaluate_typed(ast, operands, result: str):
    """The value of the typed tree ``ast`` (registry 1.10, docs/native/expr.md
    §6) for ``operands`` — the items of ``refs`` as ``(type, value)`` pairs
    (an :class:`~animageo.native.kernel.values.Input` is one) — in a slot whose
    ``result`` is ``"num"`` (a float) or ``"vec"`` (a pair ``(x, y)``); raises
    :class:`ExprError`.

    Order: post-order, left to right, ``x`` before ``y``; a domain check
    before the operation, finiteness after it, for each component. ``-0``
    comes out as ``0`` (each component of a pair). A tree that
    :func:`~.validate.problems` refuses with these operand types is
    ``formula``.
    """
    from .validate import problems

    types = [item[0] for item in operands]
    if any(t not in ('number', 'point', 'vector', 'function') for t in types) \
            or problems(ast, len(types), (), types, result):
        raise ExprError('formula')
    ops = [operand_value(t, item[1]) for t, item in zip(types, operands)]
    v = _typed(ast, ops)
    if isinstance(v, tuple):
        return v[0] + 0.0, v[1] + 0.0
    return v + 0.0
