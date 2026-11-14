# `line.tangents_parallel_conic` — tangents parallel to an oriented line

Registry 1.12 · module group `tangency` · status `beta`.

| | |
|---|---|
| inputs | `base: line`, `conic: conic_section` (`circle` or `conic`) |
| param | `count: number`, integer 1…100, default 2 |
| outputs | `tangent.k: line`, `touch.k: point`, k=1…count |
| policy | `oriented_conic_support` |
| undefined | `no_tangent`, `branch_absent`, `degenerate_conic`, `non_finite`, `upstream` |
| checks | `on_curve`, `tangent`, `parallel` |

For the base unit direction d, keep the oriented normal n=(dy,−dx).
Candidate lines (nx,ny,c) solve Lᵀadj(M)L=0 with stable scaled roots and an
explicit linear limit. Retain only finite contacts on the curve. A hyperbola's
asymptotic direction gives `no_tangent`; an asymptote is not returned as a
tangent. A parabola has at most one finite tangent parallel to the base.

The base direction is retained by every output line. Its sign is also
essential to slot order: ellipse/circle contacts follow descending n·Q,
hyperbola contacts ascending n·Q. Close ranks are clustered by decision
tolerances with exact xy tie-breaking. Reversing the base reverses the two
slots when both contacts exist.

For a radius-2 circle and d=(−1,0), contacts are (0,2), (0,−2), with lines
y=2, y=−2. For x²−y²=1 and d=(0,1), contacts are (−1,0), (1,0).
For y=x² and a horizontal base the only tangent is y=0; a vertical base
gives `no_tangent`.

Results are distinct and paired. Defined outputs have `detail: {found: N}`
for the full set before count limits capacity. Extra slots of a nonempty set
are `branch_absent`; an empty set is `no_tangent` in every requested slot.
The path parameter starts at the matching contact, including when its point
output is unbound. Degenerate producers preserve `upstream` and its cause;
the defensive kernel reasons are `degenerate_conic` and `non_finite`.
An unrepresentable line/contact pair also gives `non_finite` for the whole
set, including when finite intermediate values cannot meet the geometric
check tolerance. A partial set is not advertised as the complete result.

The `conic_section` family is used only by this new operation. Existing circle
operations and the `conical` family keep their previous semantics.
`has("tangency")` is true. Map 9 reads GGB `Tangent(l,K)`, including circular
XML conics, and lowers the existing Python DSL factory and its reversed
classic alias. Saved lines bind distinct slots by normalized coefficients.
The Commands printer reports `unprintable_operation` until a grammar exists.
