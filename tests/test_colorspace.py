"""Unit tests for animageo.style.colorspace (manim-free color math)."""

import pytest

from animageo.style.colorspace import (
    normalize_hex, hex_to_oklab, oklab_to_hex, lerp_color,
)


class TestNormalizeHex:
    def test_lowercases_long_form(self):
        assert normalize_hex('#1565C0') == '#1565c0'

    def test_expands_short_form(self):
        assert normalize_hex('#abc') == '#aabbcc'

    @pytest.mark.parametrize('bad', [
        '1565c0', '#12345', '#gggggg', '#12345678', 42, None, 'red',
    ])
    def test_rejects_non_hex(self, bad):
        with pytest.raises(ValueError):
            normalize_hex(bad)


class TestOklabRoundTrip:
    @pytest.mark.parametrize('color', [
        '#000000', '#ffffff', '#ff0000', '#00ff00', '#0000ff',
        '#1565c0', '#d05456', '#808080', '#f6e0db',
    ])
    def test_round_trip_within_one_step(self, color):
        L, a, b = hex_to_oklab(color)
        back = oklab_to_hex(L, a, b)
        # allow ±1 per 8-bit channel for float→int rounding
        for i in (1, 3, 5):
            orig = int(color[i:i + 2], 16)
            got = int(back[i:i + 2], 16)
            assert abs(orig - got) <= 1

    def test_white_has_L_one(self):
        L, a, b = hex_to_oklab('#ffffff')
        assert L == pytest.approx(1.0, abs=1e-3)
        assert a == pytest.approx(0.0, abs=1e-3)
        assert b == pytest.approx(0.0, abs=1e-3)

    def test_black_has_L_zero(self):
        L, _a, _b = hex_to_oklab('#000000')
        assert L == pytest.approx(0.0, abs=1e-3)


class TestLerpColor:
    def test_endpoints_exact(self):
        assert lerp_color('#1565c0', '#d05456', 0.0) == '#1565c0'
        assert lerp_color('#1565c0', '#d05456', 1.0) == '#d05456'

    def test_normalizes_inputs(self):
        assert lerp_color('#ABC', '#abc', 0.0) == '#aabbcc'

    def test_oklab_midpoint_gray_between_black_and_white(self):
        mid = lerp_color('#000000', '#ffffff', 0.5, space='oklab')
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert abs(r - g) <= 1 and abs(g - b) <= 1   # achromatic
        # Oklab midpoint is perceptual middle gray: L=0.5 → sRGB ≈ 0x63;
        # sRGB-space lerp would give exactly 0x80 minus rounding.
        assert 0x60 <= r <= 0x90

    def test_srgb_space_naive_midpoint(self):
        mid = lerp_color('#000000', '#ffffff', 0.5, space='srgb')
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert (r, g, b) == (0x80, 0x80, 0x80) or (r, g, b) == (0x7f, 0x7f, 0x7f)

    def test_unknown_space_raises(self):
        with pytest.raises(ValueError):
            lerp_color('#000000', '#ffffff', 0.5, space='hsl')

    def test_result_is_valid_hex(self):
        mid = lerp_color('#1565c0', '#d05456', 0.3)
        assert normalize_hex(mid) == mid


def test_is_hex_color_predicate():
    from animageo.style.colorspace import is_hex_color
    assert is_hex_color('#1565c0') is True
    assert is_hex_color('#abc') is True
    assert is_hex_color('red') is False
    assert is_hex_color(None) is False
    assert is_hex_color(42) is False
