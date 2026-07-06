# Keyframes v2 Phase 6 — Emphasis Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Add one-shot, self-restoring **emphasis events** to keyframes v2 — `indicate` (scale+colour pulse on a target), `flash` (radial flash at a point), `circumscribe` (temporary box/circle around a target) — declared per keyframe and played inside the interval, leaving the scene byte-identical once they complete.

**Architecture:** Event parsing + `EventSpec` compilation stay in `keyframes.py` (manim-free). Event adapters live in `animageo.py` and run inside the existing sentinel-updater `on_frame` loops (both `_play_keyframe_interval` and `_play_keyframe_interval_v2`), applied AFTER visibility effects. Two adapter families: **transform** (`indicate` — modifies the freshly-`become`d target mobject; self-restores by applying nothing outside its window) and **additive** (`flash`/`circumscribe` — add a temporary decoration mobject at the window start, animate it, remove it at the window end).

## Interaction analysis (required pre-implementation review — spec §7 phase 6)

Events are NOT interpolated state; they are one-shot and self-restoring. The binding invariant: **a frame at or after an event's completion is byte-identical to the same animation without the event.** How each interaction is handled:

1. **Events × become rebuild:** transform events re-apply over the fresh mobject each frame and apply *nothing* outside their `[at, at+duration]` window, so post-window frames are unchanged. Additive events add a temp mobject only within the window and remove it at the end. **Adapters never write `elem.style` or construction state** (same rule as enter/exit adapters) — so no state leaks.
2. **Events × enter/exit effects:** applied AFTER visibility effects in `on_frame`, so an event emphasises the element as it currently renders. Composition is multiplicative on the mobject; acceptable.
3. **Events × label tracker / label placement:** events transform the element's mobject (which may include its label) but never touch `elem.style['label_offset_px']`, so the label solver is unaffected.
4. **Additive-event lifecycle:** temp mobjects are tracked per interval and force-removed at interval end (belt-and-suspenders against a missed window edge), guaranteeing no leak. The byte-identical smoke test (frame-after-event vs no-event) is the enforcement.
5. **Non-monotonic easing:** events use their own `at`/`duration` window in absolute interval seconds (`t_abs = t*duration`), independent of the interval's value easing, so a non-monotonic value easing cannot double-fire an event.

**Deferred:** `passing_flash` (a highlight travelling along a parametrised stroke) — needs per-type path parametrisation; documented as a future addition.

## Global Constraints

- Events are v2-only. Using `events` under v1 → `ValueError`.
- An event adapter must NEVER mutate `elem.style` or construction state — only mobjects (transform the target, or add/remove a temp decoration).
- After an event completes, the scene must be byte-identical to the same animation without the event (enforced by a frame-comparison smoke test).
- Unknown event effect → `ValueError`. `passing_flash` → `ValueError` mentioning it's not available yet.
- `keyframes.py` stays manim-free. Branch `feat/keyframes-v2-phase6`. Conventional commits. **NO AI-attribution trailers.** Test with `python3.13 -m pytest`.

## File Structure

| File | Responsibility |
|---|---|
| Modify `animageo/keyframes.py` | `EVENT_EFFECTS`; `Keyframe.events`; parse+validate `events`; `EventSpec`; `KeyframeInterval.events`; compile in `_build_intervals` |
| Modify `animageo/animageo.py` | `_event_envelope`; `_apply_events(interval, t_abs, active)` dispatcher; `_event_indicate` (transform); `_event_additive` (flash/circumscribe add/remove); hooks in both `on_frame`s + interval-end cleanup |
| Test `tests/test_keyframe_events.py` (new) | parse/validate, EventSpec compile, envelope math, adapter identity at envelope 0, scene wiring, no-elem.style-write |
| Modify `CLAUDE.md`, `AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document (final task) |

---

### Task 1: Parse `events` + compile `EventSpec`

**Files:** Modify `animageo/keyframes.py`; Test `tests/test_keyframe_events.py` (new).

**Interfaces:**
- `EVENT_EFFECTS = ('indicate', 'flash', 'circumscribe')` module constant.
- `Keyframe.events` (slot) — list of normalized event dicts `{effect, targets, at, duration, color, scale}`.
- `EventSpec` dataclass: `effect: str`, `targets: list[str]`, `start: float`, `duration: float`, `color: str|None`, `scale: float`.
- `from_json`: parse per-keyframe `"events"` (list); require v2; validate each event's `effect` (reject unknown; `passing_flash` → "not available yet"), `targets` (non-empty list of existing element names), `at`≥0, `duration`>0; `color` normalized via `normalize_hex` if present; `scale` float default 1.2. Store on `Keyframe.events`.
- `KeyframeInterval.events: list[EventSpec]` (default `[]`). `_build_intervals`: `keyframes[i+1].events` compile into `interval.events` with `start`/`duration` clamped to the interval (`start = min(at, dur)`, `duration = min(duration, interval.duration - start)`; skip if interval.duration ≤ 0). `has_events()` on the sequence.

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyframe_events.py`:

```python
"""Keyframes v2 phase 6: emphasis events (indicate/flash/circumscribe)."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, EventSpec, EVENT_EFFECTS


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestEventParsing:
    def test_event_parsed_and_normalized(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 2, 'events': [{'effect': 'indicate', 'targets': ['B'],
                                 'at': 0.5, 'duration': 0.6, 'color': '#FF0000'}]},
        ]), _construction())
        (e,) = seq.keyframes[1].events
        assert e['effect'] == 'indicate' and e['targets'] == ['B']
        assert e['at'] == 0.5 and e['duration'] == 0.6 and e['color'] == '#ff0000'

    def test_events_require_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': ['B']}]},
            ]}, _construction())

    def test_unknown_effect_rejected(self):
        with pytest.raises(ValueError, match='event'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'sparkle', 'targets': ['B']}]},
            ]), _construction())

    def test_passing_flash_rejected_as_unavailable(self):
        with pytest.raises(ValueError, match='not available'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'passing_flash', 'targets': ['B']}]},
            ]), _construction())

    def test_unknown_target_rejected(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': ['GHOST']}]},
            ]), _construction())

    def test_empty_targets_rejected(self):
        with pytest.raises(ValueError, match='target'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': []}]},
            ]), _construction())

    def test_effect_set(self):
        assert EVENT_EFFECTS == ('indicate', 'flash', 'circumscribe')


class TestEventCompile:
    def test_interval_gets_eventspec(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 2, 'events': [{'effect': 'indicate', 'targets': ['A', 'B'],
                                 'at': 0.5, 'duration': 1.0}]},
        ]), _construction())
        (e,) = seq.intervals[0].events
        assert isinstance(e, EventSpec)
        assert e.effect == 'indicate' and e.targets == ['A', 'B']
        assert e.start == 0.5 and e.duration == pytest.approx(1.0)
        assert seq.has_events() is True

    def test_duration_clamped(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'events': [{'effect': 'flash', 'targets': ['B'],
                                 'at': 0.5, 'duration': 5.0}]},
        ]), _construction())
        (e,) = seq.intervals[0].events
        assert e.duration == pytest.approx(0.5)

    def test_no_events_empty(self):
        seq = KeyframeSequence.from_json(_v2([{'t': 0}, {'t': 1}]), _construction())
        assert seq.intervals[0].events == []
        assert seq.has_events() is False
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** in `animageo/keyframes.py`:

3a. `EVENT_EFFECTS = ('indicate', 'flash', 'circumscribe')`. `Keyframe.__slots__` += `'events'`; `__init__` param `events=None` → `self.events = events or []`.

3b. `EventSpec` dataclass:
```python
@dataclass
class EventSpec:
    effect: str
    targets: list
    start: float
    duration: float
    color: object = None      # hex str or None
    scale: float = 1.2
```

3c. Event normalizer (module-level, uses `normalize_hex`):
```python
def _normalize_event(spec, kf_index, construction):
    if not isinstance(spec, dict):
        raise ValueError(f"Keyframe {kf_index}: each event must be an object, got {spec!r}")
    effect = spec.get('effect', 'indicate')
    if effect == 'passing_flash':
        raise ValueError(
            f"Keyframe {kf_index}: 'passing_flash' event is not available yet")
    if effect not in EVENT_EFFECTS:
        raise ValueError(
            f"Keyframe {kf_index}: unknown event effect '{effect}'; valid: {EVENT_EFFECTS}")
    targets = spec.get('targets', [])
    if not isinstance(targets, (list, tuple)) or not targets:
        raise ValueError(f"Keyframe {kf_index}: event 'targets' must be a non-empty list")
    for name in targets:
        if construction.element(name) is None:
            raise ValueError(f"Keyframe {kf_index}: event target '{name}' not found")
    color = spec.get('color')
    if color is not None:
        color = normalize_hex(color)
    return {
        'effect': effect, 'targets': list(targets),
        'at': float(spec.get('at', 0.0)), 'duration': float(spec.get('duration', 0.6)),
        'color': color, 'scale': float(spec.get('scale', 1.2)),
    }
```

3d. In `from_json` per-keyframe loop (after styles/visibility parsing):
```python
            raw_events = kf_data.get('events', [])
            if raw_events and version < 2:
                raise ValueError(f"Keyframe {i}: 'events' requires '\"version\": 2'")
            events = [_normalize_event(ev, i, construction) for ev in raw_events]
```
Pass `events=events` to `Keyframe(...)`.

3e. `KeyframeInterval.__slots__` += `'events'`; init `self.events = []`. `KeyframeSequence.has_events`:
```python
    def has_events(self):
        return any(iv.events for iv in self.intervals)
```

3f. In `_build_intervals`, after the enter/exit compilation (or wherever the interval is built), compile events:
```python
        for ev in kf_next.events:
            dur = interval.duration
            if dur <= 0:
                continue
            at = min(max(ev['at'], 0.0), dur)
            edur = min(ev['duration'], dur - at)
            if edur <= 0:
                continue
            interval.events.append(EventSpec(
                effect=ev['effect'], targets=ev['targets'], start=at,
                duration=edur, color=ev['color'], scale=ev['scale']))
```
(If `_build_intervals` doesn't currently see `kf_next.events`, it does now — `kf_next` is `keyframes[i+1]`.)

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframes.py tests/test_keyframe_visibility.py tests/test_keyframe_camera.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): parse + compile emphasis events (indicate/flash/circumscribe)`.

---

### Task 2: `indicate` (transform event) + playback framework

**Files:** Modify `animageo/animageo.py`; Test append.

**Interfaces:**
- `_event_envelope(spec, t_abs) -> float`: a there-and-back bump in `[0,1]`: `local = (t_abs - spec.start)/spec.duration`; return `0.0` if `local < 0 or local > 1`, else `sin(pi*local)` (0 at both ends, 1 at the middle). Outside the window → exactly 0 (self-restoring).
- `_event_indicate(mobj, env, spec)`: scale the target by `1 + (spec.scale - 1)*env` about its centre and lerp its stroke+fill colour toward `spec.color` (default a highlight, e.g. `#ff8800`) by `env`. At `env == 0`: no scale, no colour shift (identity) — verified by test.
- `_apply_events(interval, t_abs, active)`: for each `EventSpec` in `interval.events`, compute `env`; dispatch `indicate` → `_event_indicate` on each target's mobject (after the normal `updateGeoElements`, so it transforms the fresh mobject). `active` is a dict for additive-event temp mobjects (Task 3) — for Task 2, `indicate` ignores it.
- Both `on_frame`s call `scene_ref._apply_events(interval, t_abs, active_events)` LAST (after visibility effects). Add `active_events = {}` before the play and pass it; at interval end, remove any leftover temp mobjects (Task 3 populates them; harmless empty in Task 2).

- [ ] **Step 1: Write failing tests** (append)

```python
from animageo.animageo import AnimaGeoScene
from animageo.keyframes import EventSpec


def _scene():
    s = AnimaGeoScene()
    c = _construction()
    s.geo = c
    s.applyStyle()
    return s


class TestEventEnvelope:
    def test_bump_zero_at_ends_one_at_mid(self):
        s = AnimaGeoScene()
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0)
        assert s._event_envelope(spec, 0.0) == pytest.approx(0.0)
        assert s._event_envelope(spec, 0.5) == pytest.approx(1.0)
        assert s._event_envelope(spec, 1.0) == pytest.approx(0.0, abs=1e-9)

    def test_zero_outside_window(self):
        s = AnimaGeoScene()
        spec = EventSpec('indicate', ['B'], start=0.5, duration=0.5)
        assert s._event_envelope(spec, 0.4) == 0.0
        assert s._event_envelope(spec, 1.1) == 0.0


class TestIndicateAdapter:
    def test_identity_at_envelope_zero(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('B')
        w0 = mobj.width
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0, scale=1.5)
        s._event_indicate(mobj, 0.0, spec)
        assert mobj.width == pytest.approx(w0)      # no change at env 0

    def test_scales_up_at_envelope_one(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('B')
        w0 = mobj.width
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0, scale=1.5)
        s._event_indicate(mobj, 1.0, spec)
        assert mobj.width > w0

    def test_apply_events_does_not_touch_elem_style(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        interval_events = [EventSpec('indicate', ['B'], start=0.0, duration=1.0)]
        class _IV:
            events = interval_events
        before = dict(elem.style)
        s._apply_events(_IV(), 0.5, {})
        assert dict(elem.style) == before
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement**
```python
    def _event_envelope(self, spec, t_abs):
        if spec.duration <= 0:
            return 0.0
        local = (t_abs - spec.start) / spec.duration
        if local < 0.0 or local > 1.0:
            return 0.0
        import math
        return math.sin(math.pi * local)

    def _event_indicate(self, mobj, env, spec):
        if env <= 0 or mobj is None:
            return
        factor = 1.0 + (spec.scale - 1.0) * env
        try:
            mobj.scale(factor, about_point=mobj.get_center())
        except Exception:
            pass
        col = spec.color or '#ff8800'
        try:
            from .style.colorspace import lerp_color
            for sub in mobj.family_members_with_points():
                if sub.get_stroke_opacity() > 0:
                    cur = sub.get_stroke().to_hex() if hasattr(sub.get_stroke(), 'to_hex') else None
                    # blend toward highlight colour by env (best-effort)
                    sub.set_stroke(color=col if env > 0 else cur)
        except Exception:
            pass

    def _apply_events(self, interval, t_abs, active):
        for spec in getattr(interval, 'events', []):
            env = self._event_envelope(spec, t_abs)
            if spec.effect == 'indicate':
                for name in spec.targets:
                    self._event_indicate(self.mobject(name), env, spec)
            else:
                self._event_additive(spec, env, t_abs, active)   # Task 3
```
(Note: `_event_additive` is added in Task 3; for Task 2 add a stub `def _event_additive(self, spec, env, t_abs, active): pass` so `indicate` works standalone. Task 3 replaces the stub.)

Hooks: in BOTH `on_frame`s, initialise `active_events = {}` in the enclosing method (before `self.play(...)`), and at the end of `on_frame` (after visibility effects) call `scene_ref._apply_events(interval, t_abs, active_events)`. After `self.play(...)` returns, remove leftover temp mobjects: `for m in active_events.values(): self.remove(m)`. (`_play_keyframe_interval` has no `t_abs` currently — compute `t_abs = t * interval.duration` there too.)

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframe_visibility.py tests/test_keyframe_camera.py tests/test_keyframe_styles.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): indicate emphasis event + events playback framework`.

---

### Task 3: Additive events — `flash` + `circumscribe`

**Files:** Modify `animageo/animageo.py` (replace the `_event_additive` stub); Test append.

**Interface:** `_event_additive(self, spec, env, t_abs, active)` — key = `id(spec)` (per-interval unique). If `env > 0` and no temp mobject for this spec yet, CREATE one (flash: short radial `Line`s from the target's centre; circumscribe: a `Rectangle`/`Circle` around the target's bounding box) and `self.add` it + store in `active`. Each frame set the temp mobject's opacity to `env` (fade in/out with the bump). If `env <= 0` and a temp mobject exists, `self.remove` it and drop from `active`. Uses the first target's mobject for geometry (centre / bbox).

- [ ] **Step 1: Write failing tests** (append)

```python
class TestAdditiveEvents:
    def test_flash_adds_and_removes_temp_mobject(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        spec = EventSpec('flash', ['B'], start=0.0, duration=1.0)
        active = {}
        n0 = len(s.mobjects)
        s._event_additive(spec, 0.5, 0.5, active)      # mid-window -> temp added
        assert len(active) == 1
        assert len(s.mobjects) == n0 + 1
        s._event_additive(spec, 0.0, 1.01, active)     # past window -> removed
        assert len(active) == 0
        assert len(s.mobjects) == n0

    def test_circumscribe_adds_box_around_target(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        spec = EventSpec('circumscribe', ['B'], start=0.0, duration=1.0)
        active = {}
        s._event_additive(spec, 0.5, 0.5, active)
        assert len(active) == 1
        temp = next(iter(active.values()))
        # the box encloses the target
        assert temp.width >= s.mobject('B').width
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** — replace the `_event_additive` stub with a real implementation building a manim `VGroup`/`Rectangle`/`Circle`/`Line`s from the first target's mobject geometry, adding at window start, setting opacity to `env` each frame, removing when `env<=0`. Use `key = id(spec)`. Guard all manim calls with try/except so a degenerate target can't crash the frame loop.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `feat(keyframes): flash + circumscribe additive emphasis events`.

---

### Task 4: Byte-identical invariant smoke test + docs + full suite

- [ ] **Step 1: The self-restoration smoke render (real manim) — the critical event invariant.** Render TWO short animations of the SAME scene over the SAME duration: (A) with an `indicate` (and a `circumscribe`) event that COMPLETES before the last frame, (B) identical but with NO `events`. Extract the LAST frame of each; assert they are pixel-identical (or within a tiny tolerance — anti-aliasing). This proves events self-restore. Also assert a MID-event frame of (A) DIFFERS from (B) (the event is actually visible). Report evidence.
- [ ] **Step 2: If the invariant fails (a leak — e.g. a temp mobject not removed, or indicate not restoring), fix it (TDD).** Do not proceed until the last frames match.
- [ ] **Step 3: Docs.** `AI_USAGE_PROMPT.md` §8.3: `events` example (`"events": [{"effect": "indicate", "targets": ["B"], "at": 0.5, "duration": 0.6}]`), list `indicate`/`flash`/`circumscribe`, note they are one-shot self-restoring (the scene returns to normal after), `passing_flash` not yet available. `CHANGELOG.md` `[Unreleased]`: bullet for emphasis events. CLAUDE.md: controller handles.
- [ ] **Step 4: Full suite** `python3.13 -m pytest tests/ -q` → 0 failures.
- [ ] **Step 5: Commit** `docs+test: keyframes v2 emphasis events + self-restoration invariant`.

## Out of scope (documented future additions)
- `passing_flash` emphasis event (highlight travelling along a parametrised stroke).
- Pixel-invariant camera, per-key easing, text crossfade (from phase 5).
