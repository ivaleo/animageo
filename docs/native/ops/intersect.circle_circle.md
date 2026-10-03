# `intersect.circle_circle` — intersection of two circles

Registry 1.1 · group `intersect` · branch policy `circle_side` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: circular`, `second: circular` (`circle`) |
| outputs | `first: point`, `second: point` |
| undefined | `no_intersection`, `concentric`, `coincident`, `upstream` |
| checks | `on_both` |

## Slots

`first` lies to the left of the directed segment from the centre `c1` of
`first` to the centre `c2` of `second` (`(c2 − c1) × (X − c1) > 0`),
`second` to the right; swapping the inputs swaps the slots. A tangency is a
double root: both slots hold the touching point with
`detail: {"multiplicity": 2}`.

## Value

    ex = c2x − c1x
    ey = c2y − c1y
    d  = hypot(ex, ey)
    if d ≤ tol.decide:
        |r1 − r2| ≤ tol.decide → both slots undefined "coincident", else "concentric"
    ux = ex / d
    uy = ey / d
    a  = (d·d + r1·r1 − r2·r2) / (2·d)
    e1 = d − (r1 + r2)                   (> 0: apart)
    e2 = |r1 − r2| − d                   (> 0: one inside the other)
    if e1 > tol.decide or e2 > tol.decide: → both slots undefined "no_intersection"
    fx = c1x + a·ux
    fy = c1y + a·uy
    if |e1| ≤ tol.decide or |e2| ≤ tol.decide:
        → both slots {fx, fy}, detail {"multiplicity": 2}
    h  = sqrt(max(0, (r1 − a)·(r1 + a)))
    nx = −uy
    ny = ux
    first  = {x: fx + h·nx, y: fy + h·ny}
    second = {x: fx − h·nx, y: fy − h·ny}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `concentric` | `d` | `tol.decide` (length) |
| `coincident` (only when concentric) | `|r1 − r2|` | `tol.decide` (length) |
| `tangent` | `e1` and `e2` | `tol.decide` (length) |

`tangent` is a noise decision for the fixture generator (kernel.md §6).

## Checks

- `on_both`: the largest of `| hypot(x − c1x, y − c1y) − r1 |` and
  `| hypot(x − c2x, y − c2y) − r2 |` over both slots.
