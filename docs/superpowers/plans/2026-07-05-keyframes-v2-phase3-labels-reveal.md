# Keyframes v2 Phase 3 — Labels & Construction Reveal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Round out keyframes v2 with (1) `label_text` animation (discrete swap), (2) a `write` entrance effect for text/labels, (3) a style-aware label-placement pre-pass, and (4) a `reveal_construction()` macro that stages a dependency-ordered staggered reveal of the whole construction.

**Architecture:** Registry/parsing stays manim-free in `keyframes.py`/`style/animatable.py`; adapters and the reveal macro live in `animageo.py`. `reveal_construction` reuses the Phase-2 visibility/effect machinery: it builds a 2-keyframe v2 sequence (everything hidden → everything visible) whose single interval carries per-element enter effects staggered by `at` offsets in dependency order.

**Tech Stack:** Python 3.10+, manim 0.20.1, numpy, pytest. `keyframes.py`/`animatable.py` stay manim-free.

**Spec:** `docs/superpowers/specs/2026-07-05-keyframes-v2-design.md` §7 phase 3. Depends on Phases 1 (style tracks) and 2 (visibility + effects), already on `dev`.

## Global Constraints

- v1 keyframe JSON stays byte-identical. New features are v2-only.
- `label_text` animates as a **discrete swap** (snap at eased progress ≥ 0.5) — text is never lerped. One LaTeX recompile per swap is acceptable; do NOT put it on a per-frame path.
- `write` becomes a valid entrance effect (remove the Phase-2 "phase 3" rejection for it in `enter`). It stays invalid for `exit`.
- `reveal_construction` must not change the construction or persistent `elem.style`; it only drives a keyframe animation.
- `keyframes.py`/`style/animatable.py` stay manim-free.
- Branch `feat/keyframes-v2-phase3`. Conventional commits. **NO AI-attribution trailers.** Test with `python3.13 -m pytest` (NOT `python3`).

## File Structure

| File | Responsibility |
|---|---|
| Modify `animageo/style/animatable.py` | add `TEXT` kind + `'label_text': TEXT` |
| Modify `animageo/keyframes.py` | `StyleInterpolator` handles `text` (snap); remove `write` from Phase-2 enter rejection; `build_reveal_keyframes` helper (manim-free) |
| Modify `animageo/animageo.py` | `_effect_write` adapter + route; `ENTER_EFFECTS` write already in keyframes; style-aware `_compute_keyframe_label_layouts`; `reveal_construction()` |
| Test `tests/test_keyframe_labels_v3.py` (new) | label_text swap, write adapter, pre-pass styles, reveal keyframe generation + scene wiring |
| Modify `CLAUDE.md`, `AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document (final task) |

---

### Task 1: `label_text` discrete swap

**Files:** Modify `animageo/style/animatable.py`, `animageo/keyframes.py`; Test `tests/test_keyframe_labels_v3.py` (new).

**Interfaces:**
- `animatable.py`: add `TEXT = 'text'`; add `'label_text': TEXT` to `ANIMATABLE_STYLE_KEYS`; `validate_style_value`/`normalize_style_value` treat `TEXT` like a string (accept any str or None; normalize to `str(value)` when not None).
- `keyframes.py`: `StyleInterpolator.at` handles `kind == 'text'` by snapping to `end` at eased progress ≥ 0.5 (same as discrete).

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyframe_labels_v3.py`:

```python
"""Keyframes v2 phase 3: label_text swap, write effect, reveal_construction."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, StyleInterpolator, EASING_FUNCTIONS
from animageo.style.animatable import (
    ANIMATABLE_STYLE_KEYS, TEXT, style_kind, normalize_style_value, validate_style_value,
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


class TestLabelTextRegistry:
    def test_label_text_is_text_kind(self):
        assert ANIMATABLE_STYLE_KEYS['label_text'] == TEXT
        assert style_kind('label_text') == TEXT

    def test_text_value_normalized_to_str(self):
        assert normalize_style_value('label_text', 'hi') == 'hi'
        assert normalize_style_value('label_text', 42) == '42'
        assert normalize_style_value('label_text', None) is None
        validate_style_value('label_text', 'anything')   # no raise


class TestTextInterpolator:
    def test_text_snaps_at_eased_half(self):
        si = StyleInterpolator('M', 'label_text', 'text', 'old', 'new',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.49) == 'old'
        assert si.at(0.5) == 'new'


class TestLabelTextTrack:
    def test_label_text_track_binds(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'label_text': 'P'}}},
            {'t': 1, 'styles': {'M': {'label_text': 'Q'}}},
        ]), _construction())

        class _E:
            def __init__(self): self.style = {}
        seq.bind_style_tracks(get_element=lambda n: _E(),
                              resolve=lambda e, k: 'P')
        (si,) = seq.intervals[0].style_interps
        assert si.kind == 'text'
        assert si.at(1.0) == 'Q'
```

- [ ] **Step 2: Run to verify fail** → `python3.13 -m pytest tests/test_keyframe_labels_v3.py -q` (ImportError `TEXT` / kind wrong).

- [ ] **Step 3: Implement**

3a. `animateable.py`: add constant and registry entry:
```python
TEXT = 'text'
```
add `'label_text': TEXT,` to `ANIMATABLE_STYLE_KEYS`. In `validate_style_value`, `TEXT` needs no special check (any value is acceptable except enforce str-able — leave permissive; None always ok). In `normalize_style_value`, add: `if kind == TEXT: return None if value is None else str(value)`.

3b. `keyframes.py` `StyleInterpolator.at`: add before the final discrete branch:
```python
        if self.kind == 'text':
            return self.end if et >= 0.5 else self.start
```

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframe_styles.py tests/test_value_labels.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): animate label_text as discrete swap`.

---

### Task 2: `write` entrance effect adapter

**Files:** Modify `animageo/keyframes.py` (allow `write` in enter), `animageo/animageo.py` (`_effect_write` + route); Test append.

**Interfaces:**
- `keyframes.py`: `ENTER_EFFECTS` already includes... NO — Phase 2 set `ENTER_EFFECTS = ('fade','none','create','grow')` and rejects `write` with "phase 3". This task adds `'write'` to `ENTER_EFFECTS` and removes the `write`→"phase 3" special-case rejection in `_normalize_effect` (write is now valid for enter; keep it INVALID for exit — it's not in `EXIT_EFFECTS`).
- `animageo.py`: `_effect_write(mobj, alpha)` — progressive glyph reveal for text/label mobjects: show only the first `round(alpha * n)` sub-glyphs at full opacity, the rest hidden (mirrors manim `AddTextLetterByLetter`/`Write`). `_apply_effect_alpha` routes `write` → `_effect_write`.

- [ ] **Step 1: Write failing tests** (append)
```python
from animageo.keyframes import ENTER_EFFECTS


class TestWriteEffect:
    def test_write_in_enter_effects(self):
        assert 'write' in ENTER_EFFECTS

    def test_write_accepted_for_enter(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'write'}},
        ]), _construction())
        seq.bind_visibility(get_element=_construction().element)
        assert seq.keyframes[1].enter['M']['effect'] == 'write'

    def test_write_rejected_for_exit(self):
        with pytest.raises(ValueError, match='exit'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': True}},
                {'t': 1, 'visible': {'M': False}, 'exit': {'M': 'write'}},
            ]), _construction())


class TestWriteAdapter:
    def test_write_reveals_prefix_of_glyphs(self):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        from manim import Tex, VGroup
        grp = VGroup(Tex("A"), Tex("B"), Tex("C"), Tex("D"))
        # alpha 0.5 -> first 2 of 4 shown, rest transparent
        s._effect_write(grp, 0.5)
        shown = [sub for sub in grp if sub.get_fill_opacity() > 0 or sub.get_stroke_opacity() > 0]
        assert len(shown) <= 2
        s2 = AnimaGeoScene()
        grp2 = VGroup(Tex("A"), Tex("B"), Tex("C"), Tex("D"))
        s2._effect_write(grp2, 1.0)
        shown_all = [sub for sub in grp2 if sub.get_fill_opacity() > 0 or sub.get_stroke_opacity() > 0]
        assert len(shown_all) == 4
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement**

3a. `keyframes.py`: change `ENTER_EFFECTS = ('fade', 'none', 'create', 'grow', 'write')`. In `_normalize_effect`, REMOVE the `if effect == 'write': raise ...phase 3...` block (write now validated normally against the passed `valid_effects`; since it's in `ENTER_EFFECTS` but not `EXIT_EFFECTS`, an exit `write` still fails the membership check with the exit message).

3b. `animageo.py`: add `_effect_write`:
```python
    def _effect_write(self, mobj, alpha):
        """Progressive glyph reveal (manim Write/AddTextLetterByLetter): show
        the first ``alpha`` fraction of the top-level glyph submobjects, hide
        the rest. Falls back to a plain fade for a mobject with no glyph
        substructure.
        """
        alpha = 0.0 if alpha < 0 else (1.0 if alpha > 1 else alpha)
        subs = list(getattr(mobj, 'submobjects', []) or [])
        if not subs:
            self._effect_fade(mobj, alpha)
            return
        n = len(subs)
        show = int(round(alpha * n))
        for i, sub in enumerate(subs):
            self._effect_fade(sub, 1.0 if i < show else 0.0)
```
Route in `_apply_effect_alpha` (before the fade fallback):
```python
        if kind == 'write':
            self._effect_write(mobj, alpha)
            return
```

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframe_visibility.py -q`.
- [ ] **Step 6: Commit** `feat(keyframes): write entrance effect (progressive glyph reveal)`.

---

### Task 3: Style-aware label pre-pass

**Files:** Modify `animageo/animageo.py` (`_compute_keyframe_label_layouts`); Test append.

**Problem:** `_compute_keyframe_label_layouts` (the `keyframe_snapshots` pre-pass) applies per-keyframe `values` + `show`/`hide`, but NOT `styles`. So label layouts computed for keyframes that change label-affecting styles (`font_size_px`, `label_visible`, `arc_size_px`) use stale bboxes.

**Fix:** carry-forward and apply `kf.styles` at each keyframe in the pre-pass, and restore the original `elem.style` afterward. Only the animated keys need save/restore.

- [ ] **Step 1: Write failing test** (append)
```python
class TestStyleAwarePrepass:
    def test_prepass_applies_font_size_style(self):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        s.geo = _construction()
        # enable snapshots + label placement
        s.applyStyle({'overlay': {'label_placement': {
            'enabled': True, 'keyframe_snapshots': True}}})
        for e in s.geo.elements:
            e.style['label_visible'] = True
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'font_size_px': 10}}},
            {'t': 1, 'styles': {'M': {'font_size_px': 40}}},
        ]), s.geo)
        cfg = s.style_config.overlay.label_placement
        captured = {}
        # spy: record M's font_size seen by compute_label_layout at each kf
        import animageo.animageo as mod
        layouts = s._compute_keyframe_label_layouts(seq, cfg)
        # after pre-pass, elem.style restored to original (no font_size pinned)
        assert s.geo.element('M').style.get('font_size_px') in (None, 10, 40)
        # the two layouts should differ if font size influenced placement
        assert len(layouts) == 2
```
(This test is coarse — it mainly guards that the pre-pass runs styles without crashing and restores state. The reviewer/smoke check the visual effect.)

- [ ] **Step 2: Run to verify fail** (pre-pass ignores styles → may pass trivially; if so, strengthen: assert that during the pass M's font_size was actually set to 40 at kf1 by spying on `compute_label_layout`. Implementer: add a monkeypatch spy that records `s.geo.element('M').style.get('font_size_px')` at each `compute_label_layout` call and assert it saw 40).

- [ ] **Step 3: Implement** — in `_compute_keyframe_label_layouts`:
  - Before the loop, snapshot the styles that any keyframe animates: `animated_keys = {(name,key) for kf in seq.keyframes for name,props in kf.styles.items() for key in props}`; `saved_styles = {(n,k): (k in self.geo.element(n).style, self.geo.element(n).style.get(k)) for (n,k) in animated_keys if self.geo.element(n)}`.
  - Add `running_styles = {}` carry-forward. In the per-keyframe loop, after applying values/visibility: `for name, props in kf.styles.items(): running_styles.setdefault(name, {}).update(props)`, then apply: `for name, props in running_styles.items(): elem = self.geo.element(name); [elem.style.__setitem__(k, v) for k, v in props.items() if v is not None and elem]`. (Skip None — leave as-is for pre-pass; revert semantics don't matter for layout measurement.)
  - After the loop (with the existing state restore), also restore styles: for each `(n,k),(had,val) in saved_styles.items()`: set back or delete.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `fix(keyframes): style-aware keyframe label-placement pre-pass`.

---

### Task 4: `reveal_construction()` macro

**Files:** Modify `animageo/keyframes.py` (`build_reveal_keyframes`, manim-free), `animageo/animageo.py` (`reveal_construction`); Test append.

**Interfaces:**
- `keyframes.py`: `build_reveal_keyframes(names_in_order, type_effects, lag=0.3, duration=0.5, default_effect='fade')` → a v2 keyframes dict. kf0 at t=0 = `{visible: {name: False for all}}`; kf1 at t = `(n-1)*lag + duration` = `{visible: {all True}, enter: {name_i: {effect, at: i*lag, duration}}}`. `type_effects` maps a name → effect (per element type); falls back to `default_effect`.
- `animageo.py`: `reveal_construction(self, lag=0.3, duration=0.5, effect=None, play=True)`:
  - Order = current `self.geo.elements` (already dependency/topo-sorted after rebuild); drop axis pseudo-elements (`xAxis`/`yAxis`) and elements with no drawable mobject.
  - Per-type default effect (when `effect is None`): Point→`fade`, Segment/Line/Ray/Vector/Circle/Arc/Conic/Function/ImplicitCurve→`create`, Polygon/CircleSector→`fade`, Angle→`fade`, Text→`write`. If `effect` is given, use it for all.
  - Build keyframes via `build_reveal_keyframes`; if `play`, call `self.play_keyframes(kfs)`; always return the kfs dict.

- [ ] **Step 1: Write failing tests** (append)
```python
class TestBuildRevealKeyframes:
    def test_two_keyframes_hidden_then_staggered(self):
        from animageo.keyframes import build_reveal_keyframes
        kfs = build_reveal_keyframes(
            ['A', 'B', 'M'],
            type_effects={'A': 'fade', 'B': 'fade', 'M': 'create'},
            lag=0.3, duration=0.5)
        assert kfs['version'] == 2
        k0, k1 = kfs['keyframes']
        assert k0['t'] == 0 and k0['visible'] == {'A': False, 'B': False, 'M': False}
        assert k1['visible'] == {'A': True, 'B': True, 'M': True}
        assert k1['enter']['A'] == {'effect': 'fade', 'duration': 0.5, 'at': 0.0}
        assert k1['enter']['B']['at'] == pytest.approx(0.3)
        assert k1['enter']['M'] == {'effect': 'create', 'duration': 0.5, 'at': pytest.approx(0.6)}
        assert k1['t'] == pytest.approx(0.6 + 0.5)

    def test_default_effect_fallback(self):
        from animageo.keyframes import build_reveal_keyframes
        kfs = build_reveal_keyframes(['A'], type_effects={}, default_effect='grow')
        assert kfs['keyframes'][1]['enter']['A']['effect'] == 'grow'


class TestRevealConstructionScene:
    def _scene(self):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        s.geo = _construction()
        s.applyStyle()
        return s

    def test_reveal_returns_valid_v2_keyframes(self):
        s = self._scene()
        kfs = s.reveal_construction(lag=0.2, duration=0.4, play=False)
        assert kfs['version'] == 2
        names = set(kfs['keyframes'][0]['visible'])
        assert 'xAxis' not in names and 'yAxis' not in names
        assert {'A', 'B', 'M'}.issubset(names)
        # per-type: points fade, midpoint (a Point) fade too
        assert kfs['keyframes'][1]['enter']['A']['effect'] == 'fade'

    def test_reveal_parses_through_from_json(self):
        s = self._scene()
        kfs = s.reveal_construction(play=False)
        # must be a valid sequence the player accepts
        seq = KeyframeSequence.from_json(kfs, s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        assert seq.has_visibility_effects()
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** `build_reveal_keyframes` in `keyframes.py`:
```python
def build_reveal_keyframes(names_in_order, type_effects=None, lag=0.3,
                           duration=0.5, default_effect='fade'):
    """Build a 2-keyframe v2 sequence that reveals *names_in_order* one by one,
    staggered by *lag* seconds, each with its per-name effect (from
    *type_effects*, else *default_effect*).
    """
    type_effects = type_effects or {}
    names = list(names_in_order)
    hidden = {n: False for n in names}
    shown = {n: True for n in names}
    enter = {}
    for i, n in enumerate(names):
        enter[n] = {'effect': type_effects.get(n, default_effect),
                    'duration': float(duration), 'at': float(i * lag)}
    total = (len(names) - 1) * lag + duration if names else duration
    return {'version': 2, 'keyframes': [
        {'t': 0, 'visible': hidden},
        {'t': float(total), 'visible': shown, 'enter': enter},
    ]}
```
and `reveal_construction` in `animageo.py`:
```python
    def reveal_construction(self, lag=0.3, duration=0.5, effect=None, play=True):
        """Stage a dependency-ordered, staggered reveal of the whole
        construction (GeoGebra Construction-Protocol style). Returns the
        generated v2 keyframes; plays them when ``play`` is True.
        """
        from .keyframes import build_reveal_keyframes
        from . import geo as _geo
        per_type = {
            _geo.Point: 'fade', _geo.Segment: 'create', _geo.Line: 'create',
            _geo.Ray: 'create', _geo.Vector: 'create', _geo.Circle: 'create',
            _geo.Arc: 'create', _geo.Polygon: 'fade', _geo.CircleSector: 'fade',
            _geo.Angle: 'fade', _geo.Text: 'write',
        }
        names, type_effects = [], {}
        for elem in self.geo.elements:
            if elem.name in ('xAxis', 'yAxis'):
                continue
            if self.CreateMObject(elem) is None:
                continue
            names.append(elem.name)
            if effect is None:
                type_effects[elem.name] = per_type.get(type(elem.data), 'create')
            else:
                type_effects[elem.name] = effect
        kfs = build_reveal_keyframes(names, type_effects, lag=lag,
                                     duration=duration,
                                     default_effect=effect or 'create')
        if play:
            self.play_keyframes(kfs)
        return kfs
```
(Import guard: reference conic/function/implicit types via `_geo` only if exported there; if a type isn't importable, its elements fall to the `'create'` default — safe. Confirm `animageo.geo` re-exports the names used; drop any that aren't and let them default.)

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `feat(keyframes): reveal_construction macro (staggered dependency-order reveal)`.

---

### Task 5: End-to-end smoke render + docs + full suite

- [ ] **Step 1: Smoke render (real manim).** A DSL scene (a few points + a segment + a circle + a Text label if easy) → `self.reveal_construction(lag=0.25, duration=0.5, play=True)`. Remember `self.fitView(w, h)` before revealing (frame the FULL construction while all visible — call fitView, THEN reveal, since reveal hides then shows). Render low-quality MP4; assert colored-pixel count RISES from ~0 (first frame, all hidden) to the full construction (last frame), and that intermediate frames show a monotonic-ish increase (staggered reveal). Also a second render: a `label_text` swap (`styles` animating `M`'s label_text 'P'→'Q') — assert the rendered label text region changes. Report pixel/frame evidence.
- [ ] **Step 2: Fix any bug found (TDD).**
- [ ] **Step 3: Docs.** `CLAUDE.md` (gitignored — controller handles; skip in worktree): note in report the intended block. `AI_USAGE_PROMPT.md` §8.3: add `reveal_construction()` + `label_text`/`write` note. `CHANGELOG.md` `[Unreleased]`: bullets for label_text swap, write effect, style-aware pre-pass, reveal_construction.
- [ ] **Step 4: Full suite** `python3.13 -m pytest tests/ -q` → 0 failures.
- [ ] **Step 5: Commit** `docs+test: keyframes v2 labels, write effect, reveal_construction`.

## Out of scope (later phases)
- `get_element_states`, extended easing set (phase 4)
- `@camera`, per-key easing, text crossfade, `apply_keyframes_at` (phase 5)
- `events` (phase 6)
