"""Global polynomial analysis for registry 1.11.

Coefficients are ascending, trimmed only at exact zero. Isolation recursively
partitions the Cauchy interval at derivative roots. Values and absolute-value
bounds share a positive scale, including reciprocal Horner evaluation outside
[-1, 1], so residual ratios and signs do not overflow at distant roots.
"""
from __future__ import annotations

import math
import sys

from ..expr import ExprError, compile_function
from ..registry import registry
from .function import evaluator


class AnalysisError(Exception):
    """A public failure reason, with a bounded diagnostic stage."""

    def __init__(self, reason, stage='isolation'):
        self.reason = reason
        self.stage = stage
        super().__init__(reason)


class Budget:
    """One deterministic evaluation budget shared by an operation's searches."""

    def __init__(self):
        self.profile = registry().numeric['functionAnalysis']
        self.used = 0

    def tick(self):
        self.used += 1
        if self.used > self.profile['maxEvaluations']:
            raise AnalysisError('limit_exceeded')


def _trim(c):
    while len(c) > 1 and c[-1] == 0.0:
        c.pop()
    if not all(math.isfinite(v) for v in c):
        raise AnalysisError('non_finite')
    return c


def _has_x(node):
    if isinstance(node, list):
        return any(_has_x(v) for v in node)
    return isinstance(node, dict) and ('var' in node or any(_has_x(v) for v in node.values()))


def _has_if(node):
    if isinstance(node, list):
        return any(_has_if(v) for v in node)
    return isinstance(node, dict) and ('if' in node or any(_has_if(v) for v in node.values()))


def coefficients(value, budget):
    """Recognize the polynomial AST without sampling or cancelling x denominators.

    Constant subtrees use the existing interpreter, including its domain and
    finiteness checks. Every operand is read even when multiplied by zero.
    """
    refs = value['refs']
    maximum = budget.profile['maxPolynomialDegree']

    def constant(node):
        budget.tick()
        try:
            return compile_function(node, refs)(0.0)
        except ExprError:
            raise AnalysisError('not_polynomial') from None

    def multiply(a, b):
        if len(a) + len(b) - 2 > maximum:
            raise AnalysisError('limit_exceeded')
        c = [0.0] * (len(a) + len(b) - 1)
        for i, av in enumerate(a):
            for j, bv in enumerate(b):
                product = av * bv
                if product == 0.0 and av != 0.0 and bv != 0.0:
                    raise AnalysisError('non_finite')
                c[i + j] += product
        return _trim(c)

    def read(node):
        if _has_if(node):
            raise AnalysisError('not_polynomial')
        if not _has_x(node):
            return [constant(node)]
        if 'var' in node:
            return [0.0, 1.0]
        name = node.get('op')
        if name not in ('+', '-', 'neg', '*', '/', '^'):
            raise AnalysisError('not_polynomial')
        args = node['args']
        a = read(args[0])
        if name == 'neg':
            return [-v for v in a]
        if name in ('/', '^'):
            if _has_x(args[1]):
                raise AnalysisError('not_polynomial')
            b = constant(args[1])
            if name == '/':
                if b == 0.0:
                    raise AnalysisError('not_polynomial')
                quotient = [v / b for v in a]
                if any(v != 0.0 and q == 0.0 for v, q in zip(a, quotient)):
                    raise AnalysisError('non_finite')
                return _trim(quotient)
            if b < 0 or not b.is_integer():
                raise AnalysisError('not_polynomial')
            if (len(a) - 1) * b > maximum:
                raise AnalysisError('limit_exceeded')
            # Exponentiation by squaring, without squaring past the last bit.
            result = [1.0]
            k = int(b)
            while k:
                if k & 1:
                    result = multiply(result, a)
                k >>= 1
                if k:
                    a = multiply(a, a)
            return result
        b = read(args[1])
        if name == '*':
            return multiply(a, b)
        c = [0.0] * max(len(a), len(b))
        for i, v in enumerate(a):
            c[i] = v
        for i, v in enumerate(b):
            c[i] += v if name == '+' else -v
        return _trim(c)

    return read(value['expr'])


def _normalized(c):
    scale = max(abs(v) for v in c)
    if scale == 0.0:
        return c[:]
    out = [v / scale for v in c]
    if any(v != 0 and w == 0 for v, w in zip(c, out)):
        raise AnalysisError('non_finite')
    return out


def derivative(c):
    return [i * c[i] for i in range(1, len(c))] or [0.0]


def _bound(c):
    r = 1.0 + max((abs(v / c[-1]) for v in c[:-1]), default=0.0)
    if not math.isfinite(r):
        raise AnalysisError('non_finite')
    return r


def _sample(c, x, budget):
    """Signed scaled p(x) and sum |c_i x^i| in the same scale."""
    budget.tick()
    if abs(x) <= 1:
        terms = reversed(c)
        t = x
        flip = False
    else:
        terms = iter(c)
        t = 1.0 / x
        flip = x < 0 and (len(c) - 1) % 2 == 1
    v = total = 0.0
    for ci in terms:
        v = v * t + ci
        total = total * abs(t) + abs(ci)
    return (-v if flip else v), total


def _ratio(sample):
    value, total = sample
    return abs(value) / total if total else (0.0 if value == 0 else math.inf)


def _midpoint(a, b):
    return a / 2.0 + b / 2.0 if a < 0 < b else a + (b - a) / 2.0


def _bisect(c, lo, hi, left, right, budget):
    profile = budget.profile
    for _ in range(profile['bisectionSteps']):
        mid = _midpoint(lo, hi)
        if not lo < mid < hi:
            break
        value = _sample(c, mid, budget)
        if value[0] == 0.0:
            return mid
        if (value[0] < 0) == (left[0] < 0):
            lo, left = mid, value
        else:
            hi, right = mid, value
    x, sample = (lo, left) if _ratio(left) <= _ratio(right) else (hi, right)
    if hi - lo > max(profile['xAbs'], profile['xRel'] * abs(x)) or _ratio(sample) > registry().numeric['tolerances']['decide']['scalar']:
        raise AnalysisError('no_convergence')
    return x


def _merge(xs, ctx):
    out = []
    for x in sorted(xs):
        if out:
            distance = x - out[-1]
            ctx.decide('root_merge', distance, ctx.tol.decide_length)
            if distance <= ctx.tol.decide_length:
                continue
        out.append(x + 0.0)
    return out


def isolate(c, budget, ctx):
    """All distinct real roots of a nonzero polynomial, in ascending x."""
    c = _normalized(_trim(c[:]))
    degree = len(c) - 1
    if degree == 0:
        return []
    if degree == 1:
        x = -c[0] / c[1]
        if not math.isfinite(x):
            raise AnalysisError('non_finite')
        return [x + 0.0]
    # Exact factors x avoid a flat underflow neighbourhood at repeated zero.
    if c[0] == 0.0:
        first = next(i for i, v in enumerate(c) if v != 0)
        return _merge([0.0] + isolate(c[first:], budget, ctx), ctx)
    radius = _bound(c)
    critical = isolate(derivative(c), budget, ctx)
    xs = [-radius] + [x for x in critical if -radius < x < radius] + [radius]
    values = [_sample(c, x, budget) for x in xs]
    accepted = set()
    tol = ctx.tol.decide_scalar
    for i in range(1, len(xs) - 1):
        ratio = _ratio(values[i])
        ctx.decide('tangent', ratio, tol)
        # Resolve a nearby simple pair by its two sign changes when its
        # residual exceeds arithmetic rounding noise. A stationary zero
        # otherwise contributes one candidate, with no adjacent duplicates.
        both_cross = values[i][0] != 0 and all(
            (values[j][0] < 0) != (values[i][0] < 0) for j in (i - 1, i + 1))
        rounding = 4 * degree * sys.float_info.epsilon
        if ratio <= tol and (not both_cross or ratio <= rounding):
            accepted.add(i)
    found = [xs[i] for i in sorted(accepted)]
    for i in range(len(xs) - 1):
        if i in accepted or i + 1 in accepted:
            continue
        a, b = values[i], values[i + 1]
        if a[0] == 0:
            found.append(xs[i])
        if b[0] == 0:
            found.append(xs[i + 1])
        if a[0] != 0 and b[0] != 0 and (a[0] < 0) != (b[0] < 0):
            found.append(_bisect(c, xs[i], xs[i + 1], a, b, budget))
    return _merge(found, ctx)


def polynomial_points(value, ctx, *, extrema=False, budget=None, c=None, interval=None):
    """All admissible (x, y, kind) solutions, before limiting output capacity."""
    budget = Budget() if budget is None else budget
    c = coefficients(value, budget) if c is None else c
    if not extrema and len(c) == 1 and c[0] == 0.0:
        raise AnalysisError('coincident')
    f = evaluator(value)
    lo, hi = value['domain']
    if interval is not None:
        lo = interval[0] if lo is None else max(lo, interval[0])
        hi = interval[1] if hi is None else min(hi, interval[1])
    if extrema:
        dc = _normalized(derivative(_normalized(c)))
        xs = isolate(dc, budget, ctx)
        radius = _bound(dc) if len(dc) > 1 else 1.0
    else:
        xs = isolate(c, budget, ctx)
    found = []
    for i, x in enumerate(xs):
        if (lo is not None and (x <= lo if extrema else x < lo)) or (hi is not None and (x >= hi if extrema else x > hi)):
            continue
        kind = None
        if extrema:
            left = _sample(dc, _midpoint(xs[i - 1] if i else -radius, x), budget)
            right = _sample(dc, _midpoint(x, xs[i + 1] if i + 1 < len(xs) else radius), budget)
            turn = left[0] != 0 and right[0] != 0 and (left[0] < 0) != (right[0] < 0)
            ctx.decide('extremum_turn', min(_ratio(left), _ratio(right)), ctx.tol.decide_scalar)
            if not turn:
                continue
            kind = 'min' if left[0] < 0 else 'max'
        budget.tick()
        y = f(x)
        if y is None:
            raise AnalysisError('non_finite', 'residual')
        if not extrema:
            ratio = _ratio(_sample(_normalized(c), x, budget))
            ctx.decide('root_residual', ratio, ctx.tol.decide_scalar)
            if ratio > ctx.tol.decide_scalar:
                raise AnalysisError('no_convergence', 'residual')
        found.append((x, y + 0.0 if extrema else 0.0, kind))
    if len(found) > budget.profile['maxResults']:
        raise AnalysisError('limit_exceeded')
    return found
