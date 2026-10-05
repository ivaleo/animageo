# Steps and the text of a construction (`native.steps`, `native.describe`)

animageo 1.9.0a1 (plan L3 §2.3–§2.6). Both are structural: they read the
document, never its values, so moving a free point does not change them. The
web repeats them in TypeScript; the fixtures `animageo-steps/v1`
(`parity/v1/steps`) hold the reference for every parity scene.

## Document fields

- `operations.<id>.seq` — an integer ≥ 1, optional. **Order key** of an
  operation: `(0, 0, id)` without `seq`, `(1, seq, id)` with it — operations
  without `seq` first by ID, then by `seq`, ties by ID. A repeated `seq` is the
  warning `seq_duplicate`. `native.assign_seq(doc, op_ids)` returns a copy of
  the document with `seq = max + 1, max + 2, …` in the order of `op_ids`
  (`max` over the document, `0` without any).
- `steps: [{id, kind, title?, text?, operationIds}]` — explicit groups,
  `kind ∈ given | group | condition`; `title` heads a group, `text` replaces
  the phrase of the step. `validate` errors: `step_unknown_operation`,
  `step_duplicate_operation` (an operation in two groups, or twice),
  `step_duplicate_id`, `step_empty`, `step_cycle` (the groups cannot be
  ordered by the dependencies of their operations).

## `native.steps(doc) → [Step]`

`Step(id, kind, title, text, operationIds, elementIds, auxElementIds,
conditionIds)`, `kind ∈ given | op | group | condition`;
`Step.to_dict()`. An error of the explicit steps raises `StepError` (a
`ValueError` with `.issues`).

1. Every operation outside the explicit groups is a step of its own,
   `id = "op:<opId>"`, `kind = "op"`.
2. A step depends on another when one of its operations depends on one of the
   other's (through bound elements). Steps are ordered by Kahn's algorithm;
   among the ready steps the smallest `(min order key of its operations,
   step id)` goes first. Inside a step the operations follow the same rule
   (Kahn over the dependencies inside the step, ties by order key).
   Operations on a dependency cycle (a broken document) come last, by key.
3. «Дано»: unless the document has an explicit `given` step, the longest
   prefix of `op` steps whose operation is `point.free` or `number.free`
   merges into one step `id = "given"`, `kind = "given"`.
4. `elementIds`: the outputs of the step's operations in operation order and
   then output order, unless `appearance.<id>.visible` is `false`;
   `auxElementIds`: the hidden ones (pairs of «Команды», helper lines).
   `conditionIds`: the condition of a `condition` step; for an explicit
   group, the construct conditions with an operation in it.
5. Conditions (1.9.0a2, `conditions.md` §7): the operations of a construct
   condition outside explicit groups form the step `condition:<id>`, kind
   `condition`; the receiver's operation goes to the step of the last
   condition on it. An automatic mark and its helpers (`origin.kind =
   "auto"`) join the step of their source when everything they use is built
   there or before, else the step of a direct dependency (largest order key
   first), else they stay steps of their own.

### `steps_merge(doc, step_id)`, `steps_split(doc, step_id, operation_ids)`

Both return a new `steps` array for the document (they do not change it);
a result that cannot be ordered raises `StepError` (`step_cycle`); a wrong
request raises `ValueError`.

- **Merge** «Объединить с предыдущим»: step `step_id` joins the step before
  it. The merged step takes the ID, title and text of the previous step when
  that one is explicit; the automatic «Дано» gives the ID `given`; else those
  of this step when explicit; else a new ID `s<n>` (the smallest `n ≥ 1` not
  used by a step). Its kind is `given` when either step is a «Дано», else
  `condition` when either is a condition, else `group`; its operations are
  those of the previous step, then of this one. It takes the place of the
  first of the two in the array (or is appended).
- **Split** «Разделить»: `operation_ids` (some, not all, of the step's
  operations) move to a new step `s<n>` placed right after the step in the
  array, kind `group` (`condition` for a condition). The automatic «Дано»
  becomes an explicit `given` step with the operations that stay. A step of
  one operation cannot be split.

## `native.describe(doc, *, values=False, phrases=None, ev=None, precision=2) → [str]`

One line per step: `"<n>. <phrase>."`.

- A group with a `title`: the heading `"<n>. <title>."` and a sub-item
  `"<n>.<k>. <phrase>."` per operation. A group without a title joins the
  phrases of its operations with `"; "`. A step `text` replaces the phrase
  (`"<n>. <text>."`, or `"<n>.1. <text>."` under the title).
- «Дано» of free points and numbers: «Дано: точки A, B, C» (one point:
  «Дано: точка A»), numbers after `"; "`: «числа k, m» (only numbers:
  «Дано: число k»). Three points followed by the step of a
  `polygon.by_points` on exactly those points: «Строим треугольник ABC», and
  that polygon step gets no line of its own.
- A `condition` step (1.9.0a2): `steps.condition.text` («Ставим {recipe}»)
  with `{recipe}` the `phrase.ru` of the recipe filled with the names of its
  bindings (a number literal in the decimal format, `D` in degrees), then
  the phrases of the marks of the step. The phrase of an automatic mark
  joined after another starts with a small letter; an operation whose
  outputs are all hidden helpers of automatic marks has no phrase.
- `values=True` (1.9.0a2, computational; `ev` or an evaluation): after the
  phrase of an operation `(…; …)` — a visible segment `|AB| = 2,4` (by its
  two points when the producer has them), an angle `∠ABC = 35°` (its size),
  a number `k = 1,5`; after a condition step — every `len` and three-point
  `angle` of its statement (convex degrees). Decimal comma, at most
  `precision` digits, trailing zeros dropped; an undefined value is skipped.

### The phrase table `phrases/ru.v1.json`

```json
{"format": "animageo-phrases/v1", "lang": "ru",
 "steps": {"<stepKind>": {"text": "…", "ops": {"<op>": "…"},
                          "context": [{"when": "triangle_vertices", "op"?: "<op>", "text": "…"}]}},
 "given": {"point": "Дано: точка {list}", "points": "Дано: точки {list}",
           "number": "число {list}", "numbers": "числа {list}",
           "numbers_only": "Дано: {numbers}", "triangle": "Строим треугольник {name}"}}
```

Every `stepKind` of registries 1.0–1.5 has an entry
(`tests/native/test_native_l3a1_steps.py::test_phrases_cover_registry`).
`ops` holds the template of an operation whose slots differ from the others
of its kind; a `context` entry whose `when` holds is used first:

| `when` | holds when | adds |
|---|---|---|
| `triangle_vertices` | the three points of the op (`a, b, c`, or `vertex` and the two points of the producer of `side`) are the vertices of a `polygon.by_points` with three vertices (the first such polygon by operation ID) | `{triangle}` — that polygon's name |
| `three_vertices` | a `polygon.by_points` of three vertices | — |
| `number_mover` | a `locus.of_point` whose mover is a number | — |

Without an entry for its kind an operation is told by the descriptive
`phrases.ru` of its registry record. The argument `phrases` (a dict of the
same format, the web's overlay) replaces entries by `stepKind` and the
`given` phrases.

Placeholders: `{slot}` — an input or parameter slot of the operation, else an
output slot; `{out:s1,s2,…}` — the bound outputs among those slots joined by
`", "`. A placeholder with no name becomes empty; then runs of spaces become
one, spaces before `, . ; :` and repeated commas go, and the line is
trimmed. A number literal is written with a decimal comma and at most
`precision` digits (`2`, `0,5`).

### Names

In this order: a polygon of `polygon.by_points` — its vertices together
(`ABC`); an angle of `angle.by_points` and a right-angle mark — `∠ABC`; an
equality mark — its targets; a segment, line, ray or vector that is hidden
or has no `displayName` — the two points of its producer (`segment.by_points`,
`line.by_points`, `vector.by_points`: `a`, `b`; `ray.by_points`: `origin`,
`through`; the segment of `triangle.altitude`, `triangle.median`,
`triangle.bisector`: the vertex and the foot when the foot has a name);
otherwise `displayName`, else the element ID. A list of points is written
together (`ABC`), any other list as `"X, Y и Z"`.

Snapshots of the description of every parity scene:
`tests/native/snapshots/describe/<scene>.txt` (regenerate with
`ANIMAGEO_UPDATE_SNAPSHOTS=1`).
