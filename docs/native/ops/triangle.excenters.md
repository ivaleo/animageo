# `triangle.excenters` — centre of the excircle opposite a

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `center: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `equidistant_lines` |

## Value

    the centre of circle.excircle on the same inputs (the same function, bit for bit):
    La = |b − c|, Lb = |c − a|, Lc = |a − b|; collinearity as circle.incircle
    w = (−La + Lb) + Lc;  x = ((−La·a_x + Lb·b_x) + Lc·c_x) / w   (and y)
    one output: the three excentres are three operations (the argument order picks the vertex)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` of circle.excircle | `tol.decide` |

## Checks

- `equidistant_lines`: max minus min of the distances from the centre to the lines `bc`, `ca`, `ab`
