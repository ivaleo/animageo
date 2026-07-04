"""Tests for animageo.render_config.configure_render.

Validation is dependency-free (no manim needed to reject a bad format); the
config-mutation test is guarded on manim availability.
"""
import importlib.util

import pytest

from animageo.render_config import configure_render, OUTPUT_FORMATS

_HAS_MANIM = importlib.util.find_spec("manim") is not None


def test_output_formats_membership():
    assert set(OUTPUT_FORMATS) == {"png", "gif", "mp4", "webm", "mov"}


def test_invalid_format_raises():
    with pytest.raises(ValueError):
        configure_render(format="tiff")


def test_invalid_format_with_leading_dot_raises():
    with pytest.raises(ValueError):
        configure_render(format=".jpeg")


@pytest.mark.skipif(not _HAS_MANIM, reason="requires manim")
def test_sets_manim_config():
    from manim import config
    saved = (config.format, config.frame_rate)
    try:
        configure_render(format="gif")
        assert config.format == "gif"
        configure_render(format=".webm", fps=30)
        assert config.format == "webm"
        assert config.frame_rate == 30
    finally:
        config.format, config.frame_rate = saved
