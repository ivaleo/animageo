# `polygon.centroid` — centre of mass of a polygon

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `polygon: polygon` |
| outputs | `centroid: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `balance` |

The centre of mass of the polygon region (fan triangulation from the first
vertex, signed areas, so any simple polygon works). A polygon of zero area
is `collinear_points` (the classic `centroid_P` takes the vertex mean — a
recorded difference).

## Value

    for i in 1 .. n − 2:  u = V[i] − V[0],  w = V[i+1] − V[0],  cr_i = u × w
    A2 = Σ cr_i,  P = perimeter
    if |A2| / P ≤ tol.decide:   → "collinear_points"
    centroid = V[0] + Σ (u + w)·cr_i / (3·A2)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `|A2| / P` | `tol.decide` |

## Checks

- `balance`: `|Σ cr_i·(g_i − centroid)| / |A2|`, `g_i` the centre of triangle `i`
