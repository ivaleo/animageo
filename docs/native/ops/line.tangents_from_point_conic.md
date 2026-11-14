# `line.tangents_from_point_conic` — conic tangents through a point

Registry 1.12 · module group `tangency` · status `beta`.

| | |
|---|---|
| inputs | `point: point`, `conic: conic` |
| param | `count: number`, integer 1…100, default 2 |
| outputs | `tangent.k: line`, `touch.k: point`, k=1…count |
| policy | `polar_contacts_descending` |
| undefined | `point_inside`, `no_tangent`, `branch_absent`, `degenerate_conic`, `non_finite`, `upstream` |
| checks | `through_point`, `on_curve`, `tangent` |

Finite contacts are intersections of the conic with the polar of the input
point. Each contact Q produces the tangent with normal M·Qh. An asymptote
whose contact is at infinity is excluded: for x²−y²=1 and P=(1,1), only x=1
at Q=(1,0) remains. Ellipse interiors give `point_inside`; other empty sets
give `no_tangent`.

The set contains distinct lines. P on the conic gives one line and touch=P,
with `detail: {found: 1}`; the next slot gives `branch_absent`. Every defined
line and paired point carries the same full `found`, before limiting capacity
with count. Excess slots of a nonempty set give `branch_absent` without found.
The evaluator never adds or removes elements. A normal uses the matching
`touch.k`. The path parameter of `tangent.k` starts at that contact even if
the point output is unbound.

Order is geometric and stateless. Canonicalize the equation sign so that
F(center)<0 for ellipse/hyperbola, or the nonzero quadratic eigenvalue is
positive for a parabola. Let nP=(M·Ph)xy and v=CCW90(nP)/hypot(nP).
Order distinct finite contacts by descending v·Q, clustering close ranks by
the decision tolerances and breaking ties by exact x then y. Tangent direction
is CCW90 of the canonical conic normal at Q. For y=x² and P=(0,−1), contacts
are (1,1), (−1,1), producing y=2x−1 and y=−2x−1 in that order.

Scaled equations, stable quadratic roots and an explicit linear limit avoid
depending on the arbitrary magnitude or sign of source coefficients.
Membership checks use the conic's geometric residual. Degenerate source
conics propagate `upstream`; malformed degenerate canonical values give
`degenerate_conic`. Nonfinite geometry or a line/contact pair whose precision
cannot meet the geometric check tolerance gives `non_finite` for the whole
requested set; an unconfirmed candidate is never silently dropped from found.

The frozen [`line.tangents_from_point`](line.tangents_from_point.md) circle
operation keeps its own side order and duplicate branches on the circle.
`has("tangency")` is true. Map 9 lowers GGB and Python DSL `Tangent(P,K)`
to this search, including when the saved P lies on K. Saved line coefficients
select distinct native slots once; labels and IDs remain fixed after edits.
Two coincident named saved lines refuse the group with `unsupported_signature`
and a multiplicity explanation. An empty output label creates no element and
does not shift later ordinals. The Commands printer has no grammar for this
operation and reports `unprintable_operation`.
