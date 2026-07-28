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

import contextlib
import functools
import logging

logger = logging.getLogger(__name__)

# Formats produced by the manim renderer (the "render track").
OUTPUT_FORMATS = ("png", "gif", "mp4", "webm", "mov")


@contextlib.contextmanager
def _pal8_gif_streams():
    """Coerce ``pix_fmt = "rgb8"`` writes on gif output streams to ``"pal8"``.

    Scoped patch of ``av.container.OutputContainer.add_stream``: streams
    created with the ``gif`` codec are wrapped in an attribute proxy that
    rewrites the one poisonous assignment and delegates everything else.
    Non-gif streams (partial movies, mp4/webm combining) are returned as-is.
    """
    import av

    orig_add_stream = av.container.OutputContainer.add_stream

    class _Pal8GifStream:
        __slots__ = ("_stream",)

        def __init__(self, stream):
            object.__setattr__(self, "_stream", stream)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_stream"), name)

        def __setattr__(self, name, value):
            if name == "pix_fmt" and value == "rgb8":
                value = "pal8"
            setattr(object.__getattribute__(self, "_stream"), name, value)

    def add_stream(self, codec_name=None, *args, **kwargs):
        stream = orig_add_stream(self, codec_name, *args, **kwargs)
        if getattr(codec_name, "name", codec_name) == "gif":
            return _Pal8GifStream(stream)
        return stream

    patched = False
    try:
        av.container.OutputContainer.add_stream = add_stream
        patched = True
    except (AttributeError, TypeError):  # cython build refusing monkeypatch
        logger.warning(
            "GIF palette fix could not patch pyav; GIF colors may be off"
        )
    try:
        yield
    finally:
        if patched:
            av.container.OutputContainer.add_stream = orig_add_stream


def install_gif_palette_fix():
    """Keep manim's GIF export on the palettegen palette (pal8, not rgb8).

    manim (0.19–0.21) builds GIFs by piping frames through a palettegen/
    paletteuse filter graph — which emits pal8 frames carrying the adaptive
    256-color palette — but then declares the output stream as ``pix_fmt
    "rgb8"`` (a *fixed* 3-3-2 RGB grid) unless ``transparent`` is on. Encoding
    the pal8 frames into that stream discards the adaptive palette, and colors
    scramble catastrophically: dark blue renders as pure yellow, fills break
    into green/yellow dithered patches. Measured on a real scene, mean
    per-pixel error vs the MP4 render drops from ~6/255 to ~0.5/255 (p99:
    85 → 2) with the fix, and the file shrinks ~4×.

    Wraps ``SceneFileWriter.combine_files`` so that, for its duration, gif
    output streams keep ``pal8``. Idempotent (marker attribute on the
    wrapper); a no-op for manim versions that stop assigning rgb8. Installed
    once from ``AnimaGeoScene.__init__``.

    Returns:
        True if the wrap is in place afterwards, False if manim is missing.
    """
    try:
        from manim.scene.scene_file_writer import SceneFileWriter
    except ImportError:
        return False

    if getattr(SceneFileWriter.combine_files, "_animageo_gif_palette_fix", False):
        return True

    orig = SceneFileWriter.combine_files

    @functools.wraps(orig)
    def combine_files(self, *args, **kwargs):
        with _pal8_gif_streams():
            return orig(self, *args, **kwargs)

    combine_files._animageo_gif_palette_fix = True
    SceneFileWriter.combine_files = combine_files
    logger.debug("GIF palette fix installed (combine_files wrapped)")
    return True


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
