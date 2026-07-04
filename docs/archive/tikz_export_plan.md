# TikZ Export — Implementation Plan

> Goal: a comprehensive `scene.exportTikZ(...)` that renders any AnimaGeo
> construction into editable, semantic TikZ for inclusion in LaTeX documents,
> parallel to the existing `exportSVG`.

## Decisions (confirmed)

1. **Semantic TikZ** — emit native primitives (`\draw circle`, `ellipse`,
   `(a)--(b)`, `[->]`, `arc`, `\node {$A$}`). Sampled curves with no native
   primitive (parabola/hyperbola/function/implicit/locus) become
   `\draw plot coordinates {...}` using the existing `curve_sampling.py`.
2. **Snippet by default + `standalone=True` option** — default output is a bare
   `tikzpicture` environment for `\input{}`; `standalone=True` wraps it in a
   compilable `\documentclass{standalone}` document with a Cyrillic-ready
   preamble (`fontenc T2A`, `babel russian`, `amsmath`, `amssymb`, `tikz`).
3. **Math coordinates + computed `x=/y=` scale** — coordinates are emitted in
   GeoGebra math units (same as `elem.data.coords`). The picture uses
   `x=<S>cm, y=<S>cm` so geometric lengths (unitless radii) scale with the
   coordinate system, while fixed-size things (point markers, line widths,
   arrow tips) use absolute `pt` and stay scale-independent — matching how the
   SVG output looks.

## Unit model (derived from the codebase)

- `style.export['ptUnit']` = output **pixels per math-unit (MU)**.
  SVG maps `MU → px` via `Matrix(ptUnit,0,0,-ptUnit, ptXZero, ptYZero)`.
- `ptUnit_style` (`_style_ptUnit`) — scale used for stroke/font px.
- `ptUnit_ggb` — original GGB px-per-MU, used for label offsets.
- Output pixel → physical: `DPI` (default 96). `cm_per_px = 2.54/DPI`,
  `pt_per_px = 72/DPI` (TeX big-point ≈ CSS px at 96 dpi → 0.75).
- Therefore:
  - tikzpicture `x = y = ptUnit * cm_per_px` cm (cm per MU).
  - `stroke_width_px` is *already the output pixel width* (traced through
    `stroke_width_to_manim` × cairo `0.01` × CTM `ptUnit` ⇒ px), so
    `line width = stroke_width_px * pt_per_px` pt (× `ptUnit/ptUnit_style`
    when those differ).
  - point radius = `size_px/2 * pt_per_px` pt.
  - font size = `font_size_px * pt_per_px` pt (optional; default on).
  - label offset = `label_offset_px * pt_per_px` pt as node `xshift/yshift`.
- Geometric radii / arc radii / ellipse semi-axes are emitted **unitless** (MU)
  so the `x=`/`y=` unit vectors scale them.

## Module layout

New subpackage `animageo/exporters/tikz/`:

- `__init__.py` — exports `export_tikz`, `TikZExporter`, `TikZOptions`.
- `options.py` — `TikZOptions` dataclass (dpi, standalone, clip, background,
  emit_font_size, coordinate_precision, preamble override, …).
- `document.py` — `TikZDocument`: color registry (`\definecolor{agc0}{HTML}{…}`),
  body line buffer, snippet/standalone assembly, number & coordinate formatting.
- `style_map.py` — resolved-style → TikZ option string (`draw`, `fill`,
  `line width`, `dash pattern`, `opacity`/`fill opacity`, `line cap`), color
  interning, all px→pt/cm conversions, anchor map (9-point → TikZ `anchor=`).
- `emitters.py` — per-type emitters mirroring `_render_*`:
  point (shapes), segment (+ticks), line, ray, vector (+arrow, +ticks),
  circle (+dash), arc, circlesector, polygon (fill+stroke), angle (sector fill +
  arc(s) + right-angle marker + label), conic (circle/ellipse native; parabola/
  hyperbola/degenerate-lines via sampler/clip), function, implicitcurve,
  locuscurve. Each emitter reuses the resolver (`style.resolver.resolve`),
  `resolve_label_text`, `compute_effective_arc_size_px`, `_get_scene_bounds`,
  `Line.get_endpoints`, and `curve_sampling` helpers.
- `exporter.py` — `TikZExporter`: iterate visible drawables, sort by resolved
  `z_index`, dispatch to emitters, collect label nodes to emit last (labels on
  top), build the `TikZDocument`, write file / return string.

Wiring:
- `AnimaGeoScene.exportTikZ(filepath=None, *, standalone=False, **opts)` in
  `animageo.py`, parallel to `exportSVG`. Passes `self` so emitters can use the
  resolver and scene geometry/viewport.
- `exporters/__init__.py` re-exports `export_tikz`.
- CLI `__main__.py`: add `--format {svg,tikz}` (and infer `tikz` from a `.tex`
  `-o`), pass through to a driver that calls `exportTikZ`. Add `--standalone`.

## Fidelity details

- **Z-order**: TikZ paints in emission order. Sort drawables by resolved
  `z_index`; emit fill→stroke per element; collect labels and emit after all
  geometry (matches `Z_LABEL`).
- **Colors**: intern unique hex into `\definecolor` lines; reference by name.
- **Clipping**: default `clip=True` clips the picture to the viewport rectangle
  from `_get_scene_bounds(0)` so lines/curves don't overflow the canvas
  (the SVG canvas is bounded too). Lines/rays still use `get_endpoints` against
  the viewport corners.
- **Dash**: map `stroke_dash_ratio` → `dash pattern=on a off b` derived from the
  manim `dash_length=0.17` MU base, converted to pt.
- **Ticks** (`tick_count`, `tick_style`): port `_append_tick_marks` geometry;
  `line` style fully; `wave` as best-effort (`plot[smooth]`), documented.
- **Angle**: sector fill + 1..n concentric arcs (`arc_shift_px`), right-angle
  square marker, `minor`/`reflex` range, label on bisector — port from
  `_render_angle` + `compute_effective_arc_size_px`.
- **Point shapes**: circle/square/triangle{up,down,left,right}/cross/plus; honor
  `points_display` (`only_labels`/`only_points`).
- **Labels**: `\node[anchor=…, xshift, yshift]` with LaTeX text from
  `resolve_label_text`; GGB descender correction as in `ui.py`.

## Risks / to verify empirically

- **Unitless radius scaling**: confirm `\draw (..) circle (r)` (unitless r) uses
  the `x`-unit vector under `[x=Scm,y=Scm]` (expected: yes) while `circle (Rpt)`
  stays absolute. A tiny `pdflatex` compile test will confirm; fall back to
  emitting `(r*S)cm` if not.
- **`scale` vs `x=/y=`**: we use `x=/y=` precisely so `pt` dimensions stay fixed.

## Tests (`tests/test_tikz_export.py`)

- Unit: each emitter produces expected substrings/coords/colors for a small DSL
  construction (point, segment, line clip, circle, polygon, angle, vector,
  function, conic-ellipse).
- Color interning + `\definecolor`. Number formatting (no `1.0000001`, strips).
- Snippet vs standalone wrapping; preamble contents.
- Smoke: full DSL scene → non-empty body, balanced environments.
- Optional compile test guarded by `shutil.which('pdflatex')` /
  `pytest.mark.skipif` (standalone → PDF).

## Docs

- `docs/tikz_export.md` cookbook (API, CLI, options, examples).
- Update `docs/architecture.md` (pipeline diagram + exporters), `docs/roadmap.md`,
  `CHANGELOG.md`.
