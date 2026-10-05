# `line.tangents_from_point` — tangents from a point to a circle

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `circle: circle` |
| outputs | `tangent.1: line`, `tangent.2: line`, `touch.1: point`, `touch.2: point` |
| policy | `tangent_side` |
| orientation | `point_to_touch` |
| undefined | `point_inside`, `upstream` |
| checks | `tangent`, `through_point` |

Both tangents from a point to a circle and their touch points (policy
`tangent_side`): `tangent.1`/`touch.1` lie to the left of the ray from the
point to the centre. Lines are oriented from the point to the touch point.
A point on the circle fills both slots with the tangent at it
(`multiplicity: 2`), the directions continuous with the outside case. The
classic `tangent_pc` returns `[right, left]` (a note for the L5 importer).

## Value

    w = P − c,  d² = w·w,  d = √d²
    if d − r < −tol.decide:         → all slots "point_inside"
    if |d − r| ≤ tol.decide:
        u = w / d;  touch.1 = touch.2 = P
        tangent.1 = line through P with (uy, −ux);  tangent.2 = with (−uy, ux)
    else:
        h = √((d − r)(d + r)),  k1 = r²/d²,  k2 = r·h/d²
        T1 = c + k1·w − k2·rot(w),  T2 = c + k1·w + k2·rot(w)      rot(w) = (−wy, wx)
        tangent.i = line through P with (Ti − P) / |Ti − P|

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `point_inside` | `d − r` | `tol.decide` |

## Checks

- `tangent`: `| dist(c, tangent.i) − r |` and `| |touch.i − c| − r |`
- `through_point`: distance from `P` to `tangent.i`
