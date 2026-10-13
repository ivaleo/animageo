# AnimaGeo AI Style Generation Context

Use this document as the stable context for an LLM that must generate
AnimaGeo style JSON files from a natural-language request. It is written for
models that do not know the codebase. The companion machine schema is
`docs/ai_style_json_schema.json`.

## Task For The LLM

Given:

1. A natural-language style request.
2. This context file.
3. Optionally, a compact construction summary.

Return:

1. A valid AnimaGeo style JSON object.
2. Optional AnimaGeo Python DSL code only when the request needs explicit
   styling of named elements or procedural logic that should not live in the
   general style file. This code must be a standalone `.py` DSL file loadable
   with `scene.loadCode(path)` after `scene.loadGGB(...)`; it must not be code
   inside an `AnimaGeoScene` subclass and must not call `scene.element(...)`.
3. Brief notes about assumptions, out-of-scope requests, and how to apply the
   style.

When the user asks for "only JSON", return only the style JSON object and no
Markdown. Otherwise use this response shape:

````text
STYLE_JSON:
```json
{ ... }
```

PYTHON_DSL:
```python
# omit this section if not needed; when present, this is exactly the
# content of a .py file passed to scene.loadCode(...), not scene orchestration
...
```

NOTES:
- ...
````

Do not invent new style keys. Use only the canonical keys in this document and
the JSON Schema. Do not include comments inside JSON.

## NOTES Contract

`NOTES` are not a summary of every style key. Use them to record decisions,
assumptions, risks, and limits that a caller may need for follow-up edits.
Keep each note short and concrete. Prefer element names, resolved values, and
the chosen layer when relevant.

Include `NOTES` whenever any of these situations occurs:

- The request is ambiguous. State the interpretation used, such as which
  circle, triangle, angle, or label group was targeted.
- A target was selected from `construction_summary`. Say what was chosen and
  the evidence, for example "selected segment `a` as the longest visible
  segment, length 5.98".
- A construction element may overlap another element visually. In particular,
  if a highlighted segment is also a polygon side, mention that the polygon
  outline duplicates the segment and that layer order matters.
- Python DSL is returned. Explain why style JSON alone was not enough, for
  example "triangle angle markers did not exist, so DSL creates them with
  `Angle(...)`".
- Python DSL was deliberately avoided for a computed request because the
  provided summary was sufficient. Explain that the result was resolved to
  named elements and implemented with `overlay.per_name`.
- The user asks for something outside the style-generation scope. State that
  scene orchestration, animation, rendering, and export code are not generated;
  only style JSON and optional loadCode-compatible DSL may be returned.
- Natural-language terms require numeric or color interpretation: "slightly",
  "thin", "large", "school style", "accent", "light palette", and similar.
  State the chosen values or palette.
- Relative changes are applied. State the source and target values, for
  example `font_size.main: 8.67 -> 5.78`.
- GeoGebra styling is preserved, ignored, or selectively overridden. State
  which properties were overridden and which remain from the import layer.
- Visibility changes are made. State the exact affected names or types,
  especially when hiding labels or objects.
- Automation blocks are enabled or adjusted, such as `overlay.angle_radius` or
  `overlay.label_placement`.
- There are multiple valid strategies that affect later edits. State the
  chosen strategy and a meaningful alternative.
- A required selection cannot be made reliably because no
  `construction_summary` was supplied or because the target is missing,
  hidden, or underspecified.

Do not use `NOTES` to hide invalid output. If a requested effect cannot be
represented by style JSON or loadCode-compatible DSL, say so in `NOTES` and
leave the unsupported part unapplied.

## Core Mental Model

AnimaGeo loads a package `builtin.json` first, then deep-merges the user's
style JSON on top. A generated style JSON can therefore be short. It should
define the values that matter for the request, not copy every built-in
default.

A rendered element's effective style is resolved by priority:

```text
elem.style
→ overlay.per_name
→ overlay.per_type
→ elem.ggb_style
→ defaults.<type>
→ intrinsic geometry style
→ renderer fallback
```

Meaning:

- `elem.style` is explicit Python/DSL code and always wins.
- `overlay.per_name` targets one named element and wins over type rules.
- `overlay.per_type` targets every element of a type and wins over GeoGebra
  visual import.
- `elem.ggb_style` is the normalized visual style imported from GeoGebra.
- If `import.enabled` is `false`, the resolver skips `elem.ggb_style`
  completely. Geometry, names, dependencies, and `elem.ggb_raw` remain
  available.
- `defaults.<type>` is the baseline used when no higher layer provides a key.
- Intrinsic geometry style is low-level style already stored on the element by
  geometry/parser helpers but not marked as an explicit user write.
- `visible` is special: explicit DSL/API style wins first, runtime
  Show/Hide/addAllGeometry visibility wins before style layers, and imported
  construction visibility is separate from `elem.ggb_style`.

Short rule:

```text
presets = reusable tokens
defaults = baseline by element type
import = how to read/adapt GeoGebra visual values
overlay = project styling after import
reference = authoring/reference canvas metadata
rendering = scene/export/rendering flags, not object styling
elem.style/Python DSL = explicit local edits
```

## Style JSON Top-Level Sections

Allowed top-level keys:

- `name`: optional string.
- `version`: optional number or string.
- `presets`: reusable semantic constants.
- `defaults`: per-type baseline style.
- `reference`: optional authoring/reference canvas metadata.
- `overlay`: post-import overrides and automation.
- `rendering`: scene-level rendering flags.
- `import`: GeoGebra visual import/adaptation rules.

Avoid arbitrary metadata fields. Runtime loading warns and ignores unknown
top-level keys, but the companion JSON Schema rejects them.

## Units

All visual values ending in `_px` are pixel-like style units. This includes:

- point diameter: `size_px`
- line and arc thickness: `stroke_width_px`
- angle arc radius: `arc_size_px`
- shift between multiple angle arcs: `arc_shift_px`
- right-angle marker size: `right_angle_size_px`
- tick mark sizes: `tick_length_px`, `tick_width_px`, `tick_shift_px`,
  `tick_radius_px`
- arrowhead sizes: `arrow_length_px`, `arrow_width_px`
- label offsets: `label_offset_px`, `label_radial_offset_px`
- label font size: `font_size_px`

Opacity values are numbers from `0` to `1`. Colors are hex strings
`#rrggbb`. Preset references use strings like `color.main`.

If the user asks for point size to be exactly 2 times line thickness, remember
that `size_px` is the point diameter. Set
`point_size.main = 2 * line_width.main` unless the request
clearly uses another local meaning.

## Element Type Names

Use these type names in `defaults` and `overlay.per_type`:

- `point`
- `segment`
- `line`
- `ray`
- `vector`
- `angle`
- `polygon`
- `circle`
- `arc`
- `circlesector`
- `conic`
- `function`
- `implicitcurve`

`decoration` appears in built-ins as a shared helper for tick presets, but it
is not a drawable element type.

## Canonical Style Keys

### Cross-Type Visibility And Labels

- `visible`: bool; whether the object is rendered. Runtime visibility changes
  can override style layers.
- `label_visible`: bool.
- `label_text`: TeX string, often `"$A$"` or `"$\\alpha$"`.
- `label_mode`: `label`, `value`, or `label_value`; controls whether the
  rendered text is the label, the computed value, or `label = value`.
- `label_value_precision`: integer decimal precision for computed values.
- `label_value_strip_zeros`: bool.
- `label_angle_unit`: `degree` or `radian`.
- `label_value_separator`: string, usually `" = "`.
- `label_color`: hex or preset reference.
- `label_anchor`: one of `TL`, `TC`, `TR`, `ML`, `MC`, `MR`, `BL`, `BC`, `BR`.
  A GeoGebra label without an explicit `label_anchor` keeps GeoGebra's own
  placement for its element type; setting `label_anchor` switches it to the
  general placement.
- `label_offset_px`: `[dx, dy]`.
- `label_radial_offset_px`: radial offset for angle labels.
- `label_placement_locked`: bool; prevents auto-placement from moving a label.
- `label_hint_px`: `[dx, dy]`, y up; where the label centre should be relative
  to the element's anchor (the point, a segment's midpoint, an angle's vertex).
  A soft request: auto-placement keeps the hinted side and still avoids
  collisions. Prefer it to `label_offset_px` + `label_placement_locked` when
  only the side is known.
- `font_size_px`: label font size.

### Stroke

- `stroke`: hex or preset reference.
- `stroke_width_px`: line/curve/arc thickness.
- `stroke_opacity`: `0..1`.
- `stroke_dash_ratio`: `null` or number from `0` to `1`; non-null means dashed
  (the dash's share of one period).
- `stroke_dash_period_px`: dash + gap in px (default `rendering.dash_period_px`,
  10). `0.65` of `10` draws 6.5 px dashes with 3.5 px gaps.
- `stroke_linecap`: `butt`, `round`, or `square`.
- `right_angle_joint`: `auto`, `bevel`, `miter`, or `round`.

### Fill

- `fill`: hex or preset reference.
- `fill_opacity`: `0..1`.

### Points

- `size_px`: point diameter.
- `point_shape`: `circle`, `square`, `diamond`, `triangle_up`, `triangle_down`,
  `triangle_left`, `triangle_right`, `cross`, or `plus`.

### Angles

- `angle_range`: `minor` or `reflex`.
- `arc_size_px`: base angle arc radius.
- `arc_shift_px`: radial shift between concentric angle arcs when
  `tick_count > 1`.
- `right_angle_size_px`: square marker size.
- `right_angle_marker`: bool; force square marker. Do not set this globally
  on `overlay.per_type.angle` just because the user asks to change the size
  of the right-angle marker; use `right_angle_size_px` for size and leave
  marker detection automatic unless the user explicitly asks to turn all or
  named angles into right-angle markers.
- `auto_radius`: bool; opt out of `overlay.angle_radius` when false.
- `tick_count`: for angles this means number of concentric arcs.

### Segment And Vector Marks

- `tick_count`: number of equality marks.
- `tick_style`: `line` or `wave`.
- `tick_length_px`: tick length.
- `tick_width_px`: tick stroke width.
- `tick_shift_px`: spacing between multiple ticks.
- `tick_radius_px`: rounding radius for `tick_style = "wave"`.

### Vector Arrowheads

- `arrow_length_px`
- `arrow_width_px`

### Layering

- `z_index`: main object layer.
- `z_index_fill`: fill layer for `circlesector`.

## Section Responsibilities

### `presets`

Use for reusable tokens: named colors, point sizes, line widths, angle radii,
font sizes, tick presets, arrow presets. Presets do nothing by themselves.
They must be referenced from `defaults`, `overlay`, `rendering`, or `import`.

Prefer semantic preset references over duplicating literal colors and sizes in
style JSON. The built-in style already defines common semantic tokens such as
`color.main`, `color.accent`, `color.aux`,
`color.strong`, `line_width.main`,
`line_width.bold`, `line_width.aux`,
`point_size.main`, `point_size.bold`,
`point_size.aux`, and matching `font_size` tokens. Use these roles so
the construction can keep its semantic intent while the user changes the actual
palette/scale in one place.

Recommended meanings:

- `main`: ordinary geometry/default linework;
- `strong`: primary objects from the problem statement when a dense diagram
  needs them to remain visually prominent;
- `aux`: helper/secondary construction objects;
- `accent`: the requested result, focus element, or point of attention.

Typical groups:

```json
{
  "presets": {
    "color": {
      "main": "#000000",
      "accent": "#d05456",
      "aux": "#808080",
      "strong": "#000000",
      "angle_fill": "#eeeeee",
      "background": "#ffffff"
    },
    "point_size": { "main": 6, "bold": 9, "aux": 4 },
    "line_width": { "main": 1.5, "bold": 2.5, "aux": 0.75 },
    "angle_radius": { "main": 20, "shift": 3, "right": 17 },
    "font_size": { "main": 14, "bold": 16, "aux": 12 },
    "tick": {
      "main": {
        "tick_length_px": 9,
        "tick_width_px": 1.5,
        "tick_shift_px": 2
      }
    },
    "arrow": {
      "main": {
        "arrow_length_px": 11,
        "arrow_width_px": 7.5
      }
    }
  }
}
```

### `defaults`

Use for the baseline style by type. This is useful when the user wants a
style theme for scenes created in Python/DSL or wants fallback values when
GeoGebra import is disabled. `defaults` is lower priority than imported
GeoGebra style, so it does not reliably override `.ggb` visual choices.

Use `defaults` for:

- "By default, points are black circles."
- "The baseline line width is 1.5 px."
- "Angles have default radius 20 px if GeoGebra does not specify one."

Do not use `defaults` when the user says imported GeoGebra values must be
overridden. Use `overlay.per_type` for that.

### `overlay.per_type`

Use for project-level rules applied after import to all elements of a type.
This is the best layer for requests like:

- "Make all points the same size and black."
- "Make all lines/segments/rays/circles the same stroke width."
- "Make all angle arcs a separate thickness."
- "Give all angle fills the same color."
- "Use the same font size for all labels."
- "Set all segment equality marks to the same size."

Because `overlay.per_type` is above `elem.ggb_style`, it overrides visual
choices imported from GeoGebra and also affects DSL-created elements.

### `overlay.per_name`

Use only for named exceptions that are part of the requested reusable style or
that depend on a provided construction summary.

Good examples:

- "Make point A red."
- "Hide labels on xAxis and yAxis."
- "Make angle alpha double-arc."
- "Make segment AB use two equality marks."

If there is no construction summary, do not invent element names. Put suggested
named-element rules in the AnimaGeo Python DSL section only as commented
placeholders, or prefer `overlay.per_type` when the rule is truly global.

### `overlay.angle_radius`

Use for automatic scaling of angle radii. This is not a direct visual style
key but an automation block:

```json
"overlay": {
  "angle_radius": {
    "enabled": true,
    "exp": 0.3,
    "min_px": 14,
    "max_arm_fraction": 0.55,
    "apply_to_right": false
  }
}
```

Use it when the request says angle arcs should remain readable across small
and large angles. Use per-angle `auto_radius: false` when a specific angle
must keep a fixed radius.
If the user asks for automatic angle alignment/sizing and also asks for one
named angle marker to be slightly larger than another, keep
`overlay.angle_radius.enabled = true` and use a small
`overlay.per_name.<angle>.arc_size_px` override for the named angle. Do not
disable the automatic angle layer unless the user explicitly asks for manual
fixed angle sizes.

### `overlay.label_placement`

Use for automatic label layout. It can be enabled for static scenes:

```json
"overlay": {
  "label_placement": {
    "enabled": true,
    "distance_px": 6,
    "padding_px": 2,
    "angle_gap_arc_px": 3,
    "angle_gap_sides_px": 3
  }
}
```

For animations, use:

- `keyframe_snapshots: true` for keyframe animation label layout; it works
  only together with `enabled: true`.
- `dynamic_angles: true` only together with keyframe snapshots or explicit
  dynamic auto-placement in Python.
- `canonicalize_anchor: true` only when smooth label interpolation matters.

### `reference`

Use for the authoring/reference canvas that the style was tuned for. This is
metadata in the style JSON and may be overridden at runtime:

```json
"reference": {
  "size": { "width": 800, "height": 600 },
  "source": "source_view"
}
```

Allowed `reference.source` values are `manual`, `source_view`, and
`ggb_view`. The actual source rectangle placed on that reference canvas is a
runtime `content` option, not a style JSON field. The physical output size is
a runtime `export` option:

```python
scene.loadGGB(
    "scene.ggb",
    style="style.json",
    content={"source": "rendered_bounds", "padding": 12},
    export={"size": {"width": 1600, "height": 1200}},
)
```

Use `reference` when the user asks for a reusable style calibrated to a known
canvas size. Do not put final SVG/MP4 dimensions in the style JSON; physical
output belongs in the runtime `export` block.

#### Runtime `content` options (not style JSON keys)

Since library version 1.6.2 the runtime `content` block also accepts three
decoration-scaling options. They are runtime API options like
`content.source`; never emit them inside style JSON. If a request asks for
this behavior, mention in `NOTES` that it is a runtime `content` option:

- `content.prominence`: number, default `1.0` (clamped to `0.01..100`). A
  single decoration-size multiplier applied at render time. Layout, crop, and
  label placement are computed at nominal prominence (1.0) and stay
  unaffected; prominence only scales the density that decoration sizes
  (points, strokes, label fonts, markers) are resolved against.
- `content.decoration_scale_source`: `frame` (default), `reference`,
  `output`, or `ggb`. Controls the density decorations are resolved against:
  `frame` tracks the actual export crop (`fitView` relies on this);
  `reference` re-bases `rendered_bounds` density on the style reference over
  the full source view, so decoration prominence stays constant across
  framing choices; `output` anchors decoration size to the geometry's export
  zoom, so decoration pixels are a fixed output size set only by prominence;
  `ggb` scales decorations uniformly with the output canvas like the GeoGebra
  applet (`decoration_px = authored_px × (output_width / ggb_view_width) ×
  prominence`).
- `content.label_bounds`: `reserve` (default) or `exclude`. With
  `content.source = "rendered_bounds"`, `exclude` crops to the geometry only,
  ignoring outward-placed labels; `reserve` keeps edge labels from clipping.

All three are opt-in; the library defaults are unchanged.

### `rendering`

Use for scene/export behavior, not object styling:

- `background`: scene background.
- `line_cap`: default line cap.
- `dash_period_px`: default dash period in px (dash + gap), `10`.
- `right_angle_joint`: default joint style for right-angle markers.
- `polygon_boundary_layer`: `"top"` to draw polygon boundary segments above
  fills; otherwise `null`.
- `points_display`: `auto`, `only_labels`, or `only_points`.
- `label_anchor`: default label anchor.
- `label_value_precision`: scene-level default precision for value labels.
- `fast_value_labels`: `true` (default); animated value labels skip the
  per-frame LaTeX compile.
- `label_contrast`: `off` (default) or `auto` (recolour labels on fills of
  similar luminance); `label_contrast_threshold`: luminance gap, `0.35`.
- `color_interpolation`: `oklab` (default) or `srgb`, for animated colors.

Do not put point sizes, stroke widths, fill colors, font sizes, or tick
parameters in `rendering`. Do not put `angle_radius` or `label_placement` in
`rendering`; those automation blocks belong under `overlay`.

### `import`

Use only for GeoGebra-specific visual adaptation. It has no effect on
DSL-created elements.

Use `import.colors`, `import.point_size`, `import.line_width`, or
`import.policy` when the request is about how to translate raw GGB values:

- "Remap GeoGebra blue to my brand blue."
- "Quantize imported line thicknesses to 1, 2, or 4."
- "Scale imported point sizes by 1.5."
- "Ignore all GeoGebra visual styling and use style defaults."

Disable visual import:

```json
"import": {
  "enabled": false
}
```

If `import.enabled` is false, geometry and `elem.ggb_raw` remain available,
but imported colors/sizes/labels do not become the render baseline.

Choose the import strategy deliberately:

- Preserve GeoGebra style: leave `import.enabled` unset/true and add only the
  specific `overlay` keys that the user asked to change. Do not restyle
  unrelated keys.
- Adapt GeoGebra style: keep the import layer enabled and use `import.colors`,
  `import.point_size`, `import.line_width`, or specific `import.policy` fields
  to transform raw GGB visual values before overlay.
- Replace GeoGebra style: set `import.enabled=false`, define the baseline you
  need in `defaults`, and use `overlay` only for project-wide or named
  exceptions. This is better than copying every GeoGebra-derived field into
  overlay just to neutralize it.

`import.policy` supports literal values and mini-DSL strings:

- `"const:3"`
- `"scale:1.5"`
- `"quantize:[1,2,4]"`
- `"remap:{'#1565c0':'#0066cc'}"`
- `"match_element"`
- `"auto"`

Policy fields:

- `size_px`
- `stroke_width_px`
- `arc_size_px`
- `label_offset_px`
- `label_color`
- `label_visible`
- `visible`
- `label_text`
- `label_mode`
- `label_value_precision`
- `label_value_strip_zeros`
- `label_angle_unit`
- `label_value_separator`
- `angle_range`
- `tick_count`
- `font_size_px`
- `stroke`
- `fill`
- `fill_opacity`
- `point_shape`
- `stroke_opacity`
- `stroke_dash_ratio`
- `stroke_dash_period_px`
- `stroke_linecap`

## Choosing The Right Layer

Use this decision table:

| User request | Best location |
| --- | --- |
| "All imported points black and same size" | `overlay.per_type.point` |
| "All labels 14 px" | `overlay.per_type` for each relevant type, or `defaults` if not overriding GGB |
| "Unify point labels" | Set label style under `overlay.per_type.point` only; do not force labels visible on lines, angles, or other types unless those are named |
| "All lines same thickness" | `overlay.per_type` for line-like types |
| "All lines same thickness and opaque, rest from GeoGebra" | Set only `stroke_width_px` and `stroke_opacity`; do not set `stroke` unless the user explicitly asks to change line color |
| "Angle arcs have their own thickness" | `overlay.per_type.angle.stroke_width_px` |
| "Angle fills are pale yellow" | `overlay.per_type.angle.fill` and `fill_opacity` |
| "Angles without lines, only fill" | `overlay.per_type.angle.stroke_width_px = 0`, `stroke_opacity = 0`, `fill_opacity = 1`; do not change `fill` color unless the user names a fill color for angles |
| "`r_shift` between angle arcs is 3" | `overlay.per_type.angle.arc_shift_px` |
| "Right angle marker is twice as large" | `overlay.per_type.angle.right_angle_size_px`; do not set `right_angle_marker=true` globally |
| "Segment marks have same length/width/shift" | `overlay.per_type.segment` tick fields |
| "The segment AB has two ticks" | `overlay.per_name.AB.tick_count` if AB exists; otherwise AnimaGeo Python DSL |
| "Remap GeoGebra colors" | `import.colors` or `import.policy.stroke/fill` |
| "Ignore GeoGebra styling" | `import.enabled=false` plus `defaults` for the desired baseline |
| "Keep labels from colliding" | `overlay.label_placement` |
| "Make very acute angle arcs readable" | `overlay.angle_radius` |
| "Move label A by [10, -4]" | `overlay.per_name.A.label_offset_px` if A exists; otherwise AnimaGeo Python DSL |

## Requests That Are Not Pure Style

When the user says "the rest should come from GeoGebra", treat every
unspecified visual property as protected by the GGB import layer. For example,
"same line thickness and no transparency" changes `stroke_width_px` and
`stroke_opacity`, but it must not also change `stroke` color. A separate
phrase like "make lines black" is required before setting line `stroke`.

Color adjectives apply only to the object class they modify. For example,
"brown points" means point `fill`/`stroke` may become brown; it does not imply
that angle fills, polygon fills, or line strokes should also become brown.

Likewise, object-qualified label requests apply only to that object class.
"Point labels" means `overlay.per_type.point.label_*`, not labels for every
element type.
Do not set `label_visible` when the request only says to unify, restyle, or
resize labels. Set `label_visible` only when the user explicitly asks to show
or hide labels.
When the user asks to hide labels for specific named points, use
`overlay.per_name.<name>.label_visible = false` for those names only. Do not
hide labels for the whole `point` type.

If a construction summary is provided and the user asks to accent a singular
existing object such as "the circle", prefer `overlay.per_name` for the visible
named object. Use `overlay.per_type.circle` only when the request is explicitly
about all circles.

Some requests should not be solved only by a reusable style JSON:

- Geometry changes: add/delete/move points, change construction, create new
  segments, compute intersections.
- Content-dependent selection that cannot be expressed by type or known name:
  "color the longest segment", "mark only equal sides", "highlight the largest
  angle", "color all points inside the circle".
- Dynamic procedural logic: conditional style based on measurements or other
  data available only at load time.
- Fine manual label placement for unknown element names.

If `construction_summary` contains enough information to resolve the target
element names deterministically, prefer `overlay.per_name` in the style JSON
over Python DSL. For example, if the summary lists segment lengths and the
request says "highlight the longest segment", choose the longest visible
segment from the summary and style it by name. Use Python DSL only when the
selection cannot be resolved from the supplied summary or when the user wants
the rule to be re-evaluated when a different construction is loaded.
If the user asks to highlight angles of a polygon/triangle and the summary
contains the polygon vertices but no existing angle elements for those
vertices, return DSL that creates the missing angle markers with `Angle(...)`
and styles those new DSL elements. Do not reuse unrelated existing angle
objects just because they are named with Greek letters.
When highlighting a segment that is also a side of an imported polygon, the
polygon outline may duplicate that side. Put the highlighted segment above
normal stroke geometry with `z_index` greater than the stroke tier, e.g. `6`,
or remove the polygon outline if the separate segment sides should define the
boundary. Do not use tiny z-index values like `0.4` for highlighted strokes;
they sit below normal stroke layers. Add a `NOTES` entry for this overlap as
specified in the `NOTES Contract`.

For requests that truly need procedural logic, return a normal style JSON plus
AnimaGeo Python DSL code.

The `PYTHON_DSL` section must contain only the content of the DSL file. It
must not include the surrounding scene orchestration. Never generate
`AnimaGeoScene`, `construct`, `play`, `wait`, Manim animation code, render or
export calls, `loadGGB`, or `loadCode` calls inside `PYTHON_DSL`. The web
service or user will apply it like this:

```python
scene.loadGGB(
    "scene.ggb",
    style="style.json",
    export={"size": {"width": 800, "height": 600}},
)
scene.loadCode("ai_post_style.py")
```

Example `ai_post_style.py` content:

```python
# This file is AnimaGeo Python DSL. It is executed by scene.loadCode(...)
# after the construction has already been loaded. Names like A, AB, CD must
# exist in the current Construction, usually from loadGGB or earlier DSL.

for el in [AB, CD]:
    el.style.tick_count = 2
    el.style.tick_length_px = 10

A.style.fill = "#d05456"
A.style.stroke = "#d05456"
A.style.label_color = "#d05456"
```

Allowed DSL style forms:

```python
A.style.stroke = "#ff0000"
A.style["stroke_width_px"] = 2
style(A, B, C, fill="#000000", size_px=6)
hide(A, B)
show(C)
```

Do not generate:

```python
def restyle(scene): ...
scene.element("A").style["fill"] = "#ff0000"
class MyScene(AnimaGeoScene): ...
```

`elem.style` assignments made by DSL are explicit and have the highest
priority. Only generate direct references to names that exist in the compact
construction summary. If a name is unknown, mention that in NOTES or output a
commented placeholder instead of executable code.

## Compact Construction Summary Format

Do not send raw `.ggb` XML to the LLM. Use the library exporter documented in
`docs/construction_summary.md` when the request references actual names, types,
imported styles, or geometry:

```python
summary = scene.exportStylePromptSummary("scene.summary.json")
```

Recommended format:

```json
{
  "schema": "animageo-construction-summary/v1",
  "source": {
    "kind": "ggb",
    "name": "scene.ggb"
  },
  "viewport": {
    "size": [800, 600],
    "reference_size": [800, 600],
    "ptUnit": 50,
    "ptUnit_style": 50,
    "ptUnit_ggb": 50,
    "ptXZero": 400,
    "ptYZero": 300,
    "contentScale": 1,
    "fontSize": 16
  },
  "stats": {
    "point": 4,
    "segment": 3,
    "angle": 1
  },
  "elements": [
    {
      "name": "A",
      "type": "point",
      "visible": true,
      "label_visible": true,
      "geometry": {
        "coords": [0, 0]
      },
      "ggb_style": {
        "size_px": 10,
        "fill": "#1565c0",
        "stroke": "#000000",
        "label_color": "#1565c0"
      }
    },
    {
      "name": "AB",
      "type": "segment",
      "visible": true,
      "label_visible": false,
      "construction": {
        "command": "Segment",
        "inputs": ["A", "B"],
        "outputs": ["AB"]
      },
      "geometry": {
        "endpoints": [[0, 0], [4, 0]],
        "length": 4
      },
      "ggb_style": {
        "stroke": "#1565c0",
        "stroke_width_px": 2.5
      }
    },
    {
      "name": "alpha",
      "type": "angle",
      "visible": true,
      "label_visible": true,
      "construction": {
        "command": "Angle",
        "inputs": ["B", "A", "C"],
        "outputs": ["alpha"]
      },
      "geometry": {
        "vertex": [0, 0],
        "side1": [1, 0],
        "side2": [0.5, 0.866],
        "size_rad": 1.0472,
        "size_deg": 60.0,
        "start_angle": 0.0,
        "end_angle": 1.0472
      },
      "ggb_style": {
        "arc_size_px": 30,
        "stroke_width_px": 2,
        "fill": "#000000",
        "fill_opacity": 0.1
      }
    }
  ],
  "groups": {
    "points": ["A", "B", "C"],
    "segments": ["AB", "BC", "CA"],
    "angles": ["alpha"]
  },
  "warnings": []
}
```

Keep this summary compact:

- Include all names, types, visibility, and label visibility.
- Include only geometry useful for styling decisions.
- Include imported/resolved visual style only for keys relevant to the task.
- Include dependency names in `construction.inputs` / `construction.outputs`
  for segments, vectors, angles, polygons when known.
- Include unsupported commands or parser warnings if they affect styling.
- Omit raw XML, huge sampled curves, and redundant defaults.

For large constructions, cap style payloads and provide type/name lists plus
summary statistics. If a request targets a subset, include only those elements
in detail and the rest as counts.

## Recommended Prompt Payload

A robust API request should include:

1. The user's natural-language request.
2. This context file.
3. The JSON Schema or a link/path to it.
4. Output contract:
   - return valid JSON only, or
   - return `STYLE_JSON`, optional `PYTHON_DSL`, and `NOTES`.
5. Target use case:
   - GeoGebra import only,
   - Python/DSL scenes only,
   - both.
6. Whether imported GGB visual styles should be preserved, remapped, or
   overridden.
7. Optional compact construction summary.
8. Optional existing house style JSON to edit or extend.
9. Constraints:
   - color palette,
   - exact sizes,
   - print/screen use,
   - background,
   - whether labels should be visible,
   - animation/static scene.
10. Whether named-element edits are allowed in `overlay.per_name` or should be
    returned as AnimaGeo Python DSL for `loadCode` instead.
11. Optional runtime layout requirements separately from style JSON:
    - `reference` canvas for authoring scale,
    - `content` source/fitting,
    - physical `export` size.

## Validation Checklist For The LLM

Before returning, verify:

- JSON has no comments and no trailing commas.
- Top-level keys are allowed.
- Every `<group>.<name>` preset reference exists in `presets`.
- Type names are canonical lowercase names.
- Style keys are canonical names with `_px` units where required.
- No removed top-level sections (`style`, `technic`, `ggb_export`, `palette`)
  and no removed visual keys such as `line_width`, `font_size`,
  `ang_rdefault`, `label_r_offset`, or `strich_len`.
- Do not generate removed keys such as `rendering.scale_export` or
  `overlay.label_placement.angle_gap_px`.
- Use `font_size_px`, including inside `import.policy`; do not generate
  `import.policy.font_size`.
- `overlay.per_type` is used for global post-import styling.
- `defaults` is not used when the request explicitly says to override
  imported GGB values.
- `import.policy` is used only for raw GGB adaptation.
- Opacities are in `0..1`.
- Colors are hex strings.
- `NOTES` include every required decision, assumption, risk, scope limit, and
  construction-summary-based selection described in the `NOTES Contract`.
- `label_text` TeX strings escape a single TeX backslash once in JSON, e.g.
  `"$\\alpha$"` in the JSON file. Do not double-escape it as
  `"$\\\\alpha$"`, because that becomes `\\alpha` in LaTeX and fails.
- For automatic angle labels, move labels closer to the angle marker by
  reducing `overlay.label_placement.angle_gap_arc_px` and
  `angle_gap_sides_px`. A positive `label_radial_offset_px` moves an angle
  label farther outward, so do not use a positive radial offset to satisfy
  "closer to the angle".
- If the request needs procedural or named unknown-element logic, provide
  AnimaGeo Python DSL loadable with `scene.loadCode(...)` rather than
  pretending it is a general style.

## Complete Example

Request:

> Import a GeoGebra construction. Make all points black circles of one size,
> all line-like objects the same thickness, angle arcs thinner, angle fills
> light gray, all labels 14 px, angle arc shift 3 px, and segment marks uniform.

Good style JSON:

```json
{
  "name": "uniform_black_geometry",
  "version": 1,
  "presets": {
    "color": {
      "main": "#000000",
      "background": "#ffffff",
      "angle_fill": "#eeeeee"
    },
    "point_size": {
      "main": 6
    },
    "line_width": {
      "main": 1.5,
      "angle": 1
    },
    "angle_radius": {
      "main": 20,
      "shift": 3,
      "right": 17
    },
    "font_size": {
      "main": 14
    },
    "tick": {
      "main": {
        "tick_style": "line",
        "tick_length_px": 9,
        "tick_width_px": 1.5,
        "tick_shift_px": 2
      }
    }
  },
  "overlay": {
    "per_type": {
      "point": {
        "size_px": "point_size.main",
        "point_shape": "circle",
        "fill": "color.main",
        "stroke": "color.main",
        "stroke_width_px": 0,
        "fill_opacity": 1,
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "line": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "segment": {
        "$include": "tick.main",
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "ray": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "circle": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "arc": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "conic": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "function": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "implicitcurve": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "polygon": {
        "stroke": "color.main",
        "stroke_width_px": "line_width.main",
        "fill": "color.background",
        "fill_opacity": 0,
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      },
      "angle": {
        "arc_size_px": "angle_radius.main",
        "arc_shift_px": "angle_radius.shift",
        "right_angle_size_px": "angle_radius.right",
        "stroke": "color.main",
        "stroke_width_px": "line_width.angle",
        "fill": "color.angle_fill",
        "fill_opacity": 1,
        "label_color": "color.main",
        "font_size_px": "font_size.main"
      }
    }
  },
  "rendering": {
    "background": "color.background",
    "line_cap": "round",
    "right_angle_joint": "miter",
    "points_display": "auto",
    "label_anchor": "BC"
  }
}
```

## Current Support And Gaps

Current library version audited by this context: `1.7.0`.

Already available:

- Public construction summary exporter:
  `scene.exportStylePromptSummary(filepath=None, **kwargs)`.
- Low-level exporter helpers:
  `construction_to_ai_summary(...)` and `write_ai_summary(...)`.
- Machine-readable style schema:
  `docs/ai_style_json_schema.json`.
- Runtime style validation through `StyleConfig.load(...)` /
  `StyleConfig.from_dict(...)`.
