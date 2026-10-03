# `line.perpendicular_bisector` — perpendicular bisector of two points

Registry 1.2 · group `line` · orientation `ab_ccw90` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `line: line` |
| undefined | `coincident_points`, `upstream` |
| checks | `through_midpoint`, `perpendicular` |

## Value

    vx = bx − ax
    vy = by − ay
    L  = hypot(vx, vy)
    if L ≤ tol.decide:               → undefined "coincident_points"
    ux = vx / L
    uy = vy / L
    mx = (ax + bx) / 2
    my = (ay + by) / 2
    dirx = −uy
    diry =  ux                       (b − a turned 90° counter-clockwise)
    k = mx·dirx + my·diry
    line = {p: [mx − k·dirx, my − k·diry], dir: [dirx, diry]}

Swapping `a` and `b` gives the same line with the opposite `dir`.

## Path frame

The origin of the path parameter is the midpoint `mid(a, b)`, not `p`
(kernel.md §5.5): `t = 0` is the midpoint, `t` grows along `dir`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` (length) |

## Checks

Distance from a point `(x, y)` to the line: `| (x − px)·diry − (y − py)·dirx |`.

- `through_midpoint`: the distance of `((ax + bx)/2, (ay + by)/2)`
- `perpendicular`: `| dirx·(bx − ax) + diry·(by − ay) |` (a length)
