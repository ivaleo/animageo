# `line.common_tangents`

Inputs: `first`, `second` (circles). Optional literal parameters: `kind`
(string, `external` by default, or `internal`), `index` (number, 0 by default,
0 or 1). Output `line` has type `line`.

Let d = c2-c1, D = |d|, delta = r1-r2 for external tangents and r1+r2
for internal tangents. A unit normal n satisfies n.d = delta. Index 0
uses the positive perpendicular component of n relative to d; index 1
uses the negative component. The line passes through c1+r1*n and has
direction (ny,-nx). `line.p` is the projection of the origin.

No tangent of the selected kind, concentric unequal circles, or a missing
second branch at tangency: `undefined/branch_absent`. Coincident circles:
`undefined/coincident`. Tangency within the kernel length tolerance gives
one line at index 0 with `detail: {"multiplicity": 2}`; its direction is
unit and its normal points along the line of centers (with the sign of
delta). Invalid kind or index: `undefined/invalid_parameter`.
