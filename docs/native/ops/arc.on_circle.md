# `arc.on_circle` — arc of a circle between two points

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `circle: circle`, `a: point`, `b: point` |
| outputs | `arc: arc` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The arc of a circle counterclockwise from the ray `c → a` to the ray
`c → b` (GeoGebra `CircleArc(c, A, B)`). The points need not lie on the
circle; only their directions count.
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    |a − c|, |b − c|    each ≤ tol.decide → "coincident_points"
    a0 = angle(a − c),  β = angle(b − c),  a1 = β if β ≥ a0 else β + 2π
    arc = {c, r: circle.r, a0, a1}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `|a − c|`, `|b − c|` | `tol.decide` |

## Checks

- `ends`: distances from the ends to the rays `c → a`, `c → b`; `|c − circle.c|`, `|r − circle.r|`
