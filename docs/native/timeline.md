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
  one keyframe (a video needs two).

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
  classic interpolation then gives the values of §2 (`|d| < 2π`); the test
  checks segment, ray, line, circle, polygon, arc, sector and polyline at
  and between keyframes.
- A number keeps the value of the timeline: the classic `Var` is not
  clamped to `min`/`max` of `number.free` (the kernel is) — keep numbers
  in range.

`native.render(doc, …, t=…, timeline=…)` (static formats): the document
with the inputs of `sample_timeline` (explicit `inputs` on top) and its
`visible` written to `appearance.<id>.visible`, then the usual export — the
frame of the playback at `t` with no effect in progress. The report gains
`t` and `visible`; hidden elements have `visible: false` and no box.

`fmt ∈ {"mp4", "gif", "webm", "mov"}` — the video of the timeline: the
document loaded by `loadDocument`, the bridged timeline played by
`play_keyframes`, manim + ffmpeg (`render_config.configure_render`). Without
a timeline: `ValueError("timeline_required")`. `video={fps, quality}`
(optional; `fps` 30, `quality` `low` | `medium` | `high` | `production` —
0.5, 1, 1.5, 2 times the canvas in pixels, rounded to even). The report of
a video: `{format, documentId, kernel, fmt, video: {fps, quality, width,
height, duration}, t, visible}` (`t`, `visible` of the last keyframe).

Measured (1.9.0a4, `test_native_l3a4_render_manim.py`): an MP4 frame at
`n/fps` against `render(t=n/fps, fmt="png")` — PSNR ≈ 32 dB, ≈ 1.1 % of
pixels off by more than 16/255, at every `t`, moving or still: the
rasterisers differ (cairosvg of the SVG, the manim camera and h264), the
geometry does not. The gate of plan L3 (≥ 40 dB, ≤ 0.1 %) is for 1.9.0.

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
`native.has`: `timeline`, `steps_timeline`, `render.t`, `render.video`.
