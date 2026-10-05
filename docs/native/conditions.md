# Conditions, the general case and automatic marks

animageo 1.9.0a2 (plan L3 §3). A **condition** is a statement about the
elements of a construction. A *construct* condition is made true by building:
its **receiver** (a point) is redefined to lie on a hidden **place**. A *check*
condition is only stored and checked. Everything here is shared with the web,
which repeats it in TypeScript. The fixtures `parity/v1/{recipes,general,marks}`
and the scenes `recipe_*`, `shape_*` hold the reference (§7).

Code: `animageo/native/conditions/` (`statements.py`, `validate.py`,
`recipes.py`, `apply.py`, `editing.py`, `marks.py`, `fixtures.py`),
`animageo/native/sampling.py`, `animageo/native/recipes/v1/*.json`,
`animageo/native/marks/auto.v1.json`.

## 1. Document fields

```json
"conditions": [{
  "id": "c1", "seq": 14, "mode": "construct" | "check",
  "statement": {…},
  "receiver": "C" | null, "recipe": "right_angle.vertex" | null,
  "operationIds": ["op_c1_1", "op_C"],
  "receiverOrigin": {"op": "point.free", "args": {}, "input": {"point": [2.9, 3.6]}} | null,
  "source": "panel" | "command" | "sketch" | "assistant" | "shape" | "tool",
  "shapeId": "T" | null
}],
"suppressedMarks": [{"source": "op_h" | "c1", "kind": "right_angle" | "equal_segments" | "equal_angles"}],
"elements": {"mark_c1": {…, "origin": {"kind": "auto", "source": "c1"}}},
"viewDefaults": {"autoMarks": {"rightAngles": true, "equalities": true}}
```

- `id`, `mode`, `statement` are required. A `check` condition has only
  `statement`. `operationIds` holds the place operations and then the
  receiver's operation. `receiverOrigin` is the definition of the receiver
  before its first condition; `release_condition` and `delete` use it.
- `elements.<id>.origin` stays a free object for the web. Only
  `origin.kind == "auto"` is checked.
- The library stores `viewDefaults.autoMarks` (an object of booleans) but
  never reads it.
- `validate` errors:
  - `condition_unknown_element` (statement or receiver);
  - `condition_unknown_operation`;
  - `condition_receiver_mismatch` (the receiver's producer is not in
    `operationIds`);
  - `condition_too_many` (more than 2 construct conditions on one point);
  - `condition_bad_statement`;
  - `condition_duplicate_id`.
- `validate` warnings:
  - `mark_origin_unknown` (`origin.source` is neither an operation nor a
    condition);
  - `suppressed_mark_unknown_kind`.

## 2. Statements

```
Statement := {kind: "eq"|"ne", left: Expr, right: Expr}
           | {kind: "parallel"|"perpendicular"|"tangent"|"congruent", a: Obj, b: Obj}
           | {kind: "on", point: Ref, object: Obj}
           | {kind: "collinear"|"concyclic", points: [Ref…]}
           | {kind: "coincident", points: [Ref, Ref]}
           | {kind: "concurrent", lines: [Obj…]}
Expr := AST v1 of number.expression (num, const pi, op + - * / ^, fn)
      | {len: Obj} | {angle: [Ref, Ref, Ref] | Ref} | {ref: number ID} | {deg: number}
Obj  := {ref: ID} | {pair: [P, Q]}
Ref  := {ref: point ID}
```

**Pairs.** A pair is the segment `PQ` in `len` and in `congruent`. In the
other kinds it is the line `PQ`. A pair creates no operation.

**`eq` errors and units.** `eq` compares `|left − right|`:

- a length (any `len` in the tree) is compared as is;
- an angle (`angle` or `deg`) and a scalar are compared times `S`.

**Angle leaves.**

- `angle [A, B, C]` is the convex angle at `B`:
  `atan2(|u × v|, u · v)`. It is `inconclusive` (`coincident_points`) when a
  side is shorter than `decide.length`.
- `angle` with a ref to an angle element is the convex measure
  `min(size, 2π − size)` of that element.

**Other kinds.** `ne` is `not(equal_value)`.

**Compiling** (`statement_checks`):

| Statement | Predicate |
|---|---|
| `eq` | `equal_value` |
| `ne` | `not(equal_value)` |
| `on` | `incident` |
| any other kind | the predicate of the same name |

**Predicates added to `check`:** `on_object` (= `incident`), `coincident`,
`congruent`.

- `congruent` of segments or vectors compares lengths. Angles compare sizes
  times `S`, circles compare radii.
- Two polygons with the same `n` are compared by the smallest error over
  the `2n` matchings of the vertices (rotations, both directions). Different
  `n` gives `1e300`.

**Measuring** (`measure_statement(doc, statement, ev)`) returns
`(status, error, detail)`. The status is one of:

- `passed`, `failed` or `inconclusive`, classified by `tol.check`;
- `inconclusive` with `{reason: "undefined", elementIds}` when an element is
  not defined;
- `unsupported` when the argument types do not fit the predicate.

`ne` swaps `passed` and `failed`.

**Marks as statements.**

- `mark.right_angle(a, v, b)` is `va ⟂ vb`.
- An equality mark gives `eq` of the first target and each other target.

`relation(doc, a, b, ev)` returns the predicates of `coincident, incident,
parallel, perpendicular, tangent, congruent` that pass.

## 3. «Верно в общем случае»: `check_general`

`check_general(doc, targets=None, *, seed=None, trials=50, inputs=None)`
returns `{checkId: {status, trials, passed, failed, undefined, inconclusive,
counterexample, error, seed}}`.

**Targets.** By default every condition (by its ID), then every mark
operation (by its operation ID). A target can also be a condition ID, a mark
operation ID, a statement (checkId `""`) or `(checkId, statement)`.

1. **Level 1** is the current position. `failed` (or `unsupported`) ends the
   check:
   - `trials 0`, `seed null`;
   - the counterexample is `{trial: 0, inputs: {}}`.
2. **Seed** (64-bit). Unless `seed` is given, it is
   `int(sha256(documentId + ":" + checkId).hexdigest()[:16], 16)`. The
   generator is SplitMix64:
   - `next`: `state += 0x9E3779B97F4A7C15`;
     `z = (z ^ z>>30)·0xBF58476D1CE4E5B9`; `z = (z ^ z>>27)·0x94D049BB133111EB`;
     `z ^ z>>31` (mod 2⁶⁴);
   - `uniform() = (next() >> 11)·2⁻⁵³`.
   The first output for seed 1 is `0x910A2DEC89025CC1`.
3. **Trial `k = 1 … trials`.** The free inputs are visited by ascending
   element ID, in code-point order (the specs of L2 `general_position`). An
   input without a value draws nothing. The radius of the trial is `r_k = 0.5·S·k/trials`.
   - `point`: `ρ = √uniform()`, `φ = 2π·uniform()`,
     `p + r_k·(ρ cos φ, ρ sin φ)`, each coordinate clamped to
     `viewDefaults.bounds` (or the default bounds).
   - `pathParameter`, with `[lo, hi]` the parameter range of the path frame
     and `|v|` the length of its vector:
     - uniform over `[lo, hi]` when both ends are finite;
     - otherwise (a line or a ray): `t + (2·uniform() − 1)·S/|v|`. On a ray
       a value below `lo` is reflected (`2·lo − t`).
     - The `branch` of the input is kept.
   - `number`: uniform in `[min, max]` when both are given, else
     `v·(1 + uniform() − 0.5)`.
   - `angle`: `2π·uniform()`.

   The whole document is evaluated with the trial inputs. A `ValueError` or
   an undefined element counts as `undefined`; `unsupported` counts as
   `inconclusive`.
4. **Result.**
   - `failed` if any trial failed. The counterexample is the first failed
     trial: `{trial: k, inputs}`, the inputs of the trial only.
   - `inconclusive` if `undefined + inconclusive > 0.2·trials`.
   - Otherwise `passed` (a test, not a proof).

   `error` is the error at the current position (the largest over the
   statements of a target).

## 4. Recipes v1

The files `recipes/v1/*.json` (`animageo-recipe/v1`) have these fields:

- `recipe` and `priority`;
- `condition {kind, pattern}`;
- `receiver` (a variable), `requires {variable: point | path | circle |
  positive | angle_degrees}`;
- `template` (place steps, then `{redefine: X, op: "point.on_path", args:
  {path}}`);
- `check: "statement"` and `phrase.ru`.

The 13 recipes in priority order:

| # | Recipe | Pattern | Place |
|---|---|---|---|
| 1 | `on_object` | `X ∈ W` | `W` itself |
| 2 | `on_line` | `X ∈ AB` | `line.by_points(A, B)` |
| 3 | `length.value` | `\|AX\| = V` | `circle.center_radius(A, V)` |
| 4 | `equal_length.vertex` | `\|AB\| = \|AX\|` | `circle.center_point(A, B)` |
| 5 | `equal_length.free` | `\|AB\| = \|CX\|` | `segment.by_points(A, B)`, `circle.center_segment` |
| 6 | `parallel` | `AB ∥ CX` | `line.parallel` |
| 7 | `perpendicular` | `AB ⟂ CX` | `line.perpendicular` |
| 8 | `right_angle.vertex` | `∠AXB = 90°` | `circle.diameter(A, B)` |
| 9 | `right_angle.side` | `∠ACX = 90°` | perpendicular to `CA` at `C` |
| 10 | `angle.value` | `∠ABX = D°` | `ray.at_angle(B, A, ±D)` |
| 11 | `angle.equal` | `∠ABC = ∠DEX` | `angle.by_points`, `measure.angle`, `number.expression`, `ray.at_angle` |
| 12 | `tangent` | `PX` tangent to `W` | `line.tangents_from_point(P, W)` |
| 13 | `equal_length.apex` | `\|XA\| = \|XB\|` | `line.perpendicular_bisector(A, B)` |

Card per recipe: `docs/native/ops/recipes.md`.

### 4.1 Matching (`matches`)

**Forms of a statement**, in this order (the statement first):

- `eq` / `ne` with its sides swapped;
- `parallel`, `perpendicular`, `tangent`, `congruent` with `a` and `b`
  swapped;
- every pair in both orders;
- every three-point angle reversed.

**Unification.**

- `{ref: "V"}` binds an element ID.
- `{pair: ["V", "W"]}` binds both points.
- `{value: "V"}` binds a `num` literal or a number `ref`.
- `{deg: "D"}` binds a degree literal.
- Any other node must be equal. A variable bound twice must get the same
  value.

**`requires`.**

- `point`, `path` (the registry family) and `circle` check the element type.
- `positive` holds for a literal `> 0` or a number element.
- `angle_degrees` holds for a literal in `(0, 180)`.

The receiver must be bound by exactly one point variable; other repeated
points are allowed. The result has one entry per `(recipe, receiver)`, by
priority and then by form order.

### 4.2 `apply_condition(doc, condition, *, receiver=None, id_factory=None, ev=None, marks=True)`

`condition = {statement, mode: "construct", source, shapeId?}`.

**Receivers.** The candidates are the receivers of the matches.

- A point is `ok` when its producer is `point.free` or `point.on_path`, or
  when it already has construct conditions.
- It is `not_free` otherwise. It is `ancestor` when another participant is
  built on it.
- The default receiver is the `ok` candidate with the largest order key of
  its producer; ties go to the point named last in the statement.

**Refusals** (none of them changes the document):

| Code | When | Options |
|---|---|---|
| `unsupported_condition` | no match (or no match for the given receiver) | `keep_as_check`, `manual` |
| `receiver_not_free` | — | `make_free` for every participant point that is not `point.free` and not an ancestor of another participant (by descending order key), then `keep_as_check`, `manual` |
| `receiver_is_ancestor` | — | as for `receiver_not_free` |
| `too_many_conditions` | the receiver already has 2 constraints (its conditions, plus 1 for a `point.on_path` made by no condition) | `keep_as_check`, `manual` |
| `no_intersection_now` | the place, or the meeting of two places, is not defined now | `keep_as_check`, `manual` |

**Places.**

- Each template step except the last is one operation, with
  `seq = max + 1, …` and outputs hidden as `{visible: false, role: "aux"}`.
- Arguments:
  - a variable becomes a ref;
  - `$name` refers to a made element;
  - `{value: V}` becomes a number or a ref;
  - `{signed_degrees: D, side: [A, B, X]}` becomes
    `sign·D·π/180`, where the sign is that of `(A − B) × (X − B)` now
    (`+` at 0);
  - `{signed_convex: [D, E, X]}` becomes `number.expression`
    `sign·min(x, 2π − x)`.
- An output `"tangent.1|tangent.2"` takes the slot whose line is nearest to
  `nearest` now; that choice is fixed.

**Receiver.**

- A free receiver becomes `point.on_path(place)`. Its parameter is the
  projection of its position. On a ray place, a position behind the origin
  is first moved to the point of the ray at the same distance.
- A receiver already on a path becomes the intersection of both places:
  - line–line gives `intersect.line_line`;
  - line–circle gives `intersect.line_circle`;
  - circle–circle gives `intersect.circle_circle`.

  It takes the slot nearest to its position.

**The entry.**

- It has `seq = max + 1`, `operationIds` = places + the receiver's
  operation, `receiverOrigin` (kept from the first condition on the
  receiver), `source` and `shapeId`.
- `effects` are those of `redefine` plus the places, plus
  `shift {elementId, from, to, distance}`.
- With `marks`, the automatic marks of the condition are added (§6).

**Default IDs:**

| What | ID |
|---|---|
| condition | `c<n>` (smallest free) |
| place operation | `op_<c>_<k>` |
| place element | `<c>_<name>` (`$g` → `c1_g`) |
| on a clash | `_2`, `_3`, … |

`id_factory(kind, hint)` replaces these.

### 4.3 `release_condition(doc, condition_id, *, ev=None)`

The receiver keeps the loci it has without this condition: its operation's
arguments minus the outputs of this condition's places, minus a bound locus
(the `W` of `on_object`).

| Loci left | New receiver |
|---|---|
| none | `point.free` at its position in `ev`. Without `ev`: the `receiverOrigin` point, with the warning `restored_origin`. If the origin is not `point.free`: the evaluated position |
| one | `point.on_path` on it, at the projection |

The places, the automatic marks of the condition and its `suppressedMarks`
entries go. The result has `effects.removed.conditions`.

### 4.4 `condition_candidates`, `shape_conditions`

- `condition_candidates(doc, statement)` returns `[{elementId, ok,
  reason}]` for every point of the statement. `reason` is one of
  `no_recipe`, `not_free`, `ancestor`.
- `shape_conditions(doc, polygon_id, shape)` returns `[{statement,
  receiver}]` for a `polygon.by_points` with the right number of distinct
  vertices, else `[]`:

  | Shape | Conditions |
  |---|---|
  | right triangle ABC | `∠ACB = 90°` (C) |
  | isosceles | `\|CA\| = \|CB\|` (C) |
  | equilateral | `\|AB\| = \|AC\|`, `\|BA\| = \|BC\|` (C) |
  | parallelogram ABCD | `AB ∥ DC`, `AD ∥ BC` (D) |
  | rhombus | `\|AB\| = \|BC\|` (C) + the parallels |
  | rectangle | `∠ABC = 90°` (C) + the parallels |
  | square | `∠ABC = 90°`, `\|BC\| = \|AB\|` (C) + the parallels |
  | trapezoid | `AB ∥ DC` (D) |

  The isosceles shape uses `equal_length.apex`.

## 5. Edits (`delete`, `redefine`)

- **Deleting a participant.** `delete` of anything that reaches a
  participant of a construct condition (the receiver aside) first restores
  that receiver:
  - its operation becomes the `receiverOrigin` of its first condition, with
    the origin's input;
  - without a usable origin (none, or it uses a place), it becomes
    `point.free` at its current position, with the warning
    `origin_unusable`;
  - every condition on that receiver goes, with its places and marks.

  This repeats until nothing more is affected; then the deletion runs. The
  result has `effects.removed.conditions` and
  `effects.modified.restoredFrom` (the restored receivers).
- **Gone elements.** A condition whose receiver or participant is gone
  afterwards (a deleted receiver, a `check` condition) is removed with its
  places and marks.
- **Redefining a receiver.** `redefine` of a receiver's operation removes
  its conditions. The places that the new arguments do not use go, and so
  do the marks.
- **Cycles.** A result in which a receiver is built on a participant of its
  condition is refused with `condition_cycle` (one issue per condition).
- `apply_condition` and `release_condition` use the plain `delete` and
  `redefine`.
- `redefine` (all documents) takes the default of an optional free input
  (`FREE_INPUT_DEFAULTS`: the angle of `segment.from_point_length`) instead
  of refusing with `missing_input`. No input record is written, as in
  `validate`.

## 6. Automatic marks

`auto_marks(doc, sources, *, ev=None, id_factory=None) → [operation]` returns
the new operations: for each source, its helpers and then its mark.
`add_auto_marks(...) → AutoMarks(document, operations, elements, warnings)`
returns the document with them added. `auto_sources(doc)` returns every
source in the table. The table is `marks/auto.v1.json`
(`animageo-auto-marks/v1`).

| Source | Mark | Points |
|---|---|---|
| `triangle.altitude` | right angle | `(V, H, X)`, `X` — the end of the side farther from `H` now (`b` on a tie) |
| `point.projection` with a visible `segment.by_points` P–H | right angle | `(P, H, X)` |
| `line.perpendicular` with a visible `intersect.line_line` H of the line and the base | right angle | `(P, H, X)`; none when `P` is at `H` |
| `circle.diameter(a, b)` | right angle at each visible `point.on_path` C on it | `(a, C, b)` |
| `line.tangents_from_point` with a visible centre `O` | right angle at each touch point | `(P, T, O)` |
| `point.midpoint`, `triangle.median` | equal segments | the halves |
| `triangle.bisector` | equal angles | `(A, V, F)`, `(F, V, B)` |
| `line.angle_bisector(a, v, b)` | equal angles | through the hidden meeting `F` of the line and segment `ab` |
| conditions `equal_length.*`, `length.value` with two lengths | equal segments | the pairs of the statement |
| conditions `right_angle.*` | right angle | the three points |
| condition `perpendicular` with one common point | right angle | `(other, common, other)` |
| condition `angle.equal` | equal angles | the two angles |

**Which marks are made.**

- A source is an operation ID or a construct condition ID.
- A pair `(source, kind)` in `suppressedMarks` gives nothing. Neither does a
  source that already has an automatic mark of that kind.
- Degenerate point triples are skipped.

**Helpers.**

- A segment is an existing `segment.by_points` on the same two points (the
  smallest operation ID). Otherwise it is a new hidden one.
- An angle is a new hidden `angle.by_points` oriented to be convex now:
  `(a, v, b)` when `(a − v) × (b − v) ≥ 0`, else `(b, v, a)`.

**`count` (the class of an equality).**

- If an already marked equality of the same kind is equal in value now
  (within `check.passed`; lengths, or convex angles times `S`), the new mark
  takes its count.
- Otherwise it takes the smallest of 1–3 not taken.
- If all are taken: 3, with the warning `mark_classes_exhausted`.

**New elements.**

- The mark and its new helpers get `origin {kind: "auto", source}`, so that
  they go with the source.
- Helpers are `{visible: false, role: "aux"}`.

**IDs.** Default IDs are `op_mark_<source>` / `mark_<source>` for the mark,
`op_aux_<source>` / `aux_<source>` for a helper, and `_2`, … on a clash.
Every new operation gets the next `seq`.

## 7. Steps and text

See also `steps.md`.

**Condition steps.** The operations of a construct condition outside the
explicit groups form the step `condition:<id>` (kind `condition`,
`conditionIds [id]`). The receiver's operation goes to the step of the last
condition on that receiver.

**Where a mark goes.** An automatic mark and its helpers join:

1. the step of their source, when everything they use is built there or
   before;
2. otherwise the step of a direct dependency (the one with the largest order
   key first), on the same terms;
3. otherwise they stay steps of their own.

**`describe`.**

- A condition step reads «Ставим {recipe}»: `steps.condition.text` with the
  recipe phrase filled in, then the phrases of its marks.
- A mark joined to a step starts with a small letter.
- Hidden helpers of marks get no phrase.

**`values=True`.**

- After an operation's phrase: `(|AB| = 2,4; ∠ABC = 35°; k = 1,5)` — the
  visible segments, the angles (by size) and the numbers.
- A condition step gets the `len` values and the three-point angle values of
  its statement.
- Numbers use a decimal comma, `precision` digits, and no trailing zeros.

## 8. Fixtures

`python -m animageo.native fixtures conditions [-o root] [--check]` builds
the fixtures. `--check` compares them with a fresh build and replays every
case from its inputs (`replay_case`). The web does the same.

| Format | Cases |
|---|---|
| `animageo-recipes/v1` | `recipes/{recipes,refusals,two,release,shapes}.json`, 132 cases. Apply cases: `expect {refusal, document, values, shift, check}`. A release case has `release` (and `withValues`: whether `ev` is passed). A shape case has `shape {polygon, shape}` and `expect.conditions` |
| `animageo-general/v1` | `general/general.json`, 32 cases. `expect {status, passed, failed, undefined, inconclusive, counterexample, seed}`. Seeds are decimal strings |
| `animageo-marks/v1` | `marks/marks.json`, 34 cases. `expect {operations, warnings}` |

- Documents after an edit are written as they are, with the default IDs
  (§4.2, §6). Numbers compare within `tol.parity`.
- The scenes `recipe_*` (13) and `shape_*` (4) are ordinary parity scenes
  (`fixtures generate`). They also get `animageo-steps/v1` fixtures and
  describe snapshots.
