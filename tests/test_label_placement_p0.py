"""Tests for Phase-1 (P0) label-placement features.

Covers: canonical position-preference orders, LabelCostModel (legacy-equivalence
+ preference + soft proximity terms), the shared overlap helper, the
discrete-gradient-descent repair pass and the majority-anchor consistency pass.
All pure-geometry (no manim). See docs/archive/label_placement_improvement_plan.md.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from animageo.label_placement import (
    POSITION_PRIORITY,
    POSITION_PRIORITY_ORDERS,
    LabelCostModel,
    LabelInfo,
    _candidate_has_overlap,
    _consistency_pass,
    _generate_candidates,
    _point_segment_distance,
    _repair_pass,
    _resolve_position_priority,
    _score_candidate,
)

EMPTY = np.empty((0, 2))


# ── Direction-index legend (matches _DIRECTIONS) ──────────────────────
# 0=E(R) 1=NE(TR) 2=N(T) 3=NW(TL) 4=W(L) 5=SW(BL) 6=S(B) 7=SE(BR)


class TestPositionPriority:
    def test_disabled_returns_none(self):
        assert _resolve_position_priority(None) is None
        assert _resolve_position_priority('') is None
        assert _resolve_position_priority('does-not-exist') is None

    def test_all_orders_are_permutations(self):
        for name, ranks in POSITION_PRIORITY.items():
            assert sorted(int(r) for r in ranks) == list(range(8)), name

    def test_classic_top_right_is_best(self):
        ranks = _resolve_position_priority('classic')
        assert ranks[1] == 0          # NE / top-right preferred (Yoeli)
        assert ranks[6] == max(ranks)  # S / bottom worst

    def test_perceptual_top_is_best(self):
        ranks = _resolve_position_priority('perceptual')
        assert ranks[2] == 0          # N / top preferred (PerceptPPO 2024)

    def test_orders_listed_match_table(self):
        assert set(POSITION_PRIORITY_ORDERS) == set(POSITION_PRIORITY)


class TestLabelCostModelLegacyEquivalence:
    def test_default_model_equals_score_candidate(self):
        weights = (1.0, 10.0, 8.0)
        padding = 0.1
        model = LabelCostModel(weights=weights, padding=padding)
        center = np.array([1.0, 1.0])
        seg = [(np.array([-2.0, 0.9]), np.array([2.0, 0.9]))]
        circles = [(np.array([0.0, 0.0]), 1.3)]
        arc = np.array([[1.0, 1.0]])
        placed = [(np.array([1.1, 1.0]), 0.3, 0.2)]
        for pref in range(8):
            for i in range(8):
                expected = _score_candidate(
                    center, 0.2, 0.15, padding, placed, seg, circles, arc,
                    pref, i, weights,
                )
                got = model.candidate_cost(
                    center, 0.2, 0.15, placed, seg, circles, arc, pref, i,
                )
                assert got == pytest.approx(expected)

    def test_max_overlap_free_cost_default_is_legacy_threshold(self):
        model = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.1)
        assert model.max_overlap_free_cost() == pytest.approx(4.0)


class TestLabelCostModelPreference:
    def test_preference_term_adds_ranked_cost(self):
        # w_anchor=0 isolates the preference term from the direction penalty.
        ranks = _resolve_position_priority('classic')
        model = LabelCostModel(
            weights=(0.0, 10.0, 8.0), padding=0.1,
            position_priority=ranks, w_pref=5.0,
        )
        far = np.array([20.0, 20.0])  # no obstacles → only the pref term
        best = model.candidate_cost(far, 0.2, 0.1, [], [], [], EMPTY, 0, 1)  # rank 0
        worst = model.candidate_cost(far, 0.2, 0.1, [], [], [], EMPTY, 0, 6)  # rank 7
        assert best == pytest.approx(0.0)
        assert worst == pytest.approx(5.0 * 7)

    def test_max_overlap_free_cost_includes_preference(self):
        ranks = _resolve_position_priority('classic')
        model = LabelCostModel(
            weights=(1.0, 10.0, 8.0), padding=0.1,
            position_priority=ranks, w_pref=5.0,
        )
        assert model.max_overlap_free_cost() == pytest.approx(4.0 + 5.0 * 7)


class TestLabelCostModelSoftProximity:
    def test_soft_term_decays_with_distance(self):
        model = LabelCostModel(
            weights=(0.0, 10.0, 8.0), padding=0.0, ptUnit=1.0,
            soft_falloff_px=2.0,
        )
        seg = [(np.array([0.0, -10.0]), np.array([0.0, 10.0]))]  # line x=0
        near = model.candidate_cost(np.array([0.5, 0.0]), 0.1, 0.1, [], seg, [], EMPTY, 0, 0)
        far = model.candidate_cost(np.array([5.0, 0.0]), 0.1, 0.1, [], seg, [], EMPTY, 0, 0)
        assert near > far >= 0.0

    def test_soft_term_saturates_at_overlap(self):
        model = LabelCostModel(
            weights=(0.0, 10.0, 8.0), padding=0.0, ptUnit=1.0,
            soft_falloff_px=2.0,
        )
        # Candidate centered on the line → gap ≤ 0 → soft term == w_geom*w_soft.
        seg = [(np.array([0.0, -10.0]), np.array([0.0, 10.0]))]
        on_line = model.candidate_cost(np.array([0.0, 0.0]), 0.1, 0.1, [], seg, [], EMPTY, 0, 0)
        # w_anchor=0, so the legacy overlap term + saturated soft term remain.
        assert on_line >= 8.0  # at least the soft saturation contribution


class TestPointSegmentDistance:
    def test_perpendicular(self):
        d = _point_segment_distance((0.0, 3.0), (-5.0, 0.0), (5.0, 0.0))
        assert d == pytest.approx(3.0)

    def test_beyond_endpoint(self):
        d = _point_segment_distance((10.0, 0.0), (-5.0, 0.0), (5.0, 0.0))
        assert d == pytest.approx(5.0)


class TestCandidateHasOverlap:
    def test_detects_segment(self):
        seg = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        assert _candidate_has_overlap([0.0, 0.0], 0.5, 0.5, seg, [], EMPTY)

    def test_free_position(self):
        seg = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        assert not _candidate_has_overlap([5.0, 5.0], 0.5, 0.5, seg, [], EMPTY)

    def test_detects_placed_label(self):
        placed = [(np.array([0.0, 0.0]), 0.5, 0.5)]
        assert _candidate_has_overlap([0.2, 0.0], 0.5, 0.5, [], [], EMPTY, placed)

    def test_detects_circle(self):
        circles = [(np.array([0.0, 0.0]), 1.0)]
        assert _candidate_has_overlap([1.0, 0.0], 0.3, 0.3, [], circles, EMPTY)


class TestRepairPass:
    def test_moves_lone_label_to_min_cost_direction(self):
        # Default preferred_dir is 1 (NE). Seed at the opposite direction (5/SW)
        # and confirm repair descends to the zero-penalty preferred direction.
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        model = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0)
        seed = _generate_candidates(lbl.anchor, 0.5)[5]
        result = [('A', seed, 5)]
        _repair_pass([lbl], result, [], [], EMPTY, 0.5, 0.0, model, 5)
        assert result[0][2] == 1
        expected = _generate_candidates(lbl.anchor, 0.5)[1]
        assert np.allclose(result[0][1], expected)

    def test_is_deterministic(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        model = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0)
        runs = []
        for _ in range(2):
            r = [('A', _generate_candidates(lbl.anchor, 0.5)[5], 5)]
            _repair_pass([lbl], r, [], [], EMPTY, 0.5, 0.0, model, 5)
            runs.append(r[0][2])
        assert runs[0] == runs[1]

    def test_leaves_optimal_label_unchanged(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 1
        model = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0)
        good = _generate_candidates(lbl.anchor, 0.5)[1]
        result = [('A', good, 1)]
        _repair_pass([lbl], result, [], [], EMPTY, 0.5, 0.0, model, 5)
        assert result[0][2] == 1


def _fake_scene(names):
    """Minimal scene exposing geo.element(name).data with a single dummy type."""
    class _Dummy:
        pass
    elems = {n: SimpleNamespace(data=_Dummy()) for n in names}
    geo = SimpleNamespace(element=lambda n: elems.get(n))
    return SimpleNamespace(geo=geo)


class TestConsistencyPass:
    def test_snaps_outlier_to_majority(self):
        names = ['A', 'B', 'C']
        labels = [
            LabelInfo(name=n, anchor=np.array([float(i * 10), 0.0]),
                      half_w=0.1, half_h=0.1)
            for i, n in enumerate(names)
        ]
        result = [
            ('A', _generate_candidates(labels[0].anchor, 0.5)[1], 1),
            ('B', _generate_candidates(labels[1].anchor, 0.5)[1], 1),
            ('C', _generate_candidates(labels[2].anchor, 0.5)[3], 3),  # outlier
        ]
        scene = _fake_scene(names)
        _consistency_pass(scene, labels, result, [], [], EMPTY, 0.5, 0.0)
        assert result[2][2] == 1  # C snapped to the majority direction
        assert np.allclose(result[2][1],
                           _generate_candidates(labels[2].anchor, 0.5)[1])

    def test_keeps_outlier_when_majority_slot_blocked(self):
        names = ['A', 'B', 'C']
        labels = [
            LabelInfo(name=n, anchor=np.array([float(i * 10), 0.0]),
                      half_w=0.1, half_h=0.1)
            for i, n in enumerate(names)
        ]
        result = [
            ('A', _generate_candidates(labels[0].anchor, 0.5)[1], 1),
            ('B', _generate_candidates(labels[1].anchor, 0.5)[1], 1),
            ('C', _generate_candidates(labels[2].anchor, 0.5)[3], 3),
        ]
        # Block C's majority (dir 1) candidate with a segment through that bbox.
        c_target = _generate_candidates(labels[2].anchor, 0.5)[1]
        seg = [(np.array([c_target[0], c_target[1] - 1.0]),
                np.array([c_target[0], c_target[1] + 1.0]))]
        scene = _fake_scene(names)
        _consistency_pass(scene, labels, result, seg, [], EMPTY, 0.5, 0.0)
        assert result[2][2] == 3  # stays put — snapping would overlap

    def test_singletons_untouched(self):
        labels = [LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                            half_w=0.1, half_h=0.1)]
        result = [('A', _generate_candidates(labels[0].anchor, 0.5)[3], 3)]
        scene = _fake_scene(['A'])
        _consistency_pass(scene, labels, result, [], [], EMPTY, 0.5, 0.0)
        assert result[0][2] == 3
