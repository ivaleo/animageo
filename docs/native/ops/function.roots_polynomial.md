# `function.roots_polynomial` — distinct real roots of a polynomial

Registry 1.11 · module group `function_analysis` · status `beta` · branch policy
`distinct_roots_ascending` · see [kernel.md](../kernel.md).

| | |
|---|---|
| input | `function: function` |
| param | `count`: optional slot capacity, default 100, integer 1..100 |
| outputs | `root.1 … root.count: point` |
| undefined | `not_polynomial`, `coincident`, `no_root`, `branch_absent`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

## Meaning and slots

Find all distinct real roots on the entire real line, filter them by the
function's explicit closed domain, then order them by ascending x. Each point
has value `{x, y: 0}`. The view bounds affect tolerance scale S, never the
search range. For example, `x²(x−2)³` gives 0 and 2, once each; `x−1000`
gives 1000 even when the view spans only −10..10.

`count` limits the slots, not the search. Every defined slot has
`detail: {found: N}`, where N is the full number of distinct admissible roots
before limiting capacity. With `x²−4x+3`, count 1 binds `(1,0)` with found 2;
count 3 binds `(1,0)`, `(3,0)` and an undefined `branch_absent`. Sparse bindings
such as only `root.3` are supported. There is no multiplicity field or repeated
slot for a multiple root. Invalid count declares no slots under the shared
`repeat_count` rule (integer tolerance 1e−9).

No roots gives `no_root` in every requested slot. A nonzero constant, however
small, has no roots; the identically zero polynomial gives `coincident`.
Undefined slots have no found detail. Elements and producer slots remain
fixed on reevaluation; ranks may shift as roots merge or disappear. Returning
valid refs restores results without using any previous good frame.

## Polynomial subset and isolation

The AST is expanded into ascending coefficients `[c0,…,cn]` with current numeric
refs. Supported nodes are x, finite constants and refs, addition, subtraction,
negation, multiplication, division by an x-independent nonzero constant, and
nonnegative integer powers. Constant subtrees use the existing interpreter.
`If`, x-dependent functions such as sin/abs/sqrt, and x-dependent denominators
are `not_polynomial`: `x/x` never loses its hole through cancellation. Invalid
constant operands remain invalid even under a zero multiplier or zero power.
The original AST limits still apply.

Only exact leading zeros are removed. Expanded degree above 64 gives
`error/limit_exceeded`, not `not_polynomial`. Coefficients are normalized by
their common positive maximum. The Cauchy bound
`R = 1 + max(|ci/cn|)` encloses the real roots. Recursive derivative-root
isolation partitions `[−R,R]` into monotone intervals; sign changes are
bisected and stationary zeros supply tangencies. Exact factors x are removed
before recursion. Root estimates are merged only within `1e−10·S`, retaining
the smaller x. Polynomial residuals use
`|p(x)| / sum(|ci|·|x|^i) <= 1e−10`, with an explicit exact-zero case when the
sum vanishes. Reciprocal Horner evaluation outside [−1,1] keeps the sign and
residual scale finite without forming overflowing powers.

Bisection accepts an exact zero or refines to adjacent doubles; after the
200-step budget, width must be at most `max(1e−12,1e−12·|x|)` and the residual
must pass. The operation shares a 262144-evaluation budget and allows at most
100 results. Resource exhaustion is `error/limit_exceeded`; unfinished
isolation is `no_convergence`. Unrepresentable coefficients, normalization or
global bounds give `non_finite`. The original evaluator must also have a
finite value at a retained root.

## Close roots and arithmetic resolution

At a stationary candidate, a normalized residual within `1e−10` permits a
tangency. Two neighbouring sign changes instead preserve a simple pair when
the stationary sign is confirmed by an outward Horner enclosure. Each normalized
coefficient is enclosed by its adjacent doubles; the reciprocal argument outside
[−1,1], every product and every sum are also rounded outwards. If this enclosure
still includes zero, the stationary candidate uses one slot. This is an arithmetic
resolution limit, separate from merging by geometric distance. `tangent`,
`root_residual` and `root_merge` decisions are reported to the shared fixture
generator.

At S=1, `(x−1)²` and `(x−1)²(x+2)` give one slot for the repeated root 1.
`(x−1)(x−1−d)` gives two roots for d=1e−6 and d=1e−7; multiplying these
expressions by 1e6 preserves the counts. For d=1e−8 and d=1e−9, the expanded
double coefficients exactly match those of `(x−(1+d/2))²`, including after
multiplication by 1e6. The coefficient profile cannot recover which original
AST supplied them. The result is one candidate near `1+d/2`. These examples
bracket the observed resolution limit; it also depends on coefficient rounding
and is not a universal coordinate separation threshold. Poorly conditioned
expanded polynomials can lose distinct roots, or shift their coordinates,
before the geometric merge tolerance is reached.

## Check

For all defined outputs, `on_graph` measures the largest
`|y−f(x)| / max(1,|slope(x)|)`. The finite analytic polynomial derivative
supplies the slope; otherwise use the largest finite one-sided secant at
`x±h`, `h=max(16·xTol(x),1e−10·S)`, respecting domain. With no usable
secant, slope is zero. Normalization is necessary for `1e20·(x²−2)`, whose
small x error can produce a large raw vertical residual. The check uses the
original evaluator and verifies incidence, not completeness or multiplicity.
Absent repeated slots do not suppress checks of the defined ones; an empty
result has no checks. Older `function.root` semantics and checks are unchanged.
