# `animageo.native` — contract of the reference kernel (L0)

`animageo.native` reads construction documents `animageo-construction/v1`,
evaluates them and produces parity fixtures. It never imports manim or the
classic modules (`animageo.animageo`, `animageo.geo`). The browser kernel of
the web app repeats everything on this page in TypeScript; the per-operation
formulas are in `docs/native/ops/<op>.md`. When the two kernels disagree, the library is
right and the fixtures it generates are the reference.

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
  "operationRegistryVersion": "1.0",             required, "<major>.<minor>"
  "operations": {ID: Operation},                 required
  "elements":   {ID: Element},                   required
  "inputs":     {ID: {"kind": "point", "value": [x, y]}},
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
```

- `ID` matches `^[A-Za-z0-9_-]{1,64}$`; the product uses UUIDv4, fixtures use
  readable IDs (`A`, `AB`, `op_A`).
- An argument slot matches `^[A-Za-z_][A-Za-z0-9_]*$`; an output slot may
  carry a 1-based index (`side.3`).
- Operations, elements, arguments, outputs, producers and inputs allow no
  keys besides the listed ones; the top level allows any key.
- `viewDefaults.bounds` needs `xmin < xmax` and `ymin < ymax` (checked by the
  library; JSON Schema cannot say it).
- Sections the library does not interpret — `appearance`, `styleBinding`,
  `timeline`, `exportDefaults`, `bindings`, `origin`, unknown keys — are kept
  as they are.

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
| `type_mismatch` | error | argument kind (list vs ref), a list shorter than `min`, an element type that does not fit the slot, an element type that differs from its output slot type, an input kind that differs from the free kind |
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

## 4. Registry `ops/v1`

`animageo/native/ops/v1/<group>.json` holds arrays of records:

```text
{op, status, since, inputs: [{slot, type, list?, min?}], params: [], outputs: [{slot, type, repeat?}],
 free?: {kind}, branch: null, undefined: [reason…], checks: [{id, text}], orientation,
 pathParam: null, stepKind, phrases: {ru}, math, signatureHash}
```

- a slot type may be a family: `linear = line | segment` (`_types.json`);
- `repeat: "vertices"` on output `side` declares the slots `side.1 … side.N`,
  `N` = number of items of the list argument `vertices`; a document may bind
  any subset of the declared output slots;
- `signatureHash = "sha256:" + sha256(canonical({op, inputs: [{slot, type,
  list (default false), min (default null)}], params: [{slot, type, unit
  (default null)}], outputs: [{slot, type, repeat (default null)}], free
  (default null), branch: branch.policy or null, orientation, pathParam}))`;
- `INDEX.json = {registryVersion, ops: {op: signatureHash}}`, written by
  `python -m animageo.native registry index` and checked by `--check`.

Service catalogs: `_types.json` (value fields and their kinds), `_reasons.json`
(reason → state), `_policies.json` (branch policies, empty in L0),
`_numeric.json` (bounds, tolerances, generator margin).

## 5. Evaluation `animageo-evaluated/v1`

```text
{"format": "animageo-evaluated/v1", "documentId", "kernel": {"library", "registry"},
 "scale": S, "elements": {ID: Record}, "diagnostics": [ … ]}
Record = {"state": "defined", "type", "value"}
       | {"state": "undefined" | "unsupported" | "error", "type", "reason", "cause"?, "detail"?}
```

`type` is the element's declared type. Values:

| type | value |
|---|---|
| point | `{x, y}` |
| segment | `{a: [x, y], b: [x, y], length}` |
| line | `{p: [x, y], dir: [x, y]}` — `p` the projection of the origin, `dir` unit, oriented by the definition |
| circle | `{c: [x, y], r}` |
| polygon | `{vertices: [[x, y], …], area}` — unsigned area |

### 5.1 Scale and tolerances

`S = max(w, h, D)`: `w = xmax − xmin`, `h = ymax − ymin` of `viewDefaults.bounds`
(or `defaultBounds = [-10, -10, 10, 10]`); `D = hypot(pxmax − pxmin, pymax − pymin)`
over the points of all free elements with a valid input value after the case
overrides (`D = 0` without any).

| tolerance | value |
|---|---|
| `tol.decide` | `1e-10·S` for lengths, `1e-10` for dimensionless values |
| `tol.check` | passed if error `≤ 1e-9·S`, failed if `≥ 1e-6·S`, otherwise inconclusive |
| `tol.parity` | `1e-9·S` coordinates and lengths, `1e-9·S²` areas, `1e-9` unit directions |

### 5.2 Element and operation states

Case `inputs` override the document's input values of free elements (an
override for an unknown or non-free element, or not
`{"kind": "point", "value": [finite, finite]}`, is a caller error).

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
4. a free op whose element has no valid input value → `error/schema`;
5. **upstream**: among the input elements (registry slot order, list items in
   order) that are not `defined`, take the worst state by
   `error > unsupported > undefined`, the first one on a tie; every output
   gets that state, `reason: "upstream"` and `cause` = that input's `cause`,
   or its ID when it has none (so `cause` always names the root element);
6. otherwise the implementation runs (`ops/*.md`). A value with NaN/∞
   becomes `undefined/non_finite`; an exception gives `error/internal` and a
   `diagnostics` entry `{code: "internal", operationId, op, message}`.

Every output slot is always computed; the elements bound to the op take
their slots. An element left without a record (never in L0) is `error/schema`.

### 5.3 Checks

Every operation that ran, produced a value for every slot of its result and
whose every element (by `producer.operationId`) is `defined` gets its registry
checks. A check measures an error `e ≥ 0` (a length) from the inputs and the
full op result; `e ≤ 1e-9·S` → `passed`, `e ≥ 1e-6·S` → `failed`, otherwise
(or non-finite `e`) → `inconclusive`. Report key: `"<operationId>:<checkId>"`.
The formulas are in the op pages.

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

Library set (`animageo/native/parity/v1/`): `basic_points`, `segment_line`,
`circle`, `intersect_lines`, `intersect_segments`, `polygon_triangle`,
`polygon_quad`, `upstream_chain`, `graph_errors`; at least three cases per
op, degenerate cases with binary-exact inputs.

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
skips the classic API for this entry point).

## 8. Floating point

Both kernels compute the same formulas in the same order in IEEE-754
doubles. `hypot` may differ by one unit in the last place between
implementations; values agree within `tol.parity`, and the generator's
margin rule keeps such differences away from every degeneracy decision.
