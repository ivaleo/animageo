"""Configuration for JSXGraph export.

Phase 1 defaults (see ``docs/archive/jsxgraph_export_plan.md`` §12): self-contained
HTML, MathJax labels from CDN, static fallback + coverage report for any
command without a live mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# Pinned, verified to resolve on jsDelivr.
DEFAULT_JSXGRAPH_VERSION = "1.10.1"


@dataclass(frozen=True)
class JSXGraphOptions:
    """Options for :func:`export_jsxgraph`.

    Attributes:
        output: ``"html"`` (self-contained page, default), ``"js"`` (board
            script fragment), ``"spec"`` (declarative ``animageo-board/v1``
            JSON for the framework-agnostic JS runtime / Web Component — no JS
            strings to evaluate), ``"json"`` (legacy board spec carrying JS
            statements), or ``"moodle"`` (a ``<jsxgraph>`` block for the Moodle
            filter_jsxgraph plugin).
        boundingbox: ``(left, top, right, bottom)`` in math units; when ``None``
            it is taken from the scene viewport.
        keepaspectratio: keep circles round (equal px-per-unit on both axes).
            ``None`` (default) mirrors the GeoGebra scene — equal x/y unit
            scales keep the aspect, unequal scales release it. A concrete
            ``True`` / ``False`` overrides.
        axis / grid: ``None`` (default) mirrors the imported GeoGebra scene
            (``showAxes`` / ``showGrid``, with the GeoGebra defaults — axes on,
            grid off — when the scene says nothing). A concrete ``True`` /
            ``False`` overrides the scene.
        background: board background colour. ``None`` (default) mirrors the
            scene (GeoGebra ``bgColor`` → the scene background, usually white);
            a CSS colour string overrides it; ``""`` disables it (page colour
            shows through).
        shownavigation: board chrome.
        mathjax: render labels as LaTeX via MathJax.
        jsxgraph_version: CDN version to pin.
        cdn: load JSXGraph/MathJax from CDN (Phase 1; offline/vendored later).
        div_id: id of the container ``<div>``.
        width_px / height_px: container size; when ``None`` derived from the
            scene export size.
        fallback: ``"static"`` (emit frozen geometry + report) or ``"skip"``.
        coordinate_precision: decimals for emitted coordinates.
    """

    output: str = "html"
    boundingbox: Optional[Tuple[float, float, float, float]] = None
    keepaspectratio: Optional[bool] = None
    axis: Optional[bool] = None
    grid: Optional[bool] = None
    background: Optional[str] = None
    shownavigation: bool = True
    mathjax: bool = True
    jsxgraph_version: str = DEFAULT_JSXGRAPH_VERSION
    cdn: bool = True
    div_id: str = "agbox"
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    fallback: str = "static"
    coordinate_precision: int = 4
