# `triangle.circumcenter` — centre of the circumscribed circle

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `point: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `equidistant` |

## Value

    the centre of circle.three_points on the same inputs (vertex a first; the same
    function circumcenter(a, b, c), bit for bit)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax`, `h` of circle.three_points | `tol.decide` |

## Checks

- `equidistant`: max minus min of `|P − a|`, `|P − b|`, `|P − c|`
