# `transform.rotate` — rotation about a point

Registry 1.4 · group `transform` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `obj: transformable`, `angle: number`, `center: point` |
| outputs | `image: transformable` (the type of `obj`), `side.1…side.N: segment` (N from `obj`), `vertex.1…vertex.N: point` (N from `obj`) |
| policy | `vertex_index` |
| orientation | `preserved` |
| undefined | `upstream` |
| checks | `image` |

The image `image` has the type of `obj` (record field `like: "obj"`;
family `transformable`: point, segment, ray, line, vector, circle, arc,
sector, polygon). The image of a polygon also gives `side.i` and `vertex.k`
(policy `vertex_index`, as many as `obj` has vertices — kernel.md §4):
`vertex.k` is the image of vertex `k`, the orientation is not normalised
and the area stays unsigned. Arcs and sectors stay counterclockwise. The angle is a number in radians, counterclockwise for a positive value.

## Value

    α = angle.value,  co = cos α,  si = sin α,  c = center
    f(P) = c + (co·(P − c).x − si·(P − c).y, si·(P − c).x + co·(P − c).y)
    g(d) = (co·d.x − si·d.y, si·d.x + co·d.y),  s = 1,  τ(θ) = θ + α
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

None.

## Checks

- `image`: the largest distance between the images of the defining points of `obj` (computed apart from the op) and those of the image; a line: the images of `p` and `p + dir` to the image line and `|unit(f(p + dir) − f(p)) − dir'|·S`; an arc or a sector: centre, radius, both ends (swapped after a reflection in a line) and the sweep; a polygon: the image vertices, `vertex.k` and the ends of `side.i`
