# `line.perpendicular` — line through a point perpendicular to a linear object

Registry 1.2 · group `line` · orientation `carrier_dir_ccw90` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `base: linear` (`line` \| `segment` \| `ray`) |
| outputs | `line: line` |
| undefined | `zero_length`, `upstream` |
| checks | `through_point`, `perpendicular` |

## Value

The carrier `(p, cdir, L)` of `base` is the one of
[intersect.line_line](intersect.line_line.md) (a zero-length segment gives
`zero_length`). With `q` the input point:

    dirx = −cdiry
    diry =  cdirx                    (cdir turned 90° counter-clockwise)
    k = qx·dirx + qy·diry
    line = {p: [qx − k·dirx, qy − k·diry], dir: [dirx, diry]}

The point may lie on `base`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment input) | `L` | `tol.decide` (length) |

## Checks

Distance from a point `(x, y)` to the line: `| (x − px)·diry − (y − py)·dirx |`.

- `through_point`: the distance of `q`
- `perpendicular`: `| dirx·cdirx + diry·cdiry | · S`
