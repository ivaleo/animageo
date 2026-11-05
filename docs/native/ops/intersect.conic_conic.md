# `intersect.conic_conic` — common points of two conics

Registry 1.8 · group `intersect` · status `beta` · branch policy `first_curve_order` · see [intersect.circle_circle](intersect.circle_circle.md), [intersect.line_conic](intersect.line_conic.md).

| | |
|---|---|
| inputs | `first: conical` (`conic` \| `circle` \| `arc`), `second: conical` |
| outputs | `first: point`, `second: point`, `third: point`, `fourth: point` |
| undefined | `no_intersection`, `coincident`, `concentric`, `branch_absent`, `outside_part`, `upstream` |
| checks | `on_both` |

Two conics have at most four common points; the four slots hold them in
the order along the first input. The implementation is
`animageo/native/kernel/conic_meet.py` and `kernel/ops/meet.py`; the steps
below are the contract of every copy (the arithmetic in this order).

## Two circular inputs

When both inputs are `circle` or `arc`, `first` and `second` are the slots
of [intersect.circle_circle](intersect.circle_circle.md) before its part
filter (policy `circle_side`, the same decisions); `third` and `fourth` are
`branch_absent`, or the reason of `first` when `first` and `second` are both
undefined (`no_intersection`, `concentric`, `coincident`). Then the part
filter below. So `conic_conic` of two circles equals `circle_circle` slot for
slot.

## Curves

A curve is the value of a `conic`, or a circle (an arc is its carrier
circle): `o` the centre (a parabola: its vertex), `u` the unit axis, `n = (−u.y, u.x)`
(the axis turned by +90°); a circle is the ellipse `a = b = r` with
`u = (1, 0)`; a circle conic (`a = b`) is *round* as well. In the frame of a
curve, `U = (X − o)·u`, `V = (X − o)·n`, and its equation in lengths² is

    ellipse:    G = U² + k·V² − a²,  k = (a/b)²,   unit = 2a
    hyperbola:  G = U² + k·V² − a²,  k = −(a/b)²,  unit = 2a
    parabola:   G = V² − 2p·U,                     unit = 2p

`measure(X) = G(X)/unit` is a length near the curve (its distance to first
order), the value of the decisions below.

## Value

**The param curve.** The first input when it is an ellipse (or a circle),
else the second when that is one, else the first; the other curve is
*other*. A point of the param curve is given by its local coordinates
`(x', y')`, `X = o + x'·u + y'·n`; in the frame of other

    dx, dy = o_param − o_other;  U0 = dx·u_o.x + dy·u_o.y;  V0 = dx·n_o.x + dy·n_o.y
    Ux = u_p·u_o;  Uy = n_p·u_o;  Vx = u_p·n_o;  Vy = n_p·n_o     (dot products, x·x + y·y)
    U = U0 + x'·Ux + y'·Uy;  V = V0 + x'·Vx + y'·Vy

(`_Relative`). Along a rational point `(xh, yh, wh)` of the param curve
(polynomials of the parameter, `x' = xh/wh`, `y' = yh/wh`)

    Uh = U0·wh + Ux·xh + Uy·yh;  Vh = V0·wh + Vx·xh + Vy·yh       (poly.add of poly.scale, in this order)
    P  = Uh·Uh + k·(Vh·Vh) − a²·(wh·wh)                            other an ellipse or a hyperbola
    P  = Vh·Vh − 2p·(Uh·wh)                                        other a parabola

is `G·wh²`, a polynomial of degree four at most (coefficients from the
constant term up; `poly.mul`: `out[i + j] += a[i]·b[j]`, `i` then `j`
ascending; `poly.add` term by term in the order of the arguments).

**Coincidence** (decision `same_curve`, noise). The measure of other at the
samples of the param curve; when the largest `|measure|` is within
`tol.decide` the curves coincide: all four slots `coincident`. Samples:
an ellipse `(a·cx, b·sy)` for the eight `ELLIPSE_DIRECTIONS`
`(1, 0), (h, h), (0, 1), (−h, h), (−1, 0), (−h, −h), (0, −1), (h, −h)`,
`h = Math.SQRT1_2`; a parabola `(p·t²/2, p·t)` for `t = −2, −1, 0, 1, 2`; a
hyperbola `(σ·a·(w + 1/w)/2, b·(w − 1/w)/2)` for `(σ, w) = (1, 0.5), (1, 1),
(1, 2), (−1, 1), (−1, 2)`. Five points fix a conic, so two different
conics never pass the test.

**An ellipse as the param curve.** The chart sends `t = ±∞` to the
sample direction where `|measure|` is the largest (the first of equal
ones), so no root lies there: `(c0, s0)` the opposite of that direction,

    x' = a·(c0·(1 − t²) − 2·s0·t)/(1 + t²);   y' = b·(s0·(1 − t²) + 2·c0·t)/(1 + t²)
    xh = [a·c0, −2a·s0, −a·c0];  yh = [b·s0, 2b·c0, −b·s0];  wh = [1, 0, 1]

`P` is trimmed (trailing exact zeros dropped); degree `n = 0` gives no
point; else the roots are searched on `[−B, B]`, `B = 1 + max |P[i]/P[n]|`
(Cauchy; the loop `B = max(B, 1 + |P[i]/P[n]|)` from `B = 1`, `i = 0 … n − 1`).

**A parabola as the param curve** (other is a parabola or a hyperbola).
`x' = p·t²/2`, `y' = p·t`: `xh = [0, 0, p/2]`, `yh = [0, p]`, `wh = [1]`,
on `[−T, T]`, `T = √(2·R'/p)`.

**A hyperbola as the param curve** (other is a hyperbola or a parabola).
Each branch `σ = −1`, then `σ = +1`: `x' = σ·a·(w + 1/w)/2`,
`y' = b·(w − 1/w)/2` (`w = e^t`): `xh = [σa/2, 0, σa/2]`, `yh = [−b/2, 0, b/2]`,
`wh = [0, 1]`, on `[1/W, W]`, `q = R'/a`, `W = q + √((q − 1)·(q + 1))`; no
point when `q ≤ 1`.

`R' = R + |o − Z|`: `Z` the centre of the window `B4`
(`viewDefaults.bounds`, or `defaultBounds`, scaled 4 times about its centre,
as the graphs of functions), `R` its half-diagonal `hypot(x1 − x0, y1 − y0)/2`
— every point of `B4` lies within `R'` of `o`. Two curves that are both
unbounded are thus searched near `B4` only; a point beyond `R'` is not
found.

**Roots** (`_roots`, `kernel/poly.py`). On `[lo, hi]`: the breakpoints are
`lo`, the roots of `P'` inside `(lo, hi)` where it changes sign (`sign_roots`,
recursively: the breakpoints of `P'` are `lo`, the sign-change roots of `P''`
and `hi`; a linear polynomial has the root `−c0/c1` when `lo < −c0/c1 < hi`;
an interior breakpoint where the value is exactly `0` is a root; an interval
whose ends have nonzero values of opposite signs holds one root, found by
the bisection of [function.root](function.root.md)) and `hi`; values by
Horner. Then:

    each interior breakpoint (an extremum of P): m = measure of other at its point
        |m| ≤ tol.decide (decision tangent, noise) → a root of multiplicity 2, its value counts as 0
    lo or hi where P is exactly 0                  → a simple root
    each interval of breakpoints with nonzero values of opposite signs → a simple root (bisection)
    roots ascending by the parameter

`P` is monotone between two breakpoints, so each interval holds one root at
most, and two close roots are separated as soon as the extremum between
them is found. A contact of a higher order counts as a tangency (two
slots) when it is even, as a simple root when it is odd.

**Points.** `X = o + x'·u + y'·n` of each root, with its multiplicity. No
point: all four slots `no_intersection`.

## Branches: `first_curve_order`

The points are sorted by `key(X)` (ties keep the order found); a point of
multiplicity 2 fills two consecutive slots, both
`{"multiplicity": 2}` in `detail` (as `intersect.line_conic`); slots beyond
the points (four at most) are `branch_absent`. The key on the first input:

- **a circle or an ellipse** (`circle`, an ellipse `conic`): `c1` its
  centre, `c2` the centre of the second input (a parabola: its vertex),
  `d = c2 − c1`, `dist = hypot(d)`; `dist ≤ tol.decide` (decision
  `same_centre`, noise): `d` is the axis of the first input, or of the second when
  the first is round (a circle: `(1, 0)`); else `d = d/dist`. With
  `R = X − c1`, `along = d·R`, `across = d.x·R.y − d.y·R.x`:
  key `(0, θ)`, `θ = atan2(across, along)` in `[0, 2π)` (`+2π` when
  negative, `2π` itself is `0`); when `along > 0` and `|across| ≤ tol.decide`
  (decision `seam`, noise) `θ = 0`. Counterclockwise from the direction to the
  second centre: for two circles `first` is to the left of `c1 → c2`, as
  `circle_side`.
- **a hyperbola**: key `(0, V)` on the branch `U < 0`, `(1, V)` on the
  branch `U > 0` (`U = R·u`, `V = R·n`, `R = X − c`).
- **a parabola**: key `(0, V)`, `V = (X − vertex)·n`.
- **an arc**: key `(0, φ)`, `φ = θ − a0` in `[0, 2π)` (`θ` the direction of
  `X − c` in `[0, 2π)`); when `r·(2π − φ) ≤ tol.decide` (decision `seam`)
  `φ = 0`. By the fraction of the arc from `a0`.

**The seam.** The order is a function of the points, so moving the whole
figure never swaps slots, and a slot keeps its point while it moves — except
where a point crosses the seam of the first input: the ray `c1 → c2` (a
circle or an ellipse), the direction `a0` (an arc). There the point leaves
the last defined slot and takes `first` (or the reverse), and the others
shift by one. A hyperbola or a parabola as the first input has no seam
(the key is monotone along each branch).

## Part filter

After the order, a slot is kept on an arc input only when its point lies
on the arc (`on_arc` of [intersect.line_circle](intersect.line_circle.md)),
else `outside_part` with `detail {"slot": "first"}` or `{"slot": "second"}`
(the first input is tested first). The slots are fixed on the carrier circle
before the filter, as `intersect.circle_circle`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `concentric`, `coincident`, `tangent` | as `intersect.circle_circle` (two circular inputs) | `tol.decide` (length) |
| `same_curve` (noise) | the largest `|measure|` of the samples | `tol.decide` (length) |
| `tangent` (noise) | `measure` at an extremum of `P` | `tol.decide` (length) |
| `same_centre` (noise) | `dist = |c2 − c1|` | `tol.decide` (length) |
| `seam` (noise) | `across` (along > 0); arc: `r·(2π − φ)` | `tol.decide` (length) |
| `outside_part` (per slot, arc) | as `on_arc` | `tol.decide` (length) |

| situation | result |
|---|---|
| the same conic (or the same circle) | four `coincident` |
| no common point (incl. a curve outside `R'` of an unbounded param curve) | four `no_intersection` |
| concentric circular inputs of different radii | four `concentric` |
| `k < 4` points | the points, then `branch_absent` |
| a tangency | its point in two consecutive slots, both `{"multiplicity": 2}` |
| a point off an arc input | that slot `outside_part` |

## Checks

`on_both` — the largest residual of a defined point on both inputs: the
focal residual of a conic (see [conic.five_points](conic.five_points.md)),
`| |X − c| − r |` of a circle or of the carrier of an arc. It runs when
`third` and `fourth` are absent.
