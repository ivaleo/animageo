# `line.by_points` — line through two points

Registry 1.0 · group `line` · orientation `a_to_b` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `line: line` |
| undefined | `coincident_points`, `upstream` |
| checks | `through_a`, `through_b` |

## Value

    dx = bx − ax
    dy = by − ay
    L  = hypot(dx, dy)
    if L ≤ tol.decide:            → undefined, reason "coincident_points"
    dirx = dx / L
    diry = dy / L
    k = ax·dirx + ay·diry
    line = {p: [ax − k·dirx, ay − k·diry], dir: [dirx, diry]}

`p` is the projection of the origin onto the line; `dir` points from `a` to
`b`, so `line(B, A)` has the opposite `dir` of `line(A, B)` and the same `p`
(up to rounding).

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` (length, `1e-10·S`) |

## Checks

Distance from a point `(x, y)` to the line: `| (x − px)·diry − (y − py)·dirx |`.

- `through_a`: the distance of `a`
- `through_b`: the distance of `b`
