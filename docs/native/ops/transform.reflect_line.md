# `transform.reflect_line` — reflection in a line

Registry 1.4 · group `transform` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `obj: transformable`, `line: linear` |
| outputs | `image: transformable` (the type of `obj`), `side.1…side.N: segment` (N from `obj`), `vertex.1…vertex.N: point` (N from `obj`) |
| policy | `vertex_index` |
| orientation | `reversed` |
| undefined | `zero_length`, `upstream` |
| checks | `image` |

The image `image` has the type of `obj` (record field `like: "obj"`;
family `transformable`: point, segment, ray, line, vector, circle, arc,
sector, polygon). The image of a polygon also gives `side.i` and `vertex.k`
(policy `vertex_index`, as many as `obj` has vertices — kernel.md §4):
`vertex.k` is the image of vertex `k`, the orientation is not normalised
and the area stays unsigned. Arcs and sectors stay counterclockwise. The mirror is the carrier of `line` (a segment is not cut). The map reverses orientation: a polygon comes out clockwise, an arc swaps its ends.

## Value

    carrier (p0, d) of line (zero_length as in intersect.line_line);  β = atan2(d.y, d.x)
    f(P) = p0 + 2((P − p0) · d)·d − (P − p0)
    g(u) = 2(u · d)·d − u,  s = 1,  τ(θ) = 2β − θ,  reverses
    point:            image = f(P)
    segment, vector:  a' = f(a), b' = f(b), length = hypot(b' − a')
    ray:              origin' = f(origin), dir' = unit(g(dir))
    line:             q = f(p), d = unit(g(dir)), image = line through q along d
                      (p' = q − (q · d)·d, the projection of the origin)
    circle:           c' = f(c), r' = s·r
    arc, sector:      c' = f(c), r' = s·r, sweep = a1 − a0,
                      a0' = reduce(τ(a1)) when the map reverses, else reduce(τ(a0)),
                      a1' = a0' + sweep
    polygon:          V'[k] = f(V[k]) in order; image, side.i as polygon.by_points
                      (area unsigned); vertex.k = V'[k]

    unit(w) = w / hypot(w),  reduce(t) = t − 2π·floor(t / 2π) (2π → 0)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | segment length | `tol.decide` |

## Checks

- `image`: the largest distance between the images of the defining points of `obj` (computed apart from the op) and those of the image; a line: the images of `p` and `p + dir` to the image line and `|unit(f(p + dir) − f(p)) − dir'|·S`; an arc or a sector: centre, radius, both ends (swapped after a reflection in a line) and the sweep; a polygon: the image vertices, `vertex.k` and the ends of `side.i`
