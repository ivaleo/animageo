# `intersect.line_circle` — intersection of a linear object and a circle

Registry 1.1 · group `intersect` · branch policy `line_param_order` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `line: linear` (`line` \| `segment` \| `ray`), `circle: circular` (`circle`) |
| outputs | `first: point`, `second: point` |
| undefined | `no_intersection`, `outside_part`, `zero_length`, `upstream` |
| checks | `on_both` |

## Slots

`first` and `second` are the two solutions on the carrier line of `line`,
ordered by the parameter `t` along its orientation (`dir` of a line, `b − a`
of a segment, `dir` of a ray): `first` has the smaller `t`. The slots are
fixed on the carrier first; the part filter of a segment or a ray then
works per slot, so when the first solution leaves a segment the second one
stays in `second` (it never becomes `first`). A tangency is a double root:
both slots hold the touching point with `detail: {"multiplicity": 2}`.

## Value

The carrier `(p, dir, L)` of `line` is the one of
[intersect.line_line](intersect.line_line.md) (a zero-length segment gives
`zero_length` in both slots); `c = (cx, cy)`, `r` are the centre and radius.

    wx = cx − px
    wy = cy − py
    m  = wx·dirx + wy·diry               (parameter of the foot of the centre)
    h  = |wx·diry − wy·dirx|             (distance from the centre to the carrier)
    δ  = h − r
    if δ > tol.decide:                   → both slots undefined "no_intersection"
    if |δ| ≤ tol.decide:                 → t1 = t2 = m, detail {"multiplicity": 2} on both
    else:
        k  = sqrt((r − h)·(r + h))
        t1 = m − k                       (first)
        t2 = m + k                       (second)
    for each slot (t = t1, t2):
        segment: if t < −tol.decide or t > L + tol.decide → undefined "outside_part", detail {"slot": "line"}
        ray:     if t < −tol.decide                        → undefined "outside_part", detail {"slot": "line"}
        point = {x: px + t·dirx, y: py + t·diry}

A slot outside the part loses its `multiplicity` detail. An intersection
exactly at a segment end or a ray origin is inside the part.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment input) | `L` | `tol.decide` (length) |
| `tangent` | `δ` | `tol.decide` (length) |
| `outside_part` (segment: per slot) | `t` and `t − L` | `tol.decide` (length) |
| `outside_part` (ray: per slot) | `t` | `tol.decide` (length) |

`tangent` is a noise decision for the fixture generator: `|δ| ≤ tol.decide /
1000` counts as exactly tangent (kernel.md §6).

## Checks

- `on_both`: the largest of, over both slots, the distance to the carrier
  line `|(x − px)·diry − (y − py)·dirx|` and the distance to the circle
  `| hypot(x − cx, y − cy) − r |`.
