"""FP-2 (geometry clearance gap) and FP-4 (keep a respected label in its sector
by pushing it out, not relocating). Pure-geometry.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    LabelCostModel,
    _candidate_has_overlap,
    _push_clear_along,
    _score_candidate,
)

EMPTY = np.empty((0, 2))
VLINE = [(np.array([0.0, -5.0]), np.array([0.0, 5.0]))]  # vertical line x=0


class TestGeomGapScoring:
    def test_near_miss_free_without_gap(self):
        # bbox at x∈[0.2,0.8] does not cross the line at x=0
        c = _score_candidate([0.5, 0.0], 0.3, 0.2, 0.0, [], VLINE, [], EMPTY,
                             0, 0, (0.0, 10.0, 8.0))
        assert c == pytest.approx(0.0)

    def test_near_miss_penalised_with_gap(self):
        c = _score_candidate([0.5, 0.0], 0.3, 0.2, 0.0, [], VLINE, [], EMPTY,
                             0, 0, (0.0, 10.0, 8.0), geom_gap=0.5)
        assert c > 0  # inflated bbox now reaches the line

    def test_geom_gap_does_not_affect_label_label(self):
        placed = [(np.array([0.5, 0.0]), 0.3, 0.2)]  # another label, not geometry
        a = _score_candidate([0.5, 0.0], 0.3, 0.2, 0.0, placed, [], [], EMPTY,
                             0, 0, (0.0, 10.0, 8.0), geom_gap=0.0)
        b = _score_candidate([0.5, 0.0], 0.3, 0.2, 0.0, placed, [], [], EMPTY,
                             0, 0, (0.0, 10.0, 8.0), geom_gap=0.5)
        assert a == b  # label-label term ignores geom_gap


class TestGeomGapOverlapHelper:
    def test_near_miss_flagged_with_gap(self):
        assert not _candidate_has_overlap([0.5, 0.0], 0.3, 0.2, VLINE, [], EMPTY)
        assert _candidate_has_overlap([0.5, 0.0], 0.3, 0.2, VLINE, [], EMPTY,
                                      geom_gap=0.5)


class TestCostModelGeomGap:
    def test_model_threads_geom_gap(self):
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0, geom_gap=0.5)
        on = m.candidate_cost([0.5, 0.0], 0.3, 0.2, [], VLINE, [], EMPTY, 0, 0)
        m0 = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0, geom_gap=0.0)
        off = m0.candidate_cost([0.5, 0.0], 0.3, 0.2, [], VLINE, [], EMPTY, 0, 0)
        assert on > off == pytest.approx(0.0)


class TestPushClearAlong:
    def test_pushes_out_along_direction_to_clear_segment(self):
        anchor = np.array([0.0, 0.0])
        seg = [(np.array([0.3, -5.0]), np.array([0.3, 5.0]))]  # line at x=0.3
        c, ok = _push_clear_along(np.array([0.3, 0.0]), anchor, 0.0, 0.2, 0.1,
                                  seg, [], EMPTY, [], 1.0, max_extra=5.0)
        assert ok
        assert c[0] > 0.5          # pushed right past the line
        assert c[1] == pytest.approx(0.0)  # direction preserved

    def test_reports_failure_when_cannot_clear_in_cap(self):
        anchor = np.array([0.0, 0.0])
        # bbox starts on the line and the cap is too small to step off it
        c, ok = _push_clear_along(np.array([0.05, 0.0]), anchor, 0.0, 0.3, 0.2,
                                  VLINE, [], EMPTY, [], 100.0, max_extra=0.01)
        assert not ok

    def test_already_clear_returns_immediately(self):
        anchor = np.array([0.0, 0.0])
        c, ok = _push_clear_along(np.array([5.0, 0.0]), anchor, 0.0, 0.2, 0.1,
                                  VLINE, [], EMPTY, [], 1.0, max_extra=5.0)
        assert ok and np.allclose(c, [5.0, 0.0])
