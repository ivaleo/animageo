# Plan: framework-agnostic web integration (controllable movable figures)

> Derived from `docs/archive/jsxgraph_web_integration_audit.md`. Goal: let **any** web
> project (React/Vue/Svelte/vanilla/no-build) embed AnimaGeo constructions as
> *controllable* movable geometric figures — "controllable" = a clear
> signals/actions vocabulary expressed in **construction terms**, not in the
> rendering engine's terms. We do **not** tie to any framework; each project
> writes its own thin adapter, and we ship templates.

## A. Guiding principles

1. **The API is data contracts, not code.** Public surface = three versioned,
   JSON-serialisable contracts (Spec, State, Signals/Actions). No JS strings.
2. **Construction semantics, not engine semantics.** Signals/actions speak
   AnimaGeo/GGB (`point A`, `slider k`, `kind:"midpoint"`), never JSXGraph.
3. **Headless core.** The runtime is vanilla ESM with no framework deps; it
   returns an imperative handle (signals out / actions in).
4. **Web Component as the universal primitive.** `<animageo-board>` is the
   lowest common denominator — works in every framework and with none.
5. **Framework adapters are examples, not core.** React hook / Vue composable /
   Svelte action ship as ~30-line templates.
6. **JSXGraph knowledge moves from Python to the JS driver.** Python emits a
   neutral spec; translating to `board.create(...)` happens in the runtime.
   Decouples versions, removes the "API drift" risk.

## B. Layered architecture

```
Layer 0  Python / library
         construction graph + style resolver
         →  Board Spec (data)  +  Input/State Schema (data)  +  .d.ts / JSON-schema
Layer 1  @animageo/runtime  (vanilla ESM, no framework deps)
         createBoard(spec, container, opts) -> BoardHandle
         ├─ engine driver: Spec → JSXGraph (replaceable: canvas/wasm later)
         ├─ Signals (out):  ready / change / commit / select / viewchange / error
         └─ Actions (in):   getState/setState/setValue/reset/setVisible/...
Layer 2  Universal integration primitives (still framework-agnostic)
         ├─ <animageo-board>  Web Component (CustomEvents + methods + property)
         └─ UMD build for <script> (no bundler)
Layer 3  Framework adapters — EXAMPLES, not core
         useAnimageoBoard() (React) · composable (Vue) · action (Svelte) · vanilla
```

Library owns Layers 0–2 (all agnostic). Developers own Layer 3; we ship templates.

## C. The three contracts (the long-lived API)

### C1. Board Spec — `animageo-board/v1`

Declarative; replaces the JS-string `json` output. Each element records its
AnimaGeo semantics (`role`, `kind`, source `cmd`, `tracksDrag`) plus the concrete
render instruction (`engine` kind + structured `parents` + `attrs`). The runtime
driver consumes the render instruction directly (thin, robust), while the
semantic fields drive the signals/actions vocabulary and coverage.

```jsonc
{
  "format": "animageo-board/v1",
  "boundingbox": [-8, 6, 8, -6],
  "size": [800, 600],
  "chrome": { "axis": true, "grid": false, "background": "#fff", "keepAspect": true },
  "inputs": [
    { "name": "A", "kind": "point",  "x": -2, "y": -1 },
    { "name": "k", "kind": "number", "value": 3, "min": 0, "max": 10, "step": 0.1 },
    { "name": "P", "kind": "glider", "on": "c", "t": 0.4, "x": 1.2, "y": 0.7 }
  ],
  "elements": [
    { "name": "M", "role": "live",   "kind": "midpoint",
      "engine": "midpoint", "parents": [{"ref":"A"}, {"ref":"B"}], "attrs": {} },
    { "name": "f", "role": "static", "kind": "Function",
      "engine": "curve", "parents": [[/*xs*/],[/*ys*/]], "attrs": {},
      "frozen": true, "tracksDrag": false }
  ],
  "coverage": [ { "name": "f", "kind": "static", "detail": "Function (function_T)" } ]
}
```

Structured parent forms (pure data; a contained `js` escape hatch for the few
advanced live constructs — transforms, polygon-border binding):

```
{"ref": "A"}      reference to another element
3                 numeric literal
[1, 2]            coordinate pair
[[…],[…]]         sampled polyline (xs, ys)
{"fn": "..."}     live JS function body (slider-radius etc.)
{"js": "..."}     verbatim JS expression (escape hatch)
```

### C2. Input / State schema + value

State value = canonical inputs map (same family as keyframes /
`_snapshot_independents`), self-describing with slider metadata:

```jsonc
// schema (what is controllable) — the spec's "inputs" array, see C1
// value (payload of getState/setState/signals):
{ "A": {"x": -2, "y": -1}, "k": 3, "b": true, "P": {"t": 0.4} }
```

A bidirectional adapter to/from the keyframe wire format is provided so keyframe
animations and the live widget share one vocabulary.

### C3. Signals & Actions — the `BoardHandle`

```ts
interface BoardHandle {
  // Signals (out)
  on(signal: 'ready'|'change'|'commit'|'select'|'viewchange'|'error', cb): () => void;
  once(signal, cb): void;
  //  change/commit: { name, kind, value, state }   (continuous vs drag-end)
  //  select:        { name, kind }
  //  viewchange:    { boundingbox }
  // Actions (in)
  getState(): State;  setState(partial: Partial<State>): void;
  getValue(name): unknown;  setValue(name, value): void;
  getElement(name): { kind, coords?, value?, visible };
  reset(): void;
  setVisible(name, on: boolean): void;  setStyle(name, attrs): void;
  setBoundingBox(bbox): void;  fitView(): void;  resize(): void;
  toSVG(): string;  destroy(): void;
}
createBoard(spec, container, opts?): BoardHandle
```

The vocabulary is construction-relative (element names + AnimaGeo kinds), never
JSXGraph internals. That is the "controllability".

## D. Phases

### Phase 1 — Python contracts 🟥 (unblocks everything)
- `output="spec"` → Board Spec v1 (C1), no JS strings. Refactor `builder.py` to
  record structured `SpecElement`s; classify parents into structured forms.
- New `exporters/jsxgraph/spec.py` (dataclasses + serialisation + version).
- Generate the html/js outputs **from** the structured spec (proves sufficiency).
- Enrich `get_independents()` to carry optional `min/max/step` + a slider flag;
  surface as the spec `inputs` schema. (GGB parser support for slider bounds is
  an incremental sub-task; heuristic fallback meanwhile.)
- Ship `board.schema.json` + a generated `.d.ts`.
- Tests: schema-valid JSON, all kinds covered, spec→js round-trip equals current.
- Closes audit 3.1 (data layer), 3.5.

### Phase 2 — headless runtime `@animageo/runtime` 🟥
- New JS package in-repo (ESM + UMD), peer-dep `jsxgraph`, no framework deps.
- `createBoard` + a **JSXGraph driver** (Spec → `board.create`); all JSXGraph
  specifics live here.
- Signals/actions (C3); multi-instance (unique ids, no `window` globals); `ready`
  awaits MathJax; canonical state ↔ JSXGraph object mapping; debounced `change`.
- `EngineDriver` interface so a different backend can be added later.
- Tests: jsdom/Playwright — build, drag → change/commit, setState moves geometry,
  destroy cleans up.
- Closes audit 3.1 (events/state/instances).

### Phase 3 — universal integration primitives 🟧
- **Web Component** `<animageo-board>`: signals → `CustomEvent('animageo:change')`,
  actions → element methods, spec via property/attribute. Zero-framework path.
- UMD bundle for `<script src>`.
- Example adapters in `examples/web/`: React hook, Vue composable, Svelte action,
  vanilla — marked "examples, not core".

### Phase 4 — visual parity + dynamic coverage 🟧
- DONE (verified by tests + the browser smoke):
  - dash patterns → JSXGraph dash index (ratio thresholds mirror TikZ);
  - resolved z-index → JSXGraph `layer` (renderer stacking order);
  - 9-point `label_anchor` (GGB import / placement solver) → `anchorX`/`anchorY`
    (offset applied relative to the renderer's corner);
  - angle arc radius → `compute_effective_arc_size_px` (multi-arc expansion +
    optional `overlay.angle_radius` auto-scaling), byte-for-byte safe by default;
  - `viewchange` signal confirmed firing on real pan/zoom;
  - decorations: vector arrowheads (native, live, sized from `arrow_length_px`)
    and segment congruence ticks (live perpendicular dashes from function-valued
    anchor points — track drags), verified on live JSXGraph incl. `ex_general`'s
    GGB congruence marks.
- Static-curve pan/zoom: the runtime can't re-sample a frozen analytic curve
  (the definition isn't shipped). The honest mechanism is the `viewchange`
  signal → the host re-exports a spec for the new bbox; documented in
  `web/runtime/README.md`. Live elements are exact at any zoom.
- REMAINING (need a visual baseline to judge): broader live emitter coverage,
  finer arrowhead-style matching. A screenshot capture (`run.mjs --screenshot`,
  `--fixture NAME`) exists as the baseline tool; a strict pixel diff vs Cairo is
  intentionally avoided (different text/AA engines would make it flaky and
  over-claim).
- Addresses audit 3.3, 3.4 (the high-value, verifiable parts).

### Phase 5 — later
Structural edits (spec patch/diff in the runtime), alternate drivers
(canvas/wasm), server-driven via `postMessage`/iframe, SSR guidance.

## E. Distribution & versioning

- Contracts (C1–C3) carry `format: "animageo-board/v1"`; runtime checks major.
  Semver the contracts independently of the Python package.
- JS: publish `@animageo/runtime` (+ `@animageo/web-component`) as ESM, plus a
  UMD build for `<script>`. `jsxgraph` is a peerDependency (optionally vendored).
- Python: `exportJSXGraph(output="spec")` is the primary bridge; `html`/`js`
  remain for quick sharing.

## F. Audit → phase mapping

| Audit gap | Phase |
|---|---|
| 3.1 JS strings / globals / no events / no types / one instance / CDN | 1 + 2 + 3 |
| 3.2 intersection index, DSL points, free non-points, sliders | 1 (data) + 2/4 |
| 3.3 frozen curves, pan/zoom | 4 |
| 3.4 labels/dash/arcs/ticks/layers | 4 |
| 3.5 state model (min/max/step) | 1 |
| "two engines" risk | 4 (golden diff) |

## G. Decisions (taken)

1. **JSXGraph knowledge lives in the JS driver** (Python emits neutral spec).
   The spec retains an `engine`/structured-parent fast path so the v1 driver is
   thin; full re-derivation in JS is a later refinement, not required for v1.
2. **Distribution = npm ESM + UMD** simultaneously (bundlers and `<script>`).
3. **Web Component is the primary zero-framework primitive.**
4. **Extend `get_independents`** with slider bounds (also benefits keyframes);
   GGB-parser population of bounds is incremental.
