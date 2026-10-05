# `angle.between_lines` — angle between two lines

Registry 1.4 · group `angle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: linear`, `second: linear` |
| outputs | `angle: angle` |
| orientation | `convex` |
| undefined | `zero_length`, `parallel`, `coincident`, `upstream` |
| checks | `sides` |

The convex angle between the directions `d1`, `d2` of two linear inputs
(their carriers; a segment or a ray is not cut), `size` in `(0, π)`, at the
intersection of the carriers. It runs counterclockwise from the direction
that lies clockwise of the other: from `d1` when `d1 × d2 > 0`, else from
`d2`. `angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)`; a value
`{vertex, a0, a1, size}` has `a1 = a0 + size` (`_types.json → angles`).

## Value

    c1, c2 = carriers (zero_length as in intersect.line_line)
    cross = d1 × d2
    if |cross| ≤ tol.scalar:
        dist = |(p2 − p1) × d1|
        → "coincident" if dist ≤ tol.decide else "parallel"
    t = ((p2 − p1) × d2) / cross,  vertex = p1 + t·d1
    size = angle(|cross|, d1 · d2)          (atan2(|cross|, d1 · d2))
    u = d1 if cross > 0 else d2
    angle = {vertex, a0: angle(u), a1: a0 + size, size}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | segment length | `tol.decide` |
| `parallel` | `cross` | `tol.scalar` |
| `coincident` | `dist` | `tol.decide` |
| `angle_wrap` | `u.y` when `u.x > 0` | `tol.scalar` |

## Checks

- `sides`: `max(dist(vertex, carrier 1), dist(vertex, carrier 2), min(|u(a0) − d1| + |u(a1) − d2|, |u(a0) − d2| + |u(a1) − d1|)·S)`, `u(φ) = (cos φ, sin φ)`
