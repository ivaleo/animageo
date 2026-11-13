# `function.extrema_polynomial` — isolated local extrema of a polynomial

Registry 1.11 · module group `function_analysis` · status `beta` · branch policy
`distinct_roots_ascending` · see [kernel.md](../kernel.md).

| | |
|---|---|
| input | `function: function` |
| param | `count`: optional slot capacity, default 100, integer 1..100 |
| outputs | `extremum.1 … extremum.count: point` |
| undefined | `not_polynomial`, `no_extremum`, `branch_absent`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

## Meaning

Isolate the real roots of the polynomial derivative and retain only a change
of its sign: negative to positive is a minimum, positive to negative a
maximum. Stationarity alone does not suffice. Thus `x³` has no extrema and
`x⁴` has one minimum `(0,0)`. A constant or linear polynomial gives
`no_extremum`; plateaus are not enumerated.

Candidates are ordered by ascending x, rather than by kind. `x³−3x` gives
`(−1,2)` with `kind: max`, then `(1,−2)` with `kind: min`. The original
function evaluator supplies y, rather than the expanded coefficient array.
The search is global and independent of the view window. It then retains
candidates strictly inside the explicit domain: a domain endpoint cannot
supply the required two-sided local extremum, including a stationary point
at that endpoint. Restricting a monotone function does not add endpoint
extrema. For example, `x²` with domain `[0,2]` yields `no_extremum`.

## Fixed slots and failures

Every defined slot has `detail: {found: N, kind: "min" | "max"}`. N counts
all distinct admissible extrema before count limits the bound slots. With
the cubic above, count 1 still reports found 2. Extra slots in a nonempty
set are `branch_absent`; an empty set gives `no_extremum` in all requested
slots. Undefined outputs have no found field. Multiple derivative roots do
not duplicate extrema, and reevaluation creates or removes no elements.
Ranks can change when coefficients or the number of extrema change.

The polynomial subset, degree limit 64, coefficient normalization, recursive
isolation, arithmetic sign enclosure and shared numerical budgets are those of
[`function.roots_polynomial`](function.roots_polynomial.md). No finite
coefficient is discarded just because it is small. Unsupported bodies,
including `If`, give `not_polynomial`, even if a sampled graph looks
polynomial. Degree/evaluation exhaustion gives `error/limit_exceeded`;
unconfirmed isolation gives `no_convergence`; unrepresentable arithmetic or
an absent original y gives `non_finite`. Undefined dependencies propagate
`upstream` and the original cause; valid inputs recover automatically.

Derivative sign probes lie strictly on either side of a critical point.
When a Cauchy endpoint or a midpoint rounds to the critical x, use the next
representable double on that side. Thus `(x−1e20)²` retains its minimum at
`(1e20,0)`, also in `extrema_interval` on `[5e19,1.5e20]`.

## Check

`on_graph` is the maximum `|y−f(x)|` over defined outputs, using the original
function evaluator. It checks graph incidence, not the derivative sign
change or completeness of the set. Missing repeated slots leave this check
active for the defined outputs; an empty set has no check. The pre-existing
`function.extremum` operation retains its earlier contract.
