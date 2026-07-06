# Keyframes v2 Phase 2 — Visibility & Entrance/Exit Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** In keyframes JSON v2, drive element visibility with per-keyframe `visible` maps and animate appearance/disappearance with entrance/exit effects (fade, none, create/uncreate, grow/shrink) played *inside* each interval at exact duration — replacing the legacy show/hide that injected an extra 0.4 s per batch.

**Architecture:** Parsing/compilation stays in `keyframes.py` (manim-free): `Keyframe` gains `visible`/`enter`/`exit`; `KeyframeSequence` gains `defaults`; a new `bind_visibility()` compiles per-interval `EffectSpec` lists from carry-forward visibility. Playback stays in `animageo.py`: for **v2** sequences the interval's single `self.play(...)` (exact interval duration) also drives entrance/exit effect adapters, applied to each freshly-`become`d mobject after `updateGeoElements` (effect multiplies over the render, mirroring the phase-1 style-track pattern). **v1** sequences keep the legacy show/hide-with-0.4 s path byte-identical.

**Tech Stack:** Python 3.10+, manim 0.20.1, numpy, pytest. No new deps. `keyframes.py` stays **manim-free**.

**Spec:** `docs/superpowers/specs/2026-07-05-keyframes-v2-design.md` §5.2, §5.4, §7 phase 2, §8 decisions (default entrance = fade; deprecate v1 timing).

## Global Constraints

- **v1 keyframe JSON (`version` 1 / absent) plays byte-identical**, including the legacy `+0.4 s` show/hide timing. Only v2 uses the new integrated timing. This is a hard invariant — the phase must not change any v1 code path.
- v2 total playback duration = `t` of the last keyframe **exactly** (no injected effect time).
- Default entrance effect = **`fade`**; default exit = **`fade`** (spec §8 decision 1). Per-type idiomatic defaults are out of scope (later).
- Entrance effects: `fade`, `none`, `create`, `grow`. Exit effects: `fade`, `none`, `uncreate`, `shrink`. `write` (text) is phase 3 — reject it here with a clear "phase 3" error.
- `show`/`hide` arrays remain valid v2 sugar → converted to `visible` deltas; an element in `show`/`hide` with no explicit `enter`/`exit` uses the default effect.
- `visible` is an **absolute** per-keyframe map `{name: bool}` (carry-forward). Keyframe-0 `visible` sets initial visibility (no entrance effect).
- Effects play WITHIN the interval that ENDS at the keyframe declaring the visibility change (same carry-forward interval semantics as `values`/`styles`).
- An effect adapter must **never mutate construction state or `elem.style`** — it only transforms the freshly-rendered mobject for the current frame. It is re-applied every frame after `become`.
- `keyframes.py` stays manim-free (no manim import); adapters live in `animageo.py`.
- Work on branch `feat/keyframes-v2-phase2` in the worktree. Commit conventional style. **NO AI-attribution trailers.** Test with `python3.13 -m pytest` (NOT `python3`).

## File Structure

| File | Responsibility |
|---|---|
| Modify `animageo/keyframes.py` | `Keyframe.visible/enter/exit`, `KeyframeSequence.defaults`, `EffectSpec`, `KeyframeInterval.enter_effects/exit_effects`, `bind_visibility()`, v2 parse + validation |
| Modify `animageo/animageo.py` | v1/v2 branch in `play_keyframes`; `_apply_keyframe_state` applies `visible`; effect lifecycle + adapters (`_apply_visibility_effects`, `_effect_fade`, `_effect_partial`, `_effect_scale`), integrated interval play |
| Test `tests/test_keyframe_visibility.py` (new) | schema parse, bind_visibility timeline, adapter math, scene wiring, v1-inertness |
| Modify `CLAUDE.md`, `animageo/AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document v2 visibility/effects (final task) |

---

### Task 1: Parse `visible` / `enter` / `exit` / `defaults`

**Files:**
- Modify: `animageo/keyframes.py` (`Keyframe` ~line 159 region; `KeyframeSequence.__init__`; `from_json`)
- Test: `tests/test_keyframe_visibility.py` (new)

**Interfaces produced:**
- `Keyframe(..., visible=None, enter=None, exit=None)` with slots `visible` (dict name→bool), `enter`/`exit` (dict name→{'effect','duration','at'}).
- `KeyframeSequence(..., defaults=None)` with `.defaults` dict (keys `easing`, `enter`, `exit`).
- Module constants: `ENTER_EFFECTS = ('fade','none','create','grow')`, `EXIT_EFFECTS = ('fade','none','uncreate','shrink')`, `DEFAULT_EFFECT_DURATION = 0.4`.
- `from_json` parses top-level `"defaults"`, per-keyframe `"visible"`, `"enter"`, `"exit"`; folds `show`/`hide` into `visible`; validates effect names (reject `write` with "phase 3"), element existence, and requires v2 for `visible`/`enter`/`exit`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_keyframe_visibility.py`:

```python
"""Keyframes v2 phase 2: visibility maps + entrance/exit effects."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import (
    Keyframe, KeyframeSequence, ENTER_EFFECTS, EXIT_EFFECTS,
    DEFAULT_EFFECT_DURATION,
)


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestVisibilityParsing:
    def test_visible_map_parsed(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ]), _construction())
        assert seq.keyframes[0].visible == {'M': False}
        assert seq.keyframes[1].visible == {'M': True}

    def test_show_hide_fold_into_visible(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'show': ['M'], 'hide': ['B']},
        ]), _construction())
        assert seq.keyframes[1].visible == {'M': True, 'B': False}

    def test_enter_exit_specs_parsed_with_defaults_filled(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True},
             'enter': {'M': {'effect': 'create', 'duration': 0.8, 'at': 0.1}}},
        ]), _construction())
        assert seq.keyframes[1].enter['M'] == {
            'effect': 'create', 'duration': 0.8, 'at': 0.1}

    def test_enter_effect_shorthand_string(self):
        # "enter": {"M": "grow"} is shorthand for {"effect": "grow"}
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'grow'}},
        ]), _construction())
        assert seq.keyframes[1].enter['M']['effect'] == 'grow'
        assert seq.keyframes[1].enter['M']['duration'] == DEFAULT_EFFECT_DURATION
        assert seq.keyframes[1].enter['M']['at'] == 0.0

    def test_top_level_defaults_parsed(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0}, {'t': 1},
        ], defaults={'easing': 'linear',
                     'enter': {'effect': 'create', 'duration': 0.6}}), _construction())
        assert seq.defaults['easing'] == 'linear'
        assert seq.defaults['enter'] == {'effect': 'create', 'duration': 0.6}

    def test_visible_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'visible': {'M': False}}, {'t': 1},
            ]}, _construction())

    def test_enter_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0}, {'t': 1, 'enter': {'M': 'fade'}},
            ]}, _construction())

    def test_unknown_effect_rejected(self):
        with pytest.raises(ValueError, match='effect'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': False}},
                {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'sparkle'}},
            ]), _construction())

    def test_write_effect_rejected_as_phase3(self):
        with pytest.raises(ValueError, match='phase 3'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': False}},
                {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'write'}},
            ]), _construction())

    def test_exit_effect_validated_against_exit_set(self):
        # 'create' is an entrance effect, not valid for exit
        with pytest.raises(ValueError, match='exit'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': True}},
                {'t': 1, 'visible': {'M': False}, 'exit': {'M': 'create'}},
            ]), _construction())

    def test_visible_unknown_element_rejected(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'GHOST': False}}, {'t': 1},
            ]), _construction())

    def test_effect_sets_membership(self):
        assert ENTER_EFFECTS == ('fade', 'none', 'create', 'grow')
        assert EXIT_EFFECTS == ('fade', 'none', 'uncreate', 'shrink')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest tests/test_keyframe_visibility.py -q`
Expected: ImportError (`ENTER_EFFECTS` not defined) / failures.

- [ ] **Step 3: Implement parsing in `keyframes.py`**

3a. Add module constants near the top (after `EASING_FUNCTIONS`):

```python
ENTER_EFFECTS = ('fade', 'none', 'create', 'grow')
EXIT_EFFECTS = ('fade', 'none', 'uncreate', 'shrink')
DEFAULT_EFFECT_DURATION = 0.4
```

3b. Extend `Keyframe`:

```python
class Keyframe:
    """A single keyframe at time t."""
    __slots__ = ('t', 'values', 'show', 'hide', 'easing_name', 'styles',
                 'visible', 'enter', 'exit')

    def __init__(self, t, values=None, show=None, hide=None, easing_name='smooth',
                 styles=None, visible=None, enter=None, exit=None):
        self.t = float(t)
        self.values = values or {}
        self.show = show or []
        self.hide = hide or []
        self.easing_name = easing_name
        self.styles = styles or {}
        self.visible = visible or {}     # name -> bool (absolute)
        self.enter = enter or {}         # name -> {'effect','duration','at'}
        self.exit = exit or {}           # name -> {'effect','duration','at'}
```

3c. Add a helper to normalize an effect spec (module-level):

```python
def _normalize_effect(name, spec, valid_effects, phase_kw):
    """Normalize an enter/exit effect spec to {'effect','duration','at'}.

    ``spec`` may be a bare effect string ('fade') or a dict. Validates the
    effect name against ``valid_effects`` and rejects 'write' (phase 3).
    """
    if isinstance(spec, str):
        spec = {'effect': spec}
    if not isinstance(spec, dict):
        raise ValueError(f"{phase_kw}['{name}'] must be an effect name or object, got {spec!r}")
    effect = spec.get('effect', 'fade')
    if effect == 'write':
        raise ValueError(
            f"{phase_kw}['{name}']: 'write' effect (text) is planned for phase 3, "
            f"not available yet"
        )
    if effect not in valid_effects:
        raise ValueError(
            f"{phase_kw}['{name}']: unknown {phase_kw} effect '{effect}'; "
            f"valid: {valid_effects}"
        )
    duration = float(spec.get('duration', DEFAULT_EFFECT_DURATION))
    at = float(spec.get('at', 0.0))
    return {'effect': effect, 'duration': duration, 'at': at}
```

3d. `KeyframeSequence.__init__`: add `defaults=None` param and `self.defaults = defaults or {}`.

3e. In `from_json`, after the version/deprecation handling, parse top-level defaults:

```python
        raw_defaults = data.get('defaults', {})
        defaults = {}
        if raw_defaults:
            if version < 2:
                raise ValueError("'defaults' requires '\"version\": 2'")
            defaults['easing'] = raw_defaults.get('easing', 'smooth')
            if 'enter' in raw_defaults:
                defaults['enter'] = _normalize_effect(
                    '<default>', raw_defaults['enter'], ENTER_EFFECTS, 'enter')
            if 'exit' in raw_defaults:
                defaults['exit'] = _normalize_effect(
                    '<default>', raw_defaults['exit'], EXIT_EFFECTS, 'exit')
```

3f. In the per-keyframe loop, after styles parsing, parse visibility (fold show/hide) and enter/exit. `show`/`hide` stay on the Keyframe too (v1 path still reads them); for v2 they ALSO populate `visible`:

```python
            raw_visible = kf_data.get('visible', {})
            raw_enter = kf_data.get('enter', {})
            raw_exit = kf_data.get('exit', {})
            if (raw_visible or raw_enter or raw_exit) and version < 2:
                raise ValueError(
                    f"Keyframe {i}: 'visible'/'enter'/'exit' require '\"version\": 2'"
                )
            visible = {}
            # show/hide sugar folds into the absolute visible map (v2)
            for nm in show:
                visible[nm] = True
            for nm in hide:
                visible[nm] = False
            for nm, val in raw_visible.items():
                visible[nm] = bool(val)
            for nm in visible:
                if construction.element(nm) is None:
                    raise ValueError(
                        f"Keyframe {i}: visibility target '{nm}' not found in construction"
                    )
            enter = {nm: _normalize_effect(nm, spec, ENTER_EFFECTS, 'enter')
                     for nm, spec in raw_enter.items()}
            exit_ = {nm: _normalize_effect(nm, spec, EXIT_EFFECTS, 'exit')
                     for nm, spec in raw_exit.items()}
            for nm in list(enter) + list(exit_):
                if construction.element(nm) is None:
                    raise ValueError(
                        f"Keyframe {i}: enter/exit target '{nm}' not found in construction"
                    )
```

Extend the `Keyframe(...)` construction with `visible=visible, enter=enter, exit=exit`. Keep `show=show, hide=hide` as before (v1 path unchanged). Extend the final `cls(...)` with `defaults=defaults`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest tests/test_keyframe_visibility.py -q`
Expected: PASS.

- [ ] **Step 5: v1 regression**

Run: `python3.13 -m pytest tests/test_keyframes.py tests/test_keyframe_styles.py -q`
Expected: PASS (v1 keyframes still parse; `show`/`hide` still on Keyframe).

- [ ] **Step 6: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframe_visibility.py
git commit -m "feat(keyframes): parse v2 visible maps, enter/exit effects, defaults"
```

---

### Task 2: Compile the visibility timeline (`bind_visibility`)

**Files:**
- Modify: `animageo/keyframes.py` (`KeyframeInterval` slots/init; new `EffectSpec`; `KeyframeSequence.bind_visibility`)
- Test: `tests/test_keyframe_visibility.py` (append)

**Interfaces produced:**
- `EffectSpec` (dataclass or namedtuple): `name: str`, `kind: str` (effect name), `start: float` (seconds from interval start), `duration: float`, `direction: str` (`'in'`|`'out'`).
- `KeyframeInterval.enter_effects: list[EffectSpec]`, `.exit_effects: list[EffectSpec]` (default `[]`).
- `KeyframeSequence.bind_visibility(get_element=None)` compiles them from carry-forward visibility + per-keyframe enter/exit + `self.defaults`. Also stores `self.initial_visibility: dict[name,bool]` (from keyframe 0's `visible`, for `_apply_keyframe_state`). Returns nothing (mutates intervals). `has_visibility_effects()` → bool.

**Semantics:**
- Running visibility carries forward. Starting state = keyframe-0 `visible` merged over the construction's current visibility (unlisted elements keep current).
- For interval `i` (kf `i` → kf `i+1`): for each `(name, new_vis)` in `keyframes[i+1].visible`, compare to running `prev_vis`:
  - `False → True` ⇒ an **enter** effect. Effect spec = `keyframes[i+1].enter.get(name)` else `self.defaults.get('enter')` else `{'effect':'fade','duration':DEFAULT,'at':0}`.
  - `True → False` ⇒ an **exit** effect. Effect spec = `keyframes[i+1].exit.get(name)` else `self.defaults.get('exit')` else default fade.
  - No change ⇒ nothing.
- `duration` clamped to `min(duration, interval.duration - at)` and `at` clamped to `[0, interval.duration]`; if `interval.duration == 0` skip. `start = at`.
- Update running visibility to `new_vis`.

- [ ] **Step 1: Write failing tests** (append)

```python
from animageo.keyframes import EffectSpec


class TestBindVisibility:
    def _seq(self, kfs, **top):
        return KeyframeSequence.from_json(_v2(kfs, **top), _construction())

    def test_enter_effect_created_on_false_to_true(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert (e.name, e.kind, e.direction) == ('M', 'fade', 'in')
        assert e.start == 0.0 and e.duration == pytest.approx(0.4)
        assert seq.intervals[0].exit_effects == []

    def test_exit_effect_created_on_true_to_false(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': True}},
            {'t': 1, 'visible': {'M': False}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].exit_effects
        assert (e.name, e.kind, e.direction) == ('M', 'fade', 'out')

    def test_no_change_no_effect(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': True}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        assert seq.intervals[0].enter_effects == []
        assert seq.intervals[0].exit_effects == []

    def test_explicit_effect_and_timing_used(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 2, 'visible': {'M': True},
             'enter': {'M': {'effect': 'grow', 'duration': 0.8, 'at': 0.3}}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.kind == 'grow' and e.start == 0.3 and e.duration == pytest.approx(0.8)

    def test_duration_clamped_to_interval(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 0.5, 'visible': {'M': True},
             'enter': {'M': {'effect': 'fade', 'duration': 2.0, 'at': 0.0}}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.duration == pytest.approx(0.5)   # clamped to interval

    def test_defaults_enter_used_when_no_per_kf_effect(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ], defaults={'enter': {'effect': 'create', 'duration': 0.6}})
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.kind == 'create' and e.duration == pytest.approx(0.6)

    def test_initial_visibility_recorded(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False, 'B': True}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        assert seq.initial_visibility.get('M') is False
        assert seq.initial_visibility.get('B') is True

    def test_has_visibility_effects(self):
        seq = self._seq([{'t': 0, 'visible': {'M': False}},
                         {'t': 1, 'visible': {'M': True}}])
        seq.bind_visibility()
        assert seq.has_visibility_effects() is True
        seq2 = self._seq([{'t': 0}, {'t': 1}])
        seq2.bind_visibility()
        assert seq2.has_visibility_effects() is False
```

- [ ] **Step 2: Run to verify fail**

Run: `python3.13 -m pytest tests/test_keyframe_visibility.py::TestBindVisibility -q` → FAIL (`EffectSpec` import / `bind_visibility` missing).

- [ ] **Step 3: Implement**

3a. `EffectSpec` (module-level, after imports):

```python
from dataclasses import dataclass, field   # add to imports if not present


@dataclass
class EffectSpec:
    name: str
    kind: str        # 'fade' | 'none' | 'create' | 'grow' | 'uncreate' | 'shrink'
    start: float     # seconds from interval start
    duration: float
    direction: str   # 'in' (entrance) | 'out' (exit)
```

3b. `KeyframeInterval.__slots__` — add `'enter_effects'`, `'exit_effects'`; init both to `[]`.

3c. `KeyframeSequence`: add `self.initial_visibility = {}` in `__init__`, and:

```python
    def has_visibility_effects(self):
        return any(iv.enter_effects or iv.exit_effects for iv in self.intervals)

    def bind_visibility(self, get_element=None):
        """Compile per-interval enter/exit EffectSpec lists from carry-forward
        visibility. Records keyframe-0 visibility in ``self.initial_visibility``.
        """
        DEFAULT_ENTER = self.defaults.get('enter', {'effect': 'fade', 'duration': DEFAULT_EFFECT_DURATION, 'at': 0.0})
        DEFAULT_EXIT = self.defaults.get('exit', {'effect': 'fade', 'duration': DEFAULT_EFFECT_DURATION, 'at': 0.0})

        self.initial_visibility = dict(self.keyframes[0].visible)
        running = dict(self.keyframes[0].visible)

        for i, interval in enumerate(self.intervals):
            interval.enter_effects = []
            interval.exit_effects = []
            kf = self.keyframes[i + 1]
            dur = interval.duration
            for name, new_vis in kf.visible.items():
                prev = running.get(name)
                running[name] = new_vis
                if prev == new_vis:
                    continue
                if dur <= 0:
                    continue
                if new_vis:      # entrance
                    spec = kf.enter.get(name, DEFAULT_ENTER)
                    at = min(max(float(spec.get('at', 0.0)), 0.0), dur)
                    edur = min(float(spec.get('duration', DEFAULT_EFFECT_DURATION)), dur - at)
                    interval.enter_effects.append(EffectSpec(
                        name=name, kind=spec['effect'], start=at,
                        duration=max(edur, 0.0), direction='in'))
                else:            # exit
                    spec = kf.exit.get(name, DEFAULT_EXIT)
                    at = min(max(float(spec.get('at', 0.0)), 0.0), dur)
                    edur = min(float(spec.get('duration', DEFAULT_EFFECT_DURATION)), dur - at)
                    interval.exit_effects.append(EffectSpec(
                        name=name, kind=spec['effect'], start=at,
                        duration=max(edur, 0.0), direction='out'))
```

- [ ] **Step 4: Run to verify pass**

Run: `python3.13 -m pytest tests/test_keyframe_visibility.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframe_visibility.py
git commit -m "feat(keyframes): bind_visibility — compile enter/exit effect timeline"
```

---

### Task 3: Integrated v2 playback + fade/none adapters

This is the core task: branch `play_keyframes` on version, and for v2 fold visibility effects into each interval's single `self.play(...)` with the fade/none adapters. **v1 stays byte-identical.**

**Files:**
- Modify: `animageo/animageo.py` (`play_keyframes` ~1524; `_apply_keyframe_state` ~1380; `_play_keyframe_interval` ~1595; new helpers)
- Test: `tests/test_keyframe_visibility.py` (append scene-level tests)

**Interfaces produced (all on `AnimaGeoScene`):**
- `_effect_alpha(spec, t_abs) -> float`: for a spec with `start`/`duration`, `raw = clamp((t_abs - start)/duration, 0, 1)` (duration 0 → step at `start`); returns `raw` for `direction=='in'`, `1-raw` for `'out'`. Alpha is the element's visible-fraction (1 = fully present).
- `_apply_effect_alpha(elem_name, kind, alpha) -> None`: transform the current mobject for `elem_name` by `alpha` per `kind`. Phase 3 implements only `fade` and `none`; `create`/`grow`/`uncreate`/`shrink` are added in Tasks 4–5 (until then they fall back to `fade` with a one-time debug log — see Step 3d).
- `_effect_fade(mobj, alpha)`: multiply every family member's stroke & fill opacity by `alpha`.
- `play_keyframes` branches: v2 with visibility effects → integrated interval loop (`_play_keyframe_interval_v2`); everything else → the existing loop unchanged.

**Element lifecycle within a v2 interval** (mid-interval add/remove avoided — entering elements are present-but-transparent before their `start`):
- Before the interval's `play()`: for every `enter_effects` element, set `elem.visible = True` and ensure its mobject exists (`updateGeoElements([name])`); the fade adapter keeps it transparent until `start`.
- During each frame: after the normal geometry/style `updateGeoElements`, apply every active enter/exit effect's alpha to its element's mobject.
- After the interval's `play()`: for every `exit_effects` element set `elem.visible = False` and remove its mobject; for entered elements leave them fully visible (the last frame already had alpha 1).

- [ ] **Step 1: Write failing tests** (append; scene-level, no real render — assert state + that a fade adapter changes opacity)

```python
from animageo.animageo import AnimaGeoScene


def _scene():
    s = AnimaGeoScene()
    c = s.geo
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return s


class TestEffectAlpha:
    def test_in_ramps_up(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.0, duration=1.0, direction='in')
        assert s._effect_alpha(spec, 0.0) == 0.0
        assert s._effect_alpha(spec, 0.5) == pytest.approx(0.5)
        assert s._effect_alpha(spec, 1.0) == 1.0

    def test_out_ramps_down(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.0, duration=1.0, direction='out')
        assert s._effect_alpha(spec, 0.0) == 1.0
        assert s._effect_alpha(spec, 1.0) == 0.0

    def test_start_offset_respected(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.5, duration=0.5, direction='in')
        assert s._effect_alpha(spec, 0.4) == 0.0     # before start
        assert s._effect_alpha(spec, 0.75) == pytest.approx(0.5)
        assert s._effect_alpha(spec, 1.0) == 1.0

    def test_zero_duration_steps(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'none', start=0.5, duration=0.0, direction='in')
        assert s._effect_alpha(spec, 0.49) == 0.0
        assert s._effect_alpha(spec, 0.5) == 1.0


class TestFadeAdapter:
    def test_fade_multiplies_opacity(self):
        s = _scene()
        elem = s.geo.element('M')
        elem.visible = True
        s.addGeoElement(elem)
        mobj = s.mobject('M')
        assert mobj is not None
        s._effect_fade(mobj, 0.25)
        for sub in mobj.family_members_with_points():
            assert sub.get_fill_opacity() <= 0.25 + 1e-6 or sub.get_stroke_opacity() <= 0.25 + 1e-6


class TestV2VisibilityWiring:
    def test_kf0_visible_applied(self):
        s = _scene()
        s.updateGeoElements = lambda updates=None: None
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ]), s.geo)
        seq.bind_visibility()
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert s.geo.element('M').visible is False

    def test_v1_path_unchanged_uses_show_hide(self, monkeypatch):
        # A v1 sequence must still go through the legacy Show/Hide 0.4s path.
        s = _scene()
        calls = {'show': 0, 'hide': 0, 'v2': 0}
        monkeypatch.setattr(s, 'Show', lambda names, *a, **k: (calls.__setitem__('show', calls['show'] + 1) or []))
        monkeypatch.setattr(s, 'Hide', lambda names, *a, **k: (calls.__setitem__('hide', calls['hide'] + 1) or []))
        monkeypatch.setattr(s, '_play_keyframe_interval_v2', lambda *a, **k: calls.__setitem__('v2', calls['v2'] + 1))
        monkeypatch.setattr(s, '_play_keyframe_interval', lambda *a, **k: None)
        monkeypatch.setattr(s, 'wait', lambda *a, **k: None)
        s.play_keyframes({'keyframes': [
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}, 'show': ['M']},
        ]})
        assert calls['v2'] == 0            # v2 path never taken for v1
        assert calls['show'] >= 1          # legacy Show used
```

- [ ] **Step 2: Run to verify fail** → `python3.13 -m pytest tests/test_keyframe_visibility.py -q` (new classes fail: `_effect_alpha` etc. missing).

- [ ] **Step 3: Implement in `animageo.py`**

3a. `_apply_keyframe_state` — apply `kf.visible` (after styles, alongside the existing show/hide handling). Add:

```python
        for name, vis in kf.visible.items():
            elem = self.geo.element(name)
            if elem is not None:
                elem.visible = bool(vis)
                touched.add(name)
```

3b. Add the effect-alpha + adapter helpers (place near `_apply_style_interps`):

```python
    def _effect_alpha(self, spec, t_abs):
        """Visible-fraction of an enter/exit effect at absolute interval time.

        1.0 = fully present, 0.0 = fully absent. 'in' ramps up, 'out' ramps down.
        """
        if spec.duration <= 0:
            raw = 1.0 if t_abs >= spec.start else 0.0
        else:
            raw = (t_abs - spec.start) / spec.duration
            raw = 0.0 if raw < 0 else (1.0 if raw > 1 else raw)
        return raw if spec.direction == 'in' else 1.0 - raw

    def _effect_fade(self, mobj, alpha):
        """Multiply every family member's stroke & fill opacity by *alpha*."""
        for sub in mobj.family_members_with_points():
            try:
                sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
            except Exception:
                pass
            try:
                sub.set_fill(opacity=sub.get_fill_opacity() * alpha)
            except Exception:
                pass

    def _apply_effect_alpha(self, name, kind, alpha):
        """Transform the current mobject for *name* by *alpha* per effect *kind*.

        Phase-2 Task 3 implements 'fade'/'none'; 'create'/'grow'/'uncreate'/
        'shrink' are added in later tasks and fall back to fade until then.
        """
        mobj = self.mobject(name)
        if mobj is None:
            return
        if kind == 'none':
            # step visibility: fully shown iff alpha >= 1 (in) / > 0 (already
            # handled by _effect_alpha stepping); hide when alpha == 0.
            if alpha <= 0:
                self._effect_fade(mobj, 0.0)
            return
        # 'fade' and (for now) any not-yet-implemented kind
        self._effect_fade(mobj, alpha)
```

3c. `play_keyframes` — branch on v2-with-visibility. Bind visibility for v2 and choose the loop. Replace the interval loop body. After the `bind_style_tracks` block add:

```python
        use_v2_visibility = (seq.version >= 2)
        if use_v2_visibility:
            seq.bind_visibility(get_element=self.geo.element)
```

Then change the interval loop: for v2, call a new `_play_keyframe_interval_v2` that owns visibility lifecycle + effects + the existing interps/styles/labels; keep the legacy loop for v1. Concretely, replace the `for interval in seq.intervals:` body with:

```python
            for i, interval in enumerate(seq.intervals):
                if use_v2_visibility and (interval.enter_effects or interval.exit_effects):
                    self._play_keyframe_interval_v2(interval)
                    self._finalize_style_interval(interval)
                    continue

                # Legacy visibility path (v1, and v2 intervals with no effects)
                if interval.show:
                    plays = self.Show(interval.show)
                    if plays:
                        self.play(*plays, run_time=0.4)
                if interval.hide:
                    plays = self.Hide(interval.hide)
                    if plays:
                        self.play(*plays, run_time=0.4)

                has_labels = bool(interval.label_interps) or bool(interval.dynamic_angle_params)
                has_styles = bool(interval.style_interps)
                if not interval.interpolators and not has_labels and not has_styles:
                    if interval.duration > 0:
                        self.wait(interval.duration)
                    self._finalize_style_interval(interval)
                    continue

                self._play_keyframe_interval(interval)
                self._finalize_style_interval(interval)
```

Note: for a v2 interval that uses `show`/`hide` but has NO visibility CHANGE producing effects (e.g. showing an already-visible element), `enter_effects`/`exit_effects` are empty, so it correctly falls to the legacy branch — but since v2 folds show/hide into `visible` and `bind_visibility` only makes effects on actual changes, a real change always produces an effect and takes the v2 path. An element shown that was already visible produces no effect and no legacy Show (idempotent). This preserves exact timing for v2 (no 0.4 s) whenever there's a real visibility change.

3d. Add `_play_keyframe_interval_v2` — a variant of `_play_keyframe_interval` that also drives effects. To avoid duplicating the whole method, refactor: extract the current `_play_keyframe_interval`'s `on_frame` core into the v2 method with the effect additions. Implement:

```python
    def _play_keyframe_interval_v2(self, interval):
        """v2 interval playback: geometry + style + labels + enter/exit effects
        in one exact-duration play(). Entering elements are made present at the
        interval start (transparent until their effect starts); exiting elements
        are removed at the interval end.
        """
        from .label_placement import compute_angle_label_offset_px

        # Lifecycle: reveal entering elements now (present-but-faded); their
        # first-frame alpha keeps them invisible until the effect starts.
        for e in interval.enter_effects:
            elem = self.geo.element(e.name)
            if elem is not None:
                elem.visible = True
        entering = [e.name for e in interval.enter_effects]
        if entering:
            self.updateGeoElements(entering)

        progress = ValueTracker(0)
        sentinel = Mobject()
        interps = interval.interpolators
        label_interps = interval.label_interps
        dynamic_angle_params = interval.dynamic_angle_params
        enter_effects = interval.enter_effects
        exit_effects = interval.exit_effects
        duration = interval.duration
        geo_ref = self.geo
        scene_ref = self
        ptUnit = _style_ptUnit(self.style)
        ptUnit_ggb = self.style.export.get('ptUnit_ggb', ptUnit)

        def on_frame(mob):
            t = progress.get_value()
            t_abs = t * duration
            touched = set()
            for interp in interps:
                scene_ref._apply_interp_value(interp.name, interp.kind, interp.at(t))
                touched.add(interp.name)

            updates = geo_ref.rebuild()
            for name in touched:
                updates[name] = updates.get(name, True)
            for name in scene_ref._apply_style_interps(interval, t):
                updates[name] = updates.get(name, True)

            for li in label_interps:
                elem = geo_ref.element(li.name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                ox, oy = li.at(t)
                elem.style['label_offset_px'] = [float(ox), float(oy)]
                updates[li.name] = updates.get(li.name, True)
            for name, ap in dynamic_angle_params.items():
                elem = geo_ref.element(name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                elem.style['label_offset_px'] = list(
                    compute_angle_label_offset_px(elem.data, ap, ptUnit, ptUnit_ggb))
                updates[name] = updates.get(name, True)

            # Ensure effect targets are (re)rendered this frame so the adapter
            # transforms a fresh full-opacity mobject.
            for e in enter_effects:
                updates[e.name] = updates.get(e.name, True)
            for e in exit_effects:
                updates[e.name] = updates.get(e.name, True)

            scene_ref.updateGeoElements(updates)

            # Effects LAST — multiply over the freshly-become'd mobjects.
            for e in enter_effects:
                scene_ref._apply_effect_alpha(e.name, e.kind, scene_ref._effect_alpha(e, t_abs))
            for e in exit_effects:
                scene_ref._apply_effect_alpha(e.name, e.kind, scene_ref._effect_alpha(e, t_abs))

        sentinel.add_updater(on_frame)
        self.add(progress, sentinel)
        self.play(progress.animate(rate_func=linear).set_value(1), run_time=duration)
        sentinel.clear_updaters()
        self.remove(progress, sentinel)

        # Lifecycle end: hide + remove exited elements.
        for e in exit_effects:
            elem = self.geo.element(e.name)
            if elem is not None:
                elem.visible = False
            m = self.mobject(e.name)
            if m is not None:
                self.remove(m)
```

- [ ] **Step 4: Run to verify pass** → `python3.13 -m pytest tests/test_keyframe_visibility.py -q`.

- [ ] **Step 5: v1 + keyframe regression**

Run: `python3.13 -m pytest tests/test_keyframes.py tests/test_keyframe_styles.py tests/test_keyframe_labels.py tests/test_keyframe_initial_state.py tests/test_dynamic_tracker.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add animageo/animageo.py tests/test_keyframe_visibility.py
git commit -m "feat(keyframes): v2 integrated visibility timing + fade/none effects"
```

---

### Task 4: `create` / `uncreate` adapters (progressive stroke draw)

**Files:**
- Modify: `animageo/animageo.py` (`_apply_effect_alpha`, add `_effect_partial`)
- Test: `tests/test_keyframe_visibility.py` (append)

**Interface:** `_effect_partial(mobj, alpha)` — show only the first `alpha` fraction of each family stroke via manim's `VMobject.pointwise_become_partial(vmob_copy, 0, alpha)`; the filled first sub-mobject (polygons/circles/angles) fades in with `alpha` instead (mirroring `ShowCreate`'s FadeIn-of-fill). `_apply_effect_alpha` routes `create`/`uncreate` → `_effect_partial` (uncreate uses the already-reversed alpha from `_effect_alpha` since `direction=='out'`).

- [ ] **Step 1: Write failing test** (append)

```python
class TestPartialAdapter:
    def test_partial_zero_hides_all_points(self):
        s = _scene()
        # a segment is a pure-stroke VMobject — good for partial draw
        s.geo.add(Command('Segment', ['A', 'B'], ['seg']))
        s.geo.rebuild()
        elem = s.geo.element('seg')
        elem.visible = True
        s.addGeoElement(elem)
        mobj = s.mobject('seg')
        assert mobj is not None
        import numpy as np
        full_pts = sum(sm.get_num_points() for sm in mobj.family_members_with_points())
        s._effect_partial(mobj, 0.0)
        drawn = sum(sm.get_num_points() for sm in mobj.family_members_with_points())
        # at alpha 0 the drawn stroke collapses to (near) nothing
        assert drawn < full_pts or drawn == 0

    def test_apply_effect_alpha_routes_create(self):
        s = _scene()
        called = {}
        s._effect_partial = lambda m, a: called.setdefault('partial', a)
        elem = s.geo.element('M'); elem.visible = True; s.addGeoElement(elem)
        s._apply_effect_alpha('M', 'create', 0.5)
        assert called.get('partial') == 0.5
```

- [ ] **Step 2: Run to verify fail** → FAIL (`_effect_partial` missing / route absent).

- [ ] **Step 3: Implement**

```python
    def _effect_partial(self, mobj, alpha):
        """Progressive stroke reveal (manim Create semantics): draw only the
        first *alpha* fraction of each stroke sub-mobject; fade filled parts.
        """
        alpha = 0.0 if alpha < 0 else (1.0 if alpha > 1 else alpha)
        for sub in mobj.family_members_with_points():
            has_fill = getattr(sub, 'get_fill_opacity', lambda: 0)() > 0
            if has_fill:
                # Filled sub-mobject: fade it in rather than partial-draw.
                try:
                    sub.set_fill(opacity=sub.get_fill_opacity() * alpha)
                    sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
                except Exception:
                    pass
                continue
            try:
                full = sub.copy()
                sub.pointwise_become_partial(full, 0, alpha)
            except Exception:
                # Fallback: fade if partial draw isn't supported for this sub.
                try:
                    sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
                except Exception:
                    pass
```

Extend `_apply_effect_alpha`: before the final `_effect_fade`, add:

```python
        if kind in ('create', 'uncreate'):
            self._effect_partial(mobj, alpha)
            return
```

- [ ] **Step 4: Run to verify pass** → `python3.13 -m pytest tests/test_keyframe_visibility.py -q`.

- [ ] **Step 5: Commit**

```bash
git add animageo/animageo.py tests/test_keyframe_visibility.py
git commit -m "feat(keyframes): create/uncreate progressive-draw effect adapter"
```

---

### Task 5: `grow` / `shrink` adapters (scale from center)

**Files:**
- Modify: `animageo/animageo.py` (`_apply_effect_alpha`, add `_effect_scale`)
- Test: `tests/test_keyframe_visibility.py` (append)

**Interface:** `_effect_scale(mobj, alpha)` — scale the whole mobject about its center by `max(alpha, 1e-3)` (so alpha→0 shrinks to a point, alpha→1 is full size). `_apply_effect_alpha` routes `grow`/`shrink` → `_effect_scale`.

- [ ] **Step 1: Write failing test** (append)

```python
class TestScaleAdapter:
    def test_scale_shrinks_bbox(self):
        s = _scene()
        s.geo.add(Command('Segment', ['A', 'B'], ['seg']))
        s.geo.rebuild()
        elem = s.geo.element('seg'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('seg')
        w_full = mobj.width
        s._effect_scale(mobj, 0.25)
        assert mobj.width < w_full * 0.5

    def test_apply_effect_alpha_routes_grow(self):
        s = _scene()
        called = {}
        s._effect_scale = lambda m, a: called.setdefault('scale', a)
        elem = s.geo.element('M'); elem.visible = True; s.addGeoElement(elem)
        s._apply_effect_alpha('M', 'grow', 0.3)
        assert called.get('scale') == 0.3
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement**

```python
    def _effect_scale(self, mobj, alpha):
        """Scale *mobj* about its center by alpha (grow-from/shrink-to center)."""
        factor = max(float(alpha), 1e-3)
        try:
            mobj.scale(factor, about_point=mobj.get_center())
        except Exception:
            pass
```

Extend `_apply_effect_alpha`: before the create/uncreate branch add:

```python
        if kind in ('grow', 'shrink'):
            self._effect_scale(mobj, alpha)
            return
```

- [ ] **Step 4: Run to verify pass.**

- [ ] **Step 5: Commit**

```bash
git add animageo/animageo.py tests/test_keyframe_visibility.py
git commit -m "feat(keyframes): grow/shrink scale effect adapter"
```

---

### Task 6: End-to-end smoke render + docs + full suite

**Files:**
- Create (scratch, NOT committed): a smoke render script under the session scratchpad
- Modify: `CLAUDE.md` (gitignored — on-disk edit), `animageo/AI_USAGE_PROMPT.md`, `CHANGELOG.md`
- Test: full suite

- [ ] **Step 1: End-to-end smoke render (real manim).** Write a scene (DSL points/segment/polygon), v2 keyframes that HIDE one element with `exit: fade` and SHOW another with `enter: create`, over exact 1.2 s. Render low-quality MP4 with `tempconfig`. **DSL scenes MUST call `self.fitView(w, h)` after `putCode` and before `play_keyframes`** (without it the render is blank). Assert with cv2: (a) an element visible in the first frame is gone (near-zero colored pixels at its region) in the last frame for the exit; (b) the entering element's colored-pixel count rises from ~0 to >0. Report pixel evidence. Also confirm total frames ≈ round(1.2 * 15) (exact duration, no injected 0.4 s).

- [ ] **Step 2: If the smoke render reveals a bug, fix it (TDD: add a failing unit test first), then re-render.** Do not proceed until the render passes.

- [ ] **Step 3: Docs.**
  - `CLAUDE.md` (Keyframe Animation System section): add a "Keyframes v2 — visibility & effects" paragraph: `visible` maps, `enter`/`exit` (`fade`/`none`/`create`/`grow` · `fade`/`none`/`uncreate`/`shrink`), default fade, `defaults` block, exact-duration timing (v2 drops the legacy +0.4 s; v1 keeps it), `show`/`hide` are v2 sugar. Note `write` is phase 3. (Gitignored — edit on disk; will not be in the commit.)
  - `animageo/AI_USAGE_PROMPT.md` §8.3: add a short v2 visibility/effects example.
  - `CHANGELOG.md` `[Unreleased]`: bullet the visibility/effects feature + the v2 exact-duration timing change (note v1 unchanged/deprecated).
- [ ] **Step 4: Full suite** — `python3.13 -m pytest tests/ -q` → 0 failures.
- [ ] **Step 5: Commit** (only tracked files):

```bash
git add animageo/AI_USAGE_PROMPT.md CHANGELOG.md tests/test_keyframe_visibility.py
git commit -m "docs+test: keyframes v2 visibility & entrance/exit effects"
```

---

## Out of scope (later phases)
- `write` effect + `label_text` swap + style-aware label pre-pass (phase 3)
- `reveal_construction` macro (phase 3)
- `get_element_states`, extended easing set (phase 4)
- `@camera`, per-key easing, text crossfade, `apply_keyframes_at` (phase 5)
- `events` emphasis effects (phase 6 — last)
