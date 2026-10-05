"""The names an expression of a ``.ggb`` refers to (1.10.0a3).

``depends_on`` of the import report names the objects a definition refers
to. The names inside a string literal are text, not references: the LaTeX
formula of a fixed text (``"$S = \\frac{1}{2} a h_a$"``) refers to nothing.

    names_in(texts, labels)     → the labels the texts refer to, outside string literals
"""
from __future__ import annotations

import re

__all__ = ['names_in', 'strip_strings']

_SUPERSCRIPT = '⁰¹²³⁴⁵⁶⁷⁸⁹'
_NOT_SUP = '(?![' + _SUPERSCRIPT + '])'
# a label: a letter, then letters, digits, ``_`` and primes; ``_{…}`` closes it (``t_{AB}``; a label
# has at most 200 characters, so the braces are looked for no further). A superscript digit is a power,
# not a part of the name (``a²``).
_NAME = re.compile('(?:' + _NOT_SUP + r"[^\W\d](?:" + _NOT_SUP + r"[\w'])*?_\{[^}]{0,200}\}"
                   + '|' + _NOT_SUP + r"[^\W\d](?:" + _NOT_SUP + r"[\w'])*)")


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
