"""Resolved style → TikZ path/option fragments.

These helpers turn the values produced by the style resolver into TikZ option
strings (``draw=agc0, line width=0.6pt, opacity=0.8, dashed``) and colour-macro
references. All px→pt conversion goes through :class:`TikzContext`.
"""
from __future__ import annotations

from typing import List, Optional

from .context import TikzContext
from .document import fmt_num


# 9-point anchor → TikZ ``anchor=`` (which part of the node sits at the point).
ANCHOR_MAP = {
    "TL": "north west", "TC": "north", "TR": "north east",
    "ML": "west",       "MC": "center", "MR": "east",
    "BL": "south west", "BC": "south",  "BR": "south east",
}

# manim line-cap name → TikZ ``line cap=``.
CAP_MAP = {"butt": "butt", "round": "round", "square": "rect", None: "butt"}

# manim ``DashedLine.dash_length`` (MU). Used to derive a px-faithful pattern.
_DASH_LENGTH_MU = 0.17


def stroke_default(ctx: TikzContext) -> str:
    return str(getattr(ctx.scene.style, "strong", "#000000"))


def background_color(ctx: TikzContext):
    return getattr(ctx.scene.style, "background", None)


def _opacity(value, fallback: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def dash_options(ctx: TikzContext, elem) -> Optional[str]:
    """Return a ``dash pattern=...`` fragment, or ``None`` for a solid line."""
    ratio = ctx.resolve(elem, "stroke_dash_ratio", default=None)
    if not ratio:
        return None
    try:
        ratio = float(ratio)
    except (TypeError, ValueError):
        return None
    if ratio <= 0 or ratio >= 1:
        return None
    total_pt = ctx.size_pt(_DASH_LENGTH_MU * ctx.ptUnit_style)
    on = total_pt * ratio
    off = total_pt * (1.0 - ratio)
    p = ctx.opt.size_precision
    return f"dash pattern=on {fmt_num(on, p)}pt off {fmt_num(off, p)}pt"


def stroke_options(
    ctx: TikzContext,
    elem,
    *,
    color_default: Optional[str] = None,
    width_px: Optional[float] = None,
    with_dash: bool = True,
    with_cap: bool = True,
    extra: Optional[List[str]] = None,
) -> str:
    """Build the option list for a stroked path (without surrounding ``[]``)."""
    opts: List[str] = []

    col = ctx.resolve(elem, "stroke", default=color_default or stroke_default(ctx))
    opts.append(f"draw={ctx.doc.color(col)}")

    op = _opacity(ctx.resolve(elem, "stroke_opacity", default=1.0))
    if op < 1.0:
        opts.append(f"draw opacity={fmt_num(op, 3)}")

    if width_px is None:
        width_px = ctx.resolve(elem, "stroke_width_px", default=1.0)
    lw_pt = ctx.size_pt(width_px or 0.0)
    opts.append(f"line width={fmt_num(lw_pt, ctx.opt.size_precision)}pt")

    if with_cap:
        cap = ctx.resolve(elem, "stroke_linecap",
                          default=ctx.scene.style.rendering.get("line_cap", "butt"))
        tikz_cap = CAP_MAP.get(cap, "butt")
        if tikz_cap != "butt":
            opts.append(f"line cap={tikz_cap}")

    if with_dash:
        d = dash_options(ctx, elem)
        if d:
            opts.append(d)

    if extra:
        opts.extend(extra)
    return ", ".join(opts)


def fill_options(
    ctx: TikzContext,
    elem,
    *,
    color_default: Optional[str] = None,
) -> str:
    """Build the option list for a filled (non-stroked) path.

    The fill colour falls back to the scene background when neither resolver
    nor caller supplies one — mirroring the renderer, where non-point fills
    default to ``style.background``.
    """
    opts: List[str] = []
    fallback = color_default or background_color(ctx) or stroke_default(ctx)
    col = ctx.resolve(elem, "fill", default=fallback)
    opts.append(f"fill={ctx.doc.color(col)}")
    op = _opacity(ctx.resolve(elem, "fill_opacity", default=1.0))
    if op < 1.0:
        opts.append(f"fill opacity={fmt_num(op, 3)}")
    return ", ".join(opts)


def anchor_for(ctx: TikzContext, elem) -> str:
    """Resolve the label anchor as a TikZ ``anchor=`` value (default south west)."""
    raw = ctx.resolve(
        elem, "label_anchor",
        default=ctx.scene.style.rendering.get("label_anchor"),
    )
    if isinstance(raw, str) and raw in ANCHOR_MAP:
        return ANCHOR_MAP[raw]
    return "south west"
