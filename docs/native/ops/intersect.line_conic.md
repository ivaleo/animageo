# `intersect.line_conic` — common points of a linear object and a conic

Registry 1.6 · group `intersect` · status `beta` · branch policy `line_param_order` · see [intersect.line_circle](intersect.line_circle.md).

| | |
|---|---|
| inputs | `line: linear` (`line` \| `segment` \| `ray`), `conic: conic` |
| outputs | `first: point`, `second: point` |
| undefined | `no_intersection`, `outside_part`, `zero_length`, `branch_absent`, `upstream` |
| checks | `on_both` |

## Value

The carrier `(p, dir, L)` of `line` is the one of
[intersect.line_line](intersect.line_line.md). In the frame of the conic
(`u` along `axis`, `v` along `n` from `c`, a parabola from its vertex):
`pu, pv` the coordinates of `p`, `du = dir·axis`, `dv = dir·n`. On the line
`g(t) = α t² + 2β t + γ`:

    ellipse (k = (a/b)²), hyperbola (k = −(a/b)²):
        α = du² + k·dv²;  β = pu·du + k·pv·dv;  γ = pu² + k·pv² − a²;  unit = 2a
        hyperbola: w = du² + (a/b)²·dv²
            |α/w| ≤ tol.decide (scalar) (asymptote):           a line parallel to an asymptote
                m = β/sqrt(w); |m| ≤ tol.decide (asymptote)    → both "no_intersection" (the asymptote)
                else one point t = −γ/(2β)
    parabola:
        α = dv²;  β = pv·dv − p·du;  γ = pv² − 2p·pu;  unit = 2p
        |dv| ≤ tol.decide (scalar) (parallel):                 a line parallel to the axis: one point t = −γ/(2β)
    Δ = β² − αγ;  m = Δ / (unit·|α|)                  (decision tangent, a length)
    m < −tol.decide                → both "no_intersection"
    |m| ≤ tol.decide               → t1 = t2 = −β/α, detail {"multiplicity": 2} on both
    else t1, t2 = (−β ∓ sqrt(Δ))/α, ascending
    one point: first = it, second "branch_absent"
    each slot: the part filter of intersect.line_circle ("outside_part", detail {"slot": "line"})

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (segment) | `L` | `tol.decide` (length) |
| `parallel` (parabola) | `dv` | `tol.decide` (scalar) |
| `asymptote` (hyperbola) | `α/w`, then `β/√w` | `tol.decide` (scalar), (length) |
| `tangent` (noise) | `m` | `tol.decide` (length) |
| `outside_part` (per slot) | `t`, `t − L` | `tol.decide` (length) |

## Checks

`on_both` — the larger of the distance to the carrier line and the focal
residual of the conic (see [conic.five_points](conic.five_points.md)); runs
when `second` is absent.
