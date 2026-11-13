# `point.on_path` — point on a path

Registry 1.1 · group `point` · path parameter `carrier/v1` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `path: path` (`line`, `segment`, `ray`, `circle`, `polygon`; 1.4: `arc`, `sector`, `polyline`; 1.7: `circlesegment`; 1.9: `conic`, `function`; 1.10: `locus`) |
| outputs | `point: point` |
| free | `{kind: "pathParameter"}` — the value comes from `inputs[elementId]` |
| undefined | `upstream`; registry 1.9: `path_kind_changed` (a conic), `out_of_domain` (a graph); 1.10: `empty_locus`, `degenerate_locus`, `discontinuous` (a locus); `non_finite` (any op) |
| checks | `on_path` |

## Input

    {"kind": "pathParameter", "value": t, "branch"?: -1 | 1,
     "pathKind"?: "ellipse" | "hyperbola" | "parabola"}

`t` is a finite number. `branch` picks the branch of a hyperbola (registry
1.9, default `1`); other paths read it and ignore it. `pathKind` (registry
1.9) is the kind of conic the parameter was written for: a conic of another
kind gives `undefined/path_kind_changed`, and when the kind returns the same
`t` applies again; without it any kind takes `t`; other paths ignore it.
No valid input value (missing, another kind, a non-finite `t`, a branch
other than ±1, a `pathKind` other than the three names) → `error/schema`, as
for `point.free`. Path parameters do not take part in the scene scale `S`
(only free points do).

## Value: the frame of the path (`carrier/v1`)

The parameter is measured in the frame of the path's definition, so the
point moves with the path (`ops/v1/_types.json` → `paths`):

| path | kind | frame | parameter |
|---|---|---|---|
| segment | affine | `o = a`, `v = b − a` | `t` clamped to `[0, 1]` |
| line by `line.by_points` | affine | `o = a`, `v = b − a` (the producer's points) | any `t` |
| line by `line.parallel`, `line.perpendicular` (1.2) | affine | `o = point`, `v = dir` | any `t` |
| line by `line.perpendicular_bisector` (1.2) | affine | `o = mid(a, b) = ((ax + bx)/2, (ay + by)/2)`, `v = dir` | any `t` |
| line by `line.angle_bisector` (1.2) | affine | `o = vertex`, `v = dir` | any `t` |
| other line | affine | `o = p`, `v = dir` | any `t` |
| ray by `ray.by_points` | affine | `o = origin`, `v = through − origin` | `t < 0` clamped to 0 |
| other ray | affine | `o = origin`, `v = dir` | `t < 0` clamped to 0 |
| circle | angle | centre `c`, radius `r` | angle from +x |
| polygon (`n` vertices `V`) | perimeter | the sides in order | `[0, n)`, wraps |
| conic (1.9) | conic | `u = axis`, `n = (−u_y, u_x)` of the conic value | by its kind, below |
| function (1.9) | graph | `y = f(x)` | `x`, clamped to the domain |

    affine:     t' = clamp(t)                (segment: [0, 1]; ray: t' ≥ 0; line: t' = t)
                point = (ox + t'·vx, oy + t'·vy)
    angle:      point = (cx + r·cos t, cy + r·sin t)
    perimeter:  t' = t − n·floor(t / n)
                if t' < 0:  t' = t' + n
                if t' ≥ n:  t' = 0
                k = floor(t'), f = t' − k
                A = V[k], B = V[(k + 1) mod n]
                point = (Ax + f·(Bx − Ax), Ay + f·(By − Ay))

A zero-length segment or a polygon with coinciding vertices still gives a
point (`a`, a vertex). The parameter `k` of a polygon picks side
`side.(k + 1)`.

### A conic (registry 1.9)

    pathKind present and ≠ kind of the conic  →  undefined "path_kind_changed"
    ellipse:    point = c + a·cos t·u + b·sin t·n           (t wraps over 2π)
    hyperbola:  point = c + β·a·cosh t·u + b·sinh t·n       (β = branch, default 1)
    parabola:   point = V + (p·t²/2)·u + p·t·n              (V the vertex)

`u` is the axis of the value (`_types.json` → `types.conic`): the major axis
of an ellipse (a circle conic: `a = b`, `u = (1, 0)`, so `t` is the angle
from +x as on a circle), the transverse axis of a hyperbola (branch `+1` on
the side of `+u`), the axis of a parabola from the vertex towards the focus.
So `t` of an ellipse is the eccentric anomaly measured from its own axis.
The axis of a conic value is canonical (`u_y > 0`; on the x direction
`u_x > 0`): where a turning ellipse crosses that direction the point moves
by `π`, and a hyperbola point changes side — a product that wants a
continuous motion follows the conic with `native.project`. `cosh`/`sinh`
past the float range give `undefined/non_finite`. A degenerate conic is not
a value: the point is `upstream`.

### A graph (registry 1.9)

    x = clamp(t, lo, hi)          (the domain [lo | null, hi | null] of the value)
    y = f(x);  no value  →  undefined "out_of_domain"
    point = (x, y)

The parameter is the abscissa, as for `point.on_function`: a domain clamps
it to its ends (the ends belong to the graph); a gap of a piecewise `If`
without `else`, a pole or a complex value has no point.

### A locus (registry 1.10)

The ordered `points` of `locus.of_point` form a sampled path. Append the
first sample when `closed` is true, retaining any `null` samples. With `n`
samples after that append:

    t' = clamp(t, 0, 1); w = t' · (n − 1)
    k = min(floor(w), n − 2); f = w − k
    point = points[k] + f · (points[k + 1] − points[k])

This is GeoGebra's normalized sample-index convention, not arc length or
the mover parameter in `range`. Each link occupies the same parameter
interval, even if its length differs. The closing link occupies the last
interval of a closed locus; `t = 1` reaches the first point. Parameters
outside `[0,1]` clamp, including on a closed locus.

GeoGebra's [PathNormalizer](https://github.com/geogebra/geogebra/blob/main/source/shared/common/src/main/java/org/geogebra/common/kernel/PathNormalizer.java)
clamps the supplied fraction before mapping it to the path's parameter
range; [GeoLocusND](https://github.com/geogebra/geogebra/blob/main/source/shared/common/src/main/java/org/geogebra/common/kernel/geos/GeoLocusND.java)
uses `[0, sampleCount − 1]` and interpolates neighbouring sample indices.

A `null` endpoint or a distance between neighbours greater than `0.25·S`
breaks the path, as in rendering. A finite sample at an exact endpoint is
available; between the ends of a break the point is
`undefined/discontinuous`. No finite samples gives `empty_locus`; no
continuous link longer than `tol.decide` gives `degenerate_locus`. Repeated
samples on an otherwise usable path are allowed. Gaps keep their sample
indices: neither projection nor dragging compresses the parameter range.

Projection examines each continuous link and every finite sample, clamps
the projection to the link's endpoints, and returns `(k + f)/(n − 1)`.
Candidates within `tol.decide` of the minimum distance tie by the smallest
parameter. An empty or degenerate locus has no projection (`None`). Drag
uses that same projection, moves continuously within each run and may
switch to the nearest run across a gap; it never draws a bridge across
the gap. At an outer endpoint it reports `clamped` if the target is away
from the endpoint. A hint through a locus point changes the same clamped
parameter. `Construction.tparam_from_coords` on the native bridge uses
the native frame, preserving the original indices and closing link.

GeoGebra `Point(locus)` imports to this operation, projecting saved
`<coords>` onto the current sampled path and comparing the resulting point
with those coordinates. A mismatch is `differs/value_mismatch`.
`Point(locus, t)` instead uses the dependent
[`point.on_locus`](point.on_locus.md) so a numeric reference remains live.

Defaults for a new point (`paths.<type>.default`): segment, line, ray and
polygon `0.5`, circle `π/4`; 1.9: conic `π/4`, function `0`.
Registry 1.10: locus `0.5`.

## Inverse: `native.project(doc, id, (x, y))`

The parameter of the nearest point of the path (`id` is the path or a
`point.on_path` point); `None` when the path is not defined; `ValueError`
when the element is not a path. `tol = tol.decide` (length) of the scene.

    affine:     vv = vx² + vy²;  vv ≤ tol² → 0
                t = ((x − ox)·vx + (y − oy)·vy) / vv, clamped as above
    angle:      hypot(x − cx, y − cy) ≤ tol → 0
                θ = atan2(y − cy, x − cx); θ < 0 → θ + 2π; θ ≥ 2π → 0
    perimeter:  for every side k = 0…n−1: f = the projection onto side k
                clamped to [0, 1] (0 for a zero side), d = distance;
                dmin = min d; t = the smallest k + f with d ≤ dmin + tol;
                t ≥ n → 0

Ties (the centre of a circle, the corner of a polygon) go to the smallest
parameter. `point.on_path` at `project(…)` is the nearest point of the path.

### A conic (registry 1.9)

`(X, Y)` is the point in the frame of the conic: `X = (P − o)·u`,
`Y = (P − o)·n`, `o` the centre (the vertex of a parabola). `|Y| ≤ tol →
Y = 0`. A root `root(g, lo, hi)` (`g > 0` left of it) halves while
`lo < m < hi`, `m = lo + (hi − lo)/2`, at most 1100 times: `g(m) > 0 →
lo = m`, else `hi = m`; the result is the last `m`.

    ellipse (a ≥ b; Eberly, "Distance from a point to an ellipse"):
        |X| ≤ tol → X = 0
        y0 = |X|, y1 = |Y|
        y1 > 0, y0 > 0:  z0 = y0/a, z1 = y1/b, g = z0² + z1² − 1
                         g = 0 → (x0, x1) = (y0, y1)
                         else r = (a/b)², n0 = r·z0
                              s = root(F, z1 − 1, g < 0 ? 0 : hypot(n0, z1) − 1),
                                  F(s) = (n0/(s + r))² + (z1/(s + 1))² − 1
                              (x0, x1) = (r·y0/(s + r), y1/(s + 1))
        y1 > 0, y0 = 0:  (x0, x1) = (0, b)
        y1 = 0:          y0·a < a² − b² → q = y0·a/(a² − b²), (x0, x1) = (a·q, b·√(1 − q²))
                         else (x0, x1) = (a, 0)
        X < 0 → x0 = −x0;  Y < 0 → x1 = −x1
        t = atan2(x1/b, x0/a);  t < 0 → t + 2π;  t ≥ 2π → 0
    hyperbola:
        branch = −1 when X < −tol, else +1;  X' = branch·X
        Y = 0:  X' > (a² + b²)/a → t = −acosh(a·X'/(a² + b²)), else t = 0
        Y ≠ 0:  λ = root(F, −a², b²),  F(λ) = (a·X'/(a² + λ))² − (b·|Y|/(b² − λ))² − 1
                t = asinh(b·|Y|/(b² − λ)),  negated when Y < 0
    parabola:
        Y = 0:  X > p → t = −√(2(X/p − 1)), else t = 0
        Y ≠ 0:  P = 2(1 − X/p), Q = −2|Y|/p
                s = root(−(s³ + P·s + Q), 0, max(1, √(|P| + |Q|))),  t = s, negated when Y < 0

On the major axis of an ellipse inside the centre of curvature two points
are nearest: the side `+n` (the smaller `t`). On the axis of a hyperbola or
a parabola past the centre of curvature the two points are symmetric: the
smaller `t` (the side `−n`). The centre of a circle conic gives `0`, the
centre of an ellipse `π/2`, a point on the conjugate axis of a hyperbola the
branch `+1`. `native.project` gives `t`; the branch of a hyperbola is the
nearest one (`native.project_input` gives both, kernel.md §8).

### A graph (registry 1.9)

    (x0, x1) = the x-range of the window B4 of the bounds (as intersect.function_function)
    a0 = min(x0, X), a1 = max(x1, X)               (X, Y: the point)
    lo given: a0 = max(a0, lo), a1 = max(a1, lo);  hi given: a0 = min(a0, hi), a1 = min(a1, hi)
    d²(x) = (x − X)² + (f(x) − Y)²,  no value where f has none
    nodes x_k = a0 + k·(a1 − a0)/512, k = 0…512;  k* = the first node of the least d²
    no node with a value → no point (None; point.closest: out_of_domain)
    (x, d) = golden_min(d², x_max(k*−1, 0), x_min(k*+1, 512))        (function.root.md: 100 steps, no value = +∞)
    t = x when d < d²(x_k*), else x_k*

The nearest point of a piecewise graph may be the open end of a piece (a
gap without a value): the search approaches it to the resolution of the
golden-section search. A tie between two pieces goes to the better grid
node, not exactly to the smaller `t`.

## Checks

- `on_path`: distance from the point to the path: a segment and a ray as the
  clamped part (`hypot` to the nearest point), a line as the carrier line, a
  circle `| hypot(x − cx, y − cy) − r |`, a polygon the minimum over its sides;
  1.9: a conic its focal residual (zero on the curve, as `on_both` of
  registry 1.8), a graph `|y − f(x)|`.
