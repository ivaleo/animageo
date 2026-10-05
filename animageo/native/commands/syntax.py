"""The subset of the command grammar (appendix Б of the constructions spec)
that the library applies; commands.md §2.

::

    line   ::= [ names "=" ] right [ "#" text ]
    names  ::= name { "," name }
    right  ::= Command "(" [ arg { "," arg } ] ")"
             | "(" number "," number ")"          → point.free
             | number [ "°" ]                       → number.free
             | "∠" name                             → angle.by_points
    arg    ::= name | number [ "°" ] | "не" name | "∠" name | "(" number "," number ")"
    number ::= [ "+" | "-" ] digits

A command name may be several words (``Серединный перпендикуляр``). The rest
of the grammar — ``Условие``, ``Проверить``, equations, functions,
inequalities, expressions, ``key = value``, ``около A`` — is refused with the
error ``forbidden`` («… будет позже»).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .issues import LineError
from .lexicon import normalize_name

__all__ = ['Arg', 'Name', 'Statement', 'parse_line', 'literal_value']

_LATER = 'будет позже'
_LATER_PL = 'будут позже'
_COMPARE = frozenset('<>≤≥')
_STATEMENT = frozenset('≠∥⟂∈')
_OPERATORS = frozenset('+-·/^√|!∠°∧∨')


@dataclass(frozen=True)
class Name:
    text: str
    column: int


@dataclass(frozen=True)
class Arg:
    """``kind``: ``name``, ``number``, ``point``, ``not`` (``не A``) or
    ``angle3`` (``∠ABC``); ``text`` — the name (after ``не``/``∠``);
    ``value`` — a float or an ``(x, y)`` pair; ``column`` — where it starts."""

    kind: str
    column: int
    text: str = ''
    value: object = None
    name_column: int = 0


@dataclass
class Statement:
    """One parsed line. ``kind``: ``call``, ``point``, ``number``, ``angle3``."""

    line: int
    kind: str
    column: int
    names: list = field(default_factory=list)
    command: str = ''
    command_column: int = 0
    args: list = field(default_factory=list)
    value: object = None
    text: str = ''


def literal_value(digits: str, sign: str = '', degrees: bool = False) -> float:
    """The float of a number literal; ``°`` gives radians ``(v · π) / 180``."""
    value = float(digits)
    if sign == '-':
        value = -value
    if degrees:
        value = value * math.pi / 180.0
    return value


def _matching(tokens, start: int) -> int:
    depth = 0
    for i in range(start, len(tokens)):
        tok = tokens[i]
        if tok.kind == 'sym' and tok.text == '(':
            depth += 1
        elif tok.kind == 'sym' and tok.text == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _check_balance(tokens) -> None:
    stack = []
    for tok in tokens:
        if tok.kind != 'sym':
            continue
        if tok.text == '(':
            stack.append(tok)
        elif tok.text == ')':
            if not stack:
                raise LineError('syntax', tok.column, 'лишняя «)»')
            stack.pop()
    if stack:
        raise LineError('syntax', stack[-1].column, 'не хватает «)»')


def _split_top(tokens, sym: str):
    """Segments of ``tokens`` between top-level ``sym``; each segment is
    ``(tokens, separator before it or None)``."""
    parts, current, depth, sep = [], [], 0, None
    for tok in tokens:
        if tok.kind == 'sym' and tok.text == '(':
            depth += 1
        elif tok.kind == 'sym' and tok.text == ')':
            depth -= 1
        if depth == 0 and tok.kind == 'sym' and tok.text == sym:
            parts.append((current, sep))
            current, sep = [], tok
            continue
        current.append(tok)
    parts.append((current, sep))
    return parts


def _is_sym(tok, text) -> bool:
    return tok.kind == 'sym' and tok.text == text


def _top_syms(tokens) -> set:
    out, depth = set(), 0
    for tok in tokens:
        if _is_sym(tok, '('):
            depth += 1
        elif _is_sym(tok, ')'):
            depth -= 1
        elif depth == 0 and tok.kind == 'sym':
            out.add(tok.text)
    return out


def _signed_number(tokens):
    """``(value, column)`` when ``tokens`` is ``[+|-] number [°]``, else ``None``."""
    i, sign = 0, ''
    if tokens and tokens[0].kind == 'sym' and tokens[0].text in '+-':
        sign = tokens[0].text
        i = 1
    if i >= len(tokens) or tokens[i].kind != 'number':
        return None
    digits = tokens[i].text
    i += 1
    degrees = False
    if i < len(tokens) and _is_sym(tokens[i], '°'):
        degrees = True
        i += 1
    if i != len(tokens):
        return None
    return literal_value(digits, sign, degrees), tokens[0].column


def _point_literal(tokens):
    """``((x, y), column)`` when ``tokens`` is ``( number , number )``."""
    if len(tokens) < 5 or not _is_sym(tokens[0], '(') or _matching(tokens, 0) != len(tokens) - 1:
        return None
    parts = _split_top(tokens[1:-1], ',')
    if len(parts) != 2:
        return None
    values = [_signed_number(part) for part, _sep in parts]
    if any(v is None for v in values):
        return None
    return (values[0][0], values[1][0]), tokens[0].column


def _has_xy(tokens) -> bool:
    return any(t.kind == 'name' and t.text in ('x', 'y') for t in tokens)


def _forbidden_expression(tokens, column: int, where: str = ''):
    if _has_xy(tokens):
        raise LineError('forbidden', column, f'уравнения и функции {_LATER_PL}')
    raise LineError('forbidden', column, f'выражения{where} {_LATER_PL}')


def _parse_arg(tokens, column: int) -> Arg:
    if not tokens:
        raise LineError('syntax', column, 'пустой аргумент')
    first = tokens[0]
    if '=' in _top_syms(tokens):
        raise LineError('forbidden', first.column, f'«ключ = значение» {_LATER}')
    if len(tokens) == 1 and first.kind == 'name':
        if normalize_name(first.text) in ('не', 'около'):
            raise LineError('syntax', first.end, f'после «{first.text}» нужна точка')
        return Arg('name', first.column, first.text, name_column=first.column)
    if first.kind == 'name' and normalize_name(first.text) in ('не', 'около'):
        if len(tokens) == 2 and tokens[1].kind == 'name':
            target = tokens[1]
            if normalize_name(first.text) == 'около':
                raise LineError('forbidden', first.column, f'«около {target.text}» {_LATER}',
                                hint=f'не {target.text}')
            return Arg('not', first.column, target.text, name_column=target.column)
    if len(tokens) == 2 and _is_sym(first, '∠') and tokens[1].kind == 'name':
        return Arg('angle3', first.column, tokens[1].text, name_column=tokens[1].column)
    number = _signed_number(tokens)
    if number is not None:
        return Arg('number', first.column, value=number[0])
    point = _point_literal(tokens)
    if point is not None:
        return Arg('point', first.column, value=point[0])
    if all(t.kind == 'name' for t in tokens):
        raise LineError('syntax', tokens[1].column, 'между аргументами нужна запятая')
    if any(_is_sym(t, '(') for t in tokens) or any(t.kind == 'sym' and t.text in _OPERATORS for t in tokens):
        _forbidden_expression(tokens, first.column, ' в аргументах')
    raise LineError('syntax', first.column, 'непонятный аргумент')


def _parse_right(tokens, line: int, names, column_eq: int) -> Statement:
    if not tokens:
        raise LineError('syntax', column_eq, 'нет правой части после «=»')
    first = tokens[0]
    top = _top_syms(tokens)
    if top & _COMPARE:
        raise LineError('forbidden', first.column, f'неравенства {_LATER_PL}')
    if top & _STATEMENT:
        raise LineError('forbidden', first.column, f'условия и проверки {_LATER_PL}')
    point = _point_literal(tokens)
    if point is not None:
        return Statement(line, 'point', first.column, names, value=point[0])
    number = _signed_number(tokens)
    if number is not None:
        return Statement(line, 'number', first.column, names, value=number[0])
    if len(tokens) == 2 and _is_sym(first, '∠') and tokens[1].kind == 'name':
        return Statement(line, 'angle3', first.column, names, text=tokens[1].text,
                         command_column=tokens[1].column)
    k = 0
    while k < len(tokens) and tokens[k].kind == 'name':
        k += 1
    if 0 < k < len(tokens) and _is_sym(tokens[k], '('):
        close = _matching(tokens, k)
        if close != len(tokens) - 1:
            _forbidden_expression(tokens, first.column)
        command = ' '.join(t.text for t in tokens[:k])
        inner = tokens[k + 1:close]
        args = []
        if inner:
            for part, sep in _split_top(inner, ','):
                col = sep.column if sep is not None else tokens[k].column
                args.append(_parse_arg(part, col))
        if not args and normalize_name(command) in ('условие', 'проверить'):
            raise LineError('forbidden', first.column, f'условия и проверки {_LATER_PL}')
        return Statement(line, 'call', first.column, names, command=command,
                         command_column=first.column, args=args)
    if len(tokens) == 1 and first.kind == 'name':
        raise LineError('forbidden', first.column, f'копия объекта («= {first.text}») {_LATER}')
    if top & set(',;:[]') or k == len(tokens):
        raise LineError('syntax', first.column, 'непонятная правая часть')
    _forbidden_expression(tokens, first.column)


def parse_line(tokens, line: int):
    """The :class:`Statement` of one line's tokens (comment removed), or
    ``None`` for an empty line; raises :class:`LineError`."""
    if not tokens:
        return None
    first = tokens[0]
    if first.kind == 'name' and normalize_name(first.text) in ('условие', 'проверить'):
        raise LineError('forbidden', first.column, f'условия и проверки {_LATER_PL}')
    _check_balance(tokens)
    parts = _split_top(tokens, '=')
    if len(parts) > 2:
        raise LineError('forbidden', first.column, f'уравнения {_LATER_PL}')
    if len(parts) == 1:
        return _parse_right(tokens, line, [], first.column)
    (left, _), (right, eq) = parts
    if not left:
        raise LineError('syntax', eq.column, 'нет имени слева от «=»')
    if (len(left) == 4 and left[0].kind == 'name' and _is_sym(left[1], '(')
            and left[2].kind == 'name' and _is_sym(left[3], ')')):
        raise LineError('forbidden', first.column, f'функции {_LATER_PL}')
    names = []
    bad = None
    for i, tok in enumerate(left):
        if i % 2 == 0 and tok.kind == 'name':
            names.append(Name(tok.text, tok.column))
        elif i % 2 == 1 and _is_sym(tok, ','):
            continue
        else:
            bad = tok
            break
    if bad is None and len(left) % 2 == 0:
        bad = left[-1]
    if bad is not None:
        if all(t.kind == 'name' or _is_sym(t, ',') for t in left):
            raise LineError('syntax', bad.column, 'имена слева перечисляются через запятую')
        raise LineError('forbidden', first.column, f'уравнения {_LATER_PL}')
    if len(names) == 1 and names[0].text in ('x', 'y'):
        raise LineError('forbidden', first.column, f'уравнения {_LATER_PL}')
    return _parse_right(right, line, names, eq.column)
