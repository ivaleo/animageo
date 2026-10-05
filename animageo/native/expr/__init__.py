"""Expressions of ``number.expression``: AST v1 (docs/native/expr.md).

A tree of JSON nodes, a strict subset of the AST v2 of the expression
language that comes later, so a v1 tree stays a valid v2 tree::

    Expr := {"num": v} | {"const": "pi"} | {"ref": k}
          | {"op": "+" | "-" | "*" | "/" | "^", "args": [Expr, Expr]}
          | {"op": "neg", "args": [Expr]}
          | {"fn": name, "args": [Expr, ...]}

``{"ref": k}`` is item ``k`` (from 0) of the list input ``refs`` of the
operation. No text is parsed and nothing is ``eval``-ed: :func:`problems`
checks a tree against the whitelist and the limits, :func:`evaluate` walks
it node by node.

The templates of ``text.free`` (``"Угол {0}"``) live here too
(:mod:`.template`): a string with inserts ``{k}`` into ``refs``.
"""
from .evaluate import ExprError, evaluate
from .printer import to_text
from .template import MAX_TEMPLATE_LENGTH, format_value, split_template, template_problems
from .validate import CONSTANTS, FUNCTIONS, MAX_DEPTH, MAX_INTEGER_POWER, MAX_NODES, OPERATORS, problems

__all__ = ['CONSTANTS', 'ExprError', 'FUNCTIONS', 'MAX_DEPTH', 'MAX_INTEGER_POWER', 'MAX_NODES',
           'MAX_TEMPLATE_LENGTH', 'OPERATORS', 'evaluate', 'format_value', 'problems', 'split_template',
           'template_problems', 'to_text']
