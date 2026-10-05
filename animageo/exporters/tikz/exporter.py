"""TikZ export orchestration.

``export_tikz`` walks the scene's drawable elements in z-order, dispatches each
to its emitter, collects labels to emit last, and assembles a TikZ snippet or a
standalone document via :class:`TikZDocument`.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from ...constants import Z_LINE
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


def _z_of(ctx: TikzContext, elem) -> float:
    try:
        return float(ctx.resolve(elem, "z_index", default=Z_LINE))
    except (TypeError, ValueError):
        return float(Z_LINE)
