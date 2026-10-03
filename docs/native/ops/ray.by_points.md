# `ray.by_points` — ray from a point through a point

Registry 1.1 · group `line` · orientation `origin_to_through` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `origin: point`, `through: point` |
| outputs | `ray: ray` |
| undefined | `coincident_points`, `upstream` |
| checks | `origin`, `through` |

## Value

    dx = throughx − originx
    dy = throughy − originy
    L  = hypot(dx, dy)
    if L ≤ tol.decide:            → undefined, reason "coincident_points"
    ray = {origin: [originx, originy], dir: [dx / L, dy / L]}

`dir` is a unit vector from `origin` towards `through`.

As a carrier (intersections, `docs/native/ops/intersect.*.md`) a ray is
`p = origin`, `dir`, with no length and the part filter `s ≥ −tol.decide`
for the parameter `s` along `dir`.

As a path (`point.on_path`) a ray made by this operation uses the frame
`o = origin`, `v = through − origin`, `t ≥ 0` (`t < 0` is clamped to 0); a ray
made by another operation uses `o = origin`, `v = dir`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `coincident_points` | `L` | `tol.decide` (length, `1e-10·S`) |

## Checks

- `origin`: `hypot(rayOriginx − originx, rayOriginy − originy)`
- `through`: distance from `through` to the carrier line,
  `| (x − originx)·diry − (y − originy)·dirx |`
