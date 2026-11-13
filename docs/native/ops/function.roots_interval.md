# `function.roots_interval` — distinct roots found on an interval

Registry 1.11 · module group `function_analysis` · status `beta` · branch policy
`distinct_roots_ascending`.

| | |
|---|---|
| inputs | `function: function`, `a: number`, `b: number` (literals or references) |
| param | `count`: optional slot capacity, default 100, integer 1..100 |
| outputs | `root.1 … root.count: point` |
| undefined | `empty_range`, `coincident`, `no_root`, `branch_absent`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

## Finite continuous pieces

Cut `[a,b]` by the explicit closed domain. Width at most `1e−10·S`, including
reversed bounds, gives `empty_range` before the solver runs. Search does not
use viewport bounds; S affects the shared geometric tolerances only.

The first grid has 512 equal cells, with the last node exactly b. Missing or
nonfinite values break finite chains. Refine finite/absent transitions to
adjacent doubles, with at most 2200 steps per refinement. Finite interior
probes that are undefined split the cell into two sides. Two absent ends do
not establish a finite piece between them.

Structurally continuous ASTs need no jump test: x, finite constants/refs,
addition, subtraction, negation, multiplication, nonnegative integer powers,
division by an x-independent nonzero constant and sin/cos/atan/abs over the
same subset. This preserves the steep continuous `atan(1e100·x)`. Missing
values still break such a chain.

For other ASTs, use the existing area sampling rule: suspect cells are the
first cell of each maximal equal-`|Δf|` plateau higher than its neighbours.
Bisect a suspect cell toward its larger absolute half-change, left on a tie.
A change relative to the initial nonzero cell change at most 1e−12 confirms
continuity. An undefined probe opens a domain boundary. A persistent relative
change between adjacent doubles opens both sides of a jump or pole. Running
out of 2200 steps without a terminal decision gives `no_convergence`.
Differences, ratios, midpoints and exceptionally wide grids avoid intermediate
overflow.

Merge adjacent confirmed finite cells into maximal detected pieces. Original
interval/domain ends are closed unless marked by a jump or pole. A finite
AST domain boundary such as sqrt at 0 or an included `If` boundary may be
closed; a merely nearby finite sample is not proof of a closed boundary.
Artificial open edges cannot contribute a root, even if a sample there is zero.

## Root search and fixed slots

For recognized polynomial bodies, use global isolation and filter by the
working closed interval. For other bodies, search each piece independently
on another grid of 512 cells:

1. Retain admissible exact-zero nodes.
2. Bisect sign changes up to 200 steps; require the root residual described
   on [`function.root_near`](function.root_near.md), not just a small x step.
3. At a strict local minimum of `|f|` with same-sign nonzero neighbours,
   refine by 100 golden-section steps. Keep an equally good original node.
   Require a two-sided strict minimum, continuity and
   `|f(candidate)|/max(|f(left_initial)|,|f(right_initial)|) <= 1e−10`.

Sort candidates by x and merge coordinates within `1e−10·S`, retaining the
smaller x. A tangency takes one slot. Each defined slot has
`detail: {found: N}`, the full number of distinct found roots before count
limits capacity. Thus count 1 for sin on `[−4,4]` binds only −π with found 3;
count 5 binds −π, 0, π and two undefined `branch_absent` slots. Sparse bindings
are supported. Invalid count declares no slots under the shared repeat rule.
More than 100 found results is `error/limit_exceeded`, regardless of count.

No results gives `no_root` in every slot; extra slots are branch_absent only
when N is positive. A recognized zero constant or a detected constant-zero
active branch gives `coincident`, with no fabricated representative or found
field. All-zero samples without a confirmed finite zero set give
`no_convergence`; small nonzero constants never become zero by tolerance.
All probes, derivative/residual work and refinements share 262144 evaluations.

The independent `on_graph` check measures the largest
`|y−f(x)|/max(1,|slope(x)|)` over defined outputs. Missing slots leave it active;
an empty set has no checks. The generator's `root_residual` noise report uses
this normal length and its length tolerance; the actual generic bracket
acceptance still uses the stricter relative initial-end residual. Tangency
acceptance has its own normalized scalar decision, so small positive minima
are not hidden as exact roots.

## Scope and examples

On `[−2,2]`, `If(x>0,x−1)` and `(x−1)/x` each give 1;
`If(x<0,x+1,x−1)` gives −1 and 1. On `[−4,4]`, tan gives −π, 0, π while its
poles split the search; `1/x` gives no roots. sin² gives the three tangencies
−π, 0, π once each. This intentionally retains tangencies some GeoGebra
numerical searches miss.

This is a partial numerical search. A finite grid may miss narrow domains,
rapid oscillation or tangencies. Brackets with an endpoint already at
roundoff-level residual may fail to confirm further relative improvement.
Neither count nor found promises completeness. Undefined dependencies carry
`upstream` and the original cause and recover without a last-good frame.
The old `function.root` operation keeps its earlier duplicated-tangency policy.
