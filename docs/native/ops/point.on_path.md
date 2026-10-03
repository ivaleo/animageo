# `point.on_path` — point on a path

Registry 1.1 · group `point` · path parameter `carrier/v1` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `path: path` (`line`, `segment`, `ray`, `circle`, `polygon`) |
| outputs | `point: point` |
| free | `{kind: "pathParameter"}` — the value comes from `inputs[elementId]` |
| undefined | `upstream` |
| checks | `on_path` |

## Input

    {"kind": "pathParameter", "value": t, "branch"?: -1 | 1}

`t` is a finite number. `branch` is reserved for paths with two branches
(hyperbolas, a later registry); the paths of registry 1.1 read it and ignore
it. No valid input value (missing, another kind, a non-finite `t`, a branch
other than ±1) → `error/schema`, as for `point.free`. Path parameters do not
take part in the scene scale `S` (only free points do).

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

Defaults for a new point (`paths.<type>.default`): segment, line, ray and
polygon `0.5`, circle `π/4`.

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
  circle `| hypot(x − cx, y − cy) − r |`, a polygon the minimum over its sides.
