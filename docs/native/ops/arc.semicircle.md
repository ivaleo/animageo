# `arc.semicircle` — semicircle on a segment

Registry 1.4 · group `arc` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `arc: arc` |
| orientation | `ccw` |
| undefined | `coincident_points`, `upstream` |
| checks | `ends` |

The half circle on the diameter `ab`, to the left of `a → b`
(counterclockwise from `b` to `a`, as the classic `semicircle_pp`).
`angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)` (`_types.json →
angles`). The value is stored counterclockwise from `a0` to `a1`, `a0` in
`[0, 2π)`, `a1` in `[a0, a0 + 2π]`.

## Value

    L = |b − a|
    if L ≤ tol.decide:      → "coincident_points"
    c = (a + b) / 2,  r = L / 2,  a0 = angle(b − c),  a1 = a0 + π

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |

## Checks

- `ends`: `max(|end − a|, |start − b|, |r − L/2|)`
