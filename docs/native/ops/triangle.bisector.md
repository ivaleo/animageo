# `triangle.bisector` — angle bisector of a triangle (a segment)

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertex: point`, `side: segment` |
| outputs | `bisector: segment`, `foot: point` |
| undefined | `coincident_points`, `collinear_points`, `upstream` (all slots) |
| checks | `equal_angles`, `on_side` |
| orientation | `vertex_to_foot` |

The bisector of the angle `B V C` (`B = side.a`, `C = side.b`) from the vertex
to its foot `L` on `BC`.

## Value

    lb = |V − B|,  lc = |V − C|
    lb ≤ tol.decide or lc ≤ tol.decide        → all slots "coincident_points" (decided in this order)
    collinearity as circle.three_points with a = V, b = B, c = C:
      la = |B − C|,  Lmax = max(la, lb, lc)
      cr = (B_x − V_x)(C_y − V_y) − (B_y − V_y)(C_x − V_x),  h = |cr| / Lmax
      Lmax ≤ tol.decide or h ≤ tol.decide     → all slots "collinear_points"
    w = lb + lc
    L_x = (lc·B_x + lb·C_x) / w,  L_y = (lc·B_y + lb·C_y) / w
    bisector = {a: V, b: L, length: |L − V|}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `lb`, `lc` | `tol.decide` |
| `collinear_points` | `Lmax`, `h` | `tol.decide` |

## Checks

- `equal_angles`: `|m(∠B V L) − m(∠L V C)|·S` (convex measures of `kernel.md` §5)
- `on_side`: the distance from `L` to the segment `BC`
