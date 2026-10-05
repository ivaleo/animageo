# `polygon.regular_center` — regular polygon by centre and vertex

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `center: point`, `a: point` |
| params | `n` |
| outputs | `polygon: polygon`, `side.1…side.N: segment` (N from `n`), `vertex.1…vertex.N: point` (N from `n`) |
| policy | `vertex_index` |
| orientation | `ccw` |
| undefined | `coincident_points`, `invalid_parameter`, `upstream` |
| checks | `regular` |

The regular `n`-gon with centre `center` and vertex `a`, counterclockwise
(`vertex.1 = a`). Slots and `n` as `polygon.regular`.

## Value

    n not whole, n < 3 or n > 100:   → all slots "invalid_parameter"
    w = a − center
    if |w| ≤ tol.decide:             → all slots "coincident_points"
    vertex.1 = a,  vertex.k = center + R((k − 1)·2π/n)·w
    sides and polygon as polygon.regular

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `|w|` | `tol.decide` |

## Checks

- `regular`: as `polygon.regular`, the radius being `|a − center|`
