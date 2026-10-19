# `conic.axes` — axes of a conic

Registry 1.6 · group `conic` · status `beta` · branch policy `conic_axis_order`.

| | |
|---|---|
| inputs | `conic: conic` |
| outputs | `focal: line`, `conjugate: line` |
| undefined | `branch_absent`, `upstream` |
| checks | — |

    focal     = the line through c (a parabola: the vertex) with dir = axis
    conjugate = the line through c with dir = n (the axis turned by +90°); a parabola: "branch_absent"

A line value is `{p, dir}` with `p` the projection of the origin
(`k = q·dir`, `p = q − k·dir`, as `line.by_points`).
