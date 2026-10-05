# `polygon.vertex` — vertex by number

Registry 1.4 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: vertexed` |
| params | `k` |
| outputs | `vertex: point` |
| undefined | `invalid_parameter`, `index_out_of_range`, `upstream` |
| checks | `matches` |

Vertex number `k` (from one) of a segment (`a`, `b`), a polyline or a
polygon (family `vertexed`). GeoGebra `Vertex(poly, k)`.

## Value

    if |k − round(k)| > tol.scalar or k < 1:   → "invalid_parameter"
    vertices = [a, b] (segment) or value.vertices
    if round(k) > len(vertices):              → "index_out_of_range"
    vertex = vertices[round(k) − 1]

## Checks

- `matches`: distance to vertex `k`
