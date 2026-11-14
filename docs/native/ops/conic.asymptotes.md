# conic.asymptotes

Finite straight asymptotes of a `conic_section`. Registry 1.13, beta; module group `conic_elements`.

Optional `count` is an integer capacity 1–100, default 2. Outputs `asymptote.k: line` use the nearest point to the world origin and an oriented unit direction. Each defined slot carries `detail:{found:2}` independently of capacity. In a nonempty set excess slots are `branch_absent`; an ellipse, circle or parabola gives `no_asymptote` in every requested slot. Invalid conics give `degenerate_conic`/`upstream`; an unrepresentable member makes the whole set `non_finite`.

Only a hyperbola s²/a²−t²/b²=1 has this set. Both lines pass through C. In the native frame u,n=CCW90(u), their ordered directions are

1. normalize(a u+b n);
2. normalize(−a u+b n).

Scale a,b by max(a,b) before normalization. Here a is the transverse radius, even if b>a. Equal radii still give two different perpendicular lines. Policies `conic_asymptote_order` and `conic_asymptote_frame` fix order and orientation, invariant under M↔−M. GeoGebra raw coefficient signs are not an orientation promise.

Checks `through_center` and `asymptotic_direction` inspect every defined slot. The first is a distance; the second measures angular deviation from the ordered quadratic null direction and unit-direction error multiplied by scene scale S. Step kind: `conic_asymptotes`. Function asymptotes are outside this operation.

Map 10 reads `Asymptote(K)` from GeoGebra XML, preserving saved labels,
ordinals and undefined branches. The operation remains in `opsWithoutClassic`
because no classic dispatch key exists; no new Python DSL factory is added.
Function and list searches are explicit `unsupported_signature` refusals.
`has("conic_elements")` is true. The Commands printer reports
`unprintable_operation` until its grammar is extended.
