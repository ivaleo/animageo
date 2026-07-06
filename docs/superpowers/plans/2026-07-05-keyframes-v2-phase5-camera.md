# Keyframes v2 Phase 5 — Camera & Static Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Add a `@camera` reserved pseudo-element to keyframes v2 (animate the viewport center + width — cinematic pan/zoom), and `apply_keyframes_at(seq, t)` to statically place the scene at any playhead time `t` (for server-side single-frame preview / SVG at a timestamp).

**Architecture:** `@camera` parsing + interpolation stay in `keyframes.py` (manim-free); playback applies it to `self.camera.frame` (AnimaGeoScene extends `MovingCameraScene`; `applyStyle` already frames content via `camera.frame`, so animating the frame pans/zooms). `apply_keyframes_at` reuses the existing interpolators to set state at time `t` without playing.

**Camera semantics (decision — documented):** `@camera` animates the manim `camera.frame` (center in math coords, `width` in math coords). This is a **cinematic** pan/zoom: geometry AND pixel-sized decorations (point radii, font sizes, stroke widths) scale together with zoom — it is NOT GeoGebra's pixel-invariant `ZoomIn` (where points keep their on-screen size). Pixel-invariant zoom would require a per-frame `ptUnit`/viewport recompute + full scene rebuild; that is a documented future refinement. Cinematic zoom is the natural manim behavior and is the right default for "zoom into this part of the figure."

**Tech Stack:** Python 3.10+, manim 0.20.1, numpy, pytest. `keyframes.py` stays manim-free.

**Spec:** `docs/superpowers/specs/2026-07-05-keyframes-v2-design.md` §5.5, §7 phase 5. Depends on phases 1-4 (on `dev`).

## Global Constraints

- `@camera` is v2-only and is a RESERVED name in `values` — it must be popped out before element-name validation (it is NOT a construction element). Using `@camera` under v1 → `ValueError`.
- `@camera` value: `{"center": [x, y]}` and/or `{"width": w}` (either or both; carry-forward). `width` must be > 0.
- Camera animation must not change persistent construction/style state.
- `apply_keyframes_at` must be side-effect-safe to call repeatedly (each call sets absolute state at `t`; it does not accumulate).
- `keyframes.py` stays manim-free. Branch `feat/keyframes-v2-phase5`. Conventional commits. **NO AI-attribution trailers.** Test with `python3.13 -m pytest`.

## File Structure

| File | Responsibility |
|---|---|
| Modify `animageo/keyframes.py` | `Keyframe.camera`; parse+pop `@camera` from `values`; `CameraInterpolator`; `KeyframeInterval.camera_interp`; wire into `_build_intervals` |
| Modify `animageo/animageo.py` | apply camera in `_apply_keyframe_state` + both `on_frame`s (via `_apply_camera_interp`); `apply_keyframes_at` |
| Test `tests/test_keyframe_camera.py` (new) | `@camera` parse/validate, CameraInterpolator, scene wiring, apply_keyframes_at |
| Modify `CLAUDE.md`, `AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document (final task) |

---

### Task 1: `@camera` parsing + interpolation

**Files:** Modify `animageo/keyframes.py`; Test `tests/test_keyframe_camera.py` (new).

**Interfaces:**
- `Keyframe.camera` (slot) — dict `{center?: [x,y], width?: float}` (normalized), default `{}`.
- `CAMERA_KEY = '@camera'` module constant.
- `from_json`: for each keyframe, pop `@camera` out of `values` BEFORE element validation; require v2; validate `center` is `[x,y]` numbers and/or `width` is a positive number; store on `Keyframe.camera`.
- `CameraInterpolator(start, end, easing)` with `.at(t) -> {center: [x,y], width: w}` — center 2D lerp, width scalar lerp; both endpoints are `{center, width}` dicts (fully resolved by the interval builder).
- `KeyframeInterval.camera_interp: Optional[CameraInterpolator]` (default `None`).
- `_build_intervals` carries-forward camera state (like values): the first keyframe's `@camera` seeds it; each interval whose end-keyframe changes camera gets a `CameraInterpolator`. Missing fields carry forward from the running camera state. The initial running camera (before any `@camera`) is `None` → the scene supplies it at playback (see Task 2 wiring); the interval builder marks intervals with camera changes and stores the raw start/end dicts, resolving `None` start lazily is handled at playback. **Simplify:** store on the interval the `camera_start`/`camera_end` dicts (may have partial fields); the scene fills missing/initial fields from the live `camera.frame` at playback.

To keep `keyframes.py` manim-free and simple, implement thus: `_build_intervals` tracks `running_camera` (a dict, starts `{}`); for interval i, if `keyframes[i+1].camera` is non-empty, merge it into `running_camera` to get `end`, set `interval.camera_interp = CameraInterpolator(start=dict(prev_running), end=dict(running_camera), easing=...)` where `prev_running` is the running camera BEFORE this keyframe's merge. Fields absent in both are left absent; the scene treats absent center/width as "keep current frame value".

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyframe_camera.py`:

```python
"""Keyframes v2 phase 5: @camera pseudo-element."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, CameraInterpolator, EASING_FUNCTIONS, CAMERA_KEY


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestCameraParsing:
    def test_camera_popped_from_values_not_validated_as_element(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'center': [0, 0], 'width': 14}}},
            {'t': 1, 'values': {'@camera': {'center': [2, 1], 'width': 8}}},
        ]), _construction())
        assert seq.keyframes[0].camera == {'center': [0.0, 0.0], 'width': 14.0}
        assert '@camera' not in seq.keyframes[0].values

    def test_camera_center_only(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'center': [0, 0]}}},
            {'t': 1, 'values': {'@camera': {'center': [3, 3]}}},
        ]), _construction())
        assert seq.keyframes[1].camera == {'center': [3.0, 3.0]}

    def test_camera_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'values': {'@camera': {'width': 10}}}, {'t': 1},
            ]}, _construction())

    def test_bad_width_rejected(self):
        with pytest.raises(ValueError, match='width'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'@camera': {'width': -3}}}, {'t': 1},
            ]), _construction())

    def test_bad_center_rejected(self):
        with pytest.raises(ValueError, match='center'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'@camera': {'center': [1, 2, 3]}}}, {'t': 1},
            ]), _construction())

    def test_normal_values_still_work_alongside_camera(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0], '@camera': {'width': 14}}},
            {'t': 1, 'values': {'A': [1, 1], '@camera': {'width': 7}}},
        ]), _construction())
        assert 'A' in seq.keyframes[0].values
        assert seq.keyframes[0].camera == {'width': 14.0}


class TestCameraInterpolator:
    def test_center_and_width_lerp(self):
        ci = CameraInterpolator(
            start={'center': [0.0, 0.0], 'width': 14.0},
            end={'center': [4.0, 2.0], 'width': 6.0},
            easing=EASING_FUNCTIONS['linear'])
        mid = ci.at(0.5)
        assert mid['center'] == [2.0, 1.0]
        assert mid['width'] == pytest.approx(10.0)

    def test_absent_field_stays_absent(self):
        ci = CameraInterpolator(
            start={'width': 14.0}, end={'width': 6.0},
            easing=EASING_FUNCTIONS['linear'])
        mid = ci.at(0.5)
        assert 'center' not in mid
        assert mid['width'] == pytest.approx(10.0)


class TestCameraIntervalWiring:
    def test_interval_gets_camera_interp(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'width': 14}}},
            {'t': 1, 'values': {'@camera': {'width': 6}}},
        ]), _construction())
        assert seq.intervals[0].camera_interp is not None
        assert seq.intervals[0].camera_interp.at(1.0)['width'] == pytest.approx(6.0)

    def test_no_camera_no_interp(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},
        ]), _construction())
        assert seq.intervals[0].camera_interp is None
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** in `animageo/keyframes.py`:

3a. `CAMERA_KEY = '@camera'` constant. `Keyframe.__slots__` += `'camera'`; `__init__` param `camera=None` → `self.camera = camera or {}`.

3b. Camera normalizer (module-level):
```python
def _normalize_camera(spec, kf_index):
    if not isinstance(spec, dict):
        raise ValueError(f"Keyframe {kf_index}: '@camera' must be an object, got {spec!r}")
    out = {}
    if 'center' in spec:
        c = spec['center']
        if (not isinstance(c, (list, tuple)) or len(c) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in c)):
            raise ValueError(f"Keyframe {kf_index}: '@camera' center must be [x, y] numbers, got {c!r}")
        out['center'] = [float(c[0]), float(c[1])]
    if 'width' in spec:
        w = spec['width']
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0:
            raise ValueError(f"Keyframe {kf_index}: '@camera' width must be a positive number, got {w!r}")
        out['width'] = float(w)
    return out
```

3c. In `from_json` per-keyframe loop, BEFORE the value-name validation loop, pop `@camera`:
```python
            values = dict(kf_data.get('values', {}))   # copy so we can pop
            camera = {}
            if CAMERA_KEY in values:
                if version < 2:
                    raise ValueError(f"Keyframe {i}: '@camera' requires '\"version\": 2'")
                camera = _normalize_camera(values.pop(CAMERA_KEY), i)
```
(Use this `values` — with `@camera` removed — for the existing element-name validation and for `Keyframe(values=values, ...)`. Pass `camera=camera`.)

3d. `CameraInterpolator`:
```python
class CameraInterpolator:
    __slots__ = ('start', 'end', 'easing')

    def __init__(self, start, end, easing=None):
        self.start = start
        self.end = end
        self.easing = easing or _ease_smooth

    def at(self, t):
        et = self.easing(t)
        out = {}
        if 'center' in self.start and 'center' in self.end:
            s, e = self.start['center'], self.end['center']
            out['center'] = [(1 - et) * s[0] + et * e[0], (1 - et) * s[1] + et * e[1]]
        elif 'center' in self.end:
            out['center'] = list(self.end['center'])
        if 'width' in self.start and 'width' in self.end:
            out['width'] = (1 - et) * self.start['width'] + et * self.end['width']
        elif 'width' in self.end:
            out['width'] = self.end['width']
        return out
```

3e. `KeyframeInterval.__slots__` += `'camera_interp'`; init `self.camera_interp = None`.

3f. In `_build_intervals`, track `running_camera = dict(keyframes[0].camera)`; for each interval, if `keyframes[i+1].camera`: `start = dict(running_camera); running_camera.update(keyframes[i+1].camera); interval.camera_interp = CameraInterpolator(start, dict(running_camera), easing_fn)`. (When `start` is missing a field the end has, `CameraInterpolator.at` falls back to the end value — a reasonable "snap to first specified" for a field that appears mid-sequence.)

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframes.py tests/test_keyframe_visibility.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): @camera pseudo-element (cinematic pan/zoom keyframes)`.

---

### Task 2: Camera playback + `apply_keyframes_at`

**Files:** Modify `animageo/animageo.py`; Test append to `tests/test_keyframe_camera.py`.

**Interfaces:**
- `AnimaGeoScene._apply_camera(cam) -> None`: given a `{center?, width?}` dict, set `self.camera.frame` — `move_to([cx, cy, 0])` if center present, `set(width=w)` if width present. No-op for empty dict.
- `_apply_keyframe_state` applies `kf.camera` (via `_apply_camera`).
- Both `_play_keyframe_interval` and `_play_keyframe_interval_v2` `on_frame`: if `interval.camera_interp`, call `self._apply_camera(interval.camera_interp.at(t))` (after `updateGeoElements`; camera transform is independent of mobject rebuild).
- `apply_keyframes_at(self, keyframes_data, t)`: parse to a `KeyframeSequence` (if dict), find the interval `[start_t, end_t]` containing `t` (clamp to `[first.t, last.t]`), compute local progress `p = (t - start_t)/duration`, apply keyframe-`start` state then each interpolator at `p` (values, styles via `_apply_style_interps` after `bind_style_tracks`, camera), rebuild + `updateGeoElements`. This statically places the scene at `t` for a single-frame preview (e.g. then call `exportSVG`). Returns nothing.

- [ ] **Step 1: Write failing tests** (append)

```python
from animageo.animageo import AnimaGeoScene


def _scene():
    s = AnimaGeoScene()
    s.geo = _construction()
    s.applyStyle()
    return s


class TestCameraPlayback:
    def test_apply_camera_sets_frame(self):
        s = _scene()
        s._apply_camera({'center': [2.0, 1.0], 'width': 6.0})
        c = s.camera.frame.get_center()
        assert abs(c[0] - 2.0) < 1e-6 and abs(c[1] - 1.0) < 1e-6
        assert abs(s.camera.frame.width - 6.0) < 1e-6

    def test_apply_camera_empty_noop(self):
        s = _scene()
        w0 = s.camera.frame.width
        s._apply_camera({})
        assert s.camera.frame.width == w0

    def test_apply_keyframe_state_applies_camera(self):
        s = _scene()
        s.updateGeoElements = lambda updates=None: None
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'width': 9}}},
            {'t': 1, 'values': {'@camera': {'width': 5}}},
        ]), s.geo)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert abs(s.camera.frame.width - 9.0) < 1e-6


class TestApplyKeyframesAt:
    def test_places_value_at_midpoint(self):
        import numpy as np
        s = _scene()
        s.apply_keyframes_at(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 2, 'values': {'A': [4, 0]}},
        ]), t=1.0)
        assert np.allclose(s.geo.element('A').data.coords, [2.0, 0.0], atol=1e-6)

    def test_camera_at_time(self):
        s = _scene()
        s.apply_keyframes_at(_v2([
            {'t': 0, 'values': {'@camera': {'width': 10}}},
            {'t': 2, 'values': {'@camera': {'width': 6}}},
        ]), t=1.0)
        assert abs(s.camera.frame.width - 8.0) < 1e-6

    def test_clamps_before_first_and_after_last(self):
        import numpy as np
        s = _scene()
        data = _v2([{'t': 1, 'values': {'A': [0, 0]}},
                    {'t': 3, 'values': {'A': [4, 0]}}])
        s.apply_keyframes_at(data, t=0.0)     # before first -> first state
        assert np.allclose(s.geo.element('A').data.coords, [0.0, 0.0], atol=1e-6)
        s.apply_keyframes_at(data, t=99.0)    # after last -> last state
        assert np.allclose(s.geo.element('A').data.coords, [4.0, 0.0], atol=1e-6)
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement**
  - `_apply_camera`:
    ```python
    def _apply_camera(self, cam):
        if not cam:
            return
        if 'center' in cam:
            cx, cy = cam['center']
            self.camera.frame.move_to([float(cx), float(cy), 0.0])
        if 'width' in cam:
            self.camera.frame.set(width=float(cam['width']))
    ```
  - In `_apply_keyframe_state`, after applying values/styles/visibility: `self._apply_camera(kf.camera)`.
  - In BOTH `on_frame`s, after `updateGeoElements(updates)` (and after effects in the v2 one): `if interval.camera_interp: scene_ref._apply_camera(interval.camera_interp.at(t))`.
  - `apply_keyframes_at`:
    ```python
    def apply_keyframes_at(self, keyframes_data, t):
        """Statically place the scene at playhead time ``t`` (no animation) —
        for a single-frame preview (e.g. then exportSVG). Idempotent."""
        from .keyframes import KeyframeSequence, _parse_value
        seq = (KeyframeSequence.from_json(keyframes_data, self.geo)
               if isinstance(keyframes_data, dict) else keyframes_data)
        if seq.has_style_tracks():
            cs = self.style.rendering.get('color_interpolation', 'oklab')
            seq.bind_style_tracks(get_element=self.geo.element,
                                  resolve=lambda e, k: _resolve_style(self, e, k, default=None),
                                  color_space=cs)
        seq.bind_visibility(get_element=self.geo.element)
        kfs = seq.keyframes
        t = max(kfs[0].t, min(float(t), kfs[-1].t))
        # find interval containing t
        idx = 0
        for i, iv in enumerate(seq.intervals):
            if iv.start_t <= t <= iv.end_t:
                idx = i
                break
        interval = seq.intervals[idx]
        self._apply_keyframe_state(kfs[idx], seq.element_info, update_scene=False)
        p = 0.0 if interval.duration <= 0 else (t - interval.start_t) / interval.duration
        touched = set()
        for interp in interval.interpolators:
            self._apply_interp_value(interp.name, interp.kind, interp.at(p))
            touched.add(interp.name)
        # apply visibility state at end-keyframe if p>=1 else start already set
        updates = self.geo.rebuild()
        for name in touched:
            updates[name] = updates.get(name, True)
        for name in self._apply_style_interps(interval, p):
            updates[name] = updates.get(name, True)
        if interval.camera_interp:
            self._apply_camera(interval.camera_interp.at(p))
        self.updateGeoElements(updates)
    ```
    (Note: `_apply_keyframe_state(kfs[idx])` sets the start-of-interval values/styles/visibility/camera; then interpolators advance to progress `p`. This yields the state at time `t`. Visibility mid-interval effects are not rendered statically — the element is shown per its start-keyframe visibility, which is the correct static snapshot.)

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframe_visibility.py tests/test_keyframe_styles.py tests/test_keyframe_initial_state.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): camera playback + apply_keyframes_at static preview`.

---

### Task 3: End-to-end smoke render + docs + full suite

- [ ] **Step 1: Smoke render (real manim).** A DSL scene (triangle + circle); v2 keyframes animating `@camera` width from wide (e.g. 14) to narrow (e.g. 6) over 1.2 s (a zoom-in), center panning. Render low-quality MP4; assert with cv2 that the construction's on-screen extent GROWS (the same geometry occupies more pixels as the frame zooms in) — e.g. the colored-region bounding box widens from first to last frame, OR the colored-pixel count increases. Report evidence. Also test `apply_keyframes_at` by exporting an SVG at t=midpoint and confirming it's a valid non-empty file.
- [ ] **Step 2: Fix any bug (TDD).**
- [ ] **Step 3: Docs.** `AI_USAGE_PROMPT.md` §8.3: `@camera` example (`values: {"@camera": {"center": [x,y], "width": w}}`) with a one-line note it's a cinematic zoom (geometry+pixel sizes scale together, not GGB pixel-invariant ZoomIn), and `apply_keyframes_at(kfs, t)` for a static frame at a playhead. `CHANGELOG.md` `[Unreleased]`: bullets for `@camera` (cinematic pan/zoom) and `apply_keyframes_at`. CLAUDE.md: controller handles — note the intended block in the report.
- [ ] **Step 4: Full suite** `python3.13 -m pytest tests/ -q` → 0 failures.
- [ ] **Step 5: Commit** `docs+test: keyframes v2 @camera + apply_keyframes_at`.

## Out of scope / deferred (documented opt-ins)
- **Pixel-invariant GGB-`ZoomIn` camera** (per-frame ptUnit recompute + rebuild) — future refinement; cinematic zoom ships now.
- **Per-key easing** (a style track value carrying its own `easing`) — deferred polish.
- **Text crossfade** (cross-fade old→new on a `label_text` swap instead of instant) — deferred polish.
- `events` emphasis effects — phase 6 (final).
