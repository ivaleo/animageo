# `animageo.native` — contract of the reference kernel (L0–L1)

`animageo.native` reads construction documents `animageo-construction/v1`,
evaluates them, edits them and produces parity fixtures; with manim
installed it also renders them (§9). No module of the package imports manim
or the classic modules (`animageo.animageo`, `animageo.geo`) at import time:
the bridge and the renderer load the classic code inside their functions.
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
  "operationRegistryVersion": "1.1",             required, "<major>.<minor>"
  "operations": {ID: Operation},                 required
  "elements":   {ID: Element},                   required
  "inputs":     {ID: Input},
  "viewDefaults": {"bounds": [xmin, ymin, xmax, ymax], …},
  "appearance", "styleBinding", "timeline", "exportDefaults", "bindings", any other key
}
Operation = {"id": ID, "op": "group.name", "args": {slot: Argument},
             "outputs": [{"slot": slot, "elementId": ID}], "branch"?: null | {"policy", "selector"}}
Argument  = {"kind": "ref", "elementId": ID}
          | {"kind": "list", "items": [Argument, …]}
          | {"kind": "number", "value": number}
Element   = {"id": ID, "type": type, "producer": {"operationId": ID, "slot": slot},
             "displayName": string, "origin"?: object}
Input     = {"kind": "point", "value": [x, y]}                         point.free
          | {"kind": "pathParameter", "value": t, "branch"?: -1 | 1}    point.on_path
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
  registry 1.1: the output slot names the solution (§5.4).
- Sections the library does not interpret — `appearance` (read by the
  renderer, §9), `styleBinding`, `timeline`, `exportDefaults`, `bindings`,
  `origin`, unknown keys — are kept as they are.

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
| `missing_slot` | error | a declared input slot has no argument |
| `dangling_ref` | error | a reference (argument or `inputs` key) to a missing element |
| `type_mismatch` | error | argument kind (list vs ref), a list shorter than `min`, an element type that does not fit the slot, an element type that differs from its output slot type, an input kind that differs from the free kind (`point` for `point.free`, `pathParameter` for `point.on_path`) |
| `cycle` | error | the operation lies on a dependency cycle |
| `input_not_free` | error | an input value for an element not produced by a free op |
| `missing_input` | error | a free element without an input value |

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

## 4. Registry `ops/v1` (version 1.1)

`animageo/native/ops/v1/<group>.json` holds arrays of records:

```text
{op, status, since, inputs: [{slot, type, list?, min?}], params: [], outputs: [{slot, type, repeat?}],
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

- A slot type may be a family (`_types.json` → `families`):

  | family | types |
  |---|---|
  | `linear` | `line`, `segment`, `ray` |
  | `circular` | `circle` |
  | `curve` | `line`, `segment`, `ray`, `circle` |
  | `path` | `line`, `segment`, `ray`, `circle`, `polygon` |

- `repeat: "vertices"` on output `side` declares the slots `side.1 … side.N`,
  `N` = number of items of the list argument `vertices`; a document may bind
  any subset of the declared output slots;
- `signatureHash = "sha256:" + sha256(canonical({op, inputs: [{slot, type,
  list (default false), min (default null)}], params: [{slot, type, unit
  (default null)}], outputs: [{slot, type, repeat (default null)}], free
  (default null), branch: branch.policy or null, orientation, pathParam}))`;
  the hashes of the 1.0 records did not change in 1.1;
- `INDEX.json = {registryVersion, ops: {op: signatureHash}}`, written by
  `python -m animageo.native registry index` and checked by `--check`.

Service catalogs:

- `_types.json`: value fields and their kinds (`types`), `families`, path
  frames (`paths`, `frameKinds`, §5.5) and `units`;
- `_reasons.json`: reason → state;
- `_policies.json`: branch policies (`single`, `line_param_order`,
  `circle_side`, `other_than`, §5.4);
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

A defined record carries `detail` only for a double root of a two-slot
intersection: `{"multiplicity": 2}` in both slots (§5.4). Undefined records
use `detail` for the slot of an `outside_part` (`{"slot": "<argument slot>"}`)
and the like, as the op pages say.

### 5.1 Scale and tolerances

`S = max(w, h, D)`: `w = xmax − xmin`, `h = ymax − ymin` of `viewDefaults.bounds`
(or `defaultBounds = [-10, -10, 10, 10]`); `D = hypot(pxmax − pxmin, pymax − pymin)`
over the points of all free `point` elements with a valid input value after
the case overrides (`D = 0` without any). Path parameters do not take part in
`S`.

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
   `error/type_mismatch`. The first problem found wins;
4. a free op whose element has no usable input value of its kind →
   `error/schema`;
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
their slots. An element left without a record (never in 1.1) is `error/schema`.

### 5.3 Checks

Every operation that ran, produced a value for every slot of its result and
whose every element (by `producer.operationId`) is `defined` gets its registry
checks. A check measures an error `e ≥ 0` (a length) from the inputs and the
full op result; `e ≤ 1e-9·S` → `passed`, `e ≥ 1e-6·S` → `failed`, otherwise
(or non-finite `e`) → `inconclusive`. Report key: `"<operationId>:<checkId>"`.
The formulas are in the op pages.

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
for two-branch paths of a later registry and ignored in 1.1). The parameter
lives in the frame of the path's definition (`_types.json` → `paths`), so the
point moves with the path:

| path | kind | frame | parameter | default |
|---|---|---|---|---|
| segment | affine | `o = a`, `v = b − a` | clamped to `[0, 1]` | `0.5` |
| line by `line.by_points` | affine | `o = a`, `v = b − a` (the producer's points) | any | `0.5` |
| other line | affine | `o = p`, `v = dir` | any | `0.5` |
| ray by `ray.by_points` | affine | `o = origin`, `v = through − origin` | `t < 0` → `0` | `0.5` |
| other ray | affine | `o = origin`, `v = dir` | `t < 0` → `0` | `0.5` |
| circle | angle | centre `c`, radius `r` | angle from +x | `π/4` |
| polygon (`n` vertices `V`) | perimeter | the sides in order | wraps to `[0, n)` | `0.5` |

    affine:     point = o + clamp(t)·v
    angle:      point = (cx + r·cos t, cy + r·sin t)
    perimeter:  t' = t − n·floor(t / n);  t' < 0 → t' + n;  t' ≥ n → 0
                k = floor(t'), f = t' − k
                point = V[k] + f·(V[(k + 1) mod n] − V[k])     (side side.(k + 1))

The frame of a path element comes from `frames[<producer op>]` (on the
values of the producer's arguments) when its producer is listed there,
otherwise from `frames["*"]` (on the element's own value).

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
`scalar`); arrays by length and item; check statuses exactly; the scale
within `1e-9·S`.

**Near-degenerate inputs are refused.** Every degeneracy decision reports its
decision value `m`, measured from the exact mathematical boundary, and the
decide tolerance `tol` it is compared to (listed per op). The generator
refuses a case when

    0 < |m| < 1e3 · tol        (decisionMargin = 1e3, _numeric.json)

so a fixture never depends on which side of `tol` a rounding error falls.
`m = 0` exactly — a degenerate configuration built from binary-exact inputs
(equal points, axis-parallel lines, an intersection exactly at a segment
end) — is accepted.

**Noise decisions** (`generator.noiseDecisions = ["known", "tangent"]`): for
these, `|m| ≤ tol / 1e3` also counts as exactly on the threshold. Their
values are the rounding noise of an exact construction — a tangent built as
a tangent, a `known` point that is an intersection of the same pair — and
cannot be made binary-exact. A noise value between `tol / 1e3` and `1e3·tol`
is still refused.

Library set (`animageo/native/parity/v1/`, 31 scenes):

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
  `on_path_polygon`, `on_path_chain`.

At least three cases per op; degenerate cases with binary-exact inputs or a
noise decision.

## 7. Command line

```text
python -m animageo.native fixtures generate <scenes…> -o <dir>
python -m animageo.native fixtures verify <fixtures…>          # exit 1 on a mismatch
python -m animageo.native registry index [--check]             # exit 1 when out of date
python -m animageo.native evaluate <doc.json> [--inputs case.json] [--checks] [--canonical]
python -m animageo.native validate <doc.json> [--json]          # exit 1 when there are issues
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
LaTeX for labels); `source_view` and the appearance mapping do not.

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
 "kernel": {"library": "1.8.0a2", "registry": "1.1"},
 "fmt": "svg",
 "canvas": {"width": W, "height": H, "unit": u, "origin": [ox, oy]},
 "elements": {"<elementId>": {"state": "defined" | "undefined" | "unsupported" | "error",
                              "visible": true | false,
                              "box": [x0, y0, x1, y1] | null,
                              "label": {"box": [x0, y0, x1, y1], "anchor": [x, y] | null,
                                        "text": "$A$"} | null}},
 "overlaps": [["<elementId>", "<elementId>"], …],
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
  `appearance`); otherwise `box` and `label` are `null`.
- `box` bounds the drawn element without its label; `label.box` bounds the
  label (without its leader line); `label.anchor` is the point the label is
  attached to (the classic label attach spot, in px); `label.text` is the
  label source text (LaTeX for names).
- `overlaps` lists the label pairs whose box intersection is at least
  `0.15` of the smaller box's area, each pair sorted, the list sorted, all
  pairs (no cap).
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

## 10. Floating point and determinism

Both kernels compute the same formulas in the same order in IEEE-754
doubles. `hypot` may differ by one unit in the last place between
implementations; values agree within `tol.parity`, and the generator's
margin rule keeps such differences away from every degeneracy decision.

The kernel has no state and no randomness: the evaluation of a document does
not depend on the order of its keys, the order of evaluations or on
repeating them, and no module of the package imports `random` or
`numpy.random` (`tests/native/test_native_determinism.py`).
