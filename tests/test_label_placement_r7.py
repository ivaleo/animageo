"""Round-7 principle terms:

P-ASSOC — a label must read as belonging to ITS object: never sit closer to a
different labelled point than to its own anchor (``w_assoc``).

P-DASHED — when an overlap is unavoidable, crossing a DASHED line is preferable
to a solid one (``dashed_overlap_factor`` / ``seg_dashed``). A free placement
still always beats any overlap, so this only ranks forced overlaps.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    LabelCostModel,
    _score_candidate,
)

EMPTY = np.empty((0, 2))
W = (1.0, 10.0, 8.0)


class TestAssoc:
    def test_penalises_closer_to_other_anchor(self):
        m = LabelCostModel(weights=W, padding=0.0, ptUnit=1.0, w_assoc=5.0,
                           anchors=np.array([[0.0, 0.0], [1.0, 0.0]]))
        own = np.array([0.0, 0.0])
        near_other = m.candidate_cost(np.array([0.9, 0.0]), 0.05, 0.05,
                                      [], [], [], EMPTY, 0, 0, own_anchor=own)
        near_own = m.candidate_cost(np.array([0.1, 0.0]), 0.05, 0.05,
                                    [], [], [], EMPTY, 0, 0, own_anchor=own)
        assert near_other > near_own

    def test_no_penalty_when_nearest_is_own(self):
        m = LabelCostModel(weights=W, padding=0.0, ptUnit=1.0, w_assoc=5.0,
                           anchors=np.array([[0.0, 0.0], [5.0, 0.0]]))
        own = np.array([0.0, 0.0])
        # candidate hugs its own anchor, far from the other → no assoc penalty
        c = m.candidate_cost(np.array([0.2, 0.0]), 0.05, 0.05,
                             [], [], [], EMPTY, 0, 0, own_anchor=own)
        assert c == pytest.approx(0.0)

    def test_off_by_default(self):
        m = LabelCostModel(weights=W, padding=0.0, ptUnit=1.0)  # w_assoc=0
        own = np.array([0.0, 0.0])
        c = m.candidate_cost(np.array([0.9, 0.0]), 0.05, 0.05,
                             [], [], [], EMPTY, 0, 0, own_anchor=own,
                             )
        assert c == pytest.approx(0.0)


class TestDashed:
    SEG = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]  # horizontal line

    def test_dashed_overlap_cheaper_than_solid(self):
        solid = _score_candidate([0.0, 0.0], 0.3, 0.2, 0.0, [], self.SEG, [],
                                 EMPTY, 0, 0, W,
                                 seg_dashed=[False], dashed_factor=0.3)
        dashed = _score_candidate([0.0, 0.0], 0.3, 0.2, 0.0, [], self.SEG, [],
                                  EMPTY, 0, 0, W,
                                  seg_dashed=[True], dashed_factor=0.3)
        assert dashed < solid
        # geom term scaled by the factor (dir penalty is 0 here)
        assert dashed == pytest.approx(solid * 0.3)

    def test_factor_one_is_unchanged(self):
        a = _score_candidate([0.0, 0.0], 0.3, 0.2, 0.0, [], self.SEG, [], EMPTY,
                             0, 0, W)
        b = _score_candidate([0.0, 0.0], 0.3, 0.2, 0.0, [], self.SEG, [], EMPTY,
                             0, 0, W, seg_dashed=[True], dashed_factor=1.0)
        assert a == pytest.approx(b)

    def test_free_still_beats_dashed_overlap(self):
        # a candidate clear of the line costs less than one crossing a dashed line
        overlap = _score_candidate([0.0, 0.0], 0.3, 0.2, 0.0, [], self.SEG, [],
                                   EMPTY, 0, 0, W,
                                   seg_dashed=[True], dashed_factor=0.3)
        free = _score_candidate([0.0, 5.0], 0.3, 0.2, 0.0, [], self.SEG, [],
                                EMPTY, 0, 0, W,
                                seg_dashed=[True], dashed_factor=0.3)
        assert free < overlap
