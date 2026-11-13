# `intersect.other_than` — the other intersection point

Registry 1.1 · group `intersect` · branch policy `other_than` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: curve`, `second: curve` (`curve` = `line` \| `segment` \| `ray` \| `circle`; `arc` since 1.4; `conic`, `function` since 1.8), `known: point` |
| outputs | `point: point` |
| undefined | `branch_absent`, `no_intersection`, `parallel`, `coincident`, `concentric`, `outside_part`, `zero_length`, `upstream` |
| checks | `on_both` |

"The second intersection of `first` and `second`, not `known`" — the
explicit replacement of GeoGebra's reordering of intersection points by
already known points (`order_points_by_reference`): `known` is an argument,
the result depends on nothing else.

## Value

The base pair gives the solutions `R` in its slot order:

| `first` × `second` | base | `R` |
|---|---|---|
| linear × linear | [intersect.line_line](intersect.line_line.md) | `[point]` |
| linear × circle | [intersect.line_circle](intersect.line_circle.md) (`line = first`) | `[first, second]` |
| circle × linear | [intersect.line_circle](intersect.line_circle.md) (`line = second`) | `[first, second]` |
| circle × circle | [intersect.circle_circle](intersect.circle_circle.md) | `[first, second]` |
| linear × conic, conic × linear (1.8) | [intersect.line_conic](intersect.line_conic.md) (`line` = the linear input) | `[first, second]` |
| conic × conic, circle or arc; circle or arc × conic (1.8) | [intersect.conic_conic](intersect.conic_conic.md) (`first`, `second` as given) | `[first … fourth]` |
| graph × graph (1.8) | [intersect.function_function](intersect.function_function.md) (`first`, `second` as given) | the common points by `x` |
| graph × linear, linear × graph (1.8) | [intersect.function_line](intersect.function_line.md) | the common points by `x` |
| graph × conic, circle or arc; and back (1.8) | [intersect.function_conic](intersect.function_conic.md) | the common points by `x` |

The arc of a circular input filters the points after they are fixed on its
carrier circle, as in the base. A graph pair has as many solutions as roots
in the search window (a double root twice, without the `count` limit of the
base); without a root `R` is the one reason of the base (`no_intersection`,
`coincident`). `detail.slot` of an `outside_part` from the base names the
slot of this operation (`first` or `second`) that holds the segment, ray or
arc. The `multiplicity` detail of the base is dropped.

    if no slot of R is defined:              → R[0] (its reason and detail)
    for each defined slot i of R, in order:
        dist_i = hypot(xi − kx, yi − ky)
    k = the first defined slot with dist_k ≤ tol.decide
    if there is none:                        → undefined "branch_absent"
    for the other slots in order:
        the first defined one                → the result
    if there is another slot (undefined)     → the first one: its reason and detail
    else                                     → undefined "branch_absent"

A tangency at `known` is a double root in both base slots, so the result is
the touching point, `known`. Two linear inputs have one solution, so the
result is always `branch_absent` or a reason of the pair. A pair with more
than two solutions (two conics, a graph) gives the first one after `known`
is left out, in the order of the base: the order of `first` for two conics,
`x` for a graph.

## Degeneracy decisions

The decisions of the base pair, then:

| decision | value `m` | tolerance |
|---|---|---|
| `known` (every defined slot) | `dist_i` | `tol.decide` (length) |

`known` is a noise decision for the fixture generator (kernel.md §6): a
point that lies on both curves by construction is usually found at a
rounding distance from its computed copy.

## Checks

- `on_both`: the distance of the result to the carrier line of a linear
  input or to the circle (the carrier circle of an arc), the focal residual
  of a conic, `|y − f(x)|` of a graph (1.8); the larger of the two.
