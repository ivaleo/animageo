"""Statements in «Команды» (plan L3 §4.1): ``Условие(…)``, ``Проверить(…)``,
check commands and ``Отношение(a, b)`` — tokens ↔ the statement AST of
:mod:`animageo.native.conditions.statements`.

::

    statement ::= expr ("=" | "≠") expr
                | obj ("∥" | "⟂") obj
                | point "∈" obj
                | obj "касается" obj
                | CheckCommand "(" arg { "," arg } ")"
    expr      ::= term { ("+" | "-") term }
    term      ::= unary { ("·" | "/") unary }
    unary     ::= ("-" | "+") unary | power
    power     ::= atom [ "^" unary ]
    atom      ::= number [ "°" ] | "π" | "(" expr ")" | "|" obj "|" | "∠" ABC | "∠" α
                | "√" atom | fn "(" expr { "," expr } ")" | name of a number or an angle
    obj       ::= name of an element | pair of points (AB)

``A = B`` of two points is ``coincident``. A name of an element wins over a
pair of points, as in arguments. Structural: names resolve against the lines
above.
"""
from __future__ import annotations

from ..conditions.statements import statement_problems
from .issues import LineError
from .lexicon import CHECK_KINDS, normalize_name
from .numbers import format_number
from .syntax import literal_value

__all__ = ['parse_statement', 'parse_objects', 'statement_text', 'FUNCTIONS']

FUNCTIONS = {'sqrt': 1, 'abs': 1, 'sin': 1, 'cos': 1, 'tan': 1, 'atan': 1, 'asin': 1, 'acos': 1, 'exp': 1,
             'ln': 1, 'lg': 1, 'min': 2, 'max': 2}
_RELATIONS = {'=': 'eq', '≠': 'ne', '∥': 'parallel', '⟂': 'perpendicular', '∈': 'on'}
_PRINT_REL = {'eq': '=', 'ne': '≠', 'parallel': '∥', 'perpendicular': '⟂'}
_KIND_TEXT = {'point': 'точка', 'line': 'прямая', 'segment': 'отрезок', 'ray': 'луч', 'circle': 'окружность',
              'number': 'число', 'angle': 'угол', 'vector': 'вектор', 'polygon': 'многоугольник'}


def _is(tok, text) -> bool:
    return tok.kind == 'sym' and tok.text == text


def _split_commas(tokens):
    parts, current, depth = [], [], 0
    for tok in tokens:
        if _is(tok, '('):
            depth += 1
        elif _is(tok, ')'):
            depth -= 1
        if depth == 0 and _is(tok, ','):
            parts.append(current)
            current = []
            continue
        current.append(tok)
    parts.append(current)
    return parts


class _Expr:
    """A recursive-descent parser of an expression over ``tokens``."""

    def __init__(self, tokens, resolver, end_column):
        self.t = tokens
        self.i = 0
        self.r = resolver
        self.end = end_column

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def column(self):
        tok = self.peek()
        return tok.column if tok is not None else self.end

    def take(self, text):
        tok = self.peek()
        if tok is not None and _is(tok, text):
            self.i += 1
            return tok
        return None

    def expect(self, text):
        if self.take(text) is None:
            raise LineError('syntax', self.column(), f'нужно «{text}»')

    def parse(self):
        node = self.sum()
        if self.peek() is not None:
            raise LineError('syntax', self.column(), 'непонятное выражение')
        return node

    def sum(self):
        node = self.product()
        while True:
            if self.take('+'):
                node = {'op': '+', 'args': [node, self.product()]}
            elif self.take('-'):
                node = {'op': '-', 'args': [node, self.product()]}
            else:
                return node

    def product(self):
        node = self.unary()
        while True:
            if self.take('·'):
                node = {'op': '*', 'args': [node, self.unary()]}
            elif self.take('/'):
                node = {'op': '/', 'args': [node, self.unary()]}
            else:
                return node

    def unary(self):
        if self.take('-'):
            inner = self.unary()
            if set(inner) == {'num'}:
                return {'num': -inner['num']}
            return {'op': 'neg', 'args': [inner]}
        if self.take('+'):
            return self.unary()
        return self.power()

    def power(self):
        node = self.atom()
        if self.take('^'):
            node = {'op': '^', 'args': [node, self.unary()]}
        return node

    def atom(self):
        tok = self.peek()
        if tok is None:
            raise LineError('syntax', self.end, 'не хватает выражения')
        if tok.kind == 'number':
            self.i += 1
            if self.take('°'):
                return {'deg': literal_value(tok.text)}
            return {'num': literal_value(tok.text)}
        if self.take('('):
            node = self.sum()
            self.expect(')')
            return node
        if self.take('√'):
            return {'fn': 'sqrt', 'args': [self.atom()]}
        if self.take('|'):
            start = self.i
            while self.i < len(self.t) and not _is(self.t[self.i], '|'):
                self.i += 1
            if self.i >= len(self.t):
                raise LineError('syntax', tok.column, 'не хватает «|»')
            inner = self.t[start:self.i]
            self.i += 1
            return {'len': self.r.obj(inner, tok.end, ('segment', 'vector'))}
        if self.take('∠'):
            name = self.peek()
            if name is None or name.kind != 'name':
                raise LineError('syntax', tok.end, 'после «∠» нужны три точки или имя угла')
            self.i += 1
            el = self.r.element(name.text)
            if el is not None and self.r.type_of(el) == 'angle':
                return {'angle': {'ref': el}}
            return {'angle': [{'ref': p} for p in self.r.split(name.text, name.column, 3)]}
        if tok.kind == 'name':
            self.i += 1
            nxt = self.peek()
            if nxt is not None and _is(nxt, '(') and tok.text in FUNCTIONS:
                self.i += 1
                close = self._close()
                args = [_Expr(part, self.r, tok.end).parse() for part in _split_commas(self.t[self.i:close])]
                self.i = close + 1
                if len(args) != FUNCTIONS[tok.text]:
                    raise LineError('arity', tok.column, f'у {tok.text} аргументов: {FUNCTIONS[tok.text]}')
                return {'fn': tok.text, 'args': args}
            if tok.text in ('π', 'pi') and self.r.element(tok.text) is None:
                return {'const': 'pi'}
            el = self.r.element(tok.text)
            if el is None:
                self.r.unknown(tok.text, tok.column)
            el_type = self.r.type_of(el)
            if el_type == 'number':
                return {'ref': el}
            if el_type == 'angle':
                return {'angle': {'ref': el}}
            if el_type in ('segment', 'vector'):
                raise LineError('type_mismatch', tok.column, f'длина пишется так: |{tok.text}|',
                                hint=f'|{tok.text}|')
            raise LineError('type_mismatch', tok.column,
                            f'{tok.text} — {_KIND_TEXT.get(el_type, el_type)}, а нужно число')
        raise LineError('syntax', tok.column, f'непонятный знак «{tok.text}» в выражении')

    def _close(self):
        depth = 1
        for k in range(self.i, len(self.t)):
            if _is(self.t[k], '('):
                depth += 1
            elif _is(self.t[k], ')'):
                depth -= 1
                if depth == 0:
                    return k
        raise LineError('syntax', self.column(), 'не хватает «)»')


def _top_relation(tokens, lex):
    """``(index, kind)`` of the one top-level relation of ``tokens``."""
    found, depth = [], 0
    for i, tok in enumerate(tokens):
        if _is(tok, '('):
            depth += 1
        elif _is(tok, ')'):
            depth -= 1
        elif depth == 0:
            if tok.kind == 'sym' and tok.text in _RELATIONS:
                found.append((i, _RELATIONS[tok.text]))
            elif tok.kind == 'name' and lex.keyword(tok.text) == 'touches':
                found.append((i, 'tangent'))
    if len(found) > 1:
        raise LineError('syntax', tokens[found[1][0]].column, 'в утверждении один знак отношения')
    return found[0] if found else None


def _single_name(tokens, column, what='имя'):
    if len(tokens) != 1 or tokens[0].kind != 'name':
        raise LineError('syntax', tokens[0].column if tokens else column, f'нужно {what}')
    return tokens[0]


def parse_objects(tokens, resolver, column):
    """The objects of ``Отношение(a, b)``: element IDs or ``{"pair": [P, Q]}``."""
    parts = _split_commas(tokens)
    if len(parts) != 2:
        raise LineError('arity', column, 'у Отношение два аргумента')
    out = []
    for part in parts:
        obj = resolver.obj(part, column)
        out.append(obj['ref'] if 'ref' in obj else {'pair': obj['pair']})
    return out


def _check_call(tokens, resolver, lex, column):
    k = 0
    while k < len(tokens) and tokens[k].kind == 'name':
        k += 1
    name = ' '.join(t.text for t in tokens[:k])
    kind = lex.check_kind(name)
    args = _split_commas(tokens[k + 1:-1])
    shape = CHECK_KINDS[kind]
    col = tokens[k].column
    if any(not part for part in args):
        raise LineError('syntax', col, 'пустой аргумент')
    if shape in ('two', 'point_object', 'two_points') and len(args) != 2:
        raise LineError('arity', col, f'у {name} два аргумента')
    if shape == 'two':
        return {'kind': kind, 'a': resolver.obj(args[0], col), 'b': resolver.obj(args[1], col)}
    if shape == 'point_object':
        return {'kind': 'on', 'point': resolver.point(_single_name(args[0], col, 'точка')),
                'object': resolver.obj(args[1], col)}
    if shape == 'two_points':
        return {'kind': kind, 'points': [resolver.point(_single_name(a, col, 'точка')) for a in args]}
    least = 4 if kind == 'concyclic' else 3
    if len(args) < least:
        raise LineError('arity', col, f'у {name} не меньше {least} аргументов')
    if shape == 'points':
        return {'kind': kind, 'points': [resolver.point(_single_name(a, col, 'точка')) for a in args]}
    return {'kind': kind, 'lines': [resolver.obj(a, col) for a in args]}


def parse_statement(tokens, resolver, lex, column, doc=None):
    """The statement AST of ``tokens``; raises :class:`LineError`.
    ``resolver`` gives ``element(name)``, ``type_of(id)``, ``split(text,
    column, parts)``, ``unknown(text, column)``, ``obj(tokens, column,
    types=None)`` and ``point(token)``; ``doc`` — for the structural check."""
    if not tokens:
        raise LineError('syntax', column, 'нужно утверждение')
    rel = _top_relation(tokens, lex)
    if rel is None:
        first = tokens[0]
        k = 0
        while k < len(tokens) and tokens[k].kind == 'name':
            k += 1
        if k and lex.check_kind(' '.join(t.text for t in tokens[:k])) is not None:
            statement = _check_call(tokens, resolver, lex, column)
        else:
            raise LineError('syntax', first.column, 'нужно утверждение: =, ≠, ∥, ⟂, ∈ или «касается»')
    else:
        i, kind = rel
        left, right = tokens[:i], tokens[i + 1:]
        sign = tokens[i]
        if not left or not right:
            raise LineError('syntax', sign.column, f'по обе стороны «{sign.text}» нужно по объекту')
        if kind in ('parallel', 'perpendicular', 'tangent'):
            statement = {'kind': kind, 'a': resolver.obj(left, sign.column), 'b': resolver.obj(right, sign.column)}
        elif kind == 'on':
            statement = {'kind': 'on', 'point': resolver.point(_single_name(left, sign.column, 'точка')),
                         'object': resolver.obj(right, sign.column)}
        else:
            points = [resolver.element(side[0].text) if len(side) == 1 and side[0].kind == 'name' else None
                      for side in (left, right)]
            if kind == 'eq' and all(p is not None and resolver.type_of(p) == 'point' for p in points):
                statement = {'kind': 'coincident', 'points': [{'ref': p} for p in points]}
            else:
                statement = {'kind': kind, 'left': _Expr(left, resolver, sign.column).parse(),
                             'right': _Expr(right, resolver, sign.end).parse()}
    if doc is not None:
        problems = statement_problems(statement, doc)
        if problems:
            raise LineError('type_mismatch', tokens[0].column, f'утверждение не подходит: {problems[0][2]}')
    return statement


# ── printing ──────────────────────────────────────────────────────────────

_LEVEL = {'+': 1, '-': 1, '*': 2, '/': 2, 'neg': 3, '^': 4}
_SIGN = {'+': ' + ', '-': ' - ', '*': '·', '/': '/'}
_ATOM = 5


def _level(node) -> int:
    if 'op' in node:
        return _LEVEL.get(node['op'], _ATOM)
    if 'num' in node and isinstance(node['num'], (int, float)) and node['num'] < 0:
        return _LEVEL['neg']
    return _ATOM


def _wrap(text, wrap):
    return f'({text})' if wrap else text


class _Names:
    def __init__(self, names):
        self.names = names

    def name(self, el_id):
        return self.names.get(el_id) or el_id

    def obj(self, node):
        if 'pair' in node:
            return ''.join(self.name(p) for p in node['pair'])
        return self.name(node['ref'])

    def expr(self, node):
        if 'num' in node:
            return format_number(node['num'])
        if 'deg' in node:
            return format_number(node['deg']) + '°'
        if 'const' in node:
            return 'π'
        if 'ref' in node:
            return self.name(node['ref'])
        if 'len' in node:
            return f"|{self.obj(node['len'])}|"
        if 'angle' in node:
            arg = node['angle']
            if isinstance(arg, list):
                return '∠' + ''.join(self.name(p['ref']) for p in arg)
            return self.name(arg['ref'])
        if 'fn' in node:
            return f"{node['fn']}({', '.join(self.expr(a) for a in node['args'])})"
        name, args = node['op'], node['args']
        if name == 'neg':
            return '-' + _wrap(self.expr(args[0]), _level(args[0]) <= _LEVEL['neg'])
        left, right = args
        if name == '^':
            return (_wrap(self.expr(left), _level(left) <= _LEVEL['^']) + '^'
                    + _wrap(self.expr(right), _level(right) < _LEVEL['^']))
        level = _LEVEL[name]
        return (_wrap(self.expr(left), _level(left) < level) + _SIGN[name]
                + _wrap(self.expr(right), _level(right) <= level or _level(right) == _LEVEL['neg']))


def statement_text(statement, names: dict, lex) -> str:
    """The text of ``statement`` with display names ``names`` (element ID →
    name): ``|AB| = |AC|``, ``AB ∥ CD``, ``C ∈ ω``, ``CD касается w``; the
    kinds without a sign print as their check command."""
    n = _Names(names)
    kind = statement['kind']
    if kind in ('eq', 'ne'):
        return f"{n.expr(statement['left'])} {_PRINT_REL[kind]} {n.expr(statement['right'])}"
    if kind in ('parallel', 'perpendicular'):
        return f"{n.obj(statement['a'])} {_PRINT_REL[kind]} {n.obj(statement['b'])}"
    if kind == 'tangent':
        return f"{n.obj(statement['a'])} {lex.word('touches')} {n.obj(statement['b'])}"
    if kind == 'on':
        return f"{n.obj(statement['point'])} ∈ {n.obj(statement['object'])}"
    if kind == 'coincident':
        a, b = statement['points']
        return f"{n.obj(a)} = {n.obj(b)}"
    command = lex.check_name(kind) or kind
    if kind == 'congruent':
        items = [statement['a'], statement['b']]
    else:
        items = statement.get('points') or statement.get('lines') or []
    return f"{command}({', '.join(n.obj(i) for i in items)})"


def normalize_word(word: str) -> str:
    return normalize_name(word)
