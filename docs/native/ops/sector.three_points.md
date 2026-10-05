# `sector.three_points` — sector over an arc through three points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `sector: sector`, `center: point` |
| orientation | `ccw` |
| undefined | `collinear_points`, `upstream` |
| checks | `through_all` |

The sector over the arc of `arc.three_points` (same formula, type
`sector`). GeoGebra `CircumcircularSector`.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    as arc.three_points

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` | `tol.decide` |

## Checks

- `through_all`: as `arc.three_points`
