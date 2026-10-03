# `point.projection` — foot of the perpendicular from a point

Registry 1.2 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `base: linear` (`line` \| `segment` \| `ray`) |
| params | `strict: number` (optional, default `0`) |
| outputs | `foot: point` |
| undefined | `zero_length`, `outside_part`, `invalid_parameter`, `upstream` |
| checks | `on_carrier`, `perpendicular` |

## Param

`strict` is `0` or `1`; any other value gives `invalid_parameter`. With
`strict = 0` (the default, and the GeoGebra `ClosestPoint` of a line) the
foot lies on the carrier line of `base`. With `strict = 1` the foot must lie
on the part itself: a segment or a ray gives `outside_part` when the foot
leaves it; a line ignores `strict`.

## Value

The carrier `(p, dir, L)` of `base` is the one of
[intersect.line_line](intersect.line_line.md) (a zero-length segment gives
`zero_length`).

    if strict ∉ {0, 1}:           → undefined "invalid_parameter"
    t = (x − px)·dirx + (y − py)·diry
    foot = {x: px + t·dirx, y: py + t·diry}
    if strict = 1:
        segment: if t < −tol.decide or t > L + tol.decide → undefined "outside_part", detail {"slot": "base"}
        ray:     if t < −tol.decide                        → undefined "outside_part", detail {"slot": "base"}

`invalid_parameter` is decided before the carrier, so a bad `strict` on a
zero-length segment is `invalid_parameter`. A foot exactly at a segment end
or a ray origin is inside the part.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment input) | `L` | `tol.decide` (length) |
| `outside_part` (`strict = 1`, segment) | `t` and `t − L` | `tol.decide` (length) |
| `outside_part` (`strict = 1`, ray) | `t` | `tol.decide` (length) |

## Checks

- `on_carrier`: the distance from the foot to the carrier line,
  `| (fx − px)·diry − (fy − py)·dirx |`
- `perpendicular`: `| (x − fx)·dirx + (y − fy)·diry |`
