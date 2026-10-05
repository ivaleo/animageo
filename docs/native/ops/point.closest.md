# `point.closest` — nearest point of a path

Registry 1.4 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `path: path` |
| outputs | `foot: point` |
| undefined | `upstream` |
| checks | `on_path` |

The point of a path nearest to `point` — the same projection as
`native.project` (`point.on_path.md`): clamped to the ends of a segment, a
ray, an arc and a polyline; the centre of a circle gives `θ = 0` (ties go to
the smallest parameter). GeoGebra `ClosestPoint(path, P)`.

## Value

    f = frame(path),  t = project(f, P, tol.decide)
    foot = point_at(f, t)

## Checks

- `on_path`: `distance_to_path(foot)`
