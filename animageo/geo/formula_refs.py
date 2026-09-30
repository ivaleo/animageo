"""References a formula makes to construction objects other than numbers.

GeoGebra formulas read coordinates — ``x(A)``, ``y(A)`` of a point, ``x(v)``
of a vector — and call other functions — ``f(t) = g(t) + k``. Parsing turns
``x(`` / ``y(`` into the sympy calls ``xcoord(`` / ``ycoord(`` (the ``x`` of
``x(A)`` is never the variable, even in ``f(x) = x(A) + x``) and leaves
``g(t)`` an undefined-function call. :func:`substitute_references` then puts
in the current coordinates and the current expression of ``g``.

Only sympy here: the function, conic and implicit parsers all use it.
"""
import re

import numpy as np
import sympy as sp
from sympy.core.function import AppliedUndef

XCOORD = sp.Function('xcoord')
YCOORD = sp.Function('ycoord')
COORD_FUNCS = {'xcoord': XCOORD, 'ycoord': YCOORD}

# ``x(`` right before the bracket, also after a number (``2x(A)``); not
# ``max(``, ``a2x(`` or ``a.x(``.
_COORD_CALL_RE = re.compile(
    r'(?<![\w.])((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)?([xy])\(')
_COORD_ARG_RE = re.compile(r'(?<![A-Za-z_.])[xy]coord\(\s*([A-Za-z_]\w*)\s*\)')


def coordinate_calls(text):
    """``(text, names)`` with ``x(A)`` / ``y(A)`` rewritten to ``xcoord(A)`` /
    ``ycoord(A)`` and ``names`` the parse namespace for them: the two call
    names plus every point they name as a plain symbol — ``O``, ``E``,
    ``N``, ``S`` would otherwise resolve to sympy objects."""
    text = _COORD_CALL_RE.sub(
        lambda m: f'{m.group(1) or ""}{m.group(2)}coord(', text)
    names = {name: sp.Symbol(name) for name in _COORD_ARG_RE.findall(text)}
    return text, {**names, **COORD_FUNCS}


def reference_names(expr, own):
    """Sorted names a parsed formula refers to: free symbols other than its
    own variables ``own`` (numbers, and the points inside ``x()``/``y()``)
    and the functions it calls. ``None`` when a coordinate is taken of
    something other than a name (``x(A + B)``)."""
    names = {str(s) for s in expr.free_symbols - set(own)}
    for call in expr.atoms(AppliedUndef):
        fname = call.func.__name__
        if fname in COORD_FUNCS:
            if len(call.args) != 1 or not isinstance(call.args[0], sp.Symbol):
                return None
        else:
            names.add(fname)
    return sorted(names)


def unbound_references(expr, own):
    """Names still unresolved after substitution — a curve can't be drawn
    while any remain. A call of a NumPy function (``hypot(x, 1)``) is bound:
    the numeric callable (``lambdify('numpy')``) resolves it. A coordinate
    of something other than a point, ``3x(x + 1)``, is shown as written."""
    names = {str(s) for s in expr.free_symbols - set(own)}
    for call in expr.atoms(AppliedUndef):
        fname = call.func.__name__
        if fname in COORD_FUNCS:
            names.add(f"{fname[0]}({', '.join(map(str, call.args))})")
        elif not callable(getattr(np, fname, None)):
            names.add(fname)
    return sorted(names)


# A called function is inlined, so the result stays symbolic. Nested calls —
# f_k(x) = f_{k-1}(sin x) + f_{k-1}(cos x) — would double the expression per
# level: a few lines of a file (formula text is untrusted) could hang the
# parser and every later evaluation. Past this many expression nodes, about
# what a long formula written out by hand has, the call is refused.
INLINE_LIMIT = 2000


def _node_count(expr):
    return sum(1 for _ in sp.preorder_traversal(expr))


def substitute_references(expr, parameters):
    """Replace a formula's references by their current values.

    ``parameters`` maps a name to a number or boolean, a coordinate pair (a
    point or vector, read through ``x()``/``y()``), or a function — anything
    with ``expr`` and ``var`` (``g(t)`` becomes ``g.expr`` at ``t``, and is
    undefined outside ``g.explicit_domain``). A number written before a
    bracket, ``k(x + 1)``, is a product.
    """
    # Values go in as sympy numbers: a formula that is only a reference
    # (``y = x(A)``) becomes the value itself, and a Python float there has
    # none of the expression methods the parsers call next.
    numbers, coords, funcs = {}, {}, {}
    for name, value in parameters.items():
        if hasattr(value, 'expr') and hasattr(value, 'var'):
            funcs[str(name)] = value
        elif isinstance(value, (bool, np.bool_)):
            numbers[sp.Symbol(str(name))] = bool(value)
        elif _is_pair(value):
            symbol = sp.Symbol(str(name))
            coords[XCOORD(symbol)] = sp.Float(float(value[0]))
            coords[YCOORD(symbol)] = sp.Float(float(value[1]))
        else:
            try:
                numbers[sp.Symbol(str(name))] = sp.Float(float(value))
            except (TypeError, ValueError):
                continue
    try:
        return _substitute(expr, numbers, coords, funcs)
    except TypeError as e:          # sympy: comparison with nan / non-real
        raise ValueError(f"formula cannot be evaluated: {e}") from e


def _substitute(expr, numbers, coords, funcs):
    factors = {str(k): v for k, v in numbers.items() if not isinstance(v, bool)}
    flags = {k: v for k, v in numbers.items() if isinstance(v, bool)}
    if flags:
        # A boolean is a condition inside ``If(b, …)`` and 0 / 1 anywhere
        # else (``y = x + b``), as in a conic.
        truth = {k: sp.true if v else sp.false for k, v in flags.items()}
        expr = expr.replace(
            lambda e: isinstance(e, sp.Piecewise),
            lambda e: sp.Piecewise(*[(v, c.xreplace(truth)) for v, c in e.args]),
        )
        numbers = {**numbers, **{k: sp.Integer(int(v)) for k, v in flags.items()}}
    if factors:
        expr = expr.replace(
            lambda e: (isinstance(e, AppliedUndef) and len(e.args) == 1
                       and e.func.__name__ in factors),
            lambda e: factors[e.func.__name__] * e.args[0],
        )
    if funcs:
        size = _node_count(expr)
        for call in expr.atoms(AppliedUndef):
            func = funcs.get(call.func.__name__)
            if func is not None:
                size += _node_count(func.expr)
        if size > INLINE_LIMIT:
            raise ValueError(
                f"formula too large with the functions it calls inlined "
                f"({size} > {INLINE_LIMIT} nodes)")
        expr = expr.replace(
            lambda e: (isinstance(e, AppliedUndef) and len(e.args) == 1
                       and e.func.__name__ in funcs),
            lambda e: _inline(funcs[e.func.__name__], e.args[0]),
        )
    if coords:
        expr = expr.xreplace(coords)
    if numbers:
        expr = expr.subs(numbers)
    return expr


def _inline(func, arg):
    body = func.expr.subs(func.var, arg)
    domain = getattr(func, 'explicit_domain', None)
    if domain is None:
        return body
    lo, hi = (float(v) for v in domain)
    # nan (an argument outside an inner domain, g(g(x))) can't be compared;
    # as oo it is outside this domain too.
    at = arg.xreplace({sp.nan: sp.oo, sp.zoo: sp.oo})
    return sp.Piecewise((body, (at >= lo) & (at <= hi)), (sp.nan, True))


def _is_pair(value):
    if isinstance(value, (str, bytes)):
        return False
    try:
        return len(value) == 2
    except TypeError:
        return False
