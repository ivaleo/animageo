# `intersect.nearest` — intersection nearest to a point

Registry 1.4 · beta · group `intersect` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: curve`, `second: curve`, `near: point` |
| outputs | `point: point` |
| policy | `nearest_to` |
| undefined | `no_intersection`, `parallel`, `coincident`, `concentric`, `outside_part`, `zero_length`, `upstream` |
| checks | `on_both` |

The solution of two curves (a line, a segment, a ray, a circle or an arc;
since registry 1.8 also a conic or the graph of a function) nearest to the
point `near`, as GeoGebra `Intersect(a, b, <Point>)`. The solutions are
those of the base pair, computed by the same functions and in the order of
its policy: `intersect.line_line` (one point), `intersect.line_circle`
(`line_param_order`, a linear input may come second),
`intersect.circle_circle` (`circle_side`); since 1.8
`intersect.line_conic` (along the line, either order),
`intersect.conic_conic` (`first_curve_order` of `first`, for a conic with a
conic, a circle or an arc), and for a graph with a graph, a linear input or
a conic, circle or arc `intersect.function_function`,
`intersect.function_line`, `intersect.function_conic` (by `x`, every root in
the search window, without their `count`) — after the part filters (an
arc, a segment, a ray; `detail.slot` names `first` or `second`). Without a
defined solution the result is the reason of the first solution
(`parallel`, `no_intersection`, `outside_part` …), as in
`intersect.other_than`. A document with a conic or a graph in `first` or
`second` declares registry 1.8 (`familySince`, kernel.md §2).

## Value

    roots = solutions of (first, second), plain, after the part filters
    defined = [r in roots that are defined]
    if not defined:   → reason of roots[0]
    best = defined[0];  d_best = hypot(best − near)
    for r in defined[1:]:
        d = hypot(r − near)
        if d < d_best − tol.decide: best = r;  d_best = d
    point = best

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| the decisions of the base pair | as there | as there |
| `nearest_tie` | `d − d_best` | `tol.decide` |

## Checks

- `on_both`: `max(dist(point, first), dist(point, second))`, the distance to the carrier line of a linear input or `| |X − c| − r |` to a circle or the carrier circle of an arc; since 1.8 the focal residual of a conic and `|y − f(x)|` of a graph
