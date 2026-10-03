# `point.midpoint` — midpoint of two points

Registry 1.0 · group `point` · see [kernel.md](../kernel.md) for states, tolerances and fixtures.

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `point: point` |
| undefined | `upstream` |
| checks | `equidistant`, `collinear` |

## Value

    x = (ax + bx) / 2
    y = (ay + by) / 2
    point = {x, y}

Coincident `a` and `b` are allowed: the midpoint is the common point.

## Degeneracy decisions

None.

## Checks (error measured, a length)

- `equidistant`: `| hypot(ax − mx, ay − my) − hypot(mx − bx, my − by) |`
- `collinear`: `L = hypot(bx − ax, by − ay)`; if `L ≤ tol.decide`:
  `hypot(mx − ax, my − ay)`; otherwise
  `| (mx − ax)·(by − ay) − (my − ay)·(bx − ax) | / L`
