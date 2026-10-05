# `triangle.orthocenter` — point of intersection of the altitudes

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `point: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `perpendicular` |

## Value

    O = the centre of circle.three_points (same function; collinear_points from it)
    H_x = ((a_x + b_x) + c_x) − 2·O_x,  H_y = ((a_y + b_y) + c_y) − 2·O_y     (Euler)
    in a right triangle H is the right-angle vertex (defined)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` of circle.three_points | `tol.decide` |

## Checks

- `perpendicular`: max over the vertices of `|(H − a)·(c − b)| / |c − b|` (and cyclically)
