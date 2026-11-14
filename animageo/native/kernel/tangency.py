"""Local graph tangents with a separate, bounded numerical profile.

The analytic AST derivative is shared with function analysis unchanged.
Undecided joins are checked on both sides; only represented, included domain
ends permit a one-sided stencil. No sample threshold creates a vertical line.
"""
from __future__ import annotations

import math

from ..expr import ExprError, compile_function
from ..registry import registry
from .function import evaluator
from .function_analysis_numeric import _at_switch, _dual, _truth, derivative_at


class TangencyError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def direction(slope):
    length = math.hypot(1.0, slope)
    return (1.0 / length, slope / length)


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _infinite_form(node, refs, x):
    """Elementary infinite derivatives at a zero base, without size heuristics."""
    if 'if' in node:
        condition, then, *other = node['if']
        branch = then if _truth(condition, refs, x) else (other[0] if other else None)
        return branch is not None and _infinite_form(branch, refs, x)
    args = node.get('args', ())
    name = node.get('op')
    if name == 'neg':
        return _infinite_form(args[0], refs, x)
    if name in ('+', '-', '*', '/'):
        singular = [_infinite_form(a, refs, x) for a in args]
        if sum(singular) == 1:
            i = singular.index(False)
            try:
                v, d = _dual(args[i], refs, x)
                return math.isfinite(v) and math.isfinite(d) and (name in ('+', '-') or v != 0)
            except (ExprError, ArithmeticError, ValueError):
                return False
        return False
    root = node.get('fn') == 'sqrt'
    fractional = node.get('op') == '^'
    if not (root or fractional):
        return False
    try:
        exponent = .5 if root else compile_function(args[1], refs)(x)
        if not 0 < exponent < 1 or (fractional and _dual(args[1], refs, x)[1] != 0):
            return False
        base = args[0]
        if compile_function(base, refs)(x) != 0:
            return False
        if base.get('fn') == 'abs':
            base = base['args'][0]
        return _dual(base, refs, x)[1] != 0
    except (ExprError, ArithmeticError, ValueError):
        return False


def _represented_pole(node, refs, x):
    """Reject exactly represented tan poles, without excluding steep neighbors."""
    if 'if' in node:
        condition, then, *other = node['if']
        branch = then if _truth(condition, refs, x) else (other[0] if other else None)
        return branch is not None and _represented_pole(branch, refs, x)
    if node.get('fn') == 'tan':
        a = compile_function(node['args'][0], refs)(x)
        if abs(math.remainder(a, math.pi)) == math.pi/2:
            return True
    return any(_represented_pole(a, refs, x) for a in node.get('args', ()))


def _has_switch(node, refs, x):
    """Include switches nested in a comparison's scalar operands.

    The shared derivative intentionally inspects the selected branch only;
    that does not establish continuity of the condition choosing it.
    """
    if 'if' in node:
        try:
            if _at_switch(node['if'][0], refs, x):
                return True
        except (ExprError, ArithmeticError, ValueError):
            return True
    return any(_has_switch(child, refs, x) for key in ('if', 'args', 'and', 'or', 'not')
               for child in node.get(key, ()))


def _guard_side(condition, refs, x):
    """A simple closed If guard's permitted side at its represented endpoint.

    An affine boundary is required: sampling a missing interior neighbor never
    establishes a domain end. Compound conjunctions intersect their sides.
    """
    if 'and' in condition:
        sides = [_guard_side(c, refs, x) for c in condition['and']]
        ends = {s for s in sides if s is not None}
        return next(iter(ends)) if len(ends) == 1 else None
    if condition.get('cmp') not in ('<=', '>='):
        return None
    a, b = condition['args']
    # Only x versus a constant: a nonlinear equality need not bound an interval.
    if a == {'var': 'x'}:
        constant, sign = b, 1
    elif b == {'var': 'x'}:
        constant, sign = a, -1
    else:
        return None
    try:
        v, dv = _dual(constant, refs, x)
        if v != x or dv != 0:
            return None
    except (ExprError, ArithmeticError, ValueError):
        return None
    return sign * (-1 if condition['cmp'] == '<=' else 1)


def _sides(value, x):
    lo, hi = value['domain']
    if lo == hi == x:
        return ()
    sides = [-1, 1]
    if lo == x:
        sides.remove(-1)
    if hi == x:
        sides.remove(1)
    node = value['expr']
    if 'if' in node and len(node['if']) == 2:
        side = _guard_side(node['if'][0], value['refs'], x)
        if side is not None:
            sides = [s for s in sides if s == side]
    return tuple(sides)


def _secant(a, b, h):
    difference = a - b
    if math.isfinite(difference):
        return difference / h
    scale = max(abs(a), abs(b))
    return ((a / scale - b / scale) / h) * scale if scale else 0.0


def _extrapolate(now, old, divisor=1):
    """now + (now-old)/divisor, without multiplying large slopes."""
    if not (math.isfinite(now) and math.isfinite(old)):
        return math.nan
    difference = now-old
    if math.isfinite(difference):
        return now+difference/divisor
    scale = max(abs(now), abs(old))
    return (now/scale+(now/scale-old/scale)/divisor)*scale


def _one_sided(a, b, y, h):
    first, second = a-y, b-a
    if math.isfinite(first) and math.isfinite(second):
        numerator = _extrapolate(first, second, 2)
        if math.isfinite(numerator):
            return numerator/h
    return _extrapolate(_secant(a, y, h), _secant(b, y, 2*h))


def _confirm(value, x, y, sample, profile):
    sides = _sides(value, x)
    if not sides:
        raise TangencyError('no_convergence')
    h = profile['initialStep'] * max(1.0, abs(x))
    lo, hi = value['domain']
    # Stay inside a finite declared interval from the first stencil onward.
    for side in sides:
        end = lo if side < 0 else hi
        if end is not None and end != x:
            h = min(h, abs(end - x) / 4)
    previous = None
    previous_central = None
    stable = mismatch = jump = overflow = 0
    needed = profile['requiredStableLevels']
    for _ in range(profile['maxRefinements']):
        data, near_values, hints = [], [], []
        for side in sides:
            near, far = x + side*h, x + side*2*h
            if not (math.isfinite(near) and math.isfinite(far)) or near == x or far == near:
                raise TangencyError('no_convergence')
            a, b = sample(near), sample(far)
            if a is None or b is None:
                data = []
                break
            # Three-point second order one-sided derivative, and extrapolated
            # function limit. Both sides use signed h in increasing-x units.
            m = _one_sided(a, b, y, side*h)
            limit = _extrapolate(a, b)
            data.append((m, limit))
            near_values.append(a)
            # Extrapolate available analytic neighbor derivatives to the
            # contact. This catches plateaus caused by lost value precision;
            # a constant graph remains distinguishable from an unresolved one.
            da, db = derivative_at(value, near), derivative_at(value, far)
            hint = None if da is None or db is None else _extrapolate(da, db)
            hints.append(hint if hint is not None and math.isfinite(hint) else None)
        if len(data) == len(sides) and all(not math.isnan(m) and math.isfinite(limit) for m, limit in data):
            central = (_secant(near_values[1], near_values[0], 2*h)
                       if len(sides) == 2 else data[0][0])
            if previous is not None:
                ms = [_extrapolate(now[0], old[0], 3) for now, old in zip(data, previous)]
                # Linear extrapolation of the side limit converges quadratically.
                continuity_scale = max(1.0, abs(y), *(abs(row[1]) for row in data))
                continuous = all(abs(limit - y) / continuity_scale <= profile['continuityRel']
                                 for m, limit in data)
                limits_stable = all(abs(now[1] - old[1]) / continuity_scale <= profile['continuityRel']
                                    for now, old in zip(data, previous))
                jump = jump + 1 if limits_stable and not continuous else 0
                if jump >= needed:
                    raise TangencyError('not_differentiable')
                overflowing = (continuous and limits_stable and all(
                    math.isinf(now[0]) and now[0] == old[0] for now, old in zip(data, previous)))
                overflow = overflow+1 if overflowing else 0
                if overflow >= needed:
                    signs = {math.copysign(1, m) for m, limit in data}
                    raise TangencyError('non_finite' if len(signs) == 1 else 'not_differentiable')
                if all(math.isfinite(m) for m in ms):
                    dirs = [direction(m) for m in ms]
                    agreed = len(dirs) == 1 or _distance(dirs[0], dirs[1]) <= profile['directionAbs']
                    resolved = all(hint is None or _distance(d, direction(hint)) <= profile['directionAbs']
                                   for d, hint in zip(dirs, hints))
                    changing = max(_distance(direction(now[0]), direction(old[0]))
                                   for now, old in zip(data, previous))
                    # Unit directions alone can appear stable while slopes
                    # diverge. Also require shrinking finite derivative error.
                    finite_stable = all(abs(now[0] - old[0]) <= profile['xAbs'] +
                                        profile['xRel'] * max(abs(now[0]), abs(old[0]))
                                        for now, old in zip(data, previous))
                    steady = changing <= profile['directionAbs'] and finite_stable
                    mismatch = mismatch + 1 if steady and continuous and not agreed else 0
                    if mismatch >= needed:
                        raise TangencyError('not_differentiable')
                    stable = stable + 1 if steady and continuous and agreed and resolved else 0
                    if stable >= needed:
                        # Central second-order difference and Richardson for
                        # the two-sided case; the same extrapolation one-sided.
                        slope = _extrapolate(central, previous_central, 3)
                        if not math.isfinite(slope):
                            raise TangencyError('non_finite')
                        return slope
            previous = data
            previous_central = central
        else:
            previous = None
            previous_central = None
            stable = mismatch = jump = overflow = 0
        h /= 2
    raise TangencyError('no_convergence')


def graph_derivative(value, x):
    """Return (f(x), finite slope), or a precise local refusal."""
    profile = registry().numeric['tangency']
    body = evaluator(value)
    cache = {}

    def sample(t):
        if t not in cache:
            if len(cache) >= profile['maxEvaluations']:
                raise TangencyError('no_convergence')
            cache[t] = body(t)
        return cache[t]

    y = sample(x)
    if y is None or _represented_pole(value['expr'], value['refs'], x):
        raise TangencyError('out_of_domain')
    if not _sides(value, x):
        raise TangencyError('no_convergence')
    m = derivative_at(value, x)
    if m is not None and not _has_switch(value['expr'], value['refs'], x):
        return y, m
    if _infinite_form(value['expr'], value['refs'], x):
        raise TangencyError('not_differentiable')
    try:
        v, d = _dual(value['expr'], value['refs'], x)
        if not (math.isfinite(v) and math.isfinite(d)):
            raise TangencyError('non_finite')
    except (ExprError, ArithmeticError, ValueError):
        pass
    return y, _confirm(value, x, y, sample, profile)
