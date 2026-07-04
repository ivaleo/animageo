# JSXGraph / interactive web export — deep-dive plan

> Status: **Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3 ✅ shipped.** A live, draggable
> construction in the browser, not a static picture — the flagship
> "differentiator" export. `scene.exportJSXGraph(...)` + CLI `-o foo.html`;
> subpackage `animageo/exporters/jsxgraph/`; tests in
> `tests/test_jsxgraph_export.py`. **Verified in a real browser** (headless
> Chrome) on `ex_general.ggb` and `func5.ggb`: renders, MathJax typesets, no JS
> errors, dragging a free point recomputes dependents live, and conics/functions
> draw correctly (see `docs/archive/jsxgraph/spike_notes.md`).
>
> **Live creators**: free points → draggable points, points-on-curves →
> gliders, numbers → sliders, booleans → checkboxes; midpoint/center, segment,
> line (+parallel), ray, vector, circle (center+point / +radius / +slider-
> radius), **semicircle**, **polygon** (named edges bound to `poly.borders[i]`),
> perpendicular, **perpendicular-bisector** (composite: hidden midpoint +
> perpendicular), angular bisector, angle, **ellipse / hyperbola / parabola /
> conic (5-point)**, **reflection / mirror**, and intersection (indexed, *smart*:
> live only when both parents are line/conic objects, else points are placed at
> AnimaGeo's computed coordinates).
>
> **Phase 3 adds**: live **transforms** — `rotate`/`translate` of a point via a
> JSXGraph `transform` object (verified live in-browser: dragging the source
> moves the image); live **Tier-V numeric values** — a small expression
> translator turns `distance`/`length`/`radius` and arithmetic
> (`add/sub/mult/div/pow/abs/sqrt/sin/cos/tan`) into JS so a derived number
> feeding a creator (e.g. `Circle(M, Distance(A,B))`) updates on drag; and a
> **`moodle`** output flavour (`<jsxgraph>` block for the filter_jsxgraph plugin,
> best-effort, untested against a live Moodle).
>
> **Everything else is drawn statically** — functions, implicit curves,
> conics-by-expression, arcs, sectors, loci are sampled into JSXGraph `curve`
> elements; level-0 directly-defined curves are emitted before their dependents.
> Nothing visible is dropped: on `ex_general.ggb` → **17 live / 3 inputs / 0
> static / 0 skip**; on `func5.ggb` → all conics/functions/implicit drawn, only
> genuinely-empty (`None`) outputs skipped.
>
> Phase 3 also makes **non-point transforms live** — `translate`/`rotate` of
> segments / lines / circles / vectors / polygons via
> `board.create(kind, [original, transform])` (verified in-browser).
>
> **Intentionally static** (documented): `tangent`-from-an-external-point —
> AnimaGeo yields a single tangent output while there are two tangents, and
> JSXGraph's intersection-branch index can't be matched to ours at export time,
> so a live polar construction would risk the wrong branch; the static fallback
> draws the *correct* AnimaGeo-computed tangent line. Tier-V live coverage is
> the common ops above (not every measure). DSL `Point(x,y)` constructions are
> not detected as free independents (only GGB-imported free points are) — see
> the spike notes.

---

## 1. Vision & why it matters

A reader opens an HTML page, **drags a free point or a slider**, and the whole
dependent construction recomputes live — angles, intersections, circles,
conics follow. Targets: online textbooks, LMS (Moodle), course sites, blogs.

[JSXGraph](https://jsxgraph.org) is the natural backend: cross-browser HTML5
interactive geometry, no plugins, its own constraint engine, MathJax labels,
small footprint, Moodle filter integration.

This is the one export that **no screenshot-from-GeoGebra tool can produce** —
it requires the *semantic construction graph*, which is exactly what AnimaGeo
already owns.

---

## 2. The core insight: transpile the graph, not the frame

The existing exporters (SVG / PDF / TikZ) serialise a **rendered frame**: they
walk *elements* and emit static primitives at fixed coordinates.

JSXGraph is fundamentally different. To stay interactive, we must reproduce the
**dependency graph** in the browser:

- walk **commands in topological order** (not elements in z-order);
- create each element **as a function of its parents' JS objects**, so
  JSXGraph's engine recomputes it when an ancestor moves;
- turn the **independent inputs** into draggable points / sliders / gliders.

So the central new structure is a **`command_map`: `Command → board.create(...)`**
— the inverse of `lib_commands.COMMAND_REGISTRY`.

---

## 3. What we already have that makes this tractable

### 3.1 `get_independents()` → interactive inputs (1:1 mapping)

`Construction.get_independents()` already classifies every animatable input —
this *is* the set of interactive widgets:

| AnimaGeo independent | JSXGraph element | Interaction |
|----------------------|------------------|-------------|
| `free_point` (coords) | `board.create('point', [x, y])` | draggable point |
| `tparam_point`, constraint = `circle` | `board.create('glider', [x, y, circle])` | glider on circle |
| `tparam_point`, constraint = `line`/`segment`/`ray` | `glider` on that parent | glider on line |
| `number` / `measure` | `board.create('slider', …)` | slider |
| `angle` | `slider` (radians/degrees) | angle slider |
| `boolean` | `checkbox` | toggle |

Gliders are seeded with the current `coords` from `get_independents()` (JSXGraph
then snaps to the nearest parameter on the parent).

### 3.2 The construction graph

- `Command(name, inputs, outputs)` (`lib_commands.py`): `name` is the base
  operation, `inputs`/`outputs` are element/var names (or literals).
- `Construction.commands` is already **topologically sorted** (Kahn) — emit in
  this order and every parent JS variable exists before its child.
- `construction.state[name]['outputs'/'level'/'input_commands']` gives the
  dependency closure (used by the degradation analysis, §8).

### 3.3 Style & labels

- `style.resolver.resolve(scene, elem, key)` — the same resolver SVG/TikZ use →
  one `style_map` produces JSXGraph attributes.
- `labels.resolve_label_text(scene, elem)` — LaTeX label text (for MathJax).
- Coordinates are **math units**: JSXGraph works directly in MU with a
  `boundingbox`, so no px conversions for geometry (only for style sizes).

---

## 4. Architecture (`animageo/exporters/jsxgraph/`)

Mirrors `exporters/tikz/` but graph-oriented:

| Module | Role |
|--------|------|
| `options.py` | `JSXGraphOptions`: `boundingbox` (from `_get_scene_bounds`), `keepaspectratio`, `shownavigation`, `axis`, `output ∈ {html, js, json}`, `mathjax`, `cdn`/`offline`, `fallback` policy. |
| `context.py` | resolver wiring + **name sanitiser** (element name → valid JS id, with a map) + JS-literal formatting. |
| `style_map.py` | resolved style → JSXGraph attribute dict (`strokeColor`, `fillColor`, `strokeWidth`, `dash`, `size`, `face`, `fillOpacity`, `strokeOpacity`, `withLabel`, `name`). |
| `command_map.py` | **the crux** — `Command → board.create(type, [parents], attrs)`; one entry per supported base command, keyed by `command.name` (+ input-type discrimination where needed). |
| `builder.py` | walk independents → input widgets; walk `commands` in order → `command_map` (or fallback); attach style + labels per output element; record coverage. |
| `document.py` | assemble `json` (board spec), `js` (`initBoard` fragment), or `html` (full page + CDN JSXGraph/MathJax). |
| `exporter.py` | orchestration + coverage report (logged like parser's unsupported-command diagnostics). |

Public API: `scene.exportJSXGraph(filepath=None, *, options=None, **kwargs)`.

---

## 5. The `command_map` — coverage analysis

The registry has **367 dispatch entries → 87 base command names**. Categorised
for JSXGraph (exact creator names to be confirmed against the JSXGraph
reference during the Phase 0 spike):

### Tier A — native JSXGraph constructors, **live** (Phase 1 core)
`point`, `midpoint`, `segment`, `ray`, `line` (incl. parallel `Line(pt, line)` →
`parallel`), `vector` (→ `arrow`), `polygon`, `circle`, `semicircle`,
`arc`/`circle_arc`/`circular_arc`/`circumcircle_arc`/`circumcircular_arc`,
`circle_sector`/`circular_sector`/`circumcircle_sector` (→ `sector`),
`intersect` (→ `intersection`, with branch index — see §5.1),
`perpendicular_line`/`orthogonal_line` (→ `perpendicular`),
`perpendicular_bisector`/`line_bisector` (compose: `perpendicular` at
`midpoint`), `angular_bisector` (→ `bisector`), `angle`/`angle_size` (→ `angle`),
`tangent`, `reflect`/`mirror` (→ `reflection`/`mirrorelement`), `rotate`
(→ `rotation`), `translate` (→ `translation`), `centroid` (compose: point from
averaged parents).

### Tier B — native JSXGraph, **live**, Phase 2
`conic`, `ellipse`, `hyperbola`, `parabola` (→ `ellipse`/`hyperbola`/`parabola`/
`conic`), `function` (→ `functiongraph`), `implicit_curve` (→ `implicitcurve`),
`locus` (→ `locus`), `incircle`/circumcircle constructors (→ `incircle`/
`circumcircle`), `polar` (→ `polarline`), conic-property points:
`center`, `focus`, `vertex`, `directrix`, `axes`, `major_axis`, `minor_axis`.

### Tier V — numeric / derived values
`add`, `sub`, `mult`, `div`, `pow`, `abs`, `sqrt`, `sin`, `cos`, `tan`, `ctan`,
`value`, `assign`, `equality`, `distance`, `length`, `area`, `perimeter`,
`circumference`, `radius`, `eccentricity`, `linear_eccentricity`,
`semi_major_axis_length`, `semi_minor_axis_length`, `coefficients`, `u_sub`,
`cpx_to`.
- **Phase 1:** emit as **static** values (computed once in Python).
- **Phase 3 (live):** emit as JS **function expressions** referencing parent
  values, so they recompute on drag (JSXGraph supports function-valued
  coordinates/attributes). Requires a small expression→JS translator.

### Tier C — no JSXGraph analog → **static fallback** / non-geometric
`isogonal_conjugation`, `prove`, the `are_*` predicates (`are_collinear`,
`are_concurrent`, `are_concyclic`, `are_congruent`, `are_equal`, `are_parallel`,
`are_perpendicular`, `are_complementary`), `contained_by`, `touches`.
- Predicates → boolean → `checkbox`/`text` (static value, Phase 2+).
- The rest → static geometry (frozen coords) per the degradation policy (§8).

### 5.1 Fidelity caveats (must document in output)
- **Intersection branch/index**: JSXGraph `intersection(a, b, i)` indexes the
  two solutions; our index convention may differ. Pass the index and seed from
  our computed `coords`; document possible branch swaps.
- **Glider parametrisation** differs from our `tparam` (JSXGraph stores a
  position, not an angle) → seed with current coordinates, not the raw tparam.
- **Numerical divergence**: live (Tier A/B) elements recompute in JS and should
  match; static (Tier V/C) elements do **not** move on drag.

---

## 6. Styling, labels, coordinates

- **Styling**: `style_map` reads the resolver → JSXGraph attrs. Point shapes →
  `face` (`o`/`[]`/`^`/`x`/`+`); dashes → `dash`; opacities → `fillOpacity`/
  `strokeOpacity`. Sizes that are pixel-based (point size, stroke width) map
  directly (JSXGraph sizes are pixels) — *simpler than SVG/TikZ*, no MU
  conversion.
- **Labels**: `name` + `withLabel:true`; LaTeX from `resolve_label_text` with
  the board's `useMathJax:true`. A plain-text mode drops MathJax for lighter
  output (open question §12).
- **Coordinates**: geometry emitted in MU; board `boundingbox` from
  `_get_scene_bounds`. `keepaspectratio:true` to match the rendered aspect.

---

## 7. Output modes

1. **`html`** — a self-contained page: CDN `<script>` for JSXGraph (+ MathJax),
   a `<div id="box">`, and the `initBoard` script. Open & share immediately.
2. **`js`** — just the `JXG.JSXGraph.initBoard(...)` + `create(...)` fragment,
   to drop into an existing page/bundle.
3. **`json`** — a board spec (elements + attrs + parent refs) for programmatic
   reconstruction; also the basis for the **Moodle JSXGraph filter** format.

(Priority among these is open question §12.)

---

## 8. Graceful degradation + coverage report (mandatory)

For every command:
- **supported** (Tier A/B, or Tier V live in Phase 3) → emit the live creator;
- **unsupported** in the current phase → emit the output element(s) as **static
  geometry** (Python-computed fixed coords) and record it.

If a static element's ancestor closure (`state[...]['outputs']`) contains a
draggable independent, it **won't track drags** — record that explicitly.

At export, emit a **coverage report** (same spirit as the parser's
unsupported-command diagnostics): `N live, M static`, listing each static
element and why. This sets correct expectations and guides which commands to
implement next.

---

## 9. Phasing

### Phase 0 — spike (½–1 day)
One hand-written board from a 3-command construction (A, B free; `M=Midpoint`;
`c=Circle(A,B)`; `P=Intersect(...)`). Goals: confirm the unit/boundingbox model,
that gliders/sliders drag, MathJax labels render, and the HTML scaffold works.
De-risks the architecture before building the generic pipeline.

### Phase 1 — core interactive export (~3–5 days)
- subpackage scaffold (`options/context/style_map/command_map/builder/document/
  exporter`);
- independents → point/glider/slider/checkbox;
- Tier A `command_map`;
- `style_map` + MathJax labels;
- one output mode (per §12 decision);
- coverage report + static fallback for everything else;
- `scene.exportJSXGraph(...)` + CLI `-o foo.html` / `--format jsxgraph`.

### Phase 2 — conics, functions, properties (~incremental)
Tier B commands; conic-property points; `incircle`/`circumcircle`/`polar`;
remaining output modes (`json`/`js`, Moodle).

### Phase 3 — live values, animation, embedding polish
- Tier V as live JS function expressions (expression→JS translator);
- keyframes → JSXGraph slider animation (`board` animation / `setAnimation`);
- offline/vendored assets; Moodle packaging.

---

## 10. Testing strategy

- **Unit** (no browser): build a small DSL construction, export `js`/`json`,
  assert the emitted `create(...)` calls, parent references, attrs and the
  independents→widget mapping (string/structural checks, like the TikZ tests).
- **Coverage report**: a scene with an unsupported command → element flagged
  static, warning logged.
- **Output modes**: valid JSON; HTML contains `initBoard` + CDN tags.
- **Optional CI**: headless eval via `node` + `jsdom` to instantiate the board
  and assert element count / no JS errors (guarded; only if added to CI).

---

## 11. Risks

- **`command_map` completeness** — the main scope risk; mitigated by phasing +
  static fallback + coverage report.
- **Constraint/branch fidelity** — intersection index, glider seeding (§5.1).
- **JSXGraph API drift** — pin a CDN version; confirm creator names in Phase 0.
- **Two engines, two results** — live elements recompute in JS; static ones
  don't. The coverage report makes this explicit rather than silent.

---

## 12. Decisions (resolved — locks Phase 1)

1. **Output mode** → **Self-contained HTML** first. One `.html` with CDN
   JSXGraph + MathJax and a ready `initBoard`. `js`/`json`/Moodle deferred to
   Phase 2. ⇒ `JSXGraphOptions.output` defaults to `"html"`.
2. **Phase 1 command scope** → **school/competition core (~30)** = Tier A
   (§5). Conics/functions (Tier B) and live numeric values (Tier V) deferred to
   Phase 2/3.
3. **Degradation policy** → **static element + coverage report**. Unsupported
   commands emit frozen Python-computed geometry; the report lists each static
   element and flags those whose ancestors include a draggable input (won't
   track drags). No input is frozen; nothing is silently skipped.
   ⇒ `JSXGraphOptions.fallback = "static"`.
4. **Labels & assets** → **MathJax + CDN**. LaTeX-faithful labels via the
   board's `useMathJax:true`, JSXGraph + MathJax from CDN (pin a version).
   Plain-text and offline/vendored modes are later options.
   ⇒ `JSXGraphOptions.mathjax = True`, `cdn = True`.

These four decisions make **Phase 1** concrete: a self-contained interactive
HTML page covering the ~30 core constructors, MathJax labels from CDN, static
fallback + a coverage report for everything else. Phase 0 (the spike) is the
immediate next step.
