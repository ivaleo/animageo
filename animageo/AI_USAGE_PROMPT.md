# AnimaGeo — Guide for AI Agents

You are reading the technical guide for **animageo**, a Python library that
turns geometric constructions into publication-quality SVG images and
manim-rendered MP4 animations. This document is self-sufficient: follow it
even if you have never seen the library before. Prefer it over guesses from
training data — the API here was verified against the shipped version
(**animageo 1.9.0a5**; the guide ships inside the package, so the installed
copy always matches the installed version it came with).

**Mental model.** AnimaGeo is "GeoGebra as code". You describe geometry as a
*dependency graph* (a `Construction`): free points are inputs; everything
else (midpoints, intersections, circles, angle marks…) is derived by
commands. When an input moves, the whole construction recomputes — this is
what makes animation of a *construction* (not of individual drawings)
possible. Rendering is done with manim (`AnimaGeoScene` subclasses
`manim.MovingCameraScene`), export to SVG is done through Cairo.

Three layers you will touch:

1. **Construction DSL** — Python-like code run by `scene.putCode("...")`.
   Factories like `Point`, `Segment`, `Intersect`, `Rotate` build the graph.
2. **Scene API** — `AnimaGeoScene` methods: load/style/fit the construction,
   reveal elements with animations, animate variables, export.
3. **Style JSON** — global visual policy (palette, sizes, label placement).

## 0. Working principles

Every rule in this guide is an instance of one of these. When you face a
situation the guide does not cover, derive the answer from the principles —
do not guess API details from training data.

1. **Relations live in the graph, not in coordinates.** Anything the user
   states as a property (point on circle, equal segments, perpendicular)
   must hold *by construction*, so it survives any motion. Hand-picked
   coordinates that merely look right are wrong.
2. **One mathematical object = one drawable.** Don't draw the same thing
   twice (polygon + its side segments); don't split one thing into pieces.
3. **Native marks over manual drawing.** Angle arcs, right-angle boxes,
   equality ticks, value labels are construction elements with style keys —
   manual manim overlays don't update, export, or avoid labels.
4. **Helpers are invisible in the result.** Every object you created only to
   build another (helper lines, Thales circles, anchor points) is hidden.
   Do a final sweep: everything visible must be meaningful to the user.
5. **Frame first, then reveal.** `fitView` measures visible mobjects — call
   it on the full static construction before `HideAll`/staged reveals, and
   budget the frame for the whole motion range, not just t=0.
6. **Sizing is ratios, not values.** On a ~800×600 canvas: line ~1.5–2 px,
   point ≈ 4× line, font ≈ 2–2.5× point, angle arc ≈ 1.0–1.2× font. Scale
   all families together; never one alone (§7 has the full table).
7. **Labels are solved, not sprinkled.** Label what the user named; enable
   the auto-placement preset for any labeled figure; pin individual
   stragglers with `label_offset_px` + `label_placement_locked`.
8. **Animate variables, not frames.** Route motion through `addVar`
   trackers; the dependency graph moves everything downstream. Never
   rewrite coordinates frame by frame.
9. **Verify numerically, then visually.** Assert the requested relations in
   the script; then look at rendered frames (first, middle, last) before
   reporting success. A figure wrong in numbers cannot be right on screen.
10. **The API is closed.** Unknown factory names raise; missing features are
    built from primitives and reported. When unsure, run a two-point smoke
    test, don't speculate.

---

## 1. Before you generate: what to clarify with the user

If the request leaves these open, either ask, or choose the default and say
so in your report:

- **Output**: static image (SVG/PNG/PDF) or animation (MP4)? Default: what
  the user's verb implies («нарисуй»/draw → static; «анимируй»/animate → MP4).
- **Canvas**: size and aspect. Defaults: 800×600 for stills, 1920×1080
  (16:9) for video.
- **What to emphasize**: which objects are *the result* (accent color) vs
  helpers (thin/gray/dashed/hidden)?
- **Labels**: which points/objects must be labeled; language of any text.
- **For animations**: the storyboard — order of appearance, what moves,
  how long. A good default: build up the figure step by step in dependency
  order, then animate the free points.
- **Style**: any color scheme / "textbook style" preference.

Ask only when the missing choice changes the mathematics, the intended
storyboard, or the visible conclusion. Otherwise use the library defaults
and the autonomous defaults below. Do not ask the user to choose low-level
API mechanics (manual vs native angle ticks, how labels update, whether to
use dependency variables): those are implementation details and should be
handled correctly by the scene.

Autonomous defaults (beyond the §0 principles):

- Equal angles / bisectors → native equal-angle marks (`tick_count`), not
  textual angle labels, unless the user explicitly asks for names/values.
- All angle marks in one figure share one visual system (same stroke/fill/
  opacity/width for ordinary and right angles); adjacent arcs at a vertex
  are separated by different `arc_size_px` (steps of 6–10 px) and, for
  multi-tick classes, `arc_shift_px`.
- Labeled figure → auto label placement + angle-radius automation on by
  default (§6/§7); motion → dynamic placement (§8.2).
- Do not silently add theorem decorations the user didn't ask for (e.g. no
  right-angle marks unless a perpendicular is part of the request or needed
  for readability).

## 2. Environment setup

```bash
python3 -m venv venv               # Python 3.11–3.14; prefer 3.12/3.13.
./venv/bin/pip install animageo    # pulls numpy, manim, pycairo, sympy, scipy
./venv/bin/python -c "import animageo, manim; print('ok')"
```

Notes:

- If Python 3.14 gives manim/PyAV import or build errors, recreate the venv
  with 3.13/3.12 and report that.
- `pycairo`/`av` need native libs (cairo, pkg-config, ffmpeg). On macOS:
  `brew install cairo pkg-config ffmpeg`; on Debian/Ubuntu:
  `apt install libcairo2-dev pkg-config ffmpeg`.
- **Labels need LaTeX** (manim `Tex`): check `latex --version` and
  `dvisvgm --version`. If there is no LaTeX toolchain, either install a small
  TeX distribution (e.g. TinyTeX/BasicTeX + `dvisvgm`, `standalone`,
  `preview` packages) or generate the figure without visible labels and
  report the limitation.
- MP4 rendering needs `ffmpeg` in PATH.

When in doubt about an API detail, don't guess from training data — run a
tiny smoke test (build a scene with two points and a segment, export an
SVG per §3.1) and inspect the result before writing the real script.

## 3. Canonical script skeletons

### 3.1 Static image (SVG — no manim CLI needed)

```python
from manim import config
config.pixel_width, config.pixel_height = 800, 600   # match export size

from animageo.animageo import AnimaGeoScene

W, H = 800, 600

class Figure(AnimaGeoScene):
    def construct(self):
        self.putCode('''
            A = Point(0, 0)
            B = Point(6, 0)
            C = Point(2, 4)
            tri, AB, BC, CA = Polygon(A, B, C)
            style(A, B, C, label_visible=True)
        ''')
        self.fitView(W, H, padding=40)   # frame the construction (see §4)
        self.exportSVG('figure.svg')

Figure().construct()   # direct call is enough for static export
```

Run: `./venv/bin/python figure.py`. For a PNG preview of an SVG use
`rsvg-convert` / `cairosvg`, or render the same scene through manim with
`-s` (saves the last frame as PNG):
`./venv/bin/python -m manim -sql figure.py Figure`.

`exportPDF('f.pdf')`, `exportEPS('f.eps')`, `exportTikZ('f.tex')`,
`exportJSXGraph('f.html')` work the same way as `exportSVG`.

### 3.2 Animation (MP4 via manim CLI)

```python
from manim import config
config.pixel_width, config.pixel_height = 1920, 1080

from animageo.animageo import AnimaGeoScene

W, H = 960, 540         # export canvas; keep the same aspect as pixel size

class Anim(AnimaGeoScene):
    def construct(self):
        t = self.addVar('t', 0.0)                 # variables can drive DSL geometry
        self.putCode('''
            A = Point(0, 0)
            B = Point(6, 0)
            C0 = Point(2, 4)
            M = Midpoint(A, B)
            C = Rotate(C0, t, M)                 # C moves; dependent objects follow
            tri, AB, BC, CA = Polygon(A, B, C)
            med = Segment(C, M)
            style(A, B, C, label_visible=True)
            style(med, stroke="color.accent", stroke_width_px="line_width.bold")
            hide(C0, AB, BC, CA)                 # tri draws the outline as one object
        ''')
        self.fitView(W, H, padding=40)   # BEFORE HideAll: fit measures visible elements
        self.autoPlaceLabels(dynamic=True)

        self.HideAll()
        self.playShow(['A', 'B', 'C'])            # fade in points (+labels)
        self.playShow(['tri'], mode='Create')     # draw the outline
        self.playShow(['M', 'med'], mode='Create')
        self.wait(0.5)

        with self.animating(t):
            self.play(t.animate.set_value(0.8), run_time=2)
        self.autoPlaceLabels()                    # snap final frame after EMA motion
        self.clearLabelTracker()
        self.wait(1)
```

Run: `./venv/bin/python -m manim -qm --disable_caching anim.py Anim`
(`python -m manim` works in every environment; a bare `manim` binary may be
missing from the venv). The MP4 path is printed at the end
(`media/videos/...`).

Resolution note: setting `config.pixel_width/height` in the script
**overrides** the `-ql`/`-qm`/`-qh` preset resolution (and the output folder
name follows it, e.g. `1080p15`). For fast draft iterations comment the
`config.pixel_*` lines out and use `-ql`; put them back (or just render
once at full size) for the final pass. Always take the MP4 path from
manim's own output.

**Key ordering rules (violations are the top cause of broken output):**

1. `putCode` your whole static construction first, then `fitView`, then
   `HideAll()` and staged reveals. `fitView` must run while elements are
   visible — it measures rendered mobjects.
2. If your animation *moves* geometry, the static fit at t=0 may not contain
   the motion. Either (a) temporarily add invisible "extent" points at the
   extreme positions before `fitView` (`E1 = Point(...)`, `hide(E1)` after
   fitting), (b) use a larger `padding`, or (c) set the viewport explicitly
   (§4). Check the final frames.
3. End with `self.wait(1)` so the video doesn't cut off instantly.

## 4. Viewport and framing (why your first render is often blank)

A DSL-only scene has **no meaningful default viewport**. If you skip the
`fitView` step, everything renders microscopic or off-screen. This is the
single most common failure. Symptoms → fix:

- Blank/near-blank image → you never fitted the view. Use `fitView`.
- Giant letters and dots covering everything → you called `applyStyle` with
  `content={'source': 'rendered_bounds'}` but **without**
  `reference={'size': {...}}`, or you passed `reference={'size': [w, h]}`
  (always use the dict form `{"size": {"width": w, "height": h}}`), or you
  forgot `updateAllGeometry()` after `applyStyle`.
- Figure correct but small in a corner → you did one pass instead of two.

Explicit viewport (alternative to auto-fit — full control, best when motion
range is known or you plot functions in a specific window):

```python
scene = AnimaGeoScene()
w, h, scale = 800, 600, 46        # scale = pixels per math unit
scene.style.export['ptUnit'] = scale
scene.style.export['ptWidth'] = w
scene.style.export['ptHeight'] = h
scene.style.export['ptXZero'] = w / 2   # pixel x of math origin
scene.style.export['ptYZero'] = h / 2   # pixel y of math origin (y down)
scene.applyStyle(export={"size": {"width": w, "height": h}})
scene.putCode('...')              # note: putCode AFTER applyStyle here
```

With the explicit viewport, `applyStyle` comes *before* `putCode` and no
second pass is needed. Choose `scale` so the construction spans ~70–85% of
the canvas.

**Unbounded curves break auto-fit.** When the scene's main object is
unbounded — a parabola/hyperbola, a function graph, a full `Line` — `fitView`
frames the *sampled extent of the curve*, and the semantic core (focus,
vertex, directrix, an intersection) collapses into a few pixels (a verified
failure mode: focus and vertex merge into one dot). For such scenes either:

- use the **explicit viewport** above, choosing the window from the semantic
  core (e.g. vertex ± a few focal lengths for a parabola), or
- fit on extent points: add 2–4 visible `Point`s marking the window you
  actually want, `fitView(...)`, then `hide(...)` them.

Bounded figures with one helper line are fine — this applies when the
unbounded object dominates the picture.

When loading a **GeoGebra file** none of this is needed — the .ggb carries
its own viewport:

```python
self.loadGGB('scene.ggb', style='style.json',
             export={'size': {'width': 800, 'height': 600}})
```

## 5. Construction DSL reference

`scene.putCode(code)` executes `code` in the DSL namespace;
`scene.loadCode('file.py')` does the same from a file. The DSL is ordinary
Python (loops, `if`, `def`, comprehensions, f-strings, `lambda`, kwargs) with
these rules:

- **Assignment registers the element under the variable name**:
  `A = Point(0, 0)` creates element "A". In loops/functions names
  auto-uniquify (`p, p_2, p_3`); use `name=f"P_{i}"` for explicit names.
- **Tuple-unpack multi-output commands**:
  `tri, AB, BC, CA = Polygon(A, B, C)`; `P, Q = Intersect(circ, line)`.
  Only unpack when the configuration guarantees that many outputs.
- **`Intersect` index is 1-based** and the order is a stable contract:
  `P = Intersect(a, b, index=1)` is the same point as the first element of
  the tuple-unpack. For a unique intersection just `D = Intersect(l1, l2)`.
- **Arithmetic on element proxies builds dependent geometry**:
  `D = A + t*(B - A)` is a point on AB; `E = C + (C - A)` extends AC beyond
  C; `v = B - A` is a vector-like value. Use this for ratios, extensions,
  homothety (`A1 = O + k*(A - O)`).
- **Field access is live**: `A.x`, `A.y`, `circ.center`, `circ.radius`,
  `seg.length`, `ang.size` (radians). Use `.data.value` to read a Measure's
  number.
- Math names are available without import: `pi`, `sqrt`, `sin`, `cos`,
  `tan`, `atan2`, `abs`, `math`.
- **Forbidden** (raises): `import`, `open`/`eval`/`exec`, augmented
  assignment `+=`, walrus `:=`, chained `a = b = c`, leading-underscore
  names. Manim scene methods are not available inside DSL code.
- Style helpers inside DSL: `style(el1, el2, key=value, ...)`,
  `hide(el, ...)`, `show(el, ...)`, or attribute form
  `A.style.stroke = '#ff0000'`.

### Factory quick reference (verified signatures)

Points, lines, basic shapes:

| Call | Meaning |
|---|---|
| `Point(x, y)` | free point |
| `Segment(A, B)` / `Ray(A, B)` / `Line(A, B)` | through two points |
| `Line(P, l)` | line through P **parallel** to line/segment l |
| `PerpendicularLine(P, l)` | line through P ⟂ l (also `OrthogonalLine`) |
| `PerpendicularBisector(A, B)` / `(seg)` | midpoint perpendicular (also `LineBisector`) |
| `AngularBisector(P, V, Q)` | bisector of angle PVQ — **vertex is the middle arg** |
| `Midpoint(A, B)` / `Midpoint(seg)` | midpoint |
| `Circle(O, r)` / `Circle(O, P)` / `Circle(A, B, C)` | radius / through point / circumcircle |
| `Semicircle(A, B)` | on diameter AB (CCW from A to B) |
| `CircleArc(O, P, Q)` | arc of circle centered O from P CCW to Q |
| `CircumcircleArc(A, M, B)` | arc through 3 points (M in the middle) |
| `CircleSector(O, P, Q)` | filled sector |
| `Polygon(A, B, C, ...)` | polygon; returns `poly, side1, side2, ...` |
| `Polygon(A, B, n)` | **regular n-gon on side AB**; returns `poly, sides..., new_vertices...` e.g. `tri, AB, BC, CA, C = Polygon(A, B, 3)` |
| `Vector(A, B)` | drawable arrow A→B |
| `Angle(P, V, Q)` | angle mark at vertex V (middle argument!) |
| `Locus(tracked_point, driver_point)` | locus curve |

Derived/semantic:

| Call | Meaning |
|---|---|
| `Intersect(a, b)` / `(a, b, index=k)` | works for every pair: line/segment/ray/circle/arc/conic/function/implicit |
| `Tangent(P, circle_or_conic)` | 1 tangent if P on the curve, else `t1, t2 = ...` |
| `Tangent(line, conic)`, `Tangent(P, func)`, `Tangent(c1, c2)` | tangents parallel to a line; tangent to `y=f(x)` at `x(P)`; common tangents of two circles (up to `t1..t4`) |
| `Polar(P, circle_or_conic)` | polar line |
| `Centroid(poly)`, `Incircle(A, B, C)`, `Trilinear(A, B, C, x, y, z)` | triangle helpers (`Trilinear` = point at trilinear coords `x:y:z`; `1,1,1` → incenter) |
| `Center(circle_or_conic)`, `Radius(c)` | center point / radius measure |
| `Rotate(P, angle, O)` | rotate P by angle (radians, CCW) around O; also rotates lines/vectors |
| `Translate(obj, v)`, `Reflect(P, line)` / `Mirror(...)`, `Dilate(obj, k, O)` | transforms; `Reflect(P, circle)` = inversion; `Dilate` = homothety (factor may be a slider) |
| `ClosestPoint(path, P)` | nearest point on a line/segment/ray/circle |
| `Distance(A, B)`, `Length(seg)`, `Area(poly)`, `Perimeter(poly)`, `Slope(line)` | measures (numeric proxies) |
| `Direction(line)`, `UnitVector(v)`, `PerpendicularVector(v)`, `Dot(u, v)`, `Cross(u, v)` | vector helpers (`Cross` = 2D scalar) |
| `AngleSize(P, V, Q)` | angle value without drawing a mark |
| `Ellipse(F1, F2, a)`, `Hyperbola(F1, F2, a)`, `Parabola(F, directrix)` | conics from foci |
| `Conic("x^2 + y^2 = 4")`, `Conic(P1..P5)` | from equation / five points |
| `Function("y = x^2 - 1")` or sugar `f(x) = x^2 - 1` | explicit function graph; a number defined earlier is a live parameter (`a = 1` then `f(x) = a*x^2` — animate `a`, the graph follows; same for `Conic("…")`/`ImplicitCurve("…")`/`Line("y = a*x + 1")`); so are point coordinates `x(A)`, `y(A)` (`f(x) = y(A)*x` turns with `A`) and other functions (`h(x) = f(x) + 1`); `*` may be left out (`2x`, `k x`, `(x + 1)(x - 1)`); `f(3)` is the live value at x = 3 |
| `ImplicitCurve("(x^2+y^2)^2 = 8*(x^2-y^2)")` | implicit curve F(x,y)=0 |
| `Focus(K)`, `Vertex(K)`, `Axes(K)`, `Directrix(K)`, `MajorAxis(K)`, `MinorAxis(K)`, `Eccentricity(K)` | conic anatomy (tuple-unpack where plural) |

Homothety: `Dilate(P, k, O)` (or proxy arithmetic `O + k*(P - O)`).
Unknown factory names raise `NameError` — never invent commands; if
something is missing, build it from primitives and note the substitution.

### Correctness rules

- **Encode requested relations by construction, never by convenient
  coordinates.** A chord's endpoints must lie on the circle *by dependency*
  (rotate a known circle point, or intersect a line with the circle) — not
  by hand-picked coordinates that merely look right. The figure must stay
  correct if a free point moves.
- Free points: pick generic, nondegenerate positions (avoid accidental
  right angles / equal sides / symmetry unless requested).
- Deterministic points only: do not use `Point()` with no args, or
  `Point(circle)` / `Point(seg, t)` point-on-object forms. Instead: point on
  circle = `Rotate(known_point_on_circle, angle, O)`; point on segment =
  `A + t*(B - A)`.
- Don't nest constructions inside calls (`Intersect(l, Segment(B, C))` —
  bad): assign every object to a name first, then use the name. Duplicated
  inline geometry pollutes the graph and the picture.
- `Angle(P, V, Q)` takes **points** (vertex in the middle), not
  lines/segments. The mark is drawn from arm VP counter-clockwise to VQ —
  if the mark appears on the wrong side (e.g. the reflex side), swap P and Q.
  Geometric symmetry does NOT imply symmetric argument order: in a pair of
  mirror-image marks one of the two calls typically needs the reversed
  order (check both numerically: `scene.element('a1').data.size`).

## 6. Making the figure readable (marks, labels, emphasis)

These are construction semantics, not decoration — apply them when the
concept is part of the request:

Use AnimaGeo's native marks. Do not draw angle arcs, right-angle boxes, or
equality ticks manually with manim `Line`/`Arc`/`VGroup`; manual overlays do
not participate in geometry updates, exports, auto-radius, or label
placement.

**Right angles** (perpendiculars, altitudes, tangent-radius):

```python
alt = PerpendicularLine(C, AB)
H = Intersect(alt, AB)
CH = Segment(C, H)
ra = Angle(B, H, C)                    # vertex = the foot H
style(ra, right_angle_marker=True, label_visible=False)
hide(alt)                              # show the finite segment, not the helper line
```

**Equal segments / equal angles — tick marks.** Same `tick_count` = same
equality class; different classes get different counts:

```python
style(AM, MB, tick_count=1)            # AM = MB
style(BC, CD, tick_count=2)            # another equal pair
a1 = Angle(B, A, D); a2 = Angle(D, A, C)
style(a1, a2, tick_count=1)            # bisector evidence: two equal angles
```

Adjacent angle marks at one vertex (common with bisectors): same equality
class = same `tick_count`; separate the arcs by `arc_size_px` steps of
6–10 px, and widen multi-tick spacing with `arc_shift_px`:

```python
a1 = Angle(B, A, E); a2 = Angle(E, A, D)
style(a1, a2, tick_count=1, label_visible=False)
style(a1, arc_size_px=26); style(a2, arc_size_px=34)
```

Keep ordinary angles and right angles in the same color/thickness system
unless the user asks for a contrast. If the request is about marks rather
than angle values, set `label_visible=False` on the angle elements.

**Labels.** Label what the user named and the key results; keep helper
points unlabeled (`label_visible=False`) or hidden entirely. Subscripts and
Greek letters need explicit LaTeX label text in math mode, with backslashes
escaped for Python:

```python
style(A, B, C, label_visible=True)
style(T1, label_visible=True, label_text="$T_1$")
style(alpha_mark, label_text="$\\alpha$")
```

One `label_text` per style call (labels differ → separate calls).

**Showing values** (lengths, angles, areas): put the value on the drawable
element itself via `label_mode` — segments show their length, angles their
degrees, circles their radius, polygons their **area**, vectors their norm:

```python
style(ang, label_visible=True, label_mode="value")          # → 63.4°
style(seg, label_visible=True, label_mode="label_value")    # → a = 3.61
style(poly, label_visible=True, label_mode="label_value", label_text="S")
                                                            # → S = 25.5
```

Semantics: `"value"` shows the number only (**`label_text` is ignored** in
this mode); `"label_value"` renders `<label_text or name> = <value>`. On an
`Angle` mark, `label_mode="label_value"` with no `label_text` prints the
DSL variable name — so naming the marks `AOB` and `ACB` yields the
canonical theorem labels `AOB = 80.0°`, `ACB = 40.0°` for free. A
polygon's value label anchors at its centroid — if a named point sits there
(e.g. the diagonal intersection of a parallelogram), the two labels collide
and the auto-placement solver does not deconflict polygon labels; shift the
area label manually:
`style(poly, label_offset_px=[60, 30], label_placement_locked=True)`.

Standalone `Measure` objects (`Area(...)`, `Distance(...)` assigned to a
name) are numeric proxies, not drawable text — prefer `label_mode` on the
drawable element itself. Don't assign plain Python strings to top-level DSL
names (`lbl = f"..."` logs a warning — every top-level assignment tries to
register a construction element); inline the string into the `style(...)`
call instead.

**Emphasis tokens** — pass token strings, they resolve through the style
system: `stroke="color.accent"`, `stroke_width_px="line_width.bold"`,
`size_px="point_size.bold"`, `fill="color.accent"` (points use `fill`, not
`stroke`, for their body color). Helpers: `stroke="color.aux"`,
`stroke_width_px="line_width.aux"`, or `stroke_dash_ratio=0.5` for dashed
(`stroke_dash_period_px` sets dash + gap in style px; default `rendering.dash_period_px`, 10;
SVG export writes one path with `stroke-dasharray`).
Raw values work anywhere a token does: `stroke="#2e7d32"`, `size_px=9` —
use them when a figure needs more distinct colors than the palette has
(e.g. medians vs altitudes vs circle), keeping them consistent within one
figure.

**Circles and filled regions.** A `Circle` (incl. `Incircle`) may render
with an opaque fill by default, punching a white hole in a polygon fill
under it. For an outline-only circle set `style(circ, fill_opacity=0)`;
for a translucent disc use `fill_opacity=0.2`.

**Touchpoint recipes** — both are instances of principle 1 (relations by
construction) and principle 4 (hide the scaffolding):

- Incircle touchpoint = foot of the perpendicular from the incenter to the
  side line: `T1 = Intersect(PerpendicularLine(I, lab), lab)` with
  `lab = Line(A, B)` named first; hide `lab` and the perpendicular.
- Tangent points from an external point: `Intersect(Tangent(P, c), c)` is a
  double root — numerically fragile if P animates. The robust classical
  form is the Thales circle: `thales = Circle(Midpoint(P, O), P)`, then
  `T1, T2 = Intersect(c, thales)`; draw `Segment(P, T1)`/`Segment(P, T2)`,
  hide the helpers.

**Manual label nudge.** If one label lands badly, shift it:
`style(T2, label_offset_px=[0, -14])` — pixels, x to the right, y **up**
(negative y moves the label down). When the auto-placement solver is
enabled (§7 preset or `autoPlaceLabels`), it **overrides** manual offsets —
pin a hand-placed label with
`style(T2, label_offset_px=[16, -4], label_placement_locked=True)`; the
solver then leaves that one alone. Labels of a loaded `.ggb` keep the place the
GeoGebra applet gave them (next to the same part of the element, at any export
scale) unless the solver is enabled.

**Polygon vs explicit sides.** `Polygon(...)` draws boundary segments too.
If individual sides carry different meaning (one side highlighted, sides
split by feet…), prefer explicit `Segment` per side and skip the polygon, or
keep the polygon only as a fill (`style(tri, fill="color.light",
fill_opacity=0.3)`) with its own sides as the outline.

If the polygon itself is the object being constructed/revealed, animate the
returned polygon (`tri`, `quad`, ...) as one object with `mode='Create'`
and hide the returned side elements (`hide(AB, BC, CD, DA)`) unless they
are needed for labels/ticks or separate emphasis — otherwise you get
duplicate borders and duplicate reveal animations.

**Automatic label placement** — after fitting the view, one call declutters
all labels: `scene.autoPlaceLabels()`. Treat this and the §7
`overlay.label_placement` block as **mandatory for any labeled figure**:
without the tuned solver, labels can land badly wrong (on top of other
points, far from their element), not merely suboptimal — a verified
failure mode.

For animations with staged reveals or moving geometry, use
`scene.autoPlaceLabels(dynamic=True)` after `fitView` and before
`HideAll()`/`playShow(...)`. In dynamic mode, label placement is a scene
policy: newly shown labels should appear in solved positions, and labels
should keep following moving geometry during `animating(...)`/`addUpdater`.
Do not hand-roll label offsets, temporary visibility passes, or dummy
trackers in user scenes; if a local version does not sync labels on
visibility changes, prefer upgrading/fixing AnimaGeo, or as a temporary
compatibility fallback re-run `autoPlaceLabels(dynamic=True)` at reveal
phase boundaries and verify the first frames.

## 7. Style JSON

`applyStyle(style=...)` / `loadGGB(style=...)` accept a path or a dict.
User JSON deep-merges over the packaged baseline. All `*_px` values are
pixels on the reference canvas — resolution-independent. A compact,
good-looking starting style (tweak the palette to taste):

```python
STYLE = {
    "presets": {
        "color": {
            "main": "#1a1a1a", "accent": "#d05456", "aux": "#8a8a8a",
            "light": "#d6e5f6", "accent_light": "#f6e0db",
        },
        "point_size": {"main": 7, "bold": 9, "aux": 5},
        "line_width": {"main": 1.8, "bold": 2.8, "aux": 1.0},
        "font_size":  {"main": 16, "bold": 18, "aux": 13},
        "angle_radius": {"main": 20, "right": 16, "shift": 3},
    },
    "overlay": {
        "label_placement": {
            "enabled": True, "repair_iterations": 6,
            "respect_current_position": True, "point_bisector": True,
            "geom_gap_px": 2.0, "viewport_clamp": True,
            "declutter_labels": True, "label_gap_px": 2.5, "w_assoc": 3.0,
            "dashed_overlap_factor": 0.3, "continuous_placement": True,
            "cluster_consistency": True, "compact_labels": True,
            "angle_marker_obstacle": True,
            "dynamic_angles": True, "canonicalize_anchor": True,
            "solver_every_n_frames": 1, "ema_alpha": 0.45,
            "anchor_flip_frames": 8, "keyframe_snapshots": True,
        },
        "angle_radius": {
            "enabled": True, "min_px": 20,
            "max_arm_fraction": 0.52, "apply_to_right": True,
        },
    },
}
...
scene.fitView(800, 600, style=STYLE)         # fit + apply in one call
```

`fitView` keeps the scene's current style when `style=` is omitted, so you
can also `applyStyle(style=STYLE, ...)` once and call plain
`fitView(W, H)` afterwards.

**Sizing principles (proportions, not absolute values).** All `*_px` sizes
are pixels on the reference canvas (the W×H you pass to `fitView`), so what
makes a figure comfortable is the ratios. For a ~800×600 reference canvas:

| Family | main | Anchor ratio |
|---|---|---|
| `line_width` | 1.5–2 | base unit; bold ≈ 1.6×, aux ≈ 0.6× |
| `point_size` | 6–8 | 3.5–4.5 × line width (≈1% of canvas width) |
| `font_size` | 14–17 | 2–2.5 × point diameter |
| `angle_radius` | 17–20 | 1.0–1.2 × font size; `right` ≈ 0.85 × main |

- Keep the family ratios when changing anything: giant dots on thin lines,
  arcs dwarfing their arms, or labels shouting over the figure are all
  broken-ratio symptoms.
- A figure that reads "small with huge dots" is a **framing** problem
  (construction spans too little of the canvas — fix `fitView`/padding for
  a 70–85% span), never a reason to inflate point sizes.
- Video at 1920×1080: keep the reference canvas small (e.g. `W, H = 960,
  540`) and let `config.pixel_*` scale the output; the preset above then
  needs no changes.
- Dense figure → step the label/point system down one notch (aux values);
  sparse slide figure → scale everything up together rather than any one
  family. One dial for that:
  `applyStyle(content={'prominence': 1.25, ...})` multiplies every
  decoration size (points, strokes, fonts, arcs) without touching geometry
  or layout.
- Narrow angles: don't hand-shrink `arc_size_px` per angle — the
  `overlay.angle_radius` block in the starter style above auto-scales the
  arc into the arms (`min_px`/`max_arm_fraction` clamps), and the label
  solver tracks the resolved radius automatically.

Per-type / per-name rules go in `overlay`:

```python
"overlay": {
    "per_type": {"segment": {"stroke_width_px": 2.2},
                 "point": {"size_px": 7}},
    "per_name": {"med": {"stroke": "presets.color.accent"}},
}
```

Priority (low→high): builtin defaults → your JSON `defaults` →
`overlay.per_type` → `overlay.per_name` → explicit `style(...)`/
`elem.style` writes in DSL. So DSL `style(...)` always wins.

## 8. Animation reference

### 8.1 Staged reveal (the "construction story")

```python
self.autoPlaceLabels(dynamic=True)              # after fitView, before hiding
self.HideAll()                          # after fitView!
self.playShow(['A', 'B'], run_time=0.8)          # fade-in
self.playShow(['AB'], mode='Create')             # draw along the stroke
self.playShade(['helper1'])                      # gray out
self.playRestore(['helper1'])                    # back to normal
self.playHide(['helper1'])                       # fade out
self.wait(0.5)                                   # pause between steps
```

`playShow(names, mode='Fade'|'Create', run_time=...)` plays one combined
animation for the listed element names (a point's label appears with it).
Reveal in dependency order: points → lines/circles built on them → marks.
Use `mode='Create'` for strokes (segments, circles, arcs), `'Fade'` for
points, filled regions, angle marks, labels.

For animations with labels, enable `autoPlaceLabels(dynamic=True)` once after
the view is fitted and before the staged reveal begins. Do not add manual
label-updater code to the user scene; `playShow`/`playHide` should preserve
the auto-placement policy. If the construction later moves, keep the tracker
active through the motion, then call `autoPlaceLabels()` and
`clearLabelTracker()` after the last movement to make the final still frame
exact.

For elements created mid-flight, `self.putCode('X = ...', show=False)` adds
them hidden; reveal with `playShow(['X'])`.

### 8.2 Continuous motion — animated variables

Any lowercase name in DSL code can be driven by a scene variable:

```python
t = self.addVar('t', 0.0)                    # BEFORE or AFTER putCode — both work
self.putCode('P = Rotate(P0, t, O)', show=False)   # P slides along the circle
self.playShow(['P'])
with self.animating(t):                      # rebuilds construction every frame
    self.play(t.animate.set_value(2*pi), run_time=4)
```

- Point along a circle: `Rotate(point_on_circle, t, center)`.
- Point along a segment: `P = A + t*(B - A)` with t in [0, 1].
- **Move a "free" point between positions**: define hidden anchor points and
  interpolate — `A0 = Point(0, 0)`, `A1 = Point(1.5, 0.8)`,
  `A = A0 + t*(A1 - A0)`, `hide(A0, A1)`. With `t: 0 → 1 → 0` the whole
  construction deforms and returns. Pick target positions that keep the
  configuration nondegenerate throughout the motion (e.g. a triangle stays
  acute if feet must stay on the sides).
- If the user asks to "move point D" at the end of a construction animation,
  define `D` from one or more `addVar` variables in the DSL and animate those
  variables. Do not manually call `geo.update('D', ...)` or rewrite point
  coordinates frame by frame.
- Everything depending on the moving point follows automatically —
  that's the whole point of the dependency graph.
- Several sequential `self.play(...)` calls inside one
  `with self.animating(t):` block are fine (e.g. there and back).
- Several trackers can animate simultaneously inside nested `animating`
  contexts or one `with self.animating(t):` block with a multi-animation
  `self.play(t.animate.set_value(1), s.animate.set_value(2), run_time=3)`
  (only trackers wrapped by `animating`/`addUpdater` rebuild geometry).
- Labels follow their elements. For dense scenes call
  `self.autoPlaceLabels(dynamic=True)` before the motion to re-solve label
  positions per frame (EMA-smoothed), and `self.clearLabelTracker()` after.
  Even so, inspect the final frame: an angle's value label rides its
  bisector and can end up crossed by a chord/radius in unlucky end
  positions — pin that one label
  (`label_offset_px=[...], label_placement_locked=True`) or end the motion
  a few degrees away.
  Works with both `addUpdater(t)` and the `with self.animating(t):` wrapper
  (the latter is just addUpdater + clearUpdater). With the static solver enabled a label
  may re-resolve to the other side of its point between rebuilds during
  motion; if that looks jumpy, pin that label
  (`label_placement_locked=True`, §6) or use the dynamic tracker.
- Angle/length values shown with `label_mode="value"` update per frame
  automatically (fast DecimalNumber path). Note: static export strips
  trailing zeros ("2"), animated frames use fixed decimals ("2.0") — not a
  bug.

### 8.3 Keyframe animation (JSON-driven)

For "move things through these states" scenarios:

```python
independents = self.get_independent_elements()   # dict: what CAN be animated
self.play_keyframes({
    "keyframes": [
        {"t": 0, "values": {"cx": 2.0, "x": 35}},
        {"t": 2, "values": {"cx": 4.0, "x": 110}, "easing": "smooth",
         "show": ["med"], "hide": ["helper"]},
        {"t": 4, "values": {"cx": 2.0, "x": 35}},
    ]
})
```

Style tracks (v2): add `"version": 2` and per-keyframe `"styles"` to animate
element styles between keyframes — colors (`stroke`/`fill`/`label_color`,
hex only), opacities, `stroke_width_px`, `size_px`, `font_size_px`, arc/tick
sizes, `label_offset_px`, `label_text`, and discrete props (`point_shape`,
`label_anchor`, `label_visible`, `tick_count`, `z_index`). Values are
the target state at that keyframe (carry-forward); `null` reverts to the
element's pre-animation style. Styles may target any element by name, not
just independents. Discrete props switch at the middle of the transition;
colors blend perceptually (Oklab); `stroke_dash_ratio` lerps continuously
between numbers and only snaps (at mid-transition) when one end is `null`;
`stroke_dash_period_px` lerps like any pixel size.
`label_text` is a discrete swap too — the label's text changes at
mid-transition (like `label_visible`), it does not cross-fade or morph
glyph-by-glyph. Colours must be hex (`#rrggbb`) to blend — a non-hex baseline
(e.g. a named colour) snaps instead of blending. With `keyframe_snapshots`
label auto-placement enabled, the pre-pass now applies each keyframe's
`styles` (font/arc size, `label_visible`, …) before measuring label bboxes,
so label positions track those style changes correctly.

```python
self.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "values": {"x": 0},  "styles": {"c1": {"fill_opacity": 0.0}}},
    {"t": 2, "values": {"x": 90}, "styles": {"c1": {"fill_opacity": 0.6,
                                                    "stroke": "#d05456"}}},
    {"t": 3, "styles": {"c1": {"stroke": None}}},
]})
```

Visibility & effects (v2): per-keyframe `"visible": {name: bool}` is an
absolute map (the element's visibility at that keyframe); `"show"`/`"hide"`
arrays are v2 sugar that fold into it. Appearance/disappearance plays an
entrance/exit effect timed INSIDE the keyframe interval, at its exact
duration — v2 drops the legacy extra 0.4 s that v1 injects per show/hide
batch. Set the effect per-keyframe via `"enter"`/`"exit"` maps
(`{name: {"effect": ..., "duration": ..., "at": ...}}`, or a bare effect
string). Entrance effects: `fade` (default), `none`, `create` (progressive
stroke draw), `grow` (scale from center), `write` (progressive glyph reveal —
text/labels only). Exit effects: `fade` (default), `none`, `uncreate`,
`shrink`. A top-level `"defaults": {"easing":, "enter":, "exit":}` sets the
fallback effect for keyframes that don't specify one (`write` is accepted in
`defaults.enter`, same as per-keyframe `enter`; it stays rejected for
`defaults.exit`/`exit` since it is an entrance-only effect).

```python
self.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "visible": {"c1": False}},
    {"t": 1.5, "visible": {"c1": True},
     "enter": {"c1": {"effect": "create", "duration": 0.8}}},
    {"t": 3, "visible": {"c1": False}, "exit": {"c1": "fade"}},
]})
```

**What counts as animatable differs by origin — check
`get_independent_elements()` first:**

- **DSL-built scenes: only `addVar` variables are independents.** A DSL
  `A = Point(0, 0)` is command-created and is NOT keyframable by name.
  To move DSL points via keyframes, route their coordinates through vars
  (verified pattern):

  ```python
  cx = self.addVar('cx', 2.0)
  cy = self.addVar('cy', 4.0)
  self.putCode('C = Point(cx, cy)')     # C follows the vars
  ...
  self.play_keyframes({"keyframes": [
      {"t": 0, "values": {"cx": 2.0, "cy": 4.0}},
      {"t": 2, "values": {"cx": 4.0, "cy": 3.0}, "easing": "smooth"},
  ]})
  ```

- **GGB-loaded scenes**: free points and on-path points from the .ggb are
  independents directly. Values: free point `[x, y]`; point on circle
  `{"tparam": radians, "direction": "short"|"cw"|"ccw"}`; point on
  segment/line `{"tparam": t}`; number/angle: float; boolean: bool.

Easing: `linear`, `smooth` (default), `in`, `out`, `in_out`, plus 12 more —
the full 17-name set is a lossless port of the web preview's easing, so the
same `"easing"` value renders identically in the web UI and the exported
video. Evocative ones worth knowing: `ease_out_bounce`, `ease_out_elastic`,
`ease_out_back` (springy overshoot), `rush_into`/`rush_from` (sharp
accel/decel), plus `ease_in_sine`/`ease_out_sine`/`ease_in_out_sine`,
`ease_in_cubic`/`ease_out_cubic`/`ease_in_out_cubic`, and `smootherstep`.

`scene.get_element_states()` returns a read-only snapshot
`{name: {type, visible, style}}` for every non-axis element — current
visibility and resolved animatable style values (colors, opacities, sizes,
label props). Symmetric to `get_independent_elements()`; handy for building a
keyframe-state inspector UI or diffing state before/after a keyframe edit.

**Construction reveal & labels (v2):** for "build up the whole figure in
dependency order" scenes, `reveal_construction(lag=0.3, duration=0.5)` is a
one-call macro — it walks every element in topological order, picks a
sensible per-type entrance effect (points fade, lines/circles/curves
`create`, text/labels `write`), staggers each element's start by `lag`
seconds, and plays the generated v2 keyframes (or pass `play=False` to get
the keyframes back without playing them, e.g. to inspect or splice into a
larger sequence):

```python
self.reveal_construction(lag=0.3, duration=0.5)
```

Pass `effect="create"` (or any single `ENTER_EFFECTS` name) to force one
effect for every element instead of the per-type default.

```python
self.reveal_construction(lag=0.3, duration=0.6, effect="create")
```

**Camera keyframes (v2 only):** `values["@camera"]` is a reserved
pseudo-element — not a construction element — that animates the viewport via
`{"center": [x, y], "width": w}` (either or both; carry-forward like any other
value). This is a **cinematic** pan/zoom of `camera.frame`: geometry AND
pixel-sized decorations (point radii, font sizes, stroke widths) scale
together with the zoom — it is NOT GeoGebra's pixel-invariant `ZoomIn` (where
points keep their on-screen size). `center`/`width` are in math coords
(same units as the construction, not pixels). Using `@camera` under
`"version": 1` (or with no version) raises `ValueError`.

```python
self.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "values": {"@camera": {"center": [0, 0], "width": 14}}},
    {"t": 2, "values": {"@camera": {"center": [1, 1], "width": 6}}},
]})
```

**Emphasis events (v2 only):** per-keyframe `"events": [{...}]` play a
one-shot, self-restoring emphasis on one or more targets inside the
interval leading up to that keyframe — the scene is byte-identical once the
event completes (nothing is left mutated in `elem.style` or the
construction). Effects: `indicate` (a scale+colour pulse on the target,
`scale` controls the pulse size), `flash` (radial flash lines at the
target), `circumscribe` (a temporary box drawn around the target). Each
event is `{"effect":, "targets": [names], "at":, "duration":}` plus optional
`"color"`; `targets` is a list of element names, `at`/`duration` are seconds
measured from the start of the keyframe interval (not the whole timeline).
`passing_flash` is not available yet (rejected with a clear error).

```python
self.play_keyframes({"version": 2, "keyframes": [
    {"t": 0},
    {"t": 2, "events": [
        {"effect": "indicate", "targets": ["B"], "at": 0.4, "duration": 0.6},
        {"effect": "circumscribe", "targets": ["poly"], "at": 0.4, "duration": 0.6},
    ]},
]})
```

**Static single-frame preview:** `scene.apply_keyframes_at(keyframes_data, t)`
places the scene at playhead time `t` without playing an animation — apply
keyframe/style/camera state at exactly `t` (clamped to the sequence's time
range), rebuild, and update the mobjects. Idempotent (safe to call repeatedly
at different `t`). Useful for a server-side "render this timestamp as a still":

```python
scene.apply_keyframes_at(keyframes_json, t=1.25)
scene.exportSVG("frame_at_1.25.svg")
```

### 8.4 The moving-camera trap

The viewport is fitted to the *static* construction. If motion swings
geometry outside it, the moving parts leave the frame (verified failure
mode). Budget the fit for the full motion range (§3.2 rule 2), and always
inspect the *last* frames, not only the first.

## 9. Verification protocol (do all of this before reporting success)

```bash
./venv/bin/python -m py_compile scene.py
./venv/bin/python -c "import scene"                    # imports clean?
./venv/bin/python -m manim -ql --disable_caching scene.py MyScene   # draft
```

**Verify geometry numerically before rendering** — element data is readable
from the scene: `scene.element('AB').data.length`,
`scene.element('M').data.coords`, `scene.element('ang').data.size`
(radians). Named measures (`s = Area(poly)`, `d = Distance(A, B)`) live in
a separate registry — `scene.element('s')` returns `None`; read them via
`scene.geo.var('s').data.value` (or `scene.geo.objectByName(name)` which
checks both registries). Assert the
requested relations (equal lengths, point on circle, perpendicularity) in
your build script; a construction that is wrong numerically will not become
right visually. To probe a var-dependent construction at several parameter
values without playing an animation:
`tracker.set_value(x); scene.updateVar(tracker)` rebuilds the geometry, then
read the elements.

**Numeric frame checks (mandatory if you cannot view images).** If you have
no way to actually look at the rendered PNG, verify the framing numerically
after `fitView`/`applyStyle` — the viewport mapping is readable from
`scene.style.export`:

```python
exp = scene.style.export
def to_px(xy):                     # math coords -> canvas pixels
    return (exp['ptXZero'] + xy[0] * exp['ptUnit'],
            exp['ptYZero'] - xy[1] * exp['ptUnit'])
```

Assert, for the *semantically key* points (named vertices, focus, vertex,
touchpoints — not curve samples):

1. every key point lands inside the canvas with a margin:
   `pad <= px <= ptWidth - pad` (same for `py`, `pad` ≈ your padding);
2. no two key points that must read as distinct are closer than ~10 px
   (a verified failure: auto-fit on a parabola put focus and vertex < 3 px
   apart — the figure was numerically correct and visually meaningless);
3. the key points span a healthy share of the canvas: with
   `sx = x_extent / ptWidth` and `sy = y_extent / ptHeight` of their
   bounding box, expect `max(sx, sy)` ≈ 0.5–0.9 for a compact figure (for
   scenes dominated by an unbounded curve, apply the check to the semantic
   core and see §4).

If a check fails, fix the framing (§4: explicit viewport or extent points)
before exporting — do not report success on assertions about coordinates
alone.

Then extract and **look at** frames (take the MP4 path from manim's own
output — the quality folder name, e.g. `480p15`/`600p15`, depends on your
`config.pixel_*` values):

```bash
ffmpeg -y -i <printed .mp4 path> -vf "select=eq(n\,10)" -vframes 1 f_early.png
ffmpeg -y -ss <mid seconds> -i <printed .mp4 path> -vframes 1 f_mid.png
ffmpeg -y -sseof -0.3 -i <printed .mp4 path> -vframes 1 f_last.png
```

Checklist for every frame you inspect (and for exported SVGs, converted to
PNG):

- Not blank; the construction fills a reasonable share of the canvas.
- Points are small dots (a few px), not giant disks; labels are readable
  text near their elements, not covering the figure — if not, re-read §4.
- Everything the user asked for is visible; helpers are subdued or hidden.
- Labels don't sit on top of lines/each other (use `autoPlaceLabels`).
- For animations: the first frame shows the intended initial state; motion
  stays in frame; the final state is correct. For staged reveals, inspect a
  frame after labels first appear but before any motion starts — labels must
  already be auto-placed, not only corrected once a variable animation begins.

Report at the end: files created, exact render command, Python/animageo/
manim versions, which APIs you used, and any deviations or limitations.

## 10. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Blank or microscopic output | No viewport fit for a DSL scene → use `fitView` (§3/§4) |
| Gigantic dots/letters over everything | Manual fit: `rendered_bounds` without dict-form `reference` size, or missing `updateAllGeometry()` after `applyStyle` → just use `fitView` |
| Figure small in a corner | Manual fit with one pass instead of two → use `fitView` (two passes by default) |
| `NameError: name 'X' is not defined` in DSL | Factory doesn't exist (invented name) or lowercase var never added via `addVar` → check §5 inventory |
| `DSLSyntaxError` | You used `import`/`+=`/walrus/chained assignment in DSL code |
| Label renders as garbage/missing | LaTeX not installed, or `label_text` without `$...$`, or unescaped backslash (`"\\alpha"`, not `"\alpha"`) |
| Angle mark on the wrong side / reflex | Swap the outer args: `Angle(Q, V, P)` |
| Equal-angle arcs or double ticks visually merge | Use native `Angle` options: separate `arc_size_px`; for multi-tick angle marks increase `arc_shift_px` (§6) |
| Two coincident borders on polygon sides | `Polygon` + explicit side segments both drawn → hide one (§6) |
| Polygon outline appears as separate side animations | Animate the `Polygon(...)` result itself with `mode='Create'`; do not reveal its sides unless they have separate meaning (§6/§8.1) |
| Labels correct themselves only when motion starts | Dynamic label placement is not syncing on visibility changes → use/fix scene-level `autoPlaceLabels(dynamic=True)` support; avoid hand-written label offsets (§6/§8.1) |
| White hole in a filled polygon under a circle | Circle's default opaque fill → `style(circ, fill_opacity=0)` (§6) |
| `play_keyframes`: "'A' is not an independent element" | DSL points aren't keyframable by name → route coords through `addVar` vars (§8.3) |
| Element appears instantly instead of animating | It was created visible — `putCode(..., show=False)` then `playShow` |
| Moving object exits the frame | Static fit doesn't cover motion range (§8.4) |
| Parabola/function fills the canvas, focus & vertex merge into one dot | Unbounded curve dominated `fitView` → explicit viewport or extent points (§4); catch it with the §9 numeric frame checks |
| `manim: command not found` | Use `./venv/bin/manim`, or `./venv/bin/python -m manim` |
| Render extremely slow with many value labels | Keep `rendering.fast_value_labels` on (default); avoid per-frame `Tex` label churn |

## 11. Worked sketch — the user asks for a nine-point circle

How the principles compose on a real request (structure, not a full
listing):

```python
self.putCode('''
    A = Point(0, 0); B = Point(7, 0); C = Point(2.2, 4.6)   # generic, nondegenerate
    MA = Midpoint(B, C)                                     # ... MB, MC likewise
    lBC = Line(B, C)
    altA = PerpendicularLine(A, lBC)
    HA = Intersect(altA, lBC)          # foot BY CONSTRUCTION (principle 1)
    segA = Segment(A, HA)              # show the finite segment, not the line
    H = Intersect(altA, altB)          # orthocenter; EA = Midpoint(A, H) ...
    nine = Circle(MA, MB, MC)          # the result, through three of the nine
    raA = Angle(B, HA, A)
    style(raA, right_angle_marker=True)
    style(A, B, C, label_visible=True)
    style(nine, stroke="color.accent", stroke_width_px="line_width.bold")
    hide(lBC, altA, altB)              # scaffolding sweep (principle 4)
''')
```

Then: `fitView` → `autoPlaceLabels()` → `HideAll()` → staged `playShow` in
dependency order (triangle → altitudes with right-angle marks → midpoints →
Euler points → the circle with `mode='Create'`) → vertex motion routed
through `addVar` variables (§8.3). Feet, midpoints and the circle all
follow the vertices because the construction is a dependency graph. Fit the
view generously (§8.4) so the motion stays in frame.

---

## Further reading

If you hit something this guide does not cover:

- Source & full documentation: <https://github.com/ivaleo/animageo>
  (`docs/index.md` is the map; `docs/api.md`, `docs/python_dsl.md`,
  `docs/keyframes.md`, `docs/styles.md` are the main references).
- Package index: <https://pypi.org/project/animageo/> (changelog:
  <https://github.com/ivaleo/animageo/blob/main/CHANGELOG.md>).
- Project homepage: <https://animageo.ru/>.
