# `sector.from_angle` — sector by centre, point and angle

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `a: point`, `size: number` |
| outputs | `sector: sector` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The sector with centre `center` from `a` through the angle `size` (radians;
positive counterclockwise, negative clockwise, stored counterclockwise);
`|size| ≥ 2π` is the full disc. As the classic `circle_sector_ppA`.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    w = a − center,  r = |w|
    if r ≤ tol.decide:      → "coincident_points"
    a = angle(w),  α = clamp(size.value, −2π, 2π)
    α ≥ 0: sector = {c: center, r, a0: a, a1: a + α}
    α < 0: a0 = normalize(a + α),  sector = {c: center, r, a0, a1: a0 − α}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `r` | `tol.decide` |

## Checks

- `ends`: `|start − a|` (`|end − a|` for `α < 0`), `|r − |a − center||`, `|(a1 − a0) − min(|α|, 2π)|·S`
