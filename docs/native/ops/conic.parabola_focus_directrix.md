# `conic.parabola_focus_directrix` — parabola by its focus and directrix

Registry 1.6 · group `conic` · status `beta` · see [conic.ellipse_foci_point](conic.ellipse_foci_point.md).

| | |
|---|---|
| inputs | `focus: point`, `directrix: linear` (`line` \| `segment` \| `ray`) |
| outputs | `conic: conic` (kind `parabola`) |
| undefined | `zero_length`, `degenerate_conic`, `upstream` |
| checks | `focus_directrix` |

## Value

`{kind: "parabola", vertex: [x, y], axis: [ux, uy], p}`: `axis` from the
vertex towards the focus, `p` the distance from the focus to the directrix
(`v² = 2p·u` with `u` along `axis` from the vertex, `v` along `n`). The
directrix is the whole carrier line of `directrix` (the carrier of
[intersect.line_line](intersect.line_line.md); a zero-length segment is
`zero_length`).

    side = (F − p)×dir = (Fx − px)·diry − (Fy − py)·dirx      (+: F to the right of dir)
    if |side| ≤ tol.decide:   → undefined "degenerate_conic"   (the focus on the directrix)
    p    = |side|
    axis = (diry, −dirx) if side > 0 else (−diry, dirx)      (the normal from the directrix to F)
    vertex = F − (p/2)·axis

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment) | `L` | `tol.decide` (length) |
| `degenerate` (noise) | `side` | `tol.decide` (length) |

## Checks

`focus_directrix` — the larger of `|vertex + (p/2)·axis − focus|`, the
distance of `vertex − (p/2)·axis` to the carrier and `p·|axis·dir|`.
