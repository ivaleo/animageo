"""Parameters of a formula-defined curve.

A GeoGebra formula such as ``f(x) = a x²`` or ``p: y = a x²`` depends on the
free numbers it mentions; ``g(t) = y(A) (t − x(B))`` on the points whose
coordinates it reads (and vectors: ``x(v)``); ``f(t) = g(t) + k`` on the
function it calls. The construction keeps that dependency as a command whose
first input is the formula text and whose remaining inputs are the parameter
names in sorted order — ``Function("y = a*x^2", a)``, ``Function("…", A, B,
g, k)`` — and the command implementation re-reads the formula with the
current values on every rebuild. Producer (GGB parser, DSL) and consumer
(``lib_commands.*_Tn``) both take the parameter order from
:func:`formula_parameters`, so they cannot drift.
"""
import re

import numpy as np

from .formula_refs import reference_names
from .lib_elements import Angle, Point, Vector
from .lib_function import Function
from .lib_vars import AngleSize, Boolean, Measure
from .safe_sympify import normalize_formula_text

FORMULA_KINDS = ('function', 'conic', 'line', 'implicit')


def _parse(expr_str, kind):
    if kind == 'function':
        from .lib_function import parse_function_expression
        expr, x = parse_function_expression(expr_str)
        return expr, {x}
    if kind == 'implicit':
        from .lib_implicit import parse_implicit_expression
        expr, x, y = parse_implicit_expression(expr_str)
        return expr, {x, y}
    if kind in ('conic', 'line'):
        from .lib_conic import parse_conic_equation
        expr, x, y = parse_conic_equation(expr_str)
        return expr, {x, y}
    raise ValueError(f"unknown formula kind {kind!r}")


def formula_parameters(expr_str, kind):
    """Sorted names a formula refers to other than its own variables (``x``
    for a function, ``x, y`` otherwise): numbers, points and vectors read
    through ``x()``/``y()``, functions it calls (``g(x) = f(x) + a`` →
    ``['a', 'f']``).

    ``None`` when the formula can't be parsed or takes a coordinate of
    something other than a name (``x(A + B)``).
    """
    try:
        expr, own = _parse(expr_str, kind)
    except ValueError:
        return None
    return reference_names(expr, own)


def numeric_var_values(constr):
    """``{name: value}`` for every construction object a formula can use as a
    number: plain numbers and sliders, measures of any dimension
    (``Radius(c)``, ``Distance(A, B)``, areas), angle sizes, angle objects
    (``Angle(A, B, C)``, in radians) and booleans (as ``bool``, so a formula
    such as ``If(b, x, -x)`` keeps working)."""
    values = {}
    for var in constr.vars:
        value = _number_value(var.data)
        if value is not None:
            values[var.name] = value
    for elem in constr.elements:
        if isinstance(elem.data, Angle):
            values[elem.name] = float(elem.data.value)
    return values


# Commands compute with NumPy: ``AreCollinear`` gives ``np.bool_``, which is
# not a ``bool`` — as a float, ``If(b, …)`` would get a number.
_BOOLS = (bool, np.bool_)
_NUMBERS = (int, float, np.integer, np.floating)


def _number_value(data):
    if isinstance(data, _BOOLS):
        return bool(data)
    if isinstance(data, _NUMBERS):
        return float(data)
    if isinstance(data, Boolean):
        return bool(data.value)
    if isinstance(data, (Measure, AngleSize, Angle)):
        return float(data.value)
    return None


def formula_objects(constr):
    """``{name: data}`` for every construction object a formula can refer
    to: the numbers of :func:`numeric_var_values`, points and vectors (read
    through ``x()``/``y()``) and functions (called as ``g(x)``)."""
    objects = numeric_var_values(constr)
    for elem in constr.elements:
        if isinstance(elem.data, (Point, Vector, Function)):
            objects.setdefault(elem.name, elem.data)
    return objects


def formula_bindings(constr):
    """``{name: value}`` of :func:`formula_objects` in the form the curve
    parsers substitute (``Function.from_string(…, parameters=…)``)."""
    return {name: _bound(data) for name, data in formula_objects(constr).items()}


def parametric_inputs(constr, expr_str, kind):
    """Parameter names to append to a formula command, or ``None`` when the
    formula refers to nothing in the construction or to a name that is not
    in it."""
    names = formula_parameters(expr_str, kind)
    if not names:
        return None
    objects = formula_objects(constr)
    if not all(name in objects for name in names):
        return None
    return names


def bind_parameters(expr_str, kind, values):
    """Pair a formula's parameter names with command input values."""
    names = formula_parameters(expr_str, kind)
    if names is None or len(names) != len(values):
        raise ValueError(
            f"formula {expr_str!r} takes parameters {names}, "
            f"got {len(values)} value(s)"
        )
    return {name: _bound(v) for name, v in zip(names, values)}


def _bound(value):
    if isinstance(value, Point):
        return (float(value.coords[0]), float(value.coords[1]))
    if isinstance(value, Vector):
        return (float(value.direction[0]), float(value.direction[1]))
    if isinstance(value, Function):
        return value
    raw = getattr(value, 'value', value)
    return bool(raw) if isinstance(raw, _BOOLS) else float(raw)


# A name starts with a letter or ``_``: in ``2a`` it is ``a`` (a number
# before a name is a product), in ``b2a`` it is ``b2a``.
_NAME_RE = re.compile(r'[^\W\d]\w*')


def _mentioned(names, expr_str):
    words = set(_NAME_RE.findall(normalize_formula_text(expr_str)))
    return sorted(name for name in names if name in words)


def mentioned_numbers(constr, expr_str):
    """Numeric construction vars that appear in ``expr_str`` as whole names.

    For diagnostics: works even when the formula does not parse.
    """
    return _mentioned(numeric_var_values(constr), expr_str)


def mentioned_objects(constr, expr_str):
    """Like :func:`mentioned_numbers` for everything a formula can refer to
    (:func:`formula_objects`) — numbers, points, vectors, functions."""
    return _mentioned(formula_objects(constr), expr_str)
