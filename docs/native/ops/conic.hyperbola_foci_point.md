# `conic.hyperbola_foci_point` — hyperbola by two foci and a point

Registry 1.6 · group `conic` · status `beta` · see [conic.ellipse_foci_point](conic.ellipse_foci_point.md).

| | |
|---|---|
| inputs | `f1: point`, `f2: point`, `through: point` |
| outputs | `conic: conic` (kind `hyperbola`) |
| undefined | `coincident_points`, `degenerate_conic`, `upstream` |
| checks | `on_curve`, `foci` |

## Value

`{kind: "hyperbola", c, axis, a, b}`: `a` the transverse semi-axis along
`axis`, `b` the conjugate one; both branches.

    d    = f2 − f1;  dist = hypot(d)
    if dist ≤ tol.decide:          → undefined "coincident_points"
    half = dist / 2
    a    = | |through − f1| − |through − f2| | / 2
    if a ≤ tol.decide or half − a ≤ tol.decide:   → undefined "degenerate_conic"
          (through on the perpendicular bisector, or on the focal line outside the segment)
    b    = sqrt((half − a)·(half + a))
    c    = (f1 + f2) / 2;  axis = d / dist

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `dist` | `tol.decide` (length) |
| `degenerate` (noise) | `a`, then `half − a` | `tol.decide` (length) |

## Checks

- `on_curve` — `| ||X − F1| − |X − F2|| − 2a |` at `through`, the foci
  `c ∓ √(a² + b²)·axis` of the value.
- `foci` — the larger distance between the foci of the value and `f1`, `f2`.
