"""Functions y = f(x) of the kernel (registry 1.6; docs/native/ops/function.*.md).

A ``function`` value is ``{expr, refs, domain}``: the tree of
``function.expr`` (AST with the variable ``x``), the values of its ``refs``
and ``[lo, hi]`` (``null`` — unbounded). :func:`evaluator` makes it a Python
function that returns ``None`` where the graph has no point (outside the
domain, a value outside the domain of an operation, a non-finite value).

Searches run on a grid of :data:`GRID_CELLS` equal cells; the algorithm is
the contract of the web copy, step by step:

- the grid: ``x_k = a + (k·(b − a))/n``, ``k = 0 … n``, ``n = 512``;
- simple roots: a grid node with the value exactly ``0``; a cell whose ends
  have values of opposite signs → bisection (:func:`bisect`); the root is
  kept when ``|h(x*)| ≤ max(tol.decide, 10⁻⁶·min(|h(x_k)|, |h(x_k+1)|))``
  (else the sign change is a jump or a pole);
- double roots: an interior node whose value and both neighbours have the
  same sign and whose ``|h|`` is the smallest of the three (``≤`` the left,
  ``<`` the right) → :func:`golden_min` of ``|h|`` over the two cells around
  it; ``|h(x*)| ≤ tol.decide`` (a length) is a root of multiplicity 2 (the
  decision ``tangent``);
- extrema: an interior node above its left neighbour and not below its
  right one (a maximum), or below the left and not above the right (a
  minimum) → :func:`golden_min` of ``−f`` or ``f`` over the two cells;
- roots (and extrema) closer than ``tol.decide`` merge into the first (the
  larger multiplicity stays); the list is sorted by ``x``.

:func:`function_runs` samples a graph for drawing (adaptive, gaps at
discontinuities); :func:`function_samples` gives the points of the parity
fixtures.
"""
from __future__ import annotations

import math

from ..expr import ExprError, compile_function

__all__ = ['GRID_CELLS', 'SAMPLE_COUNT', 'bisect', 'evaluator', 'find_extrema', 'find_roots', 'function_runs',
           'function_samples', 'golden_min', 'grid', 'search_interval']

GRID_CELLS = 512
BISECT_MAX = 200
GOLDEN_STEPS = 100
ROOT_RESIDUAL = 1e-6        # of the smaller end value: a sign change kept as a root (a jump or a pole is not)
INV_PHI = (math.sqrt(5.0) - 1.0) / 2.0
SAMPLE_COUNT = 33           # points of a graph in the parity fixtures
DRAW_CELLS = 256            # the first grid of a drawing
DRAW_DEPTH = 8              # halvings of a drawing cell at most
DRAW_FLATNESS = 1e-3        # of the window height: the chord error that stops halving
DRAW_JUMP = 0.05            # of the window height: a jump in a finest cell is a gap


def evaluator(value):
    """``f(x) -> float | None`` of a ``function`` value."""
    body = compile_function(value['expr'], value['refs'])
    lo, hi = value['domain']

    def f(x):
        if (lo is not None and x < lo) or (hi is not None and x > hi):
            return None
        try:
            return body(x)
        except ExprError:
            return None
    return f


def search_interval(a, b, *domains):
    """``[a, b]`` cut by the ``domain`` pairs (``None`` ends are open), or ``None`` when empty."""
    lo, hi = a, b
    for d_lo, d_hi in domains:
        if d_lo is not None and d_lo > lo:
            lo = d_lo
        if d_hi is not None and d_hi < hi:
            hi = d_hi
    return (lo, hi) if lo < hi else None


def grid(a: float, b: float, n: int = GRID_CELLS) -> list:
    return [a + (k * (b - a)) / n for k in range(n + 1)]


def bisect(h, lo, hi, h_lo, h_hi):
    """``(x, h(x))`` of a sign change of ``h`` in ``[lo, hi]``: halves at
    ``m = lo + (hi − lo)/2`` while ``lo < m < hi`` (at most
    :data:`BISECT_MAX` times), keeping the half whose ends differ in sign;
    an exact zero stops; the end with the smaller ``|h|`` (``lo`` on a tie)
    is the result; ``(None, None)`` when ``h`` has no value inside."""
    for _ in range(BISECT_MAX):
        mid = lo + (hi - lo) / 2
        if not (lo < mid < hi):
            break
        h_mid = h(mid)
        if h_mid is None:
            return None, None
        if h_mid == 0.0:
            return mid, 0.0
        if (h_mid < 0.0) == (h_lo < 0.0):
            lo, h_lo = mid, h_mid
        else:
            hi, h_hi = mid, h_mid
    return (lo, h_lo) if abs(h_lo) <= abs(h_hi) else (hi, h_hi)


def golden_min(g, a, b):
    """``(x, g(x))`` of the golden-section search for a minimum of ``g`` on
    ``[a, b]``: :data:`GOLDEN_STEPS` steps, ``c = b − φ⁻¹(b − a)``,
    ``d = a + φ⁻¹(b − a)``; ``g(c) ≤ g(d)`` keeps ``[a, d]``, else ``[c, b]``;
    the better of ``c`` and ``d`` (``c`` on a tie). ``g`` returns ``None``
    where it has no value (counted as ``+∞``)."""
    def val(x):
        v = g(x)
        return math.inf if v is None else v
    c = b - INV_PHI * (b - a)
    d = a + INV_PHI * (b - a)
    gc = val(c)
    gd = val(d)
    for _ in range(GOLDEN_STEPS):
        if gc <= gd:
            b, d, gd = d, c, gc
            c = b - INV_PHI * (b - a)
            gc = val(c)
        else:
            a, c, gc = c, d, gd
            d = a + INV_PHI * (b - a)
            gd = val(d)
    return (c, gc) if gc <= gd else (d, gd)


def _merge(found, tol):
    found.sort(key=lambda item: item[0])
    out = []
    for item in found:
        if out and item[0] - out[-1][0] <= tol:
            if item[1] > out[-1][1]:
                out[-1] = (out[-1][0], item[1]) + tuple(out[-1][2:])
            continue
        out.append(item)
    return out


def find_roots(h, a, b, ctx):
    """``[(x, multiplicity)]`` of the roots of ``h`` on ``[a, b]`` (module
    docstring); ``None`` when ``|h| ≤ tol.decide`` at every defined grid node
    and at least one is defined (``h`` vanishes on the interval: the decision
    ``coincident``)."""
    tol = ctx.tol.decide_length
    xs = grid(a, b)
    hs = [h(x) for x in xs]
    n = len(xs) - 1
    defined = [abs(v) for v in hs if v is not None]
    if defined:
        worst = max(defined)
        ctx.decide('coincident', worst, tol)
        if worst <= tol:
            return None
    found = []
    for k in range(n + 1):
        if hs[k] is None or hs[k] != 0.0:
            continue
        left = hs[k - 1] if k > 0 else None
        right = hs[k + 1] if k < n else None
        even = left is not None and right is not None and left != 0.0 and right != 0.0 \
            and (left > 0.0) == (right > 0.0)
        found.append((xs[k], 2 if even else 1))
    for k in range(n):
        h0, h1 = hs[k], hs[k + 1]
        if h0 is None or h1 is None or h0 == 0.0 or h1 == 0.0 or (h0 < 0.0) == (h1 < 0.0):
            continue
        x, hx = bisect(h, xs[k], xs[k + 1], h0, h1)
        if x is not None and abs(hx) <= max(tol, ROOT_RESIDUAL * min(abs(h0), abs(h1))):
            found.append((x, 1))
    for k in range(1, n):
        hl, hk, hr = hs[k - 1], hs[k], hs[k + 1]
        if hl is None or hk is None or hr is None or hl == 0.0 or hk == 0.0 or hr == 0.0:
            continue
        if not ((hl > 0.0) == (hk > 0.0) == (hr > 0.0)):
            continue
        if not (abs(hk) <= abs(hl) and abs(hk) < abs(hr)):
            continue

        def size(t):
            v = h(t)
            return None if v is None else abs(v)
        x, m = golden_min(size, xs[k - 1], xs[k + 1])
        ctx.decide('tangent', m, tol)
        if m <= tol:
            found.append((x, 2))
    return _merge(found, tol)


def find_extrema(f, a, b, ctx) -> list:
    """``[(x, y, kind)]`` of the extrema of ``f`` inside ``[a, b]``, ``kind``
    ``"max"`` or ``"min"`` (module docstring)."""
    tol = ctx.tol.decide_length
    xs = grid(a, b)
    fs = [f(x) for x in xs]
    found = []
    for k in range(1, len(xs) - 1):
        fl, fk, fr = fs[k - 1], fs[k], fs[k + 1]
        if fl is None or fk is None or fr is None:
            continue
        if fl < fk >= fr:
            kind = 'max'

            def g(t):
                v = f(t)
                return None if v is None else -v
        elif fl > fk <= fr:
            kind = 'min'
            g = f
        else:
            continue
        x, _ = golden_min(g, xs[k - 1], xs[k + 1])
        y = f(x)
        if y is not None:
            found.append((x, 0, y, kind))
    return [(x, y, kind) for x, _m, y, kind in _merge(found, tol)]


def function_samples(value, bounds, count: int = SAMPLE_COUNT) -> list:
    """``[[x, y | null], …]`` at ``count`` equal steps over the x-range of
    ``bounds`` cut by the domain (``[]`` when the cut is empty) — the
    sample points of the parity fixtures."""
    cut = search_interval(float(bounds[0]), float(bounds[2]), value['domain'])
    if cut is None:
        return []
    f = evaluator(value)
    lo, hi = cut
    out = []
    for k in range(count):
        x = lo + (k * (hi - lo)) / (count - 1)
        out.append([x, f(x)])
    return out


def _clip(p, q, y0, y1):
    """The part of the segment ``p q`` with ``y0 ≤ y ≤ y1``, or ``None``."""
    (xa, ya), (xb, yb) = p, q
    t0, t1 = 0.0, 1.0
    dy = yb - ya
    for bound, sign in ((y0, 1.0), (y1, -1.0)):
        num = sign * (ya - bound)
        den = sign * dy
        if den == 0.0:
            if num < 0.0:
                return None
            continue
        t = -num / den
        if den > 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    if t0 > t1:
        return None
    dx = xb - xa
    return (xa + t0 * dx, ya + t0 * dy), (xa + t1 * dx, ya + t1 * dy)


def function_runs(value, x_range, y_range) -> list:
    """Polylines ``[[(x, y), …], …]`` of the graph over ``x_range`` (cut by
    the domain), clipped to ``y_range`` widened by its height on each side.

    :data:`DRAW_CELLS` equal cells; a cell is halved (at most
    :data:`DRAW_DEPTH` times) when one end has no value, when its midpoint
    has none, or when the midpoint is farther than :data:`DRAW_FLATNESS` of
    the height from the chord; a finest cell with one end undefined, or
    whose ends differ by more than :data:`DRAW_JUMP` of the height, is a
    gap (a discontinuity is not joined)."""
    cut = search_interval(float(x_range[0]), float(x_range[1]), value['domain'])
    if cut is None:
        return []
    f = evaluator(value)
    lo, hi = cut
    height = float(y_range[1]) - float(y_range[0])
    if not height > 0:
        return []
    flat = DRAW_FLATNESS * height
    jump = DRAW_JUMP * height
    y_lo = float(y_range[0]) - height
    y_hi = float(y_range[1]) + height
    points = []                 # (x, y | None, gap before)
    xs = grid(lo, hi, DRAW_CELLS)
    first = (xs[0], f(xs[0]))
    points.append((first[0], first[1], False))

    def cell(xa, ya, xb, yb, depth):
        if ya is None and yb is None:
            points.append((xb, yb, True))
            return
        xm = xa + (xb - xa) / 2
        if depth < DRAW_DEPTH:
            ym = f(xm)
            if ya is None or yb is None or ym is None or abs(ym - (ya + yb) / 2) > flat:
                cell(xa, ya, xm, ym, depth + 1)
                cell(xm, ym, xb, yb, depth + 1)
                return
        gap = ya is None or yb is None or (depth >= DRAW_DEPTH and abs(yb - ya) > jump)
        points.append((xb, yb, gap))

    for k in range(DRAW_CELLS):
        cell(xs[k], points[-1][1] if points[-1][0] == xs[k] else f(xs[k]), xs[k + 1], f(xs[k + 1]), 0)
    runs = []
    run = []
    prev = None
    for x, y, gap in points:
        if y is None or gap:
            if len(run) > 1:
                runs.append(run)
            run = []
            prev = (x, y) if y is not None else None
            if prev is not None and y_lo <= y <= y_hi:
                run = [prev]
            continue
        if prev is None:
            prev = (x, y)
            if y_lo <= y <= y_hi:
                run = [prev]
            continue
        piece = _clip(prev, (x, y), y_lo, y_hi)
        if piece is None:
            if len(run) > 1:
                runs.append(run)
            run = []
        else:
            a, b = piece
            if not run or run[-1] != a:
                if len(run) > 1:
                    runs.append(run)
                run = [a]
            run.append(b)
            if b != (x, y):          # left the window: the run ends at its edge
                runs.append(run)
                run = []
        prev = (x, y)
    if len(run) > 1:
        runs.append(run)
    return runs
