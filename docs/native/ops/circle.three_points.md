# `circle.three_points` — circle through three points

Registry 1.2 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `circle: circle`, `center: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `through_all` |

`center` is the centre of the circle as a separate point output (GeoGebra
needs `Center(c)` for it); a document may bind only `circle`.

## Value

    La = hypot(bx − cx, by − cy)
    Lb = hypot(cx − ax, cy − ay)
    Lc = hypot(ax − bx, ay − by)
    Lmax = max(La, Lb, Lc)
    if Lmax ≤ tol.decide:          → both slots undefined "collinear_points"
    bx' = bx − ax,  by' = by − ay
    cx' = cx − ax,  cy' = cy − ay
    cr = bx'·cy' − by'·cx'
    h  = |cr| / Lmax                  (distance from the third point to the longest side)
    if h ≤ tol.decide:             → both slots undefined "collinear_points"
    b2 = bx'² + by'²                  (bx'·bx' + by'·by')
    c2 = cx'² + cy'²
    D  = 2·cr
    ux = (cy'·b2 − by'·c2) / D
    uy = (bx'·c2 − cx'·b2) / D
    circle = {c: [ax + ux, ay + uy], r: hypot(ux, uy)}
    center = {x: ax + ux, y: ay + uy}

Two coincident points with a third one apart are `collinear_points` (`h =
0`); so are three coincident points.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax` | `tol.decide` (length) |
| `collinear_points` | `h` | `tol.decide` (length) |

## Checks

- `through_all`: the largest of `| hypot(P − c) − r |` over `P = a, b, c`
  and, when `center` is bound, `hypot(center − c)`
