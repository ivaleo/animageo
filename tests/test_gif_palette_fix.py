"""Tests for the GIF palette fix (animageo.render_config.install_gif_palette_fix).

manim (0.19–0.21) builds GIFs through a palettegen/paletteuse filter graph —
which emits pal8 frames carrying an adaptive 256-color palette — but declares
the output stream as ``pix_fmt "rgb8"`` (a fixed 3-3-2 RGB grid) unless
``transparent`` is on. Re-encoding the pal8 frames into rgb8 discards the
adaptive palette and scrambles colors (dark blue renders as yellow/green with
dithered speckle). The fix wraps ``SceneFileWriter.combine_files`` so gif
streams keep ``pal8``.
"""
import contextlib
import importlib.util

import pytest

_HAS_MANIM = importlib.util.find_spec("manim") is not None
_HAS_AV = importlib.util.find_spec("av") is not None

needs_av = pytest.mark.skipif(not _HAS_AV, reason="requires pyav")
needs_manim = pytest.mark.skipif(not _HAS_MANIM, reason="requires manim")


# The fixed 3-3-2 palette rgb8 quantizes to: R and G on multiples of 36,
# B on multiples of 85.
def _on_332_grid(r, g, b):
    return r % 36 == 0 and g % 36 == 0 and b % 85 == 0


@needs_av
def test_gif_stream_rgb8_coerced_to_pal8(tmp_path):
    import av

    from animageo.render_config import _pal8_gif_streams

    with _pal8_gif_streams():
        out = av.open(str(tmp_path / "t.gif"), mode="w")
        stream = out.add_stream(codec_name="gif")
        stream.pix_fmt = "rgb8"
        assert stream.pix_fmt == "pal8"
        # other attribute writes pass through untouched
        stream.width = 64
        stream.height = 48
        assert stream.width == 64
        with contextlib.suppress(Exception):
            out.close()


@needs_av
def test_gif_stream_pal8_kept(tmp_path):
    import av

    from animageo.render_config import _pal8_gif_streams

    with _pal8_gif_streams():
        out = av.open(str(tmp_path / "t.gif"), mode="w")
        stream = out.add_stream(codec_name="gif")
        stream.pix_fmt = "pal8"  # the transparent path — must stay pal8
        assert stream.pix_fmt == "pal8"
        with contextlib.suppress(Exception):
            out.close()


@needs_av
def test_non_gif_stream_untouched(tmp_path):
    import av

    from animageo.render_config import _pal8_gif_streams

    with _pal8_gif_streams():
        out = av.open(str(tmp_path / "t.mp4"), mode="w")
        stream = out.add_stream(codec_name="libx264")
        stream.pix_fmt = "yuv420p"
        assert stream.pix_fmt == "yuv420p"
        with contextlib.suppress(Exception):
            out.close()


@needs_av
def test_add_stream_restored_after_context():
    import av

    from animageo.render_config import _pal8_gif_streams

    orig = av.container.OutputContainer.add_stream
    with _pal8_gif_streams():
        assert av.container.OutputContainer.add_stream is not orig
    assert av.container.OutputContainer.add_stream is orig


@needs_av
def test_add_stream_restored_after_exception():
    import av

    from animageo.render_config import _pal8_gif_streams

    orig = av.container.OutputContainer.add_stream
    with pytest.raises(RuntimeError):
        with _pal8_gif_streams():
            raise RuntimeError("boom")
    assert av.container.OutputContainer.add_stream is orig


@needs_manim
def test_install_wraps_combine_files_idempotently():
    from manim.scene.scene_file_writer import SceneFileWriter

    from animageo.render_config import install_gif_palette_fix

    assert install_gif_palette_fix() is True
    wrapped = SceneFileWriter.combine_files
    assert getattr(wrapped, "_animageo_gif_palette_fix", False)
    # second install is a no-op — no double wrapping
    assert install_gif_palette_fix() is True
    assert SceneFileWriter.combine_files is wrapped


@needs_manim
def test_scene_init_installs_fix():
    from manim.scene.scene_file_writer import SceneFileWriter

    from animageo import AnimaGeoScene

    AnimaGeoScene()
    assert getattr(
        SceneFileWriter.combine_files, "_animageo_gif_palette_fix", False
    )


@needs_manim
def test_gif_render_preserves_colors(tmp_path):
    """End-to-end: a dark-blue square on white must stay blue in the GIF.

    Without the fix the adaptive palette is discarded: the file carries the
    fixed 3-3-2 grid palette, the square renders yellow/green and virtually
    every pixel sits exactly on the grid. With the fix the palette is
    adaptive (white itself — (255,255,255) — is off-grid) and colors match.
    """
    import numpy as np
    from manim import Scene, Square, tempconfig
    from PIL import Image

    from animageo.render_config import install_gif_palette_fix

    install_gif_palette_fix()

    class GifColorScene_(Scene):
        def construct(self):
            self.camera.background_color = "#ffffff"
            sq = Square(side_length=2.5)
            sq.set_fill("#1565c0", opacity=1.0).set_stroke("#1565c0")
            self.add(sq)
            self.wait(0.4)

    with tempconfig({
        "format": "gif",
        "pixel_width": 192,
        "pixel_height": 108,
        "frame_rate": 5,
        "media_dir": str(tmp_path),
        "verbosity": "ERROR",
        "progress_bar": "none",
    }):
        GifColorScene_().render()

    gifs = list(tmp_path.rglob("*.gif"))
    assert gifs, "manim produced no gif"
    arr = np.asarray(Image.open(gifs[0]).convert("RGB")).astype(int)
    h, w, _ = arr.shape

    # With the adaptive palette the fill is reproduced within ±2 per channel;
    # the fixed 3-3-2 grid can't get closer than ~22 on this blue.
    center = arr[h // 2, w // 2]
    target = np.array([21, 101, 192])  # #1565c0
    assert np.abs(center - target).max() <= 10, (
        f"square fill off: center={tuple(center)}, want ~{tuple(target)}"
    )

    corner = arr[2, 2]
    assert corner.min() > 200, f"background not near-white: corner={tuple(corner)}"

    on_grid = sum(
        _on_332_grid(r, g, b) for r, g, b in map(tuple, arr.reshape(-1, 3))
    )
    frac = on_grid / (h * w)
    assert frac < 0.5, (
        f"{frac:.0%} of pixels sit exactly on the fixed 3-3-2 palette grid — "
        "the adaptive palettegen palette was discarded"
    )
