# `ray.at_angle` — ray at a given angle

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertex: point`, `a: point`, `size: number` |
| outputs | `ray: ray`, `point: point` |
| orientation | `rotated_side` |
| undefined | `coincident_points`, `upstream` |
| checks | `angle` |

The ray from `vertex` that turns the side `vertex → a` by `size` radians
counterclockwise (negative — clockwise), and the image of `a`. GeoGebra
`Angle(A, V, α)` creates the same point.

## Value

    w = a − vertex,  L = hypot(w)
    if L ≤ tol.decide:      → both slots "coincident_points"
    α = size.value,  r = R(α)·w
    ray = {origin: vertex, dir: r / L},  point = vertex + r

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |

## Checks

- `angle`: `|wrap(angle(point − vertex) − angle(a − vertex) − α)|·S` and `| |point − vertex| − L |`
