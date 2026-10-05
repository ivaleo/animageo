"""The text of an AST v1 tree (docs/native/expr.md §4), for «Команды» and messages.

Precedence from low to high: ``+ -``, ``· /``, unary minus, ``^``
(right-associative), atoms; a right operand of the same level keeps its
parentheses, so the text reads back as the same tree.
"""
from __future__ import annotations

__all__ = ['to_text']

_LEVEL = {'+': 1, '-': 1, '*': 2, '/': 2, 'neg': 3, '^': 4}
_SIGN = {'+': ' + ', '-': ' - ', '*': '·', '/': '/'}
_ATOM = 5


def _level(node) -> int:
    if 'op' in node:
        return _LEVEL[node['op']]
    if 'num' in node and node['num'] < 0:
        return _LEVEL['neg']
    return _ATOM


def _wrap(text: str, wrap: bool) -> str:
    return f'({text})' if wrap else text


def _text(node, names) -> str:
    from ..commands.numbers import format_number

    if 'num' in node:
        return format_number(node['num'])
    if 'const' in node:
        return node['const']
    if 'ref' in node:
        k = int(node['ref'])
        return names[k] if k < len(names) else f'refs[{k}]'
    if 'fn' in node:
        return f"{node['fn']}({', '.join(_text(a, names) for a in node['args'])})"
    name = node['op']
    args = node['args']
    if name == 'neg':
        return '-' + _wrap(_text(args[0], names), _level(args[0]) <= _LEVEL['neg'])
    left, right = args
    if name == '^':
        return (_wrap(_text(left, names), _level(left) <= _LEVEL['^']) + '^'
                + _wrap(_text(right, names), _level(right) < _LEVEL['^']))
    level = _LEVEL[name]
    return (_wrap(_text(left, names), _level(left) < level) + _SIGN[name]
            + _wrap(_text(right, names), _level(right) <= level or _level(right) == _LEVEL['neg']))


def to_text(ast, names=()) -> str:
    """The text of the valid tree ``ast``; ``names[k]`` stands for ``{"ref": k}``."""
    return _text(ast, list(names))
