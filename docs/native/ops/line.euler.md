# `line.euler`

Exactly one input set: `a`, `b`, `c` (points), or `polygon` (a triangle).
Output `line` has type `line`, directed from circumcenter O to orthocenter H.
The centers share the kernel calculation of `circle.nine_point`,
`triangle.circumcenter` and `triangle.orthocenter`.

If |H-O| is at most the kernel length tolerance, including an equilateral
triangle, the line is `undefined/coincident_points`. A collinear or
collapsed triangle gives `undefined/collinear_points`. A polygon with
other than three vertices gives `undefined/invalid_parameter`.
Undefined inputs propagate their state.
