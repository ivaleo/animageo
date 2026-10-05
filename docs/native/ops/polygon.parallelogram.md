# `polygon.parallelogram` — parallelogram by three vertices

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `polygon: polygon`, `side.1: segment`, `side.2: segment`, `side.3: segment`, `side.4: segment`, `vertex: point` |
| policy | `vertex_index` |
| undefined | `upstream` |
| checks | `parallel_sides` |

The parallelogram `a b c D` with `D = a + c − b`, its four sides and the new
vertex `D` (slot `vertex`). Collinear points give a defined parallelogram of
area 0, as `polygon.by_points`.

## Value

    D = a + c − b
    polygon = {vertices: [a, b, c, D], area};  side.i = vertex i → vertex i + 1
    vertex = D

## Checks

- `parallel_sides`: `max(|AB × DC|, |BC × AD|) / max(|AB|, |BC|)` (0 when both are 0)
