# Field and style attribute names — cross-layer reference

One reference for every name that appears in animageo:
- **Part 1**: fields of the geometric classes (`Point.x`, `Circle.center`, etc.).
- **Part 2**: element types across 5 layers (GGB XML → animageo class → JSON → manim mobject → SVG).
- **Part 3**: style attributes across the same 5 layers.
- **Part 4**: dictionary enumerations (enum values).
- **Part 5**: measurement units and conversion constants.

For how these names came to be (the pre-1.0 short names and their removal),
see the [History](#history) appendix at the end.

> **How to read a style value.** `elem.style` holds only explicit writes. The full "what will be drawn" answer comes from the resolver:
>
> ```python
> from animageo.style.resolver import resolve, resolved_style
>
> resolve(scene, elem, 'size_px')      # one value along the priority chain
> resolved_style(scene, elem)          # the whole materialized dict
> ```
>
> The chain: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → default=`. Every visual key below may live in `elem.style`, `elem.ggb_style`, `defaults.by_type`, and `overlay.per_type` / `overlay.per_name`; the resolver picks the effective value.

## Part 1. Geometric class fields

### Point (`lib_elements.py:Point`)
| Field | Type | Meaning |
|---|---|---|
| `coords` | `np.ndarray([x, y])` | coordinates (the real field) |
| `x` | `float` | x-coordinate (`@property` over coords[0]) |
| `y` | `float` | y-coordinate (`@property` over coords[1]) |

### Line
| Field | Type | Meaning |
|---|---|---|
| `normal` | `np.ndarray` | normal (unit vector) |
| `direction` | `np.ndarray` | direction (perpendicular to the normal) |
| `offset` | `float` | signed distance to the origin (in the equation `normal·x = offset`) |

### Segment (inherits Line)
| Field | Type | Meaning |
|---|---|---|
| `endpoints` | `np.ndarray` shape (2, 2) | the pair of end points |
| `start` | `np.ndarray` | first point (`@property` over endpoints[0]) |
| `end` | `np.ndarray` | second point (`@property` over endpoints[1]) |
| `length` | `float` | length |

### Ray (inherits Line)
| Field | Type | Meaning |
|---|---|---|
| `start` | `np.ndarray` | ray origin |
| `direction` | `np.ndarray` | direction (via Line) |

### Circle
| Field | Type | Meaning |
|---|---|---|
| `center` | `np.ndarray` | center |
| `radius` | `float` | radius |
| `radius_squared` | `float` | radius² (computed `@property`) |

### Arc, CircleSector (inherit Circle)
| Field | Type | Meaning |
|---|---|---|
| `angles` | `list[float, float]` | the [start, end] angle pair |
| `angle_start` | `float` | `@property` over angles[0] |
| `angle_end` | `float` | `@property` over angles[1] |

### Angle
| Field | Type | Meaning |
|---|---|---|
| `vertex` | `np.ndarray` | vertex (point) |
| `size` | `float` | size in radians |
| `side1` | `np.ndarray` | first side (vector) |
| `side2` | `np.ndarray` | second side |
| `arc_radius` | `float` | radius of the drawn arc |
| `start_angle` | `float` | angle from OX to side1 (radians) |
| `end_angle` | `float` | angle from OX to side2 |
| `value` | `float` | synonym for `size` (`@property`) |

### Polygon
| Field | Type | Meaning |
|---|---|---|
| `vertices` | `np.ndarray` | vertex array |

### Vector
| Field | Type | Meaning |
|---|---|---|
| `endpoints` | `np.ndarray` | the [start, end] point pair |
| `direction` | `np.ndarray` | direction (end − start) |
| `start` | `np.ndarray` | `@property` over endpoints[0] |
| `end` | `np.ndarray` | `@property` over endpoints[1] |

### Measure (`lib_vars.py:Measure`)
| Field | Type | Meaning |
|---|---|---|
| `value` | `float` | numeric value |
| `dimension` | `int` | 0=scalar, 1=length, 2=area |

### AngleSize
| Field | Type | Meaning |
|---|---|---|
| `value` | `float` | size in radians |

### Boolean
| Field | Type | Meaning |
|---|---|---|
| `value` | `bool` | True/False |

### Conic (`lib_conic.py`)
| Field | Type | Meaning |
|---|---|---|
| `matrix` | `np.ndarray` (3×3) | symmetric form matrix |
| `type` | `ConicType` | lazy-computed classification |
| `kind` | `ConicType` | `@property` synonym for `type` |

### Function (`lib_function.py`), ImplicitCurve (`lib_implicit.py`)
| Field | Type | Meaning |
|---|---|---|
| `expr` | `sympy.Expr` | expression: the RHS for `Function`, the zero level `F(x,y)=0` for `ImplicitCurve` |
| `var` (Function) / `var_x`, `var_y` (ImplicitCurve) | `sympy.Symbol` | variable symbols |
| `source` | `str` | original source string (for debug/repr) |
| `_callable` | `Callable` | numpy-lambdified |
| `natural_singularities` (Function) | `list[float]` | finite real discontinuity/undefined points; the renderer splits the curve at them |
| `explicit_domain` (Function) | `tuple[float, float] \| None` | explicit `x` range, when set by the user |
| `expression`, `variable`, `callable` (Function) | — | `@property` aliases for `expr`, `var`, `_callable` |
| `expression`, `x_var`, `y_var` (ImplicitCurve) | — | `@property` aliases for `expr`, `var_x`, `var_y` |

### Var (`lib_vars.py:Var`)
| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | variable name in the Construction |
| `data` | `Any` | value (`Measure`, `AngleSize`, `Boolean`, a number, etc.) |
| `style` | `StyleProxy` | technically present, but variables are not rendered as geometry |

### Element wrapper (`lib_elements.py:Element`, `parsers/dsl/proxy.py:ElementProxy`)
| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | name in the Construction |
| `data` | `Any` | the geometric object |
| `visible` | `bool` | visibility |
| `fixed` | `bool` | not rebuilt during `rebuild` |
| `tparam` | `Optional[float]` | curve/locus parameter of a constrained point (angle on a circle, linear t on a segment/line/ray) |
| `style` | `StyleProxy` | style |
| `ggb_raw` | `dict` | raw GGB values (before ImportPolicy) |
| `ggb_style` | `StyleProxy` | normalized GGB import layer, separate from explicit `style` |
| `_visible` | `bool` | internal visibility storage |
| `_visible_explicit` | `bool` | True after a runtime/DSL change of `elem.visible`; protects it from style layers |
| `_visible_has_value` | `bool` | True when visibility was set by the Construction/GGB/runtime |

### Construction (`lib_elements.py:Construction`) — methods
* `update_tparam(name, tparam)` — update a constrained point's `.tparam` and mark dependents for rebuild

### Construction (`geo/construction.py:Construction`) — main fields
| Field | Type | Meaning |
|---|---|---|
| `phantoms` | `dict` | temporary DSL names like `_1`, `_2` |
| `vars` | `list[Var]` | numeric/boolean/angle variables |
| `elements` | `list[Element]` | geometric elements; contains the hidden `xAxis`, `yAxis` by default |
| `commands` | `list[Command]` | deferred construction commands and dependencies |
| `state` | `dict` | dependency graph: `level`, `inputs`, `outputs`, `input_commands`, `built` |
| `name_mapping` | `dict` | GGB name → normalized Python identifier |
| `naming_counters` | `dict` | DSL-registrar counters for unique names in loops/functions |
| `command_diagnostics` | `list[dict]` | unsupported-command diagnostics |
| `_command_diagnostic_keys` | `set` | internal dedupe for diagnostics |
| `_unsupported_roots_by_output` | `dict` | output → root unsupported command link |
| `strict_unsupported` | `bool` | strict mode: an unsupported root command raises an exception |
| `log_unsupported` | `bool` | log unsupported commands |

---

## Part 2. Element types across 5 layers

Column legend:
- **GGB XML** — tag/attribute in the `.ggb` file (an element inside `<construction>`).
- **animageo class** — Python class in `animageo/geo/lib_*.py`.
- **JSON** — how the type is identified in the style JSON (via `defaults` / `presets` / `import.per_type`).
- **manim mobject** — what `CreateMObject` creates for the type.
- **SVG** — the resulting tag in the SVG output (via Cairo).

| Entity | GGB XML | animageo class | JSON | manim mobject | SVG |
|---|---|---|---|---|---|
| Point | `<element type="point">` | `Point` | `point_size`, `import.point_size`, `per_type: point` | `Circle` (radius) + opt. label | `<circle>` |
| Line | `<element type="line">` + `<coords a,b,c>` | `Line` | `line_width`, `per_type: line` | `Line` (clipped to viewport) | `<line>` |
| Segment | `<element type="segment">` | `Segment` | `line_width`, `tick`, `defaults.segment`, `per_type: segment` | `Line` + tick marks | `<line>` × N |
| Ray | `<element type="ray">` | `Ray` | `per_type: ray` | `Line` (clipped) | `<line>` |
| Vector | `<element type="vector">` | `Vector` | `arrow`, `defaults.vector`, `per_type: vector` | `Arrow` + `CustomArrowTip` | `<path>` |
| Circle | `<element type="circle">` | `Circle` | `per_type: circle` | `Circle` fill + `Circle` stroke (VGroup) | `<circle>` × 2 |
| Arc | `<element type="arc">` | `Arc` | `per_type: arc` | `Arc` + opt. label | `<path>` |
| Sector | `<element type="circlearc">` / `<element type="circlesector">` | `CircleSector` | `per_type: circlesector` | `Sector` + `Arc` + opt. label | `<path>` |
| Angle | `<element type="angle">` + `<arcSize>`, `<decoration>`, `<angleStyle>` | `Angle` | `angle_radius`, `defaults.angle`, `per_type: angle` | `AnnularSector` or `Polygon` (for right angles) + label | `<path>` |
| Polygon | `<element type="polygon">` | `Polygon` | `per_type: polygon` | `Polygon` fill + `Polygon` stroke | `<polygon>` × 2 |
| Conic | `<element type="conic">` + `<matrix A0..A5>` | `Conic` (+ `ConicType` enum) | `per_type: conic` | `Circle`/`Ellipse`/`VMobject` (depending on `.type`) | `<circle>`/`<ellipse>`/`<path>` |
| Function | `<expression type="function" exp="y=…">` | `Function` | `per_type: function` | `VMobject` × N (piecewise sampling) | `<path>` |
| Implicit curve | `<expression type="implicitpoly">` | `ImplicitCurve` | `per_type: implicitcurve` | `VMobject` × N (marching squares) | `<path>` |
| Number | `<element type="numeric">` | `Measure` (inside `Var`) | — | — (invisible) | — |
| Boolean | — | `Boolean` (inside `Var`) | — | — | — |
| Angle size | `<element type="angle">` + value | `AngleSize` (inside `Var`) | — | — | — |
| Label | `<labelMode>`, `<caption>`, `<objColor>` | via `elem.style['label_*']` | `rendering.label_anchor`, `font_size`, `per_name: {...}` | `Tex` (via `create_label`) | `<text>` + `<path>` |

**Command dispatch** (`lib_commands.py`): command name = `{command_name}_{type_shortcuts}`, where the shortcuts are `p=Point, l=Line, r=Ray, s=Segment, v=Vector, c=Circle, C=Arc, S=CircleSector, a=Angle, P=Polygon, K=Conic, F=Function, I=ImplicitCurve, i=int/float, m=Measure, A=AngleSize, b=Boolean, T=str`. Example: `intersect_Kl(conic, line)`, `midpoint_pp(p1, p2)`.

---

## Part 3. Style attributes across 5 layers

Legend:
- **GGB XML** — tag/attribute name in the `.ggb`. `—` when GGB has no equivalent.
- **`elem.ggb_raw[...]`** — key in the raw GGB value dict (before any conversion).
- **`elem.style[...]`** — key in the runtime style dict after parsing/policies.
- **JSON** — where this is set in the style JSON (if at all). Canonical schema: reusable values live in `presets`, per-type application lives in `defaults.<type>.*`.
- **manim kwarg** — the parameter actually passed to the manim constructor.
- **SVG** — the attribute in the resulting SVG.
- **Unit** — measurement unit of the value in `elem.style`.

### 3.0. Style JSON and renderer-config section names

Top level of the style JSON:

| Key | Type | Meaning |
|---|---|---|
| `name` | `str` | optional style name |
| `version` | `number` | user style file version |
| `presets` | `dict` | semantic tokens: colors, sizes, widths, font, tick/arrow structures |
| `defaults` | `{type: {style_key: value}}` | per-type baseline, read by the resolver after the import layer |
| `overlay` | `dict` | post-import overrides and automation |
| `rendering` | `dict` | scene-level render/export settings |
| `import` | `dict` | rules for reading GGB visual values |

`presets` from `builtin.json`:

| Group | Keys |
|---|---|
| `color` | `main`, `light`, `accent`, `accent_light`, `aux`, `black`, `white`, `shade`, `background`, `strong` |
| `point_size` | `main`, `bold`, `aux` |
| `line_width` | `main`, `bold`, `aux` |
| `angle_radius` | `main`, `bold`, `aux`, `shift`, `right` |
| `tick.main` | `tick_length_px`, `tick_width_px`, `tick_shift_px` |
| `arrow.main` | `arrow_length_px`, `arrow_width_px` |
| `font_size` | `main`, `bold`, `aux` |

`defaults` / `overlay.per_type` use the canonical type names:
`point`, `segment`, `line`, `ray`, `vector`, `angle`, `polygon`,
`circle`, `arc`, `circlesector`, `conic`, `function`, `implicitcurve`.
`defaults.decoration` exists in `builtin.json` as a shared helper for tick
presets, but it is not a drawable element type.

`overlay`:

| Key | Subkeys | Meaning |
|---|---|---|
| `per_type` | `<type> → style keys` | rules for all elements of a type, above `elem.ggb_style` |
| `per_name` | `<name> → style keys` | rules for a specific element, above `per_type` |
| `angle_radius` | `enabled`, `exp`, `pivot_rad`, `min_px`, `max_arm_fraction`, `apply_to_right` | auto-scaling of angle arc radii |
| `label_placement` | `enabled`, `distance_px`, `padding_px`, `angle_gap_arc_px`, `angle_gap_sides_px`, `w_anchor`, `w_label`, `w_geom`, `dynamic_angles`, `keyframe_snapshots`, `canonicalize_anchor`, `interpolation`, `ema_alpha`, `anchor_flip_frames`, `solver_every_n_frames` | automatic label layout, incl. keyframe/per-frame modes |

`rendering`:

| Key | Values | Meaning |
|---|---|---|
| `background` | hex or `color.*` | background of the Manim camera, MP4, and SVG export |
| `line_cap` | `butt` / `round` / `square` | default for `stroke_linecap` |
| `right_angle_joint` | `auto` / `bevel` / `miter` / `round` | default for `right_angle_joint` of the right-angle marker |
| `polygon_boundary_layer` | `top` / `null` | raises a polygon's side segments to `z_index=10` |
| `points_display` | `auto` / `only_labels` / `only_points` | global point+label mode |
| `label_anchor` | `TL`..`BR` | scene-wide default label anchor |
| `label_value_precision` | `int` | scene-wide default precision of value labels |

`reference`:

| Key | Type | Meaning |
|---|---|---|
| `reference.width` | `float` | width of the style's reference canvas for preview/export layout |
| `reference.height` | `float` | height of the style's reference canvas |
| `reference.source` | `manual` / `source_view` / `ggb_view` | where the reference canvas comes from; the runtime construction region is set via `content.source` |

`import`:

| Key | Type | Meaning |
|---|---|---|
| `enabled` | `bool` | `false` disables `elem.ggb_style`, `colors`, `point_size`, `line_width`, `policy`; geometry/raw remain |
| `colors` | `{"#hex [opacity]": "preset-or-#hex [opacity]"}` | palette remap of GGB colors |
| `point_size` | `{raw_or_style_size: value}` | remap of point size into `size_px` |
| `line_width` | `{raw_or_style_width: value}` | remap of line thickness into `stroke_width_px` |
| `policy` | `dict` | ImportPolicy fields: `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap` |

### 3.1. Geometric sizes

| Concept | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG | Unit |
|---|---|---|---|---|---|---|---|
| Point diameter | `<pointSize val>` | `point_size` | `size_px` | `point_size.*`, `import.point_size` | `radius = size_px/2/ptUnit` | `r` | px |
| Line thickness | `<lineStyle thickness>` | `line_thickness` | `stroke_width_px` | `line_width.*`, `import.line_width` | `stroke_width = 100*val/ptUnit` | `stroke-width` | px |
| Angle arc radius | `<arcSize val>` | `arc_size` | `arc_size_px` | `angle_radius.*`, `defaults.angle.arc_size_px`, `overlay.angle_radius` | `radius = arc_size_px/ptUnit` (divided by √2 for right angles) | — | px |
| Shift between concentric arcs | — | — | `arc_shift_px` | `angle_radius.shift`, `defaults.angle.arc_shift_px` | — | — | px |
| Tick wave radius | — | — | `tick_radius_px` | `per_name` / `overlay` | `radius` in `round_corners_vmobject` | — | px |
| Right-angle marker size | — | — | `right_angle_size_px` | `angle_radius.right`, `defaults.angle.right_angle_size_px` | `radius` for the Polygon | — | px |
| Equality ticks | `<decoration type>` | `decoration_lines` | `tick_length_px`, `tick_width_px`, `tick_shift_px` | `tick.*`, `defaults.segment`, `defaults.vector` | `length/shift = px/ptUnit`; `tick_width_px → stroke_width_to_manim()` | — | px |
| Arrow head | — | — | `arrow_length_px`, `arrow_width_px` | `arrow.*`, `defaults.vector` | `CustomArrowTip` | — | px |

### 3.2. Stroke and fill (SVG-compatible names)

| Concept | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG |
|---|---|---|---|---|---|---|
| Stroke color | `<objColor r,g,b>` (type-dependent) | `obj_color` | `stroke` | `color.*`, `import.colors`, `import.policy.stroke` | `color` | `stroke` |
| Stroke opacity | `<lineStyle opacity>` | `line_opacity` | `stroke_opacity` | `import.colors` (with opacity), `import.policy.stroke_opacity` | `stroke_opacity` | `opacity` |
| Dash (ratio) | `<lineStyle type>` (>0) | `line_type` | `stroke_dash_ratio` | `import.policy` (DSL) | `dashed_ratio=val, dash_length=0.17` | `stroke-dasharray` |
| Line caps | — | — | `stroke_linecap` | `rendering.line_cap` | `cap_style` | `stroke-linecap` |
| Fill color | `<objColor>` (for angle/polygon/arc/conic/point) | `obj_color` | `fill` | `color.*`, `import.colors`, `import.policy.fill` | `fill_color` | `fill` |
| Fill opacity | `<objColor alpha>` | `obj_color['alpha']` / `obj_color['opacity']` | `fill_opacity` | `import.colors` (with target opacity), `import.policy.fill_opacity` | `fill_opacity` | `fill-opacity` |

### 3.3. Points (shape and GGB preset decomposition)

`import.colors` normalizes the result into separate fields: `stroke` / `fill`
receive only the hex `#rrggbb`, and `stroke_opacity` / `fill_opacity` change
only when an opacity is explicitly given on the right-hand side of the
mapping. For example, `"#1565c0 0.1": "color.accent 1"` turns the color into
`#f15b5b` and sets opacity `1.0`; `"#1565c0 0.1": "color.accent"` keeps the
element's old opacity.

| Concept | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG |
|---|---|---|---|---|---|---|
| Point shape | `<pointStyle val="0..10">` (hard-coupled with fill) | `point_style` (int) | `point_shape` (str enum) | `import.policy.point_shape`, `overlay.per_type.point.point_shape` | `_make_point_mobject` (9 shapes: circle, square, diamond, triangle_\*, cross, plus) | shape-dependent |

The GGB `point_style` code is decomposed into three independent axes (`point_shape`, `fill`/`fill_opacity`, `stroke`/`stroke_width_px`/`stroke_opacity`) via `style/enums.py:_GGB_POINT_STYLE_PATCHES`.

| GGB `pointStyle` | `point_shape` | Fill | Stroke |
|---|---|---|---|
| `0` (filled, black outline — the default) | `"circle"` | color | `#000000`, 1 px |
| `2` (hollow circle) | `"circle"` | none (`fill_opacity=0`) | color, 2 px |
| `10` (filled, no outline) | `"circle"` | color | none (`stroke_opacity=0`) |
| `4` (filled diamond) | `"diamond"` | color | none |
| `5` (hollow diamond) | `"diamond"` | none | color, 2 px |
| `1` (×) | `"cross"` | none | color, 2 px |
| `3` (+) | `"plus"` | none | color, 2 px |
| `6`/`7`/`8`/`9` (▲/▼/▶/◀) | `"triangle_up"` / `"triangle_down"` / `"triangle_right"` / `"triangle_left"` | color | none |

### 3.4. Angles

| Concept | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Which arc to draw | `<angleStyle val="1\|2">` | `angle_style` | `angle_range` (`"minor"` / `"reflex"`) | `import.policy.angle_range`, `overlay.per_name` | selection logic in CreateMObject |
| Right angle (square marker) | auto | — | `right_angle_marker` (bool) | `overlay.per_name` | `Polygon` marker instead of `AnnularSector` |
| Number of arcs/ticks | `<decoration type>` | `decoration_lines` | `tick_count` (int) | `import.policy.tick_count`, `overlay.per_name` | loop in CreateMObject |
| Tick style (for Segment/Vector) | — | — | `tick_style` (`"line"` / `"wave"`) | `overlay.per_name` | `Line` vs `round_corners_vmobject` |
| Arc thickness | `<lineStyle thickness>` (same as lines) | `line_thickness` | `stroke_width_px` | `line_width.*`, `defaults.angle.stroke_width_px` | `stroke_width` |
| Right-angle joint | — | — | `right_angle_joint` | `rendering.right_angle_joint`, `overlay.per_name` / `per_type` | `joint_type` of the right angle's `VMobject` |

### 3.5. Labels

| Concept | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Text | `<labelMode>`, `<caption>` | `label_caption` | `label_text` | `import.policy.label_text`, `overlay.per_name` | `Tex(text)` |
| Text mode | `<labelMode val>` | `label_mode` (`0/1/2/3/9`) | `label_mode` (`label` / `value` / `label_value`) | `import.policy.label_mode`, `overlay.per_type`, `overlay.per_name` | picks `label`, `value`, or `label = value` |
| Value format | — | — | `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator` | `overlay.per_type`, `overlay.per_name`, `import.policy.*` | formats the numeric part |
| Visibility | `<show label>` | `show_label` | `label_visible` | `defaults.<type>.label_visible`, `overlay.per_type`, `overlay.per_name`, `import.policy.label_visible` | (conditional creation) |
| Color | `<objColor>` (the same one) | `obj_color.hex` | `label_color` | `import.policy.label_color` | `color` on `Tex` |
| Font (size) | `<gui><font size>` (scene-wide) | — | `font_size_px` | `font_size.*`, `defaults.<type>.font_size_px`, `import.policy.font_size_px` | `font_size` |
| Anchor | `<labelingStyle>` (scene-wide) | — | `label_anchor` (`"TL"..."BR"`) | `rendering.label_anchor`, `overlay.per_name` | `aligned_edge` in `move_to` |
| Offset | `<labelOffset x,y>` | `label_offset_px` (Y gets inverted) | `label_offset_px` (after Y inversion) | `import.policy.label_offset_px`, `overlay.per_name` | `tex.shift(...)` |
| Radial offset (angle) | — | — | `label_radial_offset_px` | `overlay.per_name` | added to `r` for Angle |
| Frozen position | — | — | `label_placement_locked` (bool) | `overlay.per_name` | skipped by the solver |
| Internal auto-layout flag | — | — | `_auto_placed` (bool, internal) | — | disables the GGB descender correction in `create_label` |

### 3.6. Visibility and layers

| Concept | GGB XML | `elem.ggb_raw` | elem.(style/attr) | JSON |
|---|---|---|---|---|
| Element visibility | `<show object>` | `show_object` | `elem.visible` (wrapper attr) / resolver key `visible` | `import.policy.visible`, `overlay.per_type`, `overlay.per_name`, `defaults.<type>.visible` |
| Z-index | — | — | `elem.style['z_index']` (float) | `rendering.polygon_boundary_layer`, `overlay.per_name` |
| Fill z-index (CircleSector) | — | — | `elem.style['z_index_fill']` | `overlay.per_name` |

### 3.7. GGB Graphics View: grid, axes, background

These fields are read from `<euclidianView>` in `geogebra.xml` and stored in
`scene.style.export`, not in `elem.ggb_style`: they are viewport settings,
not properties of individual geometric objects.

| Concept | GGB XML | `style.export` | Render |
|---|---|---|---|
| Viewport size | `<size width height>` | `ptWidth`, `ptHeight` | camera / SVG size |
| Origin and scale | `<coordSystem xZero yZero scale yscale>` | `ptXZero`, `ptYZero`, `ptUnit`, `ptUnit_ggb`, `ptYUnit_ggb` | camera transform, source view |
| Show axes | `<evSettings axes>` | `showAxes` | enables `_coordinate_background` axes |
| Show grid | `<evSettings grid>` | `showGrid` | enables `_coordinate_background` grid |
| Bold grid | `<evSettings gridIsBold>` | `gridIsBold` | slightly increases the grid thickness |
| Grid type | `<evSettings gridType>` | `gridType` | stored; a Cartesian grid is rendered for now |
| Background color | `<bgColor r g b>` | `background` | stored as hex |
| Axes color | `<axesColor r g b>` | `axesColor` | axis lines, ticks, numbers |
| Grid color | `<gridColor r g b>` | `gridColor` | grid lines |
| Line style | `<lineStyle axes grid>` | `axesLineStyle`, `gridLineStyle` | stored for compatibility |
| X/Y axis | `<axis id="0|1" ...>` | `axes.x`, `axes.y` | per-axis show / numbers / ticks |
| Grid step | `<grid distX distY distTheta>` | `gridDistX`, `gridDistY`, `gridDistTheta` | `distX/distY` set the grid step |

`_coordinate_background` is drawn before the geometry: the grid at
`z_index=-20`, the axes at `z_index=-10`, ticks and numbers at `z_index=-9`.
This is not the same as the built-in `xAxis` / `yAxis` in `Construction`.

---

## Part 4. Dictionary enumerations (enums)

Defined in `animageo/style/enums.py` as `Literal` types + a runtime tuple for validation.

| Type | Values | Where it is used |
|---|---|---|
| `PointShape` | `"circle"`, `"square"`, `"diamond"`, `"triangle_up"`, `"triangle_down"`, `"triangle_left"`, `"triangle_right"`, `"cross"`, `"plus"` | `elem.style['point_shape']` |
| `AngleRange` | `"minor"`, `"reflex"` | `elem.style['angle_range']` |
| `TickStyle` | `"line"`, `"wave"` | `elem.style['tick_style']` |
| `PointDisplay` | `"auto"`, `"only_labels"`, `"only_points"` | `rendering.points_display` |
| `LineCap` | `"butt"`, `"round"`, `"square"` | `rendering.line_cap`, `elem.style['stroke_linecap']` |
| `RightAngleJoint` | `"auto"`, `"bevel"`, `"miter"`, `"round"` | `rendering.right_angle_joint` |
| `LabelAnchor` | `"TL"`, `"TC"`, `"TR"`, `"ML"`, `"MC"`, `"MR"`, `"BL"`, `"BC"`, `"BR"` | `rendering.label_anchor`, `elem.style['label_anchor']` |
| `Interpolation` | `"linear"`, `"smooth"` | `overlay.label_placement.interpolation` |

---

## Part 5. Measurement units and conversion constants

### 5.1. Units

| Space | Unit | Where it appears |
|---|---|---|
| GGB screen pixels | px | GGB XML values (pointSize, thickness, arcSize, labelOffset), `elem.ggb_raw`, the `_px` suffix in `elem.style` |
| JSON style units | px-like (supplied by the user) | `presets`, `defaults.*` |
| Internal/manim coordinate units (MU) | 1 MU = `ptUnit` pixels | radii, coordinate lengths, offsets |
| Manim stroke/font render units | Manim's stroke/font scale | `stroke_width`, `set_stroke(width=...)`, `font_size` |
| Dimensionless | `[0..1]` opacity, ratio | `stroke_opacity`, `fill_opacity`, `stroke_dash_ratio` |
| Enumerations | strings | see Part 4 |

**Pixel-invariance contract:** all `_px` values are stored as pixels but are converted according to the destination Manim parameter. Coordinate sizes (`size_px`, `arc_size_px`, `tick_length_px`, `tick_shift_px`, `tick_radius_px`, `arrow_*_px`, offsets) become MU via `/ ptUnit`. Thicknesses and fonts passed to Manim `stroke_width`, `set_stroke(width=...)`, or `font_size` go through the render scale `* 100 / ptUnit`: `stroke_width_px`, `tick_width_px`, `font_size_px`. This guarantees the same visual result at any canvas size.

### 5.2. Constants (`animageo/constants.py`)

| Constant | Value | Purpose |
|---|---|---|
| `STYLE_TO_INTERNAL` | `0.02` | internal scaling constant; runtime style JSON uses pixel-unit `*_px` |
| `LINE_WIDTH_SCALE` | `2` | internal width scaling constant; the renderer reads `stroke_width_px` through the resolver |
| `FONT_SIZE_RATIO` | `50/25.9 ≈ 1.93` | internal font scaling constant; the renderer reads `font_size_px` through the resolver |
| `STROKE_WIDTH_SCALE` | `100` | `elem.style['stroke_width_px']` → manim `stroke_width` (divided by `ptUnit`) |
| `GGB_FONT_SCALE` | `100.0` | GGB font px → manim `font_size` (divided by `ptUnit`) |
| `Z_FILL`, `Z_FILL_INNER`, `Z_FILL_LABEL`, `Z_ANGLE`, `Z_LINE`, `Z_STROKE`, `Z_POINT`, `Z_LABEL` | tiers | per-element-type z-index (defaults) |

`builtin.json` (`animageo/style/builtin.json`) — package-shipped per-type defaults in pixels; `StyleConfig.load(user_path)` always starts from it and merges the user JSON via `deep_merge`.

### 5.3. Full chain examples

**Point A from GGB** (`pointSize=5`, color `#1565c0`, `pointStyle=0`):
```
GGB XML:
    <pointSize val="5"/>
    <objColor r="21" g="101" b="192"/>
    <pointStyle val="0"/>
    <labelOffset x="-28" y="32"/>

↓ ggb_parser + style/enums.ggb_point_style_to_elem_style

elem.ggb_raw = {
    'point_size': 5, 'point_style': 0,
    'obj_color': {
        'r': 21, 'g': 101, 'b': 192,
        'alpha': 0, 'opacity': 0, 'hex': '#1565c0'
    },
    'label_offset_px': [-28, 32],
}
elem.style = {
    'size_px': 10.0,              # 5 × 2
    'point_shape': 'circle',
    'fill': '#1565c0',   'fill_opacity': 1.0,
    'stroke': '#000000', 'stroke_width_px': 1.0, 'stroke_opacity': 1.0,
    'label_color': '#1565c0',
    'label_offset_px': [-28, -32],  # Y is inverted
    ...
}

↓ CreateMObject (render time, ptUnit = 50)

Circle(radius=0.1, color='#000000', fill_color='#1565c0',
       fill_opacity=1, stroke_opacity=1, stroke_width=2)

↓ Cairo → SVG

<circle cx="…" cy="…" r="0.1"
        fill="#1565c0" fill-opacity="1"
        stroke="#000000" stroke-width="2"/>
```

**Dashed line from GGB** (`thickness=10`, `type=1`):
```
GGB XML:
    <lineStyle thickness="10" type="1" opacity="255"/>
elem.style = {
    'stroke_width_px': 5.0,        # 10 / 2
    'stroke_opacity':  1.0,        # 255 / 255
    'stroke_dash_ratio': 0.65,     # type > 0 → 0.65
    ...
}

↓ CreateMObject (ptUnit = 50)

DashedLine(..., stroke_width=10, dashed_ratio=0.65, dash_length=0.17)

↓ SVG

<path stroke="…" stroke-width="10" stroke-dasharray="..."/>
```

---

## History

The field-name revision shipped in **AnimaGeo 1.0.0** (2026-04-23), as part
of the geometry-core and style-system rewrite. Short/abstract field names
(`a`, `c`, `n`, `v`, `r`, `p`, `M`, `b`, `x`, `dim`, `angle`, `original`,
`points`, `end_points`, `start_point`) were replaced by the human-readable
names documented above, with **no backward-compat aliases**: code written
against pre-1.0 names (`point.a`, `circle.c`, `line.n`, `measure.x`, …)
raises `AttributeError` and must switch to the names in Part 1.

The keyframe-animation wire-format JSON uses the current names as well:
`get_independents()` returns the type `'tparam_point'` and the key
`'tparam'`; the keyframe parser accepts only `'tparam'`.

Follow-up in **1.0.2**: the last surviving alias,
`Construction.update_alpha` (for `update_tparam`), was removed, along with
the orphan IDE-stub snapshot that still referenced pre-1.0 field names
(`Measure.x`, `Angle.angle`).

---

## See also

- `docs/styles.md` — human-readable guide to the JSON schema with examples.
- `animageo/style/enums.py` — source code with the enum values and the GGB decomposition.
- `animageo/style/proxy.pyi` — the full list of `elem.style` keys with IDE type annotations.
- `animageo/style/schema.py` — docstring with the canonical JSON example + validator.
