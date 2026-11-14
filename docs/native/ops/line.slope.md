# `line.slope` — scalar slope of a line

Registry 1.12 · module group `tangency` · status `beta`.

| | |
|---|---|
| input | `line: line` |
| params | none |
| output | `number: number`, `{value: dy/dx, unit: "scalar"}` |
| undefined | `vertical_line`, `non_finite`, `upstream` |
| checks | none |

The input line has a unit direction (dx,dy). If |dx|≤decide.scalar (1e−10),
the result is undefined with `vertical_line`. Otherwise the slope is dy/dx;
reversing the direction leaves the result unchanged. An overflow gives
`non_finite`; negative zero is normalized to positive zero. Undefined
dependencies propagate `upstream` with the original cause and recover when
their inputs recover.

For y=2x−1 the result is 2; for its normal y=−x/2+3/2 it is −1/2.
A horizontal line gives +0. A vertical line gives no finite scalar.
This operation accepts lines; construct a carrier line explicitly for a
segment, ray or vector. The output is neither an angle nor a slope triangle.
Classic command conversion is not yet provided. The complete `tangency`
capability is not advertised while its conic operations remain staged.
