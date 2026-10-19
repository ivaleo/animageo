# `intersect.function_function` — common points of two graphs

Registry 1.6 · group `intersect` · status `beta` · branch policy `roots_ascending` · see [function.root](function.root.md).

| | |
|---|---|
| inputs | `first: function`, `second: function` |
| params | `count` (optional, default 1) |
| outputs | `point: point`, repeated: `point.1 … point.count` |
| undefined | `no_intersection`, `coincident`, `branch_absent`, `upstream` |
| checks | `on_both` |

## Value

The roots of `h(x) = f(x) − g(x)` by the search of
[function.root](function.root.md) on the x-range of the window `B4` (the
document bounds scaled 4 times about their centre, as the window of a locus)
cut by both domains; `point.k = (x_k, f(x_k))`. A tangency fills two slots with
`detail: {"multiplicity": 2}`. An empty cut or no root — `no_intersection`;
`h` vanishing on the whole range — `coincident`.

## Degeneracy decisions

`coincident`, `tangent` as in [function.root](function.root.md) (`h = f − g`).

## Checks

`on_both` — the largest `|y − f(x)|`, `|y − g(x)|` of the defined slots.
