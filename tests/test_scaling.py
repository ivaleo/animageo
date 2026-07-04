"""Unit tests for animageo.style.scaling — named scaling functions.

Locks in the conversion formulas between GGB pixel space, JSON style space,
and manim internal units. Any drift here will also break
test_scaling_invariants.py and test_loadggb_snapshot.py.
"""
import math

import pytest

from animageo.style.scaling import (
    ggb_point_size_to_style,
    ggb_thickness_to_stroke_width,
    ggb_arc_size_px,
    ggb_label_offset_to_style,
    ggb_font_px_to_manim_fontsize,
    json_size_to_internal,
    json_line_width_to_internal,
    json_font_size_to_manim,
    stroke_width_to_manim,
)


class TestGgbPointSizeToStyle:
    @pytest.mark.parametrize('ggb,expected', [
        (3, 6), (4, 8), (5, 10), (0.5, 1.0),
    ])
    def test_values(self, ggb, expected):
        assert ggb_point_size_to_style(ggb) == expected


class TestGgbThicknessToStrokeWidth:
    @pytest.mark.parametrize('ggb,expected', [
        (4, 2.0), (5, 2.5), (10, 5.0), (1, 0.5),
    ])
    def test_values(self, ggb, expected):
        assert ggb_thickness_to_stroke_width(ggb) == expected


class TestGgbArcSizePx:
    def test_regular_angle(self):
        assert ggb_arc_size_px(30) == 30

    def test_right_angle_divides_by_sqrt_2(self):
        assert ggb_arc_size_px(30, right_angle=True) == pytest.approx(30 / math.sqrt(2))

    def test_right_angle_preserves_visual_diagonal(self):
        # After / sqrt(2), the bbox diagonal matches a regular arc of same size.
        arc = ggb_arc_size_px(20, right_angle=True)
        assert arc * math.sqrt(2) == pytest.approx(20)


class TestGgbLabelOffsetToStyle:
    def test_inverts_y(self):
        assert ggb_label_offset_to_style(4, 10) == [4, -10]

    def test_negative_x(self):
        assert ggb_label_offset_to_style(-28, 32) == [-28, -32]

    def test_zero(self):
        assert ggb_label_offset_to_style(0, 0) == [0, 0]


class TestGgbFontPxToManimFontsize:
    @pytest.mark.parametrize('px,ptUnit,expected', [
        (16, 50.0, 32.0),
        (12, 50.0, 24.0),
        (16, 100.0, 16.0),
        (16, 25.0, 64.0),
    ])
    def test_formula(self, px, ptUnit, expected):
        assert ggb_font_px_to_manim_fontsize(px, ptUnit) == expected

    def test_pixel_invariance(self):
        # Same (px, scaled_ptUnit) yields the same visual size.
        # If the canvas doubles in pixels, ptUnit stays proportional.
        px = 16
        a = ggb_font_px_to_manim_fontsize(px, 50.0)
        b = ggb_font_px_to_manim_fontsize(px, 100.0)
        # b is half a (canvas twice as big → manim unit relative smaller).
        assert a == 2 * b


class TestJsonSizeToInternal:
    @pytest.mark.parametrize('json,expected', [
        (10, 0.2),          # STYLE_TO_INTERNAL = 0.02
        (2.83, 0.0566),
        (6, 0.12),
    ])
    def test_values(self, json, expected):
        assert json_size_to_internal(json) == pytest.approx(expected)


class TestJsonLineWidthToInternal:
    @pytest.mark.parametrize('json,expected', [
        (1, 2), (0.75, 1.5), (2, 4),
    ])
    def test_values(self, json, expected):
        assert json_line_width_to_internal(json) == expected


class TestJsonFontSizeToManim:
    def test_known_value(self):
        # FONT_SIZE_RATIO = 50/25.9
        assert json_font_size_to_manim(10.5) == pytest.approx(10.5 * 50 / 25.9)

    def test_zero(self):
        assert json_font_size_to_manim(0) == 0


class TestStrokeWidthToManim:
    def test_formula(self):
        # stroke_width * 100 / ptUnit
        assert stroke_width_to_manim(2.5, 50.0) == 5.0

    def test_pixel_invariance(self):
        sw = 2.5
        a = stroke_width_to_manim(sw, 50.0)
        b = stroke_width_to_manim(sw, 100.0)
        assert a == 2 * b

    def test_accepts_string_input(self):
        # Historical callers pass float-convertible strings from JSON.
        assert stroke_width_to_manim('2.5', 50.0) == 5.0
