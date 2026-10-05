"""Text templates of ``text.free`` (docs/native/ops/text.free.md).

A template is a string with inserts ``{k}`` — item ``k`` (from 0) of the
list input ``refs``; ``{{`` and ``}}`` stand for the braces themselves.
Nothing inside braces is evaluated: an insert is a decimal index only.
"""
from __future__ import annotations

import math

__all__ = ['MAX_TEMPLATE_LENGTH', 'format_value', 'split_template', 'template_problems']

MAX_TEMPLATE_LENGTH = 1000      # code points; the structure check refuses a longer string


def _scan(template: str):
    """``(parts, problem)``: ``parts`` — ``[('text', s) | ('ref', k)]`` with
    adjacent literals joined; ``problem`` — ``(column, message)`` of the first
    bad brace (column from 1, in code points) or ``None``."""
    parts = []
    literal = []
    i, n = 0, len(template)
    while i < n:
        ch = template[i]
        if ch == '{' and template.startswith('{{', i):
            literal.append('{')
            i += 2
            continue
        if ch == '}' and template.startswith('}}', i):
            literal.append('}')
            i += 2
            continue
        if ch == '}':
            return parts, (i + 1, 'a lone }: write }} for a brace')
        if ch == '{':
            close = template.find('}', i + 1)
            body = template[i + 1:close] if close >= 0 else None
            if body is None:
                return parts, (i + 1, 'an unclosed {: write {{ for a brace')
            if not body or not body.isascii() or not body.isdigit() or (len(body) > 1 and body[0] == '0'):
                return parts, (i + 1, f'an insert is {{k}} with k = 0, 1, 2, …, not {{{body}}}')
            if literal:
                parts.append(('text', ''.join(literal)))
                literal = []
            parts.append(('ref', int(body)))
            i = close + 1
            continue
        literal.append(ch)
        i += 1
    if literal:
        parts.append(('text', ''.join(literal)))
    return parts, None


def template_problems(template, ref_count: int | None = None) -> list:
    """``[message]`` of the problems of ``template`` (empty when valid):
    the first bad brace, or inserts outside ``refs`` (``ref_count`` items;
    ``None`` skips that check)."""
    if not isinstance(template, str):
        return ['a template must be a string']
    if len(template) > MAX_TEMPLATE_LENGTH:
        return [f'a template is longer than {MAX_TEMPLATE_LENGTH} characters']
    parts, problem = _scan(template)
    if problem is not None:
        return [f'column {problem[0]}: {problem[1]}']
    if ref_count is None:
        return []
    return [f'insert {{{k}}} is outside refs ({ref_count} items)' for kind, k in parts
            if kind == 'ref' and k >= ref_count]


def split_template(template: str) -> list:
    """``[('text', s) | ('ref', k)]`` of a valid template."""
    parts, problem = _scan(template)
    if problem is not None:
        raise ValueError(problem[1])
    return parts


def format_value(value: float, decimals: int) -> str:
    """A number for an insert, as GeoGebra prints a value (and as the classic
    ``format_number``): the exact binary value rounded to ``decimals`` places
    half to even, trailing zeros and a bare point dropped, ``-0`` → ``0``;
    ``|value| ≥ 1e15`` prints its shortest round-trip digits instead
    (``1e+15``, ``-2.5e+20``)."""
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f'{value!r} is not a finite number')
    if abs(x) >= 1e15:
        from ..commands.numbers import format_number

        return format_number(x)
    s = f'{x:.{decimals}f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s
