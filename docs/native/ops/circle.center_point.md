# `circle.center_point` — circle with a center through a point

Registry 1.0 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `through: point` |
| outputs | `circle: circle` |
| undefined | `nonpositive_radius`, `upstream` |
| checks | `through_on_circle` |

## Value

    r = hypot(tx − cx, ty − cy)
    if r ≤ tol.decide:            → undefined, reason "nonpositive_radius"
    circle = {c: [cx, cy], r}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `nonpositive_radius` | `r` | `tol.decide` (length) |

## Checks

- `through_on_circle`: `| hypot(tx − cx, ty − cy) − r |`
