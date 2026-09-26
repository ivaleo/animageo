"""Numeric parameters of a formula-defined curve.

A GeoGebra formula such as ``f(x) = a x²`` or ``p: y = a x²`` depends on the
free numbers it mentions. The construction keeps that dependency as a command
whose first input is the formula text and whose remaining inputs are the
parameter names in sorted order — ``Function("y = a*x^2", a)`` — and the
command implementation re-reads the formula with the current values on every
rebuild. Producer (GGB parser, DSL) and consumer (``lib_commands.*_Tn``) both
take the parameter order from :func:`formula_parameters`, so they cannot drift.
"""
import re

from sympy.core.function import AppliedUndef

from .lib_elements import Angle
from .lib_vars import AngleSize, Boolean, Measure

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
    """Sorted names of a formula's free symbols other than its own variables
    (``x`` for a function, ``x, y`` otherwise).

    ``None`` when the formula can't be read as a closed expression: a parse
    error, or a call of an undefined function (``g(x) = f(x) + a``).
    """
    try:
        expr, own = _parse(expr_str, kind)
    except ValueError:
        return None
    if expr.atoms(AppliedUndef):
        return None
    return sorted(str(s) for s in expr.free_symbols - own)


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


def _number_value(data):
    if isinstance(data, bool):
        return data
    if isinstance(data, (int, float)):
        return float(data)
    if isinstance(data, Boolean):
        return bool(data.value)
    if isinstance(data, (Measure, AngleSize, Angle)):
        return float(data.value)
    return None


def parametric_inputs(constr, expr_str, kind):
    """Parameter names to append to a formula command, or ``None`` when the
    formula mentions no construction number or a symbol that is not one."""
    names = formula_parameters(expr_str, kind)
    if not names:
        return None
    numeric = numeric_var_values(constr)
    if not all(name in numeric for name in names):
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
    raw = getattr(value, 'value', value)
    return raw if isinstance(raw, bool) else float(raw)


def mentioned_numbers(constr, expr_str):
    """Numeric construction vars that appear in ``expr_str`` as whole names.

    For diagnostics: works even when the formula does not parse.
    """
    return sorted(
        name for name in numeric_var_values(constr)
        if re.search(rf'(?<!\w){re.escape(name)}(?!\w)', expr_str)
    )
