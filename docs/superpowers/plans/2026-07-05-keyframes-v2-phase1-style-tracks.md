# Keyframes v2 Phase 1 — Style Tracks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate element style properties (colors, opacities, widths, sizes, discrete props) between keyframes via a new per-keyframe `styles` map in keyframes JSON v2.

**Architecture:** A manim-free registry (`style/animatable.py`) types every animatable `elem.style` key; a manim-free Oklab color module (`style/colorspace.py`) lerps colors; `keyframes.py` parses `version`/`styles` and compiles carry-forward style state into per-interval `StyleInterpolator` lists via `bind_style_tracks(get_element, resolve)` (resolver injected — keyframes.py stays dependency-free); `animageo.py` binds tracks before playback, writes interpolated values into `elem.style` inside the existing sentinel-updater frame loop (`updateGeoElements`/`become` path), and pins exact end values / null-reverts in a finalize step after each interval.

**Tech Stack:** Python 3.10+, numpy, pytest. No new dependencies. `keyframes.py`, `style/animatable.py`, `style/colorspace.py` must stay **manim-free** (existing convention, see `apply_parsed_value` docstring).

**Spec:** `docs/superpowers/specs/2026-07-05-keyframes-v2-design.md` (§5.2–§5.4, §7 phase 1, §8 decisions).

## Global Constraints

- v1 keyframe JSON (no `"version"` key) must play **byte-identical** to today — the only new observable is a `DeprecationWarning`.
- `styles` requires `"version": 2`; versions other than 1/2 → `ValueError`.
- Default color interpolation space is **Oklab**; `rendering.color_interpolation: "srgb"` in style JSON is the escape hatch (§8 decision 2).
- Discrete keys snap to the END value when **eased** progress ≥ 0.5 (CSS rule, same as existing `bool` interpolator).
- `null` style value = revert to the element's **pre-animation** state: interpolate toward the baseline (resolved value at sequence start), then restore the original `elem.style` entry (or delete the key if there was none).
- `label_text` is NOT in the phase-1 registry (phase 3). Unknown keys → `ValueError`.
- Work on a feature branch off `dev` (e.g. `feature/keyframes-v2-style-tracks`).
- Commits: conventional style (`feat(keyframes): …`). **No AI-attribution trailers** (no `Co-Authored-By: Claude`, no `Claude-Session:` — hard project rule).
- Run tests with `python3 -m pytest` from the repo root `/Users/mac/Documents/_My_code/animageo`.

## File Structure

| File | Responsibility |
|---|---|
| Create `animageo/style/colorspace.py` | hex normalization, sRGB↔Oklab conversion, `lerp_color` |
| Create `animageo/style/animatable.py` | `ANIMATABLE_STYLE_KEYS` registry, `style_kind`, `validate_style_value`, `normalize_style_value` |
| Modify `animageo/keyframes.py` | `Keyframe.styles`, `version` parsing + DeprecationWarning, `StyleInterpolator`, `KeyframeSequence.bind_style_tracks` |
| Modify `animageo/animageo.py` | playback wiring: bind, kf0 styles, `_apply_style_interps`, `_finalize_style_interval`, style-only intervals, z-index carry after `become` |
| Create `tests/test_colorspace.py` | color module unit tests |
| Create `tests/test_keyframe_styles.py` | registry, parsing, interpolator, bind, scene wiring tests |
| Modify `CLAUDE.md`, `animageo/AI_USAGE_PROMPT.md`, `CHANGELOG.md` | document v2 `styles` (folded into final task) |

---

### Task 1: Color module (`style/colorspace.py`)

**Files:**
- Create: `animageo/style/colorspace.py`
- Test: `tests/test_colorspace.py`

**Interfaces:**
- Consumes: nothing (pure module; stdlib + math only — do NOT import manim or numpy here, it's called per frame per color and plain floats are faster for scalars).
- Produces:
  - `normalize_hex(value: str) -> str` — `'#1565C0'`/`'#abc'` → lowercase `'#rrggbb'`; raises `ValueError` on anything else (non-str, missing `#`, wrong length, bad hex digits).
  - `hex_to_oklab(hex_color: str) -> tuple[float, float, float]`
  - `oklab_to_hex(L: float, a: float, b: float) -> str` (channels clamped to [0, 1])
  - `lerp_color(c1: str, c2: str, t: float, space: str = 'oklab') -> str` — accepts any `normalize_hex`-able inputs; `space` in `('oklab', 'srgb')`, else `ValueError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_colorspace.py`:

```python
"""Unit tests for animageo.style.colorspace (manim-free color math)."""

import pytest

from animageo.style.colorspace import (
    normalize_hex, hex_to_oklab, oklab_to_hex, lerp_color,
)


class TestNormalizeHex:
    def test_lowercases_long_form(self):
        assert normalize_hex('#1565C0') == '#1565c0'

    def test_expands_short_form(self):
        assert normalize_hex('#abc') == '#aabbcc'

    @pytest.mark.parametrize('bad', [
        '1565c0', '#12345', '#gggggg', '#12345678', 42, None, 'red',
    ])
    def test_rejects_non_hex(self, bad):
        with pytest.raises(ValueError):
            normalize_hex(bad)


class TestOklabRoundTrip:
    @pytest.mark.parametrize('color', [
        '#000000', '#ffffff', '#ff0000', '#00ff00', '#0000ff',
        '#1565c0', '#d05456', '#808080', '#f6e0db',
    ])
    def test_round_trip_within_one_step(self, color):
        L, a, b = hex_to_oklab(color)
        back = oklab_to_hex(L, a, b)
        # allow ±1 per 8-bit channel for float→int rounding
        for i in (1, 3, 5):
            orig = int(color[i:i + 2], 16)
            got = int(back[i:i + 2], 16)
            assert abs(orig - got) <= 1

    def test_white_has_L_one(self):
        L, a, b = hex_to_oklab('#ffffff')
        assert L == pytest.approx(1.0, abs=1e-3)
        assert a == pytest.approx(0.0, abs=1e-3)
        assert b == pytest.approx(0.0, abs=1e-3)

    def test_black_has_L_zero(self):
        L, _a, _b = hex_to_oklab('#000000')
        assert L == pytest.approx(0.0, abs=1e-3)


class TestLerpColor:
    def test_endpoints_exact(self):
        assert lerp_color('#1565c0', '#d05456', 0.0) == '#1565c0'
        assert lerp_color('#1565c0', '#d05456', 1.0) == '#d05456'

    def test_normalizes_inputs(self):
        assert lerp_color('#ABC', '#abc', 0.0) == '#aabbcc'

    def test_oklab_midpoint_gray_between_black_and_white(self):
        mid = lerp_color('#000000', '#ffffff', 0.5, space='oklab')
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert abs(r - g) <= 1 and abs(g - b) <= 1   # achromatic
        # Oklab midpoint is perceptual middle gray: L=0.5 → sRGB ≈ 0x77;
        # sRGB-space lerp would give exactly 0x80 minus rounding.
        assert 0x60 <= r <= 0x90

    def test_srgb_space_naive_midpoint(self):
        mid = lerp_color('#000000', '#ffffff', 0.5, space='srgb')
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert (r, g, b) == (0x80, 0x80, 0x80) or (r, g, b) == (0x7f, 0x7f, 0x7f)

    def test_unknown_space_raises(self):
        with pytest.raises(ValueError):
            lerp_color('#000000', '#ffffff', 0.5, space='hsl')

    def test_result_is_valid_hex(self):
        mid = lerp_color('#1565c0', '#d05456', 0.3)
        assert normalize_hex(mid) == mid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_colorspace.py -q`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'animageo.style.colorspace'`

- [ ] **Step 3: Implement the module**

Create `animageo/style/colorspace.py`:

```python
"""Color conversion and interpolation for keyframe style tracks.

Manim-free by design (used by keyframes.py, which must not import manim).
Implements sRGB ↔ Oklab (Björn Ottosson's reference matrices,
https://bottosson.github.io/posts/oklab/). Keyframe color lerp defaults to
Oklab: perceptually even midpoints, no gray dead zone or hue detours that
naive sRGB-space lerp produces (CSS Color 4 makes the same default).
"""

COLOR_SPACES = ('oklab', 'srgb')


def normalize_hex(value):
    """Normalize a hex color to lowercase '#rrggbb'. Raise ValueError otherwise."""
    if not isinstance(value, str) or not value.startswith('#'):
        raise ValueError(
            f"style colors must be hex strings like '#1565c0', got {value!r}"
        )
    digits = value[1:].lower()
    if len(digits) == 3:
        digits = ''.join(ch * 2 for ch in digits)
    if len(digits) != 6 or any(ch not in '0123456789abcdef' for ch in digits):
        raise ValueError(
            f"style colors must be hex strings like '#1565c0', got {value!r}"
        )
    return '#' + digits


def _hex_to_rgb01(hex_color):
    h = normalize_hex(hex_color)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def _rgb01_to_hex(r, g, b):
    def _clamp8(c):
        return max(0, min(255, round(c * 255)))
    return '#{:02x}{:02x}{:02x}'.format(_clamp8(r), _clamp8(g), _clamp8(b))


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c):
    c = max(0.0, c)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklab(hex_color):
    """'#rrggbb' -> (L, a, b) in Oklab."""
    r, g, b = (_srgb_to_linear(c) for c in _hex_to_rgb01(hex_color))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_hex(L, a, b):
    """(L, a, b) in Oklab -> '#rrggbb' (channels clamped to gamut)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b2 = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return _rgb01_to_hex(*(min(1.0, max(0.0, _linear_to_srgb(c)))
                           for c in (r, g, b2)))


def lerp_color(c1, c2, t, space='oklab'):
    """Interpolate two '#rrggbb' colors at t in [0, 1] in the given space."""
    if space not in COLOR_SPACES:
        raise ValueError(f"unknown color space {space!r}; expected one of {COLOR_SPACES}")
    c1n, c2n = normalize_hex(c1), normalize_hex(c2)
    if t <= 0.0:
        return c1n
    if t >= 1.0:
        return c2n
    if space == 'srgb':
        r1, g1, b1 = _hex_to_rgb01(c1n)
        r2, g2, b2 = _hex_to_rgb01(c2n)
        return _rgb01_to_hex(
            (1 - t) * r1 + t * r2, (1 - t) * g1 + t * g2, (1 - t) * b1 + t * b2,
        )
    L1, a1, b1 = hex_to_oklab(c1n)
    L2, a2, b2 = hex_to_oklab(c2n)
    return oklab_to_hex(
        (1 - t) * L1 + t * L2, (1 - t) * a1 + t * a2, (1 - t) * b1 + t * b2,
    )
```

Note: `l ** (1/3)` is safe because linear-sRGB inputs are ≥ 0 after `_srgb_to_linear`; `oklab_to_hex` cubes (sign-preserving) so no domain issues there either.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_colorspace.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/style/colorspace.py tests/test_colorspace.py
git commit -m "feat(style): add manim-free Oklab/sRGB color lerp for keyframe tracks"
```

---

### Task 2: Animatable-keys registry (`style/animatable.py`)

**Files:**
- Create: `animageo/style/animatable.py`
- Test: `tests/test_keyframe_styles.py` (new file, first test class)

**Interfaces:**
- Consumes: `normalize_hex` from `animageo.style.colorspace`.
- Produces (used by Tasks 3–6):
  - `SCALAR = 'scalar'`, `COLOR = 'color'`, `DISCRETE = 'discrete'`, `OFFSET2 = 'offset2'`, `DASH = 'dash'` (module constants)
  - `ANIMATABLE_STYLE_KEYS: dict[str, str]` — key → kind
  - `style_kind(key: str) -> str` — raises `ValueError` for unknown keys, message lists valid keys
  - `validate_style_value(key: str, value) -> None` — raises `ValueError` on kind mismatch; `None` is valid for every key (revert-to-base)
  - `normalize_style_value(key: str, value)` — returns canonical value (colors → `normalize_hex`, scalar/dash numbers → `float`, offset2 → `[float, float]`, discrete → unchanged, `None` → `None`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_keyframe_styles.py` with:

```python
"""Keyframes v2 style tracks: registry, parsing, interpolators, binding, wiring."""

import numpy as np
import pytest

from animageo.style.animatable import (
    ANIMATABLE_STYLE_KEYS, SCALAR, COLOR, DISCRETE, OFFSET2, DASH,
    style_kind, validate_style_value, normalize_style_value,
)


class TestAnimatableRegistry:
    @pytest.mark.parametrize('key,kind', [
        ('stroke_opacity', SCALAR), ('fill_opacity', SCALAR),
        ('stroke_width_px', SCALAR), ('size_px', SCALAR),
        ('font_size_px', SCALAR), ('arc_size_px', SCALAR),
        ('stroke', COLOR), ('fill', COLOR), ('label_color', COLOR),
        ('label_offset_px', OFFSET2),
        ('point_shape', DISCRETE), ('label_anchor', DISCRETE),
        ('label_visible', DISCRETE), ('tick_count', DISCRETE),
        ('z_index', DISCRETE),
        ('stroke_dash_ratio', DASH),
    ])
    def test_kinds(self, key, kind):
        assert ANIMATABLE_STYLE_KEYS[key] == kind
        assert style_kind(key) == kind

    def test_label_text_not_animatable_in_phase1(self):
        assert 'label_text' not in ANIMATABLE_STYLE_KEYS
        with pytest.raises(ValueError, match='label_text'):
            style_kind('label_text')

    def test_unknown_key_error_lists_valid_keys(self):
        with pytest.raises(ValueError, match='stroke_width_px'):
            style_kind('thickness')


class TestValidateAndNormalize:
    def test_none_valid_for_every_key(self):
        for key in ANIMATABLE_STYLE_KEYS:
            validate_style_value(key, None)          # no raise
            assert normalize_style_value(key, None) is None

    def test_scalar_accepts_number_rejects_str(self):
        validate_style_value('stroke_width_px', 2)
        assert normalize_style_value('stroke_width_px', 2) == 2.0
        with pytest.raises(ValueError):
            validate_style_value('stroke_width_px', 'fat')

    def test_color_normalized_and_validated(self):
        assert normalize_style_value('stroke', '#ABC') == '#aabbcc'
        with pytest.raises(ValueError):
            validate_style_value('fill', 'red')

    def test_offset2_shape(self):
        assert normalize_style_value('label_offset_px', [3, -4]) == [3.0, -4.0]
        with pytest.raises(ValueError):
            validate_style_value('label_offset_px', [1, 2, 3])
        with pytest.raises(ValueError):
            validate_style_value('label_offset_px', 5)

    def test_dash_accepts_number(self):
        assert normalize_style_value('stroke_dash_ratio', 0.65) == 0.65
        with pytest.raises(ValueError):
            validate_style_value('stroke_dash_ratio', 'dashed')

    def test_bool_is_valid_scalar_for_discrete(self):
        validate_style_value('label_visible', True)
        assert normalize_style_value('label_visible', True) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: ERROR with `ModuleNotFoundError: No module named 'animageo.style.animatable'`

- [ ] **Step 3: Implement the module**

Create `animageo/style/animatable.py`:

```python
"""Registry of animatable ``elem.style`` keys for keyframes v2 style tracks.

One source of truth for which style keys keyframe ``styles`` maps may
mention and how each interpolates. Manim-free by design.

Kinds:
- ``scalar``  — float lerp (pixel sizes, opacities)
- ``color``   — hex color, lerped in Oklab (or sRGB) via style.colorspace
- ``offset2`` — [x, y] float pair, component lerp
- ``discrete``— snap to end value at eased progress >= 0.5 (CSS rule)
- ``dash``    — stroke_dash_ratio: number<->number lerps, None<->number snaps

``label_text`` is deliberately NOT here (phase 3: swap semantics + label
placement interplay).
"""

from .colorspace import normalize_hex

SCALAR = 'scalar'
COLOR = 'color'
DISCRETE = 'discrete'
OFFSET2 = 'offset2'
DASH = 'dash'

ANIMATABLE_STYLE_KEYS = {
    # continuous scalars (pixel units / 0..1 opacities)
    'stroke_opacity': SCALAR,
    'fill_opacity': SCALAR,
    'stroke_width_px': SCALAR,
    'size_px': SCALAR,
    'font_size_px': SCALAR,
    'arc_size_px': SCALAR,
    'arc_shift_px': SCALAR,
    'right_angle_size_px': SCALAR,
    'tick_length_px': SCALAR,
    'tick_width_px': SCALAR,
    'tick_shift_px': SCALAR,
    'arrow_length_px': SCALAR,
    'arrow_width_px': SCALAR,
    'label_radial_offset_px': SCALAR,
    # colors
    'stroke': COLOR,
    'fill': COLOR,
    'label_color': COLOR,
    # 2-component pixel offsets
    'label_offset_px': OFFSET2,
    # discrete (snap at eased 0.5)
    'point_shape': DISCRETE,
    'stroke_linecap': DISCRETE,
    'tick_count': DISCRETE,
    'tick_style': DISCRETE,
    'angle_range': DISCRETE,
    'right_angle_marker': DISCRETE,
    'label_anchor': DISCRETE,
    'label_visible': DISCRETE,
    'label_mode': DISCRETE,
    'z_index': DISCRETE,
    'z_index_fill': DISCRETE,
    # semi-discrete
    'stroke_dash_ratio': DASH,
}


def style_kind(key):
    """Return the interpolation kind for *key*; ValueError for unknown keys."""
    try:
        return ANIMATABLE_STYLE_KEYS[key]
    except KeyError:
        raise ValueError(
            f"'{key}' is not an animatable style key. "
            f"Animatable keys: {sorted(ANIMATABLE_STYLE_KEYS)}"
        ) from None


def _require_number(key, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"style key '{key}' expects a number, got {value!r}")


def validate_style_value(key, value):
    """Raise ValueError if *value* does not fit *key*'s kind. None always passes."""
    kind = style_kind(key)
    if value is None:
        return
    if kind in (SCALAR, DASH):
        _require_number(key, value)
    elif kind == COLOR:
        normalize_hex(value)   # raises with a helpful message
    elif kind == OFFSET2:
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       for v in value)):
            raise ValueError(
                f"style key '{key}' expects [x, y] numbers, got {value!r}"
            )
    # DISCRETE: any JSON scalar is acceptable as-is


def normalize_style_value(key, value):
    """Validate and return the canonical form of *value* for *key*."""
    validate_style_value(key, value)
    if value is None:
        return None
    kind = style_kind(key)
    if kind in (SCALAR, DASH):
        return float(value)
    if kind == COLOR:
        return normalize_hex(value)
    if kind == OFFSET2:
        return [float(value[0]), float(value[1])]
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/style/animatable.py tests/test_keyframe_styles.py
git commit -m "feat(style): registry of animatable style keys with interpolation kinds"
```

---

### Task 3: v2 parsing — `version`, `Keyframe.styles`, DeprecationWarning

**Files:**
- Modify: `animageo/keyframes.py` (imports ~line 25; `Keyframe` class ~line 159; `KeyframeSequence.__init__` ~line 198; `from_json` ~line 245)
- Test: `tests/test_keyframe_styles.py` (append)

**Interfaces:**
- Consumes: `normalize_style_value` from Task 2.
- Produces:
  - `Keyframe(t, values=None, show=None, hide=None, easing_name='smooth', styles=None)` with `.styles: dict[str, dict[str, Any]]` (normalized values) — slot added.
  - `KeyframeSequence(keyframes, intervals, element_info, version=1)` with `.version: int`.
  - `KeyframeSequence.from_json` accepts `"version"` (default 1); warns `DeprecationWarning` for v1; parses/validates per-keyframe `"styles"` (requires v2).
  - `KeyframeSequence.has_style_tracks() -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframe_styles.py`:

```python
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import Keyframe, KeyframeSequence


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes):
    return {'version': 2, 'keyframes': keyframes}


class TestV2Parsing:
    def test_v1_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'values': {'A': [0, 0]}},
                {'t': 1, 'values': {'A': [1, 1]}},
            ]}, _construction())

    def test_v2_no_warning_and_version_stored(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error', DeprecationWarning)
            seq = KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'A': [0, 0]}},
                {'t': 1, 'values': {'A': [1, 1]}},
            ]), _construction())
        assert seq.version == 2

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'version': 3, 'keyframes': [
                {'t': 0}, {'t': 1},
            ]}, _construction())

    def test_styles_require_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
                {'t': 1},
            ]}, _construction())

    def test_styles_parsed_and_normalized(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#FF0000', 'size_px': 8}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), _construction())
        assert seq.keyframes[0].styles == {
            'A': {'stroke': '#ff0000', 'size_px': 8.0}}
        assert seq.keyframes[1].styles == {'A': {'stroke': None}}
        assert seq.has_style_tracks() is True

    def test_no_styles_has_no_tracks(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},
        ]), _construction())
        assert seq.has_style_tracks() is False

    def test_styles_unknown_element_raises(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'GHOST': {'stroke': '#ff0000'}}},
                {'t': 1},
            ]), _construction())

    def test_styles_target_dependent_element_allowed(self):
        # styles may target ANY element, not only independents
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'fill_opacity': 0.2}}},
            {'t': 1, 'styles': {'M': {'fill_opacity': 1.0}}},
        ]), _construction())
        assert seq.keyframes[1].styles['M']['fill_opacity'] == 1.0

    def test_styles_unknown_key_raises(self):
        with pytest.raises(ValueError, match='animatable'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': {'thickness': 3}}},
                {'t': 1},
            ]), _construction())

    def test_styles_bad_value_raises(self):
        with pytest.raises(ValueError, match='hex'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': {'stroke': 'red'}}},
                {'t': 1},
            ]), _construction())

    def test_styles_non_dict_raises(self):
        with pytest.raises(ValueError, match='object'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': '#ff0000'}},
                {'t': 1},
            ]), _construction())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_keyframe_styles.py::TestV2Parsing -q`
Expected: FAIL (`pytest.warns` gets no warning; `styles` silently ignored; `seq.version` AttributeError)

- [ ] **Step 3: Implement parsing**

In `animageo/keyframes.py`:

3a. Add imports (top of file, after `import numpy as np`):

```python
import warnings

from .style.animatable import normalize_style_value, style_kind
from .style.colorspace import lerp_color
```

(`style_kind`/`lerp_color` are consumed by Tasks 4–5; importing now keeps one import block.)

3b. `Keyframe` — add the slot and parameter:

```python
class Keyframe:
    """A single keyframe at time t."""
    __slots__ = ('t', 'values', 'show', 'hide', 'easing_name', 'styles')

    def __init__(self, t, values=None, show=None, hide=None, easing_name='smooth',
                 styles=None):
        self.t = float(t)
        self.values = values or {}     # name -> value (raw from JSON)
        self.show = show or []
        self.hide = hide or []
        self.easing_name = easing_name
        self.styles = styles or {}     # name -> {style_key -> normalized value}
```

3c. `KeyframeSequence.__init__` — add `version`:

```python
    def __init__(self, keyframes, intervals, element_info, version=1):
        self.keyframes = keyframes           # List[Keyframe]
        self.intervals = intervals           # List[KeyframeInterval]
        self.element_info = element_info     # dict from get_independents()
        self.version = version
        self.label_layouts = None            # Optional[list[dict[name, LabelPlacement]]]

    def has_style_tracks(self):
        """True if any keyframe carries a ``styles`` map."""
        return any(kf.styles for kf in self.keyframes)
```

3d. `from_json` — after `raw_keyframes` check, add version handling:

```python
        version = data.get('version', 1)
        if version not in (1, 2):
            raise ValueError(
                f"Unsupported keyframes JSON version {version!r}; expected 1 or 2"
            )
        if version == 1:
            warnings.warn(
                "keyframes JSON without '\"version\": 2' uses the deprecated v1 "
                "schema. Add '\"version\": 2' to opt into the v2 schema "
                "(per-keyframe 'styles'; future v2 visibility/timing semantics).",
                DeprecationWarning, stacklevel=2,
            )
```

3e. Inside the keyframe loop (after `easing` validation, before `keyframes.append`), parse styles:

```python
            raw_styles = kf_data.get('styles', {})
            if raw_styles and version < 2:
                raise ValueError(
                    f"Keyframe {i}: 'styles' requires '\"version\": 2'"
                )
            styles = {}
            for ename, props in raw_styles.items():
                if construction.element(ename) is None:
                    raise ValueError(
                        f"Keyframe {i}: styles target '{ename}' not found in construction"
                    )
                if not isinstance(props, dict):
                    raise ValueError(
                        f"Keyframe {i}: styles['{ename}'] must be an object "
                        f"{{style_key: value}}, got {props!r}"
                    )
                try:
                    styles[ename] = {
                        key: normalize_style_value(key, value)
                        for key, value in props.items()
                    }
                except ValueError as e:
                    raise ValueError(f"Keyframe {i}: styles['{ename}']: {e}") from None
```

and extend the `keyframes.append(Keyframe(...))` call with `styles=styles`.

3f. Extend the final construction: `return cls(keyframes, intervals, element_info, version=version)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Check no regression in existing keyframe tests**

Run: `python3 -m pytest tests/test_keyframes.py tests/test_keyframe_labels.py tests/test_keyframe_initial_state.py -q`
Expected: all PASS (DeprecationWarnings appear in the warnings summary — that is fine; no filterwarnings config turns them into errors)

- [ ] **Step 6: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframe_styles.py
git commit -m "feat(keyframes): v2 schema — version field, per-keyframe styles, v1 deprecation"
```

---

### Task 4: `StyleInterpolator`

**Files:**
- Modify: `animageo/keyframes.py` (add class after `LabelOffsetInterpolator`, ~line 133)
- Test: `tests/test_keyframe_styles.py` (append)

**Interfaces:**
- Consumes: `lerp_color` (imported in Task 3), `EASING_FUNCTIONS`.
- Produces: `StyleInterpolator(name, key, kind, start, end, easing=None, color_space='oklab')` with `.at(t)` — same shape as `Interpolator.at` (eases internally, `t` is raw interval progress 0..1).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframe_styles.py`:

```python
from animageo.keyframes import StyleInterpolator, EASING_FUNCTIONS


class TestStyleInterpolator:
    def test_scalar_lerp_linear(self):
        si = StyleInterpolator('a', 'stroke_width_px', 'scalar', 1.0, 3.0,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.0) == 1.0
        assert si.at(0.5) == 2.0
        assert si.at(1.0) == 3.0

    def test_scalar_respects_easing(self):
        si = StyleInterpolator('a', 'stroke_width_px', 'scalar', 0.0, 1.0,
                               easing=EASING_FUNCTIONS['in'])   # t^2
        assert si.at(0.5) == pytest.approx(0.25)

    def test_color_endpoints_and_midpoint(self):
        si = StyleInterpolator('a', 'stroke', 'color', '#000000', '#ffffff',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.0) == '#000000'
        assert si.at(1.0) == '#ffffff'
        mid = si.at(0.5)
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert abs(r - g) <= 1 and abs(g - b) <= 1

    def test_color_space_srgb(self):
        si = StyleInterpolator('a', 'stroke', 'color', '#000000', '#ffffff',
                               easing=EASING_FUNCTIONS['linear'],
                               color_space='srgb')
        mid = si.at(0.5)
        assert int(mid[1:3], 16) in (0x7f, 0x80)

    def test_offset2_component_lerp(self):
        si = StyleInterpolator('a', 'label_offset_px', 'offset2',
                               [0.0, 10.0], [10.0, -10.0],
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.5) == [5.0, 0.0]

    def test_discrete_snaps_at_eased_half(self):
        si = StyleInterpolator('a', 'point_shape', 'discrete',
                               'circle', 'square',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.49) == 'circle'
        assert si.at(0.5) == 'square'

    def test_discrete_snap_uses_eased_progress(self):
        # easing 'in' = t^2: eased 0.5 is reached at t = sqrt(0.5) ≈ 0.707
        si = StyleInterpolator('a', 'point_shape', 'discrete',
                               'circle', 'square',
                               easing=EASING_FUNCTIONS['in'])
        assert si.at(0.6) == 'circle'
        assert si.at(0.75) == 'square'

    def test_dash_numeric_lerps(self):
        si = StyleInterpolator('a', 'stroke_dash_ratio', 'dash', 0.2, 0.8,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.5) == pytest.approx(0.5)

    def test_dash_with_none_snaps(self):
        si = StyleInterpolator('a', 'stroke_dash_ratio', 'dash', None, 0.65,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.4) is None
        assert si.at(0.6) == 0.65
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_keyframe_styles.py::TestStyleInterpolator -q`
Expected: ERROR with `ImportError: cannot import name 'StyleInterpolator'`

- [ ] **Step 3: Implement the class**

Add to `animageo/keyframes.py` after `LabelOffsetInterpolator`:

```python
class StyleInterpolator:
    """Interpolates one ``elem.style`` key between two keyframes.

    Kind semantics (see ``style/animatable.py``): 'scalar' lerps floats,
    'color' lerps hex colors in ``color_space`` (Oklab default), 'offset2'
    lerps [x, y] pairs, 'dash' lerps when both endpoints are numbers and
    snaps otherwise, 'discrete' snaps to the end value at eased progress
    >= 0.5 (the CSS discrete rule — same convention as the 'bool'
    Interpolator kind).
    """

    __slots__ = ('name', 'key', 'kind', 'start', 'end', 'easing', 'color_space')

    def __init__(self, name, key, kind, start, end, easing=None,
                 color_space='oklab'):
        self.name = name
        self.key = key
        self.kind = kind
        self.start = start
        self.end = end
        self.easing = easing or _ease_smooth
        self.color_space = color_space

    def at(self, t):
        """Return the interpolated value at progress t in [0, 1]."""
        et = self.easing(t)

        if self.kind == 'scalar':
            return (1 - et) * self.start + et * self.end

        if self.kind == 'color':
            return lerp_color(self.start, self.end, et, space=self.color_space)

        if self.kind == 'offset2':
            return [
                (1 - et) * self.start[0] + et * self.end[0],
                (1 - et) * self.start[1] + et * self.end[1],
            ]

        if self.kind == 'dash':
            if (isinstance(self.start, (int, float))
                    and isinstance(self.end, (int, float))):
                return (1 - et) * self.start + et * self.end
            return self.end if et >= 0.5 else self.start

        # 'discrete' — snap at eased half
        return self.end if et >= 0.5 else self.start
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframe_styles.py
git commit -m "feat(keyframes): StyleInterpolator for scalar/color/offset/discrete/dash kinds"
```

---

### Task 5: `bind_style_tracks` — compile styles into per-interval tracks

**Files:**
- Modify: `animageo/keyframes.py` (`KeyframeInterval` slots/init ~line 171; new method on `KeyframeSequence`)
- Test: `tests/test_keyframe_styles.py` (append)

**Interfaces:**
- Consumes: `StyleInterpolator`, `style_kind`, `EASING_FUNCTIONS`, `Keyframe.styles`.
- Produces:
  - `KeyframeInterval.style_interps: list[StyleInterpolator]` and `KeyframeInterval.style_finalizers: list[tuple]` (both `[]` by default) where a finalizer is `('set', name, key, value)` or `('revert', name, key, had_explicit, explicit_val)`.
  - `KeyframeSequence.bind_style_tracks(get_element, resolve, color_space='oklab')` — `get_element: name -> elem|None`, `resolve: (elem, key) -> value|None`. **Must be called before the first keyframe's styles are applied** (captures pre-animation baselines). Re-binding overwrites previous tracks.

Semantics (from spec §5.2/§5.4 + review decisions):
- Carry-forward: a track for `(name, key)` interpolates inside the interval that ENDS at the keyframe mentioning it; unmentioned intervals hold.
- Keyframe-0 styles are the initial state (applied instantly by the scene, Task 6); they seed the tracked `current` value.
- Baseline for each `(name, key)` = `resolve(elem, key)` captured lazily at bind time, plus `(key in elem.style, elem.style.get(key))` for the revert finalizer.
- `null` target: interpolate `current -> baseline`, then finalizer `('revert', ...)` restores the original `elem.style` entry (or deletes the key). Non-null targets get `('set', ...)` to pin the exact end value.
- If either interpolation endpoint is `None` (e.g. baseline resolves to `None`), the track snaps (kind forced to `'discrete'`) — you cannot lerp from nothing.
- Unknown element at bind time → `logger.warning`, track skipped (mirrors `values` behavior).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframe_styles.py`:

```python
class _StubElem:
    def __init__(self, style=None):
        self.style = dict(style or {})


def _bind(seq, elements, resolved):
    """Bind with stub elements and a fake resolver.

    ``elements``: dict name -> _StubElem; ``resolved``: dict (name, key) -> value.
    """
    return seq.bind_style_tracks(
        get_element=elements.get,
        resolve=lambda elem, key: resolved.get(
            (next(n for n, e in elements.items() if e is elem), key)),
    )


class TestBindStyleTracks:
    def _seq(self, kfs):
        return KeyframeSequence.from_json(_v2(kfs), _construction())

    def test_track_from_baseline_to_target(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke_width_px': 4}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'stroke_width_px'): 1.5})
        (si,) = seq.intervals[0].style_interps
        assert (si.name, si.key, si.kind) == ('A', 'stroke_width_px', 'scalar')
        assert si.start == 1.5 and si.end == 4.0
        assert seq.intervals[0].style_finalizers == [
            ('set', 'A', 'stroke_width_px', 4.0)]

    def test_kf0_styles_seed_current_value(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#000000'}}},
            {'t': 1, 'styles': {'A': {'stroke': '#ffffff'}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'stroke'): '#123456'})
        (si,) = seq.intervals[0].style_interps
        assert si.start == '#000000'      # kf0 value, not the resolved baseline
        assert si.end == '#ffffff'

    def test_hold_between_mentions(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'fill_opacity': 0.2}}},
            {'t': 2},
            {'t': 3, 'styles': {'A': {'fill_opacity': 1.0}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'fill_opacity'): 1.0})
        assert len(seq.intervals[0].style_interps) == 1     # 1.0 -> 0.2
        assert seq.intervals[1].style_interps == []          # hold
        (si2,) = seq.intervals[2].style_interps               # 0.2 -> 1.0
        assert si2.start == 0.2 and si2.end == 1.0

    def test_equal_values_skip_interp_but_pin_finalizer(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 6}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'size_px'): 6.0})
        assert seq.intervals[0].style_interps == []
        assert seq.intervals[0].style_finalizers == [('set', 'A', 'size_px', 6.0)]

    def test_null_reverts_to_baseline_with_explicit_restore(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ])
        # element had an explicit GGB/DSL stroke before the animation
        elements = {'A': _StubElem({'stroke': '#1565c0'})}
        _bind(seq, elements, {('A', 'stroke'): '#1565c0'})
        (si,) = seq.intervals[0].style_interps
        assert si.start == '#ff0000' and si.end == '#1565c0'
        assert seq.intervals[0].style_finalizers == [
            ('revert', 'A', 'stroke', True, '#1565c0')]

    def test_null_revert_without_explicit_entry(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ])
        elements = {'A': _StubElem()}      # no explicit stroke; resolver default
        _bind(seq, elements, {('A', 'stroke'): '#000000'})
        (si,) = seq.intervals[0].style_interps
        assert si.end == '#000000'
        assert seq.intervals[0].style_finalizers == [
            ('revert', 'A', 'stroke', False, None)]

    def test_none_baseline_forces_snap(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke_dash_ratio': 0.65}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {})            # resolver knows nothing -> None
        (si,) = seq.intervals[0].style_interps
        assert si.start is None and si.end == 0.65
        assert si.at(0.4) is None and si.at(0.6) == 0.65

    def test_missing_element_skipped_with_warning(self, caplog):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 9}}},
        ])
        import logging
        with caplog.at_level(logging.WARNING, logger='animageo.keyframes'):
            _bind(seq, {}, {})
        assert seq.intervals[0].style_interps == []
        assert any('A' in r.message for r in caplog.records)

    def test_easing_taken_from_interval(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 12}}, 'easing': 'linear'},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'size_px'): 6.0})
        (si,) = seq.intervals[0].style_interps
        assert si.at(0.5) == pytest.approx(9.0)   # linear, not smooth
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_keyframe_styles.py::TestBindStyleTracks -q`
Expected: FAIL with `AttributeError: ... no attribute 'bind_style_tracks'`

- [ ] **Step 3: Implement**

3a. `KeyframeInterval` — extend slots and init:

```python
    __slots__ = ('start_t', 'end_t', 'duration', 'interpolators',
                 'show', 'hide', 'label_interps', 'dynamic_angle_params',
                 'easing_name', 'style_interps', 'style_finalizers')
```

and at the end of `__init__`:

```python
        self.style_interps = []          # list[StyleInterpolator]
        self.style_finalizers = []       # ('set', name, key, value) | ('revert', name, key, had_explicit, explicit_val)
```

3b. Add method to `KeyframeSequence` (after `attach_label_layouts`):

```python
    def bind_style_tracks(self, get_element, resolve, color_space='oklab'):
        """Compile per-keyframe ``styles`` into per-interval style tracks.

        Args:
            get_element: callable ``name -> Element | None``.
            resolve: callable ``(elem, key) -> current resolved value | None``
                (the scene passes the style resolver; keyframes.py stays
                manim-free by taking it as an injected function).
            color_space: 'oklab' | 'srgb' for color lerp.

        MUST be called before the first keyframe's styles are applied:
        baselines (revert targets and lazy track starts) are captured from
        the pre-animation state. Re-binding replaces previous tracks.
        """
        baseline = {}   # (name, key) -> resolved value at sequence start
        restore = {}    # (name, key) -> (had_explicit, explicit_val)
        current = {}    # (name, key) -> tracked value along the timeline

        def _ensure_baseline(name, key):
            k = (name, key)
            if k in baseline:
                return True
            elem = get_element(name)
            if elem is None:
                logger.warning(
                    "bind_style_tracks: element '%s' not found — skipping "
                    "style track '%s'", name, key,
                )
                return False
            baseline[k] = resolve(elem, key)
            restore[k] = (key in elem.style, elem.style.get(key))
            return True

        # Keyframe 0 styles are applied instantly before playback
        # (_apply_keyframe_state); here they only seed the tracked value.
        for name, props in self.keyframes[0].styles.items():
            for key, value in props.items():
                if not _ensure_baseline(name, key):
                    continue
                if value is not None:
                    current[(name, key)] = value

        for i, interval in enumerate(self.intervals):
            kf_next = self.keyframes[i + 1]
            easing_fn = EASING_FUNCTIONS[interval.easing_name]
            interval.style_interps = []
            interval.style_finalizers = []

            for name, props in kf_next.styles.items():
                for key, value in props.items():
                    if not _ensure_baseline(name, key):
                        continue
                    k = (name, key)
                    start = current.get(k, baseline[k])
                    end = baseline[k] if value is None else value
                    had_explicit, explicit_val = restore[k]

                    if value is None:
                        interval.style_finalizers.append(
                            ('revert', name, key, had_explicit, explicit_val))
                    else:
                        interval.style_finalizers.append(
                            ('set', name, key, end))

                    if start != end:
                        kind = style_kind(key)
                        if start is None or end is None:
                            kind = 'discrete'   # cannot lerp from/to nothing
                        interval.style_interps.append(StyleInterpolator(
                            name=name, key=key, kind=kind,
                            start=start, end=end, easing=easing_fn,
                            color_space=color_space,
                        ))
                    current[k] = end
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframe_styles.py
git commit -m "feat(keyframes): bind_style_tracks — carry-forward style state into interval tracks"
```

---

### Task 6: Scene wiring — playback of style tracks

**Files:**
- Modify: `animageo/animageo.py`:
  - `play_keyframes` (~line 1491): bind tracks; finalize after each interval; style-only intervals run the updater
  - `_apply_keyframe_state` (~line 1361): apply kf0 styles
  - `_play_keyframe_interval.on_frame` (~line 1571): apply style interps
  - new methods `_apply_style_interps`, `_finalize_style_interval`
- Test: `tests/test_keyframe_styles.py` (append)

**Interfaces:**
- Consumes: `KeyframeSequence.has_style_tracks/bind_style_tracks`, `interval.style_interps/style_finalizers`, `_resolve_style` (already imported in animageo.py line 28), `self.style.rendering` dict.
- Produces:
  - `AnimaGeoScene._apply_style_interps(interval, t) -> set[str]` — writes interpolated values into `elem.style`, returns touched names.
  - `AnimaGeoScene._finalize_style_interval(interval)` — applies finalizers + one `updateGeoElements`.
  - `play_keyframes` reads `self.style.rendering.get('color_interpolation', 'oklab')`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframe_styles.py`:

```python
from animageo.animageo import AnimaGeoScene


def _scene():
    scene = AnimaGeoScene()
    c = scene.geo
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return scene


class TestSceneStyleWiring:
    def test_apply_keyframe_state_writes_kf0_styles(self):
        scene = _scene()
        updated = []
        scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#FF0000', 'size_px': 9}}},
            {'t': 1, 'styles': {'A': {'stroke': '#00ff00'}}},
        ]), scene.geo)
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        elem = scene.geo.element('A')
        assert elem.style['stroke'] == '#ff0000'
        assert elem.style['size_px'] == 9.0
        assert updated and 'A' in updated[-1]

    def test_apply_style_interps_writes_and_reports_touched(self):
        scene = _scene()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke_width_px': 1}}},
            {'t': 1, 'styles': {'A': {'stroke_width_px': 5}}, 'easing': 'linear'},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda elem, key: elem.style.get(key),
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        touched = scene._apply_style_interps(seq.intervals[0], 0.5)
        assert touched == {'A'}
        assert scene.geo.element('A').style['stroke_width_px'] == pytest.approx(3.0)

    def test_finalize_pins_exact_end_value(self):
        scene = _scene()
        updated = []
        scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'fill_opacity': 0.0}}},
            {'t': 1, 'styles': {'A': {'fill_opacity': 0.75}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda elem, key: elem.style.get(key),
        )
        scene._finalize_style_interval(seq.intervals[0])
        assert scene.geo.element('A').style['fill_opacity'] == 0.75
        assert updated and 'A' in updated[-1]

    def test_finalize_revert_restores_explicit_entry(self):
        scene = _scene()
        scene.updateGeoElements = lambda updates=None: None
        elem = scene.geo.element('A')
        elem.style['stroke'] = '#1565c0'          # pre-animation explicit value
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda e, key: e.style.get(key),
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        assert elem.style['stroke'] == '#ff0000'
        scene._finalize_style_interval(seq.intervals[0])
        assert elem.style['stroke'] == '#1565c0'

    def test_finalize_revert_deletes_key_when_no_explicit_entry(self):
        scene = _scene()
        scene.updateGeoElements = lambda updates=None: None
        elem = scene.geo.element('A')
        assert 'stroke' not in elem.style
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda e, key: e.style.get(key) or '#000000',
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        scene._finalize_style_interval(seq.intervals[0])
        assert 'stroke' not in elem.style

    def test_color_space_read_from_rendering_config(self):
        scene = _scene()
        scene.style.rendering['color_interpolation'] = 'srgb'
        assert scene.style.rendering.get('color_interpolation', 'oklab') == 'srgb'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_keyframe_styles.py::TestSceneStyleWiring -q`
Expected: FAIL — kf0 styles ignored (`'stroke' not in elem.style`), `AttributeError` for `_apply_style_interps` / `_finalize_style_interval`

- [ ] **Step 3: Implement scene wiring**

3a. `_apply_keyframe_state` — after the `kf.values` loop (after line 1398 `touched.add(name)` block) and before the `kf.show` loop, add:

```python
        for name, props in kf.styles.items():
            elem = self.geo.element(name)
            if elem is None:
                logger.warning(
                    "play_keyframes: skipping styles for '%s' — element not found",
                    name,
                )
                continue
            for key, value in props.items():
                if value is None:
                    continue   # null at keyframe 0 has nothing to revert
                elem.style[key] = value
            touched.add(name)
```

3b. New methods (place after `_play_keyframe_interval`):

```python
    def _apply_style_interps(self, interval, t):
        """Write interpolated style-track values for *interval* at progress t.

        Returns the set of touched element names (callers merge it into the
        ``updateGeoElements`` updates dict).
        """
        touched = set()
        for si in interval.style_interps:
            elem = self.geo.element(si.name)
            if elem is None:
                continue
            elem.style[si.key] = si.at(t)
            touched.add(si.name)
        return touched

    def _finalize_style_interval(self, interval):
        """Pin exact end-of-interval style values and run null-reverts.

        'set' writes the exact target value (deterministic end state even if
        the last updater frame landed slightly before t=1); 'revert' restores
        the element's pre-animation ``elem.style`` entry, deleting the key if
        there was none (the resolver then falls back to overlay/defaults —
        visually identical to the interpolated baseline target).
        """
        touched = set()
        for fin in interval.style_finalizers:
            op, name, key = fin[0], fin[1], fin[2]
            elem = self.geo.element(name)
            if elem is None:
                continue
            if op == 'set':
                elem.style[key] = fin[3]
            else:   # 'revert'
                had_explicit, explicit_val = fin[3], fin[4]
                if had_explicit:
                    elem.style[key] = explicit_val
                elif key in elem.style:
                    del elem.style[key]
            touched.add(name)
        if touched:
            self.updateGeoElements(touched)
```

3c. `play_keyframes` — bind tracks right after `seq` is resolved (before the `cfg = ...` line):

```python
        if seq.has_style_tracks():
            color_space = self.style.rendering.get('color_interpolation', 'oklab')
            seq.bind_style_tracks(
                get_element=self.geo.element,
                resolve=lambda elem, key: _resolve_style(self, elem, key, default=None),
                color_space=color_space,
            )
```

3d. `play_keyframes` — the interval loop: include style tracks in the has-work check and finalize on both branches. Replace:

```python
                has_labels = bool(interval.label_interps) or bool(interval.dynamic_angle_params)
                if not interval.interpolators and not has_labels:
                    if interval.duration > 0:
                        self.wait(interval.duration)
                    continue

                self._play_keyframe_interval(interval)
```

with:

```python
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

3e. `_play_keyframe_interval.on_frame` — after the `updates = geo_ref.rebuild()` / `touched` merge block (right before the label-offsets comment), add:

```python
            for name in scene_ref._apply_style_interps(interval, t):
                updates[name] = updates.get(name, True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Regression run for the keyframe subsystem**

Run: `python3 -m pytest tests/test_keyframes.py tests/test_keyframe_labels.py tests/test_keyframe_initial_state.py tests/test_dynamic_tracker.py -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add animageo/animageo.py tests/test_keyframe_styles.py
git commit -m "feat(keyframes): play style tracks through the per-frame become pipeline"
```

---

### Task 7: z-index carry through `become`

`Mobject.become()` copies points and draw style but not `z_index`, so a `z_index` style track (discrete snap) would silently not apply on the become path of `updateGeoElements`. Copy z-indices from the freshly rendered mobject after `become`.

**Files:**
- Modify: `animageo/animageo.py` (`updateGeoElements`, ~line 395)
- Test: `tests/test_keyframe_styles.py` (append)

**Interfaces:**
- Consumes: `updateGeoElements` become branch (line 395-396: `if not needRemove and not needAdd: mobj.become(mobj_new)`).
- Produces: after `become`, every family member's `z_index` matches the freshly rendered mobject.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_keyframe_styles.py`:

```python
class TestZIndexCarry:
    def test_z_index_style_change_propagates_through_become(self):
        # z_index lives on family members (the dot inside the VGroup), not on
        # the group itself — compare whole families, not the top-level attr.
        scene = _scene()
        elem = scene.geo.element('A')
        elem.visible = True
        scene.addGeoElement(elem)
        mobj = scene.mobject('A')
        assert mobj is not None
        z_family_before = sorted(m.z_index for m in mobj.get_family())

        elem.style['z_index'] = 99
        scene.updateGeoElements(['A'])

        mobj_after = scene.mobject('A')
        assert mobj_after is mobj          # become path, not remove/add
        z_expected = sorted(
            m.z_index for m in scene.CreateMObject(elem).get_family())
        assert z_expected != z_family_before   # the style change is real
        assert sorted(m.z_index for m in mobj_after.get_family()) == z_expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_keyframe_styles.py::TestZIndexCarry -q`
Expected: FAIL on the final assert (the family still carries the pre-change z indices). If it unexpectedly PASSES, the installed manim version already carries z_index through `become` — then keep the test, skip step 3, and note it in the commit message.

- [ ] **Step 3: Implement**

In `updateGeoElements`, replace:

```python
            if not needRemove and not needAdd:
                mobj.become(mobj_new)
```

with:

```python
            if not needRemove and not needAdd:
                mobj.become(mobj_new)
                # become() copies points/draw style but not z_index — carry it
                # so z_index style changes (incl. keyframe tracks) take effect.
                for sub_old, sub_new in zip(mobj.get_family(), mobj_new.get_family()):
                    sub_old.z_index = sub_new.z_index
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyframe_styles.py -q`
Expected: all PASS

- [ ] **Step 5: Broad regression (become path is shared by everything)**

Run: `python3 -m pytest tests/ -q -x --ignore=tests/test_tikz_export.py`
Expected: all PASS (tikz export excluded only for speed; run it if it was touched — it wasn't)

- [ ] **Step 6: Commit**

```bash
git add animageo/animageo.py tests/test_keyframe_styles.py
git commit -m "fix(scene): carry z_index through become in updateGeoElements"
```

---

### Task 8: Documentation + full-suite verification

**Files:**
- Modify: `CLAUDE.md` (section "Keyframe Animation System")
- Modify: `animageo/AI_USAGE_PROMPT.md` (§8.3 "Keyframe animation (JSON-driven)")
- Modify: `CHANGELOG.md` (Unreleased/next-version section, matching existing entry style)

**Interfaces:**
- Consumes: everything above (documents the shipped behavior).
- Produces: docs in sync with code (project rule: AI_USAGE_PROMPT.md must track scene-API changes).

- [ ] **Step 1: Update CLAUDE.md**

In the "Keyframe Animation System" section, after the v1 JSON format block, add:

```markdown
**Keyframes v2 — style tracks** (`"version": 2`): each keyframe may carry a
`styles` map — target style state to reach by time `t`, carry-forward like
`values`, interpolated across the interval that ends at the mentioning
keyframe. Interpolation kind per key comes from
`style/animatable.py::ANIMATABLE_STYLE_KEYS`: scalars lerp, colors lerp in
Oklab (`rendering.color_interpolation: "srgb"` to opt out,
`style/colorspace.py`), `label_offset_px` lerps componentwise, discrete keys
(point_shape, label_anchor, tick_count, z_index, …) snap at eased progress
≥ 0.5, `stroke_dash_ratio` lerps number↔number and snaps via None. `null`
value = animate back to the pre-animation baseline, then restore the
original `elem.style` entry (or delete the key). Styles may target ANY
element (not only independents). v1 JSON (no `version`) plays byte-identical
but emits a DeprecationWarning. Playback: `KeyframeSequence.bind_style_tracks`
(resolver injected — keyframes.py stays manim-free) → per-frame writes into
`elem.style` inside the sentinel updater → `_finalize_style_interval` pins
exact end values / runs reverts after each interval.

```json
{"version": 2, "keyframes": [
  {"t": 0, "styles": {"a": {"stroke": "#1565c0"}}},
  {"t": 2, "styles": {"a": {"stroke": "#d05456", "stroke_width_px": 4}},
   "easing": "smooth"},
  {"t": 4, "styles": {"a": {"stroke": null}}}
]}
```
```

- [ ] **Step 2: Update AI_USAGE_PROMPT.md §8.3**

Add after the existing keyframe example (keep the section's voice/format):

```markdown
Style tracks (v2): add `"version": 2` and per-keyframe `"styles"` to animate
element styles between keyframes — colors (`stroke`/`fill`/`label_color`,
hex only), opacities, `stroke_width_px`, `size_px`, `font_size_px`, arc/tick
sizes, `label_offset_px`, and discrete props (`point_shape`, `label_anchor`,
`label_visible`, `tick_count`, `z_index`, `stroke_dash_ratio`). Values are
the target state at that keyframe (carry-forward); `null` reverts to the
element's pre-animation style. Styles may target any element by name, not
just independents. Discrete props switch at the middle of the transition;
colors blend perceptually (Oklab). `label_text` is not animatable yet.

```python
self.play_keyframes({"version": 2, "keyframes": [
    {"t": 0, "values": {"x": 0},  "styles": {"c1": {"fill_opacity": 0.0}}},
    {"t": 2, "values": {"x": 90}, "styles": {"c1": {"fill_opacity": 0.6,
                                                    "stroke": "#d05456"}}},
    {"t": 3, "styles": {"c1": {"stroke": null}}},
]})
```
```

- [ ] **Step 3: Update CHANGELOG.md**

Add an entry under the unreleased/next-version heading (match the file's existing bullet style; **no AI attribution**):

```markdown
- Keyframes v2 (`"version": 2`): per-keyframe `styles` maps animate element
  styles between keyframes — colors (Oklab-interpolated; `rendering.
  color_interpolation: "srgb"` opt-out), opacities, pixel sizes,
  `label_offset_px`, discrete props (snap at mid-transition), `null` = revert
  to pre-animation style. Styles may target any element. v1 keyframe JSON
  still plays byte-identical but is deprecated (DeprecationWarning).
- `updateGeoElements` now carries `z_index` through `become()` so z-order
  changes take effect without a remove/add cycle.
```

- [ ] **Step 4: Full test suite**

Run: `python3 -m pytest tests/ -q`
Expected: all PASS (count grows by the new test files; no failures, no errors)

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md animageo/AI_USAGE_PROMPT.md CHANGELOG.md
git commit -m "docs: document keyframes v2 style tracks (CLAUDE.md, AI guide, changelog)"
```

---

## Out of scope for this plan (later phases, per spec §7)

- `visible` maps, enter/exit effects, exact-duration timing (phase 2)
- `label_text` swap, style-aware label-placement pre-pass, `write` (phase 3)
- `get_element_states()`, extended easing set (phase 4); web-side integration lives in animageo_web
- `@camera` (phase 5); `events` (last, after everything — review decision)
- Keyframe-snapshot label layouts (`keyframe_snapshots`) intentionally ignore `styles` in phase 1 (documented spec §5.4 p.5 / phase 3)
