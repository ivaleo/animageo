# `angle.by_size` — angle of a given size

Registry 1.4 · group `angle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertex: point`, `a: point`, `size: number` |
| outputs | `angle: angle`, `point: point` |
| orientation | `ccw_from_a` |
| undefined | `coincident_points`, `upstream` |
| checks | `rotation` |

GeoGebra `Angle(A, V, α)`: the point `P` is `a` turned about `vertex` by
`size` (radians, counterclockwise for a positive value), and the angle runs
counterclockwise from `a` to `P` (from `P` to `a` for a negative size). Its
`size` is `|size|` reduced into `[0, 2π)`. `angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)`; a value
`{vertex, a0, a1, size}` has `a1 = a0 + size` (`_types.json → angles`).

## Value

    w = a − vertex,  L = hypot(w)
    if L ≤ tol.decide:                       → "coincident_points" (both slots)
    α = size.value,  c = cos α,  s = sin α
    P = vertex + (c·wx − s·wy, s·wx + c·wy)
    if α ≥ 0:  f = w,           m = α
    else:      f = P − vertex,  m = −α
    m = m − 2π·floor(m / 2π)  (m ≥ 2π → 0)
    angle = {vertex, a0: angle(f), a1: a0 + m, size: m},  point = P

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |
| `zero_angle` | `wrap(α)` | `tol.scalar` |
| `angle_wrap` | `f.y / hypot(f)` when `f.x > 0` | `tol.scalar` |

## Checks

- `rotation`: `max(| |P − v| − |a − v| |, |wrap(θ(P − v) − θ(a − v) − α)|·|a − v|, |vertex − v|, |wrap(a0 − θ(first side))|·S, |wrap(a1 − θ(second side))|·S)`, the first side `a − v` for `α ≥ 0`, else `P − v`
