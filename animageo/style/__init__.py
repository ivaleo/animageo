"""GeoStyle — visual style configuration for AnimaGeo rendering.

Manages geometry rendering parameters: colors, line widths, dot sizes,
angle marks, arrow tips, fonts. Loads configuration from JSON style files.
"""
import json
import logging
from dataclasses import dataclass
import numpy as np

from .schema import validate_style_json
from .config import BUILTIN_STYLE_PATH, deep_merge, resolve_preset_ref

try:
    from manim import config as manim_config, ManimColor, WHITE, BLACK
except ModuleNotFoundError:
    class _FallbackManimConfig:
        pixel_width = 1920
        pixel_height = 1080

    class ManimColor:
        _NAMED = {
            'white': (1.0, 1.0, 1.0),
            'black': (0.0, 0.0, 0.0),
            'red': (1.0, 0.0, 0.0),
            'green': (0.0, 1.0, 0.0),
            'blue': (0.0, 0.0, 1.0),
        }

        def __init__(self, color, opacity=None):
            self.color = color
            self.opacity = opacity

        def _rgb(self):
            color = self.color
            if isinstance(color, str):
                color = color.strip()
                if color.startswith('#') and len(color) in (4, 7):
                    if len(color) == 4:
                        vals = [int(ch * 2, 16) for ch in color[1:]]
                    else:
                        vals = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
                    return tuple(v / 255 for v in vals)
                lowered = color.lower()
                if lowered in self._NAMED:
                    return self._NAMED[lowered]
                raise ValueError(f"unsupported fallback color: {color!r}")
            vals = list(color)
            if len(vals) < 3:
                raise ValueError("color sequence must have at least 3 channels")
            return tuple(float(v) for v in vals[:3])

        def to_rgb(self):
            return self._rgb()

        def to_rgba(self):
            rgb = self._rgb()
            alpha = 1.0 if self.opacity is None else float(self.opacity)
            return (*rgb, alpha)

    manim_config = _FallbackManimConfig()
    WHITE = '#ffffff'
    BLACK = '#000000'

logger = logging.getLogger(__name__)


# ── Utility functions ──────────────────────────────────────────────────

def isnan(x):
    """Check if x is not a valid number (None, non-numeric string, etc.)."""
    if isinstance(x, (int, float)): return False
    if x is None: return True
    try:
        float(x)
        return False
    except (ValueError, TypeError):
        return True


def rgba(arr):
    """Convert a color specification to RGBA array. Accepts hex string, [r,g,b], [r,g,b,a]."""
    if isinstance(arr, str): arr = arr.split(' ')

    try:
        if len(arr) == 1:
            return ManimColor(arr[0]).to_rgb()
        elif len(arr) == 2:
            if arr[1] is None: return ManimColor(arr[0]).to_rgb()
            else: return ManimColor(arr[0], arr[1]).to_rgba()
        elif len(arr) == 3:
            return ManimColor(arr).to_rgb()
        elif len(arr) == 4:
            return ManimColor(arr).to_rgba()
    except Exception:
        return None
    return None


def equal(arr1, arr2, eps=None):
    """Compare two arrays element-wise, optionally with epsilon tolerance."""
    if len(arr1) != len(arr2): return False
    if eps is None:
        return all(arr1[i] == arr2[i] for i in range(len(arr1)))
    return all(np.abs(arr1[i] - arr2[i]) <= eps for i in range(len(arr1)))


@dataclass(frozen=True)
class ImportColorTarget:
    """Normalized target for an ``import.colors`` mapping."""

    color: str
    opacity: float | None = None


def _split_color_opacity(value):
    """Return ``(color, opacity, has_opacity)`` for import color specs."""
    if isinstance(value, str):
        parts = value.split()
        if len(parts) >= 2:
            try:
                return parts[0], float(parts[1]), True
            except (TypeError, ValueError):
                return parts[0], None, False
        return value, None, False

    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], str):
            if value[1] is None:
                return value[0], None, False
            try:
                return value[0], float(value[1]), True
            except (TypeError, ValueError):
                return value[0], None, False
        if len(value) == 4:
            try:
                return list(value[:3]), float(value[3]), True
            except (TypeError, ValueError):
                return list(value[:3]), None, False

    return value, None, False


def _rgb_to_hex(rgb):
    vals = []
    for channel in rgb[:3]:
        value = float(channel)
        if value <= 1:
            value *= 255
        vals.append(max(0, min(255, int(round(value)))))
    return '#{:02x}{:02x}{:02x}'.format(*vals)


def _color_to_hex(value):
    if isinstance(value, str):
        color = value.strip()
        if color.startswith('#'):
            digits = color[1:]
            if len(digits) == 3:
                return '#' + ''.join(ch * 2 for ch in digits).lower()
            if len(digits) == 6:
                return '#' + digits.lower()

    rgb_value = rgba(value)
    if rgb_value is None or len(rgb_value) < 3:
        return None
    return _rgb_to_hex(rgb_value[:3])


def _normalize_import_color_target(value):
    color, opacity, has_opacity = _split_color_opacity(value)
    color_hex = _color_to_hex(color)
    if color_hex is None:
        return None
    return ImportColorTarget(color=color_hex, opacity=opacity if has_opacity else None)


def _import_color_matches(source_rgba, key, eps):
    key_rgba = rgba(key)
    if key_rgba is None:
        return False
    _, _, key_has_opacity = _split_color_opacity(key)
    if key_has_opacity:
        return equal(source_rgba, key_rgba, eps)
    return len(source_rgba) >= 3 and len(key_rgba) >= 3 and equal(source_rgba[:3], key_rgba[:3], eps)


def getColorFromDict(color_dict, col, eps=0.01):
    """Look up an import color mapping and return ``ImportColorTarget``.

    The returned color is always canonical ``#rrggbb``. Opacity is set only
    when it was explicit in the target mapping, so callers can preserve the
    element's current opacity for color-only mappings.
    """
    col = rgba(col)
    if col is None: return None
    keys = list(color_dict)
    keys.sort(key=lambda key: 0 if _split_color_opacity(key)[2] else 1)
    for key in keys:
        if _import_color_matches(col, key, eps):
            return _normalize_import_color_target(color_dict[key])
    return None


def updateMin(minX, x):
    if isnan(minX): return x
    if isnan(x): return minX
    return min(minX, x)


def updateMax(maxX, x):
    if isnan(maxX): return x
    if isnan(x): return maxX
    return max(maxX, x)


def hasParam(d, key):
    if key not in d: return False
    if not d[key]: return False
    return True


def _resolve_color_ref(value, colors):
    """Resolve color preset references in fully-qualified, short or bare form."""
    if not isinstance(value, str):
        return None
    color = resolve_preset_ref(value, {'color': colors}, fallback=None)
    if color is not None:
        return color
    return colors.get(value)


def _resolve_color_value(value, colors, fallback=None):
    color = _resolve_color_ref(value, colors)
    return fallback if color is None else color


def _is_concrete_color(value) -> bool:
    """True iff ``value`` is a usable literal colour, not a style ref or blank.

    Style-token refs (``"presets.color.background"`` / ``"color.background"``)
    and empty/absent values are NOT concrete — they signal "no explicit colour".
    """
    if not isinstance(value, str) or value == '':
        return False
    return not (value.startswith('presets.') or value.startswith('color.'))


def _resolve_group_ref(value, group_name, group_presets):
    """Resolve group preset refs for import maps.

    Accepts ``presets.<group>.name``, ``<group>.name`` and, because the import
    map already supplies the group context, bare ``name``.
    """
    if not isinstance(value, str):
        return value
    resolved = resolve_preset_ref(value, {group_name: group_presets}, fallback=None)
    if resolved is not None:
        return resolved
    return group_presets[value] if value in group_presets else value


def _resolve_preset_ref(value, presets):
    """Resolve a single preset ref for GeoStyle."""
    if not isinstance(value, str):
        return value
    return resolve_preset_ref(value, presets, fallback=value)


def _resolve_policy_preset_refs(value, presets):
    """Resolve preset refs inside import.policy values recursively."""
    if isinstance(value, str):
        return _resolve_preset_ref(value, presets)
    if isinstance(value, list):
        return [_resolve_policy_preset_refs(v, presets) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_policy_preset_refs(v, presets) for k, v in value.items()}
    return value


def _merged_presets(user_presets):
    with open(BUILTIN_STYLE_PATH, 'r', encoding='utf-8') as f:
        builtin = json.load(f)
    builtin_presets = builtin.get('presets', {})
    if not isinstance(user_presets, dict):
        return builtin_presets
    return deep_merge(builtin_presets, user_presets)


# Re-export constants used by downstream rendering helpers.
from ..constants import (
    STYLE_TO_INTERNAL, LINE_WIDTH_SCALE, FONT_SIZE_RATIO, STROKE_WIDTH_SCALE, GGB_FONT_SCALE,
    Z_FILL, Z_FILL_INNER, Z_FILL_LABEL, Z_ANGLE, Z_LINE, Z_STROKE, Z_POINT, Z_LABEL,
)

# Re-export scaling helpers (new in Phase 2 — prefer these over raw constants)
from .scaling import (
    ggb_point_size_to_style,
    ggb_thickness_to_stroke_width,
    ggb_arc_size_px,
    ggb_label_offset_to_style,
    ggb_font_px_to_manim_fontsize,
    json_size_to_internal,
    json_line_width_to_internal,
    json_font_size_to_manim,
    stroke_width_to_manim,
)


# ── GeoStyle ───────────────────────────────────────────────────────────

class GeoStyle:
    """Visual style parameters for geometry rendering.

    Attributes:
        dot_size: Radius of point dots
        line_width: Default stroke width for lines/segments
        ang_width: Stroke width for angle arcs
        ang_rdefault: Default radius for angle arcs
        ang_right: Size of right angle marks
        ang_rshift: Spacing between multiple angle arcs
        strich_len: Length of segment tick marks
        strich_width: Width of segment tick marks
        strich_rshift: Spacing between multiple tick marks
        arrow_height: Arrow tip height
        arrow_width: Arrow tip width
        label_r_offset: Offset of labels from geometry
        font_size: Default font size for labels
        col, col_light, col_accent, col_accent_light: Theme colors
        background, strong: Background and foreground colors
        rendering: Dict of renderer/pipeline options (JSON ``rendering`` section)
        imp: Dict of GGB import rules (JSON ``import`` section)
        export: Dict of export parameters (ptUnit, ptWidth, ptHeight, etc.)
    """

    def __init__(self, style=None):
        # Point sizes
        self.dot_size = 2.8346456692916

        # Line widths
        self.line_width = 1

        # Label offset
        self.label_r_offset = 6

        # Arrow dimensions
        self.arrow_height = 5
        self.arrow_width = 8

        # Tick mark (strich) dimensions
        self.strich_len = 6
        self.strich_width = 6
        self.strich_rshift = 2

        # Angle arc dimensions
        self.ang_rdefault = 10
        self.ang_right = 10
        self.ang_width = 0.75 * self.line_width
        self.ang_rshift = 0.75 * self.strich_rshift

        # Font
        self.font_size = 16 * 3.42578088

        # Colors
        self.background = WHITE
        self.background_explicit = False
        self.strong = BLACK
        self.col_shade = '#eeeeee'
        self.col = '#6688c2'
        self.col_light = '#dee7f5'
        self.col_accent = '#d05456'
        self.col_accent_light = '#f6e0db'

        # Configuration dicts
        self.reference = {}
        self.rendering = {}
        self.imp = {}
        self.export = {
            'ptUnit': 1,
            'ptWidth': manim_config.pixel_width,
            'ptHeight': manim_config.pixel_height,
            'ptXZero': 0,
            'ptYZero': 0,
        }
        self.mode = {'scale': None, 'crop': None}

        if style is not None:
            if isinstance(style, dict):
                self.load_from_dict(style)
            else:
                self.load_from_json(style)

    def load_from_json(self, path):
        """Load style parameters from a JSON file."""
        with open(path, 'r') as f:
            style_json = json.load(f)
        self.load_from_dict(style_json, file_hint=path)

    def load_from_dict(self, style_json, file_hint=None):
        """Load style parameters from a parsed canonical style dict."""
        warnings = validate_style_json(style_json, file_hint=file_hint)
        for w in warnings:
            logger.warning("Style '%s': %s", file_hint or '<dict>', w)

        _user_color = (style_json.get('presets') or {}).get('color') or {}
        _user_rendering = style_json.get('rendering') or {}
        self.background_explicit = (
            _is_concrete_color(_user_color.get('background'))
            or _is_concrete_color(_user_rendering.get('background'))
        )

        presets = _merged_presets(style_json.get('presets', {}))
        colors = dict(presets.get('color', {})) if isinstance(presets.get('color'), dict) else {}
        defaults = style_json.get('defaults', {})

        if 'point_size' in presets:
            # Pixel-invariant: dot_size is in pixels; rendered as `size/2/ptUnit`
            # at ``animageo.py:_render_point``. Previously passed through
            # ``json_size_to_internal`` (× 0.02), which collapsed the arc to
            # sub-pixel on default canvas scales.
            self.dot_size = _resolve_preset_ref(presets['point_size']['main'], presets)
        if 'line_width' in presets:
            self.line_width = json_line_width_to_internal(
                _resolve_preset_ref(presets['line_width']['main'], presets)
            )
        if 'tick' in presets and isinstance(presets['tick'].get('main'), dict):
            tick = presets['tick']['main']
            if 'tick_width_px' in tick:
                self.strich_width = _resolve_preset_ref(tick['tick_width_px'], presets)
            if 'tick_length_px' in tick:
                self.strich_len = _resolve_preset_ref(tick['tick_length_px'], presets)
            if 'tick_shift_px' in tick:
                self.strich_rshift = _resolve_preset_ref(tick['tick_shift_px'], presets)
        if 'arrow' in presets and isinstance(presets['arrow'].get('main'), dict):
            arr = presets['arrow']['main']
            if 'arrow_length_px' in arr:
                self.arrow_height = _resolve_preset_ref(arr['arrow_length_px'], presets)
            if 'arrow_width_px' in arr:
                self.arrow_width = _resolve_preset_ref(arr['arrow_width_px'], presets)
        if 'font_size' in presets and isinstance(presets['font_size'], dict):
            if 'main' in presets['font_size']:
                self.font_size = json_font_size_to_manim(
                    _resolve_preset_ref(presets['font_size']['main'], presets)
                )

        if 'angle' in defaults:
            ang = defaults['angle']
            if 'stroke_width_px' in ang:
                self.ang_width = json_line_width_to_internal(
                    _resolve_preset_ref(ang['stroke_width_px'], presets)
                )
            # Pixel-invariant (see comment above). ``ang_*`` values are
            # pixels; the renderer divides by ``ptUnit`` at draw time.
            if 'arc_shift_px' in ang:
                self.ang_rshift = _resolve_preset_ref(ang['arc_shift_px'], presets)
            if 'arc_size_px' in ang:
                self.ang_rdefault = _resolve_preset_ref(ang['arc_size_px'], presets)
            if 'right_angle_size_px' in ang:
                self.ang_right = _resolve_preset_ref(ang['right_angle_size_px'], presets)

        self.label_r_offset = json_size_to_internal(self.label_r_offset)

        if colors:
            self.col              = colors.get('main',         self.col)
            self.col_light        = colors.get('light',        self.col_light)
            self.col_accent       = colors.get('accent',       self.col_accent)
            self.col_accent_light = colors.get('accent_light', self.col_accent_light)
            self.col_shade        = colors.get('shade',        self.col_shade)
            self.background       = colors.get('background',   self.background)
            self.strong           = colors.get('strong',       self.strong)

        self.reference = dict(style_json.get('reference', {}))
        self.rendering = dict(style_json.get('rendering', {}))
        self.imp       = dict(style_json.get('import', {}))

        bg = self.rendering.get('background')
        if isinstance(bg, str):
            self.background = _resolve_color_value(bg, colors, fallback=bg)

        # Resolve preset references inside import.colors/point_size/line_width.
        if 'colors' in self.imp:
            resolved = {}
            for key, value in self.imp['colors'].items():
                arr = str(value).split(' ')
                head, rest = arr[0], arr[1:]
                color_ref = _resolve_color_ref(head, colors)
                if color_ref is not None:
                    resolved_value = color_ref
                    if rest:
                        resolved_value = f"{resolved_value} {' '.join(rest)}"
                    resolved[key] = resolved_value
                else:
                    resolved[key] = value
            self.imp['colors'] = resolved

        if 'point_size' in self.imp:
            point_size_map = self.imp['point_size']
            size_presets = presets.get('point_size', {})
            self.imp['point_size'] = {
                k: _resolve_group_ref(v, 'point_size', size_presets)
                for k, v in point_size_map.items()
            }

        if 'line_width' in self.imp:
            line_width_map = self.imp['line_width']
            width_presets = presets.get('line_width', {})
            self.imp['line_width'] = {
                k: _resolve_group_ref(v, 'line_width', width_presets)
                for k, v in line_width_map.items()
            }

        if 'policy' in self.imp:
            self.imp['policy'] = _resolve_policy_preset_refs(self.imp['policy'], presets)

    def setViewByGeo(self, geoView):
        """Adjust export parameters to fit the GeoGebra view."""
        w0, h0 = self.export['ptWidth'], self.export['ptHeight']
        w, h = geoView['ptWidth'], geoView['ptHeight']
        if isnan(w0) and isnan(h0):
            logger.error("Width and height have not been set")
            return
        elif isnan(w0):
            w0 = float(h0) * w / h
            self.export['ptWidth'] = w0
        elif isnan(h0):
            h0 = float(w0) * h / w
            self.export['ptHeight'] = h0

        q = min(w0 / w, h0 / h)

        self.export['ptUnit_ggb'] = geoView['ptUnit']
        self.export['ptUnit'] = geoView['ptUnit'] * q
        self.export['ptXZero'] = geoView['ptXZero'] * q + (w0 - q * w) / 2
        self.export['ptYZero'] = geoView['ptYZero'] * q + (h0 - q * h) / 2
