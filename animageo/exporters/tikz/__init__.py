"""TikZ export: comprehensive, semantic TikZ output for LaTeX documents.

Public entry point :func:`export_tikz` (also reachable as
``AnimaGeoScene.exportTikZ``). See ``docs/tikz_export.md``.
"""
from .exporter import export_tikz
from .options import TikZOptions

__all__ = ["export_tikz", "TikZOptions"]
