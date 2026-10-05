# `line.tangent_at` — tangent at a point of a circle

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `circle: circle` |
| outputs | `line: line` |
| orientation | `circle_ccw` |
| undefined | `not_on_curve`, `upstream` |
| checks | `tangent` |

The tangent to a circle at a point of it, oriented along the counterclockwise
traversal of the circle.

## Value

    w = P − c,  d = hypot(w)
    if |d − r| > tol.decide:        → "not_on_curve"
    line = line through P with (−wy, wx) / d

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `not_on_curve` | `d − r` | `tol.decide` |

## Checks

- `tangent`: `| dist(c, line) − r |` and the distance from `P` to the line
