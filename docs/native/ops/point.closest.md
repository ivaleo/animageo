# `point.closest` — nearest point of a path

Registry 1.4 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `path: path` |
| outputs | `foot: point` |
| undefined | `upstream`; registry 1.9: `out_of_domain` (a graph without a value in its search interval) |
| checks | `on_path` |

The point of a path nearest to `point` — the same projection as
`native.project` (`point.on_path.md`): clamped to the ends of a segment, a
ray, an arc and a polyline; the centre of a circle gives `θ = 0` (ties go to
the smallest parameter). GeoGebra `ClosestPoint(path, P)`.

Registry 1.10: a `locus` is also a path. Project onto its continuous
sampled runs (including the closing link of a closed locus); do not join
null samples or jumps over `0.25·S`. Ties select the smallest normalized
sample parameter. An empty or stationary locus gives `empty_locus` or
`degenerate_locus`. See [point.on_path](point.on_path.md#a-locus-registry-110).

Registry 1.9: the path may be a conic (the family `path`, kernel.md §16):
the exact nearest point of an ellipse, of the nearest branch of a hyperbola
(the branch on the side of `point` along the axis, `+1` on the conjugate
axis) and of a parabola; or a graph: the nearest point found on a grid over
the window `B4` of the document bounds and the abscissa of `point`, inside
the domain. Formulas in [point.on_path](point.on_path.md#inverse-nativeprojectdoc-id-x-y).

## Value

    f = frame(path)
    (t, branch) = locate(f, P, tol.decide, bounds)      (branch: a hyperbola, else 1)
    no t (a graph without a value)  →  undefined "out_of_domain"
    foot = point_at(f, t, branch)

Noise decisions (registry 1.9): `closest_axis` — the coordinates `Y` (and
`X` of an ellipse) of `point` in the frame of a conic against `tol.decide`;
`closest_branch` — `X` of a hyperbola.

## Checks

- `on_path`: `distance_to_path(foot)` (a conic: its focal residual; a graph: `|y − f(x)|`)
