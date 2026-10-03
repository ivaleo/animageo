# `line.parallel` — line through a point parallel to a linear object

Registry 1.2 · group `line` · orientation `carrier_dir` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `base: linear` (`line` \| `segment` \| `ray`) |
| outputs | `line: line` |
| undefined | `zero_length`, `upstream` |
| checks | `through_point`, `parallel` |

## Value

The carrier `(p, dir, L)` of `base` is the one of
[intersect.line_line](intersect.line_line.md) (a zero-length segment gives
`zero_length`). With `q` the input point:

    dirx, diry = carrier dir
    k = qx·dirx + qy·diry
    line = {p: [qx − k·dirx, qy − k·diry], dir: [dirx, diry]}

`dir` is the carrier direction (`dir` of a line or a ray, `(b − a)/L` of a
segment); `p` is the projection of the origin, as in
[line.by_points](line.by_points.md). A point on `base` gives `base`'s
carrier line.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment input) | `L` | `tol.decide` (length) |

## Checks

Distance from a point `(x, y)` to the line: `| (x − px)·diry − (y − py)·dirx |`.

- `through_point`: the distance of `q`
- `parallel`: `| dirx·cdiry − diry·cdirx | · S`, `cdir` the carrier direction
  of `base`
