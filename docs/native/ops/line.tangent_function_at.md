# `line.tangent_function_at` — graph tangent at an abscissa

Registry 1.12 · module group `tangency` · status `beta`.

| | |
|---|---|
| inputs | `function: function`, `x: number` (literal or live reference) |
| params | none |
| outputs | `line: line`, `touch: point` |
| orientation | `graph_increasing_x` |
| undefined | `out_of_domain`, `not_differentiable`, `no_convergence`, `non_finite`, `upstream` |
| checks | `on_curve`, `tangent` |

The contact is Q=(x,f(x)). With finite derivative m, the line passes through
Q with direction (1,m)/hypot(1,m). Its stored `p` is the projection of the
origin onto the line. The producer's path frame starts at Q, so
`point.on_path` at parameter zero returns the contact. For x² at 1 the
result is y=2x−1, Q=(1,1); for x³ at −2 it is y=12x+16.

The analytic AST rules are shared with function analysis. At an undecided
join, the independent `tangency` numeric profile refines h from
2⁻⁸·max(1,|x|), halving it at most 24 times. Central differences and
second-order one-sided stencils use Richardson extrapolation. Continuity
to f(x), agreement of both increasing-x unit directions and three stable
levels are required. Direction and continuity tolerances are 1e−10;
the evaluation budget is 262144. An unconfirmed limit, missing interior
samples, exhausted budget or indistinguishable abscissas gives
`no_convergence`. This bounded confirmation does not prove differentiability
of arbitrary oscillatory expressions.
Available analytic derivatives at neighboring samples also guard against a
flat sequence caused by lost floating-point precision.

An explicit domain includes its ends and permits a one-sided tangent there.
A closed one-branch `If` guard comparing x to a constant can also represent
an included endpoint. Open ends, holes, poles and absent function values give
`out_of_domain`; x is never clamped. A corner, jump or infinite derivative
gives `not_differentiable`. Vertical graph tangents are unsupported: sqrt(x)
at 0 is undefined. A smooth `If` join may succeed; a jump refuses the tangent
even when its selected branch has a finite analytic derivative.

Both outputs share a refusal. Undefined dependencies preserve `upstream`
and its original cause; current x and function coefficients are recomputed
without retaining an earlier frame. Nonfinite line geometry gives
`non_finite`.

Build a normal with `line.perpendicular(point=touch, base=line)`. For x² at 1
this is y=−x/2+3/2; at 0 the tangent is horizontal and the normal vertical.
No separate normal operation is needed. Selecting an external point A uses
only x(A) in this mode; the tangent and normal pass through Q.

All five tangency operations are active in registry 1.12. `has("tangency")`
remains false until the module's import integration is available. Classic
command conversion is not yet provided.
