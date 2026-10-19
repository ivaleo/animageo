# `function.root` — zeros of a function on an interval

Registry 1.6 · group `function` · status `beta` · branch policy `roots_ascending` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `function: function`, `a: number`, `b: number` (a number element or a literal) |
| params | `count` (optional, default 1: the number of slots, a whole number 1..100) |
| outputs | `root: point`, repeated: `root.1 … root.count` |
| undefined | `empty_range`, `coincident`, `no_root_in_window`, `branch_absent`, `upstream` |
| checks | `on_graph` |

## Slots

`root.k = (x_k, 0)`, the roots in ascending `x`; a double root fills two
consecutive slots, both with `detail: {"multiplicity": 2}`. Slots beyond the
roots found are `branch_absent`; no root at all — `no_root_in_window` in every
slot. A `count` that is not a whole number in `[1, 100]` gives the operation no
slots (its elements are `error/schema`).

## The search (the contract of the web copy)

    [lo, hi] = [a, b] ∩ domain;  empty or hi − lo ≤ tol.decide  → every slot "empty_range"
    x_k = lo + (k·(hi − lo))/512,  k = 0 … 512;  h_k = f(x_k) (null where f has no value)
    all defined |h_k| ≤ tol.decide (one at least)               → every slot "coincident"
    1. h_k = 0 exactly: a root at x_k; multiplicity 2 when both neighbours exist,
       are non-zero and have the same sign
    2. h_k, h_k+1 of opposite signs: bisection, m = lo + (hi − lo)/2 while lo < m < hi
       (at most 200 halvings), keep the half with the sign change, an exact 0 stops;
       x* = the end with the smaller |h| (lo on a tie);
       a root when |h(x*)| ≤ max(tol.decide, 10⁻⁶·min(|h_k|, |h_k+1|))  (a pole or a jump is not)
    3. 0 < k < 512, h_k−1, h_k, h_k+1 non-zero of one sign, |h_k| ≤ |h_k−1| and |h_k| < |h_k+1|:
       golden section of |h| over [x_k−1, x_k+1] (100 steps, c = b − φ⁻¹(b − a), d = a + φ⁻¹(b − a),
       g(c) ≤ g(d) keeps [a, d] else [c, b]; the better of c and d, c on a tie; no value counts as +∞);
       a double root when the minimum ≤ tol.decide  (decision tangent)
    roots sorted by x; a root within tol.decide of the previous one merges into it
    (the larger multiplicity stays)

Two simple roots inside one cell read as one double root; a root of odd
multiplicity above 1 is found by its sign change (multiplicity 1).

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `empty_range` | `hi − lo` | `tol.decide` (length) |
| `coincident` | `max |h_k|` | `tol.decide` (length) |
| `tangent` (per local minimum of `|h|`) | `min |h|` | `tol.decide` (length) |

`tangent` is a noise decision for the fixture generator (kernel.md §6).

## Checks

`on_graph` — the largest `|y − f(x)|` of the defined slots.
