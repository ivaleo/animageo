# `conic.equation` — conic by an equation `q(x, y) = 0`

Registry 1.6 · group `conic` · status `beta` · see [conic.ellipse_foci_point](conic.ellipse_foci_point.md), [expr.md §5](../expr.md).

| | |
|---|---|
| inputs | `expr: expr` (`vars: ["x", "y"]`), `refs: number[]` |
| outputs | `conic: conic` |
| undefined | `not_quadratic`, `degenerate_conic`, `upstream` |
| checks | — |

`expr` is the left side of `q(x, y) = 0` (an equation `L = R` is written
`L − (R)`); it takes the nodes of AST v1 and `var` with `x` or `y`, refs as
in [function.expr](function.expr.md). The coefficients are read at points,
the conic is classified by [Classification](#classification).

## Reading the equation

Frame `(0, 0, S)` (`S` the scale of the case): `q'(x', y') = q(S·x', S·y')`.

    F = q'(0, 0)
    A = (q'(1, 0) + q'(−1, 0))/2 − F;   D = (q'(1, 0) − q'(−1, 0))/2
    C = (q'(0, 1) + q'(0, −1))/2 − F;   E = (q'(0, 1) − q'(0, −1))/2
    B = q'(1, 1) − A − C − D − E − F
    misfit = max |q'(x, y) − (A x² + B xy + C y² + D x + E y + F)| over (2, 1), (−1, 2), (−1, −1), (1, −2)
    N = max(|A|, …, |F|)
    q' has no value at one of the ten points               → "not_quadratic"
    N = 0:  misfit > 0 → "not_quadratic", else "degenerate_conic"
    misfit / N > tol.decide (scalar)                        → "not_quadratic"
    else the coefficients (A … F) in the frame (0, 0, S)

## Classification

`from_coeffs(A, B, C, D, E, F; x0, y0, s)` (also [conic.five_points](conic.five_points.md))
classifies `A x'² + B x'y' + C y'² + D x' + E y' + F = 0` in the frame
`x = x0 + s·x'`, `y = y0 + s·y'`. All decisions are scalars against
`tol.decide` (scalar):

    divide A … F by max(|A|, …, |F|) (0 → "degenerate_conic") → a, b, c, d, e, f
    det = a(cf − e²/4) − (b/2)(bf/2 − ed/4) + (d/2)(be/4 − cd/2)
    |det| ≤ tol                                → "degenerate_conic"          (decision degenerate)
    mean = (a + c)/2;  half = hypot((a − c)/2, b/2)
    v+   = [1, 0] if half = 0, else normalize(((a − c)/2 + half, b/2)) if a ≥ c, else normalize((b/2, (c − a)/2 + half))
    v−   = v+ turned by +90°
    mean ≥ 0: big = mean + half, e_big = v+, e_small = v−;  else big = mean − half, e_big = v−, e_small = v+
    small = (ac − b²/4) / big;  δ = small / big
    |δ| ≤ tol → parabola (decision parabola):
        lw = (d, e)·e_big;  lu = (d, e)·e_small
        lu = 0 → "degenerate_conic"
        s0 = −lw / (2·big);  t0 = (lw²/(4·big) − f) / lu
        vertex' = s0·e_big + t0·e_small;  axis = σ·e_small, σ = +1 if −big/lu > 0 else −1
        p' = |lu| / (2|big|)
    else (central):
        centre' = ((b·e/4 − c·d/2), (b·d/4 − a·e/2)) / (ac − b²/4);  k = f + (d·cx' + e·cy')/2
        δ > 0 (ellipse):
            k·big > 0 → "degenerate_conic" (no real points)
            |(big − small)/big| ≤ tol → circle: axis [1, 0], a' = b' = sqrt(−k/big)      (decision circle)
            else axis = orient(e_small), a' = sqrt(−k/small), b' = sqrt(−k/big)
        δ < 0 (hyperbola):
            −k/big > 0: axis = orient(e_big), a' = sqrt(−k/big), b' = sqrt(k/small)
            else:       axis = orient(e_small), a' = sqrt(−k/small), b' = sqrt(k/big)
    orient(u): −u when u_y < −tol or (|u_y| ≤ tol and u_x < 0), else u    (decision axis_orientation)
    world: c = (x0, y0) + s·centre', vertex = (x0, y0) + s·vertex', a = s·a', b = s·b', p = s·p'

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `not_quadratic` (noise) | `misfit / N` | `tol.decide` (scalar) |
| `degenerate` (noise) | `det` | `tol.decide` (scalar) |
| `parabola` (noise) | `δ` | `tol.decide` (scalar) |
| `circle` (noise) | `(big − small)/big` | `tol.decide` (scalar) |
| `axis_orientation` (noise) | `u_y` | `tol.decide` (scalar) |
