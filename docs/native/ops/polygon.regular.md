# `polygon.regular` — regular polygon on a side

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| params | `n` |
| outputs | `polygon: polygon`, `side.1…side.N: segment` (N from `n`), `vertex.1…vertex.N: point` (N from `n`) |
| policy | `vertex_index` |
| orientation | `ccw` |
| undefined | `coincident_points`, `invalid_parameter`, `upstream` |
| checks | `regular` |

The regular `n`-gon with the side `ab`, counterclockwise (the centre lies to
the left of `a → b`, as the classic `polygon_ppi`), its sides and vertices
(policy `vertex_index`; `vertex.1 = a`, `vertex.2 = b`). The number of
`side`/`vertex` slots is `n` when `n` is a whole number in `[1, 100]`
(`registry.repeat_count`), else none; `n` outside `3..100` is
`invalid_parameter`. GeoGebra `Polygon(A, B, n)`.

## Value

    n not whole, n < 3 or n > 100:   → all slots "invalid_parameter"
    v = b − a,  L = hypot(v)
    if L ≤ tol.decide:               → all slots "coincident_points"
    h = L / (2·tan(π/n)),  O = (a + b)/2 + h·(−vy, vx)/L
    vertex.1 = a,  vertex.2 = b,  vertex.k = O + R((k − 1)·2π/n)·(a − O)   (k ≥ 3)
    side.i = vertex.i → vertex.(i+1),  side.n = vertex.n → vertex.1
    polygon = {vertices, area}  (area as polygon.by_points)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` |

## Checks

- `regular`: the largest deviation of the side lengths from `|b − a|`, of the vertex distances from the centre, and of the sides and vertices from the polygon
