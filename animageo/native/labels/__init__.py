"""Labels without manim (spec §9.3): :func:`layout_labels` and the TeX metrics measurer.

``tex`` sets a label's TeX with the metrics of the template fonts
(``metrics.v1.json``); ``layout`` runs the classic placement on a document.
Neither imports manim; ``layout`` loads the classic code inside its functions.
"""
from __future__ import annotations

from .layout import layout_labels

__all__ = ['layout_labels']
