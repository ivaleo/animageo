# `line.tangent_conic_at` — tangent at a point of a conic

Registry 1.12 · module group `tangency` · status `beta`.

| | |
|---|---|
| inputs | `point: point`, `conic: conic` |
| output | `line: line` |
| undefined | `not_on_curve`, `degenerate_conic`, `non_finite`, `upstream` |
| checks | `through_point`, `on_curve`, `tangent` |

The point must belong to the current nondegenerate ellipse, hyperbola or
parabola. Membership compares a scaled implicit polynomial divided by its
gradient norm with `decide.length`. This is normal displacement in length
units near the curve; compensated products avoid focal-distance cancellation
and loss of sensitivity near asymptotes. The point is neither projected nor
reinterpreted as an external point. Moving it off the curve gives `not_on_curve`.

The canonical central equation has F(center)=−1; the parabola has positive
nonzero quadratic eigenvalue. Turn its normal at the input point by +90°
and normalize with `hypot` for the line's direction. The stored `p` is the
closest point to the origin. For x²/4+y²=1 at (2,0), the result is x=2 with
direction (0,1). Vertical tangents are ordinary lines.

There is one output. The contact is the original input point, which is also
the origin of the line's path parameter. Build its normal with
`line.perpendicular(point=point, base=line)`; no duplicate point is produced.
Degenerate input producers propagate `upstream` with their original cause;
the kernel also rejects a degenerate canonical value with `degenerate_conic`.
Nonfinite geometry or a line whose contact cannot be represented within the
geometric check tolerance gives `non_finite`. Restoring inputs restores the tangent.

This operation accepts `conic`; the existing circle operation is
[`line.tangent_at`](line.tangent_at.md). `has("tangency")` is true.
This strict operation has no classic equivalent and remains in
`opsWithoutClassic`: `Tangent(A,K)` searches through A and is never rewritten
as a strict tangent from one saved frame. Use the native operation for a
strict construction. The Commands printer reports `unprintable_operation`.
