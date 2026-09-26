"""Registry of animatable ``elem.style`` keys for keyframes v2 style tracks.

One source of truth for which style keys keyframe ``styles`` maps may
mention and how each interpolates. Manim-free by design.

Kinds:
- ``scalar``  — float lerp (pixel sizes, opacities)
- ``color``   — hex color, lerped in Oklab (or sRGB) via style.colorspace
- ``offset2`` — [x, y] float pair, component lerp
- ``discrete``— snap to end value at eased progress >= 0.5 (CSS rule)
- ``dash``    — stroke_dash_ratio: number<->number lerps, None<->number snaps
- ``text``    — label_text: never lerped, snaps to end value at eased
                progress >= 0.5 (same swap rule as discrete)
"""

from .colorspace import normalize_hex

SCALAR = 'scalar'
COLOR = 'color'
DISCRETE = 'discrete'
OFFSET2 = 'offset2'
DASH = 'dash'
TEXT = 'text'

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
    'stroke_dash_period_px': SCALAR,
    # colors
    'stroke': COLOR,
    'fill': COLOR,
    'label_color': COLOR,
    # 2-component pixel offsets
    'label_offset_px': OFFSET2,
    # text (swap semantics, never lerped)
    'label_text': TEXT,
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
    # DISCRETE, TEXT: any value is acceptable as-is


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
    if kind == TEXT:
        return str(value)
    return value
