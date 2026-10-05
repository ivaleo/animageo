# The AnimaGeo Style System — Complete Reference

> A detailed guide to everything visual in AnimaGeo: the JSON schema, per-element keys, z-index, labels and automatic label placement, ImportPolicy, fonts, units, pixel invariance, and the differences between static and animated output.

---

## Where to read about styles

| Document | When to read it |
|---|---|
| `docs/styles.md` | The main style reference: layer concept, JSON schema, resolver, units, overlay, rendering, import |
| `docs/architecture.md` | A short architectural map: how GGB/DSL flow through `applyStyle`, `StyleConfig`, `ImportPolicy`, `StyleOverlay` and the renderer |
| `docs/import_policies.md` | The GGB import/adaptation layer only: raw GGB values → `elem.ggb_style`, the `scale:` / `quantize:` / `remap:` DSL directives |
| `docs/field_names.md` | Correspondence table: GGB XML → `elem.ggb_raw` → `elem.ggb_style` / `elem.style` → JSON/style layer → renderer |

## Layer concept

Styles are split by responsibility, not by "whichever place is most convenient to write the key in":

| Layer | Responsibility | What belongs here | What does not |
|---|---|---|---|
| `presets` | Semantic tokens | Colors, sizes, widths, font sizes, tick/arrow presets | Selection rules for specific objects |
| `defaults` | Per-type baseline style | "All points look like this by default", "all angles have this arc radius" | Named exceptions, GGB-specific remaps |
| `import` | GeoGebra adaptation | Mapping of GGB colors/point sizes/line widths, `ImportPolicy` for raw-derived values | Project stylization by type/name |
| `overlay` | Overrides on top of import and DSL | `per_type`, `per_name`, auto angle radius, label placement | Parsing of raw GGB values |
| `reference` | Reference canvas of a style | Reference width/height for previews and scalable export | Physical size of the output file |
| `rendering` | Fine-grained output settings | Line cap, background, z/layer behavior, global point display | Styles of individual objects and GGB remaps |
| `elem.ggb_style` | Normalized result of GGB import/adaptation | Adapted GGB colors/sizes/line types/labels | Manual DSL/API edits |
| `elem.style` | Explicit per-element settings | Local edits from DSL/API | Project-wide rules and raw GGB values |

The short rule: **`import` answers "how to read GeoGebra", `overlay` answers "how to style the project", `rendering` answers "how to export/finish the drawing".**

---

## Contents

1. [Pipeline at a glance](#1-pipeline-at-a-glance)
2. [Units and pixel invariance](#2-units-and-pixel-invariance)
3. [Canvas, camera, export](#3-canvas-camera-export)
4. [Style JSON schema](#4-style-json-schema)
5. [Z-index: rendering layers](#5-z-index-rendering-layers)
6. [Per-element style: all keys](#6-per-element-style-all-keys)
7. [Labels and TeX](#7-labels-and-tex)
8. [Automatic label placement](#8-automatic-label-placement)
9. [ImportPolicy: flexible GeoGebra import](#9-importpolicy-flexible-geogebra-import)
10. [Statics vs animation](#10-statics-vs-animation)
11. [Keyframe animation and label interpolation](#11-keyframe-animation-and-label-interpolation)
12. [Batch API: bulk style changes](#12-batch-api-bulk-style-changes)
13. [Bundled presets](#13-bundled-presets)
14. [Recipes: "how do I get X"](#14-recipes-how-do-i-get-x)
15. [Known quirks and gotchas](#15-known-quirks-and-gotchas)
16. [Sizing & proportions: values that look right](#16-sizing-proportions-values-that-look-right)

---

## 1. Pipeline at a glance

```
.ggb → ggb_parser → Construction (Elements + ggb_raw + ggb_style)
                              │
                              ▼
             applyStyle(style=style.json, reference=..., content=..., export=...)
                              │
                              ├─ GeoStyle    (scene export context)
                              ├─ StyleConfig (builtin.json + user JSON deep-merged)
                              │   ├─ presets
                              │   ├─ defaults.<type>     ← per-type baseline
                              │   ├─ overlay.per_type    ← applies equally to GGB+DSL
                              │   ├─ overlay.per_name
                              │   ├─ overlay.angle_radius
                              │   └─ overlay.label_placement
                              └─ ImportPolicy (raw-GGB → elem.ggb_style:
                                               scale:/quantize:/remap:)
                              │
                              ▼  addAllGeometry
                   CreateMObject (Element → manim Mobject)
                      └─ resolver.resolve(scene, elem, key):
                          elem.style → per_name → per_type
                          → ggb_style → defaults
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                  SVG       MP4      Live-preview
```

Every element carries three blocks of style data:

| Source | When it is populated | What it determines |
|---|---|---|
| `elem.ggb_raw` | `ggb_parser` | Raw GGB values (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color.hex` / `obj_color.opacity`) |
| `elem.ggb_style` | `ggb_parser` + `applyStyle` import rules + `ImportPolicy` | The normalized GGB visual baseline. The resolver only reads it when `import.enabled` is not `false`. |
| `elem.style` | DSL/API code, layout/keyframe helpers | Explicit per-element entries. Wins over overlay, GGB import and defaults. |
| `scene.style_config` | `StyleConfig.load(style)` | The `presets`, `defaults`, `overlay`, `rendering`, `reference` configuration. Read through `resolver.resolve()`. |
| `GeoStyle` | `applyStyle` from JSON/dict | Scene-level container for the palette, renderer flags and the computed `export`. |

Rendering in `CreateMObject`, SVG/PNG/MP4 export and previews all read visual values through `resolver.resolve()`. GGB import, defaults, overlay and direct DSL writes therefore go through a single mechanism.

### Resolver priority chain

`resolver.resolve(scene, elem, key)` walks the layers top-down and returns the first hit:

```
1. elem.style[key]                  ← explicit DSL/API write
2. overlay.per_name[name][key]      ← targeted override
3. overlay.per_type[type][key]      ← by element type
4. elem.ggb_style[key]              ← GGB import/adaptation, if import.enabled != false
5. defaults.by_type[type][key]      ← builtin.json + user defaults (deep-merged)
6. intrinsic geometry style         ← internal fallback keys of the geometry classes
7. default=… (call argument)        ← final fallback
```

**Invariant**: the overlay (per_type/per_name) wins over GGB import/adaptation. Direct user writes into `elem.style` count as explicit and have the highest priority. The overlay is never materialized into `elem.style`; the render path reads it through the resolver.

### `builtin.json`

The package-shipped file `animageo/style/builtin.json` contains sensible pixel-unit defaults for every element type. It is **always** loaded first, and the user JSON is deep-merged on top (`deep_merge`). This makes a short user file like

```json
{"defaults": {"point": {"size_px": 10}}}
```

enough to override points while keeping all other defaults (colors, widths, angles, …).

### DSL elements get the overlay

`ImportPolicy` operates only on raw GGB values, so DSL elements are not
styled through it. Shared rules by type/name belong in
`overlay.per_type` / `overlay.per_name`; the resolver reads such rules
lazily and identically for GGB and DSL.

---

## 2. Units and pixel invariance

**Three unit systems** coexist in the project, and it is important not to mix them up.

| Space | Where it lives | Examples |
|---|---|---|
| **GGB px** | `ggb_raw`, `elem.ggb_style['*_px']`, `elem.style['*_px']`, `defaults.<type>.*_px` | Values straight from `.ggb`, the import layer, user styles, builtin.json |
| **Canonical style px** | `style/*.json` (`presets`, `defaults.*`, `overlay.*`) | All visual sizes in pixels |
| **Internal / manim** | Final mobject coordinates and stroke widths | What actually gets drawn |

Conversions are centralized in `animageo/style/scaling.py`:

```python
# GGB px → elem.ggb_style
ggb_point_size_to_style(x)       = x * 2             # pointSize → size_px
ggb_thickness_to_stroke_width(x) = x / 2             # thickness → stroke_width_px
ggb_arc_size_px(x, right=False)  = x  (or x/√2)      # arcSize → arc_size_px
ggb_label_offset_to_style(x, y)  = [x, -y]           # Y is inverted (GGB screen ↓ vs math ↑)

# render-time (resolved style → manim)
stroke_width_to_manim(sw, ptUnit) = sw * 100 / ptUnit
ggb_font_px_to_manim_fontsize(px, ptUnit) = px * 100 / ptUnit
```

> **Phase 4 unit fix.** In the canonical schema, sizes in `presets`, `defaults.*` and `overlay.*` are stored in pixels, and the renderer divides them by `ptUnit` exactly once. This removed the earlier double-scale that could collapse angle arcs on DSL scenes down to sub-pixel size.

### The pixel-invariance contract

**All** visible sizes — point diameters, line widths, font size, angle arc radii, label offsets — are stored in **pixel** units. The renderer divides them by `ptUnit_style`, so a style is computed relative to the reference canvas and scales together with the reference picture up to the physical `export.size`.

`ptUnit_ggb` is stored separately: it is the original scale from the `.ggb` file (pixels per GGB unit). Labels are scaled by it so that on a small canvas they do not detach from the geometry.

### Removed input keys

The historical keys `strich_len`, `strich_rshift`, `strich_width`,
`arrow_height`, `arrow_width`, `label_r_offset`, `line_width`, `ang_width`,
`ang_rdefault`, `ang_rshift`, `ang_right`, `font_size` are no longer accepted
in style JSON. Use the canonical fields (`tick_length_px`, `tick_shift_px`,
`tick_width_px`, `arrow_length_px`, `label_radial_offset_px`,
`stroke_width_px`, `arc_size_px`, `arc_shift_px`, `right_angle_size_px`,
`font_size_px`).

---

## 3. Canvas, camera, export

### Export parameters

```python
scene.style.export = {
    'ptUnit':   ...,   # pixels per manim unit in the final export
    'ptWidth':  ...,   # px — canvas width
    'ptHeight': ...,   # px — canvas height
    'ptXZero':  ...,   # px — position of the origin (0,0) from the left edge
    'ptYZero':  ...,   # px — position of the origin from the top edge
    'ptUnit_style': ..., # reference scale for visual *_px values
    'referenceWidth': ...,
    'referenceHeight': ...,
    'geometryScale': ..., # content -> reference
    'exportScale':   ..., # reference -> physical export
    'ptUnit_ggb': ..., # original ptUnit from the .ggb (for pixel-invariant labels)
    'fontSize': ...,   # GGB font size (px) from the XML gui.font
}
```

The modern layout separates three responsibilities:

```python
scene.loadGGB(
    'x.ggb',
    style='default',
    reference={'size': {'width': 300, 'height': 220}},  # runtime override
    content={'source': 'source_view', 'fit': 'contain'},
    export={'size': {'width': 1920, 'height': 1080}, 'fit': 'contain'},
)
```

Bare preset names passed as `style=` (`default`, `book_blue`, `book_green`, `book_purple`, `book_red`) resolve to style files packaged with the library (see [§13](#13-bundled-presets)); any path or `.json` filename is loaded from disk as usual, and an on-disk file with the same name always wins over a packaged preset.

- `reference` — the reference canvas the author designed the style for. Usually stored in the style JSON and overridden by the runtime argument only when needed.
- `content` — which region of the construction to place onto the reference: `source_view`/`ggb_view` or `rendered_bounds`; also `fit`, `padding`, `anchor`, `offset`, `infinite_policy`.
- `export` — the physical output file; this is a runtime setting and is not stored in style JSON.
- `ptUnit_style` — the reference-canvas scale. `stroke_width_px`, `size_px`, `font_size_px`, `arc_size_px`, offsets and all other visual pixels render through it.
- `ptUnit` — the scale of the final export canvas. The SVG/camera use it to place the whole picture.
- `geometryScale` — how much the content/source rect was scaled to fit the reference.
- `exportScale` / `contentScale` — how much the physical file magnifies the reference picture.
- `content.source='rendered_bounds'` first builds the visible mobjects at the source scale, measures their final bounds including labels, and then fits that rectangle. `content.padding` adds a margin in source pixels. For `Line`/`Ray` the default policy `content.infinite_policy='ignore'` excludes them from the bounds; `'clip'` measures them after clipping by the source camera.
- Non-uniform stretch is not implemented: the renderer still uses a single shared `ptUnit`.

A style may store its reference:

```json
{
  "reference": {
    "size": { "width": 300, "height": 220 },
    "source": "source_view"
  }
}
```

`reference.source` accepts `manual`, `source_view` or `ggb_view` and serves as
a description of where the reference came from in the style JSON. The runtime
choice of the construction region is made through `content.source`.

The full table of accepted values for the runtime blocks `style`, `reference`,
`content` and `export` is given in [docs/api.md](api.md).

`px_size` is no longer the primary public model. Use
`export={'size': {'width': w, 'height': h}}`; one side may be given as
`"auto"`.

---

## 4. Style JSON schema

The full documentation lives in the docstring of `animageo/style/schema.py`. Below is the structure and every key that is actually read.

```json
{
    "name": "string (optional)",
    "version": 0.1,

    "presets": {
        "color": {
            "main": "#000000",
            "bold": "#000000",
            "aux": "#888888",
            "accent": "#f15b5b",
            "background": "#ffffff",
            "strong": "#000000"
        },
        "point_size":  { "main": 2.83, "bold": 4.25, "aux": 2.12 },
        "line_width":  { "main": 1,    "bold": 1.5,  "aux": 0.75 },
        "angle_radius": { "main": 17, "shift": 1.5, "right": 17 },
        "tick":  { "main": { "tick_length_px": 9, "tick_width_px": 1.5, "tick_shift_px": 2 } },
        "arrow": { "main": { "arrow_length_px": 11, "arrow_width_px": 7.5 } },
        "font_size": { "main": 14, "bold": 16, "aux": 12 }
    },

    "defaults": {
        "point": {
            "size_px": "point_size.main",
            "fill": "color.strong"
        },
        "segment": {
            "$include": "tick.main",
            "stroke_width_px": "line_width.main"
        },
        "vector": {
            "$include": ["tick.main", "arrow.main"]
        }
    },

    "overlay": {
        "per_type": {
            "angle": { "arc_size_px": 22 },
            "point": { "size_px": 7 }
        },
        "per_name": {
            "A": { "size_px": 99 }
        },
        "angle_radius":    { /* see §8 */ },
        "label_placement": { /* see §8 */ }
    },

    "rendering": {
        "background":             "color.background",
        "line_cap":               "butt",
        "dash_period_px":         10,
        "right_angle_joint":      "round",
        "polygon_boundary_layer": "top",
        "points_display":         "auto",
        "label_anchor":           "BL",
        "label_value_precision":  1
    },

    "import": {
        "colors":     { "#1565c0": "color.main", "#d32f2f": "color.accent" },
        "point_size": { "5": "point_size.main" },
        "line_width": { "5": "line_width.main" },
        "policy":     { /* see §9 */ }
    }
}
```

> **The `overlay` section** (with its `per_type`/`per_name`) is the place for stylization applied after import. It works identically for GGB and DSL elements. `overlay.angle_radius` and `overlay.label_placement` are the only public location for the automation features.

### `presets` — semantic constants

`presets` is a registry of named semantic constants. The names `main`, `bold`,
`aux` are just a convention; users may add any names
(`construction`, `answer`, `hidden_helper`) and reference them from
`defaults`, `overlay`, `rendering` and the import mappings via
`"<group>.<name>"`, e.g. `"color.accent"` or `"line_width.bold"`.

### Main preset groups

| Group.key | Purpose | Units |
|---|---|---|
| `color.main` / `bold` / `aux` / `background` / `strong` | Named colors | hex |
| `point_size.main` / `bold` / `aux` | Point diameters (`size_px`) | style px |
| `line_width.main` / `bold` / `aux` | Line widths | style px |
| `angle_radius.main` / `shift` / `right` | Angle radii and shifts | px |
| `tick.main` | The `tick_length_px/tick_width_px/tick_shift_px` structure | px |
| `arrow.main` | The `arrow_length_px/arrow_width_px` structure | px |
| `font_size.main` / `bold` / `aux` | Font size | px |

Recommended values and the ratios that make a figure read comfortably are in
[§16 Sizing & proportions](#16-sizing-proportions-values-that-look-right).

### `defaults` — per-type baseline

`defaults` no longer stores scene-level `angle/tick/arrow/font` settings.
It is a per-type baseline: `defaults.point`, `defaults.segment`, `defaults.angle`,
and so on. Values here are usually references into `presets`.

Structural presets are pulled in via `$include`; local keys in the same
type block win over the included values. The old
`defaults.angle/tick/arrow/font` forms are still accepted by the loader and are
normalized into the semantic schema before merging.

### `rendering` — render options

| Key | Values | Effect |
|---|---|---|
| `background` | hex or `color.*` | Scene background: Manim camera/MP4 and the SVG viewport |
| `line_cap` | `"butt"` \| `"round"` \| `"square"` | Line endings |
| `dash_period_px` | number > 0 (px), default `10` | Style-wide dash period (dash + gap) for elements without their own `stroke_dash_period_px` |
| `right_angle_joint` | `"auto"` \| `"bevel"` \| `"miter"` \| `"round"` | Joint of the right-angle marker's sides |
| `polygon_boundary_layer` | `"top"` \| `null` | `"top"`: polygon outline always above the fill (`z_index=10`) |
| `points_display` | `"auto"` \| `"only_labels"` \| `"only_points"` | `only_labels` hides the point and shows the label; `only_points` — the reverse |
| `label_anchor` | `"TL"`/`"TC"`/`"TR"`/`"ML"`/`"MC"`/`"MR"`/`"BL"`/`"BC"`/`"BR"` | Scene-wide default label anchor (when not set per element). Full grid — §7 |
| `label_value_precision` | int | Scene-wide default precision of value labels |
| `fast_value_labels` | bool, default `true` | During animation, value labels are drawn with cached digit glyphs instead of a LaTeX recompile per frame; `false` forces LaTeX. Static export always uses LaTeX |
| `label_contrast` | `"off"` \| `"auto"`, default `"off"` | `"auto"` recolours a label that sits on a fill of similar luminance to a readable black or white |
| `label_contrast_threshold` | float, default `0.35` | Luminance gap below which `label_contrast: "auto"` recolours |
| `color_interpolation` | `"oklab"` \| `"srgb"`, default `"oklab"` | Color space for animated colors in keyframe style tracks |

`overlay.label_placement` and `overlay.angle_radius` are read directly from
`scene.style_config.overlay`; these automation features are not accepted under
`rendering`.

### `import` — mapping of GGB values

By default this is applied **on top** of the parsed GGB values after basic
parsing. If `"enabled": false` is set, the geometry and `elem.ggb_raw`
are preserved, but the resolver skips `elem.ggb_style`, takes the baseline from
`StyleConfig.defaults`, and `colors` / `point_size` / `line_width` /
`policy` are skipped entirely. After that, `overlay.per_type` /
`overlay.per_name` and explicit DSL/Python edits work in the usual order.

**`enabled`**: bool, default `true`.

**`colors`**: a dict of the form `"#hex [opacity]" → "color_name|#hex [opacity]"`. Lets you re-palette an entire construction with one line in the style.

```json
"colors": {
    "#1565c0":     "color.main",            // GGB blue → color.main
    "#1565c0 0.1": "color.light 1",         // same color but translucent → light with alpha=1
    "#d32f2f":     "color.accent",
    "#000000 0.6": "#2581b5"          // a hex value on the right works too
}
```

The result of applying a mapping is always normalized into two import-layer fields: the color is written to
`elem.ggb_style["fill"]` / `elem.ggb_style["stroke"]` as `#rrggbb`, and the opacity
is written to `fill_opacity` / `stroke_opacity` only when it is explicitly given
on the right-hand side of the mapping. If the target opacity is not given, the element's
current opacity is preserved.

For example, `"#1565c0 0.1": "color.accent 1"` yields
`fill = "#f15b5b"` and `fill_opacity = 1.0`; `"#1565c0 0.1": "color.accent"` replaces
only the color and keeps the previous `fill_opacity`.

**`line_width`**: a thickness mapping `"N": "line_width.*"` (e.g. `"5": "line_width.main"` — GGB thickness 5 → `line_width.main`).

**`point_size`**: the same for point sizes.

**`policy`**: see §9.

### GGB Graphics View: grid and axes

During `loadGGB()` the parser reads the `<euclidianView>` settings from `geogebra.xml`
and stores them in `scene.style.export`. These fields are not a style overlay for
geometric elements: they describe the background of the coordinate area.

| GGB XML | `style.export` | Usage |
|---|---|---|
| `<evSettings axes>` | `showAxes` | Enables background axis drawing |
| `<evSettings grid>` | `showGrid` | Enables the background coordinate grid |
| `<evSettings gridIsBold>` | `gridIsBold` | Makes the grid lines slightly heavier |
| `<evSettings gridType>` | `gridType` | Stored for compatibility; a Cartesian grid is rendered for now |
| `<axesColor r g b>` | `axesColor` | Color of the axes, ticks and numbers |
| `<gridColor r g b>` | `gridColor` | Color of the grid lines |
| `<grid distX distY distTheta>` | `gridDistX`, `gridDistY`, `gridDistTheta` | Grid spacing along X/Y; `distTheta` is stored for future polar/isometric modes |
| `<axis id="0|1" show>` | `axes.x.show`, `axes.y.show` | Visibility of an individual axis |
| `<axis ... showNumbers>` | `axes.x.showNumbers`, `axes.y.showNumbers` | Numeric tick labels |
| `<axis ... tickDistance>` | `axes.x.tickDistance`, `axes.y.tickDistance` | Axis tick spacing |
| `<axis ... axisCross positiveAxis>` | `axes.*.axisCross`, `axes.*.positiveAxis` | Stored; full crossing/positive-only rendering is not enabled yet |

`addAllGeometry()` adds `_coordinate_background` before the geometry:
the grid is drawn at `z_index=-20`, the axes at `z_index=-10`, ticks and numbers at
`z_index=-9`. This is a separate background, not the service elements `xAxis` / `yAxis`
from `Construction`.

---

## 5. Z-index: rendering layers

```
┌──────────────────────────────────────────────────────┐
│   Z_POINT  = 50     ← points (topmost)               │
│   Z_LABEL  = 50     ← labels at stroke level         │
│   Z_STROKE =  5     ← segments, ticks, arc outlines  │
│   Z_LINE   =  4     ← lines, circles                 │
│   Z_ANGLE  =  3     ← angle arcs                     │
│   Z_FILL_LABEL = 0.1 ← labels at fill level          │
│   Z_FILL   =  0.01  ← polygon/sector fills           │
│   Z_FILL_INNER = 0.001 ← reserved bottom fill        │
└──────────────────────────────────────────────────────┘
             (lower = farther back; higher = closer to the viewer)
```

### Automatic assignment

With `z_auto=True` (`addAllGeometry`, `addGeoElement`) `CreateMObject` assigns the z-index by element type:

| Type | Main layer | Fill | Label |
|---|---|---|---|
| `Point` | `Z_POINT` (50) | — | `Z_LABEL` (50) |
| `Segment` / `Circle` / `Arc` / `Vector` | `Z_STROKE` (5) | — | `Z_LABEL` (50) |
| `Angle` | `Z_ANGLE` (3) | — | `Z_LABEL` (50) |
| `Polygon` | `Z_FILL` (0.01) | — | `Z_FILL_LABEL` (0.1) |
| `CircleSector` | `Z_FILL` (0.01) | `Z_FILL` (0.01) | `Z_FILL_LABEL` (0.1) |

A polygon's stroke overlay is always ≥ `max(Z_STROKE, zz+0.1)` — the outline stays above the fill. If `rendering.polygon_boundary_layer = "top"`, the polygon's side segments are placed at `z_index=10` (above everything except points/labels).

For MP4 animation stability, AnimaGeo adds a very small tie-breaker to every actual
Manim `z_index` based on the element's order in the construction
(`construction_index × 1e-6`). This does not change the `fill`/`stroke`/`point` levels,
but makes the order within a single layer deterministic even when a `Polygon`
is recreated via remove+add during `updateGeoElements()`.

### Explicit override

```python
scene.element('poly').style['z_index'] = 100          # polygon above the points
scene.element('sector').style['z_index_fill'] = 0.2   # CircleSector only
```

If the `z_index` key is set explicitly, the automatic assignment does not kick in.

An element that is undefined in the loaded `.ggb` (NaN coordinates, e.g. an
intersection that does not exist in the saved state) and becomes defined later
keeps its type's layer and label defaults.

---

## 6. Per-element style: all keys

`elem.style` is a plain Python dict that can be modified on the fly. Below is the **exhaustive list** of what the renderer actually reads.

### Visibility

| Key | Type | Default | What it does |
|---|---|---|---|
| `elem.visible` (attribute, not a key) | bool | `True` | Hides the mobject entirely |
| `visible` | bool | `True` | GGB "Show object"; read through the resolver |
| `label_visible` | bool | Element-dependent | Draw the label |

### Stroke (SVG-compatible names)

| Key | Type | Default |
|---|---|---|
| `stroke` | hex | `style.strong` |
| `stroke_width_px` | float (px) | `defaults.<type>.stroke_width_px` |
| `stroke_opacity` | float 0..1 | `1` |
| `stroke_dash_ratio` | float 0..1 \| None | None (solid); the dash's share of one period, `0`/`None` or `>= 1` = solid |
| `stroke_dash_period_px` | float (px) | `rendering.dash_period_px` (10) |
| `stroke_linecap` | `"butt"`/`"round"`/`"square"` (`"auto"` is also accepted by the runtime map) | `rendering.line_cap` |
| `right_angle_joint` | `"auto"`/`"bevel"`/`"miter"`/`"round"` | `rendering.right_angle_joint` |

### Fill

| Key | Type | Default |
|---|---|---|
| `fill` | hex | `style.background` (for points — `style.strong`) |
| `fill_opacity` | float 0..1 | `1` |

### Points

| Key | Type | Default | Effect |
|---|---|---|---|
| `size_px` | float (px) | `style.dot_size` | diameter = `size_px / 2 / ptUnit` |
| `point_shape` | enum string | `"circle"` | Shape: `"circle"`, `"square"`, `"diamond"`, `"triangle_up"`, `"triangle_down"`, `"triangle_left"`, `"triangle_right"`, `"cross"`, `"plus"`. See the GGB preset mapping in `docs/field_names.md` §3.3. |

### Angles

| Key | Type | Default | Effect |
|---|---|---|---|
| `arc_size_px` | float (px) | `defaults.angle.arc_size_px` | Base arc radius |
| `arc_shift_px` | float (px) | `defaults.angle.arc_shift_px` | Radial shift between concentric arcs when `tick_count > 1` |
| `angle_range` | `"minor"` \| `"reflex"` | From GGB | `"minor"` = the smaller sector (≤π), `"reflex"` = the reflex one (>π) |
| `right_angle_marker` | bool | Auto: `np.isclose(angle, π/2)` | Force the square right-angle marker |
| `right_angle_size_px` | float (px) | `defaults.angle.right_angle_size_px` | Size of the square right-angle marker |
| `tick_count` | int | 1 | Multiple arcs (double, triple arc marks) |

### Segments / vectors

| Key | Type | Default | Effect |
|---|---|---|---|
| `tick_count` | int | None (key may be absent) | Number of tick marks at the midpoint |
| `tick_style` | `"line"` \| `"wave"` | `"line"` | `"wave"` — a wavy mark instead of straight ticks |
| `tick_radius_px` | float | `tick_shift_px * 0.45` | Corner rounding radius for `tick_style="wave"` |

### Labels

| Key | Type | Default | Effect |
|---|---|---|---|
| `label_text` | TeX string | `"$" + elem.name + "$"` | Displayed text |
| `label_mode` | `"label"` \| `"value"` \| `"label_value"` | `"label"` | What to show: the label, the computed value, or `label = value` |
| `label_value_precision` | int | `1` | Number of decimal places for the computed value |
| `label_value_strip_zeros` | bool | `True` | Strip trailing zeros (`5.00` → `5`) |
| `label_angle_unit` | `"degree"` \| `"radian"` | `"degree"` | Unit for angle values |
| `label_value_separator` | str | `" = "` | Separator in `label_value` mode |
| `label_color` | hex | `style.strong` | Text color |
| `label_anchor` | `"TL"`..`"BR"` | `rendering.label_anchor` \| `BL` | Which part of the label bbox lands on the anchor point |
| `label_offset_px` | `[x, y]` (GGB px) | `[0, 0]` | Label offset after positioning; divided by `ptUnit_ggb` |
| `font_size_px` | float (px) | `defaults.<type>.font_size_px` | Per-element font size override |
| `label_radial_offset_px` | float (px) | `defaults.angle.label_radial_offset_px` (`0`) | Radial label offset from the geometry (used for angles) |
| `label_placement_locked` | bool | `False` | Protects the label from auto-placement |
| `label_hint_px` | `[x, y]` (GGB px, y up) | — | Where the label centre should be, relative to the element's anchor; a soft request to auto-placement (§ "A hint instead of a lock") |
| `_auto_placed` | bool | `False` (internal) | Set by the auto-layout; disables the GGB descender correction in `create_label` |

### Z-index (see §5)

| Key | Type | Default |
|---|---|---|
| `z_index` | float | By type |
| `z_index_fill` | float | `Z_FILL` |

---

## 7. Labels and TeX

### The 9-point anchor

```
    TL ── TC ── TR
    │          │
    ML   MC   MR
    │          │
    BL ── BC ── BR
```

The anchor is set in `elem.style['label_anchor']` or scene-wide in `rendering.label_anchor`. `MC` = "label centered on the point" (convenient for angles and for interaction with auto-placement — see `canonicalize_anchor`).

GeoGebra uses `BL` by default (bottom-left = the baseline for capital letters).

### The RusTex TeX template

`animageo/ui.py::RusTex` — `pdflatex` + `T2A`/`babel russian`/`utf8`, custom fraction rendering, `\angle` and `\triangle` at a reduced size.

### Automatic Unicode → TeX replacement

`correctedLabel(label)` runs the text through a dictionary of 84 substitutions (`·`→`\cdot`, `α`→`\alpha`, `△`→`\triangle`, …), which lets you write formulas in labels using plain Unicode.

### Labels placed in GeoGebra

A label of a GGB element that has no explicit `label_anchor` (in the element's
style, `overlay` or `defaults`) and is not auto-placed is positioned the way
GeoGebra does it. GeoGebra starts from a base point that depends on the element
type and adds the stored `labelOffset`:

| Element | Base point |
|---|---|
| Point | 4 px right of and 2·point size above the point |
| Segment | midpoint, 16 px along the normal |
| Vector | midpoint, shifted sideways by a quarter of the arrow size |
| Ray | midpoint of the vertex and the second point, shifted 16 px by the reflected direction `(uₓ, −u_y)` (GeoGebra's rule) |
| Polygon | average of the vertices |
| Circle, ellipse | point on the upper-left arc of the outline, 20 px inward |
| Arc, sector | point of the arc at its middle, offset by (6, 6) px |
| Line | no rule: keeps the general placement (GeoGebra measures from the applet window border) |
| Angle | no rule: angles keep their own placement |

The rules are in `animageo/label_anchor.py` (`ggb_label_anchor`). A scene-wide
`rendering.label_anchor` does not apply to these labels; set `label_anchor` on
the element (or enable auto-placement) to override.

When the figure is exported at a different scale than the applet, the label is
re-attached to the point of its element nearest to where the applet drew it
(`label_anchor.nearest_point`; nothing is stored, it is recomputed from the
offset on each render). That point scales with the figure and only the rest of
the offset stays in font space, so the gap to the line holds at any font size.
A label inside a region (polygon, sector, inside of a circle or ellipse) sticks
to its own spot of the region. Points are unaffected. Circles and ellipses
draw their labels like other elements.

### GGB descender correction

A GGB offset targets the bottom of the input box (including its descender padding). The TeX bbox is tight, so the label would sag below. `create_label` automatically raises it by `ggb_font_px * 0.25 / ptUnit`, **unless** `_auto_placed` is set (auto-placed labels already have correct offsets).

---

## 8. Automatic label placement

Works in three modes: **static one-shot**, **keyframe snapshots** (for `play_keyframes`), and a **per-frame tracker** (for `addUpdater`).

### Static — the default

```python
scene.loadGGB(
    'x.ggb',
    style='default',
    export={'size': {'width': 800, 'height': 600}},
)
scene.autoPlaceLabels()
scene.exportSVG('out.svg')
```

A greedy solver lays out the labels, minimizing overlaps. 8 candidate directions (E/NE/N/NW/W/SW/S/SE); the most "constrained" labels (fewest free positions) are placed first.

### `overlay.label_placement` parameters

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Automatically call `autoPlaceLabels()` at the end of `loadGGB` |
| `distance_px` | `6` | Base distance anchor → label center, px |
| `padding_px` | `2` | Margin around the bbox when checking overlaps, px |
| `angle_gap_arc_px` | `3` | Gap between the angle's outer arc and its label, px. Independent of the sides gap |
| `angle_gap_sides_px` | `3` | Gap between the angle's sides and the label bbox (for narrow angles), px |
| `w_anchor` | `1.0` | Penalty weight for deviating from the preferred direction |
| `w_label` | `10.0` | Weight for label×label overlap |
| `w_geom` | `8.0` | Weight for label×geometry overlap |
| `dynamic_angles` | `false` | Angle bisectors are recomputed per frame |
| `keyframe_snapshots` | `false` | The layout is computed at each keyframe and interpolated in between. Takes effect only with `enabled: true`; the snapshots then own every label position in `play_keyframes` (a keyframe `label_offset_px` track is ignored) |
| `canonicalize_anchor` | `false` | Rewrites all anchors to `MC` with a compensating offset. Removes jumps during interpolation. Off by default: it rewrites recorded label anchors, so existing outputs shift |
| `interpolation` | `"linear"` | Easing of label offsets between snapshots: `linear` or `smooth` |
| `ema_alpha` | `0.2` | Weight of the fresh solver result in the EMA (0..1); smaller → smoother but slower to converge |
| `anchor_flip_frames` | `6` | Schmitt trigger: how many consecutive frames the solver must propose a different anchor |
| `solver_every_n_frames` | `2` | Throttling: the solver runs once every N frames |

### Angles: analytical placement instead of candidates

For an Angle, the label is always placed on the bisector. The distance:

```
dist = arc_radius_effective + max(half_w, half_h) + gap_arc
# additionally, for narrow angles:
dist ≥ (√(hw² + hh²) + gap_sides) / sin(half_angle)
```

`arc_radius_effective` accounts for multiple arcs: with `elem.style['tick_count'] = N` the outer radius is `arc_size_px + (N - 1) * arc_shift_px`, so the label never sits on the outermost arc even when there are several.

`gap_arc` (`angle_gap_arc_px`) controls the clearance between the arc and the label, while `gap_sides` (`angle_gap_sides_px`) controls the clearance between the label and the angle's sides (it enters the clamp for narrow angles). The defaults are usually fine; separate settings are useful, for instance, when the angle is very acute and the label needs to be "sunk" closer to the arc without increasing the overall margin.

The anchor is always `MC`.

### Locking a label manually

```python
scene.element('A').style['label_placement_locked'] = True
scene.element('A').style['label_offset_px'] = [10, -5]
```

### A hint instead of a lock

A locked label stays exactly where `label_offset_px` puts it, whatever is
drawn there. When you only know *which side* the label belongs on — the
position comes from another drawing, from a model, from a rule of thumb —
give auto-placement a hint and let it do the rest:

```python
scene.element('A').style['label_hint_px'] = [-12, -10]   # below-left of A
```

`label_hint_px` is the desired offset of the label **centre** from the
element's anchor — the point itself, a segment's midpoint, an angle's vertex —
in the same pixels as `label_offset_px`, y up. On a point it is the same pair
of numbers you would write into `label_offset_px` with `label_anchor='MC'`.

What auto-placement does with it:

- The label keeps the hinted **side**: at a vertex it goes into the sector the
  hint points into and keeps the hinted direction there (held ~28° away from
  the sector's edges); a free point's label goes in the hinted direction. A
  segment's label takes the hinted side of the segment.
- The **distance** is the layout's own (compact, clear of the marker and of
  the lines), so a hint may be rough. Where the hinted direction would put the
  label far from its point — next to a line it has to clear — the label turns
  toward the middle of the sector, 45° at most.
- The hinted side is kept while the label can sit **within 1.6 font sizes** of
  its point there. A sector that needs more — two lines close together, a line
  across the hinted side — gives way to the neighbouring sector nearest the
  hint, when the label sits that close there; otherwise the hinted side
  stands. A sector too narrow for the label at all gives way to the next one.
- The label is **not locked**: if the hinted place is taken by a line or by
  another label, it moves along, staying as close to the hint as it can.
- The hint is read on every placement pass and outranks a manual or GeoGebra
  offset; `label_placement_locked` outranks the hint. It works whether or not
  `respect_current_position` is on.

Two rules outrank a hint, because a copied position may be wrong:

- an **angle label stays inside its angle** while it fits there — a hint that
  points outside moves it out only when the angle is too narrow for the label.
  "Fits" means clear of both sides and not past the end of the shorter one;
  if `angle_label_max_arm_fraction` stops the label where it still touches a
  side, such a label goes further in, to where it fits, instead of going out;
- the label of a **point on a closed figure** (a polygon, or segments joined
  into a cycle) stays **outside the figure** while there is room outside. When
  there is none — a circle runs close along the figure, say — a hint that
  points inside is followed.

A hint only takes effect when placement runs. `loadGGB` places labels once;
for elements created or hinted later by `putCode`/`loadCode`, call
`scene.autoPlaceLabels()` afterwards. Without a hint nothing changes.

### Dynamics and keyframe snapshots

See §11.

### Automatic angle-arc radius: `overlay.angle_radius`

When an angle is narrow (small measure), its arc at a fixed `arc_size_px` visually disappears between the two close sides. With `angle_radius` enabled, the base radius is scaled by `base * (pivot / angle) ** exp` and then clamped to `[min_px, max_arm_fraction · min(|v1|,|v2|) · ptUnit]`.

The JSON location is `overlay.angle_radius`.

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Opt-in. Off by default so GGB import stays byte-for-byte faithful |
| `exp` | `0.25` | The exponent in `(pivot / angle)^exp`. `0` = no auto-scaling |
| `pivot_rad` | `π/2` | The measure at which scale = 1.0 (wider angles → smaller, narrower → larger) |
| `min_px` | `12` | Lower floor on the radius, pixels |
| `max_arm_fraction` | `0.65` | Upper cap as a fraction of the shorter arm's length |
| `apply_to_right` | `false` | Whether to apply the clamps (min/max) to the right-angle marker |

Per-element escape: `elem.style['auto_radius'] = False` pins `arc_size_px` for that specific angle even when the global flag is on.

The label automatically follows the new radius: `_collect_labels` and the renderer use the same `compute_effective_arc_size_px` function, so the label always stays beyond the outer arc.

```json
"overlay": {
    "angle_radius": {
        "enabled": true,
        "exp": 0.3,
        "min_px": 14,
        "max_arm_fraction": 0.55
    }
}
```

---

## 9. ImportPolicy: flexible GeoGebra import

`ImportPolicy` controls how values from a `.ggb` file become `elem.ggb_style` during `loadGGB`. The full cookbook is in `docs/import_policies.md`.

### Where it comes from

Priority (lowest → highest):

1. Defaults: `ImportPolicy.faithful()` — as in GGB.
2. `import.policy` inside the style JSON.
3. `loadGGB(..., import_policy=...)` — an explicit argument.
4. `setElementStyle()` — after loading.

### Fields

Each field accepts: `None` (fallback), a literal (number/bool/list/dict/hex), a Python callable `fn(raw, defaults, elem)`, or a DSL string.

| ImportPolicy field | GGB source | `elem.ggb_style` key |
|---|---|---|
| `size_px` | `<pointSize val>` | `size_px` |
| `stroke_width_px` | `<lineStyle thickness>` | `stroke_width_px` |
| `arc_size_px` | `<arcSize val>` | `arc_size_px` |
| `label_offset_px` | `<labelOffset x y>` | `label_offset_px` |
| `label_color` | `<objColor>` as `obj_color.hex` | `label_color` |
| `label_visible` | `<show label>` | `label_visible` |
| `visible` | `<show object>` | `visible` |
| `label_text` | `<caption>` | `label_text` |
| `angle_range` | `<angleStyle val>` | `angle_range` |
| `tick_count` | `<decoration type>` | `tick_count` |
| `font_size_px` | literal / callable (`raw=None`) | `font_size_px` |
| `stroke` | `<objColor>` as `obj_color.hex` | `stroke` |
| `fill` | `<objColor>` as `obj_color.hex` | `fill` |
| `fill_opacity` | `<objColor alpha>` as `obj_color.opacity` | `fill_opacity` |
| `point_shape` | `<pointStyle val>` | `point_shape` |
| `stroke_opacity` | `<lineStyle opacity>` | `stroke_opacity` |
| `stroke_dash_ratio` | `<lineStyle type>` | `stroke_dash_ratio` |
| `stroke_dash_period_px` | — | `stroke_dash_period_px` |
| `stroke_linecap` | — | `stroke_linecap` |

`elem.ggb_raw['obj_color']` stores `r/g/b`, legacy `alpha`, plus normalized
`hex` and `opacity`, so remaps can work with `#rrggbb` and opacity directly.

### Mini-DSL

| Directive | Effect |
|---|---|
| `"const:3"` | The fixed value `3` |
| `"scale:1.5"` | Multiply the raw GGB input by `1.5` |
| `"quantize:[1,2,4]"` | Snap to the nearest list element |
| `"remap:{'#f00':'#c00'}"` | Dictionary lookup; miss → original value |
| `"match_element"` | Copy the stroke color into the label (sentinel) |
| `"auto"` | Delegate to the downstream algorithm (sentinel) |

### Hot-swap without reparsing

```python
scene.reloadPolicy(ImportPolicy(size_px=5))
```

Uses the cached `elem.ggb_raw`; the XML is not re-read.

---

## 10. Statics vs animation

| Aspect | Static (SVG) | Animation (MP4) |
|---|---|---|
| **Labels** | One-shot `autoPlaceLabels()` | `keyframe_snapshots` + offset interpolation, or the per-frame tracker |
| **Angles** | Bisector computed once | `dynamic_angles` → analytical recompute every frame |
| **Z-index** | Read at export time | Reassigned during `updateGeoElements`; equal layers are stabilized by the construction-order tie-breaker |
| **stroke_linecap** | Visible | Visible; `butt` gives a sharp end, `round` a smooth one |
| **Font** | GGB descender correction | Same correction, but `_auto_placed=True` disables it |
| **ptUnit** | Fixed after `applyStyle` | Fixed; camera changes do not recompute it |

### Canvas size and animation

When rendering MP4, manim uses `config.pixel_width/pixel_height`, not `style.export.ptWidth`. `applyStyle` reconciles the camera with the export size via the aspect ratio; if it does **not** match the manim canvas, the active area is fitted along the smaller side.

For MP4 the consumer must explicitly reconcile the Manim config with the physical export size: `config.pixel_width/config.pixel_height = export["size"]`. The library does not pick a web-quality preset and must not guess bitrate/fps; those decisions stay at the application or service level.

---

## 11. Keyframe animation and label interpolation

### JSON format

```json
{
  "keyframes": [
    {"t": 0, "values": {"A": [0, 0], "x": 35, "D": {"tparam": 0.0}}},
    {"t": 2, "values": {"A": [4, 4], "x": 110,
                         "D": {"tparam": 3.14, "direction": "ccw"}},
             "show": ["line1"], "hide": ["aux"], "easing": "smooth"},
    {"t": 4, "values": {"A": [0, 0], "x": 35}}
  ]
}
```

### Independent element types

| Type | JSON format | Interpolation |
|---|---|---|
| `free_point` | `[x, y]` | Linear on coordinates |
| `tparam_point` (circle) | `{"tparam": rad, "direction": "short"\|"cw"\|"ccw"}` | Angular |
| `tparam_point` (segment/line) | `{"tparam": 0..1}` | Linear |
| `number` / `measure` | `float` | Linear |
| `angle` | `float` (rad) | Linear |
| `boolean` | `true`/`false` | Snap at t=0.5 |

### Easing

`linear`, `smooth` (default), `smootherstep`, `in`, `out`, `in_out`,
`ease_in_sine`, `ease_out_sine`, `ease_in_out_sine`, `ease_in_cubic`,
`ease_out_cubic`, `ease_in_out_cubic`, `rush_into`, `rush_from`,
`ease_out_back`, `ease_out_elastic`, `ease_out_bounce`.

### Integration with auto-placement

Enable together:

```json
"overlay": {
    "label_placement": {
        "keyframe_snapshots":  true,
        "dynamic_angles":      true,
        "canonicalize_anchor": true,
        "interpolation":       "smooth"
    }
}
```

- `keyframe_snapshots` — (requires `enabled: true`) a pre-pass computes the layout at every keyframe (with state save/restore); offsets between snapshots are interpolated.
- `dynamic_angles` — angle bisectors are recomputed analytically every frame.
- `canonicalize_anchor` — all static anchors are converted to `MC` with compensation, removing discrete jumps.

Without `keyframe_snapshots` or `autoPlaceLabels(dynamic=True)`, the `dynamic_angles` flag **does nothing** (deliberately — the integration is explicit).

### The `addUpdater` tracker

```python
scene.loadGGB(
    'x.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
x = scene.addVar('x', 0)
scene.autoPlaceLabels(dynamic=True)   # installs the LabelTracker
with scene.animating(x):
    scene.play(x.animate.set_value(1), run_time=3)
scene.clearLabelTracker()
```

EMA smoothing (`ema_alpha`) + Schmitt-trigger anchor hysteresis (`anchor_flip_frames`) prevent jitter.

---

## 12. Batch API: bulk style changes

### `setElementStyle`

```python
scene.setElementStyle(['a', 'b', 'c'],
                      stroke='#ff0000',
                      stroke_width=3,
                      fill_opacity=0.5)
```

Walks the list of names and writes every pair into `elem.style`.

### `setVisible`

```python
scene.setVisible(['A', 'B', 'C'], False)
```

### The `animating` context manager

```python
x = scene.addVar('x', 0)
with scene.animating(x):
    scene.play(x.animate.set_value(1), run_time=3)
```

Equivalent to `addUpdater` → `try/play/clearUpdater`.

### Animation helpers

| Method | Description |
|---|---|
| `Show(names, mode='Fade'\|'Create')` / `playShow` | Show elements |
| `Hide(names)` / `playHide` | Hide |
| `Shade(names)` / `playShade` | Dim (changes stroke/fill to `col_shade`) |
| `Restore(names)` / `playRestore` | Restore from Shade |
| `Update(names)` / `playUpdate` | FadeOut → recreate → FadeIn |
| `UpdateAll()` | The same for the whole scene |
| `ShowCreate(name)` | Create for lines, Fade for fills and angles |

---

## 13. Bundled presets

Five style presets ship inside the package (`animageo/style/presets/`). Pass a bare preset name as the `style=` argument and it resolves to the packaged JSON (`animageo/style/config.py::resolve_style_input`); an on-disk file with the same name always wins over a packaged preset.

```
default        Blue/red palette (baseline; same palette as book_blue)
book_blue      Print-oriented, blue
book_green     Print-oriented, green
book_purple    Print-oriented, purple
book_red       Print-oriented, red (blue accent)
```

```python
scene.loadGGB('x.ggb', style='book_green')
```

`available_style_presets()` in `animageo.style.config` returns the current list of packaged preset names.

---

## 14. Recipes: "how do I get X"

### Unify all labels to one color and size

```python
ImportPolicy(font_size_px=14, label_color='#222222')
```

### Points of one size

```python
ImportPolicy(size_px=3)
```

### Quantize line widths

```python
ImportPolicy(stroke_width_px='quantize:[1, 2, 4]')
```

### Branding: swap the palette

In JSON:
```json
"import": {
    "colors": {
        "#1565c0": "color.main",
        "#d32f2f":     "color.accent"
    }
}
```

Or via `ImportPolicy`:
```python
ImportPolicy(stroke="remap:{'#1565c0':'#0066cc','#d32f2f':'#c04040'}")
```

### A double angle arc

```python
scene.element('α').style['tick_count'] = 2
scene.element('α').style['arc_shift_px'] = 3  # 3 px farther out
```

### A polygon "above everything"

```json
"rendering": { "polygon_boundary_layer": "top" }
```

Or per element: `scene.element('poly').style['z_index'] = 100`.

### Hide all labels

```python
ImportPolicy(label_visible=False)
```

### Scalable 2× export

```python
scene.loadGGB(
    'x.ggb',
    style='default',
    reference={'size': {'width': 800, 'height': 600}},
    export={'size': {'width': 1600, 'height': 1200}},
)
```

The geometry and the visual `*_px` sizes are scaled 2× relative to the
[800, 600] reference canvas.

### Wave ticks on equal sides

```python
scene.element('a').style['tick_count'] = 2
scene.element('a').style['tick_style'] = 'wave'
scene.element('a').style['tick_radius_px'] = 1.5
```

### A label above a point

```python
scene.element('A').style['label_anchor'] = 'BC'  # bottom-center anchor = label above the point
scene.element('A').style['label_offset_px'] = [0, 10]      # 10 px higher (positive Y = up in math coords)
```

### Labels only, no points (a "letters" diagram)

```json
"rendering": { "points_display": "only_labels" }
```

---

## 15. Known quirks and gotchas

Details in `docs/gotchas.md`. In brief:

1. **`dynamic_angles=true` does nothing by itself** — you need either `keyframe_snapshots=true` or `autoPlaceLabels(dynamic=True)`. This is deliberate, so the flag is cheap to keep in a config.
2. **`canonicalize_anchor=true` rewrites recorded label anchors**, so existing outputs shift. Off by default; enable it only for smooth animation.
3. **The TeX bbox cache is process-wide.** The key is `(label_text, font_size)`, so it is reused correctly between scenes in one process. Manual changes to `RusTex` require `clear_bbox_cache()`.
4. **`Polygon.become()` is buggy in manim** → `updateGeoElements` handles polygons via remove+add.
   The layer order must not drift as a result: the actual Manim `z_index` values
   get a micro-shift based on the element's order in the construction.
5. **An updater on an animated ValueTracker only sees start/end** — which is why `play_keyframes` uses a sentinel Mobject.
6. **`elem.ggb_raw` is empty for elements created via the Python DSL** — `ImportPolicy.resolve_overrides_only()` will receive `raw=None`.
7. **`right_angle_marker` auto-detects via `np.isclose(angle, π/2)`** — it may falsely trigger around ~89.5°–91°; set `right_angle_marker=True/False` explicitly when precision matters.
8. **`arc_size_px` overrides `r_offset`** — if both are set, `r_offset` is ignored.
9. **Removed visual fields are rejected.** The old `line_width`, `font_size`, `strich_*`, `arrow_*`, `label_r_offset`, `ang_*` keys in style JSON are rejected; use the canonical `*_px` keys.

---

## 16. Sizing & proportions: values that look right

Every `*_px` size is resolution-independent (§2), so what makes a figure look
"comfortable" is not the absolute numbers — it is (a) the **ratios between the
size families** and (b) their size **relative to the reference canvas**. This
section gives the calibrated ranges used by the shipped presets (builtin
defaults, the AI-guide starter style, and the production Pandora style all sit
inside them).

### The ratio system

Treat `line_width.main` as the base unit of visual weight. On a reference
canvas around **800×600** the comfortable ranges are:

| Family | `main` | `bold` | `aux` | Anchor ratio |
|---|---|---|---|---|
| `line_width` | 1.5–2 | ≈1.6× main (2.5–3.3) | ≈0.6× main (0.75–1.5) | base unit |
| `point_size` (diameter) | 6–8 | 9–10 | 4–5 | **3.5–4.5 × line width** |
| `font_size` | 14–17 | 16–20 | 12–14 | **2–2.5 × point diameter** |
| `angle_radius` | 17–20 | 24 | 12 | **1.0–1.2 × font size**; `right` ≈ 0.8–0.9 × main; `shift` 1.5–3 |
| `tick.tick_length_px` | 9–10 | — | — | 5–6 × line width |
| `arrow.arrow_length_px` | 10–11 | — | — | 6–7 × line width |

Relative to the canvas: a point diameter is ≈ **1% of the canvas width**, a
label is ≈ **2.5–3% of the canvas height**. Keep the *ratios between families*
fixed when you tweak any one of them — the classic "плохой чертёж" symptoms are
exactly broken ratios:

- **Giant dots on thin lines** — point/line ratio far above 4.5. Either grow
  `line_width` or shrink `point_size`, not one alone.
- **Angle arcs dwarfing the triangle** — the arc radius must stay visibly
  shorter than the shortest arm it marks. If a construction has small angles or
  short arms, don't hand-tune every `arc_size_px`: enable
  `overlay.angle_radius` (auto-scaling with `min_px` / `max_arm_fraction`
  clamps, §6) and let the renderer and label solver share the resolved radius.
- **Labels shouting over the figure** — `font_size.main` above ~2.5× point
  diameter starts to compete with the geometry. Step labels down (`aux`), not
  the geometry up.
- **Ticks/marks invisible** — tick length below ~5× line width disappears at
  typical DPI; the builtin 9 px is already conservative, avoid going lower.

### Scaling with the canvas

The reference canvas is what `*_px` values are measured against (§2–3). Rules:

1. **Prefer keeping the reference canvas in the 700–1000 px class** and raise
   only the physical output (`export.size`, or `config.pixel_*` for manim
   renders). The picture scales losslessly; no style change needed
   (see "Scalable 2× export" in §14).
2. If you *do* design for a different reference class (e.g. 1600×1200 posters),
   scale **all** px families by the same factor — the canvas diagonal ratio is
   a good multiplier (800×600 → 1600×1200 means ×2 on every px value).
3. For 16:9 video use a 960×540 reference: its diagonal is ~10% larger than
   800×600, so the same preset reads slightly finer — acceptable as is, or
   multiply the px families by 1.1.
4. **A figure that looks "мелко" with oversized dots is a framing problem, not
   a style problem.** Decorations are pixel-fixed; only the geometry scales
   with the viewport. If the construction spans a small share of the canvas,
   fix the fit (`fitView` padding, target 70–85% span) before touching sizes.

### One dial for everything: `prominence`

`applyStyle(content={'prominence': k, ...})` multiplies **all** decoration
sizes (points, strokes, fonts, arcs, ticks) by `k` in one move, without
touching the geometry, crop or label layout — the right tool when a whole
figure needs to read "larger" or "finer" while keeping its internal ratios:

```python
scene.applyStyle(
    reference={'size': {'width': 800, 'height': 600}},
    content={'source': 'rendered_bounds', 'padding': 40, 'prominence': 1.25},
    export={'size': {'width': 800, 'height': 600}},
)
```

Companion option `content.decoration_scale_source` controls what the
decoration density is anchored to: `frame` (default — decorations track the
fitted crop), `reference` (fixed decoration/geometry proportion across
different crops), `output` (fixed *output-pixel* size regardless of zoom),
`ggb` (GeoGebra-applet proportions). See
[ai_style_generation_context.md](ai_style_generation_context.md) for the
full semantics.

### Density adjustments

- **Dense figure** (many labeled points, crossing helpers): step the whole
  label/point system down one notch (use `aux` values as `main`), enable the
  recommended `overlay.label_placement` preset (§8), and consider a larger
  reference canvas so the geometry gets more room.
- **Sparse demo figure** (3–5 elements for a slide): `prominence` 1.2–1.4
  reads better at a distance than bumping individual families.
- **Adjacent angle marks at one vertex**: separate arcs by 6–10 px steps of
  `arc_size_px` (plus `arc_shift_px` for multi-tick classes) — smaller steps
  visually merge, larger ones read as unrelated arcs.

---

## See also

- [docs/api.md](api.md) — the full `AnimaGeoScene` method reference
- [docs/import_policies.md](import_policies.md) — a practical `ImportPolicy` cookbook
- [docs/gotchas.md](gotchas.md) — manim/Python/architecture pitfalls
- [docs/architecture.md](architecture.md) — module and dependency overview
- `animageo/style/schema.py` — the exhaustive JSON-schema docstring
- `animageo/style/scaling.py` — all unit-conversion formulas in one file
