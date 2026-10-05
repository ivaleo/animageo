# `triangle.incenter` — centre of the inscribed circle

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `point: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `equidistant_sides` |

## Value

    the centre of circle.incircle on the same inputs (the same function, bit for bit):
    La = |b − c|, Lb = |c − a|, Lc = |a − b|; collinearity as circle.incircle
    p = (La + Lb) + Lc;  I_x = ((La·a_x + Lb·b_x) + Lc·c_x) / p   (and y)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` of circle.incircle | `tol.decide` |

## Checks

- `equidistant_sides`: max minus min of the distances from the point to the lines `bc`, `ca`, `ab`
