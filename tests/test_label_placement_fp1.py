"""FP-1: labels clear the point marker (size-aware gap), corner anchors for
diagonals, and respected positions get pushed out (not relocated). Pure.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    LabelCostModel,
    LabelInfo,
    _DIR_TO_ANCHOR,
    _circle_bbox_intersects,
    _push_clear_of_marker,
    _solve_greedy,
)

EMPTY = np.empty((0, 2))


class TestCornerAnchors:
    def test_diagonals_use_corner_anchors(self):
        # idx: E NE N NW W SW S SE
        assert _DIR_TO_ANCHOR == ['ML', 'BL', 'BC', 'BR', 'MR', 'TR', 'TC', 'TL']
        for diag in (1, 3, 5, 7):
            assert _DIR_TO_ANCHOR[diag] in ('BL', 'BR', 'TR', 'TL')
        for card in (0, 2, 4, 6):
            assert _DIR_TO_ANCHOR[card] in ('ML', 'BC', 'MR', 'TC')


class TestPushClearOfMarker:
    def test_pushes_out_along_direction(self):
        anchor = np.array([0.0, 0.0])
        c = _push_clear_of_marker(np.array([0.2, 0.0]), anchor, 1.0, 0.3, 0.2, 1.0)
        assert not _circle_bbox_intersects(0, 0, 1.0, c[0], c[1], 0.3, 0.2)
        assert c[0] > 0  # same (right) direction preserved

    def test_diagonal_direction_preserved(self):
        anchor = np.array([0.0, 0.0])
        c = _push_clear_of_marker(np.array([0.1, 0.1]), anchor, 1.0, 0.3, 0.2, 1.0)
        assert c[0] > 0 and c[1] > 0
        assert c[1] / c[0] == pytest.approx(1.0)  # stayed on the diagonal

    def test_already_clear_unchanged(self):
        anchor = np.array([0.0, 0.0])
        c = _push_clear_of_marker(np.array([5.0, 0.0]), anchor, 1.0, 0.3, 0.2, 1.0)
        assert np.allclose(c, [5.0, 0.0])


class TestKeepClearsOwnMarker:
    def test_respected_tight_position_is_pushed_out(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.3, half_h=0.2)
        lbl.current_center = np.array([0.15, 0.0])  # sitting on its own marker
        lbl.clear_radius = 1.0
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0,
                           ptUnit=1.0, w_inertia=2.0)
        res = _solve_greedy([lbl], [], [], EMPTY, 0.2, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=m,
                            respect_current=True, keep_current_if_free=True)
        c = res[0][1]
        assert not _circle_bbox_intersects(0, 0, 1.0, c[0], c[1], 0.3, 0.2)
        assert c[0] > 0  # kept on the same side, just pushed out

    def test_clear_respected_position_is_kept(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.current_center = np.array([3.0, 0.0])  # already well clear
        lbl.clear_radius = 1.0
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0, ptUnit=1.0)
        res = _solve_greedy([lbl], [], [], EMPTY, 0.2, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=m,
                            respect_current=True, keep_current_if_free=True)
        assert np.allclose(res[0][1], [3.0, 0.0])
