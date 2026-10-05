# `angle.between_vectors` — angle from one vector to another (beta)

Registry 1.4 · beta · group `angle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: vector`, `second: vector` |
| outputs | `angle: angle` |
| orientation | `ccw_first_to_second` |
| undefined | `zero_length`, `upstream` |
| checks | `sides` |

Beta. The angle counterclockwise from the vector `first` to the vector
`second`, `size` in `[0, 2π)`, drawn at the start of `first`. `angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)`; a value
`{vertex, a0, a1, size}` has `a1 = a0 + size` (`_types.json → angles`).

## Value

    u = (first.b − first.a) / |…|,  w = (second.b − second.a) / |…|
    if a length ≤ tol.decide:                → "zero_length"
    size = angle(u × w, u · w)               (atan2, normalised)
    angle = {vertex: first.a, a0: angle(u), a1: a0 + size, size}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | vector length | `tol.decide` |
| `zero_angle` | `u × w` when `u · w > 0` | `tol.scalar` |
| `angle_wrap` | `u.y` when `u.x > 0` | `tol.scalar` |

## Checks

- `sides`: `max(|vertex − first.a|, |u(a0) − u|·S, |u(a1) − w|·S)`
