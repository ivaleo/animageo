# `line.equation` — line by an equation `q(x, y) = 0`

Registry 1.10 · group `line` · status `beta` · `has("line_equation")`.
See [conic.equation](conic.equation.md) and [expr.md §5](../expr.md).

| | |
|---|---|
| inputs | `expr: expr` (`vars: ["x", "y"]`), `refs: number[]` (min 0) |
| outputs | `line: line` |
| undefined | `not_linear`, `degenerate_line`, `upstream` |
| checks | — |
| stepKind | `line_equation` |
| phrase ru | `{line} — прямая, заданная уравнением` |

Write an equation `L = R` as `q = L − R`, preserving its sign. The scalar
AST and numeric refs compile with the same `compile_function` as
`conic.equation`. This slot has `vars`, without `result`; typed pairs,
point/vector coordinates and function calls through refs are unavailable.
Changing a numeric ref recomputes the line and its dependents.

## Reading the equation

Frame `(0, 0, S)`, where `S` is the case scale: sample `q(S·x, S·y)`
at the nine points below. Divide all finite samples by their largest
absolute value before taking differences; leave all-zero samples unchanged.
Let `q'` denote these normalized samples. Coefficient recovery, the misfit
and coefficient normalization then share the same scale, avoiding overflow
when subtracting finite probes near the limit of a double.

    F = q'(0, 0)
    D = (q'(1, 0) − q'(−1, 0))/2
    E = (q'(0, 1) − q'(0, −1))/2
    misfit = max |q'(x, y) − (D x + E y + F)|
             over (±1, 0), (0, ±1), (1, 1), (2, −1), (−1, 2), (−1, −1)
    N = max(|D|, |E|, |F|)
    no value at a sample, or nonfinite recovered coefficient → not_linear
    N = 0: misfit > 0 → not_linear, otherwise degenerate_line
    misfit / N > tol.decide (scalar) → not_linear
    hypot(D/N, E/N) ≤ tol.decide (scalar) → degenerate_line
    a = D/S; b = E/S; c = F
    n = (a, b)/hypot(a, b)
    dir = (n.y, −n.x)
    p = −c·(a, b)/(a² + b²)

The implementation normalizes coefficients before computing the foot `p`
to avoid overflow or underflow of the squared denominator. This is a
finite sampling test, like `conic.equation`, rather than a symbolic proof
of linearity. `not_linear` (`misfit/N`) and `degenerate_line`
(`hypot(D/N, E/N)`) are noise decisions against the scalar tolerance.

The direction `(b, −a)` matches GeoGebra's saved `<coords x=a y=b z=c>`
and determines the order of intersections along the line. Multiplying
an equation by a negative number reverses its direction. The bridge
produces an ordinary classic `Line`: rendering, paint, labels and
intersections use the same paths as `line.by_points`.

GGB import reads free line formulas even without refs; unsupported
formulas produce `formula_unsupported` with detail. Saved coefficients
and their orientation are checked; a mismatch is `differs`.
`describe` uses the phrase above. «Команды» prints the operation with
`unprintable_operation`; edits with a base document preserve it.
