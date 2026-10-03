# `circle.center_radius` — circle with a center and a radius

Registry 1.2 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `radius: number` |
| outputs | `circle: circle` |
| undefined | `nonpositive_radius`, `upstream` |
| checks | `matches` |

`radius` is a reference to a `number` element or a number literal
`{"kind": "number", "value": r}` (kernel.md §1); its unit is not checked.

## Value

    r = radius.value
    if r ≤ tol.decide:            → undefined "nonpositive_radius"
    circle = {c: [cx, cy], r}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `nonpositive_radius` | `r` | `tol.decide` (length) |

## Checks

- `matches`: `max(hypot(c − center), | r − radius.value |)`
