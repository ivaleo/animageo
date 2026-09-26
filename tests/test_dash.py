"""Dash pattern core (animageo/dash.py) — manim-free math."""
import math

import numpy as np
import pytest

from animageo.dash import (
    DEFAULT_DASH_PERIOD_PX,
    DashPattern,
    apply_cairo_dash,
    dash_pattern,
    dash_period_px,
    dash_ratio,
    get_dash,
    path_length,
    set_dash,
)


class TestRatioAndPeriod:
    @pytest.mark.parametrize('value', [None, 0, 0.0, -0.3, 1, 1.5, 'x', True, float('nan')])
    def test_solid_ratios(self, value):
        assert dash_ratio(value) is None

    @pytest.mark.parametrize('value', [0.65, '0.4', 0.01])
    def test_dashed_ratios(self, value):
        assert dash_ratio(value) == pytest.approx(float(value))

    def test_period_value_wins(self):
        assert dash_period_px(14, 12) == 14

    @pytest.mark.parametrize('bad', [None, 0, -5, 'abc', True, float('inf')])
    def test_invalid_period_falls_back_to_rendering(self, bad):
        assert dash_period_px(bad, 12) == 12

    def test_invalid_rendering_falls_back_to_default(self):
        assert dash_period_px(None, 0) == DEFAULT_DASH_PERIOD_PX == 10.0
        assert dash_period_px('x', 'y') == 10.0


class TestFit:
    def test_nominal_without_fit(self):
        p = dash_pattern(3.3, 0.65, 0.35)
        assert (p.on, p.off, p.offset) == (0.65, 0.35, 0.0)

    @pytest.mark.parametrize('length', [0.4, 1.0, 3.3, 7.77, 25.0])
    def test_open_path_dash_on_both_ends(self, length):
        dash, gap = 0.65, 0.35
        p = dash_pattern(length, dash, gap, fit_ends=True)
        n = max(1, round((length + gap) / (dash + gap)))
        assert n * p.on + (n - 1) * p.off == pytest.approx(length, abs=1e-6)
        assert p.on / p.off == pytest.approx(dash / gap)
        assert p.offset == 0.0

    @pytest.mark.parametrize('length', [2 * math.pi * 0.3, 2 * math.pi, 31.4])
    def test_closed_path_whole_periods(self, length):
        p = dash_pattern(length, 0.65, 0.35, closed=True)
        k = length / p.period
        assert k == pytest.approx(round(k), abs=1e-9)
        assert round(k) >= 1

    def test_fit_changes_little_on_long_paths(self):
        p = dash_pattern(100.0, 0.65, 0.35, fit_ends=True)
        assert p.on == pytest.approx(0.65, rel=0.01)

    def test_phase_kept_for_unfitted_paths(self):
        p = dash_pattern(10, 0.6, 0.4, phase_mu=2.3)
        assert p.offset == pytest.approx(0.3)


class TestCaps:
    def test_round_cap_visible_dash_is_nominal(self):
        w = 0.1
        p = dash_pattern(0, 0.65, 0.35, cap_extent_mu=w)
        assert p.on + w == pytest.approx(0.65)
        assert p.period == pytest.approx(1.0)
        # the drawn dash is centred on the nominal one: it starts w/2 later
        assert p.offset == pytest.approx(1.0 - w / 2)

    def test_cap_wider_than_dash(self):
        p = dash_pattern(0, 0.05, 0.95, cap_extent_mu=0.2)
        assert 0 < p.on <= 1e-6
        assert p.period == pytest.approx(1.0)

    def test_fit_then_caps_keeps_both_ends_visible(self):
        L, w = 5.0, 0.08
        p = dash_pattern(L, 0.65, 0.35, fit_ends=True, cap_extent_mu=w)
        n = max(1, round((L + 0.35) / 1.0))
        # first dash drawn from w/2, last one ends at L - w/2 (+ cap = L)
        first_start = (p.period - p.offset) % p.period
        assert first_start == pytest.approx(w / 2)
        last_end = first_start + (n - 1) * p.period + p.on
        assert last_end + w / 2 == pytest.approx(L)


class TestPathLength:
    def test_straight_line_exact(self):
        a, b = np.array([0.0, 0, 0]), np.array([3.0, 4, 0])
        pts = np.array([a, a + (b - a) / 3, a + 2 * (b - a) / 3, b])
        assert path_length(pts) == pytest.approx(5.0)

    def test_empty(self):
        assert path_length(np.zeros((0, 3))) == 0.0

    def test_circle(self):
        from manim import Circle
        assert path_length(Circle(radius=2).points) == pytest.approx(4 * math.pi, rel=1e-4)


class _Ctx:
    def __init__(self):
        self.calls = []

    def set_dash(self, dashes, offset=0.0):
        self.calls.append((list(dashes), offset))


class TestAttach:
    def test_set_get_roundtrip_and_clear(self):
        from manim import Line
        ln = Line()
        assert get_dash(ln) is None
        pat = DashPattern(0.2, 0.1, 0.05)
        set_dash(ln, pat)
        assert get_dash(ln) == pat
        assert get_dash(ln.copy()) == pat      # survives copy()
        set_dash(ln, None)
        assert get_dash(ln) is None
        set_dash(ln, None)                     # idempotent

    def test_apply_cairo_dash(self):
        from manim import Line
        ln = Line()
        ctx = _Ctx()
        assert apply_cairo_dash(ctx, ln) is False
        set_dash(ln, DashPattern(0.2, 0.1, 0.05))
        assert apply_cairo_dash(ctx, ln) is True
        assert ctx.calls == [([], 0.0), ([0.2, 0.1], 0.05)]
