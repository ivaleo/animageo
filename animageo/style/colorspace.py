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


def is_hex_color(value):
    """True iff *value* is a hex color string normalize_hex accepts."""
    try:
        normalize_hex(value)
        return True
    except (ValueError, TypeError):
        return False


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
