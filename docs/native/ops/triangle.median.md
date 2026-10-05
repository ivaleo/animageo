# `triangle.median` — median of a triangle

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertex: point`, `side: segment` |
| outputs | `median: segment`, `midpoint: point` |
| undefined | `zero_length` (slot `median`), `upstream` |
| checks | `midpoint` |
| orientation | `vertex_to_midpoint` |

A pair `BC` in «Команды» becomes a hidden `segment.by_points(B, C)`.

## Value

    M = ((a_x + b_x)/2, (a_y + b_y)/2)      the formula of point.midpoint (a, b the side ends)
    m = |V − M|
    m ≤ tol.decide → median "zero_length"; midpoint is defined (also for a side of zero length)
    median = {a: V, b: M, length: m}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | `m` | `tol.decide` |

## Checks

- `midpoint`: `| |M − a| − |b − M| |`
