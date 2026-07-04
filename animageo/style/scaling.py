"""Named scaling functions for converting between GeoGebra, JSON style, and
internal rendering units.

Replaces magic numbers (×2, /2, /√2, ×0.02, etc.) scattered across
ggb_parser.py and animageo.py with a single source of truth. Every formula
lives here; callers import named functions, not raw constants.

Three unit spaces in AnimaGeo:
- **GGB pixel space** — sizes as they come from .ggb XML (pointSize,
  thickness, arcSize, labelOffset, fontSize). Pixel-invariant by design.
- **JSON style space** — sizes declared in style/*.json, also pixel-like.
- **Internal / manim space** — the units used by the renderer. Visual
  pixel-style geometry is converted via `/ ptUnit_style`. Manim stroke/font
  render parameters use the same selected style scale
  (`* 100 / selected_unit`).

Pixel-invariance contract: all GGB/JSON inputs are in pixels. Coordinate
sizes are divided by the style scale selected by the scene; widths passed to
Manim `stroke_width`/`set_stroke(width=...)` must go through
`stroke_width_to_manim`. Export layout scales the reference-canvas style
together with the final output.
"""
import math

from ..constants import (
    STYLE_TO_INTERNAL,
    LINE_WIDTH_SCALE,
    FONT_SIZE_RATIO,
    STROKE_WIDTH_SCALE,
    GGB_FONT_SCALE,
)

# ── GGB → elem.ggb_style (parser-side) ────────────────────────────────

def ggb_point_size_to_style(ggb_point_size):
    """Convert GGB <pointSize val="N"/> to elem.ggb_style['size_px'].

    size_px is later rendered as `size_px / 2 / style_unit`.
    """
    return ggb_point_size * 2


def ggb_thickness_to_stroke_width(ggb_thickness):
    """Convert GGB <lineStyle thickness="N"/> to elem.ggb_style['stroke_width_px'].

    stroke_width_px is later multiplied by STROKE_WIDTH_SCALE/style_unit at render.
    """
    return ggb_thickness / 2


def ggb_arc_size_px(ggb_arc_size, right_angle=False):
    """Convert GGB <arcSize val="N"/> to elem.ggb_style['arc_size_px'].

    Angles store raw pixel value; right angles are divided by √2 at render
    so their visual size matches regular arcs (same diagonal length).
    """
    if right_angle:
        return ggb_arc_size / math.sqrt(2)
    return ggb_arc_size


def ggb_label_offset_to_style(x_px, y_px):
    """Convert GGB <labelOffset x="X" y="Y"/> to elem.ggb_style['label_offset_px'] = [x, -y].

    Y is inverted because GGB screen coords point down but math coords up.
    Values stay in GGB pixels; divided by ptUnit_ggb at render.
    """
    return [x_px, -y_px]


# ── GGB → GeoStyle (applyStyle-side) ──────────────────────────────────

def ggb_font_px_to_manim_fontsize(ggb_font_px, ptUnit):
    """Convert GGB gui font size (px) to GeoStyle.font_size (manim units).

    Formula: font_px * 100 / ptUnit. Pixel-invariant: same apparent size
    regardless of canvas resolution.
    """
    return ggb_font_px * GGB_FONT_SCALE / ptUnit


# ── JSON → GeoStyle (style.json-side) ─────────────────────────────────

def json_size_to_internal(json_value):
    """Convert JSON style value (dot/angle/strich/arrow dimensions) to internal units.

    Multiplier is STYLE_TO_INTERNAL = 0.02.
    """
    return STYLE_TO_INTERNAL * json_value


def json_line_width_to_internal(json_value):
    """Convert JSON line width / angle line / strich width to internal units.

    Multiplier is LINE_WIDTH_SCALE = 2 (different from size scale because
    stroke widths live in a separate unit system).
    """
    return LINE_WIDTH_SCALE * json_value


def json_font_size_to_manim(json_value):
    """Convert JSON font size to manim font_size.

    Multiplier is FONT_SIZE_RATIO = 50 / 25.9.
    """
    return json_value * FONT_SIZE_RATIO


# ── Internal → manim (render-time) ────────────────────────────────────

def stroke_width_to_manim(stroke_width_px, ptUnit):
    """Convert elem.style['stroke_width_px'] to manim stroke_width at render time.

    Formula: stroke_width_px * 100 / ptUnit. Callers pass the active style
    scale: active style scale, normally ``ptUnit_style``.
    """
    return STROKE_WIDTH_SCALE * float(stroke_width_px) / ptUnit
