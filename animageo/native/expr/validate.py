"""The rules of AST v1 (docs/native/expr.md §2): node shapes, the whitelist, the limits.

Registry 1.6 (docs/native/expr.md §5): an ``expr`` slot whose record lists
``vars`` (``function.expr``: ``["x"]``) also takes the nodes ``var``, ``if``
and the conditions ``cmp``, ``and``, ``or``, ``not``; other slots refuse
them as before.

Registry 1.10 (docs/native/expr.md §6): an ``expr`` slot whose record has
``result`` (``"num"`` or ``"vec"``) is typed: it also takes the nodes
``pair`` and ``call`` and the functions ``x``, ``y``; with the element types
of ``refs`` (``operands``) a second pass types the tree bottom-up
(:func:`type_problems`). Other slots refuse the typed nodes as before.
"""
from __future__ import annotations

import math

__all__ = ['COMPARISONS', 'CONSTANTS', 'FUNCTIONS', 'MAX_DEPTH', 'MAX_INTEGER_POWER', 'MAX_NODES', 'OPERAND_TYPES',
           'OPERATORS', 'TYPED_FUNCTIONS', 'integral', 'integer_power', 'problems', 'type_problems']

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
# registry 1.6, slots with ``vars``: values ``var``, ``if``; conditions ``cmp``, ``and``, ``or``, ``not``
COMPARISONS = ('<', '<=', '>', '>=')
_CONDITIONS = ('cmp', 'and', 'or', 'not')
_V2_SHAPES = {'var': ('var',), 'if': ('if',), 'cmp': ('cmp', 'args'), 'and': ('and',), 'or': ('or',),
              'not': ('not',)}
_V2_ARITY = {'and': 2, 'or': 2, 'not': 1}
# registry 1.10, typed slots (``result``): a pair of numbers, a value of a function of ``refs``,
# the coordinates of a vector
_TYPED_SHAPES = {'pair': ('pair',), 'call': ('call', 'args')}
TYPED_FUNCTIONS = {'x': 1, 'y': 1}
# the type in the tree of an element of ``refs`` (the family ``operand``)
OPERAND_TYPES = {'number': 'num', 'point': 'vec', 'vector': 'vec', 'function': 'fn'}


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


def _v2_problem(node, v2, vars_, role):
    """The problem of a node of the registry 1.6 extension, or ``None``."""
    if len(v2) != 1:
        return f'a node must have exactly one of {", ".join(_V2_ONLY)}'
    kind = v2[0]
    extra = sorted(set(node) - set(_V2_SHAPES[kind]))
    if extra:
        return f'a {kind} node does not allow key {extra[0]!r}'
    missing = [k for k in _V2_SHAPES[kind] if k not in node]
    if missing:
        return f'a {kind} node misses key {missing[0]!r}'
    if role == 'cond' and kind not in _CONDITIONS:
        return f'a condition (cmp, and, or, not) is expected, not {kind}'
    if role == 'value' and kind in _CONDITIONS:
        return f'a value is expected, not the condition {kind}'
    value = node[kind]
    if kind == 'var':
        return None if isinstance(value, str) and value in vars_ else \
            f'unknown variable {value!r} ({", ".join(vars_)})'
    if kind == 'if':
        if not isinstance(value, list) or len(value) not in (2, 3):
            return 'if takes [condition, then] or [condition, then, else]'
        return None
    if kind == 'cmp':
        if not isinstance(value, str) or value not in COMPARISONS:
            return f'unknown comparison {value!r} ({", ".join(COMPARISONS)})'
        if not isinstance(node['args'], list) or len(node['args']) != 2:
            return 'cmp takes 2 arguments'
        return None
    arity = _V2_ARITY[kind]
    if not isinstance(value, list) or len(value) != arity:
        return f'{kind} takes {arity} condition{"s" if arity > 1 else ""}'
    return None


def _children(node, pointer):
    """``[(child, pointer, role)]`` of a valid node, in order."""
    if 'args' in node:            # op, fn, cmp, call: values
        return [(a, f'{pointer}/args/{i}', 'value') for i, a in enumerate(node['args'])]
    if 'pair' in node:            # registry 1.10
        return [(a, f'{pointer}/pair/{i}', 'value') for i, a in enumerate(node['pair'])]
    if 'if' in node:
        return [(a, f'{pointer}/if/{i}', 'cond' if i == 0 else 'value') for i, a in enumerate(node['if'])]
    for kind in ('and', 'or', 'not'):
        if kind in node:
            return [(a, f'{pointer}/{kind}/{i}', 'cond') for i, a in enumerate(node[kind])]
    return []


def _ref_problem(value, ref_count, kind='ref'):
    if not integral(value) or value < 0:
        return f'{kind} must be an integer >= 0'
    if ref_count is not None and value >= ref_count:
        return f'{kind} {int(value)} is outside refs ({ref_count} items)'
    return None


def _node_problem(node, ref_count, vars_=(), role='value', typed=False):
    """The problem of one node (its own keys and values), or ``None``."""
    if not isinstance(node, dict):
        return 'a node must be an object'
    if vars_:
        v2 = [k for k in _V2_ONLY if k in node]
        if v2 and not any(k in node for k in _SHAPES):
            return _v2_problem(node, v2, vars_, role)
        if role == 'cond':
            return 'a condition (cmp, and, or, not) is expected'
    shapes = dict(_SHAPES, **_TYPED_SHAPES) if typed else _SHAPES
    kinds = [k for k in shapes if k in node]
    if len(kinds) != 1:
        v2 = [k for k in _V2_ONLY if k in node]
        if not kinds and v2:
            return f'node {v2[0]!r} is not in AST v1'
        return f'a node must have exactly one of {", ".join(shapes)}'
    kind = kinds[0]
    extra = sorted(set(node) - set(shapes[kind]))
    if extra:
        return f'a {kind} node does not allow key {extra[0]!r}'
    missing = [k for k in shapes[kind] if k not in node]
    if missing:
        return f'a {kind} node misses key {missing[0]!r}'
    value = node[kind]
    if kind == 'num':
        return None if _number(value) else 'num must be a finite number'
    if kind == 'const':
        return None if value in CONSTANTS else f'unknown constant {value!r} (pi)'
    if kind == 'ref':
        return _ref_problem(value, ref_count)
    if kind == 'pair':
        return None if isinstance(value, list) and len(value) == 2 else 'pair takes 2 values'
    if kind == 'call':
        problem = _ref_problem(value, ref_count, 'call')
        if problem is not None:
            return problem
        args = node['args']
        if not isinstance(args, list):
            return 'args must be an array'
        return None if len(args) == 1 else f'call takes 1 argument, not {len(args)}'
    args = node['args']
    if kind == 'op':
        if not isinstance(value, str) or value not in OPERATORS:
            return f'unknown operator {value!r}'
        arity = OPERATORS[value]
    else:
        names = dict(FUNCTIONS, **TYPED_FUNCTIONS) if typed else FUNCTIONS
        if not isinstance(value, str) or value not in names:
            return f'unknown function {value!r}'
        arity = names[value]
    if not isinstance(args, list):
        return 'args must be an array'
    if len(args) != arity:
        return f'{value} takes {arity} argument{"s" if arity > 1 else ""}, not {len(args)}'
    if kind == 'op' and value == '^':
        n = integer_power(node)
        if n is not None and abs(n) > MAX_INTEGER_POWER:
            return f'an integer power above {MAX_INTEGER_POWER}'
    return None


def problems(ast, ref_count: int | None = None, vars=(), operands=None, result=None) -> list:
    """``[(pointer, message)]`` of the problems of ``ast``, in pre-order (left
    to right); empty for a valid tree. ``pointer`` is a JSON pointer to the
    node inside the tree (``""`` — the root, ``/args/1`` — its second
    argument, ``/if/0`` — the condition of an ``if``). ``ref_count`` — the
    number of items of ``refs`` (``None`` skips the range check). ``vars`` —
    the variables of the slot (registry 1.6: ``("x",)`` for
    ``function.expr``); with them the tree may use ``var``, ``if`` and
    conditions. The walk does not recurse, stops descending past
    :data:`MAX_DEPTH` and stops after :data:`MAX_NODES` nodes.

    ``result`` (registry 1.10: ``"num"`` or ``"vec"``, the key of a typed
    slot) admits the nodes ``pair``, ``call`` and the functions ``x``, ``y``;
    ``operands`` — the element types of the items of ``refs`` (``number``,
    ``point``, ``vector``, ``function``) — adds the pass of
    :func:`type_problems` when the structure has no problem. Without
    ``operands`` (an item of ``refs`` that dangles or does not fit) the tree
    is checked for its structure only."""
    vars_ = tuple(vars or ())
    typed = result is not None
    if typed and vars_:
        raise ValueError('a typed slot has no vars')
    if typed and operands is not None and ref_count is None:
        ref_count = len(operands)
    out = []
    stack = [(ast, '', 1, 'value')]
    count = 0
    while stack:
        node, pointer, depth, role = stack.pop()
        count += 1
        if count > MAX_NODES:
            out.append(('', f'more than {MAX_NODES} nodes'))
            break
        if depth > MAX_DEPTH:
            out.append((pointer, f'deeper than {MAX_DEPTH} levels'))
            continue
        problem = _node_problem(node, ref_count, vars_, role, typed)
        if problem is not None:
            out.append((pointer, problem))
            continue
        for child, child_pointer, child_role in reversed(_children(node, pointer)):
            stack.append((child, child_pointer, depth + 1, child_role))
    if out or not typed or operands is None or any(t not in OPERAND_TYPES for t in operands):
        return out
    return type_problems(ast, operands, result)


def _type_of(node, kids, operands):
    """``(type, problem)`` of a valid typed node whose children have the
    types ``kids`` (none of them ``None``)."""
    if 'num' in node or 'const' in node:
        return 'num', None
    if 'ref' in node:
        t = OPERAND_TYPES[operands[int(node['ref'])]]
        return (None, 'type: a function stands only in a call f(t)') if t == 'fn' else (t, None)
    if 'pair' in node:
        return ('vec', None) if kids == ['num', 'num'] else (None, f'type: ({kids[0]}, {kids[1]})')
    if 'call' in node:
        if OPERAND_TYPES[operands[int(node['call'])]] != 'fn':
            return None, f"type: call of a {operands[int(node['call'])]}"
        return ('num', None) if kids == ['num'] else (None, f'type: f({kids[0]})')
    if 'fn' in node:
        name = node['fn']
        if name in TYPED_FUNCTIONS:
            return ('num', None) if kids == ['vec'] else (None, f'type: {name}({kids[0]})')
        if name == 'abs':
            return 'num', None
        if all(k == 'num' for k in kids):
            return 'num', None
        return None, f'type: {name}({", ".join(kids)})'
    name = node['op']
    if name == 'neg':
        return kids[0], None
    a, b = kids
    if name in ('+', '-') and a == b:
        return a, None
    if name == '*':
        return ('num' if a == b else 'vec'), None
    if name == '/' and b == 'num':
        return a, None
    if name == '^' and a == b == 'num':
        return 'num', None
    return None, f'type: {a} {name} {b}'


def type_problems(ast, operands, result=None) -> list:
    """The type problems of a structurally valid typed tree (registry 1.10,
    docs/native/expr.md §6): ``[(pointer, message)]`` in pre-order, at most
    one per node. ``operands`` — the element types of ``refs``; ``result`` —
    the type the slot needs at the root (``None``: any). The pass runs
    bottom-up over the pre-order list (no recursion); a node with an
    untyped child is left untyped without a problem of its own, so one
    mistake is reported once."""
    operands = list(operands)
    order = []                                   # (node, pointer, parent index) in pre-order
    stack = [(ast, '', -1)]
    while stack:
        node, pointer, parent = stack.pop()
        index = len(order)
        order.append((node, pointer, parent))
        for child, child_pointer, _role in reversed(_children(node, pointer)):
            stack.append((child, child_pointer, index))
    kids = [[] for _ in order]
    types = [None] * len(order)
    found = []
    for index in range(len(order) - 1, -1, -1):
        node, pointer, parent = order[index]
        children = kids[index][::-1]             # filled right to left
        if all(t is not None for t in children):
            t, problem = _type_of(node, children, operands)
            if problem is not None:
                found.append((index, pointer, problem))
            types[index] = t
        if parent >= 0:
            kids[parent].append(types[index])
    if result is not None and types[0] is not None and types[0] != result:
        found.append((0, '', f'type: the formula gives {types[0]}, the slot needs {result}'))
    return [(pointer, problem) for _index, pointer, problem in sorted(found, key=lambda f: f[0])]
