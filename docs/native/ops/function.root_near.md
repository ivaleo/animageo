# `function.root_near` — a root from an initial abscissa

Registry 1.11 · module group `function_analysis` · status `beta` · no branch policy.

| | |
|---|---|
| inputs | `function: function`, `start: number` (literal or reference) |
| params | none |
| output | `root: point`, `{x, y: 0}` |
| undefined | `coincident`, `no_root`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

## Selection

Start is the initial abscissa of a deterministic numerical method. It does
not request the nearest root or a root inside the view. All coefficients,
refs and start remain live. A recognized nonzero constant gives `no_root`;
zero gives `coincident`. A detected constant-zero active branch also gives
`coincident` rather than an arbitrary representative of infinitely many roots.

First try damped Newton, at most 128 steps. The derivative is computed from
the current AST branch without a symbolic algebra library or a public
Derivative operation. Lazy `If` skips unselected branches. Derivatives at
an `If` switch, at the cusp of abs and at invalid or nonfinite intermediate
values are unavailable. Each Newton proposal tries the full step, then up
to 16 halvings, taking the first finite point that strictly reduces `|f|`
without crossing a detected discontinuity.

An exact zero must belong to a finite continuous piece. Before returning it,
any zero active branch discovered by continuity probes is checked again.
An inexact Newton
result requires both a last accepted step at most
`xTol(x)=max(1e−12,1e−12·|x|)` and a normalized residual at most 1e−12.
The residual scale is the largest absolute finite value at start and in the
accepted sequence, without a lower floor of 1. Its control neighbourhood,
with radius `max(16·xTol(x),1e−10·S)`, must remain one confirmed piece. Merely
being near an open piece edge is insufficient: `If(x<0,x,1)` has no root at
its excluded limiting point 0. A failed neighbourhood check starts fallback;
an exact zero strictly inside a piece remains admissible even near a defect.
A zero derivative, cycle,
invalid step, exhausted Newton loop or unconfirmed residual triggers fallback.
An undefined start skips Newton and also uses fallback.

## Right-first expansion

Search around the original start with radii 1, 2, 4, …, up to 1048576:
at most 20 doublings after the first radius, with no repeated maximum.
Distances are coordinate units, independent of the view scale. At each
radius, inspect the whole right side before the left. Split each side into
detected finite continuous pieces; visit adjacent sample nodes from start
outward. An exact admissible zero is checked before a sign-changing pair.
Refine the first confirmed bracket by bisection. A rejected pole/jump bracket
does not prevent trying other pairs, sides or radii. Unrepresentable external
coordinates and sides with no new representable coordinate are skipped.

For `x²−2`, start 1 selects +√2, start −1 selects −√2, and start 0 selects
+√2 because the right bracket is tried first after the zero derivative.
Starting at the hole of `(x−1)/x` can still find 1. The method does not
promise to detect a tangency missed by Newton and the exact sample nodes.
Its basin need not match every GeoGebra start.

Bisection accepts an exact zero or refines toward adjacent doubles, at most
200 steps. An inexact generic result requires width at most xTol and
`|f(x)|/min(|f(left_initial)|,|f(right_initial)|) <= 1e−12`.
Recognized polynomials use their normalized coefficient residual from
[`function.roots_polynomial`](function.roots_polynomial.md). Finite-piece
sampling and open boundaries follow
[`function.roots_interval`](function.roots_interval.md).

All Newton, backtracking, continuity and fallback probes share one budget of
262144 body/derivative evaluations. Exhaustion is `error/limit_exceeded`,
not partial success. If the complete bounded method confirms no root,
`no_convergence` does not assert that no root exists. Unrepresentable
recognized polynomial coefficients give `non_finite`; undefined inputs
propagate `upstream` and their original cause, then recover with valid inputs.

`on_graph` independently measures `|y−f(x)|/max(1,|slope(x)|)`, using a finite
analytic AST derivative or finite one-sided secants as described on the
polynomial roots page. A single root has no count or found detail.
