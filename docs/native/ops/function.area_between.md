# `function.area_between` — the area between two graphs

Registry 1.9 · group `function` · status `beta` · branch `null` · see [kernel.md](../kernel.md) §16.

| | |
|---|---|
| inputs | `first: function`; `second: function \| line` (family `graph_bound`, optional); `a`, `b`: `number \| point` (family `limit`, optional together; a point gives its `x`, a number may be a literal) |
| inputSets | `[first, a, b]`, `[first, second, a, b]`, `[first]`, `[first, second]`; without `second` the second boundary is the x-axis `y = 0` |
| params | `lobe` (optional; only without `a`, `b`): the number of the lobe, a whole number 1..100, absent — 1 |
| outputs | `region: region` (`stepKind` `area_between`) |
| undefined | `empty_range`, `out_of_domain`, `discontinuous`, `coincident`, `no_root_in_window`, `branch_absent`, `empty_region`, `invalid_parameter`, `upstream`; error `limit_exceeded` |
| checks | `on_both` |

## The value

One `region` (kernel.md §16): a ring per lobe, the lobes by ascending `x`.
A ring is walked counterclockwise:

1. the lower curve from left to right;
2. a vertical `line` (source `limit`) at the right limit, when `|h| > tol` there;
3. the upper curve from right to left;
4. a vertical `line` (source `limit`) at the left limit, when `|h| > tol` there.

A graph is a `graph` piece (source `first` or `second`), a line or the axis one
`line` piece (source `second` or `axis`). Which curve is the upper one is the sign
of `h` at the middle of the lobe (`h ≥ 0`: `first`). At a root (and at a limit
where `|h| ≤ tol`) both curves take `y = f(x)`, so the ring closes exactly. The
ends of a graph piece take the `y` of its corners; the inner points and the cell
midpoints of the area are the curve's values.

## The algorithm (the contract of the web copy)

    1. g: the graph of second; a line g(x) = p_y + (x − p_x)·dy/dx
       (|dx| ≤ tol.decide.scalar: "out_of_domain", detail.slot "second", decision vertical);
       without second g ≡ 0. h = f − g (null where f or g has no value).
       lobe given and not a whole number 1..100, or given with a and b → "invalid_parameter"
    2. limits a, b: lo, hi = min, max of their x
         hi − lo ≤ tol.decide                                → "empty_range"
         lo below the domain of f (or of a graph g) by more than tol.decide,
         hi above it                                         → "out_of_domain", detail.slot
         (decision domain_end; within tol the limit moves onto the end of the domain)
       no limits: roots of h (find_roots of function.root) on the x-range of the
       window B4 ∩ the domains of f and g
         None → "coincident"; no root → "no_root_in_window" (also an empty range);
         fewer than lobe + 1 distinct roots → "branch_absent"
         [lo, hi] = [r_lobe, r_lobe+1]; a double root is one root
    3. continuity on [lo, hi] of f and of a graph g:
         x_k = lo + (k·(hi − lo))/512, k = 0 … 512, x_512 = hi;  u_k = u(x_k)
         a null u_k                                          → "out_of_domain", detail.slot
         d_k = |u_k+1 − u_k|; a cell is suspect when d_k > d_k−1 and d_k > d_k+1
         (a missing neighbour does not count); for each suspect cell, left to right:
         jump bisection — m = a + (b − a)/2 while a < m < b (at most 200 halvings),
         keep the half with the larger |Δu| (the left one on a tie);
         a null u(m) → "out_of_domain"; the rest |Δu| > tol.decide → "discontinuous"
         (decision jump), detail.slot
    4. with limits: the roots of h on [lo, hi] (None → "coincident") cut it into lobes
       at every root strictly inside; without limits the lobe is [lo, hi]
       a lobe of width ≤ tol.decide is dropped (decision lobe_width)
    5. a ring per lobe (above); the area of the ring is −∫ y dx over its pieces
       (lines exactly, graphs by Simpson over 256 cells of their 257 points and the
       cell midpoints); a ring of area ≤ tol.decide·S is dropped (decision empty_region:
       h ≡ 0 on the lobe); a 65th ring → error "limit_exceeded"
    6. no ring left → "empty_region"; area = the sum of the rings

A graph piece samples `x_j = x_start + (j·(x_end − x_start))/256`, the last one
`x_end` itself; its midpoints are `x_j + (x_j+1 − x_j)/2`.

The continuity test catches a pole (`1/x`, `tan x`) and a step (`if`): the cell
of a pole has `|Δu| ≈ 4/h` against `4/(3h)` of its neighbours; a smooth steep
graph passes, its rest after the bisection is rounding noise.

## Degenerate cases

- A tangency (a double root): in lobe mode it is one root, so `x²` and the axis
  give `branch_absent`; with limits it splits the area into two lobes that touch.
- `sqrt(x)` and the axis: the root at the end of the domain is the only one —
  `branch_absent`.
- `a = b` — `empty_range`; a limit that is an undefined point — `upstream`.
- `f ≡ g` — `coincident`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `vertical` | `dx` of the line | `tol.decide.scalar` |
| `empty_range` | `hi − lo` | `tol.decide` (length) |
| `domain_end` | `lo − d_lo`, `d_hi − hi` | `tol.decide` (length) |
| `coincident` | `max |h_k|` | `tol.decide` (length) |
| `tangent` | `min |h|` at a local minimum | `tol.decide` (length) |
| `jump` | the rest `|Δu|` of a suspect cell | `tol.decide` (length) |
| `lobe_width` | the width of a lobe | `tol.decide` (length) |
| `limit_gap` | `|h|` at a limit | `tol.decide` (length) |
| `empty_region` | the area of a ring | `tol.decide · S` (area) |

`tangent`, `jump` and `limit_gap` are noise decisions for the fixture generator
(kernel.md §6): the rest of the bisection of a continuous graph and the gap at a
limit placed at a common point are rounding noise.

## Checks

`on_both` — the largest `|f(x) − g(x)|` at the vertices where the two boundaries
meet without a vertical edge (the roots, and the limits with `|h| ≤ tol`); `0`
without such vertices.
