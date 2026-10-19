# `function.expr` — a function y = f(x) by a formula

Registry 1.6 · group `function` · status `beta` · see [kernel.md](../kernel.md), [expr.md §5](../expr.md).

| | |
|---|---|
| inputs | `expr: expr` (`vars: ["x"]`), `refs: number` (list, `min: 0`) |
| params | `min`, `max` (optional: the ends of the domain) |
| outputs | `function: function` |
| undefined | `empty_range`, `upstream` |
| checks | — |

## Value

    function = {expr: <the tree>, refs: [value of refs[k], …], domain: [min | null, max | null]}

The tree is the argument as it is (validated by [expr.md](../expr.md) §1–§2, §5;
a refused tree is `error/formula`). `refs` holds the values of the number
elements (any unit, an angle in radians); a change of a ref changes the
function. A missing `min` or `max` is `null` (unbounded on that side).

    if min and max are given and max − min ≤ tol.decide:  → undefined "empty_range"

`f(x)` has no value outside `[min, max]` and where the tree has none
(`out_of_domain`, `non_finite` of a node). Every consumer — the searches, the
drawing, `point.on_function` — reads the graph through
`kernel/function.py::evaluator`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `empty_range` | `max − min` | `tol.decide` (length) |

## Drawing

`function_runs(value, x_range, y_range)` (`kernel/function.py`): the x-range of
the canvas cut by the domain, 256 equal cells, a cell halved (at most 8
times) while an end or its midpoint has no value or the midpoint is farther
than `10⁻³` of the canvas height from the chord; a finest cell with an end
without a value or a jump above `0.05` of the height is a gap. The runs are
clipped to the canvas height widened by itself on each side. Style keys as a
locus (no label).
