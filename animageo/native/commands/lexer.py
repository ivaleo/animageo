"""Tokens of one line of «Команды» (commands.md §2).

Input replacements happen on tokens, so every token keeps the column where
its text starts in the line as typed: ``||`` → ``∥``, ``_|_`` → ``⟂``,
``<)`` → ``∠``, ``>=`` → ``≥``, ``<=`` → ``≤``, ``*`` → ``·``, the words
``in`` → ``∈`` and ``deg`` → ``°``; the minus sign ``−`` is ``-``.

Token kinds: ``name`` (an identifier: a letter, then letters, decimal
digits, ``_ { }``, subscript digits, primes ``'`` and ``.`` before a letter —
so a registry operation ID is one name), ``number`` (``12``, ``1.5``,
``.5``, ``2e-7``; no sign) and ``sym`` (one symbol). ``#`` starts a comment
that runs to the end of the line.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .issues import LineError

__all__ = ['Token', 'tokenize', 'SYMBOLS']

SYMBOLS = frozenset('(),=∠°·+-/^<>≤≥∥⟂∈|√≠∧∨;:[]!')
_MULTI = (('_|_', '⟂'), ('||', '∥'), ('<)', '∠'), ('>=', '≥'), ('<=', '≤'))
_SINGLE = {'*': '·', '−': '-'}
_WORDS = {'in': '∈', 'deg': '°'}
_SUBSCRIPTS = frozenset('₀₁₂₃₄₅₆₇₈₉')


@dataclass(frozen=True)
class Token:
    kind: str            # name | number | sym
    text: str            # the token after replacements (a symbol, a name, the digits)
    column: int          # 1-based column of the first code point in the line as typed
    end: int             # column just after the token


def _letter(ch: str) -> bool:
    return unicodedata.category(ch)[0] == 'L'


def _name_char(ch: str) -> bool:
    return _letter(ch) or unicodedata.category(ch) == 'Nd' or ch in "_{}'" or ch in _SUBSCRIPTS


def tokenize(line: str):
    """``(tokens, comment_column)`` of ``line`` (no newline); the comment
    column is ``None`` when the line has no ``#``. An unknown character
    raises :class:`LineError` ``syntax``."""
    tokens = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '#':
            return tokens, i + 1
        multi = next((rep for src, rep in _MULTI if line.startswith(src, i)), None)
        if multi is not None:
            size = next(len(src) for src, rep in _MULTI if line.startswith(src, i))
            tokens.append(Token('sym', multi, i + 1, i + 1 + size))
            i += size
            continue
        if ch in _SINGLE:
            tokens.append(Token('sym', _SINGLE[ch], i + 1, i + 2))
            i += 1
            continue
        if '0' <= ch <= '9' or (ch == '.' and i + 1 < n and '0' <= line[i + 1] <= '9'):
            j = i
            while j < n and '0' <= line[j] <= '9':
                j += 1
            if j < n and line[j] == '.':
                j += 1
                while j < n and '0' <= line[j] <= '9':
                    j += 1
            if j < n and line[j] in 'eE':
                k = j + 1
                if k < n and line[k] in '+-':
                    k += 1
                if k < n and '0' <= line[k] <= '9':
                    while k < n and '0' <= line[k] <= '9':
                        k += 1
                    j = k
            tokens.append(Token('number', line[i:j], i + 1, j + 1))
            i = j
            continue
        if _letter(ch):
            j = i + 1
            while j < n:
                if line.startswith('_|_', j):
                    break
                if _name_char(line[j]):
                    j += 1
                elif line[j] == '.' and j + 1 < n and _letter(line[j + 1]):
                    j += 2
                else:
                    break
            text = line[i:j]
            if text in _WORDS:
                tokens.append(Token('sym', _WORDS[text], i + 1, j + 1))
            else:
                tokens.append(Token('name', text, i + 1, j + 1))
            i = j
            continue
        if ch in SYMBOLS:
            tokens.append(Token('sym', ch, i + 1, i + 2))
            i += 1
            continue
        raise LineError('syntax', i + 1, f'непонятный знак «{ch}»')
    return tokens, None
