# `arc.three_points` — arc through three points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `arc: arc`, `center: point` |
| orientation | `ccw` |
| undefined | `collinear_points`, `upstream` |
| checks | `through_all` |

The arc of the circle through `a`, `b`, `c` from `a` through `b` to `c`
(stored counterclockwise: when `b` is not on the counterclockwise arc from
`a` to `c`, the arc runs from `c` to `a`). GeoGebra `CircumcircularArc`.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    (center, r) = steps 1–4 of circle.three_points      (collinear_points)
    θa, θb, θc = angle(a − center), angle(b − center), angle(c − center)
    φb = θb − θa,  φc = θc − θa   (each < 0 → += 2π)
    φb ≤ φc: arc = {c: center, r, a0: θa, a1: θa + φc}
    else:    arc = {c: center, r, a0: θc, a1: θc + 2π − φc}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` (as `circle.three_points`) | `tol.decide` |

## Checks

- `through_all`: the largest distance from `a`, `b`, `c` to the arc and `|center − c|`
