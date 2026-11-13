"""Bounded finite-piece searches for registry 1.11 function analysis.

The sampling and iteration order is shared with the browser implementation:
left-to-right pieces, right-first expanding brackets, one evaluation budget.
No solver consults a viewport or retains a previous frame.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..expr import ExprError, compile_function
from ..expr.evaluate import _fn, _pow, _power
from ..expr.validate import integer_power
from .function import evaluator
from .function_analysis import (AnalysisError, Budget, _has_x, _midpoint, _normalized,
                                _ratio, _sample, _merge, coefficients, polynomial_points)


def _grid(a, b, n):
    width = b - a
    out = []
    for k in range(n + 1):
        product = k * width
        out.append(a + product / n if math.isfinite(product) else
                   (1 - k / n) * a + (k / n) * b)
    out[0], out[-1] = a, b
    return out


def _relative_difference(a, b, initial_a, initial_b):
    scale = max(abs(a), abs(b), abs(initial_a), abs(initial_b))
    if scale == 0:
        return 0.0
    numerator = abs(a / scale - b / scale)
    denominator = abs(initial_a / scale - initial_b / scale)
    return numerator / denominator if denominator else (0.0 if a == b else math.inf)


def _suspect_cells(d):
    """The plateau-maxima rule of the existing area sampling profile."""
    out = []
    k = 0
    while k < len(d):
        end = k
        while end + 1 < len(d) and d[end + 1] == d[k]:
            end += 1
        if (k == 0 or d[k - 1] < d[k]) and (end == len(d) - 1 or d[end + 1] < d[k]):
            out.append(k)
        k = end + 1
    return out


def _truth(condition, refs, x):
    return compile_function({'if': [condition, {'num': 1}, {'num': 0}]}, refs)(x) != 0


def _at_switch(condition, refs, x):
    if 'cmp' in condition:
        a, b = condition['args']
        return compile_function(a, refs)(x) == compile_function(b, refs)(x)
    return any(_at_switch(c, refs, x) for key in ('and', 'or', 'not') for c in condition.get(key, ()))


def _dual(node, refs, x):
    """Value and analytic derivative of the selected AST branch."""
    if not _has_x(node):
        return compile_function(node, refs)(x), 0.0
    if 'var' in node:
        return x, 1.0
    if 'if' in node:
        condition, then, *other = node['if']
        branch = then if _truth(condition, refs, x) else (other[0] if other else None)
        if branch is None or _at_switch(condition, refs, x):
            raise ExprError('out_of_domain')
        return _dual(branch, refs, x)
    args = node['args']
    a, da = _dual(args[0], refs, x)
    if 'fn' in node:
        name = node['fn']
        if name in ('min', 'max'):
            b, db = _dual(args[1], refs, x)
            if a == b:
                raise ExprError('out_of_domain')
            return (a, da) if (a < b) == (name == 'min') else (b, db)
        v = _fn(name, a)
        if name == 'sin':
            d = math.cos(a) * da
        elif name == 'cos':
            d = -math.sin(a) * da
        elif name == 'tan':
            d = (da / math.cos(a)) / math.cos(a)
        elif name == 'atan':
            d = da / (1 + a * a) if abs(a) <= 1 else (da / a) / (a + 1 / a)
        elif name == 'abs':
            if a == 0:
                raise ExprError('out_of_domain')
            d = da if a > 0 else -da
        elif name == 'sqrt':
            d = da / (2 * v)
        elif name in ('ln', 'lg'):
            d = da / a
            if name == 'lg':
                d /= math.log(10)
        elif name in ('asin', 'acos'):
            d = da / math.sqrt((1 - a) * (1 + a))
            if name == 'acos':
                d = -d
        else:  # exp
            d = v * da
        return v, d
    name = node['op']
    if name == 'neg':
        return -a, -da
    b, db = _dual(args[1], refs, x)
    if name == '+':
        return a + b, da + db
    if name == '-':
        return a - b, da - db
    if name == '*':
        return a * b, da * b + a * db
    if name == '/':
        return a / b, (da - (a / b) * db) / b
    n = integer_power(node)
    v = _power(a, n) if n is not None else _pow(a, b)
    if db == 0 and b.is_integer():
        d = 0.0 if b == 0 else b * _power(a, int(b) - 1) * da
    else:
        d = v * (db * math.log(a) + b * da / a)
    return v, d


def derivative_at(value, x):
    """A finite analytic derivative, or None at a cusp/switch/domain failure."""
    try:
        v, d = _dual(value['expr'], value['refs'], float(x))
        return d if math.isfinite(v) and math.isfinite(d) else None
    except (ExprError, ArithmeticError, ValueError):
        return None


def _structural(node, refs):
    if not _has_x(node):
        try:
            return math.isfinite(compile_function(node, refs)(0))
        except ExprError:
            return False
    if 'var' in node:
        return True
    if 'if' in node:
        return False
    args = node.get('args', ())
    if node.get('fn') in ('sin', 'cos', 'atan', 'abs'):
        return _structural(args[0], refs)
    name = node.get('op')
    if name in ('+', '-', '*', 'neg'):
        return all(_structural(a, refs) for a in args)
    if name in ('/', '^') and not _has_x(args[1]):
        try:
            b = compile_function(args[1], refs)(0)
            permitted = b != 0 if name == '/' else b >= 0 and b.is_integer()
            return permitted and _structural(args[0], refs)
        except ExprError:
            return False
    return False


def _boundary_marker(node, refs, x):
    """A represented, finite AST domain boundary, rather than a nearby sample."""
    if 'if' in node:
        condition, then, *other = node['if']
        branch = then if _truth(condition, refs, x) else (other[0] if other else None)
        return branch is not None and (_at_switch(condition, refs, x) or _boundary_marker(branch, refs, x))
    args = node.get('args', ())
    if node.get('fn') in ('sqrt', 'asin', 'acos'):
        v = compile_function(args[0], refs)(x)
        if (node['fn'] == 'sqrt' and v == 0) or (node['fn'] != 'sqrt' and abs(v) == 1):
            return True
    return any(_boundary_marker(a, refs, x) for a in args)


@dataclass(frozen=True)
class Piece:
    lo: float
    hi: float
    left_closed: bool = True
    right_closed: bool = True

    def contains(self, x):
        return ((x > self.lo or (self.left_closed and x == self.lo)) and
                (x < self.hi or (self.right_closed and x == self.hi)))


class Search:
    """A current function, its safe evaluator and the operation-wide budget."""

    def __init__(self, value, ctx):
        self.value, self.ctx = value, ctx
        self.budget = Budget()
        self.profile = self.budget.profile
        self.body = evaluator(value)
        self.structural = _structural(value['expr'], value['refs'])
        self.poly = None
        self._constant_cache = {}
        self.zero_plateau = False
        self._working_range = None
        try:
            self.poly = coefficients(value, self.budget)
        except AnalysisError as exc:
            if exc.reason != 'not_polynomial':
                raise

    def f(self, x):
        self.budget.tick()
        y = self.body(x)
        inside = self._working_range is None or self._working_range[0] < x < self._working_range[1]
        if y == 0 and inside and self.poly is None and self.active_constant(x) == 0:
            self.zero_plateau = True
        return y

    def slope(self, x):
        self.budget.tick()
        return derivative_at(self.value, x)

    def constant_reason(self):
        if self.poly is not None and len(self.poly) == 1:
            return 'coincident' if self.poly[0] == 0 else 'no_root'
        return None

    def _successful_root(self, x):
        if self.zero_plateau:
            raise AnalysisError('coincident', 'pieces')
        return x + 0.0

    def x_tol(self, x):
        return max(self.profile['xAbs'], self.profile['xRel'] * abs(x))

    def cut(self, a, b):
        lo, hi = self.value['domain']
        if lo is not None:
            a = max(a, lo)
        if hi is not None:
            b = min(b, hi)
        return a, b

    def _closed_boundary(self, x):
        try:
            return _boundary_marker(self.value['expr'], self.value['refs'], x)
        except (ExprError, ArithmeticError, ValueError):
            return False

    def _transition(self, a, b, ya, yb):
        """Refine a finite/absent edge to neighbouring representable doubles."""
        left_finite = ya is not None
        for _ in range(self.profile['continuitySteps']):
            mid = _midpoint(a, b)
            if not a < mid < b:
                x = a if left_finite else b
                return x, self._closed_boundary(x)
            y = self.f(mid)
            if (y is not None) == left_finite:
                a, ya = mid, y
            else:
                b, yb = mid, y
        raise AnalysisError('no_convergence', 'pieces')

    def _jump(self, a, b, ya, yb):
        initial_a, initial_b = ya, yb
        if ya == yb:
            return None
        for _ in range(self.profile['continuitySteps']):
            if _relative_difference(ya, yb, initial_a, initial_b) <= self.profile['residualRel']:
                return None
            mid = _midpoint(a, b)
            if not a < mid < b:
                return a, b, False
            y = self.f(mid)
            if y is None:
                return mid, mid, True
            scale = max(abs(ya), abs(y), abs(yb))
            left = abs(y / scale - ya / scale) if scale else 0
            right = abs(yb / scale - y / scale) if scale else 0
            if left >= right:
                b, yb = mid, y
            else:
                a, ya = mid, y
        raise AnalysisError('no_convergence', 'pieces')

    def pieces(self, a, b):
        a, b = self.cut(a, b)
        if not a < b:
            return []
        xs = _grid(a, b, self.profile['pieceGridCells'])
        ys = [self.f(x) for x in xs]
        deltas = [abs(y1 - y0) if y0 is not None and y1 is not None else -1
                  for y0, y1 in zip(ys, ys[1:])]
        suspect = set() if self.structural else set(_suspect_cells(deltas))
        edges, opened = [], set()

        def add(lo, hi, lc=True, rc=True):
            if not lc:
                opened.add(lo)
            if not rc:
                opened.add(hi)
            if lo < hi:
                edges.append(Piece(lo, hi, lc, rc))

        def transition(lo, hi, ylo, yhi):
            end, closed = self._transition(lo, hi, ylo, yhi)
            if ylo is not None:
                add(lo, end, rc=closed)
            else:
                add(end, hi, lc=closed)

        for k in range(len(xs) - 1):
            lo, hi, ylo, yhi = xs[k], xs[k + 1], ys[k], ys[k + 1]
            if lo == hi or (ylo is None and yhi is None):
                continue
            if ylo is None or yhi is None:
                transition(lo, hi, ylo, yhi)
                continue
            mid = _midpoint(lo, hi)
            ym = self.f(mid) if not self.structural and lo < mid < hi else ylo
            cut = (mid, mid, True) if ym is None else self._jump(lo, hi, ylo, yhi) if k in suspect else None
            if cut is None:
                add(lo, hi)
            elif cut[2]:
                transition(lo, cut[0], ylo, None)
                transition(cut[1], hi, None, yhi)
            else:
                add(lo, cut[0], rc=False)
                add(cut[1], hi, lc=False)
        out = []
        for edge in edges:
            edge = Piece(edge.lo, edge.hi, edge.left_closed and edge.lo not in opened,
                         edge.right_closed and edge.hi not in opened)
            if out and out[-1].hi == edge.lo and out[-1].right_closed and edge.left_closed:
                prev = out.pop()
                out.append(Piece(prev.lo, edge.hi, prev.left_closed, edge.right_closed))
            else:
                out.append(edge)
        return out

    def continuous_at(self, x, *, approximate=False):
        if self.structural:
            return self.f(x) is not None
        h = max(16 * self.x_tol(x), self.ctx.tol.decide_length)
        a, b = self.cut(x - h, x + h)
        pieces = self.pieces(a, b)
        if approximate:
            return (len(pieces) == 1 and pieces[0].lo == a and pieces[0].hi == b and
                    pieces[0].left_closed and pieces[0].right_closed)
        return any(piece.contains(x) for piece in pieces)

    def continuous_between(self, a, b):
        if a == b:
            return self.continuous_at(a)
        lo, hi = min(a, b), max(a, b)
        pieces = self.pieces(lo, hi)
        return (len(pieces) == 1 and pieces[0].lo == lo and pieces[0].hi == hi and
                pieces[0].left_closed and pieces[0].right_closed)

    def bisect(self, a, b, ya, yb):
        initial_a, initial_b = ya, yb
        for _ in range(self.profile['bisectionSteps']):
            mid = _midpoint(a, b)
            if not a < mid < b:
                break
            y = self.f(mid)
            if y is None:
                return None
            if y == 0:
                return mid if self.continuous_at(mid) else None
            if (y < 0) == (ya < 0):
                a, ya = mid, y
            else:
                b, yb = mid, y
        x, y = (a, ya) if abs(ya) <= abs(yb) else (b, yb)
        scale = max(abs(y), abs(initial_a), abs(initial_b))
        denominator = min(abs(initial_a) / scale, abs(initial_b) / scale) if scale else 0
        residual = (abs(y) / scale) / denominator if denominator else math.inf
        limit = self.profile['residualRel']
        if self.poly is not None:
            residual = _ratio(_sample(_normalized(self.poly), x, self.budget))
            limit = self.ctx.tol.decide_scalar
        if b - a <= self.x_tol(x) and residual <= limit and self.continuous_at(x):
            slope = self.slope(x)
            normal = abs(y) / max(1.0, abs(slope) if slope is not None else 0.0)
            self.ctx.decide('root_residual', normal, self.ctx.tol.decide_length)
            return x
        return None

    def near(self, start):
        self._working_range = None
        reason = self.constant_reason()
        if reason:
            raise AnalysisError(reason, 'newton')
        x, y = start, self.f(start)
        scale = abs(y) if y is not None else 0.0
        seen = {x}
        for _ in range(self.profile['newtonSteps']):
            if self.zero_plateau:
                raise AnalysisError('coincident', 'pieces')
            if y is None:
                break
            if y == 0:
                if self.continuous_at(x):
                    return self._successful_root(x)
                break
            slope = self.slope(x)
            if slope is None or slope == 0:
                break
            step = y / slope
            if not math.isfinite(step):
                break
            accepted = None
            for _ in range(self.profile['backtrackSteps'] + 1):
                trial = x - step
                if trial == x:
                    break
                if math.isfinite(trial):
                    value = self.f(trial)
                    if value is not None and abs(value) < abs(y) and self.continuous_between(x, trial):
                        accepted = trial, value
                        break
                step /= 2
            if accepted is None:
                break
            trial, value = accepted
            scale = max(scale, abs(value))
            if value == 0 and self.continuous_at(trial):
                return self._successful_root(trial)
            if abs(trial - x) <= self.x_tol(trial) and scale and abs(value) / scale <= self.profile['residualRel']:
                if self.continuous_at(trial, approximate=True):
                    return self._successful_root(trial)
                break
            if trial in seen:
                break
            seen.add(trial)
            x, y = trial, value
        previous = None
        for i in range(self.profile['bracketMaxDoublings'] + 1):
            radius = min(self.profile['bracketInitialStep'] * 2 ** i, self.profile['bracketMaxStep'])
            if radius == previous:
                break
            previous = radius
            for side in (1, -1):
                end = start + side * radius
                if not math.isfinite(end) or end == start:
                    continue
                pieces = self.pieces(min(start, end), max(start, end))
                if self.zero_plateau:
                    raise AnalysisError('coincident', 'pieces')
                if side < 0:
                    pieces.reverse()
                for piece in pieces:
                    xs = _grid(piece.lo, piece.hi, self.profile['gridCells'])
                    if side < 0:
                        xs.reverse()
                    previous_node = None
                    for node in xs:
                        v = self.f(node)
                        if self.zero_plateau:
                            raise AnalysisError('coincident', 'pieces')
                        if v is None:
                            previous_node = None
                            continue
                        if v == 0 and piece.contains(node) and self.continuous_at(node):
                            return self._successful_root(node)
                        if previous_node is not None and v != 0 and previous_node[1] != 0 and (v < 0) != (previous_node[1] < 0):
                            lo, hi = sorted((node, previous_node[0]))
                            vlo, vhi = (v, previous_node[1]) if node == lo else (previous_node[1], v)
                            got = self.bisect(lo, hi, vlo, vhi)
                            if got is not None:
                                return self._successful_root(got)
                        previous_node = node, v
        if self.zero_plateau:
            raise AnalysisError('coincident', 'pieces')
        raise AnalysisError('no_convergence', 'bracket')

    def _active_constant(self, node, x):
        if 'if' in node:
            condition, then, *other = node['if']
            if _at_switch(condition, self.value['refs'], x):
                return None
            selected = then if _truth(condition, self.value['refs'], x) else (other[0] if other else None)
            return None if selected is None else self._active_constant(selected, x)
        if node.get('fn') in ('min', 'max'):
            a, b = node['args']
            av = compile_function(a, self.value['refs'])(x)
            bv = compile_function(b, self.value['refs'])(x)
            if av == bv:
                return None
            selected = a if (av < bv) == (node['fn'] == 'min') else b
            return self._active_constant(selected, x)
        args = node.get('args', ())
        if args and ('op' in node or 'fn' in node):
            values = [self._active_constant(child, x) for child in args]
            if all(v is not None for v in values):
                reduced = dict(node, args=[{'num': v} for v in values])
                return compile_function(reduced, self.value['refs'])(x)
        key = id(node)
        if key not in self._constant_cache:
            try:
                c = coefficients(dict(self.value, expr=node), self.budget)
                self._constant_cache[key] = c[0] if len(c) == 1 else None
            except AnalysisError:
                # This is only a proof attempt for a constant active branch.
                # A nonpolynomial numerical body need not obey the expanded
                # degree/representation limits of global polynomial isolation.
                if self.budget.used > self.profile['maxEvaluations']:
                    raise
                self._constant_cache[key] = None
        return self._constant_cache[key]

    def active_constant(self, x):
        try:
            return self._active_constant(self.value['expr'], x)
        except (ExprError, ArithmeticError, ValueError):
            return None

    def _golden(self, objective, a, b):
        phi = (math.sqrt(5) - 1) / 2

        def lerp(t):
            width = b - a
            return a + t * width if math.isfinite(width) else (1 - t) * a + t * b

        c, d = lerp(1 - phi), lerp(phi)
        gc, gd = objective(c), objective(d)
        for _ in range(self.profile['goldenSteps']):
            if gc <= gd:
                b, d, gd = d, c, gc
                c = lerp(1 - phi)
                gc = objective(c)
            else:
                a, c, gc = c, d, gd
                d = lerp(phi)
                gd = objective(d)
        return (c, gc) if gc <= gd else (d, gd)

    def _limit(self, found):
        if len(found) > self.profile['maxResults']:
            raise AnalysisError('limit_exceeded')
        return found

    def _piece_roots(self, piece):
        xs = _grid(piece.lo, piece.hi, self.profile['gridCells'])
        ys = [self.f(x) for x in xs]
        defined = [y for y in ys if y is not None]
        if any(y == 0 and piece.contains(x) and self.active_constant(x) == 0 for x, y in zip(xs, ys)):
            raise AnalysisError('coincident', 'pieces')
        if defined and all(y == 0 for y in defined):
            raise AnalysisError('no_convergence', 'pieces')
        found = []
        for x, y in zip(xs, ys):
            if y == 0 and piece.contains(x) and self.continuous_at(x):
                found.append(x)
        for i in range(len(xs) - 1):
            a, b = ys[i], ys[i + 1]
            if a is not None and b is not None and a != 0 and b != 0 and (a < 0) != (b < 0):
                x = self.bisect(xs[i], xs[i + 1], a, b)
                if x is not None and piece.contains(x):
                    found.append(x)
        for i in range(1, len(xs) - 1):
            left, center, right = ys[i - 1:i + 2]
            if left is None or center is None or right is None or left == 0 or center == 0 or right == 0:
                continue
            if not (left < 0) == (center < 0) == (right < 0):
                continue
            if not (abs(center) <= abs(left) and abs(center) < abs(right)):
                continue

            def absolute(t):
                v = self.f(t)
                return math.inf if v is None else abs(v)

            x, best = self._golden(absolute, xs[i - 1], xs[i + 1])
            if abs(center) <= best:
                x, best = xs[i], abs(center)
            if not piece.contains(x) or not abs(left) > best < abs(right) or not self.continuous_at(x):
                continue
            scale = max(best, abs(left), abs(right))
            residual = (best / scale) / max(abs(left) / scale, abs(right) / scale) if scale else math.inf
            self.ctx.decide('tangent', residual, self.ctx.tol.decide_scalar)
            if residual <= self.ctx.tol.decide_scalar:
                found.append(x)
        return found

    def roots(self, a, b, pieces=None):
        self._working_range = (a, b)
        reason = self.constant_reason()
        if reason:
            if reason == 'coincident':
                raise AnalysisError(reason, 'pieces')
            return []
        if self.poly is not None:
            return polynomial_points(self.value, self.ctx, budget=self.budget, c=self.poly, interval=(a, b))
        found = []
        for piece in self.pieces(a, b) if pieces is None else pieces:
            found.extend(self._piece_roots(piece))
        if self.zero_plateau:
            raise AnalysisError('coincident', 'pieces')
        xs = self._limit(_merge(found, self.ctx))
        return [(x, 0.0, None) for x in xs]

    def root_interval(self, a, b):
        self._working_range = (a, b)
        reason = self.constant_reason()
        if reason:
            raise AnalysisError(reason, 'pieces')
        pieces = self.pieces(a, b)
        if self.zero_plateau:
            raise AnalysisError('coincident', 'pieces')
        for endpoint in (a, b):
            if any(piece.contains(endpoint) for piece in pieces) and self.f(endpoint) == 0 and self.continuous_at(endpoint):
                return self._successful_root(endpoint)
        ya, yb = self.f(a), self.f(b)
        if (len(pieces) == 1 and pieces[0].lo == a and pieces[0].hi == b and
                pieces[0].left_closed and pieces[0].right_closed and
                ya is not None and yb is not None and ya != 0 and yb != 0 and (ya < 0) != (yb < 0)):
            result = self.bisect(a, b, ya, yb)
            if result is not None:
                return self._successful_root(result)
        found = self.roots(a, b, pieces)
        if not found:
            raise AnalysisError('no_root', 'pieces')
        return self._successful_root(found[0][0])

    def extrema(self, a, b):
        self._working_range = (a, b)
        if self.poly is not None:
            return polynomial_points(self.value, self.ctx, extrema=True, budget=self.budget,
                                     c=self.poly, interval=(a, b))
        found = []
        for piece in self.pieces(a, b):
            xs = _grid(piece.lo, piece.hi, self.profile['gridCells'])
            ys = [self.f(x) for x in xs]
            for i in range(1, len(xs) - 1):
                left, center, right = ys[i - 1:i + 2]
                if left is None or center is None or right is None:
                    continue
                if center < left and center <= right:
                    kind, sign = 'min', 1
                elif center > left and center >= right:
                    kind, sign = 'max', -1
                else:
                    continue

                def objective(t):
                    v = self.f(t)
                    return math.inf if v is None else sign * v

                x, best = self._golden(objective, xs[i - 1], xs[i + 1])
                if sign * center <= best:
                    x, best = xs[i], sign * center
                if not piece.lo < x < piece.hi or not (sign * left > best < sign * right):
                    continue
                if self.active_constant(x) is not None or not self.continuous_at(x):
                    continue
                y = self.f(x)
                if y is None:
                    continue
                if not self._strict_turn(piece, x, y, sign):
                    continue
                margin = min(sign * left - best, sign * right - best)
                self.ctx.decide('extremum_turn', margin, self.ctx.tol.decide_scalar)
                found.append((x, y + 0.0, kind))
        found.sort(key=lambda row: row[0])
        out = []
        for row in found:
            if not out or row[0] - out[-1][0] > self.ctx.tol.decide_length:
                out.append(row)
        return self._limit(out)


    def _strict_turn(self, piece, x, y, sign):
        """Check both local sides; distinguish a real plateau from rounded peaks."""
        h = min(max(16 * self.x_tol(x), self.ctx.tol.decide_length),
                (x - piece.lo) / 2, (piece.hi - x) / 2)
        if h <= 0:
            return False
        for side in (-1, 1):
            at = x + side * h
            if at == x:
                return False
            value = self.f(at)
            if value is None or sign * (value - y) < 0:
                return False
            if value == y:
                if self.active_constant(at) is not None:
                    return False
                slope = self.slope(at)
                if slope is None or sign * side * slope <= 0:
                    return False
        return True
