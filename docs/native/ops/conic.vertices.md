# `conic.vertices` — vertices of a conic

Registry 1.6 · group `conic` · status `beta` · branch policy `conic_axis_order`.

| | |
|---|---|
| inputs | `conic: conic` |
| outputs | `first`, `second`, `third`, `fourth`: `point` |
| undefined | `branch_absent`, `upstream` |
| checks | `on_curve` |

    ellipse:   first = c − a·axis, second = c + a·axis, third = c − b·n, fourth = c + b·n
    hyperbola: first = c − a·axis, second = c + a·axis; third, fourth "branch_absent"
    parabola:  first = vertex; second, third, fourth "branch_absent"

`n` is the axis turned by +90°. `on_curve` measures the focal residual of
the defined vertices and runs when slots are absent.
