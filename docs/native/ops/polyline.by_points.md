# `polyline.by_points` — polyline through points

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `points: point[]` (min 2) |
| outputs | `polyline: polyline` |
| undefined | `upstream` |
| checks | `vertices` |

The open polyline through the points in order (at least two).

## Value

    vertices = points in order
    length = Σ |V[i+1] − V[i]|

## Checks

- `vertices`: the largest distance between vertices and inputs
