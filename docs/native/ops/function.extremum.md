# `function.extremum` — local extrema of a function on an interval

Registry 1.6 · group `function` · status `beta` · branch policy `roots_ascending` · see [function.root](function.root.md).

| | |
|---|---|
| inputs | `function: function`, `a: number`, `b: number` |
| params | `count` (optional, default 1) |
| outputs | `extremum: point`, repeated: `extremum.1 … extremum.count` |
| undefined | `empty_range`, `no_root_in_window`, `branch_absent`, `upstream` |
| checks | `on_graph` |

## Slots

`extremum.k = (x_k, f(x_k))` with `detail: {"kind": "max" | "min"}`, the
interior extrema in ascending `x`; the ends of the interval are not extrema.
Missing slots are `branch_absent`; none at all — `no_root_in_window`.

## The search

The interval and the grid of [function.root](function.root.md) (`f_k = f(x_k)`):

    0 < k < 512, f_k−1, f_k, f_k+1 defined:
      f_k−1 < f_k ≥ f_k+1  → a maximum: golden section of −f over [x_k−1, x_k+1]
      f_k−1 > f_k ≤ f_k+1  → a minimum: golden section of  f over [x_k−1, x_k+1]
    the point (x*, f(x*)); sorted by x; within tol.decide of the previous → merged

A constant function has no extremum; a plateau gives one at its first node.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `empty_range` | `hi − lo` | `tol.decide` (length) |

## Checks

`on_graph` — the largest `|y − f(x)|` of the defined slots.
