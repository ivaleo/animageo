# `line.external_bisector` — external bisector of an angle

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `vertex: point`, `b: point` |
| outputs | `line: line` |
| orientation | `into_angle_ccw90` |
| undefined | `coincident_points`, `upstream` |
| checks | `through_vertex`, `equal_angles` |

The bisector of the angle adjacent to `a vertex b`: the direction of
`line.angle_bisector` (all its steps and decisions) turned by +90°.

## Value

    d = direction of line.angle_bisector(a, vertex, b)     (coincident_points)
    line = line through vertex with (−dy, dx)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `|a − vertex|`, `|b − vertex|` | `tol.decide` |
| `straight_angle` | `ua × ub` (noise) | `tol.scalar` |

## Checks

- `through_vertex`: distance from the vertex to the line
- `equal_angles`: `|ua·e + ub·e|·S`
