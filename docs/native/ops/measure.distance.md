# `measure.distance` — distance from a point to a figure

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `point: point`, `to: figure` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`. The distance to a path is `distance_to_path`
(kernel.md §5.5): to the clamped part of a segment or a ray, the sides of a
polygon, the links of a polyline, the arc itself, the boundary of a sector;
to a circle `| |P − c| − r |`.

## Value

    to a point: value = hypot(to − point)
    otherwise:  value = distance_to_path(point, to)
    number = {value, unit: "length"}

## Degeneracy decisions

None.

## Checks

None.
