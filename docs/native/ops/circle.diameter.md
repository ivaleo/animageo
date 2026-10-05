# `circle.diameter` — circle on a diameter

Registry 1.4 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `circle: circle`, `center: point` |
| undefined | `coincident_points`, `upstream` |
| checks | `through_ends` |

The circle with diameter `ab` and its centre.

## Value

    L = hypot(b − a)
    if L ≤ tol.decide:      → both slots "coincident_points"
    center = (a + b) / 2,  circle = {c: center, r: L / 2}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |

## Checks

- `through_ends`: `max(| |a − c| − r |, | |b − c| − r |)`
