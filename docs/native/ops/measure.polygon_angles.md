# `measure.polygon_angles` — interior angles of a polygon

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `polygon: polygon` |
| outputs | `angle.1…angle.N: angle` (N from `polygon`) |
| policy | `vertex_index` |
| orientation | `interior` |
| undefined | `collinear_points`, `coincident_points`, `upstream` |
| checks | `interior` |

The interior angle at every vertex, `angle.k` at vertex `k` (policy
`vertex_index`; the slots repeat by the vertex count of `polygon`, read from
its producer — kernel.md §4). A reflex vertex of a concave polygon gives a
size above `π`. `angle(w)` is `atan2(wy, wx)` normalised to `[0, 2π)`; a value
`{vertex, a0, a1, size}` has `a1 = a0 + size` (`_types.json → angles`).

## Value

    V = polygon.vertices,  n = |V|
    A2 = Σ (V[i].x·V[i+1].y − V[i+1].x·V[i].y)    (i + 1 mod n, in order)
    P  = Σ hypot(V[i+1] − V[i])
    h  = |A2| / P  (0 when P = 0)
    if h ≤ tol.decide:                       → "collinear_points" (every slot)
    for k = 1 … n:  v = V[k], prev = V[k − 1], next = V[k + 1]
        (f, g) = (next, prev) if A2 > 0 else (prev, next)
        u, w = unit sides from v to f and to g  (a side ≤ tol.decide → "coincident_points" for this slot)
        size = angle(u × w, u · w)
        angle.k = {vertex: v, a0: angle(u), a1: a0 + size, size}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `h` | `tol.decide` |
| `coincident_points` | side length | `tol.decide` |
| `angle_wrap` | `u.y` when `u.x > 0` | `tol.scalar` |
| `zero_angle` | `u × w` when `u · w > 0` | `tol.scalar` |

## Checks

- `interior`: `max over k of (|vertex − V[k]|, |wrap(a0 − θ(f − v))|·S, |wrap(a1 − θ(g − v))|·S)`
