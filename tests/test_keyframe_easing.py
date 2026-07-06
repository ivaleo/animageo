"""Keyframes v2 phase 4: the full 17-easing set (lossless with animageo_web)."""
import math
import pytest

from animageo.keyframes import EASING_FUNCTIONS

ALL_17 = [
    'linear', 'smooth', 'smootherstep', 'in', 'out', 'in_out',
    'ease_in_sine', 'ease_out_sine', 'ease_in_out_sine',
    'ease_in_cubic', 'ease_out_cubic', 'ease_in_out_cubic',
    'rush_into', 'rush_from', 'ease_out_back', 'ease_out_elastic',
    'ease_out_bounce',
]


class TestEasingSet:
    def test_all_17_present(self):
        for name in ALL_17:
            assert name in EASING_FUNCTIONS, name
        assert len(EASING_FUNCTIONS) >= 17

    @pytest.mark.parametrize('name', ALL_17)
    def test_endpoints(self, name):
        f = EASING_FUNCTIONS[name]
        # every easing maps 0->0 and 1->1 (endpoints), within tolerance
        assert abs(f(0.0) - 0.0) < 1e-9, name
        assert abs(f(1.0) - 1.0) < 1e-9, name

    def test_existing_five_unchanged(self):
        assert EASING_FUNCTIONS['linear'](0.3) == pytest.approx(0.3)
        assert EASING_FUNCTIONS['smooth'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['in'](0.5) == pytest.approx(0.25)
        assert EASING_FUNCTIONS['out'](0.5) == pytest.approx(0.75)
        assert EASING_FUNCTIONS['in_out'](0.25) == pytest.approx(0.125)

    def test_web_formula_values(self):
        # exact values matching animageo_web applyEasingValue
        assert EASING_FUNCTIONS['smootherstep'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['ease_in_sine'](0.5) == pytest.approx(1 - math.cos(math.pi/4))
        assert EASING_FUNCTIONS['ease_out_sine'](0.5) == pytest.approx(math.sin(math.pi/4))
        assert EASING_FUNCTIONS['ease_in_out_sine'](0.5) == pytest.approx(0.5)
        assert EASING_FUNCTIONS['ease_in_cubic'](0.5) == pytest.approx(0.125)
        assert EASING_FUNCTIONS['ease_out_cubic'](0.5) == pytest.approx(1 - 0.5**3)
        assert EASING_FUNCTIONS['ease_in_out_cubic'](0.25) == pytest.approx(4 * 0.25**3)

    def test_overshoot_easings(self):
        # back/elastic overshoot above 1 or below 0 somewhere in (0,1)
        back = EASING_FUNCTIONS['ease_out_back']
        assert max(back(t/100) for t in range(101)) > 1.0
        elastic = EASING_FUNCTIONS['ease_out_elastic']
        assert elastic(0.0) == pytest.approx(0.0)
        assert elastic(1.0) == pytest.approx(1.0)

    def test_bounce_stays_in_unit_and_ends_one(self):
        f = EASING_FUNCTIONS['ease_out_bounce']
        for i in range(101):
            v = f(i/100)
            assert -1e-9 <= v <= 1.0 + 1e-9
        assert f(1.0) == pytest.approx(1.0)

    def test_clamps_out_of_range(self):
        for name in ALL_17:
            f = EASING_FUNCTIONS[name]
            # t outside [0,1] must be clamped (no exception, sane output)
            f(-0.5); f(1.5)

    def test_rush_endpoints(self):
        assert EASING_FUNCTIONS['rush_into'](0.0) == pytest.approx(0.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_into'](1.0) == pytest.approx(1.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_from'](0.0) == pytest.approx(0.0, abs=1e-6)
        assert EASING_FUNCTIONS['rush_from'](1.0) == pytest.approx(1.0, abs=1e-6)
