# `animageo.native` — contract of the reference kernel (L0–L3)

`animageo.native` reads construction documents `animageo-construction/v1`,
evaluates them, edits them and produces parity fixtures; with manim
installed it also renders them (§9). No module of the package imports manim
or the classic modules (`animageo.animageo`, `animageo.geo`) at import time:
the bridge and the renderer load the classic code inside their functions.
Label layout (`native.layout_labels`, §9.7) works without manim.
The text form of a document, «Команды» (`native.parse_commands`,
`native.print_commands`), is in `docs/native/commands.md`; the expressions of
`number.expression` (AST v1, `animageo.native.expr`) are in
`docs/native/expr.md`; time by element ID (`sample_timeline`, `render(t)`,
video, `steps_timeline`) is in `docs/native/timeline.md`; the import of `.ggb`
and of the classic graph (`native.from_ggb`, `native.from_construction`,
`import_report.v1`, stage L5) is in `docs/native/import.md`.
The browser kernel of the web app repeats §1–§8 in TypeScript; the
per-operation formulas are in `docs/native/ops/<op>.md`. When the two kernels
disagree, the library is right and the fixtures it generates are the
reference.

Everything here is language-neutral: "number" is an IEEE-754 double, the
order of floating operations is written out where it matters, and `hypot` is
`math.hypot` / `Math.hypot`.

## 1. Document `animageo-construction/v1`

Master schema: `animageo/native/schema/construction.v1.schema.json`
(JSON Schema draft 2020-12).

```text
{
  "format": "animageo-construction/v1",          required
  "documentId": ID,                              required
  "operationRegistryVersion": "1.4",             required, "<major>.<minor>"
  "operations": {ID: Operation},                 required
  "elements":   {ID: Element},                   required
  "inputs":     {ID: Input},
  "viewDefaults": {"bounds": [xmin, ymin, xmax, ymax], "axes"?: Axes, "grid"?: Grid, …},
  "workIntent": null | WorkIntent,
  "appearance", "styleBinding", "timeline", "exportDefaults", "bindings", any other key
}
WorkIntent = {"condition"?: {"text": string ≤ 4000, "source"?: "typed" | "photo" | "voice",
                             "quote"?: string, "mediaRef"?: string},
              "forbid"?: ["solution" | "move_given" | "extra_points", …]   unique,
              "assumptions"?: [string ≤ 200, …]                          at most 10,
              "briefRevision"?: integer ≥ 0}
Operation = {"id": ID, "op": "group.name", "args": {slot: Argument},
             "outputs": [{"slot": slot, "elementId": ID}], "branch"?: null | {"policy", "selector"}}
Argument  = {"kind": "ref", "elementId": ID}
          | {"kind": "list", "items": [Argument, …]}
          | {"kind": "number", "value": number}
          | {"kind": "expr", "ast": Expr}                    1.4 (a5), expr.md
          | {"kind": "template", "value": string ≤ 1000}     1.4 (a5), ops/text.free.md
Element   = {"id": ID, "type": type, "producer": {"operationId": ID, "slot": slot},
             "displayName": string, "origin"?: object}
Input     = {"kind": "point", "value": [x, y]}                         point.free
          | {"kind": "pathParameter", "value": t, "branch"?: -1 | 1,
             "pathKind"?: "ellipse" | "hyperbola" | "parabola"}        point.on_path (pathKind 1.9)
          | {"kind": "number", "value": v}                              number.free
          | {"kind": "angle", "value": radians}                         segment.from_point_length (1.4)
```

- `ID` matches `^[A-Za-z0-9_-]{1,64}$`; the product uses UUIDv4, fixtures use
  readable IDs (`A`, `AB`, `op_A`).
- An argument slot matches `^[A-Za-z_][A-Za-z0-9_]*$`; an output slot may
  carry a 1-based index (`side.3`).
- Operations, elements, arguments, outputs, producers and inputs allow no
  keys besides the listed ones; the top level allows any key.
- `viewDefaults.bounds` needs `xmin < xmax` and `ymin < ymax` (checked by the
  library; JSON Schema cannot say it).
- 1.6: `Axes = {"show"?: bool, "numbers"?: bool, "step"?: number > 0 | null,
  "labels"?: {"x"?: string ≤ 32, "y"?: string ≤ 32}}`, `Grid = {"kind"?: "none" |
  "major" | "major_minor", "step"?: number > 0 | null}` — drawn by `native.render`
  under the elements (view.md); evaluation does not read them.
- The schema checks the shape of an input value (its `kind`, numbers, a
  `branch` of `-1` or `1`); a usable value also has finite numbers. A free
  element without a usable value of its kind evaluates to `error/schema`
  (§5.2).
- The operation `branch` stays `null` (or absent) for every operation of
  registries 1.1–1.4: the output slot names the solution (§5.4).
- The input of a free operation belongs to the element of its **first**
  output slot (`segment` of `segment.from_point_length`, not `end`). An
  `angle` input may be absent: it then is `0` (`FREE_INPUT_DEFAULTS` of
  `registry.py`); the other kinds are required.
- `args` holds input slots and params (§4) alike. A `number` argument
  (literal) is allowed in an input slot of type `number` (a radius) and is
  the only kind a param takes.
- An `expr` argument (1.4, a5) goes only into an input slot of type `expr`
  (`number.expression`), and that slot takes nothing else. The structure
  checks only that `ast` is an object; the tree itself (nodes, whitelist,
  limits, `{ref: k}` inside the list input `refs`) is checked by `validate`
  as the issue `formula` ([expr.md](expr.md)). Likewise a `template`
  argument (1.4, a5) goes only into an input slot of type `template`
  (`text.free`): the structure checks a string of at most 1000 characters
  (code points), `validate` its inserts `{k}` (`formula`).
- Sections the library does not interpret — `appearance` (read by the
  renderer, §9), `styleBinding`, `timeline`, `exportDefaults`, `bindings`,
  `origin`, unknown keys — are kept as they are.
- `workIntent` (the problem text, what the assistant must not do, the
  assumptions; written by the web action `setWorkIntent`) has a fixed shape:
  no other keys, string lengths in characters (code points). An entry of
  `appearance` may carry `locked: boolean` («Закрепить»); other entry keys and
  non-object entries stay free. Both are checked as structure, kept by
  `load → dump`, covered by the canonical text and `content_hash`, and
  ignored by evaluation and by the renderer. They joined v1 as additive
  fields, so the format name does not change.
- 1.12.0: an entry of `appearance` may carry `drag: {"via": ID | [ID, …]}`
  (`via` a non-empty list without repeats, or a single ID; no other key) —
  the free inputs through which `native.drag` moves a dependent point (§8.1).
  It is display data: evaluation never reads it; `validate` checks what it
  names (§2).

`load(source, strict=True)` reads a dict, JSON text, bytes or a path; JSON
text with `NaN`/`Infinity` or a repeated key is refused. Structural problems
are issues with code `schema`; `strict` raises `LoadError` with all of them.
`load → dump` adds no defaults and loses no key, so `dumps` of a canonical
input is byte-for-byte the input.

## 2. Validation

`validate(doc)` returns `Issue{code, path, message, elementId?, operationId?,
severity}`; `path` is a JSON pointer. Structure first; the graph rules run
only on a structurally valid document.

| code | severity | when |
|---|---|---|
| `schema` | error | structure (§1) |
| `id_mismatch` | error | a key of `operations`/`elements` differs from the record's `id` |
| `duplicate_output` | error | an op binds the same slot twice, or an element is bound twice |
| `producer_mismatch` | error | an output names a missing element or one that names another producer; an element's producer op is missing or does not bind it |
| `unknown_op` | warning | the op is not in the registry |
| `newer_registry` | warning | `operationRegistryVersion` is newer than the library's (also replaces `unknown_op` then) |
| `needs_newer_registry` | error | registry 1.8: the document declares an older registry than it uses — an operation whose `since` is above `operationRegistryVersion` (`path` is its `op`), or an argument whose element type fits its family slot only since a later registry (`_types.json → familySince`; `path` is the argument). Not reported for a document that declares a registry newer than the library's |
| `unknown_slot` | error | an argument or output slot the op does not declare (a repeat slot beyond the list length too) |
| `missing_slot` | error | a declared input slot or a required param has no argument |
| `dangling_ref` | error | a reference (argument or `inputs` key) to a missing element |
| `type_mismatch` | error | argument kind (list vs ref), a list shorter than `min`, an element type that does not fit the slot, an element type that differs from its output slot type, a number literal in an input slot of another type, a param argument that is not a number literal, an input kind that differs from the free kind (`point` for `point.free`, `pathParameter` for `point.on_path`, `number` for `number.free`, `angle` for `segment.from_point_length`) |
| `cycle` | error | the operation lies on a dependency cycle |
| `formula` | error | an `expr` tree breaks AST v1 (a node, the whitelist, a limit, a `ref` outside `refs`); `path` points at the node ([expr.md](expr.md) §2). A `template` with a bad brace or an insert outside `refs`; `path` is the template's `value` ([ops/text.free.md](ops/text.free.md)) |
| `input_not_free` | error | an input value for an element not produced by a free op, or for an element of a free op other than its first output slot |
| `missing_input` | error | the element of the first output slot of a free op without an input value (not for an `angle` input, which defaults to `0`) |
| `dangling_ref` | error | 1.12.0: `appearance.<id>.drag` of a missing element (`path` the hint) or a `via` item naming a missing element (`path` the item) |
| `type_mismatch` | error | 1.12.0: `appearance.<id>.drag` of an element that is not a point |
| `drag_via_not_free` | error | 1.12.0: a `via` item that is not the input element of `point.free`, `point.on_path` or `point.on_function` |
| `drag_via_not_upstream` | error | 1.12.0: a `via` item the point is not built from (the point itself included) |
| `drag_singular` | warning | 1.12.0: at rest the point moves in fewer than `min(2, dim u)` directions through `via`, `dim u` the number of solve variables (a `point` input 2, a path parameter or the x of `point.on_function` 1; §8.1); `path` is `…/drag/via` |

The `drag` checks run only when some entry of `appearance` has a `drag` key;
a `via` item's `path` is `…/drag/via` for a single ID and `…/drag/via/<i>`
for a list, its `elementId` the dragged point.

**The declared registry** (1.8). `min_registry_version(doc)` is the oldest
registry a document fits: the newest `since` of its operations and of the
family members its arguments use (`familySince`), `"1.0"` without them;
operations the library does not know are left out. A document the library
writes declares it: `from_ggb`, `from_construction` and `parse_commands`
without `base` write the minimum; `parse_commands` with `base`,
`redefine` (and so `apply_condition`) and `add_auto_marks` raise
`operationRegistryVersion` to the minimum when it is higher and never lower
it. So a document declares 1.8 only when it uses an
operation or a family member of 1.8, and a reader of registry 1.7 opens
every other document without `newer_registry`. The fixture generators and
the experimental space writers declare the library's registry.

## 3. Canonical JSON and hash

The text `JSON.stringify` prints after object keys are sorted:

- keys ascend by UTF-16 code units (JavaScript `sort()` on strings);
- separators `,` and `:`, no whitespace;
- strings: only `"`, `\`, control characters below U+0020 (`\b \f \n \r \t`,
  others `\u00XX` with lowercase hex) and lone surrogates (`\udXXX`) are
  escaped; Cyrillic and every other character are written as is;
- numbers as `Number.prototype.toString`: shortest round-trip digits,
  integral values without a point, `-0` → `0`, exponent form `1e-7`,
  `1.5e+21` when the decimal exponent `n` (value = `0.d₁d₂… × 10ⁿ`) is outside
  `-6 < n ≤ 21`; NaN and ±∞ are an error;
- `true`, `false`, `null`.

`content_hash(doc) = "sha256:" + hex(sha256(utf8(canonical(doc))))`. The shared
table `animageo/native/parity/v1/canonical.json` is a list of
`{"value", "canonical"}` pairs that both kernels must reproduce.

## 4. Registry `ops/v1` (version 1.9)

Registry 1.4 is frozen since animageo 1.8.1: the records of 1.0–1.4 and their
`signatureHash` stay as they are (`beta` is a descriptive status outside the
hash and may become `stable`); a new operation or a changed signature goes to
registry 1.5. Registry 1.5 (animageo 1.9.0a1) adds the operations of a
triangle and the locus (§11).

Registry 1.6 (animageo 1.11.0rc5–rc11) adds functions and conics (§14)
and is frozen. Registry 1.7 (animageo 1.11.0rc12) adds common tangents,
circular segments, cevians, the nine-point circle and the Euler line.
These five operations have `since: "1.7"`; records and signature hashes
of operations from 1.0–1.6 stay unchanged. A 1.7 document opened with rc11
reports an unknown school operation as `newer_registry`.

Registry 1.8 adds the common points of two conics and of
a graph and a conic, and the conics and graphs in the `curve` slots of
`intersect.other_than` and `intersect.nearest` (§15). The records of
1.0–1.7 and their signature hashes stay unchanged; a document that declares
1.7 reads and evaluates as before.

Registry 1.9 puts a point on a conic and on a graph: the family `path`
takes `conic` and `function` (§16). No record changes; a document that
declares 1.8 reads and evaluates as before.

**Registry 1.5 is the 1.0 contract** (animageo 1.11.0rc1;
`tests/native/test_registry_frozen_1_0.py`, snapshot
`tests/native/registry_frozen_1_0.json`): while the version is 1.5 no record
and no catalog entry (`_types`, `_policies`, `_reasons`, `_numeric`)
changes and nothing is added. An operation is never removed (it may become
`deprecated` with a new registry version); its signature never changes (a
new operation instead); any other change of a record needs a new registry
version and the record's `since` set to it; a new operation has `since`
above 1.5; a catalog entry is never removed, and a changed or new one needs
a new registry version. `beta` may become `stable` at any time.

`animageo/native/ops/v1/<group>.json` holds arrays of records:

```text
{op, status, since, inputs: [{slot, type, list?, min?}], params: [{slot, type, unit, optional?, default?, text}],
 outputs: [{slot, type, repeat?, like?}],
 free?: {kind}, branch: null | {policy, slots, text}, undefined: [reason…], checks: [{id, text}],
 orientation, pathParam: null | "carrier/v1", stepKind, phrases: {ru}, math, signatureHash}
```

| op | since | inputs → outputs | branch policy |
|---|---|---|---|
| `point.free` | 1.0 | free `point` → `point` | — |
| `point.midpoint` | 1.0 | `a, b: point` → `point` | — |
| `segment.by_points` | 1.0 | `a, b: point` → `segment` | — |
| `line.by_points` | 1.0 | `a, b: point` → `line` | — |
| `circle.center_point` | 1.0 | `center, through: point` → `circle` | — |
| `intersect.line_line` | 1.0 (rays 1.1) | `first, second: linear` → `point` | — |
| `polygon.by_points` | 1.0 | `vertices: point[] (min 3)` → `polygon`, `side.1…N: segment` | — |
| `ray.by_points` | 1.1 | `origin, through: point` → `ray` | — |
| `intersect.line_circle` | 1.1 | `line: linear, circle: circular` → `first, second` | `line_param_order` |
| `intersect.circle_circle` | 1.1 | `first, second: circular` → `first, second` | `circle_side` |
| `intersect.other_than` | 1.1 | `first, second: curve, known: point` → `point` | `other_than` |
| `point.on_path` | 1.1 | free `pathParameter`, `path: path` → `point` | — |
| `point.projection` | 1.2 | `point: point, base: linear`; param `strict` → `foot` | — |
| `line.parallel` | 1.2 | `point: point, base: linear` → `line` | — |
| `line.perpendicular` | 1.2 | `point: point, base: linear` → `line` | — |
| `line.perpendicular_bisector` | 1.2 | `a, b: point` → `line` | — |
| `line.angle_bisector` | 1.2 | `a, vertex, b: point` → `line` | — |
| `vector.by_points` | 1.2 | `a, b: point` → `vector` | — |
| `circle.center_radius` | 1.2 | `center: point, radius: number` → `circle` | — |
| `circle.three_points` | 1.2 | `a, b, c: point` → `circle`, `center: point` | — |
| `number.free` | 1.2 | free `number`; params `min`, `max`, `step` → `number` | — |
| `angle.by_points` | 1.3 | `a, vertex, b: point` → `angle` | — |
| `circle.incircle` | 1.3 | `a, b, c: point` → `circle`, `center`, `touch_a`, `touch_b`, `touch_c: point` | — |
| `mark.equal_segments` | 1.3 | `segments: segment[] (min 2)`; param `count` → `mark` | — |
| `mark.equal_angles` | 1.3 | `angles: angle[] (min 2)`; param `count` → `mark` | — |
| `mark.right_angle` | 1.3 | `a, vertex, b: point` → `mark` | — |
| `point.divide` | 1.4 | `a, b: point, m, n: number` → `point` (ratio `m : n` from `a`) | — |
| `point.center` | 1.4 | `of: round` → `center` | — |
| `point.closest` | 1.4 | `point: point, path: path` → `foot` | — |
| `point.at_distance` | 1.4 | `a, b: point, distance: number` → `point`, `segment` | — |
| `polygon.vertex` | 1.4 | `of: vertexed`; param `k` → `vertex` | — |
| `line.angle_bisectors_of_lines` | 1.4 | `first, second: linear` → `internal`, `external` | `bisector_kind` |
| `line.external_bisector` | 1.4 | `a, vertex, b: point` → `line` | — |
| `ray.at_angle` | 1.4 | `vertex, a: point, size: number` → `ray`, `point` | — |
| `ray.by_vector` (beta) | 1.4 | `origin: point, vector: vector` → `ray` | — |
| `line.tangents_from_point` | 1.4 | `point: point, circle: circle` → `tangent.1`, `tangent.2: line`, `touch.1`, `touch.2: point` | `tangent_side` |
| `line.tangent_at` | 1.4 | `point: point, circle: circle` → `line` | — |
| `segment.from_point_length` | 1.4 | free `angle`, `start: point, length: number` → `segment`, `end` | — |
| `segment.midline` | 1.4 | `first, second: segment` → `segment`, `mid.1`, `mid.2` | — |
| `polyline.by_points` | 1.4 | `points: point[] (min 2)` → `polyline` | — |
| `circle.diameter` | 1.4 | `a, b: point` → `circle`, `center` | — |
| `circle.center_segment` | 1.4 | `center: point, radius: segment` → `circle` | — |
| `circle.excircle` | 1.4 | `a, b, c: point` → `circle`, `center`, `touch` (the circle opposite `a`, `touch` on `bc`) | — |
| `arc.center_two_points`, `sector.center_two_points` | 1.4 | `center, a, b: point` → `arc` / `sector` | — |
| `arc.three_points`, `sector.three_points` | 1.4 | `a, b, c: point` → `arc` / `sector`, `center` | — |
| `arc.semicircle` | 1.4 | `a, b: point` → `arc` | — |
| `arc.on_circle`, `sector.on_circle` | 1.4 | `circle: circle, a, b: point` → `arc` / `sector` | — |
| `sector.from_angle` | 1.4 | `center, a: point, size: number` → `sector` | — |
| `polygon.regular` | 1.4 | `a, b: point`; param `n` → `polygon`, `side.1…n`, `vertex.1…n` | `vertex_index` |
| `polygon.regular_center` | 1.4 | `center, a: point`; param `n` → `polygon`, `side.1…n`, `vertex.1…n` | `vertex_index` |
| `polygon.parallelogram` | 1.4 | `a, b, c: point` → `polygon`, `side.1…4`, `vertex` | `vertex_index` |
| `polygon.centroid` | 1.4 | `polygon: polygon` → `centroid` | — |
| `intersect.line_sector` | 1.4 | `line: linear, sector: sector` → `arc.1`, `arc.2`, `side.1`, `side.2` | `sector_sides` |
| `angle.between_lines` | 1.4 (a5) | `first, second: linear` → `angle` (convex, at the crossing of the carriers) | — |
| `angle.between_vectors` (beta) | 1.4 (a5) | `first, second: vector` → `angle` (counterclockwise, at `first.a`) | — |
| `angle.by_size` | 1.4 (a5) | `vertex, a: point, size: number` → `angle`, `point` | — |
| `number.angle` | 1.4 (a5) | free `angle`; params `min`, `max`, `step` → `number` (`unit: "angle"`) | — |
| `measure.length` | 1.4 (a5) | `of: measurable` → `number` (`length`) | — |
| `measure.distance` | 1.4 (a5) | `point: point, to: figure` → `number` (`length`) | — |
| `measure.area`, `measure.perimeter` | 1.4 (a5) | `of: bounded` → `number` (`area` / `length`) | — |
| `measure.angle` | 1.4 (a5) | `angle: angle` → `number` (`angle`) | — |
| `measure.radius` | 1.4 (a5) | `of: round` → `number` (`length`) | — |
| `measure.circumference` | 1.4 (a5) | `circle: circle` → `number` (`length`) | — |
| `number.expression` | 1.4 (a5) | `expr: expr, refs: number[]` (min 0) → `number` (`unit: "scalar"`, [expr.md](expr.md)) | — |
| `text.free` | 1.4 (a5) | `text: template, anchor: point, refs: insertable[]` (min 0); param `decimals` → `text` | — |
| `measure.polygon_angles` | 1.4 (a5) | `polygon: polygon` → `angle.1…N` (interior, at vertex `k`) | `vertex_index` |
| `transform.translate` | 1.4 (a5) | `obj: transformable, vector: vector` → `image` (like `obj`), `side.1…N`, `vertex.1…N` | `vertex_index` |
| `transform.rotate` | 1.4 (a5) | `obj: transformable, angle: number, center: point` → `image`, `side.i`, `vertex.k` | `vertex_index` |
| `transform.reflect_line` | 1.4 (a5) | `obj: transformable, line: linear` → `image`, `side.i`, `vertex.k` (orientation reversed) | `vertex_index` |
| `transform.reflect_point` | 1.4 (a5) | `obj: transformable, point: point` → `image`, `side.i`, `vertex.k` | `vertex_index` |
| `transform.dilate` | 1.4 (a5) | `obj: transformable, factor: number, center: point` → `image`, `side.i`, `vertex.k` | `vertex_index` |
| `intersect.nearest` (beta) | 1.4 (a5) | `first, second: curve, near: point` → `point` (the solution nearest to `near`) | `nearest_to` |
| `line.common_tangents` | 1.7 | `first, second: circle`; params `kind`, `index` → `line` | — |
| `sector.segment` | 1.7 | `arc: arc` or `circle: circle, a, b: point` → `segment: circlesegment` | — |
| `triangle.cevian` | 1.7 | `vertex, point: point` or `polygon: polygon`; params `index`, `t` → `cevian: segment` | — |
| `circle.nine_point` | 1.7 | `a, b, c: point` or `polygon: polygon` → `circle` | — |
| `line.euler` | 1.7 | `a, b, c: point` or `polygon: polygon` → `line` | — |

- A slot type may be a family (`_types.json` → `families`):

  | family | types |
  |---|---|
  | `linear` | `line`, `segment`, `ray` |
  | `circular` | `circle`, `arc` (1.4) |
  | `curve` | `line`, `segment`, `ray`, `circle`, `arc` (1.4), `conic`, `function` (1.8) |
  | `path` | `line`, `segment`, `ray`, `circle`, `polygon`, `arc`, `sector`, `polyline` (1.4) |
  | `round` (1.4) | `circle`, `arc`, `sector` |
  | `vertexed` (1.4) | `segment`, `polyline`, `polygon` |
  | `measurable` (1.4, a5) | `segment`, `vector`, `polyline`, `arc` |
  | `bounded` (1.4, a5) | `polygon`, `circle`, `sector` |
  | `figure` (1.4, a5) | `point` and the `path` types |
  | `transformable` (1.4, a5) | `point`, `segment`, `ray`, `line`, `vector`, `circle`, `arc`, `sector`, `polygon` |
  | `insertable` (1.4, a5) | `number`, `point` |
  | `straight` (1.8) | `line`, `segment`, `ray`, `vector` |

  An arc in a `circular` slot (`intersect.line_circle`,
  `intersect.circle_circle`, `intersect.other_than`) is intersected as its
  carrier circle and then filtered (the arc filter, §5.4);
- `repeat: "vertices"` on output `side` declares the slots `side.1 … side.N`,
  `N` = number of items of the list argument `vertices`; a `repeat` naming a
  param (`repeat: "n"` of `polygon.regular`, 1.4) declares `N =
  repeat_count(n)`: `round(n)` when `n` is a whole number in `[1, 100]`,
  else `0` (so `n = 2` declares two slots that evaluate to
  `invalid_parameter`, `n = 2.5` none); a `repeat` naming a single
  reference input (`repeat: "obj"` of the transforms, `repeat: "polygon"`
  of `measure.polygon_angles`, 1.4 a5) declares `N` = the vertex count of
  that element: the number of `side.i` slots its producer declares (`0`
  for an element of another type, so the image of a segment has no
  `side`/`vertex` slots); a document may bind any subset of the declared
  output slots;
- `like: "obj"` on an output (1.4 a5) gives it the type of the element
  bound to that input (`image` of `transform.rotate` on a circle is a
  `circle`); the declared `type` is the family it must belong to;
- `signatureHash = "sha256:" + sha256(canonical({op, inputs: [{slot, type,
  list (default false), min (default null)}], params: [{slot, type, unit
  (default null)}], outputs: [{slot, type, repeat (default null), like (only when set)}], free
  (default null), branch: branch.policy or null, orientation, pathParam}))`;
  the hashes of the 1.0 records did not change in 1.1, nor those of the
  1.0 and 1.1 records in 1.2, nor those of the earlier records in 1.3 and
  1.4; registries 1.5, 1.6, 1.7 and 1.8 also preserve all earlier signatures
  (tests pin them);
- params (`type: "number"`, or since 1.7 `"string"`) are op settings written
  in `args` as matching literals: `optional` (default `false`) and `default`
  (a matching literal or absent) are outside the hash. An absent optional param reaches the
  implementation as its `default`, or as nothing (`None`/`null`) without
  one; whether a value is allowed (`strict ∈ {0, 1}`, `min ≤ max`) is the
  op's decision, `undefined/invalid_parameter`. The registry check refuses a
  param with an unsupported type, a `default` of the wrong type and a
  required param with a `default`;
- `INDEX.json = {registryVersion, ops: {op: signatureHash}}`, written by
  `python -m animageo.native registry index` and checked by `--check`.

Service catalogs:

- `_types.json`: value fields and their kinds (`types`), `families`, path
  frames (`paths`, `frameKinds`, §5.5), `units` and `numberUnits` (§6);
  since 1.3 `markKinds` (mark kind → the operation that makes it; the
  registry check refuses a kind whose operation has no `mark` output) and
  `angles` (the normalisation of a direction, the convex measure and the
  wrap of a difference of directions, §5); since 1.8 `familySince`
  (`{family: {type: version}}`: a member that joined a family later than
  the family itself, for `min_registry_version` and
  `needs_newer_registry`, §2);
- `_reasons.json`: reason → state;
- `_policies.json`: branch policies (`single`, `line_param_order`,
  `circle_side`, `other_than`; since 1.4 `tangent_side`, `bisector_kind`,
  `vertex_index`, `sector_sides`, and in a5 `nearest_to`, §5.4);
- `_numeric.json`: bounds, tolerances, the generator margin and its noise
  decisions (§6).

## 5. Evaluation `animageo-evaluated/v1`

```text
{"format": "animageo-evaluated/v1", "documentId", "kernel": {"library", "registry"},
 "scale": S, "elements": {ID: Record}, "diagnostics": [ … ]}
Record = {"state": "defined", "type", "value", "detail"?}
       | {"state": "undefined" | "unsupported" | "error", "type", "reason", "cause"?, "detail"?}
```

`type` is the element's declared type. Values:

| type | value |
|---|---|
| point | `{x, y}` |
| segment | `{a: [x, y], b: [x, y], length}` |
| ray | `{origin: [x, y], dir: [x, y]}` — `dir` unit, from the origin towards the defining point |
| line | `{p: [x, y], dir: [x, y]}` — `p` the projection of the origin, `dir` unit, oriented by the definition |
| circle | `{c: [x, y], r}` |
| polygon | `{vertices: [[x, y], …], area}` — unsigned area |
| vector | `{a: [x, y], b: [x, y], length}` — `a` the start, `b` the end; a zero vector is defined |
| number | `{value, unit}` — `unit` one of `scalar`, `length`, `area`, `angle` (radians), `count` |
| angle | `{vertex: [x, y], a0, a1, size}` — radians; `a0 ∈ [0, 2π)` the direction of the first side from `+x`, `size ∈ [0, 2π)` counter-clockwise from the first side to the second, `a1 = a0 + size` (not normalised) |
| mark | `{kind, count}` — `kind` one of `markKinds` (`equal_segments`, `equal_angles`, `right_angle`, `parallel` since 1.8), `count` an integer `1…3` (`1` for a right angle) |
| arc | `{c: [x, y], r, a0, a1}` — radians, counter-clockwise from `a0` to `a1`; `a0 ∈ [0, 2π)`, `a1 ∈ [a0, a0 + 2π]`; a zero sweep is defined, `a1 = a0 + 2π` is the full circle |
| sector | `{c: [x, y], r, a0, a1}` — the region of the arc `{c, r, a0, a1}` and the radii to its ends `S0`, `S1`; `a1 = a0 + 2π` is the full disc |
| polyline | `{vertices: [[x, y], …], length}` — at least two vertices in definition order, `length` the sum of the links |
| text (1.4, a5) | `{anchor: [x, y], text, parts}` — the filled template and its pieces `{text}` / `{ref: k, text}`; `text` and `parts` compare exactly |

`_types.json` also lists `expr` and `template` (1.4, a5, `"argument": true`):
the types of input slots that take an `expr` or a `template` argument,
never the type of an element.

Angles (`_types.json → angles`): a direction is normalised by `θ =
atan2(y, x)`, `θ < 0` gives `θ + 2π`, then `θ ≥ 2π` gives `0` and `−0`
gives `0`; the convex measure is `m(size) = size` when `size ≤ π`, else
`2π − size`; a difference of directions wraps into `[−π, π)`: `wrap(d) =
d − 2π·floor((d + π) / 2π)`.

A mark has no geometry of its own: it is the claim that its arguments are
equal (or that the angle is right), drawn on the arguments (§9.3). It is
defined whenever its arguments are and its `count` is valid; whether the
claim holds is its check (§5.3), so a `failed` check is a warning and the
mark stays defined.

A defined record carries `detail` only for a double root of a two-slot
intersection: `{"multiplicity": 2}` in both slots (§5.4). Undefined records
use `detail` for the slot of an `outside_part` (`{"slot": "<argument slot>"}`)
and the like, as the op pages say.

### 5.1 Scale and tolerances

`S = max(w, h, D)`: `w = xmax − xmin`, `h = ymax − ymin` of `viewDefaults.bounds`
(or `defaultBounds = [-10, -10, 10, 10]`); `D = hypot(pxmax − pxmin, pymax − pymin)`
over the points of all free `point` elements with a valid input value after
the case overrides (`D = 0` without any). Path parameters and number inputs
do not take part in `S`.

| tolerance | value |
|---|---|
| `tol.decide` | `1e-10·S` for lengths, `1e-10` for dimensionless values |
| `tol.check` | passed if error `≤ 1e-9·S`, failed if `≥ 1e-6·S`, otherwise inconclusive |
| `tol.parity` | `1e-9·S` coordinates and lengths, `1e-9·S²` areas, `1e-9` unit directions |

### 5.2 Element and operation states

Case `inputs` override the document's input values of free elements. An
override for an unknown or non-free element, or one that is not a usable
value of the element's free kind (§1), is a caller error (`ValueError`).

Each element first: if its producer op does not exist or does not bind it
under `producer.slot` → `error/schema`; if the op is known and does not
declare the slot → `error/schema`; if the slot type differs from the
element type → `error/type_mismatch`. Otherwise the element takes its
producer's result for its slot.

Each operation, in dependency order (the result does not depend on the
order):

1. on a dependency cycle (strongly connected component of two or more ops,
   or an op referencing its own output) → `error/cycle`;
2. op not in the registry → `unsupported/unknown_op`, or
   `unsupported/newer_registry` when the document's registry version is newer;
3. arguments: an argument slot the op does not declare → `error/schema`;
   then for each declared input slot in registry order: no argument →
   `error/schema`; a list slot without a list argument, a scalar slot with a
   list, a list shorter than `min`, an item that is not a ref →
   `error/type_mismatch`; each reference in order: missing element →
   `error/dangling_ref`, element type not fitting the slot type or family →
   `error/type_mismatch`; a number literal is accepted in an input slot of
   type `number` (it is the defined value `{value, unit: "scalar"}` and no
   dependency) and is a `type_mismatch` elsewhere. Then each param in
   registry order: absent and required → `error/schema`; not a number
   literal → `error/type_mismatch`. An `expr` or `template` slot (1.4, a5)
   takes only an argument of that kind (else `error/type_mismatch`), and
   after the params a tree or a template that the rules refuse, with the
   item count of `refs`, is `error/formula`.
   The first problem found wins;
4. a free op whose element (first output slot) has no usable input value of
   its kind → `error/schema`; an absent `angle` input is `0`;
5. **upstream**: among the input elements (registry slot order, list items in
   order) that are not `defined`, take the worst state by
   `error > unsupported > undefined`, the first one on a tie; every output
   gets that state, `reason: "upstream"` and `cause` = that input's `cause`,
   or its ID when it has none (so `cause` always names the root element);
6. otherwise the implementation runs (`ops/*.md`) on the input values; a
   `path` slot also receives the frame of its element (§5.5). A value with
   NaN/∞ becomes `undefined/non_finite`; an exception gives `error/internal`
   and a `diagnostics` entry `{code: "internal", operationId, op, message}`.

Every output slot is always computed; the elements bound to the op take
their slots. An element left without a record (never in 1.1–1.4) is `error/schema`.

### 5.3 Checks

Every operation that ran, produced a value for every slot of its result and
whose every element (by `producer.operationId`) is `defined` gets its registry
checks. A check measures an error `e ≥ 0` (a length) from the inputs and the
full op result; `e ≤ 1e-9·S` → `passed`, `e ≥ 1e-6·S` → `failed`, otherwise
(or non-finite `e`) → `inconclusive`. Report key: `"<operationId>:<checkId>"`.
The formulas are in the op pages. The check of a mark (`equal`, `right`) is
the claim it draws: a `failed` status says the drawing no longer matches
the claim; it does not change the mark's state.

Since 1.8.1a4 `native.check(doc, checks=None, *, inputs=None,
relations=None, trials=0, seed=None)` also measures relations between
elements (`incident`, `parallel`, `perpendicular`, `equal_length`,
`equal_angle`, `collinear`, `concyclic`, `concurrent`, `tangent`; report key
`"relation:<id>"`, status `unsupported` for an unknown predicate or argument
type) and, with `trials > 0`, re-evaluates the document with perturbed free
inputs (`general_position`). The predicates, the generator and the
aggregation are in [checks.md](checks.md).

### 5.4 Branches and slot policies

An operation with several solutions has one output slot per solution; the
policy of the registry record (`branch.policy`, `_policies.json`) says which
solution goes to which slot. The slot is part of the document, so a dragged
input never swaps two elements, and a solution that disappears leaves its
slot `undefined` instead of moving another solution into it.

| policy | slots |
|---|---|
| `single` | one solution, one slot (every op without a `branch` record) |
| `line_param_order` | `first` has the smaller parameter `t` along the orientation of the linear input (`dir` of a line or ray, `b − a` of a segment). The slots are fixed on the **carrier line** before the part filter of a segment or a ray, which then works per slot: when the first solution leaves the segment, the second stays in `second` |
| `circle_side` | `first` lies to the left of the directed segment from the first centre to the second (`(c2 − c1) × (X − c1) > 0`), `second` to the right; swapping the inputs swaps the slots |
| `other_than` | one slot: the solution of the base pair other than the explicit argument `known`; tangency at `known` gives `known`; `known` not among the solutions → `undefined/branch_absent` |
| `tangent_side` (1.4) | tangents from a point: `tangent.1`, `touch.1` to the left of the ray from the point to the centre, `tangent.2`, `touch.2` to the right; a point on the circle fills both slots with the tangent at it (`multiplicity 2`, directions continuous with the outside case); inside → `point_inside` |
| `bisector_kind` (1.4) | `internal` has the direction `normalize(d1 + d2)`, `external` is it turned by `+90°`; for parallel lines the slot whose direction sum is not zero is the midline, the other is `parallel` (`coincident` for one line) |
| `vertex_index` (1.4) | `polygon`, `side.i` from `vertex.i` to `vertex.(i + 1)` (`side.n` closes), `vertex.k` from one; `vertex.1 = a`, `vertex.2 = b` exactly; a clockwise input stays clockwise (the area is unsigned) |
| `sector_sides` (1.4) | `arc.1`, `arc.2` on the arc in the order of the line parameter (fixed on the carrier circle before the part filters), `side.1` on the radius `c → S0`, `side.2` on the radius `c → S1` |
| `nearest_to` (1.4, a5) | one slot: of the solutions of the base pair (its order, after the part filters) the one nearest to the argument `near`; a distance within `tol.decide` of the best keeps the earlier solution (decision `nearest_tie`); no defined solution → the reason of the first one |
| `first_curve_order` (1.8) | `first … fourth` in the order along the first input: a circle or an ellipse by the counterclockwise angle of `X − c1` from the direction to the second centre (or vertex) in `[0, 2π)` (`circle_side` for two circles), a hyperbola by branch (`U < 0` first) then along `n`, a parabola along `n`, an arc by its fraction from `a0`; a tangency fills two slots (`multiplicity: 2`), slots beyond the points are `branch_absent`; the slots swap where a point crosses the seam (the ray `c1 → c2`, `a0`) — [intersect.conic_conic](ops/intersect.conic_conic.md) |

**Arc filter** (1.4). An arc in a `circular` slot is intersected as its
carrier circle; the slots are fixed there, then each slot is kept only on
the arc: `φ = θ − a0` wrapped into `[0, 2π)` (`θ` the direction of the
solution from the centre), the solution is on the arc when `r·(φ − sweep) ≤
tol.decide` or `r·(2π − φ) ≤ tol.decide`, otherwise the slot is
`undefined/outside_part` with `detail: {"slot": <the arc's argument slot>}`
(`circle` of `intersect.line_circle`, `first`/`second` of
`intersect.circle_circle` and `intersect.other_than`, `sector` of
`intersect.line_sector`). A double root keeps its `multiplicity` only when
it stays.

A tangency (`|δ| ≤ tol.decide` for a line and a circle, `|e1|` or `|e2| ≤
tol.decide` for two circles) is a double root: both slots hold the touching
point with `detail: {"multiplicity": 2}`. A slot outside the part loses
that detail; `intersect.other_than` drops it.

`intersect.line_line` with a ray input filters the ray before the segment
check of the same slot (`s < −tol.decide` → `outside_part`); an intersection
exactly at a segment end or at a ray origin is inside the part.

### 5.5 Path parameter (`carrier/v1`)

`point.on_path` is free: its value comes from the input
`{"kind": "pathParameter", "value": t, "branch"?: ±1, "pathKind"?: kind}`
(`branch` picks the branch of a hyperbola, registry 1.9; other paths ignore
it; `pathKind`, registry 1.9, is the kind of conic the parameter was written
for, see §16). The parameter
lives in the frame of the path's definition (`_types.json` → `paths`), so the
point moves with the path:

| path | kind | frame | parameter | default |
|---|---|---|---|---|
| segment | affine | `o = a`, `v = b − a` | clamped to `[0, 1]` | `0.5` |
| line by `line.by_points` | affine | `o = a`, `v = b − a` (the producer's points) | any | `0.5` |
| other line | affine | `o = p`, `v = dir` | any | `0.5` |
| line by `line.parallel`, `line.perpendicular` | affine | `o = point`, `v = dir` | any | `0.5` |
| line by `line.perpendicular_bisector` | affine | `o = mid(a, b)`, `v = dir` | any | `0.5` |
| line by `line.angle_bisector` | affine | `o = vertex`, `v = dir` | any | `0.5` |
| ray by `ray.by_points` | affine | `o = origin`, `v = through − origin` | `t < 0` → `0` | `0.5` |
| other ray | affine | `o = origin`, `v = dir` | `t < 0` → `0` | `0.5` |
| circle | angle | centre `c`, radius `r` | angle from +x | `π/4` |
| polygon (`n` vertices `V`) | perimeter | the sides in order | wraps to `[0, n)` | `0.5` |
| line by `line.external_bisector` | affine | `o = vertex`, `v = dir` | any | `0.5` |
| line by `line.tangents_from_point`, `line.tangent_at` | affine | `o = point`, `v = dir` | any | `0.5` |
| ray by `ray.at_angle` | affine | `o = origin`, `v = dir` | `t < 0` → `0` | `0.5` |
| arc (1.4) | arc | `c`, `r`, `a0`, `a1` | fraction of the arc, clamped to `[0, 1]` | `0.5` |
| sector (1.4) | sector | the arc, then the radius `S1 → c`, then `c → S0` | wraps to `[0, 3)` | `0.5` |
| polyline (1.4, `n` vertices) | polyline | the links in order | clamped to `[0, n − 1]` | `0.5` |
| conic (1.9) | conic | `u = axis`, `n = (−u_y, u_x)` of the value | ellipse: eccentric anomaly from `u`, wraps to `[0, 2π)`; hyperbola, parabola: any, with `branch` | `π/4` |
| function (1.9) | graph | the graph `y = f(x)` | `x`, clamped to the domain | `0` |

    affine:     point = o + clamp(t)·v
    angle:      point = (cx + r·cos t, cy + r·sin t)
    perimeter:  t' = t − n·floor(t / n);  t' < 0 → t' + n;  t' ≥ n → 0
                k = floor(t'), f = t' − k
                point = V[k] + f·(V[(k + 1) mod n] − V[k])     (side side.(k + 1))
    arc:        φ = a0 + clamp(t, 0, 1)·(a1 − a0);  point = (cx + r·cos φ, cy + r·sin φ)
    sector:     w = t wrapped into [0, 3) like perimeter;  S_i = c + r·(cos a_i, sin a_i)
                w ≤ 1: the arc point of w;  w ≤ 2: S1 + (w − 1)·(c − S1);  else c + (w − 2)·(S0 − c)
    polyline:   w = clamp(t, 0, n − 1);  k = min(floor(w), n − 2);  f = w − k
                point = V[k] + f·(V[k + 1] − V[k])
    conic:      ellipse    point = c + a·cos t·u + b·sin t·n
                hyperbola  point = c + β·a·cosh t·u + b·sinh t·n     (β = branch, default 1)
                parabola   point = V + (p·t²/2)·u + p·t·n
    graph:      x = clamp(t, lo, hi) by the domain;  point = (x, f(x));  no value → out_of_domain

The frame of a path element comes from `frames[<producer op>]` (on the
values of the producer's arguments) when its producer is listed there,
otherwise from `frames["*"]` (on the element's own value). A frame
expression is a term or a difference `<term> - <term>`; a term is
`<src>.<field>` (`src` is `value` or `args`) or `mid(<term>, <term>)`, the
midpoint `((x1 + x2)/2, (y1 + y2)/2)`.

`native.project(doc, id, (x, y), *, inputs=None) → t | None` is the inverse:
the parameter of the nearest point of the path (`id` is the path or a
`point.on_path` point, then its path), `None` when the path is not defined,
`ValueError` when the element is not a path. Ties (the centre of a circle, a
polygon corner) go to the smallest parameter; formulas in
[point.on_path](ops/point.on_path.md).

## 6. Parity fixtures `animageo-parity/v1`

Scene (`parity/v1/scenes/*.json`): `{format, id, document, cases: [{name,
inputs?}]}`. `fixtures generate` writes `{format, id, registry, generatedBy,
document, cases: [{name, inputs?, scale, expect, checks}]}` where `expect` is
the record of every element (§5) and `checks` maps keys to statuses; each case
has its own `scale`.

`fixtures verify` evaluates again and compares: `state`, `type`, `reason`,
`cause`, `detail` exactly; numbers in values within `tol.parity` of the
case's `scale` by the field kind of `_types.json` (`length`, `area`,
`scalar`); a field of kind `by_unit` (the `value` of a number) takes the
kind of its unit (`numberUnits`: `scalar → scalar`, `length → length`,
`area → area`, `angle → scalar`, `count → scalar`); fields the kinds do not
list (the `unit` of a number, the `kind` and `count` of a mark) compare
exactly; arrays by length and item; check statuses exactly; the scale
within `1e-9·S`. An angle compares its `vertex` as lengths and `a0`, `a1`,
`size` as scalars: the generator keeps cases away from the jumps of `a0`
and `size` between `0` and `2π` (below).

**Near-degenerate inputs are refused.** Every degeneracy decision reports its
decision value `m`, measured from the exact mathematical boundary, and the
decide tolerance `tol` it is compared to (listed per op). The generator
refuses a case when

    0 < |m| < 1e3 · tol        (decisionMargin = 1e3, _numeric.json)

so a fixture never depends on which side of `tol` a rounding error falls.
`m = 0` exactly — a degenerate configuration built from binary-exact inputs
(equal points, axis-parallel lines, an intersection exactly at a segment
end) — is accepted.

**Noise decisions** (`generator.noiseDecisions = ["known", "tangent",
"straight_angle"]`): for these, `|m| ≤ tol / 1e3` also counts as exactly on
the threshold. Their values are the rounding noise of an exact construction
— a tangent built as a tangent, a `known` point that is an intersection of
the same pair, a straight angle of collinear points — and cannot be made
binary-exact. A noise value between `tol / 1e3` and `1e3·tol`
is still refused. The decisions `angle_wrap` and `zero_angle` of
`angle.by_points` (registry 1.3) are not noise decisions: the value jumps
across their boundaries, so a case near them is refused even when it is
built exactly; only `m = 0` exactly is accepted.

Library set (`animageo/native/parity/v1/`, 71 scenes):

- registry 1.0: `basic_points`, `segment_line`, `circle`, `intersect_lines`,
  `intersect_segments`, `polygon_triangle`, `polygon_quad`, `upstream_chain`,
  `graph_errors`;
- rays: `ray_points`, `ray_segment_cross`, `ray_circle`;
- a line and a circle: `line_circle_order`, `line_circle_tangent`,
  `line_circle_miss`, `segment_circle_part`, `segment_circle_zero`;
- two circles: `circle_circle_sides`, `circle_circle_tangent_out`,
  `circle_circle_tangent_in`, `circle_circle_apart`,
  `circle_circle_concentric`;
- the other point: `other_than_line_circle`, `other_than_circles`,
  `other_than_tangent`, `other_than_absent`;
- points on paths: `on_path_segment`, `on_path_line_ray`, `on_path_circle`,
  `on_path_polygon`, `on_path_chain`;
- registry 1.2: `projection`, `parallel_perpendicular`,
  `perpendicular_bisector`, `angle_bisector`, `vector_points`,
  `circle_center_radius`, `circle_three_points`, `number_free`,
  `on_path_l2_lines`, `l2a1_chain`;
- registry 1.3: `angle_points`, `angle_zero_wrap`, `marks_equal_segments`,
  `marks_equal_angles`, `marks_right_angle`, `incircle`,
  `incircle_touch_chain`, `a3_chain` (marks both passed and failed);
- registry 1.4: `l2a4_divide`, `l2a4_center`, `l2a4_closest`,
  `l2a4_at_distance`, `l2a4_vertex`, `l2a4_bisectors_lines`,
  `l2a4_external_bisector`, `l2a4_ray_at_angle`, `l2a4_ray_by_vector`,
  `l2a4_tangents`, `l2a4_tangent_at`, `l2a4_segment_length`, `l2a4_midline`,
  `l2a4_polyline`, `l2a4_circles`, `l2a4_arcs`, `l2a4_sectors`,
  `l2a4_on_path_arcs`, `l2a4_regular`, `l2a4_parallelogram`,
  `l2a4_line_sector`, `l2a4_arc_filter`. A line through the centre of a
  sector (both radii met at `s = 0` up to rounding) is left to unit tests:
  its decision value is rounding noise of a non-exact zero.

At least three cases per op; degenerate cases with binary-exact inputs or a
noise decision.

## 7. Command line

```text
python -m animageo.native fixtures generate <scenes…> -o <dir>
python -m animageo.native fixtures verify <fixtures…>          # exit 1 on a mismatch
python -m animageo.native registry index [--check]             # exit 1 when out of date
python -m animageo.native evaluate <doc.json> [--inputs case.json] [--checks] [--canonical]
python -m animageo.native validate <doc.json> [--json]          # exit 1 when there are issues
python -m animageo.native commands fixtures|parse|print …       # «Команды», commands.md §10
python -m animageo.native fixtures timeline [--check]           # animageo-timeline/v1, timeline.md §5
python -m animageo.native fixtures paint [--check]              # animageo-paint-parity/v1, §9.8
python -m animageo.native fixtures curves [--check]             # parity/v1/curves: graphs and conics, §14
python -m animageo.native fixtures drag [-o <dir>] [--check]    # animageo-drag-parity/v1, §8.1
python -m animageo.native style export [--check]               # native/style: builtin.json, keys.v1.json, §9.8
python -m animageo.native steps|describe|timeline <doc.json> …  # timeline.md §5
python -m animageo.native from-ggb <file.ggb> [-o …] [--report …] # import.md §7
python -m animageo.native convert map [--check]                 # import.md §1
```

Exit codes: `0` success; `1` a verify mismatch, an issue found by `validate`
(a document that is not valid JSON is such an issue), an out-of-date index or
a scene the generator refuses; `2` an input that cannot be used — a missing
file, or for `evaluate` a document that does not load or bad `--inputs`.

`python -m animageo.native` does not import manim (the package `__init__`
skips the classic API for this entry point). Rendering a document from the
command line is `python -m animageo doc.json …` (§9.6).

## 8. Graph queries and edits

`animageo/native/edit.py`, exported from `animageo.native`. Queries return
element ID lists; edits return `EditResult(document, effects)` — a new
`NativeDocument` and what changed — and never change their input. Edits
never create or change IDs. A refused edit raises `EditError(issues)` with
`Issue` records (`code`, `path`, `message`, `elementId?`, `operationId?`).

**Topological order** of elements: operations in Kahn order (ties by
operation ID; members of a cycle wait for nothing), the elements of one
operation by ID, then elements without a consistent producer by ID. Every
query lists its result in this order.

| function | result |
|---|---|
| `closure(doc, ids, *, direction="down")` | the elements reachable from `ids` (included): `"down"` the dependents, `"up"` the ancestors; `ValueError` for an unknown ID |
| `dependencies(doc, id)` | the ancestors of `id`, without it |
| `free_inputs(doc, ids)` | the free elements (`point.free`, `point.on_path`) among `closure(ids, "up")` |
| `delete(doc, ids, *, mode="element")` | `closure(ids, "down")` goes; an operation loses the outputs that went and goes when none are left or when it references a removed element; `mode="operation"` also removes every other output of the producers of `ids`. Inputs, appearance and `bindings.legacyNames` of removed elements go; a removed operation leaves its step in `steps`, a step left empty goes (no step left — no `steps`; 1.10.0a2) |
| `redefine(doc, op_id, new_op, *, slot_map=None, inputs=None)` | replaces the definition (`{op, args, branch?}`) keeping the output IDs: outputs pair with new slots by name or `slot_map`; an output without a pair goes with its dependents (warning `output_removed`); types and producers of the paired elements follow the new op; `inputs` gives the input values a new free op needs; the inputs of elements that stop being free go |
| `rename(doc, id, display_name)` | sets `displayName`; the graph does not change |

`effects` is JSON-ready; every list is sorted:

```text
{"added":    {"operations": [], "elements": [], "inputs": []},
 "removed":  {"operations": [], "elements": [], "inputs": [], "appearance": []},
 "modified": {"operations": [], "elements": [], "inputs": []},
 "warnings": [Issue.to_dict(), …]}
```

When an edit changes `steps` (1.10.0a2), `removed.steps` lists the steps
that went and `modified.steps` the steps that lost operations; the keys are
absent otherwise. When a redefine drops drag hints (1.12.0, §8.1),
`removed.drag` lists their elements; the key is absent otherwise.

Refusal codes:

| code | edit | when |
|---|---|---|
| `unknown_element` | delete, rename | an ID is not an element |
| `unknown_operation` | redefine | `op_id` is not an operation |
| `unknown_op` | redefine | the new op is not in the registry |
| `slot_conflict` | redefine | two outputs map to the same new slot |
| `type_mismatch` | redefine | a new output type does not fit an operation that uses the element |
| `cycle` | redefine | a new argument depends on an output of the operation |
| `missing_input` | redefine | a free op without an input of its kind in `inputs` or the document |
| `input_not_free` | redefine | `inputs` names an element that is not a free output of the new op |
| any `validate` code | redefine | an error the document did not have before (never a `drag` hint: §8.1) |
| `invalid_name` | rename | the name breaks the grammar |
| `duplicate_name` | rename | another element has the same name key |

Display names (`valid_name`, at most 32 code points):

    name   = letter+ suffix? "'"*
    suffix = "_{" alnum+ "}" | "_" alnum+ | [0-9]+ | [₀-₉]+

`letter` is a Unicode letter (category L*), `alnum` a letter or a decimal
digit (Nd): `A`, `AB`, `A1`, `A₁`, `A_1`, `A_{12}`, `α'`, `Точка`.
Uniqueness compares `name_key`, where `_{x}` equals `_x`.

### 8.1 Drag (`native.drag`, 1.12.0)

`animageo/native/drag.py`; `has("drag")`. `drag(doc, inputs, element_id,
target) → {"inputs", "status"}` moves the point `element_id` towards
`target = (x, y)` by changing input values; the document never changes.
`inputs` are the input values of the case (`{elementId: Input}` as for
`evaluate`; `None` is none), merged over the document's `inputs`.

| `status` | `inputs` returned |
|---|---|
| `ok` | a new dict: a deep copy of the given `inputs` with the moved entries set |
| `clamped` | the same, a path parameter stopped at an end of its range |
| `no_convergence` | the given `inputs` object itself, unchanged |
| `singular` | the given `inputs` object itself, unchanged |

The given `inputs` are never changed. `ValueError`: an unknown element, an
element that is not a point, a target that is not two finite numbers,
`inputs` that `evaluate` refuses, a dependent point without a hint, a hint
whose `via` fails §2.

**Which way.** In this order:

1. The element of `point.free`: its input becomes `target`; `ok`.
2. A point with `appearance.<id>.drag.via` (§1): Gauss–Newton over the
   `via` inputs (below).
3. The element of `point.on_path` without a hint: `t = project(path,
   target)` (§5.5, as `native.project`); the input is its current input
   with the entries of `native.project_input` set (`value: t`; registry
   1.9: a conic also `pathKind`, its kind at rest, and a hyperbola `branch`,
   the nearest branch — the point may change branch), its other keys (a
   `branch` elsewhere) kept; `clamped` when the path is clamped (`outside`
   of the frame is `clamp`: segment, ray, arc, polyline, a graph with a
   given end of its domain), `t` equals an end of its range and the
   distance from the point at `t` (on its branch) to the target is above
   `tol`; else `ok`. A path that is not defined at rest, or a graph without
   a point in its search interval (§16) — `no_convergence`.
4. The element of `point.on_function` without a hint
   ([ops/point.on_function.md](ops/point.on_function.md)): the input
   becomes `x = target.x`, clamped into the domain `[min, max]` of the
   function at rest where an end is given — `clamped` when `target.x` lies
   outside it, else `ok`. The function not defined at rest, or the point not
   defined at the new `x` (no value of `f` there) — `no_convergence`; the
   nearest `x` with a value is not searched.
5. Any other point — `ValueError`.

**Variables.** `S` (scene scale) and `tol = tol.decide` (length, `1e-10·S`)
come from `evaluate(doc, inputs)` at rest. Constants: `STEP_FRACTION =
1e-5`, `RANK_EPSILON = 1e-6`, `CURVATURE_FLOOR = 1e-2`, `ACCEPT_SLACK =
1e-3`, `MAX_ITERATIONS = 8`, `MAX_HALVINGS = 4`. The vector `u` joins the
`via` values in `via` order: a `point` input gives `x, y`, a `pathParameter`
input gives `t`. Per variable:

| variable | difference step `h` | range |
|---|---|---|
| coordinate | `STEP_FRACTION · S` | none |
| `t`, both ends finite | `STEP_FRACTION · (hi − lo)` (`STEP_FRACTION` when `hi = lo`) | clamped (`outside: "clamp"`) or wrapped (`"wrap"`: circle, polygon, sector, circle segment; registry 1.9: an ellipse, `[0, 2π)`) |
| `t`, an end infinite (line, ray; registry 1.9: hyperbola, parabola, graph) | `STEP_FRACTION · S / unit`, `unit` at rest: `|v|` the length of the frame vector (line, ray), `b` (hyperbola), `p` (parabola), `1` (graph); `STEP_FRACTION` when `unit ≤ tol` | ray clamped at `0`, a graph at the given end of its domain, line, hyperbola, parabola and a graph without a domain none |
| `x` of `point.on_function` | `STEP_FRACTION · S` (`c = 1`) | clamped into the domain at rest, each end only where given |

`lo, hi` are `parameter_range` of the path frame at rest (§5.5, §16); the
range is that of `outside(frame)` (`kernel/paths.py`: `_types.json →
paths.<type>.outside`, a conic by its kind, a graph `clamp` with a given
end of its domain). A clamped `t` starts clamped into its range (at each
given end). The column scale is `c = h /
(STEP_FRACTION · S)` (`1` for a coordinate). `f(u)` is the point
`element_id` of `evaluate(doc, inputs ⊕ entries(u))`, *undefined* unless its
state is `defined`; `entries(u)` writes `{"kind": "point", "value": [x, y]}`
and the current `pathParameter` input with `value: t` (its other keys —
`branch`, `pathKind` — kept; a hyperbola branch is not switched).

**Stencil** at `u` with `p = f(u)`: per variable `j`, `u⁺ = u_j + h`, `u⁻ =
u_j − h`, then `u⁺ = min(u⁺, hi)`, `u⁻ = max(u⁻, lo)` for a clamped range
(no clamp for a wrapped one). Width `w = u⁺ − u⁻`; `w ≤ 0` gives the column
`(0, 0)` without evaluation. Else `col_j = c_j · (f(u⁺) − f(u⁻)) / w`; an
undefined `f(u±)` makes the whole stencil undefined. With a single variable
and both `h⁺ = u⁺ − u_j > 0`, `h⁻ = u_j − u⁻ > 0`, the second difference
`f″ = 2 · ((f(u⁺) − p)/h⁺ − (p − f(u⁻))/h⁻) / w`; else `f″ = (0, 0)`.

**Rank and least-norm step** of the 2×k matrix `Ĵ` of columns `col_j`:
`F = Σ|col_j|²`, `P = Σ_{i<j} (col_i × col_j)²` (`× ` the 2-D cross
product; `P = det ĴĴᵀ`, Cauchy–Binet), `σ₁² = (F + √max(F² − 4P, 0)) / 2`,
`σ₂ = √(P / σ₁²)` (`0` when `σ₁² = 0`). A singular value counts when it is
above `ε = RANK_EPSILON · max(1, σ₁)`: rank 0 when `σ₁ ≤ ε` (`d = 0`), rank 1
when `σ₂ ≤ ε` (`d_j = −(col_j · r) / F`), else rank 2 with `a = Σx²`, `b =
Σxy`, `e = Σy²` over the columns, `w = ((e r_x − b r_y)/P, (a r_y − b
r_x)/P)`, `d_j = −(col_j · w)`. The step of variable `j` is `δ_j = c_j ·
d_j` (`r = p − target`).

**Active set.** Start with every variable free; solve on the free columns;
a free variable of a clamped range with `u_j ≤ lo` and `δ_j < 0`, or `u_j ≥
hi` and `δ_j > 0`, is frozen (`δ_j = 0`); repeat until none is frozen anew.
The predicted move is `moved = |Σ_{free j} col_j δ_j / c_j|`; `frozen` is
whether any variable was frozen.

**Step length** `λ₀`: `1` with two or more variables. With one: `A =
|col/c|²`, `B = r · f″`; `λ₀ = 1` when `A = 0` or `|B| ≤ CURVATURE_FLOOR ·
A`; else with `L = max(1, S / moved)`: `λ₀ = L` when `A + B ≤ 0`, else
`λ₀ = min(A / (A + B), L)` — the Newton step of `|r|²/2` along `δ`. Plain
Gauss–Newton on a curved path far from the target overshoots or falls
short by that factor (it converges only linearly); `L` keeps a long step
within the scene.

**Line search** with `ε = ACCEPT_SLACK · tol`, `limit = |r| + ε`: for `k =
0 … MAX_HALVINGS`, the trial `ũ = clamp(u + λ₀ 2⁻ᵏ δ)` (clamped ranges
only) and `q = f(ũ)`; an undefined `q` is skipped. The first defined trial
is kept; a later one replaces the kept one only when `|q − target| <
|kept| − ε`; the search stops at a kept `|q − target| ≤ tol`, or at a
defined trial that does not replace a kept one already within `limit`. The
kept trial is taken when it is within `limit`, else none is.

**Solve.**

1. The inputs of `via` lack a usable value, a path or a function is not defined, `f(u₀)`
   or its stencil is undefined → `no_convergence`.
2. `rank₀` = the rank of the stencil at `u₀`; `rank₀ < min(2, dim u)` →
   `singular` (also when the point already is at the target).
3. While `|r| > tol`, fewer than `MAX_ITERATIONS` steps and the stencil is
   defined: active-set step; `moved ≤ tol` ends (stationary); the line
   search taking none ends; else `u, p` become the trial, one more step, and
   when `|r| > tol` the stencil is computed at the new `u` (from its `p`).
4. Status: `|r| ≤ tol` → `ok`; the last stencil undefined →
   `no_convergence`; else with the active-set step at the end, `moved ≤ tol`
   and `frozen` → `clamped`; `moved ≤ tol`, `rank₀ < 2` and not the
   farthest point → `ok` (the nearest point a single parameter reaches);
   otherwise `no_convergence`. The farthest point: a single variable with
   `A + B < −CURVATURE_FLOOR · A` (`A`, `B` as for `λ₀` at the end) — the
   target straight across a curved path, where the step is zero.
5. `ok` and `clamped` return `entries(u)`; a wrapped `t` is written back as
   `t − (hi − lo) · ⌊(t − lo) / (hi − lo)⌋`, and `lo` when that is `≥ hi`
   or `< lo`.

Affine dependencies (the fourth vertex of a parallelogram, a reflection, a
translation, a midpoint) are solved in one step to rounding (≈ `1e-12·S`).
The solve evaluates the whole document per probe (`2·dim u` per stencil, at
most `MAX_HALVINGS + 1` per step).

**Validation** (§2): `via` items must be the input elements of
`point.free`, `point.on_path` or `point.on_function` upstream of the point;
`drag_singular` is `rank₀ < min(2, dim u)` (`dim u` as above: a `point`
input 2, a path parameter or an `x` 1) at the document's own inputs.

**Edits.** A hint is display data and never refuses an edit. `redefine`
(with conditions too) drops from the result every `appearance.<id>.drag`
that has an error of §2 — its point gone or no longer a point, a `via` item
missing, no longer free (`drag_via_not_free`) or no longer upstream
(`drag_via_not_upstream`): only the `drag` key goes, the rest of the entry
stays; `effects.removed.drag` lists those elements (absent when none went).
A hint with only `drag_singular` stays. `delete` needs no such rule: an
input of a valid hint is an ancestor of its point, so they go together.

**Fixtures** `animageo/native/parity/v1/drag/*.json`, format
`animageo-drag-parity/v1`, one case per file: `{format, id, generatedBy,
text, doc, inputs, element, target, expect: {status, inputs}}` where
`expect` is `native.drag(doc, inputs, element, target)`. A port compares
the status exactly; on `no_convergence` and `singular` `expect.inputs`
equals `inputs` and the call must return the given object; on `ok` and
`clamped` a new object whose entries match by key, `kind`, `branch` and
`pathKind` exactly and every number within `1e-9` absolute (world units for a point,
parameter units for a path parameter). Success numbers are written rounded
to 10 digits. Each document declares the lowest registry version its
operations need. `python -m animageo.native fixtures drag [-o <dir>]
[--check]` writes them or checks the shipped ones against the generator;
`drag_fixtures.verify_fixtures(dir)` replays them.

## 9. Rendering

`native.render` draws a document with the classic renderer: the bridge turns
it into an `animageo.geo.Construction`, `AnimaGeoScene.loadDocument` lays it
out and styles it exactly as `loadGGB` does a `.ggb`. It needs manim (and
LaTeX for labels); `source_view`, the appearance mapping and the label
layout (§9.7) do not.

### 9.1 Source view

The analogue of the applet window of a `.ggb`:

    bounds  = viewDefaults.bounds or defaultBounds          [xmin, ymin, xmax, ymax]
    ptWidth = 800,  ptUnit = 800 / (xmax − xmin)
    ptHeight = (ymax − ymin)·ptUnit
    ptXZero = −xmin·ptUnit,  ptYZero = ymax·ptUnit

`native.source_view(doc)` returns `{ptWidth, ptHeight, ptUnit, ptXZero,
ptYZero}`. The source unit also serves as `ptUnit_ggb`, so label offsets
are in world units. `export_layout.content.source = "source_view"` frames
this rectangle.

### 9.2 Bridge

`kernel/bridge.py`: `build_construction(doc, *, inputs=None, seed=None) →
(Construction, Names)`.

- Every element becomes a classic element named `e_<id>`: a UUID as 32
  lowercase hex digits, other characters outside `[A-Za-z0-9_]` as `_`;
  collisions get `_2`, `_3`… in ID order. `Names.by_id` / `Names.by_name`
  map the two ways (`scene.native_names` after `loadDocument`).
- A free point is a level-0 element; a `point.on_path` point keeps its
  parameter in the classic `tparam`, so animations move it along the path;
  every other operation is a `NativeCommand` (with `operation_id`) whose
  function runs the kernel implementation on the classic values.
  `rebuild(full=True)` therefore gives the values of `native.evaluate`
  bit for bit (tested on every fixture case).
- A free number is a level-0 `Var` holding the kernel value (clamped to
  `min`/`max`; `None` when undefined). Values convert by type: a vector is
  a classic `Vector`; a number is a `float` (`scalar`), a `Measure` of
  dimension 1 or 2 (`length`, `area`), an `AngleSize` (`angle`) or a
  `Measure` of dimension 0 (`count`). Params and number literals are
  constants of the command, not classic inputs.
- An angle (registry 1.3) is a classic `Angle(vertex, side1, side2)`
  carrying the kernel `size`; `angle.by_points` gives it the sides
  `a − vertex` and `b − vertex` (the classic arc radius depends on their
  lengths, so the arc is that of a DSL `Angle(A, B, C)`), other values unit
  sides along `a0` and `a1`. A right-angle mark is a classic `Angle` of its
  three points, drawn with the right-angle marker (§9.3); an equality mark
  is a `NativeMark(kind, count)` with no geometry — the renderer draws its
  ticks on the targets. Back to kernel values: a `NativeMark` gives
  `{kind, count}`, the angle of a right-angle mark `{kind: "right_angle",
  count: 1}`.
- Registry 1.4: an arc is a classic `Arc` and a sector a `CircleSector`
  whose `angles` are the kernel `[a0, a1]` as they are (a full arc keeps
  `a1 = a0 + 2π`; the classic constructor would fold it to zero); a
  polyline is a `LocusCurve` of its vertices. The free `angle` input of
  `segment.from_point_length` is a constant of the command (the document's
  value, `0` when absent).
- The renderer draws the classic types of `animageo.geo.DRAW_ORDER` (by
  exact type, in that order of layers); a number, an equality mark and an
  undefined element are not drawn (`geo.is_drawn`).
- Elements are created in the operation order of `evaluate` (Kahn, ties by
  operation ID; outputs by slot), as a DSL creates them line by line; the
  renderer breaks z-index ties by this order. Elements of structurally
  broken operations come last in ID order and stay undefined.

### 9.3 Appearance

`appearance` is `{elementId: {visible?, label?: {mode?, text?,
offsetWorld?}, overrides?}}`. Each element gets:

- `visible` (default `true`); an invisible element is not drawn;
- the label: `mode` defaults to `name` for a point and `none` otherwise
  (as on the web canvas). `name` → classic `label`, `value` → `value`,
  `name_value` → `label_value`, `caption` → `label` with `text` as the
  label text, `none` → no label. `name` and `name_value` need a non-empty
  `displayName`; `displayName` is the label name. 1.11.0
  (`has("label.parts")`): a name is TeX in math mode, as GeoGebra shows it —
  `_x` indexes the one character (or command) after it (`A_12` is A₁2,
  `S_бок` is S with the index б), `_{…}` a group, `^` raises the same way;
  consecutive Unicode subscript digits form one index (`B₁₂` is `B_{12}`),
  with ASCII digits and `script: "sub"` in `label.parts`;
  an `_` or `^` with nothing to take (at the end, before a space, another
  script sign or a closing brace), a brace without its pair and the signs
  `% # & $ ~` are the characters themselves (`~` is `∼`), so a name of
  letters (Latin, Greek, Cyrillic), digits and ASCII signs compiles; a
  backslash starts a TeX command, kept as written (`labels.name_tex`). The
  still, the video and `resolve_paint` (`label.text`, `label.parts`, §9.8)
  set one text;
- `offsetWorld: [dx, dy]` (world units, y up) → `label_offset_px =
  [dx·ptUnit, dy·ptUnit]` of the source view, and the label is locked
  against automatic placement;
- `overrides`: element style keys (stroke, fill, points, labels, ticks,
  arrows, angles, `z_index`, `z_index_fill`; the list is
  `rendering.APPEARANCE_STYLE_KEYS`). Other keys are not applied.
  1.11.0 (`has("label.halo")`): the halo of a label — `label_halo_px` (the
  width of a stroke of its glyphs drawn under them, style px, half of it
  outside; `0` draws none), `label_halo_color` (default the background
  colour), `label_halo_opacity` (default `1`); an element without them takes
  `rendering.label_halo_*` of the style; the built-in style has no halo. It
  is drawn in SVG, PDF, EPS, PNG and the video (the `write` and `create`
  effects reveal it with its glyph), not in TikZ.
  1.11.0rc3 (`has("style_keys")`): `native.style_keys()` is the contract
  by type — `{format: "animageo-style-keys/v1", types: {type: {style, keys:
  {key: {unit, default, values?}}, transfers?}}}`, `type` a document type or
  a mark by its operation (`mark.right_angle`, `mark.equal_segments`,
  `mark.equal_angles`), `style` the classic style type (`sector` →
  `circlesector`, `polyline` and `locus` → `locuscurve`, `mark.right_angle`
  → `angle`, `null` for what is not drawn), `unit` one of `color`, `px`,
  `opacity`, `ratio`, `deg`, `count`, `enum`, `bool`, `number`, `string`,
  `default` the value under the built-in style. A key the element does not
  read is applied and reported as `style_key_ineffective` (below): the
  stroke of a polygon and of a sector is solid, the fill of a polygon lies
  at its `z_index` (no `z_index_fill`), a circle has no caps, an angle no
  ticks, a polyline or a locus no label, a text only `label_color`,
  `font_size_px` and `z_index`, a right-angle mark draws the square (no
  `tick_count`, `arc_shift_px`), a number, an expression or a template
  nothing.
  1.10.0a2 (`has("appearance.hatch")`): the hatching of a polygon, circle or
  sector — `fill_pattern` (`solid`, `hatch`, `crosshatch`, `dots`, `none`),
  `hatch_angle_deg`, `hatch_spacing_px`, `hatch_width_px`, `hatch_color`
  (`stroke` or a colour), `hatch_opacity` — the keys the style already had
  (`overlay.per_type`, `animageo/hatch.py`). An override is the element's
  own style: it wins over the style's `overlay` and draws the pattern on
  this element only, in SVG, PNG, PDF, EPS and TikZ alike.

Marks (registry 1.3, `native.appearance_plan`):

- a visible, defined equality mark (`mark.equal_segments`,
  `mark.equal_angles`) puts `tick_count = count` on its targets — the
  elements of its list argument, in order (`rendering.mark_targets`). An
  explicit `overrides.tick_count` of a target wins; of several marks on one
  target, the first mark in ID order wins. A hidden or undefined mark puts
  nothing. 1.11.0rc3: the `overrides` of the sizes of the ticks
  (`tick_length_px`, `tick_width_px`, `tick_shift_px`, `tick_style`,
  `tick_radius_px`) of `mark.equal_segments` and `arc_shift_px` of
  `mark.equal_angles` go to the targets the same way (an explicit key of a
  target wins); 1.11.0rc8: so does `arc_size_px` of `mark.equal_angles` —
  the radius of the arcs of its angles (the innermost arc).
  1.11.0rc13: `appearance[markId].overrides.stroke` is a six-digit hex colour
  (`#RRGGBB`) of the ticks/arcs only; the target's stroke and fill keep their
  own styles. `overrides.tick_count` is an integer from `0` to `3`: the drawn
  count, independent of the operation's semantic `count` (`1`, `2`, `3`).
  `0` draws no decoration. Omitting either override restores the target's
  stroke or the semantic count. On a right angle `tick_count` draws arcs
  instead of the square; a colour alone keeps the square. A target's own
  count and size overrides still win. Other keys are reported as `mark_transfers_only`;
- a visible, defined right-angle mark gets `right_angle_marker = true`
  unless its `overrides` set it to `false` (an explicit `null` is the
  square too).
- a visible, defined parallel mark (`mark.parallel`, registry 1.8) puts
  `parallel_count = count` and `parallel_direction` on its targets (the
  elements of its list, in order): the first target of a direction of
  non-zero length is the reference, a target whose direction (`b − a` of a
  segment or a vector, `dir` of a line or a ray) makes a negative dot
  product with it gets `backward`, every other `forward`
  (`kernel.ops.mark.parallel_directions`), so the chevrons of all the
  targets point the same way on the sheet. The directions are those of the
  values evaluated with the inputs of the frame (`resolve_paint` at `t`
  recomputes them; the classic renderer keeps those of the load). The
  mark's `overrides.parallel_direction: "backward"` turns them all;
  `parallel_count` (0–3, `0` draws none), `parallel_size_px` and
  `parallel_shift_px` go to the targets as the sizes of an equality mark; a
  target's own `parallel_*` key wins; of several parallel marks on one
  target the first in ID order wins a key. Its `stroke` colours only the
  chevrons and lives in a second channel `parallelDecoration: {owner,
  stroke}` beside `decoration`: one segment carries the ticks of an
  equality mark and the chevrons of a parallel mark at once, each in its own
  colour and owned by its own mark (an enter or exit effect of a mark is
  drawn on its own decoration only). `resolve_paint` and the render report
  give such a target `parallelDecoration: {owner, color, count, sizePx,
  shiftPx, direction}`; the chevrons themselves stay in `parallel`. TikZ
  and JSXGraph draw them in the colour of the channel;

For several equality marks on a target, the first visible, defined mark in
ID order owns the colour channel, even if it has no colour override (the
target's stroke is then used). Count and sizes retain the per-key rule:
the target's own key wins, then the first mark supplying that key. Hiding
or undefining a mark removes its contribution; showing it restores it.
No style is written back into the document or the equality value. Marks
remain decorations, while construction conditions remain `recipes/v1`.

`appearance_plan` keeps the target's body `style` separate from
`decoration: {owner, stroke, explicit}` (and `parallelDecoration: {owner,
stroke}` of a parallel mark). `stroke: null` means target stroke;
`explicit` means a colour or count override is present. The existing
count/size keys remain in `style` for compatibility. The bridge keeps the
colour channel outside the body's style resolver. With a new override an
equal-angle mark draws its requested number of arcs even at 90 degrees,
including when the target's ordinary decoration is a square. The fill colour and opacity
are unchanged. `load` rejects invalid colour/count overrides on equality
marks; `$defs/equalityMarkOverrides` in the construction schema is the
reusable schema for clients that have resolved the producer operation.
Other appearance entries retain their existing, open style contract.

`native/style/keys.v1.json` (from `python -m animageo.native style export`)
lists the new keys in `keys` and `transfers`; count values are `0..3`, and
both defaults are `null`. This is the source for the web's generated
`OVERRIDE_KEYS`, TypeScript and schema; consumers regenerate from the
exported contract rather than maintaining their own allow-list.

An element that is not drawn (§9.2: undefined, a number, an equality mark)
has no label: it is neither drawn nor seen by automatic placement
(`rendering.apply_appearance`).

**Point labels clear their marker** (1.8.1a2, documents only). A point
label that is neither pinned (`offsetWorld`) nor placed by the solver and
whose offset no layer sets (no `overrides.label_offset_px`, no style
`overlay` or element offset — only the point's built-in default) hangs off
its marker: with `e` the edge vector of the label anchor (`BL` = `(−1,
−1)`, `BC` = `(0, −1)`, `TR` = `(1, 1)`, …; the anchor is the element's
`label_anchor`, else `rendering.label_anchor` of the given style, else
`BL` — the built-in style sets none),

    label_offset_px = −e / |e| · (size_px / 2 + point_gap_px) · ptUnit_ggb / ptUnit_style

so the label box keeps `size_px / 2 + point_gap_px` decoration pixels
(`point_gap_px` of `overlay.label_placement`, default `3`) between its
nearest point and the centre of the point. `MC` (the box centred on the
point) is left as it is. A `.ggb` and a DSL scene keep the classic offset
(`[0.5, 0]` px from the anchor corner): the rule is switched on by
`AnimaGeoScene.loadDocument` only (`scene.label_point_clearance`).

Problems are reported, not raised, in `report.diagnostics`:
`{code: "unknown_element", elementId}`, `{code: "bad_label_mode",
elementId, mode}`, `{code: "bad_label_offset", elementId}`,
`{code: "unknown_style_key", elementId, key}`, `{code:
"style_key_ineffective", elementId, key, type, reason}` (1.11.0rc3; `type`
of `style_keys()`, `reason` — `not_read`: the drawing of the type does not
read the key, `not_drawn`: the element is not drawn, `mark_transfers_only`:
an equality mark passes only `transfers`, `single_arc`: `arc_shift_px` is the
distance between several arcs and an angle with `tick_count` ≤ 1 has one). The keys of a role are not
reported: a role is written for every type. A right-angle mark given
`right_angle_marker: false` is drawn as the arcs of an angle and reads the
keys of `angle` (its `tick_count`, `arc_shift_px`; 1.11.0).

### 9.4 `native.render`

```text
render(doc, *, style_config=None, export_layout=None, fmt="svg", out=None,
       inputs=None, t=None, timeline=None, report=True) -> RenderResult(path, fmt, report)
```

- `style_config`: a style dict (on the web: after `migrate_style_config` and
  `style_config_for_animageo`), a style file path, a packaged preset name or
  `None` (built-in). The document's `styleBinding` is not read.
- `export_layout`: `{reference?, content?, export?}` — the placement keyword
  arguments of `loadGGB`; another key or a non-mapping is a `ValueError`.
- `fmt`: `svg`, `png` (the SVG rasterised by cairosvg) or `pdf` (96 dpi);
  another format, `t` or `timeline` → `NotImplementedError`.
- `out`: the file to write (a temporary file when `None`); `path` is its
  absolute path.
- `inputs`: case overrides as in §5.2 (`ValueError` when not usable).
- A document that does not load → `LoadError` (a `ValueError`); no manim →
  `RuntimeError("native.render needs manim …")`; no cairosvg for PNG →
  `RuntimeError`.
- `report=False` → `RenderResult.report is None`.
- `t` with `timeline` (1.11.0, `has("render.t.effects")`): the frame of the
  video at `t` — effects, events, labels placed at keyframes and explicit
  `inputs` as the video draws them; the report gains `t`, `visible` and
  `effects` (`docs/native/timeline.md` §3).

All argument errors are raised before anything is drawn. Manim writes its
LaTeX cache under `media/` of the working directory; a sandbox should run
the render in a scratch directory.

### 9.5 Report `animageo-render-report/v1`

```text
{"format": "animageo-render-report/v1",
 "documentId": "…",
 "kernel": {"library": "1.8.1a2", "registry": "1.3"},
 "fmt": "svg",
 "canvas": {"width": W, "height": H, "unit": u, "origin": [ox, oy]},
 "elements": {"<elementId>": {"state": "defined" | "undefined" | "unsupported" | "error",
                              "visible": true | false,
                              "box": [x0, y0, x1, y1] | null,
                              "label": {"box": [x0, y0, x1, y1], "anchor": [x, y] | null,
                                        "text": "$A$"} | null}},
 "overlaps": [["<elementId>", "<elementId>"], …],
 "pointOverlaps": [["<labelId>", "<pointId>"], …],
 "diagnostics": [{"code": …, "elementId": …, …}]}
```

- Keys of `elements` are the document's element IDs, every element listed,
  sorted. `state` is the kernel state (§5).
- Coordinates are pixels of the output (for PDF px at 96 dpi), the y axis
  points down, rounded to 3 decimals. `canvas` is the final export layout:
  `W` and `H` are integers, `u` is pixels per world unit and `origin` is the
  pixel of the world origin, so

      px = ox + u·x,   py = oy − u·y

- `visible` is `true` when the element is drawn (defined and not hidden by
  `appearance`); otherwise `box` and `label` are `null`. A number is never
  drawn; a vector is drawn as an arrow.
- `box` bounds the drawn element without its label (an arrow with its
  shaft and its tip); `label.box` bounds the
  label (without its leader line); `label.anchor` is the point the label is
  attached to (the classic label attach spot, in px); `label.text` is the
  label source text (LaTeX for names).
- An equality mark has no drawing of its own: its `box` is the union of
  the boxes of its drawn targets (`null` when none is drawn, or the mark
  is hidden or undefined) and its `label` is `null`. A right-angle mark is
  drawn as an angle with the marker and reports its own box.
- `overlaps` lists the label pairs whose box intersection is at least
  `0.15` of the smaller box's area, each pair sorted, the list sorted, all
  pairs (no cap).
- `pointOverlaps` (1.8.1a2) lists the label boxes that enter the marker of
  a drawn point, its own point included: `[labelId, pointId]`, the list
  sorted. The marker is the circle inscribed in the point's `box` (centre
  `c`, radius `r`); a box enters it when the squared distance from `c` to
  the box is less than `r²`. A key added to the format: readers of
  `overlaps` are not affected.
- `diagnostics` are those of §9.3.

### 9.6 Command line

```text
python -m animageo doc.json [-o out.svg] [-f svg|png|pdf] [-s style] [--style-from-document]
                            [--export-size W H] [--fit …] [--source-rect …] [--anchor …] …
```

A file whose text is JSON with `"format": "animageo-construction/v1"` is a
document (a `.ggb` is a zip and keeps the classic path). The document is
rendered in process with `native.render` and the placement flags of the
`.ggb` path; the output defaults to the document name with the format's
extension. `--style-from-document` uses `styleBinding.configSnapshot` as is
(without the web's migrations and `import.sources`, a warning says so) and
cannot be combined with `--style`. `--keyframes` and video formats are
refused, `--dpi` is ignored. Exit codes: `0` written, `2` a missing file, a
document that does not load, an unusable flag or a render error.

### 9.7 Label layout without manim (`native.layout_labels`)

```text
layout_labels(doc, ev=None, *, inputs=None, style_config=None, export_layout=None,
              backend="metrics", place=None) -> {elementId: Entry}
Entry = {"text": "$A$", "anchor": "BL", "point": [x, y],
         "offsetPx": [dx, dy], "offsetWorld": [wx, wy],
         "box": [x0, y0, x1, y1], "leader": [[x, y], [x, y]] | null,
         "overlaps": [elementId, …], "pointOverlaps": [elementId, …],
         "placed": bool, "locked": bool}
```

The labels of a document where `native.render` would draw them, for a
readability check or a placement suggestion, without manim and LaTeX. The
pipeline is that of the render up to the drawing: the bridge (§9.2), the
appearance (§9.3, point labels clear of their markers included), the style
and the export layout give the output canvas, and the classic placement
solver (`label_placement.compute_label_layout`) runs on a
`label_placement.LayoutInput` instead of a scene.

- `style_config`, `export_layout` and `inputs` are those of `native.render`
  (§9.4) with the same errors (`ValueError`); `ev` is an `Evaluated` of the
  same inputs, computed when `null`.
- `backend`: `metrics` measures a label by setting its TeX with the metrics
  of the template's fonts (below); `tex` measures it with manim's `Tex`, as
  the renderer does (`RuntimeError` without manim); another value is a
  `ValueError`.
- `place`: `null` follows the style (`overlay.label_placement.enabled`,
  off in the built-in style: labels stay at their anchor and offset);
  `true` places every label that is not pinned; `false` places none.
- One entry per drawn element with a shown label (a hidden, undefined or
  undrawn element has none), keys sorted. Pixels of the output as in the
  render report (§9.5: y down, 3 decimals). `point` is the spot the label
  hangs from (the point; for an angle the spot on its bisector); `anchor`
  is the label anchor name (`TL` … `BR`, `MC`) in effect; `offsetPx` is the
  offset of the anchor corner from `point` in output px (y down),
  `offsetWorld` the same in world units (y up, 9 decimals); `box` is the
  label box; `leader` the connector of a label the solver displaced
  (`overlay.label_placement.label_overflow = "leader"`, off by default;
  `null` otherwise); `placed` says the solver placed it; `locked` that it
  is pinned.
- `overlaps`: the other labels whose box covers at least `0.15` of the
  smaller box; `pointOverlaps`: the drawn points whose marker the box
  enters (§9.5), its own point included. Both sorted; they are the
  report's `overlaps` and `pointOverlaps` read per label.
- Nothing is written into the document. To keep a suggestion, the caller
  pins it: `appearance.<id>.label.offsetWorld = offsetWorld` and
  `appearance.<id>.overrides.label_anchor = anchor`; `native.render` then
  draws the label at `box` (tested within `0.01` px) and `layout_labels`
  reports it `locked`.
- `export_layout.content.source = "rendered_bounds"`: the renderer crops to
  the measured bounds of its drawing; here the crop is computed from the
  geometry (point markers, segment and arrow ends, lines and rays clipped
  to the frame unless `infinite_policy` is `ignore`, circles, polygons,
  angle arcs) and the label boxes (unless `label_bounds = "exclude"`), in
  the same two passes as the renderer when placement is on. The library
  set of scenes gives the boxes of the render within `0.01` px; a drawing
  whose stroke widths decide the crop may differ by a stroke width.

**Label metrics.** `animageo/native/labels/metrics.v1.json`
(`animageo-label-metrics/v1`) holds, for every font the label template
(`ui.RusTex`) uses — math italic, roman, symbols and AMS symbols in text,
script and scriptscript sizes, the T2A text font — the TFM metrics of each
character (width, height, depth, italic correction, ligatures and kerns,
font parameters) and the ink box of its outline, a few composite symbols
(`\angle`, `\triangle`, `\neq`, …) measured whole, and the scale from TeX
points to manim units. `labels/tex.py` sets a label with them by the rules
of TeX (Appendix G of the TeXbook for scripts) and returns the ink box,
which is what manim measures. It covers text mode with Latin, digits,
Cyrillic and punctuation, and math mode with letters, digits, operators
and relations with TeX's spacing, Greek, the symbols of the template's
fonts, groups, sub- and superscripts, primes, `\text`, `\mbox`,
`\mathrm` and math spaces. Anything else (`\frac`, `\sqrt`, accents,
unknown commands) is estimated as the renderer estimates a label when
LaTeX fails. On a seeded corpus of 2000 labels
(`tests/native/label_corpus.py`) the boxes equal manim's within 1 %.
`scripts/native/build_label_metrics.py` rebuilds the file from the TeX
installation (manim, `latex`, `dvisvgm`, `kpsewhich`); `--check` compares.

### 9.8 Paint without manim (`native.resolve_paint`, 1.11.0rc3)

`resolve_paint(doc, style_config=None, t=None, *, timeline=None,
inputs=None, export_layout=None)` (`has("resolve_paint")`) is the paint
`native.render` draws each element with, read through the same appearance
plan and style resolver as the renderer, without manim (the classic graph
of §9.2, as `layout_labels`). `t` with `timeline`: the inputs and the
visibility of `sample_timeline` and the style tracks of the timeline at `t`
(its `@camera` does not change the paint); 1.11.0: the presence of the frame
of the video — an element in an enter or exit effect is drawn as
`timeline_effects` says (`present`: an entrance begun, an exit not done,
before the keyframe that changes its visibility), and its entry gains
`effect` `{phase, effect, progress}` once the effect has begun (the paint
is that of the element in full; `docs/native/timeline.md` §3). It returns

    {"format": "animageo-paint/v1", "background": "#ffffff",
     "ptUnit": 100.0, "ptUnitStyle": 100.0, "t": null,
     "elements": {id: entry}, "order": [id, …], "diagnostics": […]}

`ptUnit` — output pixels per world unit, `ptUnitStyle` — style pixels per
world unit (a decoration of `n` px is `n / ptUnitStyle` world units),
`order` — the drawn elements by their layer, bottom up, `diagnostics` —
those of `appearance_plan` (§9.3). Every element has an entry: `type`,
`styleType` (the type of `style_keys()`), `style` (the classic style type),
`drawn`; a drawn element also has `z` (its layer, the construction order
breaking ties by `1e-6`) and, by type:

- `stroke`: `color`, `opacity`, `widthPx`, `cap` (`stroke_linecap`, by
  default `rendering.line_cap`, for a segment, a line, a ray, a vector, an
  arc and a sector without its sides; `null` — butt — for every other stroke:
  a polyline, a locus, a curve, the arcs of an angle, a right-angle mark; the
  ticks of a segment are butt whatever its cap; since 1.11.0rc12 every
  dashed stroke is butt too, even under an explicit round or square cap.
  The SVG, PDF, EPS,
  PNG, TikZ and the frames of the video draw these caps, and a stroke without
  a cap or join of its own no longer takes those of the stroke drawn before
  it in the video), `z`, and `dash` — `null` or `{onPx, offPx, fit, drawn}`: the
  nominal pattern, how the renderer fits it to the path (`ends` — a dash at
  both ends of a segment, a vector or an arc; `closed` — whole periods on a
  circle or a closed polyline; `none` — from the start of a line, a ray or an
  open polyline) and the pattern drawn `{onPx, offPx, offsetPx}`
  (`null` for a vector: the renderer measures the
  stem of its arrow). The fit is computed on the exact length; the renderer
  measures its Bézier path, within `1e-3` of it for a circle or an arc;
- `fill`: `color` (`null` — nothing is drawn), `opacity` as drawn,
  `isBackground`, `z`, and for a polygon, circle or sector `pattern` and
  `hatch` (`{pattern, angleDeg, spacingPx, widthPx, color, opacity}` or
  `null`). An angle or a right-angle mark filled with the background colour
  has no fill (1.11.0rc3); a polygon, a circle, an arc or a sector filled
  with it is drawn (opaque) — `isBackground` tells it. An angle or a
  right-angle mark has `pattern` and `hatch` only with a `fill_pattern`
  other than `solid` (1.13.0): the sector to the outer arc or the square,
  drawn also when the fill itself is the background colour;
- `point`: `sizePx`, `shape`, `display` (`rendering.points_display`); a
  hollow point (`point_fill: hollow`, 1.13.0; a cross or a plus ignores it)
  is drawn at `sizePx = max(size, 2H / (k·S))` (`H` 3 output px, the disc
  its hole holds; `k` 1 for a circle, `1/√2` for a square or a diamond, `1/2`
  for a triangle; `S = ptUnit / ptUnitStyle`), with `givenSizePx` (the
  `size_px` of the style) when that is larger, and has
  also `fill: "hollow"`, `hole` `{shape, radiusPx}` (the shape of the point
  at half its size, `radiusPx = sizePx / 4`), `ringPx` (half the inscribed
  radius: `sizePx/4` for a circle, `sizePx/(4√2)` for a square or a diamond,
  `sizePx/8` for a triangle) and `innerColor` — the background: the hole is
  painted with it on a solid sheet and cut out of every layer under the
  point on a transparent one (`exportSVG(…, transparent=True)`);
- `arrow` (a vector): `lengthPx`, `widthPx`; a segment with `arrow_head`
  (1.13.0): `head` (`end`, `start`, `both`), `lengthPx`, `widthPx` (those
  of a vector of the style by default), `stem` `[x1, y1, x2, y2]` (the line
  between the bases, its dash fitted to it) and `tips` `[[Tx, Ty, B1x, B1y,
  B2x, B2y], …]` (world units; a head is at most the segment long, half of
  it for two);
- `parallel` (a segment, a line, a ray, a vector with `parallel_count`,
  1.13.0): `count`, `sizePx`, `depthPx` (`sizePx/2`), `shiftPx`,
  `direction`, `chevrons` `[[x0, y0, Tx, Ty, x1, y1], …]` (world units;
  `[]` for a line of no length): around the middle of a segment or a vector
  (moved past its ticks by `tick_shift_px·(n − 1)/2 + tick_width_px/2 +
  s/2 + (p·(k − 1) + s/2)/2`) or of the drawn part of a line or a ray,
  tips `T_j = c + v·(s/4 + p·((1 − k)/2 + j))`, arms to `T_j − v·s/2 ±
  n·s/2`; solid, butt, mitred, in the stroke of the element;
- `ticks` (a segment, a vector): `count`, `style`, `lengthPx`, `widthPx`,
  `shiftPx`, `radiusPx`, and the lines `[[x1, y1, x2, y2], …]` or the
  corners of the wave `wave` with its `cornerRadius` (world units);
- `angle` (an angle, a right-angle mark): `range`, `autoRadius`,
  `arcSizePx` (the base), `radiusPx` (after `overlay.angle_radius`),
  `arcs`, `arcShiftPx`, `arcRadiiPx` or, for a right angle, `rightSizePx`
  and the corners of the square `square` (world units), `shownSize`,
  `right`, `joint`. With `rendering.angle_marker_fit` (off by default;
  on: `limitPx = side_fraction · min(L1, L2) · ptUnitStyle`, `side_fraction`
  0.6, see `docs/styles.md` §8) also `fit`: `supportWorld` (`[L1, L2]` — a
  visible segment or polygon side on the vertex along a side counts with
  how far it reaches, also past the defining point; `null` — a
  side without a bound), `limitPx` (`null` — no bound), `clamped`,
  `hidden`; `radiusPx`, `arcRadiiPx`, `rightSizePx` and `square` are then
  the fitted marker (`arcSizePx` stays the desired base), a hidden marker
  has `arcRadiiPx: []` and no `square` (no fill either), and the label
  stands at the fitted extent. The kinds of marks (1.13.0, only with a
  decoration — `arc_style` other than `solid`, `arc_tick_count`,
  `arrow_head`; such an angle of 90° is drawn as arcs unless
  `right_angle_marker` is `true`): `arcStyle` (`dashed`, `wave`),
  `arcStepPx` (two waves and more: `max(arcShiftPx, 2A + gapPx)`),
  `arcGrowPx` (how far the inner arc grows past `radiusPx` of the style to
  the floors of legibility: `r_in ≥ 3·minPeriodPx / Δ` for two waves and
  more; for a dashed marker with ticks, a head or several arcs every arc
  `L ≥ T = 7.5` px — `r_in ≥ T / Δ`, the outer arc past its `h` heads of
  length `ℓ` `r_out ≥ min((T + h·ℓ) / Δ, 2T / Δ)`; `radiusPx` and
  `arcRadiiPx` are the grown ones, the fit moves them in after; the growth
  stops at `2 ×` the original inner radius — then `arcGrowMaxPx` is the
  ceiling, `wave.cappedMinPeriodPx: 3`, the wave has `N = max(2, min(N, ⌊r_in·Δ / 3⌋))`
  periods and a dashed arc `periodPx = L / 1.5`, two dashes, below 3 px), `wave`
  `{amplitudePx: 1, periodPx: 6, samplesPerPeriod: 16, gapPx: 2,
  minPeriodPx: 4, periods, arcs}`,
  `arcDashes` `[{radiusPx, startAngle, span, onPx, offPx, offsetPx,
  dashes, periodPx}, …]` (`on = off = periodPx/2` fitted to each arc with
  a dash at both ends: `periodPx` 4, or, for a dashed marker with ticks, a
  head or several arcs whose arc gets fewer than three dashes at 4 px,
  `max(3, min(4, L/2.5))`; the explicit `stroke_dash_pattern_px` as it is,
  `dashes` and `periodPx` `null` then),
  `arcTicks` `{count, lengthPx, shiftPx, widthPx, lines}` (radial lines from
  `max(0, r_in − L/2)` to `r_out + L/2` at `φ0 + Δ/2 + δ·((1 − k)/2 + j)`,
  `δ = min(h/r_out, Δ/(k + 1))`, as wide as the arcs), `arrow` `{head,
  lengthPx, widthPx, drawnLengthPx, drawnWidthPx, tips, stemEndAngles}` (a
  head on the outer arc, `end` at the second side; `ℓ' = min(ℓ,
  r_out·Δ_e/2)`, `w' = w·ℓ'/ℓ`; the outer arc stops at its base,
  `stemEndAngles`) and `overhangPx` — how far the decoration reaches past
  the outer arc (the wave `A`, half a tick, half a head; the fit bounds
  `r_out + overhangPx`, the label clears the wave and the ticks). Every arc
  of `wave.arcs` is `{radiusPx, startAngle, span, periods, points}`: the
  sample rule is `N = max(1, round(r_out·span/λ))` periods, `16·N + 1`
  points `φ_k = startAngle + span·k/(16·N)`, `ρ_k = r + A·sin(2π·(k mod
  16)/16)` (world units) — both ends on the arc, the arcs of one span radial
  shifts of each other; the outer arc shortened by a head counts its own
  `N`; two waves and more take `N = max(3, …)`. An angle of no size draws nothing: `arcRadiiPx: []`;
- `decoration` (1.11.0rc13, a drawn equality target): `owner` (mark document
  ID), `color`, `count`, `kind` (`ticks`, `arcs`, or `square`),
  and actual dimensions in style pixels. Ticks report `style`, `lengthPx`,
  `widthPx`, `shiftPx`, `radiusPx`; arcs report `arcSizePx`, `radiusPx`,
  `arcShiftPx`, `widthPx` and, decorated (1.13.0), `arcStyle` and
  `arcTicks` (their count). The same entry is in `render().report.elements`.
  It is absent when no visible, defined mark contributes. Existing paint
  fields and diagnostic warnings keep their rc12 values without new
  overrides; `decoration` is additive. Use its colour to compare a mark,
  rather than the target's body `stroke.color`;
- `label`: `shown`, `color`, `fontSizePx`, `halo` (1.11.0: `{widthPx,
  color, opacity}`, `widthPx` `0` — none), `anchor` (`label_anchor` →
  `rendering.label_anchor` of the given style → `BL`), `radialOffsetPx`
  (angles), and for a shown label `z`, `text`, `parts` (1.11.0: the runs of
  `text` `[{text, italic, script}]` — `script` `sub`, `sup` or `null`;
  Latin letters and lowercase Greek italic, digits, signs and values
  upright; `null` for a caption or TeX the runs do not cover), `spotWorld`,
  `offsetWorld` (the placement solver is not run: `layout_labels` does); a
  text has only `color`, `fontSizePx` and `halo`;
- `value` (types with a value): `precision`, `stripZeros`, `separator`,
  `angleUnit`.

Fixtures `animageo-paint-parity/v1` (`animageo/native/parity/v1/paint`,
`python -m animageo.native fixtures paint [-o DIR] [--check]`): one file per
theme, `{format, id, registry, generatedBy, cases: [{name, document, style,
t, timeline, expect}]}`, `expect` — `resolve_paint` of the case; numbers
compare with `1e-9`. The scenes: ticks 1/2/3, the wave and the sizes of a
mark, arcs and the automatic radius, right angles, a reflex angle, an angle
in a filled triangle (`wedge`), point shapes, `points_display`, arrows,
caps, dashes and their fit, label anchors by type and their overrides, the
format of values, layers, `text.free`, the zoo of types without a style,
under the built-in style and a preset, roles, hatching, a dark background,
a style track of a timeline, a right-angle mark drawn as arcs (1.11.0), the
enter and exit effects of a timeline with a style track and a discrete one
(1.11.0), the kinds of marks (`paint_marks`, 1.13.0: waves, dashes, ticks
and heads on arcs, arcs instead of a square, hatched angles, equality marks
passing them, the overhang in the fit, hollow points, heads of segments,
chevrons, degenerate cases). A test renders each scene — a scene with a timeline as the frame
`render(t)` draws — and compares with the entry of every element its render
context and what it draws: the layers of the fill and the label, the size
and shape of a point, the hatch (spacing, angle, width, colour), the lines
or the corners of the wave of the ticks, the radii of the arcs and the
corners of the right-angle square, the font size, the dash patterns, the
samples of waves, the dashes, ticks and heads of arcs, the hole of a hollow
point, the heads of a segment, the chevrons, and that an element not drawn
is not in the frame.

The style contract for code generation (`animageo/native/style`, `python -m
animageo.native style export [-o DIR] [--check]`): `builtin.json` — the
built-in style byte for byte, `keys.v1.json` — `style_keys()` (§9.3).

## 10. Floating point and determinism

Both kernels compute the same formulas in the same order in IEEE-754
doubles. `hypot` may differ by one unit in the last place between
implementations; values agree within `tol.parity`, and the generator's
margin rule keeps such differences away from every degeneracy decision.

The kernel has no state and no randomness: the evaluation of a document does
not depend on the order of its keys, the order of evaluations or on
repeating them, and no module of the package imports `random` or
`numpy.random` (`tests/native/test_native_determinism.py`).

## 11. Stage L3, part 1 (registry 1.5, animageo 1.9.0a1)

### 11.1 Registry 1.5

Nine operations, `since: "1.5"`, `stable` (formulas, decisions and checks in
`docs/native/ops/<op>.md`):

| op | inputs → outputs | undefined | checks |
|---|---|---|---|
| `triangle.altitude` | `vertex: point, side: linear` (`ends`) → `altitude, extension: segment, foot: point` | `zero_length`, `branch_absent`, `upstream` | `perpendicular`, `on_carrier` |
| `triangle.median` | `vertex: point, side: segment` → `median: segment, midpoint: point` | `zero_length`, `upstream` | `midpoint` |
| `triangle.bisector` | `vertex: point, side: segment` → `bisector: segment, foot: point` | `coincident_points`, `collinear_points`, `upstream` | `equal_angles`, `on_side` |
| `triangle.centroid` | `a, b, c: point` → `point` | `upstream` | `medians` |
| `triangle.incenter` | `a, b, c` → `point` | `collinear_points`, `upstream` | `equidistant_sides` |
| `triangle.circumcenter` | `a, b, c` → `point` | `collinear_points`, `upstream` | `equidistant` |
| `triangle.orthocenter` | `a, b, c` → `point` | `collinear_points`, `upstream` | `perpendicular` |
| `triangle.excenters` | `a, b, c` → `center: point` (opposite `a`) | `collinear_points`, `upstream` | `equidistant_lines` |
| `locus.of_point` | `trace: point, mover: locus_driver` → `locus: locus` | `unsupported_signature`, `not_dependent`, `empty_range`, `upstream` | `on_trace` |

- Type `locus`: `{points: [[x, y] | null, …], range: [t0, t1], closed: bool}`
  (`points` — length, `range` — scalar); family `locus_driver = [point,
  number]`; `locus` is in no other family (a point on a locus and
  intersections with it are L4). Reasons `not_dependent`, `empty_range`
  (state `undefined`).
- `ends` (a field of a record input, outside the signature hash): the side of
  `triangle.altitude` receives the two defining points of a line or a ray
  whose producer frame is `o = args.Y`, `v = args.X − args.Y`
  (`line.by_points`: `a`, `b`; `ray.by_points`: `origin`, `through`;
  `evaluate.side_end_slots`); any other line or ray has no ends and no
  `extension`. A pair `BC` in the side slot of «Команды» is a hidden
  `line.by_points` (a `segment.by_points` for `median` and `bisector`).
- The centres are bit for bit the centres of `circle.incircle`,
  `circle.three_points` (vertex `a` first) and `circle.excircle`; the foot of
  an altitude is the arithmetic of `point.projection`.

### 11.2 Evaluation

- An implementation that returns `unsupported_signature` gives the state of
  that reason in `_reasons.json` (`unsupported`), as the structural rules do.
- Checks of `triangle.altitude` run when `altitude` and `foot` are defined:
  its `extension` may be `undefined` (`branch_absent` in every acute
  triangle) without skipping them (`CHECK_OPTIONAL_SLOTS`).
- `locus.of_point` is a graph operation: it receives the evaluation scope
  (document, states so far, inputs, order). Mover: the point of
  `point.on_path` or the number of `number.free` with both `min` and `max`;
  else `unsupported_signature`. The trace's producer must depend on the
  mover's (else `not_dependent`). Range from the definition: segment, arc
  `[0, 1]`; polyline `[0, n − 1]`; circle `[0, 2π)`, polygon `[0, n)`, sector
  `[0, 3)` — closed; line and ray — Liang–Barsky clip of the producer frame
  to the window `B4` (`viewDefaults.bounds` scaled 4 times about its centre),
  a ray from `0`; number `[min, max]`. A window of no length
  (`(t1 − t0)·|v| ≤ tol.decide_length`, a number `t1 − t0 ≤ tol.decide_scalar`)
  or a line that misses the window is `empty_range`. `N = 256` samples: open
  `t_k = t0 + (k·(t1 − t0))/(N − 1)`, closed `t_k = t0 + (k·(t1 − t0))/N`.
  Each sample replaces the mover input by `t_k` and evaluates only the
  operations between the mover and the trace (downstream of the mover ∩
  upstream of the trace, in the evaluation order; a free op inside keeps its
  input or default); `points[k]` is the trace or `null`. The decisions of
  the sampled operations are reported like the decisions of the document
  (the generator refuses a near-degenerate sample). The check `on_trace`
  compares the samples `0, N/4, N/2, 3N/4` with full evaluations.

### 11.3 Document: `seq`, `steps`, `role`

- `operations.<id>.seq` (integer ≥ 1, optional): the order key of the steps
  and the printer — operations without `seq` first by ID, then by `seq`,
  ties by ID; a repeated `seq` is the warning `seq_duplicate`.
  `native.assign_seq(doc, op_ids)` returns a copy numbered after the largest
  `seq`.
- `steps: [{id, kind: given | group | condition, title?, text?,
  operationIds}]` — explicit groups. `validate` errors:
  `step_unknown_operation`, `step_duplicate_operation`, `step_duplicate_id`,
  `step_empty`, `step_cycle`.
- `appearance.<id>.role` (a string): `given | aux | sought`; another value is
  the warning `role_unknown` and is ignored.

The JSON schema `schema/construction.v1.schema.json` and the structure check
agree on these fields. `native.steps`, `steps_merge`, `steps_split` and
`native.describe` are in `docs/native/steps.md`; `native.has(feature)` and
`native.FEATURES` list the features of the stage (`triangle`, `locus`,
`steps`, `describe`, `render.eps`, `render.tikz`, `roles`).

### 11.4 Rendering

- `native.render(fmt=…)`: `eps` (`exportEPS`), `tikz` (`exportTikZ`,
  `standalone=False`), `tex` (`standalone=True`), besides `svg`, `png`,
  `pdf`.
- The TikZ/TeX frame (1.10.0a2, `has("render.tikz_frame")`): the clip, the
  background and the `\useasboundingbox` of the `tikzpicture` are the export
  canvas of the same `export_layout` — `canvas.width × canvas.height` pixels
  of the report from the pixel `(0, 0)`, the frame of SVG, PNG, PDF and EPS
  (one pixel is `ptUnit·2.54/96` cm of the picture unit, so a compiled TeX
  page is the PDF page). Lines and sampled curves are still drawn across the
  camera frame and cut by the clip. Before, the clip was the manim camera
  frame (16:9): the height was right, the width was not. The classic
  `exportTikZ` keeps the camera frame unless asked
  (`TikZOptions(frame="export")`).
- Roles: `appearance.<id>.role` puts the keys of the style's `roles.<role>`
  (a point takes `roles.<role>.point`) under `appearance.overrides`; token
  references are resolved by the style resolver. The defaults
  (`animageo.style.schema.ROLE_DEFAULTS`, mirrored by `roles` in
  `builtin.json`): `given` — stroke `color.main`, point fill `color.strong`;
  `aux` — stroke `color.aux`, width `line_width.aux`, dash ratio `0.5`, point
  size `point_size.aux`; `sought` — stroke `color.accent`, width
  `line_width.bold`, point fill `color.accent` and size `point_size.bold`.
- A `locus` is a classic `LocusCurve` of its defined samples with `breaks`
  (a new optional field: one polyline per run in the renderer, TikZ and
  JSXGraph) where a neighbour is `null` or two neighbours are more than
  `0.25·S` apart; a closed locus joins its last sample to the first when they
  are near. Its bridge command evaluates the document with the current free
  inputs of the construction.
- Report: `elements.<id>.role` for an element with a role; a `locus`
  reports the box of its defined samples.

### 11.5 Fixtures `animageo-steps/v1`

`python -m animageo.native fixtures generate <scenes…> -o <dir> --steps
<dir>` also writes, per scene, `{format: "animageo-steps/v1", id, registry,
generatedBy, document, expect: {steps: [{id, kind, title?, text?,
operationIds, elementIds, auxElementIds}], describe: [line…], timeline:
null}}` (`parity/v1/steps`, all scenes); `fixtures verify` compares them
exactly. 1.9.0a4: `timeline` is `steps_timeline(doc).to_dict()`
(`docs/native/timeline.md` §4).

## 12. Stage L3, part 2 (animageo 1.9.0a2)

Conditions, the general case and automatic marks: the contract is
`docs/native/conditions.md`; recipe cards for the assistant —
`docs/native/ops/recipes.md`. In short:

- Document: `conditions[]`, `suppressedMarks[]`, `elements.<id>.origin`
  (`kind: "auto"` checked), `viewDefaults.autoMarks`; `validate` codes
  `condition_*`, `mark_origin_unknown`, `suppressed_mark_unknown_kind`; the
  JSON schema follows.
- Statements (AST shared with the web) compile to `check` predicates
  (`statement_checks`); new predicates `on_object`, `coincident`,
  `congruent`; `measure_statement`, `relation`.
- `check_general` — the general case: SplitMix64 trials with the seed
  `sha256(documentId:checkId)`, a counterexample (trial and inputs),
  `inconclusive` over 20 % unmeasured trials. L2 `general_position` (the
  trials of `native.check`) is unchanged.
- Recipes v1 (13 files) → `apply_condition`, `release_condition`,
  `condition_candidates`, `shape_conditions`; `delete` and `redefine`
  respect conditions (§8 codes `condition_cycle`, effects
  `removed.conditions`, `modified.restoredFrom`).
- `auto_marks`, `add_auto_marks`, `auto_sources` (`marks/auto.v1.json`);
  `apply_condition` adds the marks of its condition.
- `steps`: `condition` steps; marks in the step of their source; `describe`
  phrases conditions and gives `values=True`.
- `redefine` takes the default of an optional free input
  (`FREE_INPUT_DEFAULTS`) instead of `missing_input`.
- Fixtures `animageo-recipes/v1`, `animageo-general/v1`,
  `animageo-marks/v1` (`fixtures conditions`), 17 scenes `recipe_*`,
  `shape_*`; `native.has`: `check.general`, `conditions`, `apply_condition`,
  `auto_marks`, `describe.values`.

## 13. Stage L3, part 4 (animageo 1.9.0a4)

Time by element ID: the contract is `docs/native/timeline.md`. In short:

- `animageo/easing.py` — the easing functions of `keyframes.py` (a leaf
  module, bitwise the same values); `animageo.native` may import it at
  module level.
- A timeline is the keyframe JSON v2 with element IDs as keys;
  `sample_timeline(doc, timeline, t) → {t, inputs, visible}` (values carry
  forward, path parameters with `short | long | cw | ccw` on wrapping
  paths, visibility carried forward); `evaluate(doc, t=…, timeline=…)` adds
  `ev.t` and `ev.visible`.
- `timeline_to_bridge` — IDs → `e_<hex>`, unwrapped `tparam`;
  `render(t=…, timeline=…)` for static formats, `mp4`, `gif`, `webm`,
  `mov` with `video={fps, quality, duration}` (`ValueError("timeline_required")`;
  `duration` — the still of a timeline of one keyframe, 1.11.0rc7).
- `steps_timeline(doc, *, lag, duration, pause, effects, start) →
  StepsTimeline(keyframes, steps, duration)`.
- Fixtures `animageo-timeline/v1` (`fixtures timeline`); the steps fixtures
  carry `expect.timeline`; CLI `steps`, `describe`, `timeline`;
  `native.has`: `timeline`, `steps_timeline`, `render.t`, `render.video`.

## 14. Registry 1.6: functions and conics (wave G2)

Operations `since: "1.6"`, `beta` (formulas, decisions and checks in
`docs/native/ops/<op>.md`). The view keys `axes` and `grid` of
`viewDefaults` are [view.md](view.md). Features (1.11.0rc6):
`has("functions")`, `has("conics")`, `has("view_axes_grid")`.

| op | inputs → outputs | undefined | checks |
|---|---|---|---|
| `function.expr` | `expr: expr` (`vars: ["x"]`), `refs: number[]`; params `min`, `max` (optional) → `function` | `empty_range`, `upstream` | — |
| `function.root` | `function, a: number, b: number`; param `count` (default 1) → `root.1 … root.count: point` | `empty_range`, `coincident`, `no_root_in_window`, `branch_absent`, `upstream` | `on_graph` |
| `function.extremum` | `function, a, b`; `count` → `extremum.k: point` (`detail.kind`: `max`, `min`) | `empty_range`, `no_root_in_window`, `branch_absent`, `upstream` | `on_graph` |
| `intersect.function_function` | `first, second: function`; `count` → `point.k` | `no_intersection`, `coincident`, `branch_absent`, `upstream` | `on_both` |
| `intersect.function_line` | `function, line: linear`; `count` → `point.k` | `no_intersection`, `coincident`, `outside_part`, `zero_length`, `branch_absent`, `upstream` | `on_both` |
| `point.on_function` | `function`; free `pathParameter` (x) → `point` | `out_of_domain`, `upstream` | `on_graph` |
| `conic.ellipse_foci_point` | `f1, f2, through: point` → `conic` | `degenerate_conic`, `upstream` | `on_curve`, `foci` |
| `conic.hyperbola_foci_point` | `f1, f2, through: point` → `conic` | `coincident_points`, `degenerate_conic`, `upstream` | `on_curve`, `foci` |
| `conic.parabola_focus_directrix` | `focus: point, directrix: linear` → `conic` | `zero_length`, `degenerate_conic`, `upstream` | `focus_directrix` |
| `conic.five_points` | `a … e: point` → `conic` | `coincident_points`, `degenerate_conic`, `upstream` | `on_curve` |
| `conic.equation` | `expr: expr` (`vars: ["x", "y"]`), `refs: number[]` → `conic` | `not_quadratic`, `degenerate_conic`, `upstream` | — |
| `conic.center` | `conic` → `center: point` | `not_central`, `upstream` | — |
| `conic.foci` | `conic` → `first, second: point` | `branch_absent`, `upstream` | `focal` |
| `conic.vertices` | `conic` → `first … fourth: point` | `branch_absent`, `upstream` | `on_curve` |
| `conic.axes` | `conic` → `focal, conjugate: line` | `branch_absent`, `upstream` | — |
| `intersect.line_conic` | `line: linear, conic` → `first, second: point` | `no_intersection`, `outside_part`, `zero_length`, `branch_absent`, `upstream` | `on_both` |

- Type `function`: `{expr, refs, domain: [lo | null, hi | null]}` (`refs`,
  `domain` — length; `expr` compares exactly); in no family.
- Type `conic`: ellipse `{kind, c, axis, a, b}` (`a ≥ b`, a circle has
  `a == b`, `axis = [1, 0]`), hyperbola `{kind, c, axis, a, b}`, parabola
  `{kind, vertex, axis, p}` (`axis` towards the focus, `p` focus–directrix);
  `kind` compares exactly; in no family. A degenerate conic is not a value
  (`degenerate_conic`). The classification of coefficients (equation, five
  points) is [conic.equation](ops/conic.equation.md#classification); policy
  `conic_axis_order` for the parts. New noise decisions: `degenerate`,
  `parabola`, `circle`, `axis_orientation`, `not_quadratic`.
- An input of a record may list `vars` (`function.expr`: `["x"]`): its `expr`
  argument takes the nodes of [expr.md §5](expr.md); `vars` enters the
  signature only when present (the hashes of older records stay).
- Searches run on the grid of 512 cells with bisection and golden section
  ([function.root](ops/function.root.md)); policy `roots_ascending`: by `x`,
  a double root in two slots (`detail.multiplicity: 2`). The intersections
  search the x-range of the window `B4` of `viewDefaults.bounds`
  (`OpContext.bounds`). A missing repeated slot does not skip the checks of
  its operation (`CHECK_OPTIONAL_SLOTS` by the base name of the slot); an
  operation with no defined output (a search that found nothing) has no
  checks, as in 2D.
- Bridge: a classic `Function` without sympy (`bridge.native_function`),
  drawn by `kernel/function.py::function_runs` (manim and TikZ); the `x` of
  `point.on_function` is the `tparam` of its classic element. A conic is a
  classic `Conic` of `kernel/conic.py::matrix` with the type of its `kind`
  (`bridge.native_conic`); its label hangs off `conic.label_anchor`
  (ellipse `c + b·n`, hyperbola `c + a·axis`, parabola the vertex).
- «Команды»: no commands for functions and conics yet
  (`commands.lexicon.deferred_op`); the printer prints their lines with the
  warning `unprintable_operation` («функции и коники в «Командах» будут позже»).
- The DSL map lists them in `opsWithoutClassic`.
- `style_keys()` and `resolve_paint` (types `function`, `conic`): a graph
  reads the stroke, the dash and `z_index`, draws no label (a dash fits
  `none`, open runs); a conic reads the stroke, the dash, the fill,
  `z_index`, `z_index_fill` and the label keys — an ellipse (a circle) has
  its fill below the stroke at `z_index_fill` as a circle and a closed dash
  measured by the renderer (`drawn: null`), a hyperbola or a parabola has
  no fill and open runs (`fit: none`); the label spot is
  `conic.label_anchor`. Fixtures `paint_curves.json`.
- Parity fixtures `parity/v1/curves/*.json` (`fixtures curves [-o DIR]
  [--check]`, `animageo/native/curves_fixtures.py`): 14 scenes of graphs
  (`fn_*`) and 17 of conics (`conic_*`), every op of 1.6 in three defined
  cases or more and each of its reasons. The shape is that of
  `parity/v1/expected` (`fixtures verify` reads them); a case of a document
  with graphs also has `samples` — `{elementId: [[x, y | null], …]}`,
  `function_samples` of each defined graph at 33 equal steps over the
  x-range of the bounds cut by the domain (`[]` when the cut is empty).
  Inputs are rounded to 6 decimals, expectations and samples to 9 (a fresh
  build is byte-identical away from libm noise); numbers compare with
  `tol.parity`. `--check` compares a fresh build (the `generatedBy` label
  aside) and replays every case. The coverage tests of the parity set and
  the registry mix of L6 read them with `parity/v1/expected`.

## 15. Registry 1.8: common points of conics and graphs; the parallel mark

Operations `since: "1.8"`, `beta` (formulas, decisions and checks in
`docs/native/ops/<op>.md`); a document that uses one declares 1.8 (§2).

| op | inputs → outputs | undefined | checks |
|---|---|---|---|
| `intersect.conic_conic` | `first, second: conical` → `first … fourth: point` | `no_intersection`, `coincident`, `concentric`, `branch_absent`, `outside_part`, `upstream` | `on_both` |
| `intersect.function_conic` | `function, conic: conical`; `count` → `point.k` | `no_intersection`, `coincident`, `outside_part`, `branch_absent`, `upstream` | `on_both` |
| `mark.parallel` | `lines: straight[] (min 2)`; param `count` → `mark` | `invalid_parameter`, `upstream` | `parallel` |

- Family `conical`: `conic`, `circle`, `arc` (an arc is met as its carrier
  circle, then filtered, as in §5.4).
- The common points of two curves are the real roots of a polynomial of
  degree four at most: one curve (an ellipse or a circle when there is one)
  is written by a rational parameter and substituted into the canonical
  equation of the other (`kernel/conic_meet.py`, `kernel/poly.py`). The
  roots are bracketed by the extrema of the polynomial (the sign-change
  roots of its derivative, recursively) and bisected; an extremum whose
  point lies within `tol.decide` of the other curve is a tangency. Two
  unbounded curves (hyperbolas, parabolas) are searched near the window
  `B4` only. Policy `first_curve_order`: the order along the first input —
  counterclockwise from the direction to the second centre (a circle, an
  ellipse), by branch and along it (a hyperbola), along the parabola, by
  the fraction of an arc; a tangency in two slots, both
  `detail.multiplicity: 2`. The slots swap only where a point crosses the
  seam of the first input (the ray from its centre to the second centre;
  `a0` of an arc). Two circular inputs give the slots of
  `intersect.circle_circle`.
- New noise decisions: `same_curve`, `same_centre`, `seam`.
- `intersect.function_conic` searches `h(x) = measure(x, f(x))` of the
  conic (its canonical equation over its unit, a length near the curve) on
  the grid of §14 over the x-range of `B4` cut by the domain, as
  `intersect.function_function`: policy `roots_ascending`, a tangency in two
  slots, a point off an arc `outside_part` (`detail.slot: "conic"`).
- Family `curve` takes `conic` and `function` (`_types.json → familySince`:
  `{"curve": {"conic": "1.8", "function": "1.8"}}`), so
  `intersect.nearest` and `intersect.other_than` meet them; their records
  and signatures stay those of 1.4 and 1.1, and only a document that puts a
  conic or a graph in such a slot declares 1.8. The solutions of a pair are
  those of its operation, in its order: graph × graph, graph × linear and
  graph × conic, circle or arc by `x` (`intersect.function_function`,
  `intersect.function_line`, `intersect.function_conic`), linear × conic
  along the line (`intersect.line_conic`), conic × conic, circle or arc by
  `first_curve_order` (`intersect.conic_conic`); `detail.slot` of an
  `outside_part` names `first` or `second`. `on_both` measures the focal
  residual of a conic and `|y − f(x)|` of a graph.
- «Команды»: no commands for them yet (`commands.lexicon.deferred_op`, as §14).
- Parity fixtures: the scenes `meet_*` of `parity/v1/curves`
  (`curves_fixtures.py`; `meet_graph_*` for the graphs), every reason of the operations, tangency,
  coincidence, close roots, a miss and the recovery, far coordinates, and
  `meet_seam`: a point crossing the seam swaps two slots between the cases
  `near_before` and `after`; `meet_curve_slots`: `intersect.nearest` and
  `intersect.other_than` on every kind of pair with a conic or a graph,
  including a tangency, a vertical line, a part and an arc.
- GGB import (`mapVersion` 5): `Intersect` of two conics, a conic and a
  circle or an arc, with or without the output number, is
  `intersect.conic_conic`, its slots bound by the saved values (`byValue`,
  as `intersect.circle_circle`). `intersect.function_conic` stays in
  `opsWithoutClassic` with the other intersections of functions.
- `mark.parallel` (`docs/native/ops/mark.parallel.md`): chevrons on two or
  more lines of family `straight` (`line`, `segment`, `ray`, `vector`; a
  side of a polygon is its segment `side.i`), value `{kind: "parallel",
  count}`, mark kind `parallel`. The `parallel` check is `max |u_1 × u_i| ·
  S` over the unit directions; a segment or a vector of no length leaves it
  `inconclusive`. The drawing (`parallel_count`, the direction of the
  chevrons, a second decoration channel) is in §9.3 «Marks». Command
  `ОтметкаПараллельных(AB, CD[, count])`: a pair of points is the segment
  between them (a hidden helper unless a visible one exists).

## 16. Registry 1.9: a point on a conic and on a graph

No new operation: the family `path` takes `conic` and `function`
(`_types.json → familySince`: `{"path": {"conic": "1.9", "function":
"1.9"}}`), so `point.on_path` and `point.closest` take them. Their records
and signatures stay those of 1.1 and 1.4; only a document that puts a conic
or a graph in a `path` slot declares 1.9 (`needs_newer_registry` otherwise,
§2). Formulas in [point.on_path](ops/point.on_path.md).

- `paths.conic` (kind `conic`): the parameter lives in the frame of the
  conic value (`u = axis`, `n = (−u_y, u_x)`). An ellipse (a circle conic
  too: `a = b`, `u = (1, 0)`) is measured by the eccentric anomaly from its
  own axis and wraps over `2π`; a hyperbola takes `t ∈ ℝ` and the `branch`
  `±1` of the input (default `+1`, the branch on `+u`), which the point
  keeps; a parabola takes `t ∈ ℝ`, `P = V + (p t²/2)·u + p t·n` (the frame
  of GeoGebra). `byKind` gives the range of each kind. The axis of a conic
  value is canonical (`u_y > 0`, kernel `conic.py`): a turning ellipse
  flips `u` where it crosses the x direction, and its points move by `π`
  there; a near-circle ellipse whose major axis switches turns `u` by `π/2`.
- `pathKind` (`"ellipse" | "hyperbola" | "parabola"`) of the input is the
  kind of conic the parameter was written for. A conic of another kind
  gives the point `undefined/path_kind_changed` (a new reason); when the
  kind returns, the same `t` applies again. Without `pathKind` any kind
  takes the parameter. Other paths ignore it; library writers put it only
  on a point on a conic. Carrying a point over to another kind ("as in
  GeoGebra") is a stateful wrapper of the product over `native.project`, not
  part of the kernel.
- `paths.function` (kind `graph`): `t` is the abscissa, clamped to the
  domain of the function (a `null` end is open); a point where `f` has no
  value (a gap of a piecewise `If` without `else`, a pole) is
  `undefined/out_of_domain`, as `point.on_function`.
- `point.closest` (and the projection of `native.project`): the exact
  nearest point of an ellipse (Eberly's bisection), of the nearest branch of
  a hyperbola and of a parabola (a root of a monotone function, bisected to
  the resolution of a double); the nearest point of a graph on a grid of 512
  cells over the window `B4` of the bounds and the point's abscissa, inside
  the domain, refined by the golden section (no value at all:
  `out_of_domain`). Formulas in
  [point.on_path](ops/point.on_path.md#inverse-nativeprojectdoc-id-x-y). New
  noise decisions: `closest_axis`, `closest_branch`. The registry has no
  `PathParameter` operation (a dependent path parameter of GeoGebra), so
  none is added for the new paths.
- Distances (`distance_to_path`; the check `on_path`, incidence): a conic
  gives its focal residual, a graph `|y − f(x)|` (as `on_both`, §15).
- A cosh/sinh that overflows gives `undefined/non_finite`.
- `native.project_input(doc, id, xy)` (library 1.14.0) is the whole input
  of the point at the projection: `{kind: "pathParameter", value: t}`, on a
  conic with `pathKind` (its kind now) and on a hyperbola with `branch`
  (the nearest). `native.project` is its `value`; both search a graph over
  the window of `viewDefaults.bounds`. Library writers of a path parameter
  (drag without a hint, conditions, the `move` request of commands, GGB
  import) write that input.
- Drag (§8.1): without a hint a point on a conic or a graph is projected
  (the nearest branch of a hyperbola; a graph stops at a given end of its
  domain — `clamped`); through a hint the parameter of an ellipse wraps
  over `2π`, a hyperbola keeps its branch, the difference step of a
  hyperbola, a parabola and a graph is `STEP_FRACTION · S / unit` (`b`,
  `p`, `1`). A `point.on_function` keeps its 1.12 rule (`x` of the target;
  no value there — `no_convergence`, the point stays). Fixtures
  `drag_conic_*`, `drag_graph_path*`, `drag_via_ellipse`,
  `drag_via_hyperbola` in `parity/v1/drag`.
- Timeline: a point on an ellipse wraps with the period `2π`; a sampled
  path parameter keeps `branch` and `pathKind` of the document's input
  ([timeline.md](timeline.md)).
- Parity fixtures: `path_conics` (an ellipse, both branches of a
  hyperbola, a parabola: turned, a circle, wrapped parameters, degenerate
  conics), `path_conic_kind` (`x²/9 + k y² = 1`: `path_kind_changed` and
  the recovery), `path_graphs` (domain ends, a piecewise graph with a gap, a
  pole), `closest_conics` (inside, outside, on the axes, both branches, a
  turned set), `closest_graphs` (a domain, the ends of a gap, no value, far
  from the window) in `parity/v1/curves`.
