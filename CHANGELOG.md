# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] — 2026-07-04

### Added

- **First-class GeoGebra text objects across the whole pipeline** — parse,
  render (SVG/MP4), and export (TikZ, JSXGraph). Supports static text, LaTeX
  text, and dynamic text that resolves live values (`Point → (x, y)`,
  `Polygon → area`, `Segment → length`, numbers/angles/booleans with
  trailing-zero stripping). Previously LaTeX text was dropped and plain text
  was unrenderable.
  - `Text` element with position/anchor and `is_latex`; manim-free value
    formatting shared by the renderer and exporters.
  - GGB parser splits string-literal expressions into literal/object segments,
    with `<startPoint>` anchoring, `<isLaTeX>`, `<font>`, and kernel decimals.
  - `_render_text` (top-left anchor, live dynamic resolution), TikZ `\node`,
    and a JSXGraph text creator + `animageo-board/v1` spec element.

## [1.4.6] — 2026-07-04

### Changed

- Updated the packaged AI usage guide with stronger autonomous-animation
  defaults: prefer native AnimaGeo marks over manual Manim overlays, reveal
  polygons as single drawable objects when that is the intended construction,
  enable automatic label placement for labeled staged animations, and verify
  label placement before the first motion frame.

### Fixed

- **`autoPlaceLabels(dynamic=True)` now synchronizes labels during visibility
  transitions.** `Show`/`playShow`, `Hide`/`playHide`, and
  `setVisible(update=True)` recompute the current visible label layout and seed
  the dynamic tracker before the next mobject/render frame, so staged labels
  appear in solved positions immediately instead of correcting only when the
  first `addUpdater`/`updateVar` animation starts.
- **Indexed conic intersections now use GeoGebra-style known-point ordering.**
  `Intersect(conic, line, 2)` and related indexed conic intersections now share
  the same known-point ordering contract previously applied to circle
  intersections, avoiding selection of the already-known point when GeoGebra's
  second intersection is requested.

## [1.4.5] — 2026-07-03

### Added

- **AI agent usage guide shipped in the package** (`animageo/AI_USAGE_PROMPT.md`,
  rewritten as a self-sufficient reference). Written for an AI agent with zero
  prior knowledge of animageo: environment setup, canonical static-SVG and
  MP4-animation script skeletons, the two-pass `fit_view` viewport recipe for
  DSL-built scenes, verified DSL factory signatures, construction-correctness
  rules, marks/labels/value-labels, style JSON, staged reveal + animated
  variables + keyframes, a visual verification protocol, and a troubleshooting
  table. Validated end-to-end by independent context-free AI agents (six
  scenarios: nine-point circle animation, incircle figure, parabola definition
  animation, tangents from external point, parallelogram diagonals, inscribed
  angle theorem). The wheel now includes `animageo/*.md` (MANIFEST.in +
  package-data).
- `animageo --ai-guide` / `python -m animageo --ai-guide` — print the packaged
  AI usage guide and exit (no `.ggb` argument needed); README gained an
  "AI agent usage" section pointing agents at it.
- **`AnimaGeoScene.fitView(width, height, *, padding=40, style=None,
  passes=2)`** — canonical framing for DSL-built scenes (which have no
  meaningful default viewport). Measures the rendered bounds of the visible
  elements and configures the reference→content→export layout so the content
  fills the canvas with a uniform pixel margin; runs two
  `applyStyle(content='rendered_bounds')` + `updateAllGeometry()` passes (the
  first fixes the pixel-style scale, the second re-measures with correctly
  sized points/labels). Keeps the scene's current style when `style=` is
  omitted. Replaces the hand-rolled double-`applyStyle` recipe from the AI
  guide.

### Fixed

- **`Point(Polygon)` is now imported instead of dropped.** A GeoGebra point
  constrained to a polygon boundary had no dispatch (`point_P` was missing), so
  the point built as `None`, cascaded every dependent segment to
  `depends_on_unsupported`, and recorded a spurious `unsupported_signature`
  diagnostic (a hard failure under `--strict`). Added the `point_P` creator and
  taught the parser to recognise `Polygon` as a point host: the point is now
  materialised at its serialized coordinates (a fixed point — no perimeter
  `tparam` yet) so it renders and unblocks its segments. Also fixed a latent
  bug where the parser's point-element handler appended a duplicate `Element`
  instead of overwriting an already-created output.
- **Transparent GeoGebra arcs/sectors (`type="conicpart"`) no longer render
  filled.** `conicpart` was missing from the fill-import type list, so a
  `CircleArc` with `<objColor alpha="0">` never wrote `fill_opacity` into
  `ggb_style`; the resolver then fell back to the builtin `arc` default
  (`fill_opacity = 1`) and drew an opaque fill. `conicpart` is now honoured in
  both import paths (`ggb_parser` and `ggb_resolver`), so the arc's real alpha
  wins.
- `applyStyle(reference={'size': [w, h]})` — the documented list/tuple form of
  the reference size was silently ignored (only the
  `{'width': ..., 'height': ...}` dict form worked), so pixel styles resolved
  against a degenerate `ptUnit_style` and DSL-only scenes rendered with giant
  points/labels. Both forms now behave identically.
- Style validation no longer warns about underscore-prefixed top-level keys
  (`_comment` etc. are comments by convention — the shipped `builtin.json`
  itself uses one), and `applyStyle` logs a dict style's `name` instead of
  dumping the whole style dict into the INFO log.

## [1.4.4] — 2026-07-03

### Added

- **Points on conics, loci and function graphs are now fully animatable in
  keyframes.** A `tparam_point` on an ellipse/hyperbola/parabola/circle-as-conic,
  a locus, or a function graph can be driven through `play_keyframes` the same
  way circle/segment/line points already were. `get_independents()` reports the
  path type in the new `constraint` field (`circle`/`segment`/`ray`/`line`/
  `ellipse`/`hyperbola`/`parabola`/`locus`/`function`); ellipse and circle
  interpolate cyclically with 2π wrap (shortest arc), hyperbola carries a
  `(branch, t)` pair (branch snaps at t=0.5), everything else is linear.
- **Keyframe values for `tparam_point`s may be plain `[x, y]` coordinates** in
  addition to `{"tparam": ...}` — the library projects them onto the point's
  path via the new public API `Construction.tparam_from_coords(name, coords)`.
- `animageo/geo/tparam.py`: new module unifying point↔path-parameter math
  (`tparam_from_point_and_path` dispatcher, `get_tparam_from_point_and_function`
  for function graphs); the classic circle/line/segment/conic/locus helpers
  moved here from `ggb_parser`, which now re-exports them for compatibility.
- `point_F` command — a point constrained to a function graph; GGB `Point[f]`
  now imports with a `tparam`.

### Changed

- **Locus point parameter now uses nearest-segment projection** (with
  fractional position along the segment), matching GeoGebra's
  `GeoLocus.pointChanged` semantics, instead of snapping to the nearest sampled
  vertex.

### Fixed

- **RecursionError after ~1000 renders in one process (labels and points
  silently vanishing).** `applyStyle` (via `setStyle`) called
  `Text/MathTex/MarkupText.set_default(color=…)` on every invocation; manim's
  `set_default` wraps the
  current `__init__` in a new `functools.partialmethod` each time (nested
  partialmethods never flatten because the class attribute read returns the
  descriptor's compiled `_method` function), so the chain grew by one layer
  per render. Once it exceeded `sys.getrecursionlimit()`, every label
  construction raised `RecursionError`: per-element error recovery silently
  dropped points and labels, `autoPlaceLabels` crashed on Tex bbox
  measurement, and DecimalNumber-backed value labels failed too. The
  `set_default` calls are removed: the label render path always passes its
  colour explicitly (`col_label`), and `ShowText` now receives explicit
  colours too. `setStyle` no longer mutates any global manim class state,
  which also makes concurrent renders in threads safe from racing on
  `MathTex.__init__`.
- **Cyclic GGB macros no longer crash `loadGGB` with RecursionError.**
  `expand_macros_in_construction` recursed once per expansion pass with no
  bound, so a `geogebra_macro.xml` whose macro body calls itself (directly
  or mutually) blew the stack after ~1000 passes. Expansion now stops after
  32 passes with a warning; the unexpanded calls surface through the
  existing unsupported-command diagnostics.
- **RecursionError render failures now log a root-cause hint.** A
  `RecursionError` caught by the per-element recovery in `CreateMObject` is
  process-wide state corruption, not an element defect; the warning now says
  so instead of reading like a per-element failure.

## [1.4.3] — 2026-06-30

### Fixed

- **Angle markers are now obstacles for automatic label placement.** A vertex
  point's label could be placed in the sector occupied by its angle marker (a
  right-angle square or arc), leaving the marker between the label and its
  point. The new opt-in `overlay.label_placement.angle_marker_obstacle` flag
  (default `false` → byte-identical GGB import) registers the *real* drawn
  marker at its rendered pixel radius as an obstacle (mirroring `_render_angle`
  via `_angle_drawn_sector` / `_angle_marker_obstacle_segments`, replacing the
  legacy coarse `0.3·min(arm)` arc) and excludes the marked wedge from the
  point-label direction resolvers (`_bisector_of_largest_gap`,
  `_bisector_of_gap_nearest`), so a GGB offset hint can no longer pin a label
  onto the marker. Enabled in the recommended label-placement preset.

## [1.4.2] — 2026-06-27

### Fixed

- **Stable Manim layer order during MP4 animation.** Equal z-index tiers now get
  a tiny construction-order tie-breaker before being passed to Manim. This keeps
  polygon stroke overlays and ordinary segments in the same relative order after
  `Polygon` objects are recreated via remove/add during `updateGeoElements()`.

### Documentation

- Documented the z-index tie-breaker and the `Polygon` remove/add layer-order
  contract in the style guide and gotchas.

## [1.4.1] — 2026-06-27

### Fixed

- **GeoGebra-style ordering for multi-output intersections.** Multi-output
  `Intersect(circle, ...)` now uses the same already-known-point ordering as
  indexed `Intersect(..., index=1/2)`, so `.ggb` imports keep GeoGebra's output
  label mapping when one intersection coincides with a point used to construct
  the input objects. This fixes dependent constructions such as circles through
  a named second intersection being built through the wrong point.

### Documentation

- Documented the public intersection-ordering contract: tuple-unpack order,
  indexed `Intersect(..., index=N)`, `.ggb` import, and export/JSXGraph paths
  must agree; `index` remains 1-based.

## [1.4.0] — 2026-06-23

### Added

- **Comprehensive automatic label placement** (`autoPlaceLabels()` /
  `compute_label_layout` / `apply_label_layout`). A deterministic greedy solver
  with continuous (non-octant) direction search, then a sequence of opt-in
  refinement passes, all configured under `overlay.label_placement`. Every flag
  defaults OFF so a bare GGB import stays byte-identical; enable the documented
  **recommended preset** (see `docs/styles.md`) for the validated layout. Key
  mechanisms:
  - **Visual-glyph-box reasoning** — a vertex label's sector is chosen from where
    its text actually renders (anchor corner + descender), not the raw offset
    vector, so it keeps the user's original part of the angle.
  - **Compaction + association (`compact_labels`, `overlap_tol_px`)** — pulls a
    label that overshot a dense node back next to its point, accepting a small
    clip of a SOLID line *incident to its own point* rather than a far
    displacement; never moves it past the Voronoi midpoint to another point
    (no false attachment). Dashed lines/circles and angle markers stay hard.
  - **Solid-circle rescue** — a label stuck on a solid circle is moved to the
    nearest clear spot (e.g. radially outward).
  - **Anti-hug** — a label clinging to a line in a *sparse* spot is nudged out
    for clearance, bounded by a small cap and the association limit.
  - **Point-on-circle radial placement** — a point on a solid circle takes the
    symmetric radially-outward direction.
  - **Region-aware cluster consistency** — a collinear row/column of free points
    aligns to one side, with blocked members nudged out so the run reads uniform.
  - **Contrast-aware label colour**, **viewport clamp**, **declutter**,
    **dashed-vs-solid overlap weighting**, and **per-frame / keyframe dynamic
    trackers** (EMA + anchor hysteresis) for animation.
  - Obstacles are culled to each label's reach, keeping dense scenes fast.
- **Leader lines (P2-A, opt-in, `label_overflow: "leader"`)** — a genuinely
  stuck POINT label is displaced to a free spot with a thin connector, rendered
  in SVG/manim, TikZ and the eval-free JSXGraph spec. Default `"overplot"` (off).
- **Label-name canonicalization** — primed names (`U'''`) recovered from the GGB
  `name_mapping` for display.

### Notes

- The auto-placement passes are static-layout only and do not change default
  (un-`enabled`) GGB import. Known limit: two *equal adjacent* angles still get
  ambiguous value labels (both show the same measure).

## [1.3.4] — 2026-06-19

### Fixed

- **`content.padding` is now a uniform canvas-edge margin**, not a source-crop
  inset. It previously expanded the `rendered_bounds` source view (an inward
  crop margin that scaled the whole figure in source px and did nothing for
  other sources). Now it fits the content into the export canvas reduced by
  `padding` on every side and insets it by `padding` — an exact margin in
  output pixels, applied at the reference→export stage for all content sources.
  `rendered_bounds` crops tight again. Used by the web "Отступ от краёв" control.

## [1.3.3] — 2026-06-18

### Fixed

- **Angle labels no longer fly far off very small angles.** The narrow-angle
  clearance in `compute_angle_label_center` pushed the label out by
  `clearance / sin(half_angle)`, which blows up as the angle → 0 — so a
  value-label on a shrinking angle (e.g. during an animation) drifted far from
  the marker. The push is now capped at `base_dist * 2.5`
  (`ANGLE_LABEL_NARROW_MAX_FACTOR`), keeping the label a reasonable distance
  from the vertex (it may then slightly overlap the near-parallel sides, which
  is preferable to flying away). Wide angles are unchanged.

## [1.3.2] — 2026-06-18

### Fixed

- **Right-angle labels no longer drift away from their marker during
  auto-placement.** `compute_label_layout` targeted a right angle's label at the
  non-right arc radius (`arc_size_px`), while the square right-angle marker is
  sized from `right_angle_size_px`. When those differed (or auto-radius enlarged
  the arc), the label floated out to the phantom arc distance, detached from the
  smaller square. The label target now follows the actual square marker's outer
  corner (`right_angle_size_px`). No change when
  `right_angle_size_px == arc_size_px`.

### Added

- **`fill: "stroke"` — fill follows the element's own outline colour.** The style
  resolver now treats the literal fill value `"stroke"` as "use this element's
  resolved stroke colour", so a shape can be filled with a translucent tint of its
  own border (opacity set separately) rather than a fixed palette slot — e.g. a
  blue-outlined polygon gets a blue wash, not a reddish `accent_light`. Resolved
  centrally in the style resolver, so the manim renderer and the TikZ/JSXGraph
  exporters stay consistent. Explicit/literal fill colours are unaffected.

## [1.3.1] — 2026-06-13

### Fixed

- **`rendered_bounds` no longer clips auto-placed edge/corner labels.** When
  `content.source="rendered_bounds"` (the tight fit-to-content crop) was combined
  with label auto-placement (`overlay.label_placement.enabled`), labels of points
  at the extreme edges of the figure were clipped off the export canvas. The crop
  was measured inside `applyStyle` *before* `autoPlaceLabels()` shifted labels
  outward, so the frozen canvas had no room for them. `applyStyle` now re-fits the
  rendered-bounds crop *after* placement (a second measurement pass that picks up
  the placed offsets), so the canvas always contains the labels. Other content
  sources (`ggb_view`, `source_view`) and placement-disabled styles are unchanged.
  See `docs/archive/fix-rendered-bounds-label-clipping.md`.

## [1.3.0] — 2026-06-01

### Added

- **Fast value labels (DecimalNumber-backed).** Labels that display a changing
  numeric value (`label_mode` `value`/`label_value`: angle measure, segment
  length, vector norm, circle radius, polygon area, measure) now animate via a
  new `ui.ValueLabel` (manim `DecimalNumber` with cached digit glyphs) instead
  of recompiling a `Tex` every frame — ~80× faster per value label (~130–280 ms
  of LaTeX per frame → ~2 ms). `labels.resolve_label_spec()` exposes the
  structured prefix/value/suffix; `ValueLabel` is also exported from the package
  for hand-built live read-outs. Static SVG/PDF/TikZ export keeps the `Tex` path
  (trailing-zero stripping, byte-identical output); the fast path engages only
  while animating (`play_keyframes`, `addUpdater`/`animating`). Master switch
  `rendering.fast_value_labels` (default `true`).
- **Framework-agnostic web integration** for controllable, movable geometry
  figures — embeddable in any web project (React/Vue/Svelte/vanilla/no-build),
  not just a standalone HTML page.
  - **Declarative board spec** `exportJSXGraph(output="spec")` →
    `animageo-board/v1`: eval-free structured JSON (elements with semantic kind +
    engine render-instruction + structured parents; an interactive-input schema;
    coverage). No JS strings. JSON Schema shipped in the wheel at
    `animageo/exporters/jsxgraph/board.schema.json` and loadable via
    `animageo.exporters.jsxgraph.load_schema()`; real exports are validated
    against it in the test suite. CLI: `-o board.json --format jsxgraph`.
  - `Construction.get_independents()` now surfaces optional slider `min`/`max`/
    `step` (from a var's style), feeding the spec's input schema.
  - **`web/runtime`** (`@animageo/runtime`): headless `createBoard(spec,
    container, opts) -> BoardHandle` with construction-relative **signals**
    (`ready`/`change`/`commit`/`viewchange`/`error`) and **actions**
    (`getState`/`setState`/`setValue`/`reset`/…). JSXGraph is injected (peer
    dep); no globals; multi-instance safe.
  - **`web/web-component`** (`<animageo-board>`): the zero-framework primitive —
    signals as `CustomEvent`s, actions as element methods.
  - **`web/adapters/`**: thin React / Vue / Svelte / vanilla templates.
  - Tests: `tests/test_jsxgraph_spec.py` (Python) + `node --test` in each web
    package, including a cross-language contract test against real exported specs.
  - Design: `docs/archive/jsxgraph_web_integration_audit.md`,
    `docs/archive/jsxgraph_web_integration_plan.md`.
  - Verified end-to-end with a real headless-Chrome smoke against live JSXGraph
    (`web/runtime/scripts/browser-smoke/run.mjs`): a real exported spec builds,
    `setState` moves a point, `change`/`commit` fire on real drag events, and the
    SVG renders.

- **TikZ export** (`scene.exportTikZ(...)`): comprehensive, semantic TikZ output
  for inclusion in LaTeX documents — the TikZ counterpart of `exportSVG`. Emits
  native primitives (`\draw circle`/`ellipse`/`(a)--(b)`/`arc`/`[->]`), real
  LaTeX `\node` labels, and `\draw plot coordinates` for sampled curves
  (parabola/hyperbola/function/implicit/locus). All drawable types are covered,
  reading the same style resolver as the renderer (GGB import → overlay →
  explicit `elem.style`): colours (interned into `\definecolor`), opacities,
  dash patterns, line caps, tick marks, angle-arc auto-sizing, point shapes and
  z-order. Coordinates are math units; the picture's `x=/y=` unit reproduces the
  SVG physical size while markers/widths/fonts use absolute `pt`.
  - Snippet output by default (for `\input{}`); `standalone=True` wraps a
    compilable `\documentclass{standalone}` document with a Cyrillic-ready
    preamble.
  - CLI: `-o foo.tex` (format inferred), `--format tikz`, `--standalone`.
  - New package `animageo/exporters/tikz/`; docs in `docs/tikz_export.md`.
  - Verified end-to-end: every drawable type and every `TikZOptions` setting are
    covered in `tests/test_tikz_export.py`, including `pdflatex` compile smoke
    tests (skipped when no LaTeX toolchain is available).

- **PDF / EPS export** (`scene.exportPDF(...)`, `scene.exportEPS(...)`): vector
  output on the existing Cairo path (the same mobject walk as `exportSVG`).
  `dpi` (default 96, matching the TikZ exporter) controls the physical page
  size; the figure stays vector and rescales via `\includegraphics[width=...]`.
  EPS warns once when the scene has semi-transparent fills/strokes (EPS has no
  transparency — cairo flattens them; PDF/SVG preserve opacity).
  - CLI: `-o foo.pdf` / `-o foo.eps` (format inferred) or `--format pdf|eps`,
    with `--dpi`.
  - Internals: `parsers/svg_parser._get_cairo_context(surface=…, dpi=…)` now
    builds SVG/PDF/PS/EPS cairo surfaces; `exportSVG/PDF/EPS` share
    `_export_cairo`. Tests in `tests/test_pdf_eps_export.py`.

- **Animation containers GIF / WebM / MOV** (in addition to MP4) via the manim
  renderer. `animageo.configure_render(format=…, fps=…, transparent=…)` selects
  the container before a render.
  - CLI render track: `--format png|gif|mp4|webm|mov` (inferred from `-o`),
    `--keyframes file.json` to animate, plus `--fps` / `--transparent` /
    `--quality {l,m,h,p,k}`. The produced file is moved to the requested `-o`
    path.
  - CLI now propagates `PYTHONPATH` to the `manim` subprocess so the generated
    driver imports `animageo` when running from a source checkout (not only when
    pip-installed). Tests in `tests/test_render_config.py`,
    `tests/test_cli_main.py`.

- **Interactive JSXGraph export (Phase 1)** (`scene.exportJSXGraph(...)`): a
  live, draggable construction in the browser. Unlike the SVG/PDF/TikZ
  exporters, which serialise a rendered frame, this *transpiles the construction
  graph*: free points → draggable points, points-on-curves → gliders, numbers →
  sliders, booleans → checkboxes, and derived elements are created in terms of
  their parents so JSXGraph recomputes them live on drag.
  - Live creators: midpoint/center, segment, line (+parallel), ray, vector,
    circle (center+point / +radius / +slider-driven radius), semicircle,
    **polygon** (named edges bound to `poly.borders[i]`, so the shape and
    everything built on its edges tracks drags), perpendicular,
    perpendicular-bisector (composite), angular bisector, angle, **ellipse /
    hyperbola / parabola / conic (5-point)**, reflection/mirror, and
    intersection (indexed; *smart* — live only when both parents are line/conic
    objects, otherwise placed at the computed coordinates).
  - Everything else is **drawn statically**: functions, implicit curves,
    conics-by-expression, arcs, sectors and loci are sampled into JSXGraph
    `curve` elements (level-0 directly-defined curves are emitted before their
    dependents). Only genuinely-empty (`None`) outputs are skipped; a
    **coverage report** lists live vs static (logged at INFO).
  - Verified in a real browser (headless Chrome) on `ex_general.ggb`
    (17 live / 0 static) and `func5.ggb` (conics/functions/implicit all drawn):
    renders, MathJax labels typeset, no JS errors, dragging a free point
    recomputes dependents live.
  - Live **transforms**: `rotate` / `translate` of points and of segments /
    lines / circles / vectors / polygons via a JSXGraph `transform` object
    (dragging the source moves the image). Live **Tier-V numeric values**: a
    derived number feeding a creator — e.g. `Circle(M, Distance(A,B))` — becomes
    a live JS function (`distance`/`length`/`radius` +
    `add/sub/mult/div/pow/abs/sqrt/sin/cos/tan`). `tangent`-from-a-point is
    drawn statically (single-output / branch-ambiguity — see the plan doc).
  - Output flavours: `html` (default), `js`, `json`, and `moodle`
    (`<jsxgraph>` block for the filter_jsxgraph plugin, best-effort).
  - Output `html` (self-contained, default — CDN JSXGraph `1.10.1` + MathJax 3
    labels), `js` (board fragment), or `json` (board spec).
  - CLI: `-o foo.html` (format inferred) or `--format jsxgraph`.
  - **Visibility fidelity:** hidden elements are emitted with `visible: false`
    (kept in the board so visible dependents still recompute on drag) instead
    of being drawn — mirrors a hidden GeoGebra object still participating in the
    construction.
  - **Angle orientation fidelity:** a 3-point `Angle` now honours GeoGebra's
    reflex/non-reflex setting by emitting the dedicated `reflexangle` /
    `nonreflexangle` element (keyed off the resolved `angle_range`, same as the
    SVG renderer) instead of the plain `angle`, which always sweeps CCW
    `p1`→`p3` and so could draw the wrong side of the plane.
  - **Board chrome from the scene:** background colour, axes and grid
    show/hide, per-axis visibility, and axes/grid colours are now imported from
    the GeoGebra view (`bgColor` / `showAxes` / `showGrid` / `axesColor` /
    `gridColor`) instead of being hard-coded. `JSXGraphOptions.axis` / `grid`
    default to `None` (mirror the scene; GeoGebra defaults — axes on, grid off —
    when the scene is silent) and accept an explicit `True`/`False` override;
    `background` defaults to the scene colour, takes a CSS override, or `""` to
    let the page show through. Also imported (mirroring the SVG renderer):
    grid boldness (`gridIsBold` → grid stroke width), grid spacing
    (`gridDistX/Y` → `majorStep`), per-axis tick numbering (`showNumbers` →
    `drawLabels`) and tick spacing (`tickDistance` → `ticksDistance`), and the
    x/y unit scale → `keepaspectratio` (equal scales keep circles round;
    unequal scales reproduce GeoGebra's distortion; `JSXGraphOptions.keepaspectratio`
    is now `Optional` and overrides). GeoGebra polar/isometric grids have no
    JSXGraph equivalent and fall back to a rectangular grid (logged).
  - **Element size fidelity:** angle arcs carry GeoGebra's `arcSize` over to the
    JSXGraph angle `radius` (px → user units), and a deliberate `labelOffset` is
    emitted as the JSXGraph label `offset` (near-zero offsets keep JSXGraph's
    own sensible default). Stroke/fill colour, width, opacity, dash, point
    size/shape and label colour already route through the shared style resolver.
  - New package `animageo/exporters/jsxgraph/`; deep-dive plan in
    `docs/archive/jsxgraph_export_plan.md`; tests in `tests/test_jsxgraph_export.py`.

### Changed

- **Manim 0.20.1** is now the minimum supported renderer (`manim>=0.20.1,<0.22`).
- JSXGraph export: dash patterns now map to JSXGraph dash indices by the
  dash/line-width ratio (dotted → 1, dashes → 3, loose dashes → 4), mirroring
  the TikZ exporter's thresholds, instead of collapsing every dash to one style.
- JSXGraph export: the resolved z-index maps to a JSXGraph `layer` so the live
  widget stacks like the SVG/PNG renderer (fills below angles below lines below
  strokes below points), instead of relying on JSXGraph's per-type defaults.
- JSXGraph export: an explicit 9-point label anchor (from GGB import or the
  `label_placement` solver) now maps to JSXGraph `label.anchorX`/`anchorY`, so a
  label offset is applied relative to the same corner the renderer uses (most
  visibly fixes solver-placed and angle labels) instead of JSXGraph's default
  anchor.
- JSXGraph export: angle arc radius now mirrors the renderer — the resolved
  `arc_size_px` run through `compute_effective_arc_size_px` (multi-arc expansion
  for `tick_count > 1`, plus `overlay.angle_radius` auto-scaling when enabled),
  instead of the raw base radius. Byte-for-byte unchanged when `angle_radius` is
  off (the default) and `tick_count` is 1.
- JSXGraph export: **decorations now carried** — vectors get a native, live
  arrowhead sized from the resolved GGB `arrow_length_px`/`stroke_width_px`
  (`lastArrow`), and segments with `tick_count > 0` get **live congruence tick
  marks**: short perpendicular dashes at the midpoint, built from
  function-valued anchor points tied to the segment's parents (so they track
  drags — no frozen geometry). Mirrors the renderer/TikZ geometry
  (`tick_length_px`/`tick_shift_px`). None emitted when `tick_count` is unset.
  Verified on live JSXGraph (headless Chrome) incl. the GGB congruence marks in
  `ex_general.ggb`.
- JSXGraph spec: now carries `ptUnitGgb` / `ptUnitExport` (the GGB authoring and
  export px-per-unit). A live board rendering the bounding box at a different
  scale can rescale label offsets (`offset / ptUnitGgb`) and reproduce the
  absolute pixel size of pixel-sized decorations. Schema updated accordingly.
- JSXGraph export: segment congruence ticks now keep a **fixed pixel length
  under zoom** — the tick coordinate functions divide the pixel size by the
  board's live px-per-unit on every redraw (like GeoGebra), instead of baking a
  math-unit size at export time.
- JSXGraph export: closed shapes with a fill colour now always pin
  `fillOpacity` (even at 0), so a stroke-only GeoGebra circle/conic/polygon is
  not painted solid by JSXGraph's default; point `size` is kept fractional
  (no longer rounded to an int) so the point-size : line-width ratio matches the
  SVG/preview.

### Documentation

- The HTML user guide was reworked end-to-end: migrated under `docs/guide/`
  (old `docs/style_guide/` removed and links redirected), renumbered to 12
  chapters, added an outputs map and a new interactive-web chapter with a live
  board, and an expanded export/reference covering every exporter, the web spec
  and the CLI.

## [1.2.6] — 2026-05-24

### Changed

- Finalized the style/layout API cleanup around the canonical
  `style` / `reference` / `content` / `export` arguments.
- Renamed the faithful GeoGebra style mapping helper from the legacy adapter
  naming to `style.ggb_resolver.resolve_ggb_style()`.
- Style validation is now stricter: removed legacy top-level sections,
  removed visual aliases, `rendering.scale_export`, and unknown
  `import.policy` keys fail fast instead of being silently accepted.
- Overlay and label-placement documentation now describe the resolver-based
  style path directly.

### Removed

- Removed runtime compatibility shims for deprecated API arguments such as
  `style_file`, `px_size`, `reference_size`, and flat `export_*` kwargs on
  `loadGGB()` / `applyStyle()`.
- Removed the deprecated CLI `--debug` shortcut; use `--verbose` or
  `--log-level DEBUG`.
- Removed the `angle_gap_px` label-placement fallback in favor of explicit
  `angle_gap_arc_px` and `angle_gap_sides_px`.

### Tests

- Updated style/import-policy tests to assert the canonical API and removed
  legacy compatibility behavior.

## [1.2.5] — 2026-05-24

### Fixed

- GeoGebra XML parsing now accepts both the historical misspelling
  `euclidianView` and the correct `euclideanView` element emitted by current
  GeoGebra files.

## [1.2.4] — 2026-05-17

### Added

- Added a unified logging configuration helper and wired CLI verbosity flags
  through it.
- Added GeoGebra custom macro expansion before construction parsing.

### Fixed

- Unsupported command diagnostics are now summarized through structured
  logging instead of ad-hoc console output.

## [1.2.3] — 2026-05-15

### Added

- Imported GeoGebra axes/grid view settings are now preserved and can render as
  a quiet coordinate background layer.
- DSL `Intersect(...)` factories now accept `index=` as a semantic keyword for
  selecting a specific intersection.

### Changed

- `content.infinite_policy` now defaults to `ignore` for `rendered_bounds`;
  use `clip` explicitly to include `Line`/`Ray` bounds clipped by the current
  source camera.
- Style preset references now also accept short forms such as `color.main`,
  `line_width.main`, and `tick.main` where the preset group is unambiguous.
- Value-label precision now defaults to one decimal place and can be set via
  `rendering.label_value_precision`.
- Expanded API docs for the accepted `style`, `reference`, `content`, and
  `export` shapes, values, and defaults.
- Removed the PyPI `Development Status :: 5 - Production/Stable` classifier
  from package metadata.

### Fixed

- Automatic label placement now clips line/ray obstacles to the current scene
  bounds and uses exact segment/bbox clipping instead of dense sampling.

## [1.2.2] — 2026-05-09

### Added

- **Unified layout API** — `loadGGB()` and `applyStyle()` now accept
  `style`, `reference`, `content`, and `export` blocks. `style` can be a JSON
  path, raw style dict, or `StyleConfig`; `reference`, `content`, and `export`
  can be passed as dictionaries for structured runtime layout control.
- **Top-level style reference** — style JSON now uses
  `reference: {size: {width, height}, source}` as the authoring/reference
  canvas metadata.
- **Reference-to-export layout pipeline** — geometry/content placement on the
  reference canvas is separated from physical export placement, preserving
  authored visual scale while still supporting different output sizes.

### Changed

- Public examples, guide snippets, docs, style-guide generated sources, and
  bundled style JSON files now use the new `style` / `content` / `export`
  shape instead of legacy `style_file`, `px_size`, and flat `export_*` fields.
- Runtime export sizing is now expressed through
  `export={'size': {'width': ..., 'height': ...}}`; one side may still be
  `"auto"`.
- Rendered-bounds fitting is now configured as
  `content={'source': 'rendered_bounds', 'padding': ...}`.
- AI construction summaries now report viewport dimensions under
  `viewport.size` instead of `viewport.px_size`.

### Fixed

- `applyStyle(style=...)` now correctly passes the style path/dict into the
  legacy `GeoStyle` container while keeping `StyleConfig` as the canonical
  resolver source.
- Updated the guide render server and standalone style-guide example
  generator to emit runnable snippets with the new API.
- Migrated conics/functions helpers and all example style files away from
  obsolete public export/style fields.

### Tests

- Added and updated coverage for reference/export layout separation, style
  reference parsing, dict-based style loading, guide overlay examples, AI
  summary viewport metadata, label placement behavior, and migrated examples.

## [1.2.1] — 2026-05-08

### Added

- **Split export layout** — `loadGGB()` and `applyStyle()` now support
  `reference_size`, `export_size`, `export_fit`, `export_source_rect`,
  `export_scale`, `export_anchor`, `export_offset`,
  `export_bounds_padding`, and `export_infinite_policy`. This separates the
  style-authoring reference canvas from the physical SVG/MP4 canvas.
- **Rendered-bounds export source** — `export_source_rect='rendered_bounds'`
  measures visible finite geometry and labels before fitting content into the
  export canvas, with `clip`/`ignore` handling for infinite lines and rays.
- **CLI export-layout flags** — the `animageo` command now exposes
  `--reference-size`, `--export-size`, `--fit`, `--source-rect`,
  `--export-scale`, `--anchor`, `--offset`, `--bounds-padding`, and
  `--infinite-policy`.
- **Canvas reference metadata** — style JSON may now include
  `canvas.reference` for preview/export reference dimensions.

### Changed

- Visual `*_px` style values now resolve through `ptUnit_style` in split
  export-layout mode, so strokes, points, labels, tick marks, and angle arcs
  scale with the reference canvas when exporting to a larger physical size.
- `overlay.angle_radius` and `overlay.label_placement` are read directly from
  `StyleConfig`; they are no longer projected through `rendering`.
- Style import maps now require fully-qualified preset references such as
  `presets.color.main`, `presets.point_size.main`, and
  `presets.line_width.main`.

### Fixed

- **Keyframe playback initial state** — `AnimaGeoScene.play_keyframes()` now
  applies the first keyframe's values and `show`/`hide` visibility before
  playback starts, rebuilds geometry, and rerenders touched mobjects. MP4
  exports no longer show the saved `.ggb` editor state before the first
  keyframed motion begins.
- **Measure/AngleSize keyframe updates** — parsed keyframe values now update
  the real `.value` field for measure-like variables and mark dependents
  dirty, so downstream geometry rebuilds from the animated value.

### Removed

- Legacy style JSON migration is no longer part of runtime loading. Old
  top-level sections and legacy visual keys such as `line_width`, `font_size`,
  `ang_rdefault`, and `label_r_offset` now raise validation errors; canonical
  `*_px` fields are required.

### Tests

- Added coverage for export layout math, rendered-bounds export integration,
  CLI export options, canonical style validation, overlay automation access,
  construction-level parsed keyframe application, and scene-level
  first-keyframe state application.

## [1.2.0] — 2026-05-06

AI style-generation support release. This release adds a compact construction
summary exporter, machine-checkable style schema, and LLM prompt context for
generating style JSON plus optional loadCode-compatible DSL.

### Added

- **Compact construction summary exporter** — new
  `animageo.exporters.construction_summary` module with
  `construction_to_ai_summary(...)` and `write_ai_summary(...)`.
- **Scene-level AI summary API** —
  `AnimaGeoScene.exportStylePromptSummary(filepath=None, **kwargs)` exports
  `animageo-construction-summary/v1` as a dict or JSON file. The summary keeps
  names, canonical types, visibility, compact geometry, selected GGB style,
  construction dependencies, vars, groups, and parser diagnostics without raw
  `.ggb` XML.
- **AI style-generation context** —
  `docs/ai_style_generation_context.md` defines the style-layer model,
  resolver priority, when to use `overlay.per_type`, `overlay.per_name`,
  automation blocks, and when optional Python DSL is appropriate.
- **AI output contract** — the context now explicitly separates generated
  `STYLE_JSON`, optional `PYTHON_DSL`, and `NOTES`. `PYTHON_DSL` is limited to
  the body of a file passed to `scene.loadCode(...)`; it must not contain
  `AnimaGeoScene`, `loadGGB`, render/export calls, Manim animation code, or
  scene orchestration.
- **NOTES contract for LLM output** — the AI context now requires notes for
  ambiguity, construction-summary-based selections, overlapping geometry such
  as polygon sides vs. separate segments, DSL usage/avoidance, relative
  numeric changes, visibility changes, automation blocks, out-of-scope
  requests, and other follow-up-relevant assumptions.
- **Style JSON Schema** — `docs/ai_style_json_schema.json` provides a
  Draft 2020-12 schema for validating generated style JSON.
- **Construction summary documentation** —
  `docs/construction_summary.md` documents the
  `animageo-construction-summary/v1` format and exporter options.
- **AI style-generation fixture** — `examples/ai_style_generation_scene10/`
  contains a reproducible GeoGebra-based test setup for AI-generated style JSON
  and optional DSL, with output SVG generated into the same folder.

### Changed

- **Documentation navigation** — README, docs index, and API docs now link to
  the construction summary exporter, AI context, and style JSON schema.
- **AI guidance for layer choice** — the context now prefers `overlay.per_name`
  when a supplied construction summary is sufficient to resolve computed
  requests such as "longest segment", and reserves DSL for missing geometry or
  logic that cannot be represented by style JSON alone.
- **AI guidance for polygon-side highlights** — the context now warns that
  imported polygon outlines can duplicate side segments; highlighted sides
  should be raised above normal stroke layers or the polygon outline should be
  restyled/disabled, with the choice reported in `NOTES`.

### Fixed

- **GeoGebra `Point(Conic)` import** — points constrained to conics now keep
  their canonical curve parameter from GGB XML coordinates. This fixes scenes
  where a point on a hyperbola was imported as `data=None`, causing downstream
  `Line`, `Intersect`, `Segment`, `Distance`, `CircumcircleArc`, and `Angle`
  commands to remain unbuilt.
- **Wrapped arc containment** — `Arc.contains()` now compares point angles in
  the same unwrapped interval as the arc itself. This fixes
  `CircumcircleArc(A, M, B)` choosing the opposite side of chord `AB` when the
  intended arc crosses the `0` angle.
- **GeoGebra arc/ray intersections with Unicode labels** —
  `Intersect(Arc, Ray, index)` and `Intersect(Arc, Segment, index)` are now
  dispatchable, and command inputs such as `β` are treated as simple
  identifiers instead of being rewritten through empty phantom expressions.
- **DSL redefinition redraws dependents** — `loadCode()` and `putCode()` now
  run a final full rebuild before rerendering, so redefining an imported GGB
  element (for example `E = Rotate(...)`) updates downstream elements such as
  `Segment(B, E)` instead of drawing stale geometry.

### Tests

- Added coverage for construction summary export.

## [1.1.1] — 2026-05-01

Patch release for the resolver-based style architecture introduced in 1.1.0.
This release separates GGB import data, project overlay rules, explicit
Python/DSL edits, and construction visibility into distinct layers.

### Fixed

- **Explicit Python/DSL style priority** — `elem.style` is now reserved for
  explicit Python/DSL writes and remains the highest-priority style layer.
  `overlay.per_type` / `overlay.per_name` are no longer materialized into
  `elem.style`; the resolver reads overlay rules lazily from `StyleConfig`.
  This fixes cases like `d.style.stroke_width_px = 10` being overwritten by
  overlay during `addAllGeometry()` / `updateAllGeometry()`.
- **GGB visual import isolation** — GGB visual values are stored in
  `elem.ggb_style` and consumed by the resolver below overlay and above
  defaults. `import.enabled=false` now disables the whole visual import layer
  without clearing `elem.ggb_raw` or seeding defaults into `elem.style`.
- **Construction visibility separation** — GeoGebra `show_object` and
  `ImportPolicy.visible` are treated as geometry/construction visibility
  (`elem.visible`), not visual style. Runtime `Show` / `Hide` /
  `addAllGeometry(show=False)` stay above imported visibility.
- **Label placement resolver call** — label-placement code now consistently
  uses the imported `_resolve_style(...)` helper, preventing the
  `_resolve is not defined` crash when automatic label placement is enabled.
- **Canonical import color remapping** — `import.colors` writes canonical
  `#rrggbb` colors plus optional opacity into `elem.ggb_style`, avoiding raw
  RGB/RGBA arrays and stale-opacity edge cases.
- **Background export parity** — `rendering.background` is applied consistently
  to Manim preview/MP4 and SVG/PNG export.
- **Renderer no longer needs web-side legacy style bridge** — render paths read
  canonical `StyleConfig` defaults and resolver values directly; web clients do
  not need to add legacy `defaults.tick` / `defaults.arrow` / angle aliases.
- **GGB unsupported-command warning cascades** — GGB loading now records root
  unsupported commands in `scene.geo.command_diagnostics`, deduplicates repeats,
  and suppresses downstream `NoneType` warning cascades in non-strict mode.
- **Unicode GGB identifiers in generated expressions** — names such as `α_2`
  now resolve before command dispatch, fixing expression chains like
  `4 * (α_2 - 90°)` that previously degraded into `Sub(str, AngleSize)`.

### Changed

- **Resolver priority is explicit**:
  `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults`.
- **Overlay API compatibility** — `scene.applyOverlay()` / `StyleOverlay.apply`
  remain as no-op compatibility hooks; rendering uses lazy resolver reads.
- **GGB import/adaptation coverage** — `import.point_size` now maps GGB point
  sizes to `size_px`, and `ImportPolicy` covers raw-derived fields such as
  `stroke_opacity`, `stroke_dash_ratio`, `label_text`, `angle_range`, and
  `tick_count`.
- **Legacy visual fields are input migration only** — `line_width`,
  `ang_width`, `strich_*`, `arrow_*`, `label_r_offset`, and `font_size` in
  style JSON are normalized to canonical pixel-unit keys before resolving.
  Runtime render code reads `stroke_width_px`, `tick_*_px`, `arrow_*_px`,
  `label_radial_offset_px`, and `font_size_px`.
- **Manim baseline updated** — runtime dependency now requires
  `manim>=0.20.1,<0.22`, matching the latest PyPI release tested before
  1.1.1.
- **Documentation refresh** — README, API docs, architecture docs, style guide,
  field-name reference, import-policy docs, examples, and snapshots now
  describe the separate `ggb_raw` / `ggb_style` / `overlay` / `elem.style`
  layers.

### Tests

- Full suite: `1036 passed` with Manim Community `0.20.1`.

## [1.1.0] — 2026-04-29

Style-system release: semantic presets, per-type defaults, overlay parity for
GGB and DSL scenes, and a rewritten style guide. This release completes the
transition to the canonical style schema and removes the temporary alias and
normalization layer.

### Added

- **Semantic `presets` registry** — canonical style constants now live under
  `presets`: `presets.color`, `presets.point_size`, `presets.line_width`,
  `presets.angle_radius`, `presets.tick`, `presets.arrow`, and
  `presets.font_size`. Names such as `main`, `bold`, and `aux` are conventions;
  user-defined names are valid and can be referenced from other blocks.
- **Generic style references** — values like `presets.color.main`,
  `presets.line_width.bold`, and `presets.arrow.main` are resolved
  recursively by `StyleConfig`.
- **Structural preset includes** — per-type style maps can use `$include` to
  merge reusable structured presets, for example vector arrows and segment
  tick marks.
- **Scene background styling** — `rendering.background` accepts a hex color or
  a preset reference such as `presets.color.background` and is applied to the
  Manim camera background.
- **Canonical tick/arrow style keys** — renderers now understand
  `tick_length_px`, `tick_width_px`, `tick_shift_px`, `arrow_length_px`, and
  `arrow_width_px` through the resolver.

### Changed

- **`presets.color` is the only color registry** — builtin styles, examples,
  docs, and runtime access now use `presets.color`.
- **`defaults` is now a per-type baseline** — defaults choose or include
  semantic presets for element types (`point`, `segment`, `vector`, `angle`,
  etc.) instead of storing scene-level `angle` / `tick` / `arrow` / `font`
  knobs directly.
- **Overlay application order** — `overlay.per_type` and `overlay.per_name`
  apply uniformly to GGB-imported and DSL-created elements, with `per_name`
  winning over `per_type`.
- **Style import maps** — `import.colors`, `import.point_size`, and
  `import.line_width` accept fully qualified preset refs as well as bare
  preset names. `import.colors` now normalizes remap results to hex colors and
  applies target opacity separately, preserving the current opacity when the
  target does not specify one.
- **GGB import adaptation** — `import.point_size` is now applied by
  `applyStyle`; `ImportPolicy` can target raw-derived visibility, labels,
  angle range, tick count, line opacity and dash style. `obj_color` raw data
  exposes normalized `hex` and `opacity` aliases for policy callables/remaps.
- **ImportPolicy scope** — `ImportPolicy` is now limited to raw-GGB
  adaptation. Type/name stylization moved fully to `overlay.per_type` and
  `overlay.per_name`, which apply uniformly to GGB and DSL elements.
- **Documentation and examples** — README, style docs, field-name reference,
  migration guide, policy examples, and the HTML style guide were updated to
  the canonical `presets` schema.

### Removed

- Removed top-level `palette` and `palette.*` reference resolution.
  Use `presets.color` and `presets.color.<name>` references.
- Removed normalization of old scene-level `defaults` blocks for tick, arrow,
  font, and angle-radius settings. Use `presets.tick`, `presets.arrow`,
  `presets.font_size`, `presets.angle_radius`, and per-type `defaults`.
- Removed `strich_*_px` per-element aliases. Use `tick_length_px`,
  `tick_width_px`, and `tick_shift_px`.
- Removed public support for automation settings under `rendering`; use
  `overlay.angle_radius` and `overlay.label_placement`.

### Tests

- Full suite: `1013 passed` with Manim Community `0.19.0`.

## [1.0.2] — 2026-04-24

Security, correctness, dead-code cleanup and manim 0.20 compatibility pass.
Driven by a full library audit; every item below has a regression test.

### Removed (breaking)

- **``animageo/_stubs.py``** — 613-line orphan IDE-stub snapshot that
  referenced pre-1.0 field names (``Measure.x``, ``Angle.angle``).
  Unreferenced from package; deleted.
- **``mult_ff`` / ``mult_fm`` / ``mult_mf`` / ``mult_if``** — unreachable from
  dispatch (``f`` was never registered in ``type_to_shortcut``); deleted.
- **Unused Lark parser block in ``ggb_parser.py``** (~130 lines: grammar +
  ``GeoGebraTransformer`` + ``parse_geogebra_xml``). Never called.
  ``lark`` removed from ``pyproject.toml`` dependencies.
- **DSL sandbox**: ``type`` and ``getattr`` removed from ``SAFE_BUILTINS``
  (classic sandbox escape via ``type(x).__mro__[-1].__subclasses__()``).
  Use ``isinstance(x, Cls)`` and the new ``type_name(x)`` DSL helper.
- **CLI ``-d/--debug`` flag** — semantic reversed to ``action='store_true'``
  (intuitive: ``-d`` turns debug ON). Previously was ``store_false`` which
  meant ``-d`` silenced debug output.

### Added

- **``AnimaGeoScene.resetScene()``** — explicit state wipe for reusing one
  scene instance across render jobs. Called automatically by ``loadGGB``.
- **``setElementStyle(..., update=True)`` / ``setVisible(..., update=True)``**
  — auto-rerender by default so changes are visible immediately.
  ``update=False`` defers for bulk operations.
- **``COMMAND_REGISTRY`` + ``list_commands()``** in ``lib_commands``. Dispatch
  uses the explicit registry instead of ``globals()``. Emits a warning when
  a command name doesn't match any implementation (previously silent ``None``).
- **Pixel-invariant decoration overrides** — per-element opt-in keys in
  ``elem.style``: ``strich_len_px`` / ``strich_rshift_px`` / ``arrow_width_px``
  / ``arrow_length_px``. When set, rendered at an absolute pixel size
  regardless of canvas ``ptUnit``. Scene-level defaults keep legacy
  scale-with-canvas semantics (backward-compatible).
- **DSL helper ``type_name(x)``** — returns ``type(x).__name__`` as a string.
  Safe stand-in for the removed ``type(x).__name__`` pattern.

### Fixed

- **Shell / Python injection in ``python -m animageo``** — CLI used
  ``os.system`` with f-string interpolation of user-supplied arguments into
  generated Python source. Rewritten to ``subprocess.run`` with argv-list
  and ``repr()``-escaped placeholders.
- **ZIP slip + zip bomb in ``.ggb`` loader** — ``ZipFile.extractall`` ran
  without path validation. New ``_safe_extract_ggb`` rejects traversal
  paths, absolute paths, archives with >4096 members, and >256 MB
  uncompressed total.
- **``loadGGB`` state leakage** — a second ``loadGGB`` on the same scene
  instance stacked new geometry on top of the old (visible as leftover
  elements from the prior file). Now starts from a fresh ``Construction``.
- **Global ``_bbox_cache`` thread-safety** in ``label_placement`` — added
  ``threading.Lock``; extended cache key with ``tex_template`` identity.
- **``Angle.equivalent`` / ``AngleSize.equivalent``** — used the non-existent
  ``.angle`` attribute; would raise ``AttributeError``. Now use ``.value``.
- **``are_congruent_aa`` / ``are_complementary_aa``** (``lib_commands``) —
  same ``.angle`` bug; 100% crash on any invocation. Fixed.
- **``_apply_interp_value`` for Measure vars** — wrote to ``.x``, which
  doesn't exist on ``Measure`` (phantom attribute created; real ``.value``
  unchanged). Keyframe animations on Measure variables were silently no-ops.
- **``Element.value()`` for Measure/AngleSize/Boolean** — circular import
  between ``lib_vars`` and ``lib_elements`` left those classes unbound at
  method-call time → ``NameError``. Fixed with local imports.
- **``font_size_px`` dead key** — builtin defaults and overlay shipped the
  key, but the renderer only read ``font_size`` (manim units), silently
  dropping pixel-invariant font overrides. Renderer and label placement
  now prefer ``font_size_px`` through the resolver.
- **``label_radial_offset_px``** — name said pixels, code treated value as
  manim units. ``5`` meant 5 MU ≈ 500 px. Now honoured as actual pixels.
- **Sandbox hardening** — see "Removed" above for ``type``/``getattr``.
- **Marching-squares ``_edge_point``** — unguarded divisions by corner-
  difference could yield ``inf``/``nan`` for near-coincident corner values.
  Now collapses to mid-edge.
- **``intersect_*`` near-zero endpoint detection** — ``if a == 0`` on a
  float could miss a true zero rounded to ±1e-17, losing a valid root.
  Replaced with ``abs(a) < 1e-12`` + symmetric case at the other endpoint.
- **``play_keyframes`` on a missing element** — silently skipped via
  ``info is None``; now logs a warning with context so debug traces aren't
  lost.

### Changed

- **Python requirement** relaxed from ``>=3.13`` to ``>=3.10``. Code uses
  PEP 604 unions and PEP 585 generics; no newer syntax.
- **Dependency pins** — ``numpy<3.0``, ``manim<0.20`` upper bounds added
  (manim has had breaking API changes between minor versions).
- **Internal project notes**: stale statistics removed (test count,
  render-method count).
- **``style/schema.py``** doc table split into pixel-invariant vs
  scale-with-canvas unit classes (previously mixed).

### Docs

- ``docs/style_guide/assets/examples/src/anim_scenes.py`` (served download)
  was using pre-1.0 API names (``show_label``, ``stroke_width``,
  ``technic``, ``ggb_export.import_policy``); synced with the current
  source in ``docs/style_guide/examples/``.
- ``examples/main.py``: 15 SyntaxWarnings from invalid escape sequences
  (``'$...\circ...$'``) fixed with raw-string prefix.

### Tests

- 937 → 988 (+51 new regression tests).
- 0 regressions; ``_safe_extract_ggb`` path traversal / bomb prevention,
  DSL sandbox escape vectors, state-reset on ``loadGGB``, overlay reaching
  renderer for stroke/font/size, ``Element.value()`` for each variable
  type, ``Angle.equivalent`` symmetry, float-tolerance edge cases, CLI
  injection payload lock-in, pixel-invariant decoration overrides.

### Compatibility

- Tested against manim 0.19.0 and 0.20.1. Upper bound in ``pyproject.toml``
  relaxed to ``manim>=0.19.0,<0.22``.
- Fixed manim 0.20 deprecations in our code:
  ``VMobject.get_cap_style()`` → direct ``cap_style`` attribute read.
- Fixed NumPy 2.0 deprecations in our code: replaced 2-D ``np.cross``
  calls (``lib_commands.area`` and ``are_concurrent_lll``) with explicit
  scalar ``x1*y2 − y1*x2`` expressions.
- Silenced the startup ``pytest-asyncio`` deprecation via
  ``[tool.pytest.ini_options]``.

## [1.0.1] — 2026-04-24

Patch release: reliability fixes in rendering and DSL re-definition.

### Fixed

- **Arc / CircleSector rendering** (`animageo.py`) — both renderers read `elem.data.sizes`, but the geometry classes expose the attribute as `angles`. Any scene containing Arc or CircleSector crashed during `CreateMObject`, cascading through dependents. Renamed to `elem.data.angles`.
- **`.contains` typos in `lib_commands.py`** — `arc.centerontains(...)` / `line.offsetontains(...)` were pre-1.0 search-and-replace artifacts with no matching method on the target classes. Broke `intersect_Cl` (arc∩line), `circumcircle_arc_ppp` / `circumcircle_sector_ppp`, `contained_by_pc` / `contained_by_pl`. All five call sites now use `.contains(...)`.
- **DSL command failure with forward-ref Vars** — when a command's inputs contain a forward-reference Var with no data yet, `Construction.apply()` only wrote `None` into outputs that *already existed* as elements. Phantom outputs (e.g., intermediate `_3` from `4 + x` arithmetic) were silently skipped, so `element(name)` later returned `None` and `styleGeometry`-style code raised `AttributeError`. Fix: `apply()` now creates placeholder elements for all outputs, including not-yet-existing phantoms.
- **`Construction.rename()` broke downstream dependency graph** — when a DSL file redefined a GGB-loaded element (e.g., `X = A + x * (B - A)` where `X` was already a Point in the GGB), the `_forget(X) + rename(phantom, X)` sequence cleared every `state[downstream].inputs` reference to `X`, but did not restore them for the new command using `X`. Symptom: animating the Var re-computed `X` itself, but `q1`/`g`/… that depended on `X` never rebuilt, so the animation was visually frozen. Fix: `rename()` now re-runs `updateStateLevels` on every command that references the new name.

### Notes

- All 937 unit tests continue to pass.
- No API surface changes.

## [1.0.0] — 2026-04-23

First stable release. Substantial rewrite of the style system, parsers, and geometry core, with three new element types and full animation/labeling pipelines.

### Added

- **Python DSL (`animageo.dsl`, `parsers/dsl/`)** — exec-based mini-DSL replacing the old short-parser. Supports `for`/`if`/`def`, keyword args, tuple unpacking, live `.field` access on elements, proxy arithmetic (`A-B`, `-v`, `abs(x)`), `f(x) = expr` sugar for functions, and auto-generated `.pyi` stubs per scene.
- **Style subsystem (`animageo/style/`)** — three-layer resolver architecture: package-shipped `builtin.json` defaults (pixels), user JSON defaults, `overlay.per_type` / `overlay.per_name` stylization, with explicit `elem.style[...]` writes always winning. Mini-DSL for policy values: `const:`, `scale:`, `quantize:`, `remap:`.
- **`ImportPolicy`** — configurable GGB-to-style mapping. Pass to `loadGGB` or embed under `import.policy` in the style JSON. Supports scalar, callable, and DSL-string rules. `scene.reloadPolicy()` reapplies a new policy without reparsing XML. Type/name overrides belong to `overlay.per_type` / `overlay.per_name`.
- **`Conic` element** — first-class conic stored as a 3×3 symmetric matrix with lazy classification into 9 types (circle / ellipse / parabola / hyperbola / intersecting / parallel / double lines / point / empty). Canonical parametrizations via eigendecomposition. Constructors: `Conic(matrix)`, `from_ggb_matrix`, `from_coeffs`, `from_string`.
- **`Function` element** — explicit `y = f(x)` with sympy parsing: `^` → `**`, Unicode `≤/≥`, chained comparisons, `If[...]` → `Piecewise`. numpy `lambdify` on the hot path.
- **`ImplicitCurve` element** — `F(x, y) = 0` for any sympy expression, rendered by marching squares.
- **Adaptive curve sampling (`geo/curve_sampling.py`)** — viewport-aware sampler with Liang–Barsky clipping, analytic t-ranges for parabola / hyperbola branches, marching squares for implicit curves. Hard `max_samples` caps guarantee no hangs on pathological curves.
- **Intersections across all type pairs** — analytic for `Kl` / `KK` / `Kc` (pencil method); numeric with sympy + `scipy.brentq` / `fsolve` fallbacks for `F*` and `I*`. 150+ commands in `lib_commands.py`.
- **Conic geometric constructors** — `Ellipse`/`Hyperbola` from foci + semi-axis, `Parabola` from focus + directrix, `Conic` from 5 points.
- **Conic properties** — `Center`, `Focus`, `Vertex`, `Axes`, `Directrix`, `Eccentricity`, `Polar`, `Tangent`.
- **Automatic label placement (`label_placement.py`)** — priority-ordered greedy solver with 8 candidate directions, analytic bisector placement for angles, EMA smoothing + anchor hysteresis for dynamic tracking, per-keyframe snapshots with interpolation.
- **Keyframe animation (`keyframes.py`)** — JSON-driven animation: free points, tparam-constrained points, numbers, angles, booleans; linear / smooth / in / out / in\_out easing; per-keyframe `show` / `hide`.
- **Batch API** — `setElementStyle(names, **kwargs)`, `setVisible(names, visible)`, `animating(...)` context manager.
- **Pixel-invariant sizing** — all GGB sizes (point radius, line width, font, arc, label offset) stored in pixel units, divided by `ptUnit` at render time. Same pixel output across canvas sizes.
- **Angle arc auto-sizing** — opt-in `rendering.angle_radius` scales arc radius by `(π/2 / angle) ** exp`, clamped by arm-length fraction. Shared between renderer and label placement.
- **Z-index tiers** — named constants in `constants.py` (`Z_FILL`, `Z_LABEL`, …).
- **`CreateMObject` dispatch** — split into 13 per-type `_render_<typename>` methods plus a small context builder. `CreateMObject` itself is a 20-line dispatcher.
- **Structured logging** — all modules use `logging.getLogger(__name__)`; no stray `print` in library code.
- **`CHANGELOG.md`** (this file).

### Changed

- **Version:** 0.1.11 → 1.0.0.
- **Python requirement:** bumped to `>=3.13`.
- **Metadata:** added MIT license, `Development Status :: 5 - Production/Stable`, audience and topic classifiers. Homepage switched to `https://`.
- **Topological rebuild** — Construction now uses Kahn's algorithm with cycle detection and per-element error recovery, so one broken element no longer aborts the whole scene.
- **CLI entry point** — `animageo` console script remains, unchanged surface.

### Fixed

- **`intersect_cc`** — edge-case reliability (tangent / coincident circles).
- **Angle arc radius units** — no longer collapse to sub-pixel values when `elem.style` is empty (builtin default of 17 px now applies).
- **GGB label offsets** — now scale proportionally with canvas size via `ptUnit_ggb`.

### Removed

- **`animageo/style.py` / `animageo/style_schema.py`** — replaced by the `animageo/style/` subpackage.
- **`animageo/parsers/short_parser.py`** — replaced by the Python DSL.
- **`requests` dependency** — was unused.
- **Legacy `geodynamic/` package** — earlier rename; no longer shipped in the wheel after build hygiene fix.

### Packaging

- **`pyproject.toml`** is now the single source of truth; `setup.py` reduced to a one-line shim.
- **`package-data`** — `style/builtin.json` and `*.pyi` stub files now ship inside the wheel.
- **`find_packages`** — restricted to `animageo*`; `tests/` is no longer included in the distribution.
