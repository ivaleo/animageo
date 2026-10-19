"""TikZ export orchestration.

``export_tikz`` walks the scene's drawable elements in z-order, dispatches each
to its emitter, collects labels to emit last, and assembles a TikZ snippet or a
standalone document via :class:`TikZDocument`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

from ...constants import Z_LINE
from ...geo.lib_elements import latex_escape_text
from .context import TikzContext
from .document import TikZDocument, fmt_num
from .emitters import emitter_for
from .options import TikZOptions

logger = logging.getLogger(__name__)


def _picture_options(ctx: TikzContext) -> str:
    s = ctx.cm_per_mu
    return f"x={fmt_num(s, 6)}cm, y={fmt_num(s, 6)}cm, line join=round"


def _background_color(ctx: TikzContext):
    """Resolve the background colour per options (None=scene, False=off)."""
    bg = ctx.opt.background
    if bg is False:
        return None
    if bg is None:
        return getattr(ctx.scene.style, "background", None)
    return bg


def export_tikz(
    scene,
    filepath: Optional[str] = None,
    *,
    options: Optional[TikZOptions] = None,
    **kwargs,
) -> str:
    """Render ``scene`` to TikZ.

    Args:
        scene: An ``AnimaGeoScene`` after ``loadGGB`` / ``applyStyle``.
        filepath: Optional ``.tex`` path. When given, the result is written
            there (parent dirs created). The TikZ string is always returned.
        options: A :class:`TikZOptions`. When omitted, one is built from
            ``**kwargs`` (e.g. ``standalone=True``, ``dpi=150``).

    Returns:
        The generated TikZ text.
    """
    if options is None:
        options = TikZOptions(**kwargs)
    elif kwargs:
        raise TypeError("pass either `options=` or keyword options, not both")

    doc = TikZDocument(options)
    ctx = TikzContext(scene, options, doc)
    doc.picture_options = _picture_options(ctx)

    left, bottom, right, top = ctx.frame()
    rect = f"{doc.coord(left, bottom)} rectangle {doc.coord(right, top)}"
    if ctx.exact_frame:
        # the picture is the export canvas: labels past it do not grow the page
        doc.line(f"\\useasboundingbox {rect};")

    bg = _background_color(ctx)
    if bg is not None:
        doc.line(f"\\fill[{doc.color(bg)}] {rect};")

    clip = bool(options.clip)
    if clip:
        doc.line("\\begin{scope}")
        doc.line(f"\\clip {rect};")

    view = getattr(scene, "native_view", None)
    if view is not None:
        _emit_native_view(ctx, doc, view, (left, bottom, right, top))

    labels: List[str] = []
    drawables = [
        elem for elem in scene.geo.elements
        if emitter_for(elem) is not None and ctx.is_visible(elem)
    ]
    drawables.sort(key=lambda e: _z_of(ctx, e))

    for elem in drawables:
        emit = emitter_for(elem)
        try:
            emit(ctx, elem, labels)
        except Exception:  # one bad element must not abort the export
            logger.warning("TikZ export: failed to emit %r", getattr(elem, "name", "?"),
                           exc_info=True)

    if clip:
        doc.line("\\end{scope}")

    for ln in labels:
        doc.line(ln)

    text = doc.render()
    if filepath is not None:
        filepath = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("TikZ exported: %s (%d bytes)", filepath, len(text))
    return text


def _emit_native_view(ctx: TikzContext, doc: TikZDocument, settings, rect) -> None:
    """The axes and grid of a native document (``animageo/native/view.py``),
    under the elements, as the SVG draws them."""
    from ...native.view import view_layout, view_style

    left, bottom, right, top = rect
    st = view_style(getattr(ctx.scene.style_config, "rendering", None))
    layout = view_layout(settings, rect, margin=st["axes_font_size_px"] / ctx.ptUnit_style)
    p = ctx.opt.size_precision

    def opts(color, width_px, opacity):
        out = [f"draw={doc.color(color)}", f"line width={fmt_num(ctx.size_pt(width_px), p)}pt"]
        if opacity < 1.0:
            out.append(f"draw opacity={fmt_num(opacity, 3)}")
        return ", ".join(out)

    grid = layout["grid"]
    if any(grid[k][a] for k in ("major", "minor") for a in ("x", "y")):
        doc.comment("grid")
        for kind, width, opacity in (("minor", st["grid_minor_width_px"], st["grid_minor_opacity"]),
                                     ("major", st["grid_width_px"], st["grid_opacity"])):
            o = opts(st["grid_color"], width, opacity)
            for x in grid[kind]["x"]:
                doc.line(f"\\draw[{o}] {doc.coord(x, bottom)} -- {doc.coord(x, top)};")
            for y in grid[kind]["y"]:
                doc.line(f"\\draw[{o}] {doc.coord(left, y)} -- {doc.coord(right, y)};")
    if not (layout["axes"]["x"] or layout["axes"]["y"]):
        return
    doc.comment("axes")
    o = opts(st["axes_color"], st["axes_width_px"], st["axes_opacity"])
    tick = st["axes_tick_length_px"] / 2 / ctx.ptUnit_style
    fpt = ctx.size_pt(st["axes_font_size_px"])
    font = f"font=\\fontsize{{{fmt_num(fpt, p)}}}{{{fmt_num(fpt * 1.2, p)}}}\\selectfont"
    text = f"text={doc.color(st['axes_color'])}"
    if st["axes_opacity"] < 1.0:
        text += f", text opacity={fmt_num(st['axes_opacity'], 3)}"
    sep = f"inner sep={fmt_num(ctx.size_pt(st['axes_tick_length_px'] / 2 + 2), p)}pt"
    if layout["axes"]["x"]:
        doc.line(f"\\draw[{o}] {doc.coord(left, 0)} -- {doc.coord(right, 0)};")
        for x in layout["ticks"]["x"]:
            doc.line(f"\\draw[{o}] {doc.coord(x, -tick)} -- {doc.coord(x, tick)};")
    if layout["axes"]["y"]:
        doc.line(f"\\draw[{o}] {doc.coord(0, bottom)} -- {doc.coord(0, top)};")
        for y in layout["ticks"]["y"]:
            doc.line(f"\\draw[{o}] {doc.coord(-tick, y)} -- {doc.coord(tick, y)};")
    for axis, anchor in (("x", "north"), ("y", "east")):
        for value, label in layout["numbers"][axis]:
            at = doc.coord(value, 0) if axis == "x" else doc.coord(0, value)
            doc.line(f"\\node[{text}, {font}, {sep}, anchor={anchor}] at {at} "
                     f"{{${label.replace(chr(0x2212), '-')}$}};")
    for axis, at, anchor in (("x", doc.coord(right, 0), "south east"), ("y", doc.coord(0, top), "north west")):
        label = layout["labels"][axis]
        if label:
            # a name of letters and digits in math italic, anything else as escaped text
            body = f"${label}$" if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", label) \
                else f"\\textit{{{latex_escape_text(label)}}}"
            doc.line(f"\\node[{text}, {font}, {sep}, anchor={anchor}] at {at} {{{body}}};")


def _z_of(ctx: TikzContext, elem) -> float:
    try:
        return float(ctx.resolve(elem, "z_index", default=Z_LINE))
    except (TypeError, ValueError):
        return float(Z_LINE)
