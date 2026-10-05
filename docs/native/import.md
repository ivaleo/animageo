# Import: `.ggb` and the classic graph as documents (`native.from_ggb`, `native.from_construction`)

animageo 1.10.0a1, kernel stage L5, stage 1 (plan L5 §3). The package
`animageo.native.convert` translates the classic `Construction` — the graph
`ggb_parser` builds from a `.ggb` and the DSL builds from a scene — into an
`animageo-construction/v1` document, by one table of commands. What does not
translate is reported with a reason; nothing is translated falsely.

```python
from animageo import native
doc, report = native.from_ggb("file.ggb", id_namespace=ns)          # partial by default
doc, report = native.from_construction(constr, id_namespace=ns)     # strict by default
native.has("from_ggb"), native.has("from_construction"), native.has("import_report.v1")
```

`doc` is `None` when nothing translates; with `empty_document=True`
(1.10.0a2, `native.has("from_ggb.empty_document")`) it is then a valid
document without operations — a file of pictures only gives the web a
document to place them on. `id_namespace` (a `uuid.UUID` or
its string) is given by the caller — the web passes the uuid of the import
(decision 6). `mode="strict"` raises `native.ConvertError` (`.items` — the
objects that are not editable) unless everything is editable;
`mode="partial"` returns the document of what translates.

## 1. The table `convert/dsl_map.json`

A row per classic dispatch key (`strFullCommand`: `midpoint_pp`,
`intersect_lci`, `polygon`; the same key for a `.ggb` and a DSL scene):

- an op row `{factory, ggb, op, args, outputs, index?, input?}` — `args`
  names the op slot of each classic input (`null` — not an argument, e.g.
  the output number; `{"ends": [a, b]}` — a segment whose two points fill
  `a` and `b`) or `{"variadic": slot}`; `outputs` — slots by classic output
  number, `{"byValue": [slots]}` (§3) or `{"pattern": "polygon_sides" |
  "regular"}`; `index` — the input holding the output number;
  `input: "pathParameter"` — a point on a path whose parameter is projected
  from the value;
- a free row `{free: "point" | "angle", value}` — `Point(x, y)` and
  `AngleSize(0.7)` of the DSL with literal arguments;
- an unmapped row `{unmapped: reason, note?}` — the reason of the report
  (`no_registry_op`, `formula_unsupported`, `unsupported_signature`); the
  note is English for the table, the report shows a Russian `detail`
  (`construction.NOTE_DETAILS`).

`opsWithoutClassic` lists the registry ops no classic key builds, with the
reason. `map_problems(seed=…)` checks both directions: every classic key has
a row, every op and slot exists, every registry op is used or listed, every
command of the web seed (`docs/native/seed/translate-2026-10.json`) is in a
row. `python -m animageo.native convert map [--check]`.

1.10.0a1: 477 classic keys; 140 op rows → 47 ops, 2 free rows; the rest
unmapped: conics, functions and coordinates — `no_registry_op` until stage
L4; arithmetic of values — `formula_unsupported`; predicates (`AreParallel`,
…) — `no_registry_op`; intersections with conics, points by numbers —
`unsupported_signature`.

Every op and free row has three cases in `tests/native/test_native_l5_convert.py`
(1.10.0a2): the general one, another configuration (the next variant of
each input — for a `byValue` row the classic outputs meet the slots in
another order, for an indexed row it is the other output) and a degenerate
one (well-formed inputs in a degenerate configuration: coincident or
collinear points, parallel lines, a tangency, a zero factor or vector).
Eight rows have no degenerate configuration the classic can reach, with
the reason (`NO_DEGENERACY`: a circle of radius 0 and a line through one
point are undefined in the classic; a free point; a locus is never
compared). In 31 degenerate configurations the classic and the kernel
disagree — at a tangency the classic gives one point and the kernel a
double one; a zero factor, a zero vector of a ray, a regular polygon on
coincident points, a semicircle on coincident points, a point on a ray of
zero length are point-like in the classic and undefined in the kernel; the
bisectors of parallel lines are undefined in the classic, the kernel gives
the midline; a flat polygon has a centroid in the classic only. They are
`differs`, never `editable` (`DEGENERATE_DIFFERS`).

## 2. Keys and IDs

`id = uuid5(id_namespace, key)`. Keys: a `.ggb` object — `ggb:<label>`; a DSL
variable — `dsl:<name>` (`key_of(name)` gives another key); a phantom `_N` —
`anon:<classic key>(<input keys>)#<output number>`, a repeat `~2`, `~3`: the
key follows the inputs, so a line inserted above changes no ID. An element —
`el:` + key (the second element of one object — `el:<key>/<slot>`); an
operation — `op:` + the key of its first output; `documentId` —
`uuid5(namespace, "document")` (the web replaces it). The names stay in
`bindings.legacyNames` and `displayName`.

## 3. Translation

Free objects first (a point → `point.free`, a number or slider →
`number.free` / `number.angle` with `min`, `max`, `step`), then the commands
in the classic order. A command whose input did not translate makes the
closure. Multi-output commands (intersections, tangents, bisectors of lines,
sector-line intersections) choose the slot of each classic output by value:
one evaluation of a probe document that binds every slot (decision 9; the
order of the classic is not static — C3). A point on a path gets its
`pathParameter` by `native.project` of its value. The document is validated
after every stage; an operation `validate` refuses is dropped with its
dependents.

## 4. `value_check` (tolerance `tol.import = 1e-6·S`)

| Type | `ggb_value` (from the XML) | Measure |
|---|---|---|
| point | `<coords x y z>` → `[x/z, y/z]` | distance |
| number, angle | `<value val>` (radians) | difference (an angle — on the circle; with `<angleStyle val="1|2">` the size shown within 0–180° / 180–360° is accepted too, `range` in `ggb_value`) |
| line, ray | normalised `<coords>` coefficients | coefficients |
| segment | the coefficients (the check); the two points in `ggb_value` when it is between two points | coefficients |
| circle, arc, sector | `<matrix>` → centre and radius | centre and radius |
| polygon | the vertices by label | vertices |
| other | — | `not_checked` |

`from_construction` compares with the classic values (`kernel/bridge.from_classic`).
Undefined in both (an intersection that does not exist) is `passed`.

## 5. The report `import_report.v1`

Schema: `schema/import_report.v1.schema.json` (the master copy; the web's
draft plus additions). Every `<element>` of the XML is exactly one entry:

- `editable` — an op with `value_check = passed`, or a free input taken as is;
- `differs` — translated, the value does not match (`value_mismatch`, `delta`)
  or is not comparable (`value_unchecked`, `not_checked`: a locus — decision
  12, «zero falsely editable»);
- `picture` — not translated, a value the web can place still (a point, a
  segment between two points, a polygon, a text);
- `unsupported` — not translated, with a reason;
- `closure` — depends (through any chain) on an unsupported object
  (`depends_on_unsupported`); a dependent of a picture is a picture or
  `unsupported` with `depends_on_unsupported`.

Reasons: `no_registry_op`, `random_point`, `formula_unsupported` (an argument
is an expression: `detail` names it), `style_only`, `script`, `3d`, `cas`,
`spreadsheet`, `image`, `latex_macros`, `fixed_text`, `unsupported_signature`,
`list`, `macro`, `ui_object`, `parse_error`, `depends_on_unsupported`,
`value_mismatch`, `slot_ambiguous`, `value_unchecked`. An object with a GGB
script is `script` (the script is never run; its siblings of one command stay
editable); an object the classic froze (a command it cannot run, an
expression it cannot parse) is not editable.

Each entry also carries `command`, `signature`, `detail` (Russian), `ggb_value`,
`native_value`, `delta`, `label {visible, mode, caption?}`, `ggb_style` (keys
of `appearance.overrides` the classic `loadGGB` would give: colours 6-digit
hex, thickness / 2 px, point size × 2 px, dash 0.65, the point shape,
`angle_range`), `hidden`, `layer`. The document carries `appearance.visible`
and `appearance.label` only; the colours are the web's decision (decision 8).
`dropped`: `script` (a non-default global `ggbOnInit` too), `animation`,
`conditional_visibility`, `dynamic_color`, `layers`, `3d`, `cas`, `image`
with `names` (≤ 50). `warnings`: `{code, ggb_name?, detail?}`.
`document_hash` is `native.content_hash` of the document.
`report_problems(report, document)` checks the rules the schema cannot.

`seq` of the operations follows the construction protocol (the XML order);
`steps` (groups) appear only when the XML has breakpoints — a step is the
protocol up to a breakpoint inclusive, the rest is the last step.

## 6. Untrusted input (plan §7)

A `.ggb` is data. `from_ggb` refuses before parsing (`native.ImportRefused`,
`.code`): `import_too_large` (file 20 MB, 50 entries, 50 MB unpacked by the
headers and by a bounded read — a zip bomb with lying sizes too, XML 10 MB),
`import_not_ggb` (not a zip, no `geogebra.xml`), `import_too_many_objects`
(3000), `ggb_invalid` (a `DOCTYPE` or `ENTITY`, XML deeper than 64, broken
XML). The archive is read in memory, nothing is extracted. GGB scripts are
counted, never run. The classic parser turns GGB expressions into Python for
`dsl.run`; `ggb_parser._check_ggb_code` now refuses there anything but one
assignment of an expression — no `__dunder__` name, no private attribute, no
lambda, comprehension or definition (before 1.10.0a1 a `.ggb` expression
could reach `object.__subclasses__()`). `tests/native/test_native_no_exec.py`
keeps `exec`, `eval`, `compile`, `subprocess`, … out of `animageo.native`.

1.10.0a2, after fuzzing (`tests/native/test_native_l5_fuzz.py`, marker
`fuzz`; the random series are `slow` too): the outcome of any input is a
report or `ImportRefused` — never another exception, never a hang (each case
runs under a 20 s deadline). What the fuzzing changed:

- refusals: any damage of the archive (a broken deflate stream, an unknown or
  encrypted method, a wrong CRC) is `import_not_ggb`; a `DOCTYPE` is refused
  in any encoding (UTF-16/32 too, by the parser, not by a byte search); an
  encoding Python cannot decode is `ggb_invalid`; an object name longer than
  200 characters is `ggb_invalid`;
- a regular polygon takes 3 to 100 vertices (`unsupported_signature`
  otherwise); the classic `Polygon(A, B, n)` refuses more than 10 000;
- a name defined twice: the first definition wins, the second command is the
  warning `duplicate_definition`; an output of a command without its own
  `<element>` is not an object of the report, its dependents are
  `parse_error`;
- a free input whose value fails the check (a point at infinity, a
  non-finite value) is `differs`, not `editable`; a view with non-finite or
  empty bounds is ignored;
- the categories are set dependencies first and then settled
  (`report.settle`): the closure is exactly the dependents of unsupported
  objects, and an editable object never refers to an element that is not in
  the document — whatever the order of the XML, a cycle or a dangling name;
- the long strings of the report are cut to the schema (`signature` 80,
  `app` and `ggb_version` 40).

## 7. Command line

```text
python -m animageo.native from-ggb <file.ggb> [-o doc.json] [--report rep.json] [--namespace UUID] [--mode partial|strict]
python -m animageo.native convert map [--check]
```

`from-ggb`: exit 0 (`partial`, even with objects that do not translate), 1 —
`strict` with objects that are not editable, 2 — a refused or missing file.
Without `--namespace` the IDs come from the sha256 of the file.

## 8. Deliberate files (1.10.0a2)

The deliberate files `tests/native/import/synthetic/*.ggb` (21: 3D, CAS,
spreadsheet cells, scripts and a button, lists, a macro, breakpoints, a DTD,
a zip without `geogebra.xml`, pictures only, texts, a function and its
closure, an expression argument, dropped effects, a random point, styles,
user-interface objects, regular polygons) are the output of
`tests/native/ggb_synth.py` (`python -m tests.native.ggb_synth` rewrites
them; a test compares them entry by entry); each shows what it is for
(`test_native_l5_corpus.py`).
