"""DSL sugar preprocessor (``f(x) = expr`` → ``f = Function("y = expr")``).

Runs as a text-level pre-pass before :func:`dsl.transform` / ``ast.parse``,
so the transform never sees the non-Python ``name(var) = expr`` form.
Recognises two common forms::

    f(x) = expr             → f = Function("y = expr")
    f(t) = expr             → f = Function("y = expr-with-t-renamed-to-x")

More elaborate sugar (``g: x^2 + y^2 = 4`` for conics) is left as an
explicit ``Conic(...)`` call form — it would require a proper lexer.

Lives here (in ``parsers/dsl/``) rather than in the now-removed
``short_parser.py``: any sugar the exec engine needs is part of its
own package.
"""

from __future__ import annotations

import re

from ...geo.safe_sympify import normalize_formula_text


_FUNCTION_DEF_RE = re.compile(
    r'''^(\s*)                      # indent
        ([A-Za-z_][A-Za-z0-9_]*)    # function name
        \s*\(\s*
        ([A-Za-z_][A-Za-z0-9_]*)    # variable
        \s*\)\s*=\s*
        ([^#]+?)                    # expression (non-greedy)
        (\s*\#.*)?                  # a trailing comment, kept as is
        \s*$''',
    re.VERBOSE,
)


_NAME_RE = re.compile(r'[^\W\d]\w*')
_OPEN_RE = re.compile(r'\s*\(')


def _rename_variable(expr: str, var: str) -> str:
    """``var`` → ``x`` as a whole name, also after a number (``2t``);
    ``t(t + 1)`` becomes ``x*(x + 1)``, since ``x(`` reads a coordinate."""
    def rename(m):
        if m.group() != var:
            return m.group()
        return 'x*' if _OPEN_RE.match(expr, m.end()) else 'x'
    return _NAME_RE.sub(rename, expr)


def preprocess_dsl_sugar(code: str) -> str:
    """Rewrite ``name(var) = expr`` lines as ``name = Function("y = expr")``.

    If ``var`` is not ``x``, it's textually renamed to ``x`` inside
    the expression so the resulting ``Function`` parses via the
    standard x-as-free-variable path. Lines that don't match are
    passed through unchanged.
    """
    out_lines = []
    for line in code.splitlines(keepends=False):
        m = _FUNCTION_DEF_RE.match(line)
        if m is None:
            out_lines.append(line)
            continue
        indent, name, var, expr = m.group(1), m.group(2), m.group(3), m.group(4)
        comment = m.group(5) or ''
        if var != 'x':
            # ``πt`` is two names once π is read (see normalize_formula_text).
            expr = _rename_variable(normalize_formula_text(expr), var)
        expr_escaped = expr.replace('\\', '\\\\').replace('"', '\\"')
        out_lines.append(
            f'{indent}{name} = Function("y = {expr_escaped}"){comment}')
    return '\n'.join(out_lines) + ('\n' if code.endswith('\n') else '')
