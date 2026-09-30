# Known Pitfalls and Gotchas

This file records non-obvious behaviors of manim, Python, and AnimaGeo internals
discovered during development and testing. Keep them in mind when extending the
library.

---

## manim

### `Mobject.set_default` accumulates a partialmethod chain — never call it in a hot path

`cls.set_default(**kwargs)` in manim executes
`cls.__init__ = partialmethod(cls.__init__, **kwargs)`. Reading `cls.__init__`
from the class goes through the `partialmethod.__get__` descriptor and returns
the compiled `_method` function, not the `partialmethod` object itself — so the
built-in flattening of nested partialmethods never triggers, and every call
adds another wrapper layer. Calling it on every render (as `setStyle` used to
do) grows the chain depth linearly; after ~1000 calls in a single long-lived
process, any construction of `MathTex`/`Tex`/`Text` fails with
`RecursionError`. The symptoms look unrelated: points and labels silently
disappear (per-element recovery in `_render_*`), `autoPlaceLabels` fails (bbox
measurement goes through Tex), value labels break (`DecimalNumber` in manim
0.20 builds glyphs via `mob_class=MathTex`).

**Rules:**

1. Never call `set_default` in code executed on every render. It has been
   removed from `setStyle`; label color is passed explicitly (`col_label` in
   `_build_render_ctx` → `create_label`).
2. If a global default is genuinely needed (scripts, examples) — set it once
   per process, or make the call idempotent: first `cls.set_default()` (reset
   to `_original__init__`), then `cls.set_default(color=...)`.
3. `set_default()` with no arguments fully restores the original `__init__` —
   the test fixtures rely on this
   (`tests/test_mobject_default_leak.py`).
4. A `Tex` created with an explicit `color=` may return `None` from the
   top-level `get_fill_color()` — check the actual glyph color via
   `family_members_with_points()`.

### `tex_template` only works in the constructor — `.set(tex_template=…)` does nothing

`Tex.__init__` compiles the LaTeX **immediately**: if `tex_template` is not
passed as an argument, `config["tex_template"]` is used. Assigning it after the
constructor — `Tex(s).set(font_size=…, tex_template=RusTex)` — merely stores an
attribute on the already-compiled object and has **no effect** on the render.
Labels used to be built exactly this way in `create_label`: the template looked
like it was passed, but compilation ran under manim's stock non-Cyrillic
template, and any Cyrillic label took the whole element down
(`CreateMObject failed` → both the marker and the label vanished).

**Rules:**

1. `tex_template` is a constructor argument only.
2. The Cyrillic-capable template is installed as the global default once at
   scene initialization: `ui.install_cyrillic_tex_template()` (called from
   `AnimaGeoScene.__init__`). This is NOT `Mobject.set_default` — it is a
   plain idempotent assignment to `config.tex_template`, so no partialmethod
   chain accumulates. A caller-installed (non-stock) template is left alone.
3. A failed label compilation must not take the element down:
   `ui._compile_label_tex` degrades LaTeX → escaped plain text → `None` (the
   element is drawn without a label), and `_measure_label_bbox` estimates the
   bbox in that case.

### Cyrillic in math mode compiles to nothing

This is worse than an error: `$Б$` under `T2A` compiles **successfully** and
draws nothing — the math alphabet has no Cyrillic glyphs. Symptoms: a label
`$Б_1$` showed a lone "1", and a chunk silently disappeared from the text
`Отрезок $БВ$ равен`. Reproducible both in manim (latex→dvisvgm) and in the
TikZ export (pdflatex).

**Rule:** wrap Cyrillic runs inside `$…$` in text mode —
`geo.lib_elements.textify_cyrillic` (`$Б$` → `$\text{Б}$`; under a subscript
also braced: `$A_{\text{Б}}$`, otherwise `_\text` would consume only the
command). Applied in `correctedLabel`, `_render_text`, and TikZ
(`TikzContext.label_text`, `emit_text`). Cyrillic already typed in text mode is
left alone — it renders as-is. The JSXGraph export is unaffected: its labels go
through MathJax, which does have Cyrillic in math mode.

### Rendering an external scene script through the manim CLI

`python3 -m manim ...` may resolve to a Python interpreter that does not have
`manim` installed. A reliable command to render a standalone scene script
locally:

```bash
PYTHONPATH=/path/to/animageo manim scene.py MyScene -ql --format=png --media_dir /tmp/animageo_render
```

If you need to run pytest or other checks against the same Python that has
manim installed (Homebrew on macOS):

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 -m pytest ...
```

### An updater on the animated object never sees intermediate values

If `add_updater(func)` is attached to the same `ValueTracker` that is animated
via `.animate.set_value()`, then inside `func` a call to `mob.get_value()`
(where `mob` is the parameter passed in by manim) returns only the initial and
final values, never the intermediate ones. The reason: during an animation
manim creates copies of the start/end states of the object and calls the
updater on those copies, not on the interpolated original.

**Working approaches:**

1. **Sentinel object** (used in `play_keyframes`): the updater lives on a
   separate invisible `Mobject`, and the `ValueTracker` is read through a
   closure:
   ```python
   progress = ValueTracker(0)
   sentinel = Mobject()
   def on_frame(mob):
       t = progress.get_value()  # closure — reads the original
       ...
   sentinel.add_updater(on_frame)
   self.add(progress, sentinel)
   self.play(progress.animate(...).set_value(1), ...)
   ```

2. **Closure instead of the parameter** (used in `addUpdater`): the updater is
   on the tracker, but it reads the closed-over variable, not the `mob`
   parameter:
   ```python
   tracker.add_updater(lambda v, self=self: self.updateVar(tracker))
   #                                                       ^^^^^^^ closure, not v
   ```

**Does not work:**
```python
tracker.add_updater(lambda v: do_something(v.get_value()))
#                              ^^^^^^^^^^^ v is a copy, not the original
```

### Polygon does not support become()

In manim, `become()` does not work correctly for `Polygon` (flicker, broken
animation). `updateGeoElements` therefore handles polygons via remove + add
rather than `become()`. This is a known manim behavior, not an AnimaGeo bug.

The remove + add must not change layer order: the effective manim `z_index`
additionally gets a micro-offset based on the element's position in the
construction. This preserves ordering within a single tier (`Z_STROKE`,
`Z_POINT`, etc.) both in static renders and during MP4 animation.

---

### A dash is a stroke property — keep it on the mobject, not in the path

Since 1.7.10 a dashed stroke is the solid case's single VMobject carrying an
`animageo.dash.DashPattern` in the private attribute `_ag_dash` (MU, fixed when
the mobject is built). Whoever strokes the path applies it: `svg_parser`
(SVG/PDF/EPS) and `DashCamera`, the scene's video camera. Three traps:

- manim's `Mobject.__getattr__` synthesises `get_*`/`set_*` names, so the
  pattern is never exposed as `mobject.get_dash()`; use the module functions
  `animageo.dash.get_dash(m)` / `set_dash(m, pattern)`.
- `become()` copies points and colours but no custom attributes (nor
  `cap_style`); `updateGeoElements` carries the pattern and the cap in the same
  family loop as `z_index`. Any new `become()` path must do the same, or a
  solid ↔ dashed change never reaches the drawn line.
- cairo (and SVG) restart the pattern on every subpath. A curve drawn as many
  small pieces reads as solid: `_render_implicitcurve` dashes the stitched
  polylines (`curve_sampling.stitch_segments`), not the marching-squares cells.
  Do not use manim's `DashedLine`/`DashedVMobject` — they cut the path into one
  mobject per dash, which exports as a heap of `<path>` elements.

---

## Label placement

### `dynamic_angles=true` does nothing by itself

The flag `overlay.label_placement.dynamic_angles=true` marks angles for
bisector tracking, but something must actually call
`compute_angle_label_center` every frame. Two supported ways to enable that:

1. **`play_keyframes` with `keyframe_snapshots=true`** — `on_frame` triggers
   the recomputation automatically.
2. **`scene.autoPlaceLabels(dynamic=True)`** — installs a `LabelTracker`, and
   `updateVar` (fired on every tracker change inside `addUpdater`) rewrites
   the offsets.

If only `dynamic_angles=true` is set, without either of the above, angles stay
static as before. This is intentional: the option is cheap to enable in the
config, while the cost of per-frame work is an explicit choice of integration
point.

### MC canonicalization is off by default

`canonicalize_anchor=true` rewrites labels to `label_anchor='MC'` with a
compensating offset. This eliminates anchor jumps during interpolation between
keyframes, but breaks the snapshot tests in `test_loadggb_snapshot.py` — they
pinned `label_anchor='BC'/'ML'/...` from the older solver. The default is
therefore `false`; enable it only when smooth dynamics matter.

### The Tex bbox cache is module-level, not per-scene

`_bbox_cache` in `label_placement.py` is a process-wide dict keyed by
`(label_text, font_size)`. When `font_size` changes in `GeoStyle` between two
scenes in the same process, the cache is reused correctly (the key includes
`font_size`). But if you swap the TeX template (`RusTex`) in memory by hand —
call `clear_bbox_cache()`. `play_keyframes` does this automatically at the
start of the snapshot pass.

### `overlay.angle_radius` is off by default

`compute_effective_arc_size_px` (shared between the renderer and label
placement) applies the `(pivot_rad / angle) ** exp` scaling + clamps only when
`overlay.angle_radius.enabled=true`. The default is `false` — byte-for-byte
GGB import is preserved and the snapshot tests keep passing.

Enable it deliberately: with `enabled=true` the visual size of every angle arc
in the scene changes (narrow angles get bigger, wide ones smaller). For a
targeted opt-out use the per-element escape:
`elem.style['auto_radius'] = False`.

### `angle_gap_px` has been removed

The key `overlay.label_placement.angle_gap_px` is no longer read. Use the two
explicit keys instead: `angle_gap_arc_px` for the arc→label gap and
`angle_gap_sides_px` for the sides→label-bbox gap.

---

## GeoGebra import

### `Point(Conic)` must preserve the parameter from the XML coordinates

GeoGebra can create a point on a conic with the command `Point(e)`, where `e`
is a `Conic` (for example, a hyperbola). If the importer does not support
`Point(Conic)`, such a point stays `data=None`, and all downstream commands
(`Line`, `Intersect`, `Segment`, `Distance`, `CircumcircleArc`, `Angle`) break
in a cascade.

Fix: the `point_K` command builds the point on a
circle/ellipse/hyperbola/parabola in the canonical parametrization, and the
GGB parser computes `elem.tparam` from the `<element type="point">`
coordinates. For a hyperbola the parameter is stored as `(branch, t)` to keep
the branch GeoGebra selected.

### `CircumcircleArc(A, M, B)` selects the arc through the middle point

GeoGebra's rule: `CircumcircleArc(A, M, B)` builds the circular arc with
endpoints `A` and `B` that passes through `M`. Relative to the chord `AB`, the
selected arc must therefore lie on the same side of the line `AB` as `M`
(unless `M` lies on the line itself).

A typical implementation mistake: `Arc` stores its range as an unwrapped
interval `[angle_start, angle_end]` where `angle_end` may exceed `2π`, while
the point being tested is computed via `np.angle(...)` in `[-π, π]`. These
values cannot be compared directly: arcs crossing the zero angle start being
wrongly classified as not containing their own middle point. Before comparing,
the point's angle must be lifted into the same unwrapped interval.

### Unicode names in GGB commands must remain direct references

GeoGebra freely uses names like `α` and `β` as labels. If "simple name" is
tested with an ASCII regex, the command `Intersect(β, k, 1)` turns into an
expression through a phantom variable (`_1 = β`), and when that resolution
fails, downstream commands receive `None`.

Rule: after name normalization, `str.isidentifier()` is the systemic check for
a simple Python/DSL identifier. Unicode labels must pass through as ordinary
references to existing elements.

The same kind of construction can also use `Intersect(β, k, 1)` and
`Intersect(β, l, 1)` where `β` is an arc and `k`/`l` are rays. AnimaGeo
therefore supports not only `Arc ∩ Line` but also the indexed intersections
`Arc ∩ Ray` / `Arc ∩ Segment`.

### Labels that are not identifiers, and the degree sign

GeoGebra accepts labels that Python does not, such as `K°`. The name is
normalised the same way in the element and in every expression that uses it:
each character that cannot continue an identifier becomes `_` (`K°` → `K_`),
`'` becomes `_Prime`, and a leading digit gets a `var_` prefix. A degree sign
after a number or a numeric variable that is not such a label is an angle:
`Rotate(A, K°, O)` with a slider `K` rotates by `K` degrees.

### `Point(path, t)` takes GeoGebra's parameter, not `tparam`

With a number `t`, `Point(path, t)` uses GeoGebra's normalised path
parameter: `t` is clamped to `[0, 1]`; on a circle or an ellipse it maps to the
angle `−π … π` from the first axis, on a segment to the fraction from A to B,
on a function graph to the x-range of the view saved in the file. So
`Point(c, 0.25)` on a circle centred at O is the bottom point, not the point
at 0.25 rad. `update_tparam` and keyframe `tparam` values use AnimaGeo's own
parameter (the angle in radians on a circle). On import, a `Point(path, t)`
whose computed position differs from the saved one keeps the saved position
and is reported as `parametric_dependency_frozen`.

### `loadCode` may redefine GGB elements and must rebuild the graph

A script may load a `.ggb` file and then execute a DSL file in which a name is
reused:

```python
E = Rotate(D + Vector(r2, 0), ang2 * deg, D)
```

If in the original `.ggb` the name `E` was a point `Intersect(β, k, 1)` on
which `m = Segment(B, E)` depended, then after the name is redefined the
downstream commands must be recomputed from the new `E`. That is why
`loadCode()` / `putCode()` must be followed by a final
`geo.rebuild(full=True)` before `updateAllGeometry()`; otherwise the render
may pick up stale geometry of the old `m`.

---

## Formulas

These rules apply to function, conic and implicit-curve formulas and to line
equations, both from a `.ggb` file and in the DSL (`Line("y = 2x + 1")`).

### `x(A)` is a coordinate, `x (A)` is a product

`x(` directly before a bracket always reads a coordinate: `x(A)` is A's
x-coordinate, `2x(A)` twice that. `x(x + 1)` is therefore not `x·(x + 1)` —
write `x (x + 1)` or `x*(x + 1)`. With a space, `x (A)` multiplies `x` by the
point `A`, which is not a number, so the curve is not built.

### `π`, `ℯ` and typographic characters

`π` and `pi` are π and `ℯ` is Euler's number in every formula, whatever the
construction calls `pi`, `e` or `E`; `2π`, `πx`, `sin(πx)`, `2ℯ` are products,
like `2x`. `e` is Euler's number only in functions and implicit curves: in a
conic or line equation it is an ordinary name (a number called `e`) — write
`ℯ` or `exp(1)` there. In functions and implicit curves a number named `e`
cannot be used: `e` is always Euler's number there.

The minus sign `−`, `·`, `⋅` and `×` for multiplication and `÷` for division
are read as `-`, `*` and `/`, so a formula copied from GeoGebra's display
parses as it is.

### Asymptotes of periodic functions

A graph is split where its formula is undefined, so no line joins the two
sides of an asymptote. For a periodic function — `tan(x)`, `cot(x)`,
`sec(2x)`, `csc(x − 1)` — those points are taken within 1000 units of the
origin (at most 1000 of each period family); farther out, and where sympy
cannot find them (`tan(x^2)`), the graph is drawn without the split.

### A number named like a math function

`k(x + 1)` with a number `k` is the product `k·(x + 1)`, and numbers named
`E`, `N`, `S`, `O`, `I` work as ordinary names. But a name that is a math
function stays a call before a bracket: with a number `gamma`,
`gamma(x + 1)` is Γ(x + 1). Write `gamma*(x + 1)`.

### Other called names are construction objects

A formula calls only math functions (`sin`, `sqrt`, `exp`, `log`, `abs`,
`floor`, `gamma`, `erf`, …). Any other called name — `g(t)`, `foo(x)` — is an
object of the construction, normally another function. If the construction has
no such object, the curve is not built: the import records
`expression_parse_error`, the DSL logs a warning.

### Size limits

Formula text is limited to 4000 characters. A formula that asks for a huge
exact computation — `7^(9^9)`, `(10^7)!`, `exp(10^9 log(7))`, a conic of
degree 10 000 — is refused, and so is a chain of functions that would inline
into more than 2000 expression nodes; on import both are reported as
`expression_parse_error`. Formulas are still evaluated exactly by sympy, so a
service that parses uploaded files should keep a time limit on loading.

## Python

### Circular import between lib_elements and lib_vars

`lib_elements.py` imports from `lib_vars.py` (`from .lib_vars import *`), and
`lib_vars.py` imports from `lib_elements.py`
(`from .lib_elements import Angle`). This circular import resolves correctly
**only if `lib_vars` is imported first** (as `construction.py` does).

If tests or external code import `lib_elements` first, the result is
`ImportError: cannot import name 'Angle' from partially initialized module`.

**Rule:** always import `construction` (or `lib_vars`) before `lib_elements`:
```python
from animageo.geo.construction import Construction  # first
from animageo.geo.lib_elements import Point, Line   # then
```

### ImportPolicy: DSL strings are parsed in `__post_init__`, not in resolve()

Previously `parse_directive` was called only inside `ImportPolicy.from_dict()`.
As a result, `ImportPolicy(stroke_width_px='quantize:[1,3,6]')` stored the
literal string, and in `resolve_overrides_only` it flowed into
`elem.style['stroke_width_px']` as-is — the downstream manim thickness
conversion then broke (a string instead of a number → lines were not drawn).

Fix: `__post_init__` in `ImportPolicy` runs every field through
`parse_directive`, so DSL strings work identically when loaded from JSON and
when passed directly to the constructor.

**Consequence:** if someone genuinely needs to pass a literal string that
happens to match a DSL prefix (unlikely), it must be wrapped in a callable:
`ImportPolicy(label_color=lambda *_: 'scale:1.5_as_literal')`.

### `elem.ggb_raw` is absent on elements created via the Python DSL

The `ggb_raw` field is populated only by the `.ggb` parser. For elements added
via `loadCode`/`putCode` it stays an empty dict. `ImportPolicy` is therefore a
GGB-only layer: raw-derived rules work on imported elements, while DSL
elements have no source GGB value.

**Fix:** type-level and name-level rules were moved into `StyleOverlay`.
`scene.style_config.overlay.apply(scene)` is called automatically in
`addAllGeometry` and works identically for GGB and DSL via `type(elem.data)`.
For styling on top of the import (per_type/per_name + autoPlaceLabels) —
define `overlay` in JSON. `ImportPolicy` remains for raw-GGB transformations
(`scale:`/`quantize:`/`remap:`).

### Legacy unit bug: JSON angle/dot sizes were multiplied by 0.02 and collapsed

Before the move to canonical `*_px` fields, some scene-level sizes went
through `json_size_to_internal` (× 0.02), and the renderer then divided by
`ptUnit` **again**. On a typical canvas this turned a normal arc radius into a
sub-pixel size, and the arc could collapse into an invisible dot on DSL
scenes.

GGB scenes were unaffected because the parser wrote `arc_size_px` straight
into `elem.style` (bypassing the scene-level `ang_rdefault`). The bug
therefore surfaced only through the Python DSL.

**Fix:** the canonical schema stores sizes as semantic `presets`
(`angle_radius.*`, `point_size.*`, `tick.*`, `arrow.*`) and applies them via
per-type `defaults`. All `*_px` values are interpreted as pixels and converted
at render time according to the target manim parameter: coordinate sizes are
divided by `ptUnit`, while `stroke_width`/`font_size` values go through the
manim scale `* 100 / ptUnit`. See `tests/test_angle_units_regression.py`.

### `tick_width_px` is a stroke width, not a coordinate length

`tick_length_px`, `tick_shift_px`, and `tick_radius_px` participate in the
tick mark's geometry, so they render as coordinate sizes: `px / ptUnit`.

`tick_width_px` is used differently: segment/vector ticks pass it into manim's
`Line(..., stroke_width=...)` or `VMobject.set_stroke(width=...)`. That is the
same unit system as `stroke_width_px`, so the correct conversion is
`stroke_width_to_manim(tick_width_px, ptUnit)`, i.e.
`tick_width_px * 100 / ptUnit`. Dividing by `ptUnit` alone makes the tick
stroke 100× thinner in SVG/export renders. See
`tests/test_style_config_integration.py::TestPixelInvariantDecorations`.

### `python -m animageo` must not import Manim before argument validation

A regular `import animageo` still exports the Manim-backed API. But the CLI
path (`python -m animageo file.ggb`) stays lightweight until the input files
are validated, so that errors like a missing file are reported immediately
without initializing the heavy runtime.

---

## Python DSL

### `putCode`/`loadCode` — exec engine only (short_parser removed)

The DSL used to run through an AST walker (`short_parser.py`) that silently
ignored loops, conditionals, `def`, and kwargs. After the migration,
`short_parser.py` was deleted — only the exec engine (`parsers/dsl/`) remains.
The `engine=` kwarg of `putCode`/`loadCode` was removed as well.

If external code passed `engine='legacy'`, it now gets
`TypeError: got unexpected keyword argument 'engine'`. Drop the kwarg.

### Forward references for lowercase names

A common pattern in a scene script:

```python
self.loadGGB(...)                  # populates A, B, R, Q …
self.loadCode('scene.py')          # scene.py references x
self.addVar('x', 115)              # x gets its value AFTER loadCode
```

The exec engine supports this forward reference for **lowercase** names:
`FactoryDict.__missing__` auto-creates a Var placeholder with `data=None`, the
Command remembers the name, and it resolves during `rebuild`. For uppercase
names — `Rotat` (a typo of `Rotate`) raises at runtime; this is deliberate, to
catch typos.

Formula strings do not take forward references: the names inside
`Function("y = a*x^2")` or `f(x) = a x^2` must already exist when the line
runs. Otherwise the formula refers to nothing, and the element stays
undefined even after `a` is added.

### Backward-compat field aliases removed

The short/abstract names (`.a`, `.c`, `.n`, `.r`, `.v`, `.M`, `.b`, `.x`,
`.dim`, `.angle`, `.original`, `.points`, `.end_points`, `.start_point`) were
fully replaced by descriptive ones (`.coords`, `.center/.offset`, `.normal`,
`.radius`, `.direction`, `.matrix`, `.value`, `.dimension`, `.tparam`,
`.size`, `.source`, `.vertices`, `.endpoints`, `.start`). The aliases are gone
— old code gets an `AttributeError`.

The full list is in [docs/field_names.md](field_names.md). The JSON wire
format of keyframe animation uses `tparam_point` and the `tparam` key.
