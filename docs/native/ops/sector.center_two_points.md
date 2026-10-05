# `sector.center_two_points` — sector by centre and two points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `a: point`, `b: point` |
| outputs | `sector: sector` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The sector over the arc of `arc.center_two_points` (same formula, type
`sector`). GeoGebra `CircularSector(O, A, B)`.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    as arc.center_two_points

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `r`, `|b − center|` | `tol.decide` |

## Checks

- `ends`: as `arc.center_two_points`
