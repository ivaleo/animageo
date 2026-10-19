# `conic.five_points` — conic through five points

Registry 1.6 · group `conic` · status `beta` · classification in [conic.equation](conic.equation.md#classification).

| | |
|---|---|
| inputs | `a`, `b`, `c`, `d`, `e`: `point` |
| outputs | `conic: conic` |
| undefined | `coincident_points`, `degenerate_conic`, `upstream` |
| checks | `on_curve` |

## Value

    (x0, y0) = (Σx/5, Σy/5) in the order a … e;  s = max |P − (x0, y0)|
    s ≤ tol.decide (length)                    → "coincident_points"
    rows: [x'², x'y', y'², x', y', 1] with x' = (x − x0)/s, y' = (y − y0)/s
    Gaussian elimination with full pivoting, k = 0 … 4:
        the pivot is the first largest |entry| of rows k…4, columns k…5 in row-major order (strict >);
        swap it to (k, k) (rows and columns, the column permutation is kept)
        k = 4, or a pivot 0: decision degenerate on the pivot; ≤ tol.decide (scalar) → "degenerate_conic"
        eliminate below: row_i −= (row_i[k] / row_k[k])·row_k   (skipped when the factor is 0)
    the null vector: z5 = 1, z_k = −Σ_{j>k} row_k[j]·z_j / row_k[k] (k = 4 … 0), unpermuted → (A … F)
    → from_coeffs(A … F; x0, y0, s)

Four collinear points or two coincident points leave a pencil (the last
pivot); three collinear points give a pair of lines (`det`): both are
`degenerate_conic`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `s` | `tol.decide` (length) |
| `degenerate` (noise) | the fifth pivot | `tol.decide` (scalar) |
| then those of [Classification](conic.equation.md#classification) | | |

## Checks

`on_curve` — the largest focal residual of the five points: ellipse
`| |X − F1| + |X − F2| − 2a |`, hyperbola `| ||X − F1| − |X − F2|| − 2a |`,
parabola `| |X − F| − (distance to the directrix) |`.
