# Time by element ID (`native.sample_timeline`, `render(t)`, `steps_timeline`)

animageo 1.9.0a4 (plan L3 §5). The browser kernel of the web app repeats §1,
§2 and §4 in TypeScript (W4); the fixtures `animageo-timeline/v1`
(`parity/v1/timeline`) and the `timeline` of the steps fixtures
(`parity/v1/steps`) are the reference.

## 1. Timeline (contract)

A timeline is the keyframe JSON v2 of the classic library
(`animageo/keyframes.py`) whose keys are **element IDs** of the document:

```json
{"version": 2, "defaults": {"easing": "smooth"},
 "keyframes": [
   {"t": 0, "values": {"A": [0, 0], "P": {"tparam": 0.5}}, "hide": ["s"]},
   {"t": 2, "values": {"A": [2, -1], "P": {"tparam": 5.5, "direction": "ccw"}, "k": 3},
    "show": ["s"], "enter": {"s": {"effect": "create", "duration": 0.5, "at": 0.2}},
    "easing": "linear"}]}
```

- `values.<id>` by the free input of the element: `point.free` — `[x, y]`;
  `point.on_path` — `{"tparam": t, "direction": "short" | "long" | "cw" |
  "ccw"}` (`direction` defaults to `short`) in the parameter of the path
  (`kernel/paths.py`, `docs/native/ops/point.on_path.md`); `number.free` —
  a number `v`. A free `angle` input or anything else is a `ValueError`
  («not animatable»); a value for an element that is not free is a
  `ValueError` too. `@camera` passes through to the video.
- `show`, `hide`, `visible`, `enter`, `exit`, `styles`, `events`,
  `easing`, `defaults` — as in v2. `easing` names: `animageo/easing.py`
  (`EASING_FUNCTIONS`, the functions moved there from `keyframes.py` in
  1.9.0a4 with bitwise the same values).
- An ID that is not in the document is skipped everywhere (an element
  deleted after the keyframe was saved).
- Keyframes are sorted by `t`; times must be strictly increasing; at least
  one keyframe. A timeline of one keyframe (1.11.0rc7) is a still: the
  frame at any `t` is the state of that keyframe, the video holds it for
  `video.duration` seconds (§3).

## 2. `sample_timeline(doc, timeline, t) → {t, inputs, visible}` (contract)

No classic code, no evaluation except the vertex count of a polygon path.

1. `t` is clamped to `[t_0, t_last]`. The interval is the first `[t_k,
   t_{k+1}]` with `t_k ≤ t ≤ t_{k+1}` (at an inner keyframe time, the
   interval that ends there); `p = (t − t_k)/(t_{k+1} − t_k)`, `e =
   ease(p)` with the `easing` of keyframe `k+1`, else `defaults.easing`,
   else `smooth`. One keyframe: `k = 0`, `p = 0`.
2. **Values carry forward.** The value of `id` at keyframe 0 is its value
   there, else the input of the document (`FREE_INPUT_DEFAULTS` for an
   optional one). At keyframe `k + 1` it is unchanged unless the keyframe
   has a value for `id`: then a point and a number take that value, a path
   parameter on a non-wrapping path too, and a path parameter on a wrapping
   path (circle — period `P = 2π`; polygon — `P = n`, the vertex count of
   the polygon in the document now; sector — `P = 3`) becomes `s + d`
   (unwrapped), where `s` is the value at `k`, `v` the keyframe's
   `tparam`, `r = (v − s) mod P ∈ [0, P)` and

   | direction | `d` |
   |---|---|
   | `short` | `r` if `r ≤ P/2`, else `r − P` |
   | `long` | `0` if `r = 0`; `r − P` if `r ≤ P/2`; else `r` |
   | `ccw` | `r` |
   | `cw` | `r − P` if `r > 0`, else `0` |

   The direction is ignored on segment, ray, line, arc and polyline.
3. In the interval, an `id` with a value in keyframe `k+1` is
   `(1 − e)·a + e·b` (point coordinates one by one, numbers, path
   parameters on non-wrapping paths) or `a + e·(b − a)` (a path parameter
   on a wrapping path), `a`, `b` its values at `k` and `k+1`; any other
   animated `id` keeps its value at `k`.
4. **Visibility carries forward** — the formula of the web's
   `tests/fixtures/keyframe_visibility_parity.json` (a copy is
   `tests/native/snapshots/keyframe_visibility_parity.json`): for every
   element, the value of the last keyframe with `t_k ≤ t` that mentions it
   (inside one keyframe: `show`, then `hide`, then `visible`), else
   `appearance.<id>.visible` (default `true`). Entrance and exit effects do
   not change it: an element is visible from its keyframe on.
5. Result: `{"t": t (clamped), "inputs": {id: {"kind", "value"}},
   "visible": {id: bool}}` — `inputs` only for the animated elements, in the
   format of `evaluate(doc, inputs=…)`; `visible` for every element of the
   document.

`native.evaluate(doc, t=…, timeline=…)` is `evaluate(doc,
inputs=sample.inputs)` (explicit `inputs` go on top) plus `ev.t` and
`ev.visible`; `ev.to_dict()` then adds `t` and `visible` to
`animageo-evaluated/v1` (without a timeline the output is unchanged). `t`
without `timeline`, or the reverse, is a `ValueError`.

## 3. Bridge and rendering

`timeline_to_bridge(doc, timeline)` — the classic keyframe JSON of the scene
the bridge builds (`kernel/bridge.py`):

- IDs → `e_<hex>` (`classic_name`); `@camera`, `defaults`, `easing` and
  effect specs pass through; IDs not in the document and number elements
  (a classic `Var` has no visibility) are dropped from `visible`, `enter`,
  `exit`, `styles` and event `targets`.
- A path parameter is the classic `tparam` as it is (the bridge passes the
  classic `tparam` to the kernel), unwrapped along the timeline as in §2
  step 2, with `direction` `ccw` for `d > 0`, `cw` for `d < 0`, `short`
  for `d = 0`. Whatever the classic constraint of the point (a circle,
  arc and sector are classic circles, a polygon is `unknown` → linear), the
  classic interpolation then gives the values of §2 — on a polygon also for
  `|d| ≥ 2π` (an 8-gon, period 8, shifts of ±7–7.5 per interval: the classic
  constraint of a point on a polygon is that of its path, never `circle`, so
  the classic lerps the unwrapped `tparam`; 1.9.0a5 test); the test
  checks segment, ray, line, circle, polygon, arc, sector and polyline at
  and between keyframes.
- A number is clamped to the `min`/`max` literals of its operation at each
  keyframe (the kernel clamps, the classic `Var` does not); inside an
  interval the classic lerps the clamped ends, the kernel clamps the lerp —
  the same while both ends are in range.

`native.render(doc, …, t=…, timeline=…)` (static formats; 1.11.0,
`native.has("render.t.effects")`) is the frame of the video at `t`: the
document loaded as the video loads it (`loadDocument`, explicit `inputs`),
then `seek_keyframes(bridged, t)` — the classic playback without playing:
the sequence prepared as `play_keyframes` prepares it (style tracks, the
effects of `bind_visibility`, the label snapshots of every keyframe), every
interval before the one holding `t` left as its last frame leaves it
(values, styles and their finalizers, label offsets, the camera, the
elements its effects bring in and take out), then the frame of that
interval at its progress. Both paths draw a frame with one function,
`AnimaGeoScene._keyframe_frame`: values, geometry, styles, label offsets,
the mobjects, then the enter/exit effects, the camera and the emphasis
events over them. The interval of `t` is `[t_k, t_{k+1})`, as in the video
(its frame `k` shows `t_k + k/fps`); the last one is held to its end.

- Effects. A change of visibility at keyframe `k+1` plays inside
  `[t_k, t_{k+1}]`, from `t_k + at` for `duration` (`keyframes.md`): an
  element that enters there is drawn from `t_k + at` on, in its effect
  (`fade`, `create`, `grow`, `write`, `none`) until the window ends, in full
  after it — before the keyframe that makes it visible. An element its
  effect shows nothing of yet (an entrance not begun, an exit done) is left
  out of the frame (no mobject, no box).
- Equality marks (1.11.0rc5). A `mark.equal_segments` or
  `mark.equal_angles` has no drawing of its own: its ticks and arcs are
  drawn by its targets, and they belong to the mark in time — on the
  targets while the mark is in the frame (visible at `t`, defined, its
  entrance begun, its exit not done), and its effect is drawn on them
  (`fade` — their opacity, `create` — their stroke up to the progress,
  `grow` — about each target's ticks). Of the arcs of an angle the mark's are
  the outer ones (those beyond the angle's own `tick_count`); the angle's
  own arc stays. A mark hidden in the document puts its ticks from the
  frame that shows it. Before (1.11.0rc4) the frame and the video kept the
  ticks of the visibility of the document at every `t`; in 1.11.0rc3 the
  still read the visibility at `t`, its video drew the static ticks.
- Events (`indicate`, `flash`, `circumscribe`) are drawn in their window.
  1.11.0: the overlay of `flash` and `circumscribe` is rebuilt from its
  target every frame (it follows a moving target), overlays stack by the
  order of their events, and an overlay leaves the frame when its window
  closes (before, the video held it to the end of the interval).
- Labels: placed as the video places them, snapshots interpolated. Value
  labels are TeX in the vector still and the cairosvg PNG; the video-camera
  PNG below draws them with the cached digits of the video
  (`rendering.fast_value_labels`), so it is the video's frame to the pixel.
  1.11.0rc7: the cached digits stand where the TeX of the label puts its
  glyphs (`ui.ValueLabel`: the label with every digit `0` compiled once per
  pattern, the ink offset of each digit against `0` at the same pen
  position; prefix, sign, point and suffix at their places in the pattern),
  so the label of the video is the label of the still — of one width, the
  degree sign raised as TeX raises it. Measured
  (`test_native_frame_equals_video.py`): the video-camera PNG equals the
  cairosvg PNG of the SVG still to the pixel (PSNR ∞) around an angle value
  label, the frame the video writes is ≥ 48 dB around it; before, 17.6 dB.
- Explicit `inputs` are on top of the timeline in the still and in the video
  alike: the bridged timeline loses the values of those elements
  (`rendering._bridged_timeline`).
- The camera moves the frame of the manim camera: it shows in the
  video-camera PNG (and the video); the vector exports (SVG, PDF, EPS, TikZ)
  and the cairosvg PNG draw the export frame of the style. TikZ draws an
  element in an effect in full.

The report gains `t` and `visible` of `sample_timeline` (carried forward:
an element is `visible` from its keyframe on, as the web's
`keyframe_visibility_parity.json`) and `effects` — `{id: {phase, effect,
progress}}` of the effects of the interval that have begun
(`timeline_effects`, `progress` to 9 places as in `resolve_paint`; the
playback plays the same effects, `seek_keyframes`): an element entering
with `progress > 0` is drawn
though `visible` is still `false`. Its boxes are those of the elements in
the frame. `resolve_paint(t=…)` draws the same presence and gives the entry
`effect`.

`timeline_effects(doc, timeline, t)` (1.11.0, `native.has("timeline.effects")`,
manim-free) — `{id: {phase, effect, progress, present}}`: the effects of
the interval of the frame at `t` by the rule of
`KeyframeSequence.bind_visibility` (the spec of keyframe `k+1`, else
`defaults.enter`/`defaults.exit`, else `fade` 0.4 s; `at` clamped to the
interval, the duration cut at its end); `progress` — `(t − t_k − at) /
duration` in `[0, 1]` (a zero duration: `1` from `at` on); `present` —
`progress > 0` for an entrance, `< 1` for an exit. Numbers have no effects.
The web's `sampleTimeline(...).effects` follows the same rule.

1.9.0a5–1.10: `render(t)` drew the document with the inputs and the
carried-forward visibility of `sample_timeline` plus the styles and the
camera (`timeline_extras`), with no effect and no event: an element
entering before its keyframe was missing from the still for the rest of
the interval. `timeline_extras(doc, timeline)` remains — the styles and
`@camera` of the bridged timeline, which `resolve_paint` reads.

`render(fmt="png", video={fps?, quality})` (1.9.0a5, `native.has("render.frame")`):
the frame through the camera of the video — a scene loaded under the pixel
size of the video (the canvas times `quality`, even), one `update_frame`,
the camera image (RGBA PNG, background of the style). With `t` and
`timeline` it is the frame of the video at `t`. The report gains `video`
`{quality, width, height}`; its boxes stay in pixels of the canvas. Without
`video` a PNG is cairosvg of the SVG, as before (the static export of the
web); `video` with another static format is a `ValueError`.

`fmt ∈ {"mp4", "gif", "webm", "mov"}` — the video of the timeline: the
document loaded by `loadDocument`, the bridged timeline played by
`play_keyframes`, manim + ffmpeg (`render_config.configure_render`). Without
a timeline: `ValueError("timeline_required")`. `video={fps, quality,
duration}` (optional; `fps` 30, `quality` `low` | `medium` | `high` |
`production` — 0.5, 1, 1.5, 2 times the canvas in pixels, rounded to even).
The report of a video: `{format, documentId, kernel, fmt, video: {fps,
quality, width, height, duration}, t, visible}` (`t`, `visible` of the last
keyframe).

One keyframe (1.11.0rc7): the bridged timeline gets a second keyframe
`duration` seconds after the first that changes nothing, so the one
interval holds the state still (`play_keyframes` waits through it): the
video is `int(duration · fps)` frames of that state, `render(t)` at any
`t` is the same state (`t` clamped to the keyframe, the report `t` is its
time, `effects` empty). `video.duration` — seconds in `(0, 600]`, `1` by
default; it applies to a timeline of one keyframe only (with two keyframes
or more the length is the timeline's, a `duration` is a `ValueError`).

Measured (1.11.0, `test_native_frame_equals_video.py`): the frames the
video writes, taken from the renderer before the codec, against
`render(t, fmt="png", video=…)` at the time of each frame (the rule above)
— identical (PSNR ∞) on 77 of 85 frames of seven timelines: steps of a
construction, every enter and exit effect inside its window, an element
entering before its keyframe, events with a moving camera; ≥ 78 dB on the
others (labels placed at keyframes, value labels, explicit inputs). The
test guards ≥ 60 dB on every frame, inside the windows too. Before (1.10,
the same harness): 27–48 dB inside the windows of effects and 30 dB for the
rest of an interval whose element enters before its keyframe.

Earlier (1.9.0a5, `test_native_l3a4_render_manim.py`, 20 frames of
`tests/native/frames/*.json`): an MP4 frame `n` against `render(t=n/fps,
fmt="png", video=…)` — PSNR 45.7 dB – ∞ on all 20 frames; 17 frames have
≤ 0.1 % of pixels off by more than 16/255, three (`paths` 3 and 5, `number`
19) have 0.100–0.134 %, less than H.264 alone (libx264, crf 23, yuv420p as
manim encodes) on the same still: 0.17–0.37 %. What is left is the codec:
the steps frames, where nothing moves between H.264 references, are 62–67 dB
and 0 %. The test guards ≥ 40 dB and ≤ 0.1 % or not more than the codec
alone, and that the frame `n` is closest to `render` at `t = n/fps`. A
timeline with `styles` and `@camera` (five frames, red on green edges):
38.5–53 dB, within the codec alone. Before (1.9.0a4, cairosvg of the SVG):
29.6–46 dB, ≤ 1.23 %.

## 4. `steps_timeline(doc, *, lag=0.3, duration=0.5, pause=0.6, effects=None, start=0.0) → StepsTimeline` (contract)

`StepsTimeline(keyframes, steps, duration)`, `to_dict()`. Structural (no
evaluation).

1. Steps — `native.steps(doc)`; the elements of a step — its `elementIds`
   (visible, in operation then output order) without `number` elements;
   steps without one are skipped.
2. `n_i` elements, `d_i = (n_i − 1)·lag + duration`; `S_1 = start`,
   `S_{i+1} = S_i + d_i + pause` (floating operations in this order).
3. Keyframe 0: `{"t": start, "visible": {id: false}}` for every element of
   the steps (in step order). Keyframe `i`: `{"t": S_i + d_i, "visible":
   {id: true}, "enter": {id: {"effect", "duration": duration, "at"}}}` with
   `at = j·lag` (`j` — the index in the step) for the first step and
   `pause + j·lag` for the others. No pause keyframes.
4. Effects by type: `point` — `fade`; `segment`, `line`, `ray`, `vector`,
   `circle`, `arc`, `polyline`, `locus` — `create`; `polygon`, `sector`,
   `angle`, `mark` — `fade`; `text` — `write`; another type — `fade`.
   `effects` (`{type: effect}`, effects of `keyframes.ENTER_EFFECTS`)
   overrides by type.
5. Hidden elements never appear; a label appears with its element.
6. `keyframes = {"version": 2, "keyframes": [...]}`; `steps = [{"stepId",
   "start": S_i, "end": S_i + d_i, "elementIds", "text"}]` — `text` is the
   step's `text`, else its `title`, else `null` (the phrase of the step is
   `describe`); `duration` — `t` of the last keyframe (`start` without
   steps: one keyframe, no steps).

`ValueError`: `lag < 0`, `duration ≤ 0`, `pause < 0`, a non-finite
`start`, an unknown effect. Tested on every parity scene: each visible
element appears exactly once and not before its visible ancestors, hidden
ones never, two calls give byte-equal results. Budget: 300 operations ≤
10 ms (measured p95 ≈ 7 ms on a busy machine, of which `native.steps` ≈
5 ms); `sample_timeline` on the same document ≈ 0.6 ms.

## 5. Fixtures and command line

`animageo-timeline/v1`, one file per document: `{format, id, registry,
generatedBy, document, steps (steps_timeline with the defaults), cases:
[{name, timeline, samples: [t…], expect: {samples: [{t, inputs, visible}],
bridge}}]}`; numbers compare within `1e-9`, the rest exactly. 27 cases:
six easings, four directions on a circle and on a polygon, two on a
sector, five non-wrapping paths, a number, carried values, carried
visibility with unknown IDs, clamped time, `@camera`/`styles`/`events`, the
steps timeline of a document with a titled step. The steps fixtures
(`animageo-steps/v1`) carry `expect.timeline` = `steps_timeline(doc)`.

```text
python -m animageo.native fixtures timeline [-o <dir>] [--check]
python -m animageo.native steps <doc.json>
python -m animageo.native describe <doc.json> [--values] [--precision N]
python -m animageo.native timeline <doc.json> [--lag L --duration D --pause P --start S]
python -m animageo.native timeline <doc.json> --timeline <keyframes.json> (--t T | --bridge)
```

`<doc.json>` may be a parity scene or fixture (its `document`). `timeline`
prints `steps_timeline`, or `sample_timeline` at `--t`, or
`timeline_to_bridge` with `--bridge`; a timeline file may be the output of
the first form. `fixtures verify` also checks `animageo-timeline/v1` files.
`native.has`: `timeline`, `steps_timeline`, `render.t`, `render.video`,
`render.frame` (1.9.0a5).
