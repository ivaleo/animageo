# Audit: JSXGraph export & readiness for framework-agnostic web integration

> Scope: the interactive `exportJSXGraph` path (`animageo/exporters/jsxgraph/`)
> and the construction-state plumbing it depends on
> (`Construction.get_independents`, `AnimaGeoScene._snapshot_independents`).
> Goal: assess fitness for embedding AnimaGeo constructions as **controllable,
> movable geometric figures** in arbitrary web projects (any framework or none),
> with a clear signals/actions vocabulary tied to the construction.
>
> Companion: `docs/archive/jsxgraph_web_integration_plan.md` (the implementation plan
> derived from this audit).

## 0. What was audited

Full read of `exporters/jsxgraph/{builder,command_map,style_map,context,document,options,exporter,__init__}.py`,
`docs/archive/jsxgraph_export_plan.md` (Phases 0–3 marked shipped), `docs/archive/jsxgraph/spike_notes.md`,
`geo/construction.py::get_independents`, `animageo.py::exportJSXGraph` / `_snapshot_independents`,
and the CLI wiring in `__main__.py`.

## 1. Export model (how it works today)

The core idea is correct and strong: it **transpiles the construction graph, not
a rendered frame** (unlike SVG/TikZ). `build_board` walks:

1. **independents → widgets** (`_emit_free_inputs`): `free_point`→`point`,
   number/measure/angle→`slider`, boolean→`checkbox`; `tparam_point`→`glider`
   on its parent curve.
2. **commands in topological order → live emitters** (`command_map.py`): each
   element is created as a function of its parents' JS objects, so the JSXGraph
   engine recomputes it on drag.
3. **static fallback** (`_emit_static`): anything without a live mapping is
   sampled to frozen polylines and recorded in `coverage`.

Assembled into a `BoardModel` → `render()` emits `html`/`js`/`json`/`moodle`.

## 2. What is done well

- **Single shared style resolver** (`context.resolve` → `style.resolver`) — the
  same one SVG/TikZ use. Colours, widths, opacities, point shape, label colour
  carry over identically for GGB import, overlay and explicit `elem.style`.
- **No coordinate conversion**: geometry in math units (JSXGraph works in MU
  with a `boundingbox`); pixel sizes match JSXGraph pixels.
- **Transitive dynamic closure** (`_dynamic_closure`) — honestly computes what
  depends on draggable inputs and flags "won't track drags".
- **Solid school live set**: midpoint, segment, line/parallel, ray, vector,
  circle (incl. slider-radius via `function(){…}`), semicircle, polygon (with
  named edges bound to `poly.borders[i]`), perpendicular, perpendicular-bisector
  (composite), bisector, angle (reflex/nonreflex via `angle_range`),
  ellipse/hyperbola/parabola/conic-5, reflection, intersection, translate/rotate.
- **Tier-V** numeric expressions (`value_expr`): arithmetic + `distance/length/
  radius` translated to live JS.
- **Graceful degradation + coverage report**; smart intersection (live only when
  both parents are line/conic, else placed at exact AnimaGeo coords).
- **Thorough chrome import** (`_resolve_chrome`): axes/grid (+ per-axis), bg,
  colours, grid step/boldness, ticks, keep-aspect.
- **MathJax labels** with correct `$…$`/`\(…\)` unwrapping.

## 3. Weaknesses & gaps

### 3.1 Output architecture — the blocker for integration 🟥

| Problem | Where | Consequence |
|---|---|---|
| `output="json"` stores **JS strings** in `statements[]` | `document.py` json branch | Not a declarative spec — a consumer must `eval`. No typing, no inspection. |
| Script is an **IIFE** with `window.agboard`/`window.agS` | `document.py:48-50` | One board per page (globals clobber), no clean handle, no instance isolation. |
| **No events at all**: nothing registers `board.on(...)` | all of `document.py` | A host cannot learn about user motion without writing its own glue. |
| **No state API**: no `getState`/`setState` | — | Can't read construction state canonically nor drive it (controlled mode, analytics replay). |
| **No TS types / JSON schema** | — | Event payload and value props must be hand-typed. |
| `div_id` defaults to `"agbox"` (fixed) | `options.py:60` | Collisions with multiple figures on a page. |
| **CDN-only** load, global MathJax, no ESM/npm/vendored | `document.py::_cdn` | Anti-pattern for real bundles; no readiness signal (async load). |

### 3.2 GeoGebra-representation fidelity 🟧

| Aspect | Status | Detail |
|---|---|---|
| Slider min/max/step from GGB | ❌ lost | `_slider_range` uses heuristic `start ± max(|start|,5)`; angle 0..2π. Worse: `get_independents` (construction.py:493-503) returns only `value` — the bounds aren't stored in the model (`lib_vars` has no min/max/step). Two-layer gap. |
| Free number vs slider | ❌ not distinguished | Any free number becomes a slider, even if not interactive in GGB. |
| DSL `Point(x,y)` | ⚠️ not interactive | Carries a `point_ii` command → excluded from independents → emitted `fixed`. Code-built scenes are nearly non-interactive. |
| Free non-points (free line/circle/conic/vector at level 0) | ❌ frozen | independents returns only points/vars; in GGB these are draggable. |
| Intersection branch index | ⚠️ risk | `intersection(a,b,str(i))` ordering may not match AnimaGeo/GGB t-order (roadmap §5.1). |
| Tangent-from-point | ⚠️ static by design | Branch ambiguity → correct but frozen. |
| Glider on arc/conic | ⚠️ partial | Seeded by coords; JSXGraph parametrisation ≠ `tparam`. |

### 3.3 Dynamics — what does not come alive 🟧

- **Frozen, won't follow drag**: functions, implicit curves, conics-by-equation,
  arcs, sectors, loci, tangents. If an ancestor is draggable, the picture
  desyncs (flagged in coverage, but visually wrong).
- **Pan/zoom enabled** (`document.py`: `pan/zoom enabled`) yet static curves are
  polylines sampled to a fixed bbox → zoom/pan reveals coarseness / clipping.

### 3.4 Visual parity with the renderer 🟧

Carries colour/width/opacity/point-shape, but diverges in:

- **Label placement**: the `label_placement`/`autoPlaceLabels` solver is **not**
  applied in the JSXGraph path (`_apply_label` only carries an explicit
  `label_offset_px` > 1px). Labels land differently than in print SVG.
- **Dash**: any dash collapses to `dash: 2` (`style_map.py:74-75`).
- **Angle arcs**: a single `arc_size_px` is carried; **multi-arc (tick_count>1)
  and auto-radius `rendering.angle_radius` are not reproduced** (`emit_angle`
  reads `arc_size_px` directly, not `compute_effective_arc_size_px`).
- **Decorations**: segment/vector tick marks, arrow styles, line caps/joints not
  carried.
- **Z-order/layers**: JSXGraph `layer` not set → draw order = emission order.

### 3.5 State model (core gaps, not just the exporter) 🟧

`get_independents()` — the only source of "movable inputs" — drops the metadata a
UI needs: slider range/step, a "this is a slider" flag, and it misses DSL points.
Any integration hits this **before** the exporter. The existing
`_snapshot_independents` (animageo.py:1149) already produces a canonical value
format (same as keyframes) — that should become the official state contract.

## 4. How native GeoGebra solves this (reference)

Per the documented GeoGebra Apps API and general architecture:

- **Architecture**: Java core, web build transpiled to JS (GWT). The graphics
  view renders to an **HTML5 `<canvas>`** (immediate-mode raster), *not* SVG. One
  engine for authoring and embedding → pixel-identical "for free".
- **Embedding**: `deployggb.js` + `GGBApplet({...}, true).inject('div')`;
  **`appletOnLoad(api)`** is the readiness callback (the applet loads async).
- **Value/object API**: `evalCommand`, `setValue/getValue`, `setCoords`,
  `getXcoord/getYcoord`, `setXcoord/setYcoord`, `getObjectType`,
  `getAllObjectNames`, plus style setters (`setColor/setVisible/setLineStyle/…`).
- **State serialization**: `getXML()/setXML()`, `getBase64()/setBase64()`,
  `getFileJSON/setFileJSON` — full round-trip.
- **Events — tiered listeners (the key mechanism)**:
  - `registerUpdateListener(fn)` — any value change (drag);
  - `registerObjectUpdateListener(name, fn)` — per object;
  - `registerAddListener/RemoveListener/RenameListener/ClearListener` — structural;
  - `registerClientListener(fn)` — a rich typed event stream
    (`dragEnd`, `mouseDown`, `updateStyle`, `movedGeos`, `select`, `setMode`,
    `viewChanged2D`, undo/redo …) — distinguishes a continuous drag from a
    committed one (`dragEnd`/`movedGeos`);
  - `registerStoreUndoListener`.
- **React**: no first-party component (community `react-geogebra`); canonical
  pattern is `useEffect` + `appletOnLoad`, then `registerClientListener` +
  `getXcoord/getValue`.

**Lessons / contrasts:**

| | GeoGebra | AnimaGeo today | Lesson |
|---|---|---|---|
| Web render | canvas (1 engine) | SVG via JSXGraph (2 engines: Cairo + JSXGraph) | SVG is **better** for web/React (DOM nodes, CSS, a11y, inspection) — our advantage; but 2 engines → visual-divergence risk (§3.4). |
| Readiness | `appletOnLoad` | none | Need a `ready` signal. |
| Events | 3 listener tiers + `dragEnd` | **none** | Mirror the tiering: `change` (continuous) / `commit` (dragEnd) / `ready`. |
| State | getXML/getBase64 + get/setValue | manual global reads | Need `getState/setState` + per-object getters; value format already exists. |

## 5. Summary

The exporter core is **architecturally sound and mature** (graph transpilation,
shared resolver, graceful degradation, good live set). But it is designed for a
**single use case — a self-contained HTML page for viewing/dragging** — and is
**not ready** to be embedded as a controllable component on three critical axes:

1. no declarative, typed, versioned contract (only JS strings);
2. no state/signals API (only `window` globals);
3. the core state model drops interactive-input metadata (`get_independents`).

Plus the systemic "two engines" risk: the live widget can drift from the print
SVG (§3.4), which GeoGebra avoids by design.

Good news: the SVG/JSXGraph choice suits a web-component story **better** than
GeoGebra's canvas, and the canonical value format already exists
(`_snapshot_independents`) — it needs to be raised to a contract and wrapped with
events modelled on GeoGebra's listeners.
