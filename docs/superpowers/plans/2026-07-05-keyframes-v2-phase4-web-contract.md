# Keyframes v2 Phase 4 — Core Web Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Give the web layer a lossless contract: (1) extend the core easing set from 5 to the web's full 17 (byte-for-byte formulas), and (2) add `get_element_states()` — a per-element snapshot of visibility + resolved animatable style values (symmetric to `get_independent_elements()`) for the web's keyframe-state inspector and diffs.

**Architecture:** Easing lives in `keyframes.py` (`EASING_FUNCTIONS`, manim-free). `get_element_states()` is a scene method in `animageo.py` reading the style resolver. Web-side integration (converter, TS types, UI) is OUT of scope — this only ships the core contract.

**Tech Stack:** Python 3.10+, numpy, pytest. `keyframes.py` stays manim-free.

**Spec:** `docs/superpowers/specs/2026-07-05-keyframes-v2-design.md` §7 phase 4. Depends on phases 1-3 (on `dev`).

## Global Constraints

- The 5 existing easings (`linear`, `smooth`, `in`, `out`, `in_out`) must keep their exact current formulas (v1/v2 keyframes rely on them). Only ADD the 12 new ones.
- New easing formulas must match `animageo_web`'s `applyEasingValue` (frontend/src/types/timeline.ts) exactly, so the same `easing` name renders identically in the web preview and the exported video.
- All easing functions take `t ∈ [0,1]` and clamp; return a float.
- `get_element_states()` must not mutate anything; it reads resolved style via `resolver.resolve`.
- `keyframes.py` stays manim-free. Branch `feat/keyframes-v2-phase4`. Conventional commits. **NO AI-attribution trailers.** Test with `python3.13 -m pytest`.

## File Structure

| File | Responsibility |
|---|---|
| Modify `animageo/keyframes.py` | 12 new easing functions + `EASING_FUNCTIONS` entries |
| Modify `animageo/animageo.py` | `get_element_states()` |
| Test `tests/test_keyframe_easing.py` (new) | all 17 names resolve; key formula values; monotonic where expected |
| Test `tests/test_element_states.py` (new) | per-element state shape, resolved style, visibility |
| Modify `CLAUDE.md`, `AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document (final task) |

---

### Task 1: Extend the easing set to the web's 17

**Files:** Modify `animageo/keyframes.py`; Test `tests/test_keyframe_easing.py` (new).

**Interfaces:** `EASING_FUNCTIONS` dict gains 12 keys: `smootherstep`, `ease_in_sine`, `ease_out_sine`, `ease_in_out_sine`, `ease_in_cubic`, `ease_out_cubic`, `ease_in_out_cubic`, `rush_into`, `rush_from`, `ease_out_back`, `ease_out_elastic`, `ease_out_bounce`. Each is `f(t: float) -> float`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyframe_easing.py`:

```python
"""Keyframes v2 phase 4: the full 17-easing set (lossless with animageo_web)."""
import math
import pytest

from animageo.keyframes import EASING_FUNCTIONS

ALL_17 = [
    'linear', 'smooth', 'smootherstep', 'in', 'out', 'in_out',
    'ease_in_sine', 'ease_out_sine', 'ease_in_out_sine',
    'ease_in_cubic', 'ease_out_cubic', 'ease_in_out_cubic',
    'rush_into', 'rush_from', 'ease_out_back', 'ease_out_elastic',
    'ease_out_bounce',
]


class TestEasingSet:
    def test_all_17_present(self):
        for name in ALL_17:
            assert name in EASING_FUNCTIONS, name
        assert len(EASING_FUNCTIONS) >= 17

    @pytest.mark.parametrize('name', ALL_17)
    def test_endpoints(self, name):
        f = EASING_FUNCTIONS[name]
        # every easing maps 0->0 and 1->1 (endpoints), within tolerance
        assert abs(f(0.0) - 0.0) < 1e-9, name
        assert abs(f(1.0) - 1.0) < 1e-9, name

    def test_existing_five_unchanged(self):
        assert EASING_FUNCTIONS['linear'](0.3) == pytest.approx(0.3)
        assert EASING_FUNCTIONS['smooth'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['in'](0.5) == pytest.approx(0.25)
        assert EASING_FUNCTIONS['out'](0.5) == pytest.approx(0.75)
        assert EASING_FUNCTIONS['in_out'](0.25) == pytest.approx(0.125)

    def test_web_formula_values(self):
        # exact values matching animageo_web applyEasingValue
        assert EASING_FUNCTIONS['smootherstep'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['ease_in_sine'](0.5) == pytest.approx(1 - math.cos(math.pi/4))
        assert EASING_FUNCTIONS['ease_out_sine'](0.5) == pytest.approx(math.sin(math.pi/4))
        assert EASING_FUNCTIONS['ease_in_out_sine'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['ease_in_cubic'](0.5) == pytest.approx(0.125)
        assert EASING_FUNCTIONS['ease_out_cubic'](0.5) == pytest.approx(1 - 0.5**3)
        assert EASING_FUNCTIONS['ease_in_out_cubic'](0.25) == pytest.approx(4 * 0.25**3)

    def test_overshoot_easings(self):
        # back/elastic overshoot above 1 or below 0 somewhere in (0,1)
        back = EASING_FUNCTIONS['ease_out_back']
        assert max(back(t/100) for t in range(101)) > 1.0
        elastic = EASING_FUNCTIONS['ease_out_elastic']
        assert elastic(0.0) == pytest.approx(0.0)
        assert elastic(1.0) == pytest.approx(1.0)

    def test_bounce_stays_in_unit_and_ends_one(self):
        f = EASING_FUNCTIONS['ease_out_bounce']
        for i in range(101):
            v = f(i/100)
            assert -1e-9 <= v <= 1.0 + 1e-9
        assert f(1.0) == pytest.approx(1.0)

    def test_clamps_out_of_range(self):
        for name in ALL_17:
            f = EASING_FUNCTIONS[name]
            # t outside [0,1] must be clamped (no exception, sane output)
            f(-0.5); f(1.5)

    def test_rush_endpoints(self):
        assert EASING_FUNCTIONS['rush_into'](0.0) == pytest.approx(0.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_into'](1.0) == pytest.approx(1.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_from'](0.0) == pytest.approx(0.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_from'](1.0) == pytest.approx(1.0, abs=1e-6)
```

- [ ] **Step 2: Run to verify fail** → `python3.13 -m pytest tests/test_keyframe_easing.py -q` (KeyError on new names).

- [ ] **Step 3: Implement** — in `animageo/keyframes.py`, after the existing easing functions and BEFORE `EASING_FUNCTIONS`, add (formulas ported verbatim from `animageo_web`'s `applyEasingValue`):

```python
import math


def _clamp01(t):
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def _ease_smootherstep(t):
    t = _clamp01(t)
    return 6 * t**5 - 15 * t**4 + 10 * t**3


def _ease_in_sine(t):
    t = _clamp01(t)
    return 1 - math.cos((t * math.pi) / 2)


def _ease_out_sine(t):
    t = _clamp01(t)
    return math.sin((t * math.pi) / 2)


def _ease_in_out_sine(t):
    t = _clamp01(t)
    return -(math.cos(math.pi * t) - 1) / 2


def _ease_in_cubic(t):
    t = _clamp01(t)
    return t * t * t


def _ease_out_cubic(t):
    t = _clamp01(t)
    return 1 - (1 - t) ** 3


def _ease_in_out_cubic(t):
    t = _clamp01(t)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _manim_smooth_sigmoid(t, inflection=10.0):
    # animageo_web manimSmooth (sigmoid) — used by rush_into/rush_from
    error = 1 / (1 + math.exp(inflection / 2))
    return max(0.0, min(1.0, (
        1 / (1 + math.exp(-inflection * (t - 0.5))) - error
    ) / (1 - 2 * error)))


def _ease_rush_into(t):
    t = _clamp01(t)
    return 2 * _manim_smooth_sigmoid(t / 2)


def _ease_rush_from(t):
    t = _clamp01(t)
    return 2 * _manim_smooth_sigmoid(t / 2 + 0.5) - 1


def _ease_out_back(t):
    t = _clamp01(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _ease_out_elastic(t):
    t = _clamp01(t)
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def _ease_out_bounce(t):
    t = _clamp01(t)
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375
```

Then extend the `EASING_FUNCTIONS` dict with the 12 new entries:
```python
    'smootherstep': _ease_smootherstep,
    'ease_in_sine': _ease_in_sine,
    'ease_out_sine': _ease_out_sine,
    'ease_in_out_sine': _ease_in_out_sine,
    'ease_in_cubic': _ease_in_cubic,
    'ease_out_cubic': _ease_out_cubic,
    'ease_in_out_cubic': _ease_in_out_cubic,
    'rush_into': _ease_rush_into,
    'rush_from': _ease_rush_from,
    'ease_out_back': _ease_out_back,
    'ease_out_elastic': _ease_out_elastic,
    'ease_out_bounce': _ease_out_bounce,
```

Note: `ease_out_back`'s endpoint `f(1.0)` should be exactly 1.0 (the `(t-1)` terms vanish). `f(0.0)` = `1 + c3*(-1)³ + c1*(-1)² = 1 - c3 + c1 = 1 - (c1+1) + c1 = 0`. Good — endpoints hold. `ease_out_bounce` uses the expanded `(t - k)² ` form (rewritten as `t -= k; n1*t*t + c`) — equivalent to the web's `(t - k)**2`.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Regression** `python3.13 -m pytest tests/test_keyframes.py -q` (existing easing behavior intact).
- [ ] **Step 6: Commit** `feat(keyframes): full 17-easing set (lossless with web applyEasingValue)`.

---

### Task 2: `get_element_states()`

**Files:** Modify `animageo/animageo.py`; Test `tests/test_element_states.py` (new).

**Interface:** `AnimaGeoScene.get_element_states() -> dict[name, {type, visible, style}]` — for every non-axis element: `type` = element data class name, `visible` = `self._element_visible(elem)`, `style` = a dict of the resolved values for every key in `ANIMATABLE_STYLE_KEYS` that resolves to a non-None value. Symmetric to `get_independent_elements()`; the web uses it to populate a "state at keyframe" inspector and to diff keyframes.

- [ ] **Step 1: Write failing tests**

Create `tests/test_element_states.py`:

```python
"""get_element_states(): per-element visibility + resolved animatable styles."""
from animageo.animageo import AnimaGeoScene
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.style.animatable import ANIMATABLE_STYLE_KEYS


def _scene():
    s = AnimaGeoScene()
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    s.geo = c
    s.applyStyle()
    return s


class TestElementStates:
    def test_returns_all_non_axis_elements(self):
        s = _scene()
        st = s.get_element_states()
        assert {'A', 'B', 'M'}.issubset(st)
        assert 'xAxis' not in st and 'yAxis' not in st

    def test_state_shape(self):
        s = _scene()
        st = s.get_element_states()['A']
        assert st['type'] == 'Point'
        assert st['visible'] in (True, False)
        assert isinstance(st['style'], dict)

    def test_style_keys_are_animatable(self):
        s = _scene()
        st = s.get_element_states()['A']
        for key in st['style']:
            assert key in ANIMATABLE_STYLE_KEYS

    def test_reflects_visibility(self):
        s = _scene()
        s.geo.element('M').visible = False
        assert s.get_element_states()['M']['visible'] is False

    def test_reflects_explicit_style(self):
        s = _scene()
        s.geo.element('A').style['stroke'] = '#123456'
        assert s.get_element_states()['A']['style'].get('stroke') == '#123456'

    def test_no_mutation(self):
        s = _scene()
        before = {e.name: dict(e.style) for e in s.geo.elements}
        s.get_element_states()
        after = {e.name: dict(e.style) for e in s.geo.elements}
        assert before == after
```

- [ ] **Step 2: Run to verify fail** (AttributeError `get_element_states`).

- [ ] **Step 3: Implement** — in `animageo/animageo.py` (near `get_independent_elements`):

```python
    def get_element_states(self):
        """Per-element snapshot for the web keyframe-state inspector: every
        non-axis element's type, current visibility, and resolved animatable
        style values (the keys in ``ANIMATABLE_STYLE_KEYS``). Symmetric to
        ``get_independent_elements()``; read-only.
        """
        from .style.animatable import ANIMATABLE_STYLE_KEYS
        states = {}
        for elem in self.geo.elements:
            if elem.name in ('xAxis', 'yAxis'):
                continue
            style = {}
            for key in ANIMATABLE_STYLE_KEYS:
                val = _resolve_style(self, elem, key, default=None)
                if val is not None:
                    style[key] = val
            states[elem.name] = {
                'type': type(elem.data).__name__,
                'visible': self._element_visible(elem),
                'style': style,
            }
        return states
```

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `feat(scene): get_element_states for web keyframe-state inspector`.

---

### Task 3: Docs + full suite

**Files:** Modify `animageo/AI_USAGE_PROMPT.md`, `CHANGELOG.md` (CLAUDE.md handled by controller — skip in worktree); full suite.

- [ ] **Step 1: `AI_USAGE_PROMPT.md` §8.3** — note the full easing set is available (list a few: `ease_out_bounce`, `ease_out_elastic`, `ease_out_back`, `rush_into`, sine/cubic variants) and `get_element_states()` for reading per-element visibility + style.
- [ ] **Step 2: `CHANGELOG.md` `[Unreleased]`** — bullets: 17-easing set (lossless with web), `get_element_states()`.
- [ ] **Step 3: Full suite** `python3.13 -m pytest tests/ -q` → 0 failures.
- [ ] **Step 4: Commit** `docs: keyframes v2 phase 4 — full easing set + get_element_states`.

## Out of scope (later phases)
- `@camera`, per-key easing, text crossfade, `apply_keyframes_at` (phase 5)
- `events` (phase 6)
- Web-side integration (converter/TS/UI) — lives in animageo_web
