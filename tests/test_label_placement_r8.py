"""Round-8 continuous (non-octant) placement.

The 8-direction solver quantises every label to a 45° octant, so it can settle
for an overlapping octant when a FREE angle exists between two octants. Sweeping
N angles with a continuous direction penalty finds that free angle and lands the
label at its exact resolved direction, with no proximity cost.
"""
import math
import numpy as np
import pytest

from animageo.label_placement import (
    _octant_angle_dist,
    _generate_candidates_continuous,
    _nearest_dir_index,
    compute_label_layout,
)


def _ang(v):
    return math.degrees(math.atan2(v[1], v[0])) % 360


class TestOctantAngleDist:
    def test_zero_when_aligned(self):
        assert _octant_angle_dist(1.0, 1.0) == pytest.approx(0.0)

    def test_one_octant_is_unit(self):
        # 45° apart == 1.0 octant unit (same scale as the discrete penalty)
        assert _octant_angle_dist(0.0, math.pi / 4) == pytest.approx(1.0)

    def test_wraps_around(self):
        # 350° vs 10° is 20° apart, not 340°
        d = _octant_angle_dist(math.radians(350), math.radians(10))
        assert d == pytest.approx(20.0 / 45.0, abs=1e-6)

    def test_opposite_is_four(self):
        assert _octant_angle_dist(0.0, math.pi) == pytest.approx(4.0)


class TestContinuousCandidates:
    def test_count_and_extra(self):
        a = np.array([0.0, 0.0])
        out = _generate_candidates_continuous(a, 1.0, 8)
        assert len(out) == 8
        out2 = _generate_candidates_continuous(a, 1.0, 8, extra_angle=0.1)
        assert len(out2) == 9

    def test_center_on_circle_and_octant_idx(self):
        a = np.array([2.0, 3.0])
        out = _generate_candidates_continuous(a, 5.0, 4)  # 0,90,180,270
        for c, di, ang in out:
            assert np.hypot(c[0] - 2.0, c[1] - 3.0) == pytest.approx(5.0)
            assert di == _nearest_dir_index(c - a)


def _scene_blocked():
    """Point B at a crossing where the octant left/up directions are blocked by
    a line, but an off-octant angle is free."""
    from animageo.animageo import AnimaGeoScene
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                            'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
    sc.putCode("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
    for n in ('A', 'B', 'C'):
        sc.element(n).style['label_visible'] = True
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return sc


class TestContinuousIntegration:
    def test_off_by_default_matches_octant(self):
        sc = _scene_blocked()
        oct_ = compute_label_layout(sc, cfg={'enabled': True, 'point_bisector': True})
        cont = compute_label_layout(sc, cfg={'enabled': True, 'point_bisector': True,
                                             'continuous_placement': False})
        for k in oct_:
            assert np.allclose(oct_[k].offset_ggb, cont[k].offset_ggb)

    def test_continuous_lands_off_octant(self):
        """With a bisector hint at a non-octant angle, continuous placement lands
        the label at that angle instead of snapping to the nearest 45°."""
        sc = _scene_blocked()
        # bias B's label toward 20° (between E=0° and NE=45°)
        sc.element('B').style['label_offset_px'] = [3.0, 1.09]   # ~20°
        cont = compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'continuous_placement': True, 'continuous_steps': 72})
        a = _ang(cont['B'].offset_ggb)
        # not snapped to 0 or 45 — sits near the resolved 20°
        assert min(abs(a - 0), abs(a - 45)) > 8.0
