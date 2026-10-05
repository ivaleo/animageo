# `animageo.native` — API reference

The public API of `animageo.native`, as of 1.11.0rc1: every name of
`animageo.native.__all__` with its actual signature, and the three names
outside `__all__` that the web service imports (`REGISTRY_VERSION`,
`as_document`, `bound_producer`). The signatures are those of
`tests/snapshots/public_api.json`; `tests/test_public_api.py` checks that this
page lists exactly those names with exactly those signatures, so a change of
the API changes the snapshot, this page and the CHANGELOG together.

```python
from animageo import native

doc = native.load('triangle.json')          # animageo-construction/v1
assert native.validate(doc) == []
ev = native.evaluate(doc)                   # values, states, reasons
native.render(doc, fmt='svg', out='triangle.svg')   # needs manim
```

`import animageo.native` needs neither manim nor the classic modules; only
`render()` (and `from_ggb()`/`from_construction()`, which call the classic
parser inside) load them. The contracts behind the functions are in
[kernel.md](kernel.md) (documents, registry, evaluation, edits, rendering),
[checks.md](checks.md), [conditions.md](conditions.md), [steps.md](steps.md),
[timeline.md](timeline.md), [commands.md](commands.md), [expr.md](expr.md)
and [import.md](import.md); what may change and how is in
[deprecations.md](deprecations.md).

Stability: the names and signatures below change only with a CHANGELOG entry
(a removal only in 2.0, after a deprecation); the operation registry `1.5` is
frozen as the 1.0 contract (kernel.md §4).

## Documents

Read, check and write `animageo-construction/v1` (kernel.md §1–§2).

- `DOCUMENT_FORMAT = 'animageo-construction/v1'`
- `class NativeDocument(data, schema_issues=())` — A loaded document. `data` is the JSON object; treat it as read-only.
- `class Issue(code, path, message, elementId=None, operationId=None, severity='error')` — One problem of a document. `severity` is `"error"` or `"warning"`.
- `exception LoadError(issues)` — The document cannot be read; `issues` lists the reasons.
- `load(source, *, strict=True)` — Read a document from a dict, a JSON string, bytes or a path.
- `validate(doc)` — All issues of a document: structure first, then the graph rules.
- `dump(doc)` — The document as a new JSON object (no defaults added, unknown keys kept).
- `dumps(doc)` — Canonical JSON text of the document (`canonical.py`).
- `canonical_json(value)` — Return the canonical JSON text of `value` (dict/list/str/number/bool/None).
- `content_hash(doc)` — `"sha256:" + hex(sha256(utf8(dumps(doc))))`; a plain dict is hashed as is.
- `as_document(source)` — `source` as a structurally valid document (loads it when needed).
- `bound_producer(doc, element_id)` — The producing operation ID of a consistently bound element, else `None`.

## Registry and features

The operation registry `ops/v1` (kernel.md §4) and what this library can do.

- `REGISTRY_VERSION = '1.5'`
- `__registry_version__ = '1.5'`
- `class Registry(version, ops, groups, types, families, policies, reasons, numeric, index=<factory>, paths=<factory>, number_units=<factory>, mark_kinds=<factory>)` — The loaded registry: records by op, service catalogs and the index.
- `registry()` — The registry shipped with this library (cached).
- `signature_hash(record)` — `"sha256:<hex>"` of the canonical JSON of `signature()`.
- `FEATURES` — The names `has()` knows, a tuple of strings. A feature is added with the release that brings it and is never removed.
- `has(feature)` — Whether this library has `feature` (one of `FEATURES`). A consumer checks a feature before it uses it, so it can run on an older library; the release that brought each feature is in the CHANGELOG.

## Evaluation and checks

Values, states and reasons (kernel.md §5–§7); checks and the general case (checks.md).

- `EVALUATED_FORMAT = 'animageo-evaluated/v1'`
- `class Evaluated(document_id, scale, elements, diagnostics, tolerances, library='', registry='1.5', computed=<factory>, t=None, visible=None)` — The result of `evaluate()`; `to_dict()` is `animageo-evaluated/v1`.
- `evaluate(doc, *, inputs=None, t=None, timeline=None)` — Values, states and reasons of every element of `doc`.
- `project(doc, element_id, xy, *, inputs=None)` — The path parameter of the point of a path nearest to `xy`.
- `check(doc, checks=None, *, inputs=None, relations=None, trials=0, seed=None)` — Mandatory checks of every operation whose outputs are defined, and relations between elements.
- `class CheckReport(results=<factory>, errors=<factory>, details=<factory>)` — `results`: key → status; `errors`: key → measured error; `details`: key → reason or `general_position` trial summary.
- `run_checks(evaluated, keys=None)` — Run the registry checks over an `Evaluated` result.
- `check_general(doc, targets=None, *, seed=None, trials=50, inputs=None)` — `{checkId: {status, trials, passed, failed, undefined, inconclusive, counterexample: {trial, inputs} | null, error, seed}}`.

## Editing

Edits return a new document (kernel.md §8).

- `class EditResult(document, effects)` — `document` — the edited `NativeDocument`; `effects` — what changed.
- `exception EditError(issues)` — An edit was refused; `issues` lists why (codes in kernel.md §8).
- `delete(doc, ids, *, mode='element')` — Delete elements and everything built on them.
- `redefine(doc, op_id, new_op, *, slot_map=None, inputs=None)` — Replace the definition of operation `op_id` keeping its output IDs (see `_redefine()`). Conditions (1.9.0a2): redefining the operation of a receiver removes the conditions on it (their places and automatic marks go, `effects.removed.conditions`); a result in which a receiver is an ancestor of a participant of its condition is refused with `condition_cycle` (one issue per condition).
- `rename(doc, element_id, display_name)` — Set the `displayName` of an element; the graph does not change.
- `closure(doc, ids, *, direction='down')` — Element IDs reachable from `ids` through the graph, `ids` included, in topological order (`element_order()`).
- `dependencies(doc, element_id)` — The ancestors of `element_id` (without it), in topological order.
- `free_inputs(doc, ids)` — The free elements (a free producer: point, path parameter) that `ids` are built from, `ids` included, in topological order.

## Conditions and marks

Conditions by recipes and automatic marks (conditions.md).

- `class ConditionResult(document, effects, condition, refusal)` — `document` — the new document (the old one on a refusal); `effects` as `redefine()` plus `shift`; `condition` — the entry of `conditions[]`; `refusal` — `Refusal` or `None`.
- `class Refusal(code, message, options)` — Why a condition was not applied: `code` (conditions.md), a `message` and the `options` the caller may offer instead.
- `apply_condition(doc, condition, *, receiver=None, id_factory=None, ev=None, marks=True)` — Apply `condition = {statement, mode: "construct", source, shapeId?}` (plan L3 §3.6). Refusals: `unsupported_condition`, `receiver_not_free`, `receiver_is_ancestor`, `too_many_conditions`, `no_intersection_now`. `marks`: add the automatic marks of the condition (`add_auto_marks()`; the web passes `False` when «Отмечать автоматически» is off).
- `release_condition(doc, condition_id, *, ev=None)` — Remove a condition: the receiver keeps its other constraints (none — `point.free` at its position, from `receiverOrigin` without `ev` and the warning `restored_origin`; one — `point.on_path` on the place left, at the projection); the places and marks of the condition go.
- `condition_candidates(doc, statement)` — `[{elementId, ok, reason}]` for every point of the statement, in its order: `ok` when it can be the receiver; `reason` `None`, `no_recipe` (no recipe puts it in the receiver's place), `not_free` or `ancestor`. Structural.
- `shape_conditions(doc, polygon_id, shape)` — `[{statement, receiver}]` that make the `polygon.by_points` `polygon_id` the `shape` (`SHAPES`), in the order to apply them; `[]` for another polygon (the caller refuses with `unsupported_condition`). Structural.
- `statement_checks(doc, statement)` — The predicates a statement compiles to: `[{predicate, args}]` where an argument is an element ID, `{"pair": [P, Q]}` or, for `equal_value`, the two expressions; `ne` is `not` around `equal_value`. Structural.
- `statement_problems(statement, doc=None, path='')` — `[(code, path, message, elementId)]`: `condition_bad_statement` (shape, kinds, types) and `condition_unknown_element`; types and existence are checked only with `doc`.
- `measure_statement(doc, statement, ev)` — `(status, error | None, detail | None)` of a statement in the evaluated document `ev`: `passed`, `failed` or `inconclusive` by `tol.check`, `unsupported` for argument types a predicate does not take. `ne` turns `passed` and `failed` round (`not`).
- `relation(doc, a, b, ev)` — `check.relation`: the predicates of `RELATION_ORDER` that hold (`passed`) for the objects `a` and `b` (element IDs or pairs) in `ev`, in that order.
- `class AutoMarks(document, operations, elements, warnings)` — `document` with the marks; `operations` — the new operations; `elements` — the new element IDs; `warnings`.
- `auto_marks(doc, sources, *, ev=None, id_factory=None)` — The new operations (helpers, then the mark; source by source) of the automatic marks of `sources` (operation or condition IDs).
- `add_auto_marks(doc, sources, *, ev=None, id_factory=None)` — `auto_marks()` put into a copy of the document.
- `auto_sources(doc)` — Every operation whose op is in the table and every construct condition with a recipe in the table — the sources of «Отметить автоматически» for a whole document (operation IDs sorted, then conditions in order).

## Steps and time

Steps of a construction (steps.md) and time by element ID (timeline.md).

- `class Step(id, kind, title=None, text=None, operationIds=<factory>, elementIds=<factory>, auxElementIds=<factory>, conditionIds=<factory>)` — One step of `steps()`; `kind` is given | op | group | condition.
- `exception StepError(issues)` — The explicit steps of a document are wrong (`issues`: `Issue` list).
- `steps(doc)` — The steps of `doc` in order (see the module docstring).
- `steps_split(doc, step_id, operation_ids)` — The `steps` array after moving `operation_ids` of step `step_id` into a new step (`s<n>`, kind `group` — `condition` for a condition) right after it. A «Дано» made automatically becomes explicit with the operations that stay. `ValueError`: no such step, a step of one operation, an empty selection, the whole step, or an operation that is not in the step.
- `steps_merge(doc, step_id)` — The `steps` array after merging step `step_id` into the step before it.
- `assign_seq(doc, op_ids)` — A copy of the document with `seq` = `max(seq) + 1, …` given to `op_ids` in that order (`max` over the document, `0` without any). `ValueError` for an operation that does not exist.
- `class StepsTimeline(keyframes, steps=<factory>, duration=0.0)` — The result of `steps_timeline()`: `keyframes` — a timeline v2 with ID keys; `steps` — `[{stepId, start, end, elementIds, text}]`; `duration` — the time of the last keyframe.
- `steps_timeline(doc, *, lag=0.3, duration=0.5, pause=0.6, effects=None, start=0.0)` — The construction step by step (plan L3 §5.4; docs/native/timeline.md §4).
- `sample_timeline(doc, timeline, t)` — `{t, inputs, visible}` of `timeline` at time `t` (module docstring).
- `timeline_to_bridge(doc, timeline)` — The classic keyframe JSON v2 of `timeline` for the scene of the bridge.

## Text

«Команды» (commands.md) and the description of a construction.

- `parse_commands(text, *, lexicon=None, base=None, id_factory=None, document_id=None)` — Build a document from «Команды» `text` (commands.md).
- `print_commands(doc, *, lexicon=None)` — The text of «Команды» for `doc` (commands.md §6).
- `describe(doc, *, values=False, phrases=None, ev=None, precision=2)` — The lines of the construction (see the module docstring).

## Rendering and labels

Rendering needs manim; label layout does not (kernel.md §9).

- `class RenderResult(path, fmt, report)` — `path` of the written file, its `fmt` and the `report` (a dict or `None`).
- `render(doc, *, style_config=None, export_layout=None, fmt='svg', out=None, inputs=None, t=None, timeline=None, report=True, video=None)` — Render `doc` to `out` (a temporary file when `None`).
- `source_view(doc)` — `{ptWidth, ptHeight, ptUnit, ptXZero, ptYZero}` of `viewDefaults.bounds`.
- `layout_labels(doc, ev=None, *, inputs=None, style_config=None, export_layout=None, backend='metrics', place=None)` — Label positions of `doc` as `native.render` would draw them, without manim.

## Import

From a `.ggb` and from the classic graph (import.md).

- `from_ggb(path_or_bytes, *, id_namespace, mode='partial', limits=None, name=None, empty_document=False)` — A `.ggb` (path or bytes) as `(document | None, import_report.v1)`.
- `exception ImportRefused(code, detail='')` — The file is refused before parsing: `code` — `import_too_large`, `import_not_ggb`, `import_too_many_objects` or `ggb_invalid`.
- `from_construction(constr, *, mode='strict', id_namespace, key_of=None, origin_of=None)` — A classic `Construction` (a DSL scene) as a document and a report.
- `exception ConvertError(items)` — `mode="strict"`: something does not translate; `items` — the records.

## Command line

`python -m animageo.native` (no manim needed except where noted):

| Command | What it does |
|---|---|
| `validate DOC` | the issues of a document (exit 1 if any) |
| `evaluate DOC` | `animageo-evaluated/v1` |
| `commands print DOC` / `commands parse TEXT` | «Команды» of a document, and back |
| `steps DOC`, `describe DOC`, `timeline DOC` | `steps()`, `describe()`, `steps_timeline()` / `sample_timeline()` |
| `from-ggb FILE.ggb` | the document and `import_report.v1` |
| `convert map --check` | the GGB command → operation table (`convert/dsl_map.json`) |
| `registry index --check` | `ops/v1/INDEX.json` matches the records |
| `fixtures verify`, `fixtures conditions --check`, `fixtures timeline --check` | the parity fixtures are up to date (manim for render fixtures) |
| `commands fixtures --check` | the fixtures of «Команды» |
