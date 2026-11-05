"""Real roots of polynomials of low degree (registry 1.8; docs/native/ops/intersect.conic_conic.md).

A polynomial is a list of coefficients from the constant term up:
``[c0, c1, …, cn]`` is ``c0 + c1·x + … + cn·xⁿ``. The algorithm is the
contract of the web copy, step by step:

- :func:`trim` drops trailing coefficients that are exactly ``0``;
- :func:`value` is Horner's scheme from the highest coefficient;
- :func:`sign_roots` finds the roots of ``c`` inside ``(lo, hi)`` where ``c``
  changes sign. The breakpoints are ``lo``, the sign-change roots of the
  derivative (found the same way, recursively) and ``hi``; ``c`` is monotone
  between two breakpoints, so each interval holds at most one root. An
  interior breakpoint where ``c`` is exactly ``0`` is a root; an interval
  whose ends have nonzero values of opposite signs holds one, found by
  :func:`~animageo.native.kernel.function.bisect`. A linear polynomial has
  the root ``−c0/c1`` when it lies inside; a constant has none.

Two roots of ``c`` always have a breakpoint between them (Rolle), so close
roots are separated as well as the critical point between them is found.
"""
from __future__ import annotations

from .function import bisect

__all__ = ['add', 'derivative', 'mul', 'scale', 'sign_roots', 'trim', 'value']


def trim(c) -> list:
    """``c`` without trailing exact zeros (at least one coefficient stays)."""
    out = list(c)
    while len(out) > 1 and out[-1] == 0.0:
        out.pop()
    return out


def value(c, x: float) -> float:
    """``c(x)`` by Horner's scheme: ``v = c[n]``, then ``v = v·x + c[i]`` for ``i = n − 1 … 0``."""
    v = c[-1]
    for i in range(len(c) - 2, -1, -1):
        v = v * x + c[i]
    return v


def derivative(c) -> list:
    """``[1·c1, 2·c2, …, n·cn]`` (``[0.0]`` for a constant)."""
    if len(c) <= 1:
        return [0.0]
    return [i * c[i] for i in range(1, len(c))]


def add(*polys) -> list:
    """The sum, term by term in the order of the arguments."""
    n = max(len(p) for p in polys)
    out = [0.0] * n
    for p in polys:
        for i, v in enumerate(p):
            out[i] = out[i] + v
    return out


def scale(k: float, c) -> list:
    return [k * v for v in c]


def mul(a, b) -> list:
    """The product: ``out[i + j] += a[i]·b[j]`` for ``i`` ascending, then ``j`` ascending."""
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] = out[i + j] + x * y
    return out


def sign_roots(c, lo: float, hi: float) -> list:
    """The roots of ``c`` inside ``(lo, hi)`` where it changes sign, ascending (module docstring)."""
    c = trim(c)
    n = len(c) - 1
    if n <= 0:
        return []
    if n == 1:
        x = -c[0] / c[1]
        return [x] if lo < x < hi else []
    breaks = [lo] + sign_roots(derivative(c), lo, hi) + [hi]
    values = [value(c, x) for x in breaks]
    out = []
    for k in range(len(breaks) - 1):
        v0 = values[k]
        v1 = values[k + 1]
        if k > 0 and v0 == 0.0:
            out.append(breaks[k])
        if v0 != 0.0 and v1 != 0.0 and (v0 < 0.0) != (v1 < 0.0):
            x, _ = bisect(lambda t: value(c, t), breaks[k], breaks[k + 1], v0, v1)
            out.append(x)
    return out
