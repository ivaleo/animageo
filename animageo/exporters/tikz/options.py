"""Configuration for TikZ export.

A small immutable bundle of knobs controlling how a construction is rendered
into TikZ. Sensible defaults reproduce the SVG look (96-dpi pixel mapping, real
LaTeX labels, viewport clipping).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# CSS-pixel ↔ physical conversion. AnimaGeo stores all sizes in output pixels;
# the SVG canvas is pixel-addressed. 96 dpi is the CSS default, at which a
# pixel equals a TeX "big point" (bp = 1/72 in) closely enough that
# ``pt_per_px = 72/96 = 0.75`` reproduces the on-screen look in print.
DEFAULT_DPI: float = 96.0


@dataclass(frozen=True)
class TikZOptions:
    """Options for :func:`export_tikz`.

    Attributes:
        standalone: Wrap the ``tikzpicture`` in a compilable
            ``\\documentclass{standalone}`` document with a Cyrillic-ready
            preamble. Default ``False`` emits a bare snippet for ``\\input{}``.
        dpi: Pixels-per-inch used to convert output pixels to cm/pt. The
            picture's ``x=/y=`` unit and all ``pt`` sizes derive from this.
        clip: Clip the picture to the viewport rectangle so infinite/sampled
            geometry does not overflow the canvas (mirrors the bounded SVG).
        background: Emit a filled background rectangle. ``None`` follows the
            scene's ``style.background``; ``False`` forces no background;
            a colour string forces that colour.
        emit_font_size: Emit an explicit ``\\fontsize`` on label nodes so text
            size matches the raster output. When ``False`` labels inherit the
            host document's font (often preferable for LaTeX integration).
        coordinate_precision: Significant decimals for coordinates (MU).
        size_precision: Decimals for ``pt`` sizes (widths, radii, offsets).
        indent: Indentation string for body lines.
        standalone_preamble: Override the standalone preamble (advanced). When
            ``None`` a default Cyrillic-capable preamble is used.
        comment_header: Emit a ``% AnimaGeo TikZ export`` header comment.
    """

    standalone: bool = False
    dpi: float = DEFAULT_DPI
    clip: bool = True
    background: Optional[object] = None
    emit_font_size: bool = True
    coordinate_precision: int = 4
    size_precision: int = 3
    indent: str = "  "
    standalone_preamble: Optional[str] = None
    comment_header: bool = True

    @property
    def cm_per_px(self) -> float:
        return 2.54 / float(self.dpi)

    @property
    def pt_per_px(self) -> float:
        # TeX big-point convention (72 pt per inch).
        return 72.0 / float(self.dpi)
