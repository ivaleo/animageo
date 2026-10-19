# `intersect.function_line` — common points of a graph and a line

Registry 1.6 · group `intersect` · status `beta` · branch policy `roots_ascending` · see [function.root](function.root.md).

| | |
|---|---|
| inputs | `function: function`, `line: linear` (`line` \| `segment` \| `ray`) |
| params | `count` (optional, default 1) |
| outputs | `point: point`, repeated: `point.1 … point.count` |
| undefined | `no_intersection`, `coincident`, `outside_part`, `zero_length`, `branch_absent`, `upstream` |
| checks | `on_both` |

## Value

The carrier `(p, dir, L)` of `line` is the one of
[intersect.line_line](intersect.line_line.md).

    |dir_x| ≤ tol.decide (scalar):  a vertical line x = p_x  → point.1 = (p_x, f(p_x)) or "no_intersection";
                                    point.2 … are "branch_absent"
    else: h(x) = f(x) − (p_y + (x − p_x)·dir_y/dir_x), the search of function.root on the
          x-range of the window B4 cut by the domain;  point.k = (x_k, p_y + (x_k − p_x)·dir_y/dir_x)

Slots are fixed on the carrier line first; a segment or a ray then filters
each slot as [intersect.line_circle](intersect.line_circle.md) does
(`outside_part` with `detail: {"slot": "line"}`, which drops the
multiplicity). Slot order is ascending `x`, whatever the orientation of the line.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment) | `L` | `tol.decide` (length) |
| `vertical` | `dir_x` | `tol.decide` (scalar) |
| `coincident`, `tangent` | as in [function.root](function.root.md) | |
| `outside_part` (per slot) | `t`, `t − L` | `tol.decide` (length) |

## Checks

`on_both` — the larger of `|y − f(x)|` and the distance to the carrier line.
