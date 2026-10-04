# `angle.by_points` — angle a–vertex–b

Registry 1.3 · group `angle` · orientation `ccw_from_a` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `vertex: point`, `b: point` |
| outputs | `angle: angle` |
| undefined | `coincident_points`, `upstream` |
| checks | `sides` |

The oriented angle from the side `vertex → a` counter-clockwise to the side
`vertex → b`, as GeoGebra `Angle(A, B, C)`: its size is in `[0, 2π)`, so
swapping `a` and `b` gives the reflex complement. The value is
`{vertex: [x, y], a0, a1, size}` in radians (`_types.json → angles`):
`a0` is the direction of the side to `a` normalised to `[0, 2π)`, `size`
the counter-clockwise size, and `a1 = a0 + size` (not normalised, it lies
in `[0, 4π)`). Marks compare angles by their convex measure
`m(size) = size` when `size ≤ π`, else `2π − size`.

## Value

    ax' = ax − vx,  ay' = ay − vy,  La = hypot(ax', ay')
    bx' = bx − vx,  by' = by − vy,  Lb = hypot(bx', by')
    if La ≤ tol.decide or Lb ≤ tol.decide:   → undefined "coincident_points"
    ua = (ax'/La, ay'/La)
    ub = (bx'/Lb, by'/Lb)
    a0   = norm(atan2(uay, uax))
    cr   = uax·uby − uay·ubx
    q    = uax·ubx + uay·uby
    size = norm(atan2(cr, q))
    angle = {vertex: [vx, vy], a0, a1: a0 + size, size}

`norm(θ)`: `θ < 0` gives `θ + 2π`; then `θ ≥ 2π` gives `0` (a tiny negative
`θ` rounds to exactly `2π` after the addition); `−0` gives `0`.

Collinear sides give `size = 0` (same direction) or `size = π` (opposite);
neither is undefined.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` (twice) | `La`, `Lb` | `tol.decide` (length) |
| `angle_wrap` (only when `uax > 0`) | `uay` | `tol.decide` (scalar) |
| `zero_angle` (only when `q > 0`) | `cr` | `tol.decide` (scalar) |

`angle_wrap` marks the jump of `a0` between `0` and `2π` when the side to
`a` points along `+x`; `zero_angle` marks the jump of `size` between `0` and
`2π` when the sides nearly coincide. Neither is a noise decision: the value
is discontinuous across both boundaries, so the fixture generator refuses
cases near them (kernel.md §6).

## Checks

- `sides`: the largest of `hypot(vertex − v)`,
  `|wrap(a0 − atan2(ay − vy, ax − vx))| · S` and
  `|wrap(a1 − atan2(by − vy, bx − vx))| · S`, where
  `wrap(d) = d − 2π·floor((d + π) / 2π)` brings a difference of directions
  into `[−π, π)`; infinite when a side has no length
