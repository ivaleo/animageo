"""Expressions of numbers of a ``.ggb``, read by the import itself (1.10.0a3).

The classic parser turns the expression of a ``.ggb`` into DSL code and does
not take what GeoGebra itself writes: ``sqrt(a)``, ``sin(a)`` and the other
lowercase functions over objects, the implicit product (``2a``, ``a b``,
``2(a + b)``), the powers ``a²``, ``π``; its ``abs`` of a computed value has
no signature. Decision 3 of the tech lead (1.10.0a2): the classic parser is
the behaviour of production (``loadGGB``) and is not changed. The import
reads the expression of a number here instead — only where the classic does
not translate it — into an AST v1 tree of ``number.expression``
(``docs/native/expr.md``) whose ``{"ref": k}`` is the label ``labels[k]``
of the file.

Nothing is evaluated: the text is tokenized and read by recursive descent,
within a length and a depth. The grammar is GeoGebra's: ``+ −`` below
``· /`` and the implicit product (left to right), then the unary minus, then
``^`` (right-associative; ``−a²`` is ``−(a²)``), then the postfix
superscript power and ``°``.

    parse_number(text, kinds)   → (ast, labels) or ExprError(reason, detail)
    names_in(texts, labels)     → the labels the texts refer to, outside string literals
"""
from __future__ import annotations

import math
import re

__all__ = ['ExprError', 'MAX_CHARS', 'parse_number', 'parse_typed', 'names_in', 'strip_strings', 'NUMBER_KINDS']

MAX_CHARS = 1000            # a longer expression is past the limits of AST v1 anyway (256 nodes)
NUMBER_KINDS = ('numeric', 'angle')     # GGB types an expression of a number may refer to (an angle in radians)

_SUPERSCRIPT = '⁰¹²³⁴⁵⁶⁷⁸⁹'
_NOT_SUP = '(?![' + _SUPERSCRIPT + '])'
# a label: a letter, then letters, digits, ``_`` and primes; ``_{…}`` closes it (``t_{AB}``; a label
# has at most 200 characters, so the braces are looked for no further). A superscript digit is a power,
# not a part of the name (``a²``).
_NAME = re.compile('(?:' + _NOT_SUP + r"[^\W\d](?:" + _NOT_SUP + r"[\w'])*?_\{[^}]{0,200}\}"
                   + '|' + _NOT_SUP + r"[^\W\d](?:" + _NOT_SUP + r"[\w'])*)")
_NUMBER = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:E[+-]?\d+)?')
_SUP = re.compile('[⁻⁺]?[' + _SUPERSCRIPT + ']+')
_SPACE = re.compile(r'\s+')
_OPERATORS = {'+': '+', '-': '-', '−': '-', '*': '*', '·': '*', '⋅': '*', '×': '*', '∙': '*', '/': '/', '÷': '/',
              '^': '^', '(': '(', ')': ')', '[': '[', ']': ']', ',': ','}

# lowercase functions of GeoGebra → AST v1 (``log`` of one argument is the natural one, as in GeoGebra)
_FUNCTIONS = {'sqrt': 'sqrt', 'abs': 'abs', 'sin': 'sin', 'cos': 'cos', 'tan': 'tan', 'asin': 'asin',
              'arcsin': 'asin', 'acos': 'acos', 'arccos': 'acos', 'atan': 'atan', 'arctan': 'atan', 'exp': 'exp',
              'ln': 'ln', 'log': 'ln', 'lg': 'lg'}
_RECIPROCALS = {'cot': 'tan', 'sec': 'cos', 'csc': 'sin'}
_COMMANDS = {'Min': 'min', 'Max': 'max', 'min': 'min', 'max': 'max'}      # of two numbers (the text of AST v1 too)


class ExprError(ValueError):
    """The expression is not read: ``reason`` — ``parse_error`` (not an
    expression of GeoGebra this module knows) or ``formula_unsupported``
    (read, but not a formula of the kernel); ``detail`` — for people."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f'{reason}: {detail}')
        self.reason = reason
        self.detail = detail[:300]


def strip_strings(text: str) -> str:
    """``text`` with every string literal (``"…"``, ``\\"`` inside it is a
    quote, as in the classic ``split_text_parts``) replaced by one space."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c != '"':
            out.append(c)
            i += 1
            continue
        j = i + 1
        while j < n and text[j] != '"':
            j += 2 if text[j] == '\\' and j + 1 < n and text[j + 1] == '"' else 1
        out.append(' ')
        i = j + 1
    return ''.join(out)


def names_in(texts, labels) -> list:
    """The labels (of ``labels``) the texts refer to, in order, once each: a
    text that is a label is that label; otherwise the names outside its string
    literals (the letters of ``"$S = \\frac{1}{2} a h_a$"`` are no reference)."""
    out = []
    for text in texts:
        text = str(text)
        found = [text] if text in labels else [t for t in _NAME.findall(strip_strings(text)) if t in labels]
        for t in found:
            if t not in out:
                out.append(t)
    return out


def _tokens(text: str, *, conditions=False) -> list:
    """``[(kind, value)]``: ``num`` (float), ``name``, ``sup`` (int), ``deg``,
    ``op`` (one of :data:`_OPERATORS` values); ``ExprError`` on anything else."""
    out, i, n = [], 0, len(text)
    while i < n:
        m = _SPACE.match(text, i)
        if m:
            i = m.end()
            continue
        c = text[i]
        if conditions:
            pair = text[i:i + 2]
            if pair in ('<=', '>=', '&&', '||'):
                out.append(('op', pair))
                i += 2
                continue
            if c in '<>≤≥!':
                out.append(('op', {'≤': '<=', '≥': '>='}.get(c, c)))
                i += 1
                continue
        m = _NUMBER.match(text, i)
        if m:
            try:
                value = float(m.group())
            except ValueError:        # pragma: no cover — the pattern is a float
                raise ExprError('parse_error', f'число {m.group()[:20]}') from None
            if not math.isfinite(value):
                raise ExprError('formula_unsupported', f'число {m.group()[:20]} вне формул')
            out.append(('num', value))
            i = m.end()
            continue
        m = _NAME.match(text, i)
        if m:
            out.append(('name', m.group()))
            i = m.end()
            continue
        m = _SUP.match(text, i)
        if m:
            digits = m.group().translate(str.maketrans(_SUPERSCRIPT + '⁻⁺', '0123456789-+'))
            out.append(('sup', int(digits)))
            i = m.end()
            continue
        if c == '°':
            out.append(('deg', None))
        elif c in _OPERATORS:
            out.append(('op', _OPERATORS[c]))
        else:
            raise ExprError('parse_error', f'знак {c!r} не входит в выражения чисел')
        i += 1
    return out


def _negative(node):
    """``−node``; the minus of a literal is a negative literal (``2^-1``, as the classic reads ``-1``)."""
    if set(node) == {'num'}:
        return {'num': -node['num']}
    return {'op': 'neg', 'args': [node]}


class _Reader:
    """Recursive descent over :func:`_tokens`; ``labels`` — the references in order."""

    def __init__(self, tokens, kinds, variables=(), *, typed=False):
        self.variables = variables
        self.typed = typed
        self.t = tokens
        self.i = 0
        self.kinds = kinds
        self.labels: list = []
        self.depth = 0

    # -- tokens ---------------------------------------------------------------
    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def is_op(self, *ops, k=0):
        kind, value = self.peek(k)
        return kind == 'op' and value in ops

    def expect(self, op):
        if not self.is_op(op):
            kind, value = self.peek()
            raise ExprError('parse_error', f'ожидалось «{op}», а не {value if kind else "конец"}')
        self.i += 1

    def deeper(self):
        self.depth += 1
        if self.depth > 32:
            raise ExprError('formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)')

    # -- grammar --------------------------------------------------------------
    def read(self):
        node = self.sum()
        kind, value = self.peek()
        if kind is not None:
            raise ExprError('parse_error', f'лишнее в выражении: {value!r}')
        return node

    def sum(self):
        node = self.product()
        while self.is_op('+', '-'):
            op = self.take()[1]
            node = {'op': op, 'args': [node, self.product()]}
        return node

    def product(self):
        node = self.unary()
        while True:
            if self.is_op('*', '/'):
                op = self.take()[1]
                node = {'op': op, 'args': [node, self.unary()]}
            elif self.starts_factor():
                node = {'op': '*', 'args': [node, self.power()]}      # the implicit product: 2a, a b, 2(a + b)
            else:
                return node

    def starts_factor(self) -> bool:
        kind, _value = self.peek()
        if kind == 'name' or self.is_op('('):
            return True
        if kind == 'num':
            prev_kind, _ = self.t[self.i - 1] if self.i else (None, None)
            if prev_kind in ('num', 'sup', 'deg'):
                raise ExprError('parse_error', 'два числа подряд')
            return True
        return False

    def unary(self):
        if self.is_op('-'):
            self.take()
            self.deeper()
            node = _negative(self.unary())
            self.depth -= 1
            return node
        if self.is_op('+'):
            self.take()
            if not self.typed:
                return self.unary()
            self.deeper()
            node = self.unary()
            self.depth -= 1
            return node
        return self.power()

    def power(self):
        base = self.postfix()
        if not self.is_op('^'):
            return base
        self.take()
        self.deeper()
        node = {'op': '^', 'args': [base, self.exponent()]}
        self.depth -= 1
        return node

    def exponent(self):
        if self.is_op('-'):
            self.take()
            self.deeper()
            node = _negative(self.exponent())
            self.depth -= 1
            return node
        if self.is_op('+'):
            self.take()
            if not self.typed:
                return self.exponent()
            self.deeper()
            node = self.exponent()
            self.depth -= 1
            return node
        return self.power()

    def postfix(self):
        node = self.primary()
        while True:
            kind, value = self.peek()
            if kind == 'sup':
                self.take()
                node = {'op': '^', 'args': [node, {'num': float(value)}]}
            elif kind == 'deg':
                self.take()
                node = {'op': '*', 'args': [node, {'op': '/', 'args': [{'const': 'pi'}, {'num': 180.0}]}]}
            else:
                return node

    def primary(self):
        kind, value = self.peek()
        if kind == 'num':
            self.take()
            return {'num': value}
        if self.is_op('('):
            self.take()
            self.deeper()
            node = self.sum()
            if self.typed and self.is_op(','):
                self.take()
                node = {'pair': [node, self.sum()]}
                if self.is_op(','):
                    raise ExprError('formula_unsupported', 'пара должна содержать ровно две координаты')
            self.expect(')')
            self.depth -= 1
            return node
        if kind == 'name':
            self.take()
            return self.name(value)
        raise ExprError('parse_error', f'ожидалось число или имя, а не {value if kind else "конец"}')

    def arguments(self):
        close = ')' if self.take()[1] == '(' else ']'
        self.deeper()
        args = [self.sum()]
        while self.is_op(','):
            self.take()
            args.append(self.sum())
        self.expect(close)
        self.depth -= 1
        return args

    def name(self, name):
        call = self.is_op('(', '[')
        if name in self.variables:
            return {'var': name}
        kind = self.kinds.get(name)
        if kind is not None:
            allowed = NUMBER_KINDS + ('point', 'vector', 'function') if self.typed else NUMBER_KINDS
            if kind not in allowed:
                what = 'функция' if kind in ('function', 'functionnvar') else 'не число'
                raise ExprError('formula_unsupported', f'в выражении {name[:40]} — {what}: в формулу входят '
                                                       'только числа и углы')
            if name not in self.labels:
                self.labels.append(name)
            index = self.labels.index(name)
            if self.typed and kind == 'function' and call:
                args = self.arguments()
                if len(args) != 1:
                    raise ExprError('formula_unsupported', 'функция должна иметь один аргумент')
                return {'call': index, 'args': args}
            return {'ref': index}
        if self.typed and call and name in ('x', 'y'):
            args = self.arguments()
            if len(args) != 1:
                raise ExprError('formula_unsupported', 'компонента должна иметь один аргумент')
            return {'fn': name, 'args': args}
        if call and name in _FUNCTIONS:
            args = self.arguments()
            if name == 'log' and len(args) == 2:            # log(b, x): the logarithm of x to the base b
                return {'op': '/', 'args': [{'fn': 'ln', 'args': [args[1]]}, {'fn': 'ln', 'args': [args[0]]}]}
            if len(args) != 1:
                raise ExprError('parse_error', f'у {name} один аргумент')
            return {'fn': _FUNCTIONS[name], 'args': args}
        if call and name in _RECIPROCALS:
            args = self.arguments()
            if len(args) != 1:
                raise ExprError('parse_error', f'у {name} один аргумент')
            return {'op': '/', 'args': [{'num': 1.0}, {'fn': _RECIPROCALS[name], 'args': args}]}
        if call and name in _COMMANDS:
            args = self.arguments()
            if len(args) != 2:
                raise ExprError('formula_unsupported', f'{name} не двух чисел не входит в формулы')
            return {'fn': _COMMANDS[name], 'args': args}
        if name in ('π', 'pi') and not call:
            return {'const': 'pi'}
        if name == 'ℯ' and not call:
            return {'num': math.e}
        if call:
            if name in ('x', 'y', 'z'):
                raise ExprError('formula_unsupported', 'координаты точек пока не переносятся в формулы')
            if name[:1].isupper():
                raise ExprError('formula_unsupported', 'в выражении есть команда, которой нет в формулах')
            raise ExprError('formula_unsupported', f'функции {name[:40]} нет в формулах')
        raise ExprError('parse_error', f'неизвестное имя {name[:40]}')


def parse_number(text: str, kinds: dict, *, variables=()):
    """``(ast, labels)`` of the expression of a number ``text`` of a ``.ggb``:
    an AST v1 tree whose ``{"ref": k}`` is ``labels[k]``; ``kinds`` — the GGB
    type of every label of the file (a reference must be a ``numeric`` or an
    ``angle``). Raises :class:`ExprError`."""
    from ..expr.validate import problems
    text = str(text)
    if len(text) > MAX_CHARS:
        raise ExprError('formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)')
    if '"' in text:
        raise ExprError('parse_error', 'строка в выражении числа')
    reader = _Reader(_tokens(text), kinds, variables)
    ast = reader.read()
    if problems(ast, len(reader.labels), vars=variables):
        raise ExprError('formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)')
    return ast, reader.labels


def parse_typed(text: str, kinds: dict, *, result: str):
    """Read the typed language of a ``num`` or ``vec`` slot (registry 1.10).

    Source kinds supply operand types; the kernel checks the tree. Refusals
    include the source formula, including syntax outside this language.
    The legacy number/function readers keep their original node set.
    """
    from ..expr.validate import MAX_INTEGER_POWER, problems
    if result not in ('num', 'vec'):
        raise ValueError('result must be num or vec')
    text = str(text)
    try:
        if len(text) > MAX_CHARS:
            raise ExprError('formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)')
        tokens = _tokens(text)
        if any(k == 'sup' and abs(v) > MAX_INTEGER_POWER for k, v in tokens):
            raise ExprError('formula_unsupported', 'степень выходит за пределы формул (expr.md §2)')
        reader = _Reader(tokens, kinds, typed=True)
        ast = reader.read()
        # Lowerings such as log(base, value) reorder children. References
        # follow the emitted tree's pre-order, including the target of call.
        labels, indices, pending = [], {}, [ast]
        while pending:
            node = pending.pop()
            key = 'ref' if 'ref' in node else 'call' if 'call' in node else None
            if key:
                old = node[key]
                if old not in indices:
                    indices[old] = len(labels)
                    labels.append(reader.labels[old])
                node[key] = indices[old]
            pending.extend(reversed(node.get('pair', node.get('args', []))))
        reader.labels = labels
        operands = ['number' if kinds[n] in NUMBER_KINDS else kinds[n] for n in reader.labels]
        issues = problems(ast, len(operands), operands=operands, result=result)
        if issues:
            raise ExprError('formula_unsupported', issues[0][1])
    except (ExprError, RecursionError) as exc:
        detail = exc.detail if isinstance(exc, ExprError) else 'выражение слишком глубоко'
        raise ExprError('formula_unsupported', f'{text[:180]} ({detail})') from None
    return ast, reader.labels
