# `point.on_path` — point on a path

Registry 1.1 · group `point` · path parameter `carrier/v1` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `path: path` (`line`, `segment`, `ray`, `circle`, `polygon`; 1.4: `arc`, `sector`, `polyline`; 1.7: `circlesegment`; 1.9: `conic`, `function`) |
| outputs | `point: point` |
| free | `{kind: "pathParameter"}` — the value comes from `inputs[elementId]` |
| undefined | `upstream`; registry 1.9: `path_kind_changed` (a conic), `out_of_domain` (a graph); `non_finite` (any op) |
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

Defaults for a new point (`paths.<type>.default`): segment, line, ray and
polygon `0.5`, circle `π/4`; 1.9: conic `π/4`, function `0`.

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

## Checks

- `on_path`: distance from the point to the path: a segment and a ray as the
  clamped part (`hypot` to the nearest point), a line as the carrier line, a
  circle `| hypot(x − cx, y − cy) − r |`, a polygon the minimum over its sides;
  1.9: a conic its focal residual (zero on the curve, as `on_both` of
  registry 1.8), a graph `|y − f(x)|`.
