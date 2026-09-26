"""Parse formula text from a file with sympy without handing it Python.

``sympy.sympify(text)`` evaluates the text with Python's ``eval`` in a
namespace that includes builtins such as ``__import__``; a .ggb file is
untrusted input (the web service parses uploads). Formula text needs
arithmetic, names and calls only, so text with dunders, quotes, attribute
access or statements is refused, and the evaluation namespace is sympy's
public names plus the few builtins a formula can mean — no ``__builtins__``.
"""
import builtins
import re
from tokenize import TokenError

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor, parse_expr, standard_transformations,
)

_UNSAFE = re.compile(
    r"__|['\"`;\\@]|\.\s*[A-Za-z_]"
    r"|\b(?:lambda|import|exec|eval|compile|open|globals|locals|vars"
    r"|getattr|setattr|delattr|breakpoint|input)\b"
)
_TRANSFORMATIONS = standard_transformations + (convert_xor,)
_GLOBALS = None


def _global_dict():
    global _GLOBALS
    if _GLOBALS is None:
        namespace = {}
        exec('from sympy import *', namespace)          # our code, not the file's
        namespace['__builtins__'] = {}
        # The builtins sympify would offer that a formula can mean.
        namespace.update(abs=builtins.abs, pow=builtins.pow,
                         round=builtins.round, max=sp.Max, min=sp.Min)
        _GLOBALS = namespace
    return dict(_GLOBALS)


def safe_sympify(text, local_dict=None):
    """``sympy.sympify(text, locals=local_dict)`` for untrusted formula text.

    Raises ``sympy.SympifyError`` for refused or malformed text, so callers
    that already catch sympify's errors keep working.
    """
    if _UNSAFE.search(text):
        raise sp.SympifyError(text, 'refused: not a formula')
    try:
        return parse_expr(text, local_dict=dict(local_dict or {}),
                          global_dict=_global_dict(),
                          transformations=_TRANSFORMATIONS)
    except (TokenError, SyntaxError, NameError, AttributeError) as e:
        raise sp.SympifyError(text, e)
