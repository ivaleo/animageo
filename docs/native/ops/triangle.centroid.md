# `triangle.centroid` — point of intersection of the medians

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `point: point` |
| undefined | `upstream` |
| checks | `medians` |

## Value

    G_x = ((a_x + b_x) + c_x) / 3,  G_y = ((a_y + b_y) + c_y) / 3
    a degenerate triangle still gives the point (as GeoGebra)

## Degeneracy decisions

None.

## Checks

- `medians`: the larger distance from `G` to the lines `a – mid(b, c)` and `b – mid(c, a)` (a degenerate triangle: `|G − (a + b + c)/3|`)
