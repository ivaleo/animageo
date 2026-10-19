# `conic.foci` — foci of a conic

Registry 1.6 · group `conic` · status `beta` · branch policy `conic_axis_order`.

| | |
|---|---|
| inputs | `conic: conic` |
| outputs | `first: point`, `second: point` |
| undefined | `branch_absent`, `upstream` |
| checks | `focal` |

    ellipse:   e = sqrt((a − b)(a + b));  first = c − e·axis, second = c + e·axis   (a circle: c twice)
    hyperbola: e = hypot(a, b);           first = c − e·axis, second = c + e·axis
    parabola:  first = vertex + (p/2)·axis, second "branch_absent"

An ellipse or a hyperbola by its foci gives them back in their order
(`axis` runs from `f1` to `f2`).

## Checks

`focal` — each defined focus lies on the axis line (`|(F − c)×axis|`) and at
`a` from `c + b·n` (ellipse), at `√(a² + b²)` from `c` (hyperbola), at `p/2`
from the vertex (parabola). The check runs when `second` is absent.
