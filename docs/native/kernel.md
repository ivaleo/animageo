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
  "viewDefaults": {"bounds": [xmin, ymin, xmax, ymax], …},
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
          | {"kind": "pathParameter", "value": t, "branch"?: -1 | 1}    point.on_path
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
| `unknown_slot` | error | an argument or output slot the op does not declare (a repeat slot beyond the list length too) |
| `missing_slot` | error | a declared input slot or a required param has no argument |
| `dangling_ref` | error | a reference (argument or `inputs` key) to a missing element |
| `type_mismatch` | error | argument kind (list vs ref), a list shorter than `min`, an element type that does not fit the slot, an element type that differs from its output slot type, a number literal in an input slot of another type, a param argument that is not a number literal, an input kind that differs from the free kind (`point` for `point.free`, `pathParameter` for `point.on_path`, `number` for `number.free`, `angle` for `segment.from_point_length`) |
| `cycle` | error | the operation lies on a dependency cycle |
| `formula` | error | an `expr` tree breaks AST v1 (a node, the whitelist, a limit, a `ref` outside `refs`); `path` points at the node ([expr.md](expr.md) §2). A `template` with a bad brace or an insert outside `refs`; `path` is the template's `value` ([ops/text.free.md](ops/text.free.md)) |
| `input_not_free` | error | an input value for an element not produced by a free op, or for an element of a free op other than its first output slot |
| `missing_input` | error | the element of the first output slot of a free op without an input value (not for an `angle` input, which defaults to `0`) |

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

## 4. Registry `ops/v1` (version 1.5)

Registry 1.4 is frozen since animageo 1.8.1: the records of 1.0–1.4 and their
`signatureHash` stay as they are (`beta` is a descriptive status outside the
hash and may become `stable`); a new operation or a changed signature goes to
registry 1.5. Registry 1.5 (animageo 1.9.0a1) adds the operations of a
triangle and the locus (§11).

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

- A slot type may be a family (`_types.json` → `families`):

  | family | types |
  |---|---|
  | `linear` | `line`, `segment`, `ray` |
  | `circular` | `circle`, `arc` (1.4) |
  | `curve` | `line`, `segment`, `ray`, `circle`, `arc` (1.4) |
  | `path` | `line`, `segment`, `ray`, `circle`, `polygon`, `arc`, `sector`, `polyline` (1.4) |
  | `round` (1.4) | `circle`, `arc`, `sector` |
  | `vertexed` (1.4) | `segment`, `polyline`, `polygon` |
  | `measurable` (1.4, a5) | `segment`, `vector`, `polyline`, `arc` |
  | `bounded` (1.4, a5) | `polygon`, `circle`, `sector` |
  | `figure` (1.4, a5) | `point` and the `path` types |
  | `transformable` (1.4, a5) | `point`, `segment`, `ray`, `line`, `vector`, `circle`, `arc`, `sector`, `polygon` |
  | `insertable` (1.4, a5) | `number`, `point` |

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
  1.4 (a test pins them);
- params (`type: "number"` only) are op settings written in `args` as
  number literals: `optional` (default `false`) and `default` (a number or
  absent) are outside the hash. An absent optional param reaches the
  implementation as its `default`, or as nothing (`None`/`null`) without
  one; whether a value is allowed (`strict ∈ {0, 1}`, `min ≤ max`) is the
  op's decision, `undefined/invalid_parameter`. The registry check refuses a
  param that is not a number, a non-numeric `default` and a required param
  with a `default`;
- `INDEX.json = {registryVersion, ops: {op: signatureHash}}`, written by
  `python -m animageo.native registry index` and checked by `--check`.

Service catalogs:

- `_types.json`: value fields and their kinds (`types`), `families`, path
  frames (`paths`, `frameKinds`, §5.5), `units` and `numberUnits` (§6);
  since 1.3 `markKinds` (mark kind → the operation that makes it; the
  registry check refuses a kind whose operation has no `mark` output) and
  `angles` (the normalisation of a direction, the convex measure and the
  wrap of a difference of directions, §5);
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
| mark | `{kind, count}` — `kind` one of `markKinds` (`equal_segments`, `equal_angles`, `right_angle`), `count` an integer `1…3` (`1` for a right angle) |
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
`{"kind": "pathParameter", "value": t, "branch"?: ±1}` (`branch` is reserved
for two-branch paths of a later registry and ignored in 1.1 and 1.2). The parameter
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
| `delete(doc, ids, *, mode="element")` | `closure(ids, "down")` goes; an operation loses the outputs that went and goes when none are left or when it references a removed element; `mode="operation"` also removes every other output of the producers of `ids`. Inputs and appearance of removed elements go |
| `redefine(doc, op_id, new_op, *, slot_map=None, inputs=None)` | replaces the definition (`{op, args, branch?}`) keeping the output IDs: outputs pair with new slots by name or `slot_map`; an output without a pair goes with its dependents (warning `output_removed`); types and producers of the paired elements follow the new op; `inputs` gives the input values a new free op needs; the inputs of elements that stop being free go |
| `rename(doc, id, display_name)` | sets `displayName`; the graph does not change |

`effects` is JSON-ready; every list is sorted:

```text
{"added":    {"operations": [], "elements": [], "inputs": []},
 "removed":  {"operations": [], "elements": [], "inputs": [], "appearance": []},
 "modified": {"operations": [], "elements": [], "inputs": []},
 "warnings": [Issue.to_dict(), …]}
```

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
| any `validate` code | redefine | an error the document did not have before |
| `invalid_name` | rename | the name breaks the grammar |
| `duplicate_name` | rename | another element has the same name key |

Display names (`valid_name`, at most 32 code points):

    name   = letter+ suffix? "'"*
    suffix = "_{" alnum+ "}" | "_" alnum+ | [0-9]+ | [₀-₉]+

`letter` is a Unicode letter (category L*), `alnum` a letter or a decimal
digit (Nd): `A`, `AB`, `A1`, `A₁`, `A_1`, `A_{12}`, `α'`, `Точка`.
Uniqueness compares `name_key`, where `_{x}` equals `_x`.

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
  `displayName`; `displayName` is the label name;
- `offsetWorld: [dx, dy]` (world units, y up) → `label_offset_px =
  [dx·ptUnit, dy·ptUnit]` of the source view, and the label is locked
  against automatic placement;
- `overrides`: element style keys (stroke, fill, points, labels, ticks,
  arrows, angles, `z_index`, `z_index_fill`; the list is
  `rendering.APPEARANCE_STYLE_KEYS`). Other keys are not applied.
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
  nothing;
- a visible, defined right-angle mark gets `right_angle_marker = true`
  unless its `overrides` set it.

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
`{code: "unknown_style_key", elementId, key}`.

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
  `mov` with `video={fps, quality}` (`ValueError("timeline_required")`).
- `steps_timeline(doc, *, lag, duration, pause, effects, start) →
  StepsTimeline(keyframes, steps, duration)`.
- Fixtures `animageo-timeline/v1` (`fixtures timeline`); the steps fixtures
  carry `expect.timeline`; CLI `steps`, `describe`, `timeline`;
  `native.has`: `timeline`, `steps_timeline`, `render.t`, `render.video`.
