"""Select the manim render output format/quality before a render.

The rasterised/video formats (``png``/``gif``/``mp4``/``webm``/``mov``) are
produced by manim's own ``SceneFileWriter`` + ffmpeg, not by AnimaGeo. The
writer reads ``manim.config`` at scene-setup time, so these helpers must be
called **before** the scene is rendered (e.g. at module import, or by passing
``--format`` to the ``manim`` CLI). Setting them inside ``construct()`` is too
late.

The static vector formats (``svg``/``pdf``/``eps``/``tikz``) bypass this path
entirely — they are written by ``AnimaGeoScene.exportSVG/exportPDF/exportEPS/
exportTikZ`` after ``construct()``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Formats produced by the manim renderer (the "render track").
OUTPUT_FORMATS = ("png", "gif", "mp4", "webm", "mov")


def configure_render(*, format=None, fps=None, transparent=None):
    """Set manim global render config for the next render.

    Args:
        format: One of :data:`OUTPUT_FORMATS` (a leading ``.`` is tolerated).
            Controls the movie/image container manim writes.
        fps: Frames per second (``config.frame_rate``).
        transparent: Render on a transparent background (``config.transparent``).
            Honoured by ``png``/``webm``/``mov``; ``gif`` only supports 1-bit
            transparency and ``mp4`` none.

    Raises:
        ValueError: if ``format`` is not a recognised output format.
    """
    # Validate before importing manim so the error path is dependency-free.
    fmt = None
    if format is not None:
        fmt = str(format).lower().lstrip(".")
        if fmt not in OUTPUT_FORMATS:
            raise ValueError(
                f"unsupported output format {format!r}; "
                f"choose from {OUTPUT_FORMATS}"
            )

    from manim import config

    if fmt is not None:
        config.format = fmt
    if fps is not None:
        config.frame_rate = float(fps)
    if transparent is not None:
        config.transparent = bool(transparent)

    logger.info(
        "Render config set: format=%s frame_rate=%s transparent=%s",
        getattr(config, "format", None),
        getattr(config, "frame_rate", None),
        getattr(config, "transparent", None),
    )
