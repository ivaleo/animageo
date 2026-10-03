# `line.angle_bisector` — bisector of the angle a–vertex–b

Registry 1.2 · group `line` · orientation `into_angle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `vertex: point`, `b: point` |
| outputs | `line: line` |
| undefined | `coincident_points`, `upstream` |
| checks | `through_vertex`, `equal_angles` |

The bisector of the angle `∠a·vertex·b` (at most 180°), not of the
adjacent angle; `dir` points into the angle. GeoGebra
`AngleBisector(A, B, C)`.

## Value

    ax' = ax − vx,  ay' = ay − vy,  La = hypot(ax', ay')
    bx' = bx − vx,  by' = by − vy,  Lb = hypot(bx', by')
    if La ≤ tol.decide or Lb ≤ tol.decide:   → undefined "coincident_points"
    ua = (ax'/La, ay'/La)
    ub = (bx'/Lb, by'/Lb)
    q  = uax·ubx + uay·uby                   (cos of the angle)
    if q ≥ 0:                                 acute or right
        s = (uax + ubx, uay + uby)
        n = hypot(sx, sy)
        dir = (sx / n, sy / n)
    else:                                     obtuse or straight
        w  = (ubx − uax, uby − uay)
        n  = hypot(wx, wy)
        cr = uax·uby − uay·ubx
        σ  = −1 if cr < −tol.scalar else 1
        dir = (σ·wy / n, −σ·wx / n)           (w turned 90° clockwise when σ = 1)
    k = vx·dirx + vy·diry
    line = {p: [vx − k·dirx, vy − k·diry], dir}

Both branches give the same direction for a non-degenerate angle; the
second one avoids `s ≈ 0` near a straight angle. A straight angle
(`|cr| ≤ tol.scalar`, `q < 0`) takes `σ = 1`: `dir` is `ua` turned 90°
counter-clockwise. Swapping `a` and `b` gives the same line.

## Path frame

The origin of the path parameter is `vertex` (kernel.md §5.5).

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` (twice) | `La`, `Lb` | `tol.decide` (length) |
| `straight_angle` (only when `q < 0`) | `cr` | `tol.decide` (scalar) |

`straight_angle` is a noise decision for the fixture generator (kernel.md §6).

## Checks

- `through_vertex`: the distance of `vertex` to the line,
  `| (vx − px)·diry − (vy − py)·dirx |`
- `equal_angles`: `| ua·dir − ub·dir | · S` with `ua`, `ub` recomputed from
  the inputs
