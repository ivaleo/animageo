"""Round 18-22 compaction / P3-P5 mechanisms in ``_recompact_pass``.

Covers: pulling an overshot label back toward its point; the incident-only solid
clip (a label may clip a line through its OWN point but not a non-incident line or
a dashed line); the radial-outward placement for a point on a solid circle (P5);
and the solid-circle rescue. All config-gated by ``compact_labels`` (default off).
"""
import numpy as np

from animageo.label_placement import (
    LabelInfo,
    _recompact_pass,
    _on_solid_circle_outward,
    _candidate_has_overlap,
)

EMPTY = np.empty((0, 2))


def _lbl(name, anchor, hw=0.1, hh=0.1):
    return LabelInfo(name=name, anchor=np.asarray(anchor, float),
                     half_w=hw, half_h=hh)


class TestOnSolidCircleOutward:
    def test_point_on_solid_circle_points_outward(self):
        # point (3,0) on a circle centred at origin, r=3 → outward unit is +x
        r = _on_solid_circle_outward(np.array([3.0, 0.0]),
                                     [(np.array([0.0, 0.0]), 3.0)], [False])
        assert r is not None
        assert abs(r[0] - 1.0) < 1e-6 and abs(r[1]) < 1e-6

    def test_dashed_circle_ignored(self):
        r = _on_solid_circle_outward(np.array([3.0, 0.0]),
                                     [(np.array([0.0, 0.0]), 3.0)], [True])
        assert r is None

    def test_point_off_circle(self):
        r = _on_solid_circle_outward(np.array([1.0, 0.0]),
                                     [(np.array([0.0, 0.0]), 3.0)], [False])
        assert r is None


class TestRecompactPullIn:
    def test_overshot_label_pulled_closer(self):
        # a label sitting far out (0.5) in open space is pulled toward base (0.1)
        lbl = _lbl('A', [0.0, 0.0])
        result = [('A', np.array([0.5, 0.0]), 0)]
        _recompact_pass([lbl], result, [], [], EMPTY, 0.1, 0.02, 50.0, 0.0,
                        seg_dashed=None, circ_dashed=None, overlap_tol=0.0)
        assert float(np.linalg.norm(result[0][1])) < 0.5 - 1e-6


class TestRecompactObstacles:
    def test_incident_solid_line_may_be_clipped(self):
        # a SOLID line through the anchor (incident) — the label may sit close,
        # clipping it, instead of being kept far.
        lbl = _lbl('A', [0.0, 0.0])
        seg = (np.array([-5.0, 0.0]), np.array([5.0, 0.0]))  # horizontal, through anchor
        result = [('A', np.array([0.0, 0.4]), 2)]   # up, far
        _recompact_pass([lbl], result, [seg], [], EMPTY, 0.1, 0.02, 50.0, 0.0,
                        seg_dashed=[False], circ_dashed=None, overlap_tol=0.05)
        # pulled in close (clipping its own incident line is allowed)
        assert float(np.linalg.norm(result[0][1])) < 0.4 - 1e-6

    def test_dashed_line_is_an_obstacle(self):
        # a DASHED line just inside the current distance must NOT be sat upon —
        # the label is not pulled onto it (round-22: dashed = hard).
        lbl = _lbl('A', [0.0, 0.0], hw=0.05, hh=0.05)
        dashed = (np.array([-5.0, 0.18]), np.array([5.0, 0.18]))  # horizontal at y=0.18
        result = [('A', np.array([0.0, 0.4]), 2)]
        _recompact_pass([lbl], result, [dashed], [], EMPTY, 0.1, 0.02, 50.0, 0.0,
                        seg_dashed=[True], circ_dashed=None, overlap_tol=0.0)
        c = result[0][1]
        # the final position does not overlap the dashed line
        assert not _candidate_has_overlap(c, 0.05 + 0.02, 0.05 + 0.02,
                                          [dashed], [], EMPTY)


class TestRecompactCircleRescue:
    def test_label_moved_off_solid_circle(self):
        # anchor ON a solid circle; the solver spot overlaps the circle → rescue
        # moves it to a spot clear of the circle.
        circle = (np.array([0.0, 0.0]), 0.5)
        lbl = _lbl('A', [0.5, 0.0], hw=0.08, hh=0.08)   # on the circle (x=r)
        result = [('A', np.array([0.46, 0.06]), 1)]     # overlaps the arc
        assert _candidate_has_overlap(result[0][1], 0.1, 0.1, [], [circle], EMPTY)
        _recompact_pass([lbl], result, [], [circle], EMPTY, 0.1, 0.02, 50.0, 0.0,
                        seg_dashed=None, circ_dashed=[False], overlap_tol=0.0)
        assert not _candidate_has_overlap(result[0][1], 0.08 + 0.02, 0.08 + 0.02,
                                          [], [circle], EMPTY)
