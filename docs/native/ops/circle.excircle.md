# `circle.excircle` — excircle of a triangle

Registry 1.4 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `circle: circle`, `center: point`, `touch: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `tangent_sides` |

The excircle of the triangle `abc` opposite `a` (it touches the side `bc`
and the extensions of `ab`, `ac`), its centre and the touch point on `bc`.
The three excircles are three operations (the argument order picks the
vertex); `triangle.excenters` (L3) repeats this formula and order.

## Value

    La = |b − c|,  Lb = |c − a|,  Lc = |a − b|,  Lmax = max(La, Lb, Lc)
    if Lmax ≤ tol.decide:   → all slots "collinear_points"
    cr = (b − a) × (c − a),  h = |cr| / Lmax
    if h ≤ tol.decide:      → all slots "collinear_points"
    s = −La + Lb + Lc                                  (> 0 for a triangle)
    center = (−La·a + Lb·b + Lc·c) / s
    e = (c − b) / La,  t = (center − b)·e,  touch = b + t·e
    circle = {c: center, r: |center − touch|}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax` | `tol.decide` |
| `collinear_points` | `h` | `tol.decide` |

## Checks

- `tangent_sides`: `max |dist(center, side line) − r|` over the three lines, the distance from `touch` to `bc`, `| |touch − c| − r |` and `|center − c|`
