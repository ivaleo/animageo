# `circle.nine_point`

Exactly one input set: `a`, `b`, `c` (points), or `polygon` (a triangle).
Output `circle` has type `circle`. The circumcenter O and circumradius R
use the same kernel calculation as `circle.three_points` and
`triangle.circumcenter`; H = A+B+C-2O, as for `triangle.orthocenter`.
The center is (O+H)/2 and the radius R/2. An equilateral triangle gives
a defined circle centered at O.

A collinear or collapsed triangle gives `undefined/collinear_points`;
a polygon with other than three vertices gives
`undefined/invalid_parameter`. Undefined inputs propagate their state.
