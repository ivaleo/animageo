"""Resolved style → TikZ path/option fragments.

These helpers turn the values produced by the style resolver into TikZ option
strings (``draw=agc0, line width=0.6pt, opacity=0.8, dashed``) and colour-macro
references. All px→pt conversion goes through :class:`TikzContext`.
"""
from __future__ import annotations

from typing import List, Optional

from ...dash import dash_pattern, element_dash_px
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


def stroke_default(ctx: TikzContext) -> str:
    return str(getattr(ctx.scene.style, "strong", "#000000"))


def background_color(ctx: TikzContext):
    return getattr(ctx.scene.style, "background", None)


def _opacity(value, fallback: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def dash_options(ctx: TikzContext, elem, *, width_px=None, cap=None) -> Optional[str]:
    """Return a ``dash pattern=...`` fragment, or ``None`` for a solid line.

    The renderer's nominal pattern: ``stroke_dash_ratio`` of the period in
    style px (``stroke_dash_period_px`` → ``rendering.dash_period_px`` → 10),
    sized like line widths (``size_pt``). With a round/square ``cap`` every
    dash grows by the line width, so the drawn dash is shortened and phased
    to keep the visible one nominal — as in the SVG. No fit to the path
    length: TikZ starts the pattern at each path's start.
    """
    dash_px = element_dash_px(
        ctx.scene, elem, resolve=lambda e, k, d=None: ctx.resolve(e, k, default=d))
    if dash_px is None:
        return None
    on_px, off_px = dash_px
    cap_extent = 0.0
    if cap in ("round", "square") and width_px:
        try:
            cap_extent = max(0.0, float(width_px))
        except (TypeError, ValueError):
            cap_extent = 0.0
    pat = dash_pattern(0.0, ctx.size_pt(on_px), ctx.size_pt(off_px),
                       cap_extent_mu=ctx.size_pt(cap_extent))
    p = ctx.opt.size_precision
    out = f"dash pattern=on {fmt_num(pat.on, p)}pt off {fmt_num(pat.off, p)}pt"
    if pat.offset:
        out += f", dash phase={fmt_num(pat.offset, p)}pt"
    return out


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

    cap = None
    if with_cap:
        cap = ctx.resolve(elem, "stroke_linecap",
                          default=ctx.scene.style.rendering.get("line_cap", "butt"))
        tikz_cap = CAP_MAP.get(cap, "butt")
        if tikz_cap != "butt":
            opts.append(f"line cap={tikz_cap}")

    if with_dash:
        d = dash_options(ctx, elem, width_px=width_px, cap=cap)
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
