# Keyframe animations

`play_keyframes()` animates a construction from a timeline JSON/dict. Use it
when you need repeatable "state at time T" animation that can be authored by a
UI, saved as JSON, previewed at a single playhead time, and rendered to video.

## Minimal format

```python
scene.loadGGB("scene.ggb", style="style.json", export={"size": {"width": 800, "height": 600}})

scene.play_keyframes({
    "version": 2,
    "keyframes": [
        {"t": 0, "values": {"A": [0, 0], "x": 35}},
        {"t": 2, "values": {"A": [4, 2], "x": 110}, "easing": "smooth"},
        {"t": 4, "values": {"A": [0, 0], "x": 35}},
    ],
})
```

Keyframe times are seconds and must be strictly increasing. The first keyframe
is applied before playback, so the first rendered frame matches the timeline,
not necessarily the saved GeoGebra editor state.

`"version": 2` opts into the current format. Omitted version means legacy v1:
plain value animation still works byte-identically, but v1 is deprecated and
does not support style tracks, visibility effects, camera tracks, or events.

## What can be animated

Call `scene.get_independent_elements()` before authoring a timeline. It returns
the free inputs that can be driven by `values`.

For GeoGebra-loaded scenes:

- free points: `[x, y]`
- points constrained to a path: `{"tparam": ...}`; circle/ellipse points also
  accept `"direction": "short" | "cw" | "ccw"`
- points constrained to a path may also be provided as `[x, y]`; AnimaGeo
  projects coordinates back to the path parameter
- numbers, angles: floats
- booleans: `true`/`false` in JSON, `True`/`False` in Python

For DSL-built scenes, command-created points are not independent by name. Route
them through variables:

```python
cx = scene.addVar("cx", 2.0)
cy = scene.addVar("cy", 4.0)
scene.putCode("C = Point(cx, cy)")

scene.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "values": {"cx": 2.0, "cy": 4.0}},
    {"t": 2, "values": {"cx": 4.0, "cy": 3.0}},
]})
```

## Easing

Per-keyframe `"easing"` controls the interval leading into that keyframe. A
top-level default can be set with:

```python
{"version": 2, "defaults": {"easing": "linear"}, "keyframes": [...]}
```

Supported names:

`linear`, `smooth`, `in`, `out`, `in_out`, `smootherstep`,
`ease_in_sine`, `ease_out_sine`, `ease_in_out_sine`, `ease_in_cubic`,
`ease_out_cubic`, `ease_in_out_cubic`, `rush_into`, `rush_from`,
`ease_out_back`, `ease_out_elastic`, `ease_out_bounce`.

The same names are used by the web preview and Python renderer.

## Style tracks

In v2, each keyframe may include `styles`. Styles can target any element, not
only independents.

```python
scene.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "styles": {"c1": {"fill_opacity": 0.0, "stroke": "#2581b5"}}},
    {"t": 2, "styles": {"c1": {"fill_opacity": 0.6, "stroke": "#d05456"}}},
    {"t": 3, "styles": {"c1": {"stroke": None}}},
]})
```

Use JSON `null` or Python `None` to revert a style key to its pre-animation
value. Colors blend perceptually when both sides are hex colors; non-hex color
values snap. Discrete keys such as `label_visible`, `label_anchor`,
`point_shape`, `tick_count`, `label_text`, and `z_index` switch halfway through
the interval.

Animatable style keys:

- numbers (interpolated): `stroke_opacity`, `fill_opacity`, `stroke_width_px`,
  `stroke_dash_period_px`, `size_px`, `font_size_px`, `arc_size_px`,
  `arc_shift_px`, `right_angle_size_px`, `tick_length_px`, `tick_width_px`,
  `tick_shift_px`, `arrow_length_px`, `arrow_width_px`,
  `label_radial_offset_px`
- colors (interpolated): `stroke`, `fill`, `label_color`
- `label_offset_px`: `[x, y]`, interpolated per component
- `stroke_dash_ratio`: interpolated between numbers; switches when one side is
  `None` (solid)
- `label_text`: swaps halfway through the interval, never blended
- switched halfway: `point_shape`, `stroke_linecap`, `tick_count`,
  `tick_style`, `angle_range`, `right_angle_marker`, `label_anchor`,
  `label_visible`, `label_mode`, `z_index`, `z_index_fill`

Any other key raises an error.

### Labels during keyframes

Label layout snapshots run only when both `overlay.label_placement.enabled`
and `overlay.label_placement.keyframe_snapshots` are `true`. The pre-pass
applies each keyframe's styles before measuring labels, so animated font sizes,
arc sizes, text, and visibility affect label layout.

With snapshots on, they own every label position: a `label_offset_px` style
track is ignored, so it does not fight the snapshot interpolation. A label that
appears during an interval (its element or the label itself hidden at the
start) is already at its auto-placed position. With placement off, labels keep
their imported or hand-set offsets and snapshots do not run.
`apply_keyframes_at()` places labels from the same snapshots (it computes only
the two keyframes around the requested time).

## Visibility and effects

`visible` is an absolute per-keyframe visibility map. `show` and `hide` are
accepted as v2 sugar and folded into `visible`.

```python
scene.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "visible": {"seg": False}},
    {"t": 1.5, "visible": {"seg": True},
     "enter": {"seg": {"effect": "create", "duration": 0.8}}},
    {"t": 3, "visible": {"seg": False}, "exit": {"seg": "fade"}},
]})
```

Entrance effects: `fade`, `none`, `create`, `grow`, `write`. Exit effects:
`fade`, `none`, `uncreate`, `shrink`. Effects run inside the keyframe interval
at the requested duration; v2 does not add the legacy v1 0.4 second show/hide
delay. `grow` and `shrink` scale the element's geometry about its own centre;
the label stays in place and fades instead of scaling.

## Construction reveal

For a staged "construction protocol" animation:

```python
scene.reveal_construction(lag=0.3, duration=0.5)
```

The scene walks elements in dependency order, chooses sensible entrance effects
by type, and plays generated v2 keyframes. Pass `play=False` to inspect or
splice the generated timeline instead of playing it immediately.

## Camera keyframes

`"@camera"` is a reserved v2 pseudo-element inside `values`:

```python
scene.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "values": {"@camera": {"center": [0, 0], "width": 14}}},
    {"t": 2, "values": {"@camera": {"center": [1, 1], "width": 6}}},
]})
```

This animates the Manim camera frame: geometry and pixel-sized decorations scale
together with the zoom. It is a cinematic pan/zoom, not GeoGebra's
pixel-invariant `ZoomIn`.

## Emphasis events

Per-keyframe `events` play one-shot, self-restoring accents during the interval
leading into that keyframe:

```python
scene.play_keyframes({"version": 2, "keyframes": [
    {"t": 0},
    {"t": 2, "events": [
        {"effect": "indicate", "targets": ["B"], "at": 0.4, "duration": 0.6},
        {"effect": "circumscribe", "targets": ["poly"], "at": 0.4, "duration": 0.6},
    ]},
]})
```

Effects: `indicate`, `flash`, `circumscribe`. `targets` is a list of element
names. `at` and `duration` are seconds from the start of the current interval.

## Static preview

Use `apply_keyframes_at()` to place a scene at one timeline time without
playing animation:

```python
scene.apply_keyframes_at(keyframes_data, t=1.25)
scene.exportSVG("frame_at_1_25.svg")
```

The call is idempotent and clamps outside the timeline range. It is useful for
server-side thumbnailing or UI playhead previews.
