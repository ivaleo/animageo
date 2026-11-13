# `function.root_interval` — one root on an interval

Registry 1.11 · module group `function_analysis` · status `beta` · no branch policy.

| | |
|---|---|
| inputs | `function: function`, `a: number`, `b: number` (literals or references) |
| params | none |
| output | `root: point`, `{x, y: 0}` |
| undefined | `empty_range`, `coincident`, `no_root`, `no_convergence`, `non_finite`, `upstream` |
| check | `on_graph` |

Intersect `[a,b]` with the function's explicit closed domain. The resulting
width must exceed `1e−10·S`; reversed or empty ranges are not swapped and give
`empty_range` before solver work. A recognized zero constant gives
`coincident`, a nonzero one gives `no_root`. A detected zero active branch
also gives coincident. The bounds and all function refs recompute together.

## Primary bisection, then fallback

Split the working interval into detected finite continuous pieces. An exact
zero at the original left endpoint is preferred to one at the right,
provided it is not an artificial open edge or a jump/pole. If both finite
ends have opposite signs and the entire working interval is one confirmed
continuous piece, use bisection. Compare signs without multiplying values.
A successful bisection has priority, even if another root lies to its left.

Otherwise run the same full search as
[`function.roots_interval`](function.roots_interval.md) and take its smallest
found x. Fallback covers equal endpoint signs, undefined endpoints, several
pieces and an unconfirmed first bisection. A failed local bracket alone is
not an operation failure. No result in fallback gives `no_root`.

Examples:

- `x²` on `[−1,1]` gives 0 through fallback, retaining the tangency.
- `(x−1)(x−3)` on `[0,4]` gives 1 through fallback.
- `(x−1)(x−2)(x−4)` on `[0,5]` gives 4 through primary bisection.
- `If(x>0,x−1)` on `[0,2]` gives 1 despite its undefined left endpoint.
- `(x−1)/x` on `[−2,2]` gives 1; the pole at 0 never becomes a root.
- `If(x<0,x+1,x−1)` on `[−2,2]` searches the pieces and gives −1.

Bisection, residuals, finite-piece boundaries and the shared evaluation budget
follow the near/interval search pages. Generic bracket residuals use the
smaller absolute initial endpoint value, before refinement; polynomial
residuals use their normalized coefficients. Iteration ambiguity gives
`no_convergence`, resource exhaustion `error/limit_exceeded`, unrepresentable
recognized coefficients `non_finite`. Neither a local hole nor a jump gives
global `out_of_domain` or `discontinuous`. Undefined dependencies propagate
`upstream` with their cause; valid inputs restore the root.

The independent `on_graph` check is the normalized graph distance of this
point, as for `function.root_near`. The operation has neither count nor
found detail and never creates or deletes document elements.
