# `sector.on_circle` — sector of a circle between two points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `circle: circle`, `a: point`, `b: point` |
| outputs | `sector: sector` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The sector over the arc of `arc.on_circle` (same formula, type `sector`).
GeoGebra `CircleSector(c, A, B)`.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    as arc.on_circle

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `|a − c|`, `|b − c|` | `tol.decide` |

## Checks

- `ends`: as `arc.on_circle`
