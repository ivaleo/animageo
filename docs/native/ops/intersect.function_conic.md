# `intersect.function_conic` — common points of a graph and a conic

Registry 1.8 · group `intersect` · status `beta` · branch policy `roots_ascending` · see [intersect.function_line](intersect.function_line.md), [intersect.conic_conic](intersect.conic_conic.md).

| | |
|---|---|
| inputs | `function: function`, `conic: conical` (`conic` \| `circle` \| `arc`) |
| params | `count` — number of slots, a whole number 1..100 (default 1); outside it the operation has no output slots |
| outputs | `point.1 … point.count: point` |
| undefined | `no_intersection`, `coincident`, `outside_part`, `branch_absent`, `upstream` |
| checks | `on_both` |

## Value

The curve of `conic` (an arc is its carrier circle) and its
`measure(X) = G(X)/unit` are those of
[intersect.conic_conic](intersect.conic_conic.md#curves). The common points
are the roots of

    h(x) = measure(x, f(x))           (None where f has no value)

searched as [intersect.function_function](intersect.function_function.md):
on the x-range of the window `B4` of the bounds cut by the domain of the
function (`search_interval`; an empty cut is `no_intersection` in every
slot), by `find_roots` on its grid — a sign change is a simple root found
by bisection, a local minimum of `|h|` within `tol.decide` a double root
(decision `tangent`, noise). Each `x` gives one point `(x, f(x))` (a graph
meets a vertical line once), so a closed conic is met at most four times
and a graph that crosses a branch twice gives two roots.

    |h| ≤ tol.decide at every defined node   → every slot "coincident"
    no root                                  → every slot "no_intersection"
    a root where f(x) is not finite          → that slot "non_finite"

## Branches: `roots_ascending`

`point.k` is the `k`-th common point by `x`; a double root fills two
consecutive slots, both `{"multiplicity": 2}` in `detail`; slots beyond the
roots are `branch_absent`. The slots are fixed on the carrier circle of an
arc; then a point off the arc (`on_arc` of
[intersect.line_circle](intersect.line_circle.md)) is `outside_part` with
`detail {"slot": "conic"}` (and no multiplicity).

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident` | the largest `|h|` on the grid | `tol.decide` (length) |
| `tangent` (noise) | `h` at a local minimum of `|h|` | `tol.decide` (length) |
| `outside_part` (per slot, arc) | as `on_arc` | `tol.decide` (length) |

## Checks

`on_both` — the larger of `|y − f(x)|` and the residual on the conic (the
focal residual, `| |X − c| − r |` of a circle or of the carrier of an arc)
over the defined points; runs when slots beyond the roots are absent.
