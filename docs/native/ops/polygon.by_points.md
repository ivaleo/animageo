# `polygon.by_points` — polygon through vertices, with its sides

Registry 1.0 · group `polygon` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertices: point[]` (list, `min: 3`) |
| outputs | `polygon: polygon`, `side: segment` with `repeat: "vertices"` → slots `side.1 … side.N` |
| undefined | `upstream` |
| checks | `sides_match` |

A document binds any subset of the slots (`polygon`, `side.1`, …); all of them
are computed.

## Value

`N` vertices `(x_i, y_i)`, `i = 0 … N−1`, `j = (i + 1) mod N`:

    acc = 0
    for i = 0 … N−1:  acc = acc + (x_i·y_j − x_j·y_i)
    polygon = {vertices: [[x_0, y_0], …], area: |acc| / 2}
    side.(i+1) = {a: [x_i, y_i], b: [x_j, y_j], length: hypot(x_j − x_i, y_j − y_i)}

Side `side.k` joins vertex `k` and vertex `k + 1` (1-based, cyclically: the
last side joins the last vertex and the first). The area is unsigned
(shoelace), so a clockwise polygon has the same area as its counter-clockwise
copy, a self-intersecting one the absolute value of the signed sum, a
degenerate one `0`; all of these are **defined**.

## Degeneracy decisions

None. Upstream: if any vertex is not defined, every output gets the upstream
state of the worst vertex (the first on a tie).

## Checks

- `sides_match`: the largest of `hypot(side.a − v_i)` and `hypot(side.b − v_j)`
  over all sides.
