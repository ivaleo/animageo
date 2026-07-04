"""Tests for P1-D: respecting an existing manual/GGB label position
(keep-if-free, inertia toward current, no needless side-flip). Pure-geometry.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    LabelCostModel,
    LabelInfo,
    _generate_candidates,
    _nearest_dir_index,
    _solve_greedy,
)

EMPTY = np.empty((0, 2))


class TestInertiaTerm:
    def test_zero_at_current_grows_with_distance(self):
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=3.0)
        cur = np.array([0.0, 0.0])
        at = m.candidate_cost(np.array([0.0, 0.0]), 0.1, 0.1, [], [], [], EMPTY,
                              0, 0, current_center=cur)
        far = m.candidate_cost(np.array([5.0, 0.0]), 0.1, 0.1, [], [], [], EMPTY,
                               0, 0, current_center=cur)
        assert at == pytest.approx(0.0)
        assert far == pytest.approx(3.0 * 5.0)

    def test_no_current_means_no_inertia(self):
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=3.0)
        c = m.candidate_cost(np.array([5.0, 0.0]), 0.1, 0.1, [], [], [], EMPTY, 0, 0)
        assert c == pytest.approx(0.0)

    def test_inertia_scales_with_ptUnit(self):
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0,
                           ptUnit=10.0, w_inertia=1.0)
        cur = np.array([0.0, 0.0])
        c = m.candidate_cost(np.array([2.0, 0.0]), 0.1, 0.1, [], [], [], EMPTY,
                             0, 0, current_center=cur)
        assert c == pytest.approx(1.0 * 2.0 * 10.0)  # px = scene*ptUnit


class TestKeepCurrentIfFree:
    def test_collision_free_current_is_kept_verbatim(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.current_center = np.array([0.5, 0.5])  # free, away from anything
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=2.0)
        res = _solve_greedy([lbl], [], [], EMPTY, 0.2, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=m,
                            respect_current=True, keep_current_if_free=True)
        assert np.allclose(res[0][1], lbl.current_center)

    def test_keeps_manual_side_against_base_preference(self):
        # Both sides of the line are free; base preference points LEFT, but the
        # manual position is on the RIGHT — respect must keep it on the right.
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.3, half_h=0.2)
        lbl.preferred_dir = 4  # W / left
        lbl.current_center = np.array([0.7, 0.0])  # right, clear of the line
        seg = [(np.array([0.0, -5.0]), np.array([0.0, 5.0]))]  # vertical line x=0
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=3.0)
        res = _solve_greedy([lbl], seg, [], EMPTY, 0.5, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=m,
                            respect_current=True, keep_current_if_free=True)
        assert res[0][1][0] > 0  # stayed on the right side


class TestInertiaSearchWhenCurrentBlocked:
    def test_moves_to_nearest_free_side(self):
        # Current overlaps the line → must move. With w_anchor=0 the only driver
        # is inertia, which picks the closer free candidate (right, near current)
        # rather than flipping to the far side.
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.3, half_h=0.2)
        lbl.current_center = np.array([0.2, 0.0])  # overlaps line x=0
        seg = [(np.array([0.0, -5.0]), np.array([0.0, 5.0]))]
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=3.0)
        res = _solve_greedy([lbl], seg, [], EMPTY, 0.5, 0.0, (0.0, 10.0, 8.0),
                            1.0, cost_model=m,
                            respect_current=True, keep_current_if_free=True)
        cx = res[0][1][0]
        assert cx > 0          # stayed on the same (right) side
        # and it is a genuine move (current was blocked), not the blocked current
        assert not np.allclose(res[0][1], lbl.current_center)


class TestNearestDirIndex:
    @pytest.mark.parametrize("vec,idx", [
        ((1, 0), 0), ((1, 1), 1), ((0, 1), 2), ((-1, 1), 3),
        ((-1, 0), 4), ((-1, -1), 5), ((0, -1), 6), ((1, -1), 7),
    ])
    def test_snaps_to_eight(self, vec, idx):
        assert _nearest_dir_index(np.array(vec, dtype=float)) == idx


class TestRespectOffByDefault:
    def test_without_respect_ignores_current(self):
        # respect_current=False → current_center must not influence placement;
        # result equals the plain greedy choice (here: preferred_dir candidate).
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 1
        lbl.current_center = np.array([-0.5, 0.0])  # would pull left if respected
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0, ptUnit=1.0)
        res = _solve_greedy([lbl], [], [], EMPTY, 0.5, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=m, respect_current=False)
        expected = _generate_candidates(lbl.anchor, 0.5)[1]  # NE, preferred
        assert np.allclose(res[0][1], expected)
