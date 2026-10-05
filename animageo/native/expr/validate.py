"""The rules of AST v1 (docs/native/expr.md §2): node shapes, the whitelist, the limits."""
from __future__ import annotations

import math

__all__ = ['CONSTANTS', 'FUNCTIONS', 'MAX_DEPTH', 'MAX_INTEGER_POWER', 'MAX_NODES', 'OPERATORS', 'integral',
           'integer_power', 'problems']

OPERATORS = {'+': 2, '-': 2, '*': 2, '/': 2, '^': 2, 'neg': 1}
FUNCTIONS = {
    'sqrt': 1, 'abs': 1, 'sin': 1, 'cos': 1, 'tan': 1, 'asin': 1, 'acos': 1, 'atan': 1,
    'exp': 1, 'ln': 1, 'lg': 1, 'min': 2, 'max': 2,
}
CONSTANTS = ('pi',)
MAX_DEPTH = 32            # the root is at depth 1
MAX_NODES = 256
MAX_INTEGER_POWER = 64    # |n| of an integer literal exponent

_V2_ONLY = ('var', 'if', 'cmp', 'and', 'or', 'not')
_SHAPES = {'num': ('num',), 'const': ('const',), 'ref': ('ref',), 'op': ('op', 'args'), 'fn': ('fn', 'args')}


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def integral(v) -> bool:
    """``v`` is a finite number with an integral value (``2`` and ``2.0`` alike:
    JSON does not tell them apart)."""
    return _number(v) and float(v).is_integer()


def integer_power(node):
    """The integer exponent ``n`` of a ``^`` node whose exponent is a literal
    ``{"num": n}`` with an integral ``n``, else ``None``."""
    exponent = node['args'][1]
    if isinstance(exponent, dict) and set(exponent) == {'num'} and integral(exponent['num']):
        return int(exponent['num'])
    return None


def _node_problem(node, ref_count):
    """The problem of one node (its own keys and values), or ``None``."""
    if not isinstance(node, dict):
        return 'a node must be an object'
    kinds = [k for k in _SHAPES if k in node]
    if len(kinds) != 1:
        v2 = [k for k in _V2_ONLY if k in node]
        if not kinds and v2:
            return f'node {v2[0]!r} is not in AST v1'
        return 'a node must have exactly one of num, const, ref, op, fn'
    kind = kinds[0]
    extra = sorted(set(node) - set(_SHAPES[kind]))
    if extra:
        return f'a {kind} node does not allow key {extra[0]!r}'
    missing = [k for k in _SHAPES[kind] if k not in node]
    if missing:
        return f'a {kind} node misses key {missing[0]!r}'
    value = node[kind]
    if kind == 'num':
        return None if _number(value) else 'num must be a finite number'
    if kind == 'const':
        return None if value in CONSTANTS else f'unknown constant {value!r} (pi)'
    if kind == 'ref':
        if not integral(value) or value < 0:
            return 'ref must be an integer >= 0'
        if ref_count is not None and value >= ref_count:
            return f'ref {int(value)} is outside refs ({ref_count} items)'
        return None
    args = node['args']
    if kind == 'op':
        if not isinstance(value, str) or value not in OPERATORS:
            return f'unknown operator {value!r}'
        arity = OPERATORS[value]
    else:
        if not isinstance(value, str) or value not in FUNCTIONS:
            return f'unknown function {value!r}'
        arity = FUNCTIONS[value]
    if not isinstance(args, list):
        return 'args must be an array'
    if len(args) != arity:
        return f'{value} takes {arity} argument{"s" if arity > 1 else ""}, not {len(args)}'
    if kind == 'op' and value == '^':
        n = integer_power(node)
        if n is not None and abs(n) > MAX_INTEGER_POWER:
            return f'an integer power above {MAX_INTEGER_POWER}'
    return None


def problems(ast, ref_count: int | None = None) -> list:
    """``[(pointer, message)]`` of the problems of ``ast``, in pre-order (left
    to right); empty for a valid tree. ``pointer`` is a JSON pointer to the
    node inside the tree (``""`` — the root, ``/args/1`` — its second
    argument). ``ref_count`` — the number of items of ``refs`` (``None``
    skips the range check). The walk does not recurse, stops descending past
    :data:`MAX_DEPTH` and stops after :data:`MAX_NODES` nodes."""
    out = []
    stack = [(ast, '', 1)]
    count = 0
    while stack:
        node, pointer, depth = stack.pop()
        count += 1
        if count > MAX_NODES:
            out.append(('', f'more than {MAX_NODES} nodes'))
            break
        if depth > MAX_DEPTH:
            out.append((pointer, f'deeper than {MAX_DEPTH} levels'))
            continue
        problem = _node_problem(node, ref_count)
        if problem is not None:
            out.append((pointer, problem))
            continue
        if 'args' in node:
            for i in range(len(node['args']) - 1, -1, -1):
                stack.append((node['args'][i], f'{pointer}/args/{i}', depth + 1))
    return out
