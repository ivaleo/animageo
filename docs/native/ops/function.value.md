# `function.value` — scalar value at a given abscissa

Registry 1.11 · module group `function_analysis` · status `beta` · no branch
policy · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `function: function`, `x: number` (literal or reference) |
| params | none |
| output | `number: number`, value `{value: f(x), unit: "scalar"}` |
| undefined | `out_of_domain`, `upstream` |
| checks | none |

The output is a dependent number. It evaluates the current function AST and
numeric refs at the requested finite abscissa, with the existing lazy
interpreter. Both the function's coefficients and a referenced x remain
live dependencies: for `f(x)=c·x²`, c=3 and x=2 gives 12; changing x to 4
gives 48, then changing c to −2 gives −32.

An explicit domain is closed. Its endpoints are evaluated at their actual
abscissas; an x outside it gives `out_of_domain` without clamping to an
endpoint. The same reason covers a hole, pole, nonreal or nonfinite result
of the function evaluator: `1/x` at 0 and `exp(x)` at 1000 are undefined.
A nonfinite x itself is rejected by the common native input rules.

Only the selected `If` branch is evaluated. No continuous neighbourhood is
required: `If(x<0,1,2)` at 0 gives 2, while replacing `<` with `<=` gives 1.
An invalid unselected branch does not poison the value. Negative zero is
normalized to positive zero. Undefined dependencies propagate `upstream`
with their original cause; restoring inputs restores the value without a
last-good-value cache.

For a point on OY, continue using `point.expression` with `(0,f(0))`.
Likewise, `(a,f(a))` is a typed point expression over a and f. These existing
representations need registry 1.10; they do not need a new point operation
or a free path input. `function.value` instead requires registry 1.11 and
creates only a number. Its current scope does not add typed function calls
to `number.expression` or imply support for compound scalar import
expressions such as `f(a)+2`.
