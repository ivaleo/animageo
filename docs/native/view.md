# Axes and grid of the view (registry 1.6)

`viewDefaults.axes` and `viewDefaults.grid` of an `animageo-construction/v1`
document ask `native.render` to draw coordinate axes and a grid under the
elements (`native.has("view_axes_grid")`, 1.11.0rc6). Evaluation does
not read them. Code: `animageo/native/view.py`
(manim-free), drawing — `AnimaGeoScene._addNativeViewBackground` (SVG, PNG,
PDF, EPS, video) and the TikZ exporter.

## Document

```text
"viewDefaults": {
  "bounds": [xmin, ymin, xmax, ymax],
  "axes": {"show"?: bool, "numbers"?: bool, "step"?: number > 0 | null,
           "labels"?: {"x"?: string ≤ 32, "y"?: string ≤ 32}},
  "grid": {"kind"?: "none" | "major" | "major_minor", "step"?: number > 0 | null}
}
```

| Key | Default | Meaning |
|---|---|---|
| `axes` | absent — no axes | the object asks for the axes |
| `axes.show` | `true` | `false` keeps the settings and hides the axes |
| `axes.numbers` | `true` | numbers at the ticks |
| `axes.step` | `null` — automatic | the distance of the ticks (both axes) |
| `axes.labels.x`, `.y` | `"x"`, `"y"` | names at the ends; `""` — none |
| `grid` | absent — no grid | |
| `grid.kind` | `major` | `none`, `major` (lines at the step), `major_minor` (and 5 minor cells in each) |
| `grid.step` | the step of the axes | |

Unknown keys are schema issues. A document without `axes` and `grid` (or
with `show: false` and `kind: "none"`) draws nothing extra: its output is
byte for byte that of 1.5.

## Layout (`view_layout`)

- Automatic step: `nice(max(w, h) / 10)`, `w, h` the sizes of
  `viewDefaults.bounds` (`defaultBounds` without them); `nice(v)` is the
  smallest of `{1, 2, 5}·10^k` not less than `v`. Bounds 20×20 → 2.
- The rectangle is the export canvas. Lines, ticks and numbers lie at `k·step`
  (`k` an integer) inside it; a direction with more than 400 lines takes
  every `m`-th (`m` the smallest integer that fits).
- The x axis is drawn when `y = 0` is inside the rectangle, the y axis when
  `x = 0` is; a grid line on a drawn axis is left out, as are the tick and
  the number at `0`. A number closer than `axes_font_size_px` to an end of
  its axis is left out (the frame would cut it).
- Numbers: `%.10g` of the value with the minus sign `−` (U+2212); TikZ
  writes them in math mode. The x numbers lie under the axis, the y numbers
  left of it; the name `x` above the right end, `y` right of the top end.

## Style (`rendering` section; `style_keys()["view"]`)

| Key | Built-in | Unit |
|---|---|---|
| `axes_color` | `presets.color.aux` (`#808080`) | colour |
| `axes_width_px` | `presets.line_width.aux` (0.75) | px |
| `axes_opacity` | 1 | opacity |
| `axes_font_size_px` | 10 | px |
| `axes_tick_length_px` | 4 | px (the whole tick, across the axis) |
| `grid_color` | `presets.color.light` (`#cccccc`) | colour |
| `grid_width_px` | 0.5 | px |
| `grid_opacity` | 1 | opacity |
| `grid_minor_width_px` | 0.25 | px |
| `grid_minor_opacity` | 0.6 | opacity |

Layers: minor grid `−21`, grid `−20`, axes and ticks `−10`, numbers and names
`−9` — under every element.
