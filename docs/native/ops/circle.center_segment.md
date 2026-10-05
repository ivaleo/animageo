# `circle.center_segment` — circle with a segment as radius

Registry 1.4 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `radius: segment` |
| outputs | `circle: circle` |
| undefined | `nonpositive_radius`, `upstream` |
| checks | `matches` |

The circle with centre `center` and the length of a segment as radius.
GeoGebra `Circle(A, s)`.

## Value

    r = radius.length
    if r ≤ tol.decide:      → "nonpositive_radius"
    circle = {c: center, r}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `nonpositive_radius` | `r` | `tol.decide` |

## Checks

- `matches`: `max(|c − center|, |r − radius.length|)`
