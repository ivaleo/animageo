"""Scene scale and tolerances (``ops/v1/_numeric.json``).

``S = max(w, h, D)``: ``w, h`` are the sizes of ``viewDefaults.bounds`` (or of
``defaultBounds``), ``D = hypot(xmax - xmin, ymax - ymin)`` over the free
points of the evaluated case (0 when there are none).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..registry import registry

__all__ = ['Tolerances', 'default_bounds', 'decision_margin', 'scene_scale', 'tolerances']


def _numeric() -> dict:
    return registry().numeric


def default_bounds() -> list:
    return list(_numeric()['defaultBounds'])


def decision_margin() -> float:
    """Factor of ``tol.decide`` within which the fixture generator refuses a case."""
    return float(_numeric()['generator']['decisionMargin'])


def scene_scale(bounds, points) -> float:
    """``S`` for view ``bounds`` (``[xmin, ymin, xmax, ymax]`` or ``None``) and
    free ``points`` (iterable of ``(x, y)``)."""
    if bounds is None:
        bounds = default_bounds()
    xmin, ymin, xmax, ymax = (float(v) for v in bounds)
    w = xmax - xmin
    h = ymax - ymin
    d = 0.0
    pts = list(points)
    if pts:
        pxmin = min(p[0] for p in pts)
        pxmax = max(p[0] for p in pts)
        pymin = min(p[1] for p in pts)
        pymax = max(p[1] for p in pts)
        d = math.hypot(pxmax - pxmin, pymax - pymin)
    return max(w, h, d)


@dataclass(frozen=True)
class Tolerances:
    """Absolute tolerances for one scale ``S``."""

    scale: float
    decide_length: float
    decide_scalar: float
    check_passed: float
    check_failed: float
    parity_length: float
    parity_area: float
    parity_scalar: float

    def parity(self, kind: str) -> float:
        """Parity tolerance for a value kind of ``_types.json``."""
        return {'length': self.parity_length, 'area': self.parity_area,
                'scalar': self.parity_scalar}[kind]


def tolerances(scale: float) -> Tolerances:
    tol = _numeric()['tolerances']
    s = float(scale)
    return Tolerances(
        scale=s,
        decide_length=tol['decide']['length'] * s,
        decide_scalar=tol['decide']['scalar'],
        check_passed=tol['check']['passed'] * s,
        check_failed=tol['check']['failed'] * s,
        parity_length=tol['parity']['length'] * s,
        parity_area=tol['parity']['area'] * s * s,
        parity_scalar=tol['parity']['scalar'],
    )
