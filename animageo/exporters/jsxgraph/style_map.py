"""Resolved style → JSXGraph attributes.

Reads through the same ``style.resolver`` the renderer uses, so GGB import →
overlay → explicit ``elem.style`` behave identically. Sizes are pixels in both
AnimaGeo and JSXGraph, so no unit conversion is needed.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .context import JsxContext, Raw


# AnimaGeo point_shape → JSXGraph `face`.
_FACE = {
    "circle": "o", "square": "[]", "diamond": "<>",
    "triangle_up": "^", "triangle_down": "v",
    "triangle_left": "<", "triangle_right": ">",
    "cross": "x", "plus": "+",
}


def _hex(color) -> str:
    """Return a CSS hex colour string for any colour input."""
    if color is None:
        return "#000000"
    try:
        from manim import ManimColor
        return ManimColor(color).to_hex()
    except Exception:
        s = str(color)
        return s if s.startswith("#") else "#000000"


def _opacity(ctx: JsxContext, elem, key: str, default: float) -> float:
    try:
        v = ctx.resolve(elem, key, default=default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# JSXGraph `dash` index by dash/line-width ratio, mirroring the TikZ exporter's
# thresholds (animageo/exporters/tikz/style.py): dotted → 1, dashes → 3, loose
# dashes → 4. (0 = solid; we omit the attr in that case.)
def _dash_value(ctx: JsxContext, elem) -> Optional[int]:
    ratio = ctx.resolve(elem, "stroke_dash_ratio", default=None)
    if not ratio:
        return None
    try:
        r = float(ratio)
    except (TypeError, ValueError):
        return None
    if r <= 2.5:
        return 1   # dotted
    if r <= 6.0:
        return 3   # (medium) dashes
    return 4       # big / loose dashes


# AnimaGeo z-index tiers → JSXGraph `layer` (0..9, higher = on top). Reproduces
# the renderer's draw order (fills < angles < lines/circles < strokes < points)
# instead of relying on JSXGraph's per-type defaults, which differ. Keyed by the
# resolved numeric z-index; the renderer's _Z_AUTO_BY_TYPE uses the same values.
def _layer_for_z(z) -> Optional[int]:
    try:
        zf = float(z)
    except (TypeError, ValueError):
        return None
    # Z_FILL≈0.01, Z_ANGLE=3, Z_LINE=4, Z_STROKE=5, Z_POINT=50.
    if zf < 1:
        return 3      # fills (background)
    if zf < 4:
        return 5      # angle arcs
    if zf < 5:
        return 6      # lines, circles
    if zf < 50:
        return 7      # segments, arcs, vectors
    return 9          # points (topmost)


def base_attrs(ctx: JsxContext, elem, *, stroke_default="#000000") -> Dict[str, Any]:
    """Stroke/fill/width/opacity/dash/label attributes common to most elements."""
    if elem is None:
        return {}
    attrs: Dict[str, Any] = {}
    # Hidden objects must not be drawn, but they still exist in the board so
    # visible elements built on them keep recomputing on drag (mirrors how a
    # hidden GeoGebra object still participates in the construction). Only emit
    # the attribute when hidden — JSXGraph defaults to visible.
    if not ctx.is_visible(elem):
        attrs["visible"] = False
    attrs["strokeColor"] = _hex(ctx.resolve(elem, "stroke", default=stroke_default))

    fill = ctx.resolve(elem, "fill", default=None)
    if fill is not None:
        attrs["fillColor"] = _hex(fill)

    sw = ctx.resolve(elem, "stroke_width_px", default=1.0)
    try:
        attrs["strokeWidth"] = float(sw)
    except (TypeError, ValueError):
        pass

    so = _opacity(ctx, elem, "stroke_opacity", 1.0)
    if so < 1.0:
        attrs["strokeOpacity"] = round(so, 3)
    fo = _opacity(ctx, elem, "fill_opacity", 0.0)
    if "fillColor" in attrs:
        # Pin fill opacity whenever a fill colour is set — even at 0. JSXGraph
        # defaults closed shapes (circles/conics/polygons) to a *solid* fill, so
        # omitting the attr paints a fill the renderer never draws (a stroke-only
        # GeoGebra circle has fill alpha 0 but still carries a fill colour).
        attrs["fillOpacity"] = round(max(fo, 0.0), 3)
    elif fo > 0.0:
        attrs["fillOpacity"] = round(fo, 3)

    dash = _dash_value(ctx, elem)
    if dash:
        attrs["dash"] = dash

    # Draw order: map the resolved z-index to a JSXGraph layer so the widget
    # stacks like the renderer. Only emit an explicit z-index; when unset we
    # leave JSXGraph's per-type default (which is already a sensible order).
    z = ctx.resolve(elem, "z_index", default=None)
    layer = _layer_for_z(z) if z is not None else None
    if layer is not None:
        attrs["layer"] = layer

    _apply_label(ctx, elem, attrs)
    return attrs


def point_attrs(ctx: JsxContext, elem) -> Dict[str, Any]:
    """Point-specific attributes (size/face) on top of the common ones."""
    if elem is None:
        return {}
    attrs = base_attrs(ctx, elem)
    # JSXGraph `size` is the marker radius in px; the renderer draws size_px/2
    # (see ``_render_point``). Keep it fractional — rounding to an int skews the
    # point-size : line-width ratio away from the SVG/preview (e.g. 2.5→2).
    size_px = ctx.resolve(elem, "size_px", default=ctx.scene.style.dot_size)
    try:
        attrs["size"] = round(max(float(size_px) / 2.0, 1.0), 2)
    except (TypeError, ValueError):
        pass
    shape = ctx.resolve(elem, "point_shape", default="circle")
    attrs["face"] = _FACE.get(shape, "o")
    # A point marker is filled by default; mirror the renderer (op_f default 1).
    if "fillColor" not in attrs:
        attrs["fillColor"] = attrs.get("strokeColor", "#000000")
    attrs["fillOpacity"] = round(_opacity(ctx, elem, "fill_opacity", 1.0), 3)
    return attrs


# AnimaGeo 9-point label anchor (which corner/edge of the label bbox sits at
# the target) → JSXGraph label (anchorX, anchorY): which point of the label is
# pinned at its position. e.g. 'BL' = bottom-left pinned → label extends up-right
# = anchorX 'left', anchorY 'bottom'. First char = vertical (T/M/B), second =
# horizontal (L/C/R).
_ANCHOR_Y = {"T": "top", "M": "middle", "B": "bottom"}
_ANCHOR_X = {"L": "left", "C": "middle", "R": "right"}


def _anchor_xy(anchor):
    """Return (anchorX, anchorY) for an AnimaGeo anchor code, or None if it
    isn't a recognised 9-point code."""
    if not isinstance(anchor, str) or len(anchor) != 2:
        return None
    ay = _ANCHOR_Y.get(anchor[0])
    ax = _ANCHOR_X.get(anchor[1])
    if ax is None or ay is None:
        return None
    return ax, ay


def arrow_attrs(ctx: JsxContext, elem, *, last=True, first=False) -> Dict[str, Any]:
    """JSXGraph arrowhead attributes for a vector/ray, sized from the resolved
    GGB ``arrow_length_px`` / ``arrow_width_px``.

    JSXGraph draws arrowheads in multiples of the stroke width; its ``size`` is
    roughly the head length in those multiples. Map the GGB head length (px) to
    ``size`` by dividing by the stroke width, clamped to a sane range so a thin
    stroke doesn't yield a giant head. Returns ``{}`` when no arrow size is
    resolved (then JSXGraph's default head is used)."""
    length = ctx.resolve(elem, "arrow_length_px", default=None)
    if length is None:
        return {}
    try:
        length = float(length)
    except (TypeError, ValueError):
        return {}
    sw = ctx.resolve(elem, "stroke_width_px", default=1.0)
    try:
        sw = max(float(sw), 0.5)
    except (TypeError, ValueError):
        sw = 1.0
    # size in stroke-width multiples; clamp to keep heads reasonable.
    size = max(2.0, min(round(length / sw, 2), 12.0))
    spec: Dict[str, Any] = {"type": 1, "size": size}
    out: Dict[str, Any] = {}
    if last:
        out["lastArrow"] = dict(spec)
    if first:
        out["firstArrow"] = dict(spec)
    return out


def _strip_math_delims(text: str) -> str:
    """Remove a surrounding ``$…$`` or ``\\(…\\)`` from a label.

    ``resolve_label_text`` returns LaTeX already wrapped in ``$…$`` (the TikZ/
    manim convention); JSXGraph's MathJax expects ``\\(…\\)``, so we unwrap
    first to avoid the literal ``$…$`` showing through (double-wrapping)."""
    t = text.strip()
    if len(t) >= 2 and t[0] == "$" and t[-1] == "$":
        return t[1:-1]
    if t.startswith("\\(") and t.endswith("\\)"):
        return t[2:-2]
    return t


def label_name(text: str, mathjax: bool) -> str:
    body = _strip_math_delims(text)
    return f"\\({body}\\)" if mathjax else body


def _apply_label(ctx: JsxContext, elem, attrs: Dict[str, Any]) -> None:
    if not ctx.label_visible(elem):
        attrs["withLabel"] = False
        return
    text = ctx.label_text(elem)
    if not text:
        attrs["withLabel"] = False
        return
    attrs["name"] = label_name(text, ctx.opt.mathjax)
    attrs["withLabel"] = True
    label: Dict[str, Any] = {}
    if ctx.opt.mathjax:
        label["useMathJax"] = True
    lc = ctx.resolve(elem, "label_color", default=None)
    if lc is not None:
        label["strokeColor"] = _hex(lc)
    # GeoGebra `labelOffset` (stored as pixels, y up-positive — same convention
    # as JSXGraph's label `offset`). Only carry a deliberate nudge over; a near-
    # zero offset means "GeoGebra default position", so leave JSXGraph's own
    # sensible default in place rather than dropping the label onto the anchor.
    off = ctx.resolve(elem, "label_offset_px", default=None)
    try:
        if off is not None and (abs(float(off[0])) > 1.0 or abs(float(off[1])) > 1.0):
            label["offset"] = [round(float(off[0]), 2), round(float(off[1]), 2)]
    except (TypeError, ValueError, IndexError):
        pass
    # Honour an explicit 9-point anchor (from GGB import or the label-placement
    # solver) so the offset is applied relative to the same label corner the
    # renderer uses. When unset, leave JSXGraph's own sensible default.
    xy = _anchor_xy(ctx.resolve(elem, "label_anchor", default=None))
    if xy is not None:
        label["anchorX"], label["anchorY"] = xy
    if label:
        attrs["label"] = label


def js_attrs(ctx: JsxContext, attrs: Dict[str, Any]) -> str:
    """Serialise an attribute dict to a JS object literal."""
    parts = []
    for k, v in attrs.items():
        if isinstance(v, dict):
            inner = js_attrs(ctx, v)
            parts.append(f"{k}: {inner}")
        else:
            parts.append(f"{k}: {ctx.js_value(v)}")
    return "{" + ", ".join(parts) + "}"
