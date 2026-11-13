"""Independent on-graph checks for registry 1.11 function analysis.

Imported after checks.py finishes registering its base checks. Undefined
repeated slots are skipped; the evaluator suppresses checks of an empty set.
"""
import math

from ..registry import registry
from .checks import register_check
from .function import evaluator
from .function_analysis import AnalysisError, Budget, coefficients, derivative
from .values import Undefined


def _slope(value, x):
    """Analytic polynomial derivative, or None when it is not finite."""
    try:
        dc = derivative(coefficients(value, Budget()))
        slope = 0.0
        for ci in reversed(dc):
            slope = slope * x + ci
        return slope if math.isfinite(slope) else None
    except AnalysisError:
        return None


def _secant(y, fx, dx):
    # Divide a normalized difference before restoring its magnitude; avoids
    # overflow of y-fx when the resulting secant is representable.
    scale = max(abs(y), abs(fx))
    if scale == 0:
        return 0.0
    return ((y / scale - fx / scale) / dx) * scale


def _off_graph(args, result, tol, *, roots):
    value = args['function'].value
    f = evaluator(value)
    profile = registry().numeric['functionAnalysis']
    error = 0.0
    for point in result.values():
        if point is None or isinstance(point, Undefined):
            continue
        x, y = point['x'], point['y']
        fx = f(x)
        if fx is None:
            return math.inf
        denominator = 1.0
        if roots:
            slope = _slope(value, x)
            if slope is None:
                h = max(16 * max(profile['xAbs'], profile['xRel'] * abs(x)), tol.decide_length)
                slopes = []
                for near in (x - h, x + h):
                    if near == x or not math.isfinite(near):
                        continue
                    fy = f(near)
                    if fy is not None:
                        secant = _secant(fy, fx, near - x)
                        if math.isfinite(secant):
                            slopes.append(abs(secant))
                slope = max(slopes, default=0.0)
            denominator = max(1.0, abs(slope))
        error = max(error, abs(y / denominator - fx / denominator))
    return error


@register_check('function.roots_polynomial', 'on_graph')
def roots_on_graph(args, result, tol):
    return _off_graph(args, result, tol, roots=True)


@register_check('function.extrema_polynomial', 'on_graph')
def extrema_on_graph(args, result, tol):
    return _off_graph(args, result, tol, roots=False)
