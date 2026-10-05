# `arc.center_two_points` — arc by centre and two points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `a: point`, `b: point` |
| outputs | `arc: arc` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The arc of the circle with centre `center` through `a`, counterclockwise
from `a` to the ray `center → b` (GeoGebra `CircularArc(O, A, B)`).
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    r = |a − center|,  |b − center|    each ≤ tol.decide → "coincident_points"
    a0 = angle(a − center),  β = angle(b − center)
    a1 = β if β ≥ a0 else β + 2π
    arc = {c: center, r, a0, a1}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `r`, `|b − center|` | `tol.decide` |

## Checks

- `ends`: `|start − a|`, the distance from the end to the ray `center → b`, `|c − center|`
