# `conic.ellipse_foci_point` — ellipse by two foci and a point

Registry 1.6 · group `conic` · status `beta` · see [kernel.md §14](../kernel.md).

| | |
|---|---|
| inputs | `f1: point`, `f2: point`, `through: point` |
| outputs | `conic: conic` (kind `ellipse`) |
| undefined | `degenerate_conic`, `upstream` |
| checks | `on_curve`, `foci` |

## Value

The type `conic` (`ops/v1/_types.json`): an ellipse is
`{kind: "ellipse", c: [x, y], axis: [ux, uy], a, b}`, `a ≥ b > 0`, `a`
along the unit `axis`; a circle is an ellipse with `a == b` and
`axis = [1, 0]`. `n = (−uy, ux)` is the axis turned by +90°.

    d    = f2 − f1;  dist = hypot(d)
    half = dist / 2
    a    = (|through − f1| + |through − f2|) / 2
    if a − half ≤ tol.decide:   → undefined "degenerate_conic"   (through on the segment f1f2, or all three coincide)
    c    = (f1 + f2) / 2
    if dist ≤ tol.decide:       → {kind: ellipse, c, axis: [1, 0], a, b: a}   (a circle)
    b    = sqrt((a − half)·(a + half))
    axis = d / dist             (from f1 towards f2)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `degenerate` (noise) | `a − half` | `tol.decide` (length) |
| `circle` | `dist` | `tol.decide` (length) |

## Checks

- `on_curve` — `| |X − F1| + |X − F2| − 2a |` at `through`, the foci taken
  from the value (`c ∓ √((a − b)(a + b))·axis`).
- `foci` — the larger distance between the foci of the value and `f1`, `f2`.
