"""Shared render context for TikZ emitters.

``TikzContext`` bundles the scene, the export options, the in-progress
``TikZDocument`` and the unit conversions every emitter needs. It is the TikZ
analogue of ``AnimaGeoScene._build_render_ctx``: style values are read through
the same resolver the manim renderer uses, so GGB import / overlay / explicit
``elem.style`` all behave identically.

Unit model:
- coordinates are math units (MU); the picture sets ``x=y=ptUnit*cm_per_px`` cm.
- "size" pixels (stroke width, point radius, font) map to absolute pt via
  ``px * (ptUnit/ptUnit_style) * pt_per_px`` — the same output-pixel size the
  SVG path produces.
- label-offset pixels map via ``px * (ptUnit/ptUnit_ggb) * pt_per_px``.
"""
from __future__ import annotations

from typing import Any, Optional

from ...geo.lib_elements import textify_cyrillic
from ...labels import resolve_label_text
from ...style.resolver import resolve as _resolve
from .document import TikZDocument
from .options import TikZOptions


class TikzContext:
    def __init__(self, scene, options: TikZOptions, document: TikZDocument):
        self.scene = scene
        self.opt = options
        self.doc = document

        export = getattr(scene.style, "export", {}) or {}
        self.ptUnit = float(export.get("ptUnit", 1) or 1)
        self.ptUnit_style = float(export.get("ptUnit_style", self.ptUnit) or self.ptUnit)
        self.ptUnit_ggb = float(export.get("ptUnit_ggb", self.ptUnit_style) or self.ptUnit_style)
        self.ggb_font_px = export.get("fontSize")

        # px → pt factors. ``_size`` covers strokes/markers/fonts; ``_offset``
        # covers GGB label offsets (which were authored at the GGB scale).
        self._size_factor = (self.ptUnit / self.ptUnit_style) * self.opt.pt_per_px
        self._offset_factor = (self.ptUnit / self.ptUnit_ggb) * self.opt.pt_per_px

    # ── style resolution ────────────────────────────────────────────────
    def resolve(self, elem, key: str, default: Any = None) -> Any:
        return _resolve(self.scene, elem, key, default=default)

    def label_text(self, elem) -> str:
        # Cyrillic must leave math mode: ``\node {$Б$}`` compiles to an empty
        # node under the T2A math alphabet this exporter's preamble sets up.
        return textify_cyrillic(resolve_label_text(self.scene, elem))

    # ── unit conversions ─────────────────────────────────────────────────
    def size_pt(self, px: float) -> float:
        """Convert a "size" pixel value to absolute pt (fixed, scale-free)."""
        return float(px) * self._size_factor

    def offset_pt(self, px: float) -> float:
        """Convert a GGB label-offset pixel value to absolute pt."""
        return float(px) * self._offset_factor

    @property
    def cm_per_mu(self) -> float:
        return self.ptUnit * self.opt.cm_per_px

    # ── geometry ─────────────────────────────────────────────────────────
    def viewport(self):
        """(left, bottom, right, top) of the camera frame in MU: lines and
        sampled curves are drawn across it (it contains the export canvas)."""
        return self.scene._get_scene_bounds(padding=0)

    @property
    def exact_frame(self) -> bool:
        """Whether the picture is the export canvas (``TikZOptions.frame``)."""
        if self.opt.frame is not None:
            return self.opt.frame == "export"
        return bool(getattr(self.scene, "export_frame_exact", False))

    def frame(self):
        """(left, bottom, right, top) in MU of the picture: the clip, the
        background and the bounding box. With :attr:`exact_frame` — the export
        canvas of the scene, the integer pixel size SVG, PDF and EPS take
        (``int(ptWidth)`` × ``int(ptHeight)`` from ``(ptXZero, ptYZero)``);
        otherwise the camera frame (:meth:`viewport`)."""
        if not self.exact_frame:
            return self.viewport()
        export = self.scene.style.export
        unit = float(export["ptUnit"])
        ox, oy = float(export["ptXZero"]), float(export["ptYZero"])
        width, height = int(export["ptWidth"]), int(export["ptHeight"])
        return (-ox / unit, (oy - height) / unit, (width - ox) / unit, oy / unit)

    def is_visible(self, elem) -> bool:
        return self.scene._element_visible(elem)
