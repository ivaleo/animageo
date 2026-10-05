# `point.at_distance` — point at a distance along a ray

Registry 1.4 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `distance: number` |
| outputs | `point: point`, `segment: segment` |
| orientation | `a_to_b` |
| undefined | `coincident_points`, `upstream` |
| checks | `distance` |

The point at the signed distance `distance` from `a` along the ray `ab`,
and the segment from `a` to it.

## Value

    v = b − a,  L = hypot(v)
    if L ≤ tol.decide:      → both slots "coincident_points"
    u = v / L,  d = distance.value
    point = a + d·u
    segment = {a: a, b: point, length: |d|}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |

## Checks

- `distance`: the larger of `| |P − a| − |d| |` and the distance from `P` to the line `ab`
