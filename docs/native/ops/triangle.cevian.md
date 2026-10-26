# `triangle.cevian`

Exactly one input set: `vertex`, `point` (points), or `polygon` (a triangle).
For the first form, the caller supplies a point on the opposite side,
usually constructed with `point.on_path` on that side segment. As with
`segment.by_points`, the operation does not infer an unprovided triangle.
For a polygon, `index` is the vertex number 1..3 (the same convention as
`polygon.vertex`); `t` defaults to 0.5 and is clamped to [0,1], along the
side from the next vertex to the following vertex in definition order.
Output `cevian` is a segment directed from the vertex to the side point.

Coincident ends within the kernel length tolerance give
`undefined/zero_length`. A non-triangle polygon gives
`undefined/invalid_parameter`; a missing, fractional or out-of-range
polygon vertex index gives `undefined/index_out_of_range`.
