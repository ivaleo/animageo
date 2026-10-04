# `mark.right_angle` — right-angle square

Registry 1.3 · group `mark` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `vertex: point`, `b: point` |
| outputs | `mark: mark` |
| undefined | `coincident_points`, `upstream` |
| checks | `right` |

A mark that the angle `∠a·vertex·b` is right: a small square at the vertex.
The value is `{kind: "right_angle", count: 1}`; a renderer draws the angle
`a–vertex–b` with the right-angle marker (kernel.md §9.3,
`right_angle_marker`).

## Value

The unit sides `ua`, `ub` are the ones of
[angle.by_points](angle.by_points.md).

    if La ≤ tol.decide or Lb ≤ tol.decide:   → undefined "coincident_points"
    mark = {kind: "right_angle", count: 1}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` (twice) | `La`, `Lb` | `tol.decide` (length) |

## Checks

- `right`: `|m(size) − π/2| · S`, where `size` is the size of the angle
  `a–vertex–b` and `m` the convex measure; the orientation does not matter;
  infinite when a side has no length
