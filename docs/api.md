# API Reference

## AnimaGeoScene

The main class — a subclass of `manim.MovingCameraScene`.

### Loading data

| Method | Description |
|-------|----------|
| `loadGGB(filepath, style=None, import_policy=None, debug=False, generate_stubs=True, strict=False, reference=None, content=None, export=None)` | Load a .ggb file, apply a style (optionally through an `ImportPolicy`), and render the geometry. `style` accepts a path, dict or `StyleConfig`; `reference` sets the authoring reference canvas; `content` places the construction onto it; `export` sets the physical output. In non-strict mode unsupported GGB commands land in `scene.geo.command_diagnostics` without cascade warning noise; `strict=True` turns a root unsupported command into an error. `generate_stubs=True` writes `<basename>_stubs.pyi` next to the .ggb |
| `loadCode(filepath, debug=False, show=True)` | Load a Python file with DSL code (exec engine) |
| `putCode(code, debug=False, show=True)` | Execute a Python code string as DSL (exec engine; see [docs/python_dsl.md](python_dsl.md)) |
| `applyStyle(style=None, import_policy=None, reference=None, content=None, export=None)` | Apply a style to the current construction and recompute the layout. Internally: builtin + `style`, then `reference -> content -> export` |
| `fitView(width=800, height=600, *, padding=40, style=None, passes=2)` | Canonical framing for a DSL-built scene: measures the rendered bounds of visible elements and fits them onto a `width×height` canvas with a `padding` px margin. Runs `passes` rounds of `applyStyle(content='rendered_bounds')` + `updateAllGeometry()` (the first round establishes the scale for pixel-sized styles, the second re-measures with point/label sizes already correct). Without `style=` it keeps the scene's current `style_config`. Call it while the relevant elements are visible (before `HideAll()`); for animations leave extra `padding` headroom for the motion |
| `reloadPolicy(import_policy)` | Apply a new `ImportPolicy` without re-parsing the XML (uses the cached `elem.ggb_raw`). Affects GGB elements only |

For the import policy, see the `ImportPolicy` section below and [docs/import_policies.md](import_policies.md).

Unsupported GeoGebra commands are diagnosed in a structured way:

```python
scene.loadGGB('scene.ggb', strict=False)
scene.geo.command_diagnostics
# [{'command': 'Sub', 'signature': ['str', 'AngleSize'],
#   'outputs': ['_3'], 'reason': 'unsupported_signature'}]
```

Commands that received `None` only because of such a root unsupported command
are added as `dependents` to the original diagnostic and are not logged in bulk
as independent problems.

### Layout parameters: `style`, `reference`, `content`, `export`

`loadGGB(...)` and `applyStyle(...)` share the same pipeline:
`style/reference -> content -> export`.

`style` sets the visual style:

| Value | Behavior |
|---|---|
| `None` | builtin style without any user JSON |
| `str` / `PathLike` | path to a style JSON, loaded on top of builtin. A bare preset name (`default`, `book_blue`, `book_green`, `book_purple`, `book_red`) resolves to the packaged preset via `animageo.style.config.resolve_style_input`; an existing on-disk file with the same name always wins |
| `dict` | style JSON passed directly |
| `StyleConfig` | a ready-made configuration; its `source` is used for the backward-compatible `GeoStyle` and the configuration itself for the resolver |

`reference` sets the reference canvas on which the style is considered authored:

| Field | Values | Default / meaning |
|---|---|---|
| `size` | `[width, height]` or `{"width": w, "height": h}`; each side is a positive number, `None` or `"auto"` | runtime override over `style.reference.size`; if unset, the construction's original viewport is used |
| `source` | `"manual"`, `"source_view"`, `"ggb_view"` | metadata in the style JSON: where the reference came from. The actual construction area is selected by `content.source` |

`content` describes which area of the construction to fit into `reference`:

| Field | Values | Default / meaning |
|---|---|---|
| `source` | `"source_view"`, `"ggb_view"`, `"rendered_bounds"`; aliases: `"ggb"` -> `"ggb_view"`, `"bounds"` -> `"rendered_bounds"` | `"source_view"` |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | positive number | only for `fit="manual"`; alias `manual_scale` |
| `anchor` | `"top_left"`, `"top"`, `"top_right"`, `"left"`, `"center"`, `"right"`, `"bottom_left"`, `"bottom"`, `"bottom_right"` | `"center"` |
| `offset` | `[x, y]` in pixels | extra shift applied after the anchor |
| `padding` | number >= 0 | margin in source pixels for `source="rendered_bounds"`; alias `bounds_padding` |
| `infinite_policy` | `"ignore"` or `"clip"` | `"ignore"`: `Line`/`Ray` do not extend the measured bounds; `"clip"`: they are measured after clipping by the current source camera |

`export` describes the physical output canvas:

| Field | Values | Default / meaning |
|---|---|---|
| `size` | `[width, height]` or `{"width": w, "height": h}`; one side may be `None`/`"auto"` | if unset, the size equals `reference.size`; `[auto, auto]` is not allowed |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | positive number | only for `fit="manual"`; alias `manual_scale` |
| `anchor` | the same 9 anchor values as `content.anchor` | `"center"` |
| `offset` | `[x, y]` in pixels | shift of the reference picture inside the export canvas |

When loading a `.ggb`, the parser also carries `<euclidianView>` parameters into
`style.export`: `showAxes`, `showGrid`, `gridIsBold`, `gridType`,
`axesColor`, `gridColor`, `gridDistX`, `gridDistY`, `gridDistTheta`,
`axes.x` and `axes.y`. `addAllGeometry()` uses them for the
`_coordinate_background` layer: the grid is drawn under the geometry, axes and
ticks above the grid but below all construction objects.

### Variables and updates

| Method | Description |
|-------|----------|
| `addVar(name, value)` | Create an animatable variable, return a ValueTracker |
| `addUpdater(tracker)` | Bind a ValueTracker to geometry rebuilds |
| `clearUpdater(tracker)` | Unbind a ValueTracker |
| `animating(tracker)` | Context manager: addUpdater + yield + clearUpdater |
| `updateAllGeometry()` | Rebuild all manim objects from the current geometry |

`animating` example:
```python
x = self.addVar('x', 0)
with self.animating(x):
    self.play(x.animate.set_value(1), run_time=3)
```

### Animations

| Method | Returns | Description |
|-------|-----------|----------|
| `Show(names, mode)` | `[Animation]` | Show elements. mode: `'Fade'` or `'Create'` |
| `Hide(names)` | `[Animation]` | Hide elements |
| `Shade(names)` | `[Animation]` | Shade elements (gray color) |
| `Restore(names)` | `[Animation]` | Restore from shading |
| `Update(names)` | `[Animation]` | Redraw elements |
| `UpdateAll()` | `[Animation]` | Redraw all elements |

Convenience wrappers that auto-run `self.play(...)`:

```python
self.playShow(['A', 'B', 'C'])
self.playHide(['A'])
self.playShade(['B', 'C'])
self.playRestore(['B', 'C'])
self.playUpdate(['a', 'b'])
```

### Keyframe animations

| Method | Description |
|-------|----------|
| `get_independent_elements()` | Return the animatable inputs of the construction for `values`: free points, points on paths, numbers/angles/booleans and variables created via `addVar()` |
| `get_element_states()` | Return `{name: {type, visible, style}}` for all non-axis elements: current visibility and resolved animatable style values; convenient for a keyframe-state inspector UI |
| `play_keyframes(keyframes_data)` | Play a JSON/dict timeline. `"version": 2` enables style tracks, visibility/effects, camera keyframes and events; v1 without `version` is kept for compatibility and deprecated |
| `apply_keyframes_at(keyframes_data, t)` | Statically apply the timeline state at time `t` without `self.play(...)`; useful for a single-frame SVG/PNG preview |
| `reveal_construction(lag=0.3, duration=0.5, effect=None, play=True)` | Generate a v2 timeline revealing elements in dependency order and play it immediately; with `play=False` return the timeline dict |

Short example:

```python
self.play_keyframes({
    "version": 2,
    "keyframes": [
        {"t": 0, "values": {"A": [0, 0]}, "visible": {"a": False}},
        {"t": 2, "values": {"A": [4, 2]},
         "styles": {"a": {"stroke": "#d05456", "stroke_width_px": 4}},
         "visible": {"a": True},
         "enter": {"a": "create"},
         "events": [{"effect": "indicate", "targets": ["A"], "at": 0.4, "duration": 0.6}]},
    ],
})
```

Full format: [docs/keyframes.md](keyframes.md).

### Batch operations

| Method | Description |
|-------|----------|
| `setElementStyle(names, *, update=True, **props)` | Set style properties on several elements at once |
| `setVisible(names, visible, *, update=True)` | Set visibility on several elements |

```python
self.setElementStyle(['a', 'b', 'c'], stroke='#ff0000', fill_opacity=0.5)
self.setVisible(['A', 'B', 'C', 'D', 'E'], False)
```

### Data access

| Method | Returns | Description |
|-------|-----------|----------|
| `element(name)` | `Element` | Construction element by name |
| `mobject(name)` | `Mobject` | Manim object by name |

### Label placement

| Method | Description |
|-------|----------|
| `autoPlaceLabels(dynamic=False)` | Automatically lay out labels. `dynamic=True` installs a `LabelTracker` — subsequent `addUpdater(...)` animations recompute the layout every frame with EMA smoothing and anchor hysteresis |
| `clearLabelTracker()` | Remove the `LabelTracker`. Further `updateVar` calls will not invoke the per-frame solver |

Static invocation (legacy, one-shot — as before):

```python
scene.loadGGB(
    'scene.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
scene.autoPlaceLabels()
scene.exportSVG('out.svg')
```

Dynamic layout under `addUpdater`:

```python
scene.loadGGB(
    'scene.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
x = scene.addVar('x', 0)
scene.autoPlaceLabels(dynamic=True)   # installs the LabelTracker
scene.addUpdater(x)
scene.play(x.animate.set_value(1), run_time=3)
# Angles track their bisector per-frame; other labels smoothly converge to the
# solver output via EMA. With canonicalize_anchor=True all anchors are 'MC',
# with no jumps.
scene.clearUpdater(x)
scene.clearLabelTracker()
```

Configuration lives in `overlay.label_placement` of the style JSON (see [docs/styles.md](styles.md)).

Before playback starts, `play_keyframes()` applies the values, v2 `visible` and
legacy `show`/`hide` from the first keyframe, rebuilds the geometry and updates
the mobjects. So the first rendered frame matches keyframe `0` even if the
saved `.ggb` was in a different editor state. With `keyframe_snapshots=true`
the layout is computed at every keyframe (a pre-pass with state save/restore,
including v2 `styles`), and offsets are interpolated in between. Angles are
additionally tracked per-frame analytically when `dynamic_angles=true`.

### Export

| Method | Description |
|-------|----------|
| `exportSVG(filepath)` | Export the scene to SVG via Cairo |
| `exportPDF(filepath, *, dpi=96.0)` | Export the current frame as a single-page vector PDF. `dpi` governs the physical page size; the default (96) reproduces the on-screen SVG size, and the figure stays vector and can be rescaled with `\includegraphics[width=...]` in LaTeX |
| `exportEPS(filepath, *, dpi=96.0)` | Export the current frame as vector EPS (Encapsulated PostScript). EPS has no transparency — semi-transparent fills are flattened (a warning is logged); use `exportPDF` to preserve opacity |
| `exportTikZ(filepath=None, *, standalone=False, options=None, **kwargs)` | Export the construction as semantic, editable TikZ (native `\draw circle`/`ellipse`/`(a)--(b)`/`arc` primitives, real LaTeX `\node` labels, `\draw plot coordinates` for sampled curves). Returns the TikZ text; `filepath` optionally writes a `.tex` file. `standalone=True` wraps the picture in a compilable `\documentclass{standalone}` document. Pass either an `options=TikZOptions(...)` instance or keyword options (`dpi`, `clip`, `background`, `emit_font_size`, ...) — not both. See [docs/tikz_export.md](tikz_export.md) |
| `exportJSXGraph(filepath=None, *, options=None, **kwargs)` | Export the construction as an interactive JSXGraph board. Transpiles the construction graph (not the rendered frame): free points become draggable, points on curves become gliders, numbers become sliders, and derived elements are recomputed live on drag. Commands with no native JSXGraph creator fall back to static geometry and are listed in a coverage report (logged at INFO). Returns the HTML/JS/JSON text; `filepath` optionally writes `.html`/`.js`/`.json`. Pass either `options=JSXGraphOptions(...)` or keyword options (`output="js"`, `mathjax=False`, `axis=False`, ...) — not both |
| `exportStylePromptSummary(filepath=None, **kwargs)` | Export a compact JSON summary of the construction for AI style-JSON generation. If `filepath` is omitted, returns the dict without writing a file. Format: `animageo-construction-summary/v1`; see [docs/construction_summary.md](construction_summary.md) |

Example:

```python
scene.loadGGB(
    'scene.ggb',
    style='base.json',
    export={'size': {'width': 800, 'height': 600}},
)
summary = scene.exportStylePromptSummary('scene.summary.json')
```

Useful parameters: `include_geometry`, `include_ggb_style`,
`include_style`, `include_resolved_style`, `include_axes`, `max_elements`,
`style_keys`, `source`, `viewport`.

### Utilities

| Method | Description |
|-------|----------|
| `addGrid(x_range, y_range)` | Add a manual coordinate grid |
| `addCoordinateBackground()` | Add the background grid/axes from the GGB `<euclidianView>` |
| `waitCut(msg)` | Pause for video editing with a visual marker |

---

## StyleConfig + resolver

`scene.style_config` (`animageo.style.config.StyleConfig`) is a three-layer configuration:

```python
scene.style_config.presets      # dict — semantic constants (colors/sizes/structures)
scene.style_config.defaults      # DefaultsProfile: per-type baseline in pixels
scene.style_config.overlay       # StyleOverlay: per_type/per_name + automation
scene.style_config.rendering     # dict — low-level render flags
scene.style_config.reference     # dict — authoring reference canvas
```

It is loaded automatically in `__init__` (builtin.json) and reloaded in
`applyStyle(style=...)` with the user JSON/dict deep-merged on top.

```python
from animageo.style.config import StyleConfig
cfg = StyleConfig.load('my_style.json')   # or StyleConfig.load() for builtin-only
cfg.defaults.get('point', 'size_px')       # → 6
```

**Reading a style value.** Instead of `elem.style.get(k, scene.style.X)`, use the unified resolver:

```python
from animageo.style.resolver import resolve, resolved_style, trace

resolve(scene, elem, 'size_px', default=6)   # → value along the priority chain
resolved_style(scene, elem)                  # → dict of all keys (for debugging/snapshots)
trace(scene, elem, 'size_px')                # → ('elem.style', 99) / ('ggb_style', 10) / …
```

Priority chain: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → intrinsic geometry style → default=`. If `import.enabled=false`, the `elem.ggb_style` layer is skipped. References such as `"color.main"` / `"line_width.bold"` are resolved automatically.

`StyleOverlay` is configured through the `overlay` section of the style JSON
(`per_type` / `per_name`). Overlay rules are never materialized into
`elem.style`; the renderer reads them lazily through the resolver during
`applyStyle` / `addAllGeometry`.

---

## ImportPolicy

Dataclass from `animageo.style.import_policy`. Controls how values from a `.ggb` become `elem.ggb_style` during `loadGGB`. Fields accept: `None` (fall back to the base mode), a literal, a callable `fn(raw, defaults, elem)`, or a DSL string (`"const:"`, `"scale:"`, `"quantize:"`, `"remap:"`).

> **Specialization:** `ImportPolicy` is currently recommended for **raw-GGB transformations** (`scale:/quantize:/remap:`). For stylization applied uniformly to GGB and DSL, use `overlay.per_type` / `overlay.per_name` in JSON. See [docs/import_policies.md](import_policies.md) and [docs/styles.md](styles.md).

```python
from animageo.style.import_policy import ImportPolicy

ImportPolicy.faithful()                       # default: as in GGB (backward compat)
ImportPolicy.style_only()                     # everything from style.json, GGB ignored
ImportPolicy.from_dict(cfg)                   # from a JSON dict (e.g. import.policy)
ImportPolicy(size_px=3, font_size_px=14)   # explicit overrides
ImportPolicy(stroke_width_px='quantize:[1,2,4]')   # DSL string (works in the Python API too)
```

**Fields:** `base`, `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap`.

Define per-type/per-name rules (`per_type`, `per_name`) in `overlay`, not in `ImportPolicy`.

**Methods:**

| Method | Returns | Description |
|-------|------------|----------|
| `resolve(elem, defaults, ptUnit)` | `dict` | Full import-style dict (faithful baseline + overrides). Used for diagnostics/compatibility |
| `resolve_overrides_only(elem, defaults, ptUnit)` | `dict` | Only the keys the policy actively overrides; `applyStyle` puts them into `elem.ggb_style` |

A detailed cookbook for 12 scenarios: [docs/import_policies.md](import_policies.md).
Ready-made JSON presets: `examples/policies/*.json`.

---

## Construction

Manages the state of the geometric construction.

| Method | Description |
|-------|----------|
| `add(obj)` | Add an Element, Var or Command |
| `update(name, data)` | Update an element's data |
| `element(name)` | Find an element by name |
| `var(name)` | Find a variable by name |
| `objectByName(name)` | Find an Element or Var by name |
| `rebuild(debug, full)` | Rebuild the construction. `full=True` --- all commands |
| `commandByElementName(name)` | Find the command that creates an element |
| `rename(old_name, new_name)` | Rename an element + update all references in commands + state |
| `add_and_build(cmd)` | Add a command and immediately rebuild only its node (eager mode for the DSL) |
| `update_tparam(name, tparam)` | Update the curve/locus parameter of a constrained point (angle on a circle, linear t on a segment/line/ray) |
| `get_independents()` | Return a dict of independent (animatable) elements for a keyframe UI |

---

## Geometric elements

Elements additionally store `elem.ggb_raw` — a dict of raw GGB values (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color`, etc.). `obj_color` holds the original `r/g/b/alpha` plus the `hex` / `opacity` aliases. It is populated by the parser and consumed by `ImportPolicy` and `reloadPolicy`.

For the full list of field names, see [docs/field_names.md](field_names.md).

### Point
```python
p = Point([x, y])
p.coords     # numpy array [x, y]
p.x, p.y     # float — x and y coordinates
p.style      # StyleProxy{'label_visible': False, 'label_offset_px': [0.5, 0], 'z_index': 50}
```

### Line
```python
l = Line(normal, offset)     # normal·x = offset
l.normal     # unit normal vector
l.direction  # perpendicular to normal
l.offset     # signed distance to the origin
l.contains(point_array)      # membership test
```

### Segment (inherits Line)
```python
s = Segment(p1_array, p2_array)
s.endpoints  # [[x1,y1], [x2,y2]]
s.start      # np.array[0] — first point
s.end        # np.array[1] — second point
s.length     # float
```

### Ray (inherits Line)
```python
r = Ray(start_point, direction_vec)
r.start      # np.array — origin point of the ray
r.direction  # np.array — direction (via Line)
```

### Circle
```python
c = Circle(center, radius)
c.center         # np.array — center
c.radius         # float
c.radius_squared # computed @property: radius²
c.contains(point_array)
```

### Arc, CircleSector (inherit Circle)
```python
a = Arc(center, radius, [angle_start, angle_end])
a.angles        # [start, end] in radians
a.angle_start   # @property over angles[0]
a.angle_end     # @property over angles[1]
```

### Angle
```python
a = Angle(vertex_point, v1_vec, v2_vec)
a.vertex        # np.array — vertex
a.size          # float — magnitude in radians
a.value         # @property synonym for .size
a.side1, a.side2 # side vectors
a.arc_radius    # radius of the drawn arc
a.start_angle   # angle from OX to side1 (radians)
a.end_angle     # angle from OX to side2
```

### Polygon
```python
p = Polygon([[x1, y1], [x2, y2], ...])
p.vertices      # np.ndarray — array of vertices
```

### Vector
```python
v = Vector([[x1, y1], [x2, y2]])
v.endpoints     # point pair [start, end]
v.start, v.end  # @property over endpoints[0/1]
v.direction     # end − start
```

### Measure, AngleSize, Boolean (lib_vars)
```python
m = Measure(value, dimension=0)  # dimension: 0=scalar, 1=length, 2=area
m.value, m.dimension

a = AngleSize(value)             # value in radians
b = Boolean(True)
b.value                          # True / False
```

### Conic

A conic as a 3×3 symmetric matrix. Covers the circle, ellipse,
parabola, hyperbola and degenerate cases (line pairs, point, empty).

```python
from animageo.geo.lib_elements import Conic
from animageo.geo.lib_conic import ConicType

# Four constructors:
c = Conic(matrix_3x3)                         # raw matrix
c = Conic.from_ggb_matrix(A0, A1, A2, A3, A4, A5)  # GGB <matrix> format
c = Conic.from_coeffs(a=1, c=1, f=-1)         # A·x² + B·x·y + C·y² + D·x + E·y + F
c = Conic.from_string("x^2 + y^2 = 4")        # equation parsing (sympy)

# Fields:
c.matrix             # np.ndarray (3×3) — symmetric matrix
c.type               # ConicType.CIRCLE / ELLIPSE / PARABOLA / HYPERBOLA /
                     # INTERSECTING_LINES / PARALLEL_LINES / DOUBLE_LINE /
                     # POINT / EMPTY  (lazy, cached)
c.kind               # @property synonym for .type

# Canonical parameters (None if the type does not match):
c.as_circle()        # (center: ndarray, radius: float)
c.as_ellipse()       # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_parabola()      # {'vertex', 'axis', 'perp', 'focal_parameter'}
c.as_hyperbola()     # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_lines()         # List[Line] for degenerate cases (0, 1 or 2 lines)
c.as_point()         # Point for POINT

# Standard element interface:
c.evaluate(x, y)     # pᵀ·matrix·p — value of the quadratic form at a point
c.contains(pt)       # True if pt lies on the conic
c.translate(vec), c.scale(ratio)
c.equivalent(other)  # matrices are proportional
```

### Function

An explicit function `y = f(x)` backed by sympy. Parsing supports the GGB forms:

```python
from animageo.geo.lib_elements import Function

f = Function.from_string('y = x^2 + 1')
f = Function.from_string('f(x) = sin(x) + cos(2*x)')
f = Function.from_string('i: y = -abs(x) + 4')        # GGB "label:" prefix
f = Function.from_string('m(x) = If[-1 ≤ x ≤ 1, x^2]') # piecewise

# Fields:
f.expr                     # sympy expression of the RHS
f.var                      # sympy Symbol (usually x)
f.source                   # source string (for debug/repr)
# @property: .expression, .variable, .callable — aliases

f(2)                       # numeric, via numpy lambdify (no sympy in the hot path)
f.natural_singularities    # [0.0] for 1/x, [] for polynomials — used by the renderer
                           # to split the x-range at discontinuities
f.sample((-2, 2), n=100)   # (n, 2) array of points
f.translate([dx, dy])      # shift the graph
f.contains([x, y])         # True if y == f(x)
```

Supported expression forms:
- polynomial: `x^2 + 1`, `(x-3)^3`
- trigonometry: `sin(x)`, `cos(x)`, `tan(x)`
- `abs`, `sqrt`, `log`, `exp`, `ln`
- `If[cond, then]` / `If[cond, then, else]` (recursive, with support for
  Unicode `≤`, `≥`, `≠` and chains `-1 ≤ x ≤ 1`)

### ImplicitCurve

An arbitrary implicit curve `F(x, y) = 0`, for when an explicit `y = f(x)` or
a quadratic form does not fit.

```python
from animageo.geo.lib_elements import ImplicitCurve

curve = ImplicitCurve.from_string("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")  # lemniscate
curve = ImplicitCurve.from_string("sin(x) + cos(y) = 0.5")
curve = ImplicitCurve.from_string("sqrt(-4*y) + sqrt(abs(x - 1)) = 5")

# Fields:
curve.expr                 # sympy expression F(x, y)
curve.var_x, curve.var_y   # sympy Symbol for x and y
curve.source               # source string

curve(x, y)                # scalar or vectorized evaluation
curve.contains([x, y])
curve.translate([dx, dy]), curve.scale(ratio)
```

Rendered via marching squares in `curve_sampling.py` (a 128×128 grid over the
viewport), O(grid_n²) work.

---

## Python DSL

Full guide: [docs/python_dsl.md](python_dsl.md). Below is a short summary.

Exec-based engine. Any valid Python code works — loops, conditionals, functions, comprehensions, kwargs, tuple unpacking are all supported. The full set of ~74 factories is auto-discovered from `lib_commands.py`.

```python
# Points and basic constructions
A = Point(0, 0)
B = Point(4, 0)
M = Midpoint(A, B)
s = Segment(A, B)

# Tuple unpacking for multi-output commands
p, s1, s2, s3 = Polygon(A, B, C)
X, Y = Intersect(line1, circle1)

# Arithmetic — registers Add/Sub/Mult/Div commands
D = A + B
v = B - A
E = 2 * A
neg = -A
m = abs(x)

# Loops, conditionals, functions
for i in range(3):
    p = Point(i, 0)        # creates p, p_2, p_3

def triangle(prefix, side):
    A = Point(0, 0, name=f'{prefix}_A')   # explicit name via kwarg
    B = Point(side, 0, name=f'{prefix}_B')
    return A, B

# Field access (via proxy)
x_val = A.x                # float
ctr = circ.center          # np.array
seg_len = s.length         # float

# Styles as attributes
A.style.stroke = '#ff0000'
A.style.size_px = 10
```

### Higher-order curves

```python
# String constructors:
f = Function("y = x^2 + 1")
g = Conic("x^2 + y^2 = 4")
h = ImplicitCurve("sin(x) + cos(y) = 0.5")

# DSL sugar: natural function notation (preprocessor before AST):
#   name(var) = expr   →   name = Function("y = expr")
f(x) = x^2 + 1
g(t) = 2*t + 1            # → g = Function("y = 2*x + 1")

# Geometric conic constructors:
ell = Ellipse(F1, F2, 5)
par = Parabola(F, directrix_line)
conic5 = Conic(P1, P2, P3, P4, P5)
```

### Conic commands (GGB)

Dispatched on the `K` shortcut; they work for every applicable `ConicType`:

```python
O          = Center(conic)                  # center of an ellipse/hyperbola, vertex of a parabola
F1, F2     = Focus(ellipse)                 # 2 points for ellipse/hyperbola
F          = Focus(parabola)                # 1 point
vs         = Vertex(conic)                  # 4 for an ellipse, 2 for a hyperbola, 1 for a parabola
ax1, ax2   = Axes(ellipse_or_hyperbola)     # major and minor axes (Line)
d          = Directrix(parabola)
d1, d2     = Directrix(ellipse_or_hyperbola)
e          = Eccentricity(conic)            # Measure(value, dimension=0)
c_lin      = LinearEccentricity(conic)      # Measure(value, dimension=1)
coeffs     = Coefficients(conic)            # [A, B, C, D, E, F]
P          = Point(conic)                   # point on the conic; GGB import keeps the parameter from the XML coordinates

polar_line = Polar(point, conic)            # pᵀ·matrix
tangent    = Tangent(point_on_conic, conic) # one tangent
t1, t2     = Tangent(external_point, conic) # two tangents via pole-polar duality
```

### Intersections

All pairs of first-class elements (Line/Segment/Ray/Circle/Arc/Conic/Function/
ImplicitCurve) are supported. The `Intersect` command returns a `Point` or a
list of `Point`s (indexable):

```python
# Analytic (Conic):
X, Y    = Intersect(line, conic)       # intersect_Kl: quadratic
A,B,C,D = Intersect(conic1, conic2)    # intersect_KK: pencil + cubic

# Numeric (Function/ImplicitCurve):
X       = Intersect(function, line)    # intersect_Fl: sympy.solve → brentq fallback
J, K    = Intersect(function, conic)   # intersect_FK: 1D via substitution
G, H    = Intersect(implicit, circle)  # intersect_IK: marching squares + Newton
M, N    = Intersect(implicit, line)    # intersect_Il

# Index selection (as in GGB):
A = Intersect(conic, line, index=1)   # first intersection point
B = Intersect(conic, line, 2)         # second
```

The index is always 1-based: `1, 2, ...`. For multi-output the order is the
same: `P, Q = Intersect(a, b)` corresponds to `P = Intersect(a, b, index=1)`
and `Q = Intersect(a, b, index=2)`. The intersection order is stable and is
part of the contract for the DSL, `.ggb` import and export/JSXGraph. For
circles AnimaGeo applies a GeoGebra-like heuristic: points already
participating in the input objects of the circle/second object are matched to
the computed intersections first; the remaining points follow the internal
deterministic order.

A hard cap on the numeric methods guarantees no hangs: 1D scans use
`n_samples=401` points over the range `[-50, 50]`; 2D marching squares uses a
`grid_n=128` × 128 cell grid.
