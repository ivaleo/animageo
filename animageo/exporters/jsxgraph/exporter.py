"""JSXGraph export orchestration.

Builds the board model from the construction graph, assembles the requested
output (html/js/json) and logs a coverage report (which elements are live vs
static), mirroring the parser's unsupported-command diagnostics.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from .builder import build_board
from .document import render
from .options import JSXGraphOptions

logger = logging.getLogger(__name__)


def _resolve_size(scene, options: JSXGraphOptions):
    """Container px size: explicit option → scene export size → 640×480."""
    w, h = options.width_px, options.height_px
    export = getattr(scene.style, "export", {}) or {}
    if w is None:
        w = int(export.get("ptWidth", 640) or 640)
    if h is None:
        h = int(export.get("ptHeight", 480) or 480)
    return int(w), int(h)


def _log_coverage(model) -> None:
    counts = model.counts()
    logger.info(
        "JSXGraph export: %d live, %d static, %d input, %d skip",
        counts.get("live", 0), counts.get("static", 0),
        counts.get("input", 0), counts.get("skip", 0),
    )
    for name, kind, detail in model.coverage:
        if kind in ("static", "skip"):
            logger.info("  [%s] %s — %s", kind, name, detail)


def export_jsxgraph(
    scene,
    filepath: Optional[str] = None,
    *,
    options: Optional[JSXGraphOptions] = None,
    **kwargs,
) -> str:
    """Export ``scene`` as an interactive JSXGraph board.

    Args:
        scene: An ``AnimaGeoScene`` after ``loadGGB`` / ``applyStyle``.
        filepath: Optional output path; the text is always returned.
        options: A :class:`JSXGraphOptions`; when omitted, built from kwargs
            (e.g. ``output="js"``, ``mathjax=False``).

    Returns:
        The generated HTML / JS / JSON text.
    """
    if options is None:
        options = JSXGraphOptions(**kwargs)
    elif kwargs:
        raise TypeError("pass either `options=` or keyword options, not both")

    model = build_board(scene, options)
    width, height = _resolve_size(scene, options)
    text = render(model, options, width=width, height=height)
    _log_coverage(model)

    if filepath is not None:
        filepath = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("JSXGraph exported: %s (%d bytes)", filepath, len(text))
    return text
