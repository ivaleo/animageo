# Export formats

AnimaGeo writes a construction in several formats. Two tracks exist:

- **Static vector** — the construction is built once and serialised by an
  `export*` method: **SVG**, **PDF**, **EPS**, **TikZ**.
- **Render** — manim's renderer produces a raster/video file: **PNG**, **GIF**,
  **MP4**, **WebM**, **MOV**. Animate with keyframes; otherwise a single frame
  is produced.

See `docs/tikz_export.md` for TikZ specifics. This page covers PDF/EPS and the
animation containers.

## PDF / EPS (vector)

Both reuse the same Cairo pipeline as `exportSVG` (identical look), only the
cairo surface differs.

```python
scene.loadGGB("scene.ggb", style="style.json", export={"size": {"width": 800, "height": 600}})
scene.exportPDF("figure.pdf")            # vector PDF, single page
scene.exportEPS("figure.eps")            # vector EPS (Encapsulated PostScript)
scene.exportPDF("figure.pdf", dpi=150)   # smaller physical page (denser)
```

- `dpi` (default **96**, matching the TikZ exporter) sets the **physical page
  size**. SVG is measured in pixels; PDF/EPS in PostScript points (1/72"), so a
  pixel maps to `72/dpi` pt. A 640×480 px canvas → 480×360 pt (≈ 6.67"×5") at 96
  dpi. The figure stays vector regardless — in LaTeX you rescale with
  `\includegraphics[width=\linewidth]{figure.pdf}`.
- **Text is outlines, not selectable text** (labels are rendered as Bézier
  curves, same as the SVG path). Fine for print; not searchable.
- **EPS has no transparency.** Semi-transparent fills/strokes are flattened
  (rasterised) by cairo, which bloats the file and softens edges — a warning is
  logged. Use **PDF** or **SVG** to preserve opacity.

### CLI

```bash
python -m animageo scene.ggb -o figure.pdf            # format inferred from .pdf
python -m animageo scene.ggb -o figure.eps --dpi 150
python -m animageo scene.ggb --format pdf -o out.pdf
```

## Animation: MP4 / GIF / WebM / MOV

The container is chosen with `configure_render` **before** the render (manim's
file writer reads it at scene setup, so setting it inside `construct()` is too
late):

```python
from animageo import configure_render

configure_render(format="gif", fps=20)   # or "mp4" (default), "webm", "mov", "png"

class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB("scene.ggb", style="style.json", export={"size": {"width": 800, "height": 600}})
        self.play_keyframes(keyframes_json)
```

| Container | Transparency | Notes |
|-----------|--------------|-------|
| `mp4`  | none        | universal video default |
| `gif`  | 1-bit       | universal, but 256-colour palette → banding on gradients |
| `webm` | alpha       | small, modern web video |
| `mov`  | alpha       | alpha-capable video |
| `png`  | alpha       | single frame (last frame) |

For gradients/anti-aliased fills with a transparent background, prefer `webm`
or `mov` over `gif`.

GIF colours are near-faithful to the MP4 render: AnimaGeo patches manim's GIF
writer (`install_gif_palette_fix`, installed automatically by
`AnimaGeoScene`) to keep the adaptive per-scene palette. Stock manim
0.19–0.21 declares the GIF stream as `rgb8` — a fixed 3-3-2 RGB grid — which
discards the palette computed by `palettegen` and scrambles colours into
yellow/green artifacts.

### CLI render track

```bash
# single frame (no animation) → PNG
python -m animageo scene.ggb -o frame.png

# animation from a keyframes JSON → GIF / WebM / MP4
python -m animageo scene.ggb -o anim.gif  --keyframes keys.json --fps 15
python -m animageo scene.ggb -o anim.webm --keyframes keys.json --transparent
python -m animageo scene.ggb --format mp4 -o anim.mp4 --keyframes keys.json
```

- `--keyframes file.json` — keyframe sequence (see
  [docs/keyframes.md](keyframes.md)). Without it, a single frame is rendered.
- `--fps`, `--transparent` — forwarded to manim.
- `--quality {l,m,h,p,k}` — manim quality preset governing the render-track
  resolution/fps: `l`=854×480@15, `m`=1280×720@30, `h`=1920×1080@60,
  `p`=2560×1440@60, `k`=3840×2160@60.
- **Output resolution** of the render track is governed by manim's config
  (default 1920×1080; set with `--quality`), *not* by `--export-size`.
  `--export-size` controls the camera framing/aspect; the static vector track
  uses it for the canvas size directly.

The keyframes JSON has the same format used by `scene.play_keyframes(...)`.
Use `"version": 2` for the current style/visibility/camera/events-capable
timeline:

```json
{"version": 2, "keyframes": [
  {"t": 0,   "values": {"A": [-4, -1]}},
  {"t": 1.5, "values": {"A": [-2, 2]}, "easing": "smooth"}
]}
```

## Interactive: JSXGraph (HTML)

Unlike every other export (which serialise a rendered frame), this produces a
**live, draggable** construction: drag free points / gliders / sliders and the
dependent geometry recomputes in the browser. See
`docs/archive/jsxgraph_export_plan.md` for the design and roadmap.

```python
scene.loadGGB("scene.ggb", style="style.json", export={"size": {"width": 800, "height": 600}})
scene.exportJSXGraph("board.html")              # self-contained page (default)
scene.exportJSXGraph("board.js", output="js")   # board fragment for embedding
scene.exportJSXGraph("board.json", output="json")
```

```bash
python -m animageo scene.ggb -o board.html      # format inferred from .html
python -m animageo scene.ggb --format jsxgraph -o board.html
```

- **Best results from GGB-imported scenes**: free points become draggable,
  points constrained to a curve become gliders, numbers become sliders. (DSL
  `Point(x, y)` points are emitted as fixed points — they are not detected as
  free inputs.)
- **Live** (recompute on drag): points/gliders/sliders, midpoint, segment,
  line/parallel, ray, vector, circle (incl. slider-/distance-driven radius),
  semicircle, polygon (with its edges), perpendicular, perpendicular-bisector,
  angular bisector, angle, ellipse/hyperbola/parabola/conic, reflection,
  intersection, and **rotate/translate** (of points, segments, lines, circles,
  vectors, polygons). **Decorations** are live too: vector arrowheads (sized
  from the GGB arrow size) and segment **congruence tick marks** (perpendicular
  dashes built from function-valued anchor points, so they track drags).
- **Drawn statically** (sampled curves): functions, implicit curves, conics
  defined by an expression, arcs, sectors, loci, and tangent-from-a-point. A
  **coverage report** lists live vs static (logged at INFO: `N live, M static …`);
  only genuinely-empty outputs are dropped.
- Output: `output="html"` (default, self-contained), `"js"` (fragment),
  `"spec"` (declarative `animageo-board/v1` JSON — see below), `"json"` (legacy
  board spec carrying JS statements), or `"moodle"` (`<jsxgraph>` block for the
  Moodle filter_jsxgraph plugin).
- Labels render as LaTeX via MathJax; JSXGraph + MathJax load from CDN.
- **Board chrome follows the scene**: background colour, axes/grid show-hide
  (incl. per-axis visibility) and axes/grid colours are imported from the
  GeoGebra view. Override with `JSXGraphOptions`:

  ```python
  from animageo.exporters.jsxgraph import JSXGraphOptions
  opt = JSXGraphOptions(output="html", axis=False, grid=True, background="#fff")
  scene.exportJSXGraph("board.html", options=opt)
  ```

  `axis` / `grid` default to `None` (mirror the scene; GeoGebra defaults —
  axes on, grid off — when the scene says nothing); pass `True`/`False` to
  force. `background` defaults to the scene colour; pass a CSS colour to
  override or `""` to let the page colour show through.
- **Element styles** (stroke/fill colour, width, opacity, dash, point
  size/shape, label colour, angle arc radius, and a deliberate label offset)
  are read through the same style resolver the SVG/PNG renderer uses, so a GGB
  import, style overlay or explicit `elem.style` write all carry over.

### Declarative spec + framework-agnostic web runtime

For embedding a board as a *controllable* component in any web project (any
framework or none — not just a standalone page), export the **declarative
spec** instead of HTML:

```python
scene.exportJSXGraph("board.json", output="spec")   # animageo-board/v1
```

```bash
python -m animageo scene.ggb -o board.json --format jsxgraph   # .json → spec
```

The spec is **eval-free structured data** (schema:
`animageo/exporters/jsxgraph/board.schema.json`): a topologically-ordered list
of `elements` (with their AnimaGeo semantic `kind`, an engine render-instruction
and structured `parents`) plus an interactive-input `inputs` schema. It carries
no JS strings, so a consumer needn't evaluate code to build the board.

The `web/` directory turns a spec into a live, draggable board with a clear
**signals/actions** API (in construction terms — element names + AnimaGeo kinds):

- `@animageo/runtime` — `createBoard(spec, container, opts) -> BoardHandle`;
  signals `ready` / `change` / `commit` / `viewchange` / `error`; actions
  `getState` / `setState` / `setValue` / `reset` / … JSXGraph is injected (peer
  dependency); no globals; multi-instance safe.
- `<animageo-board>` — a Web Component (the zero-framework primitive): signals as
  `CustomEvent`s, actions as element methods.
- `web/adapters/` — thin React / Vue / Svelte / vanilla templates.

See `web/README.md`, `docs/archive/jsxgraph_web_integration_plan.md` and the audit doc.

## Choosing a format

| Goal | Format |
|------|--------|
| LaTeX `\includegraphics`, journals, print | **PDF** (or **EPS** for EPS-only workflows) |
| Web, Inkscape, editing | **SVG** |
| Native LaTeX figure (editable, real LaTeX labels) | **TikZ** |
| Interactive web widget (drag points/sliders) | **JSXGraph** (`.html`) |
| Universal animation (chat, slides, README) | **GIF** |
| Lightweight web video / transparent video | **WebM** / **MOV** |
| Highest-compatibility video | **MP4** |
| Quick raster preview, Office/Docs paste | **PNG** |
