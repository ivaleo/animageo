"""Expressions of ``number.expression``: AST v1 (docs/native/expr.md).

A tree of JSON nodes, a strict subset of the AST v2 of the expression
language that comes later, so a v1 tree stays a valid v2 tree::

    Expr := {"num": v} | {"const": "pi"} | {"ref": k}
          | {"op": "+" | "-" | "*" | "/" | "^", "args": [Expr, Expr]}
          | {"op": "neg", "args": [Expr]}
          | {"fn": name, "args": [Expr, ...]}

``{"ref": k}`` is item ``k`` (from 0) of the list input ``refs`` of the
operation. Registry 1.10: a typed slot (``result`` in its record) also takes
``{"pair": [Expr, Expr]}``, ``{"call": k, "args": [Expr]}`` and the functions
``x``, ``y``; its values are numbers and pairs (:func:`evaluate_typed`). No text is parsed and nothing is ``eval``-ed: :func:`problems`
checks a tree against the whitelist and the limits, :func:`evaluate` walks
it node by node.

The templates of ``text.free`` (``"Угол {0}"``) live here too
(:mod:`.template`): a string with inserts ``{k}`` into ``refs``.
"""
from .evaluate import ExprError, evaluate, evaluate_typed, operand_value
from .function import compile_function
from .printer import to_text
from .template import MAX_TEMPLATE_LENGTH, format_value, split_template, template_problems
from .validate import (COMPARISONS, CONSTANTS, FUNCTIONS, MAX_DEPTH, MAX_INTEGER_POWER, MAX_NODES, OPERAND_TYPES, OPERATORS,
                       TYPED_FUNCTIONS, problems, type_problems)

__all__ = ['COMPARISONS', 'CONSTANTS', 'ExprError', 'FUNCTIONS', 'MAX_DEPTH', 'MAX_INTEGER_POWER', 'MAX_NODES',
           'MAX_TEMPLATE_LENGTH', 'OPERAND_TYPES', 'OPERATORS', 'TYPED_FUNCTIONS', 'compile_function', 'evaluate',
           'evaluate_typed', 'format_value', 'operand_value', 'problems', 'split_template', 'template_problems',
           'to_text', 'type_problems']
