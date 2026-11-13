# `function.extrema_interval` — isolated local extrema found inside an interval

Registry 1.11 · module group `function_analysis` · status `beta` · branch policy
`distinct_roots_ascending`.

| | |
|---|---|
| inputs | `function: function`, `a: number`, `b: number` (literals or references) |
| param | `count`: optional slot capacity, default 100, integer 1..100 |
| outputs | `extremum.1 … extremum.count: point` |
| undefined | `empty_range`, `no_extremum`, `branch_absent`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

Use the range validation, finite-piece subdivision and shared budgets of
[`function.roots_interval`](function.roots_interval.md). Every extremum must
be strictly inside a finite continuous piece and the working interval; neither
original endpoints nor open boundaries at holes, poles and jumps contribute.

For polynomial bodies, isolate derivative roots and retain only changes of
derivative sign, with the same strict domain/interval filter as
[`function.extrema_polynomial`](function.extrema_polynomial.md). For other
bodies, sample 512 cells per piece. Refine interior minimum/maximum candidates
by 100 golden-section steps, keeping an equally good original grid node.
Require a finite original evaluator value and a strict two-sided local turn.
A detected constant active branch is a plateau, not an isolated extremum;
that proof propagates through arithmetic and function wrappers. Thus
`max(abs(x)−0.001,0)+1` has no isolated minimum. Two-sided local probes at
`h=max(16·xTol(x),1e−10·S)`, shortened to stay inside the piece, must confirm
the turn. If rounded probe values equal the candidate, finite derivatives
with the proper opposite signs can confirm a smooth peak; a constant active
branch on either side rejects a plateau edge. Stationarity alone is
insufficient; cusp minima need no derivative.

Examples:

- sin on `(0,2π)` gives `(π/2,1)` max, then `(3π/2,−1)` min.
- abs on `(−1,1)` gives `(0,0)` min.
- `If(x>0,(x−1)²)` on `[−2,2]` gives `(1,0)` min despite its absent left half.
- A continuous `If` join can be a minimum; a jump or pole cannot.
- A constant, plateau, monotone function or `x³` has no isolated local extrema.
- `x²` on `[0,2]` has none: its stationary point is an endpoint.

Slots follow ascending x. Every defined slot has
`detail: {found: N, kind: "min" | "max"}`, where N precedes the count limit.
Count 1 for the sine example reports found 2 and kind max. Extra slots in a
nonempty set are `branch_absent`; an empty set gives `no_extremum` everywhere.
No undefined slot carries found. More than 100 found results or an exhausted
evaluation budget gives `error/limit_exceeded`, never a truncated success.

Iteration ambiguity gives `no_convergence`; unrepresentable recognized
coefficients give `non_finite`; invalid range gives `empty_range`. A local
undefined value splits a piece rather than failing the whole search.
Undefined inputs propagate `upstream` with their original cause and recover
when valid. General numerical search does not promise completeness.

`on_graph` is the largest `|y−f(x)|` over defined outputs, using the original
function evaluator. It checks incidence, not completeness or local extremality.
Missing slots do not suppress the check; an empty set has no checks. Existing
`function.extremum` behavior and details remain unchanged.
