"""Tests for label_placement module — pure geometry, no manim dependency."""
import numpy as np
import pytest

from animageo.label_placement import (
    _bbox_overlap_area,
    _point_in_bbox,
    _generate_candidates,
    _segment_bbox_overlap,
    _collect_obstacles,
    _get_anchor,
    _score_candidate,
    _solve_greedy,
    _compute_preferred_dir,
    LabelInfo,
    AngleParams,
    compute_angle_label_center,
    compute_angle_label_base_center,
    compute_angle_label_offset_px,
    ANGLE_LABEL_NARROW_MAX_FACTOR,
)
from animageo.geo.lib_elements import Angle, Element, Line, Ray


class TestBboxOverlap:
    def test_no_overlap(self):
        assert _bbox_overlap_area(0, 0, 1, 1, 5, 0, 1, 1) == 0.0

    def test_full_overlap(self):
        assert _bbox_overlap_area(0, 0, 1, 1, 0, 0, 1, 1) == pytest.approx(4.0)

    def test_partial_overlap(self):
        assert _bbox_overlap_area(0, 0, 1, 1, 1, 0, 1, 1) == pytest.approx(2.0)

    def test_touching_edge(self):
        assert _bbox_overlap_area(0, 0, 1, 1, 2, 0, 1, 1) == 0.0

    def test_one_inside_other(self):
        assert _bbox_overlap_area(0, 0, 5, 5, 0, 0, 1, 1) == pytest.approx(4.0)


class TestPointInBbox:
    def test_inside(self):
        assert _point_in_bbox(0.5, 0.5, 0, 0, 1, 1) is True

    def test_outside(self):
        assert _point_in_bbox(2, 2, 0, 0, 1, 1) is False

    def test_on_edge(self):
        assert _point_in_bbox(1, 0, 0, 0, 1, 1) is True


class TestSegmentBboxOverlap:
    def test_segment_through_bbox(self):
        """Horizontal segment crossing through the box center."""
        p1 = np.array([-2.0, 0.0])
        p2 = np.array([2.0, 0.0])
        overlap = _segment_bbox_overlap(p1, p2, 0, 0, 0.5, 0.5)
        assert overlap > 0.5  # at least some of the segment is inside

    def test_segment_outside(self):
        p1 = np.array([5.0, 5.0])
        p2 = np.array([6.0, 5.0])
        overlap = _segment_bbox_overlap(p1, p2, 0, 0, 0.5, 0.5)
        assert overlap == 0.0

    def test_segment_fully_inside(self):
        p1 = np.array([-0.1, 0.0])
        p2 = np.array([0.1, 0.0])
        overlap = _segment_bbox_overlap(p1, p2, 0, 0, 0.5, 0.5)
        assert overlap == pytest.approx(0.2, abs=0.02)

    def test_long_segment_crossing_tiny_bbox_is_not_missed(self):
        p1 = np.array([-100.0, 0.0])
        p2 = np.array([100.0, 0.0])
        overlap = _segment_bbox_overlap(p1, p2, 0.25, 0.0, 0.01, 0.01)
        assert overlap == pytest.approx(0.02)


class TestLineRayObstacles:
    class _Geo:
        def __init__(self, elements):
            self.elements = elements

    class _Scene:
        def __init__(self, elements):
            self.geo = TestLineRayObstacles._Geo(elements)

        def _get_scene_bounds(self, padding=0.1):
            return (-2.0 - padding, -1.0 - padding,
                    2.0 + padding, 1.0 + padding)

    def test_collect_obstacles_clips_infinite_line_to_viewport(self):
        elem = Element('l', Line([0, 1], 0))
        scene = self._Scene([elem])

        segments, circles, arc_pts, _, _ = _collect_obstacles(scene)

        assert circles == []
        assert arc_pts.shape == (0, 2)
        assert len(segments) == 1
        p1, p2 = segments[0]
        xs = sorted([p1[0], p2[0]])
        assert xs == pytest.approx([-2.1, 2.1])
        assert p1[1] == pytest.approx(0.0)
        assert p2[1] == pytest.approx(0.0)

    def test_line_anchor_matches_rendered_clipped_midpoint(self):
        elem = Element('l', Line([1, 0], 1))
        scene = self._Scene([elem])

        anchor = _get_anchor(elem, scene)

        assert anchor == pytest.approx([1.0, 0.0])

    def test_collect_obstacles_clips_ray_to_visible_half_line(self):
        elem = Element('r', Ray(np.array([0.0, 0.0]), np.array([1.0, 0.0])))
        scene = self._Scene([elem])

        segments, _, _, _, _ = _collect_obstacles(scene)

        assert len(segments) == 1
        p1, p2 = segments[0]
        xs = sorted([p1[0], p2[0]])
        assert xs == pytest.approx([0.0, 2.1])
        assert p1[1] == pytest.approx(0.0)
        assert p2[1] == pytest.approx(0.0)


class TestCandidateGeneration:
    def test_eight_candidates(self):
        candidates = _generate_candidates(np.array([0.0, 0.0]), 1.0)
        assert candidates.shape == (8, 2)

    def test_distance(self):
        anchor = np.array([3.0, 4.0])
        candidates = _generate_candidates(anchor, 0.5)
        for c in candidates:
            dist = np.linalg.norm(c - anchor)
            assert dist == pytest.approx(0.5, abs=1e-10)

    def test_directions(self):
        candidates = _generate_candidates(np.array([0.0, 0.0]), 1.0)
        assert candidates[0][0] == pytest.approx(1.0, abs=1e-10)
        assert candidates[0][1] == pytest.approx(0.0, abs=1e-10)
        assert candidates[2][0] == pytest.approx(0.0, abs=1e-10)
        assert candidates[2][1] == pytest.approx(1.0, abs=1e-10)


class TestPreferredDirection:
    def test_away_from_right(self):
        """Geometry to the right → preferred dir is left (W=4)."""
        cloud = np.array([[2.0, 0.0], [3.0, 0.0], [4.0, 0.0]])
        idx = _compute_preferred_dir(np.array([0.0, 0.0]), cloud, radius=5.0)
        assert idx == 4  # W

    def test_away_from_above(self):
        """Geometry above → preferred dir is below (S=6)."""
        cloud = np.array([[0.0, 2.0], [0.0, 3.0]])
        idx = _compute_preferred_dir(np.array([0.0, 0.0]), cloud, radius=5.0)
        assert idx == 6  # S

    def test_no_nearby_geometry(self):
        """No geometry nearby → default NE (1)."""
        cloud = np.array([[100.0, 100.0]])
        idx = _compute_preferred_dir(np.array([0.0, 0.0]), cloud, radius=2.0)
        assert idx == 1


class TestScoring:
    def test_preferred_direction_zero_cost(self):
        score = _score_candidate(
            np.array([1.0, 0.0]), 0.1, 0.1, 0.0,
            [], [], [], np.empty((0, 2)),
            preferred_dir=0, candidate_idx=0,
            weights=(1.0, 10.0, 5.0),
        )
        assert score == 0.0

    def test_opposite_direction_penalty(self):
        score = _score_candidate(
            np.array([-1.0, 0.0]), 0.1, 0.1, 0.0,
            [], [], [], np.empty((0, 2)),
            preferred_dir=0, candidate_idx=4,
            weights=(1.0, 10.0, 5.0),
        )
        assert score == pytest.approx(4.0)

    def test_label_overlap_penalty(self):
        placed = [(np.array([0.0, 0.0]), 0.5, 0.5)]
        score = _score_candidate(
            np.array([0.0, 0.0]), 0.5, 0.5, 0.0,
            placed, [], [], np.empty((0, 2)),
            preferred_dir=0, candidate_idx=0,
            weights=(1.0, 10.0, 5.0),
        )
        assert score > 5.0

    def test_segment_overlap_penalty(self):
        """Segment going through the label bbox should add penalty."""
        segs = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        score = _score_candidate(
            np.array([0.0, 0.0]), 0.3, 0.1, 0.0,
            [], segs, [], np.empty((0, 2)),
            preferred_dir=0, candidate_idx=0,
            weights=(1.0, 10.0, 5.0),
        )
        assert score > 5.0  # w_geom * (1 + seg_length_inside)

    def test_arc_point_penalty(self):
        arc_pts = np.array([[0.0, 0.0]])
        score = _score_candidate(
            np.array([0.0, 0.0]), 0.5, 0.5, 0.0,
            [], [], [], arc_pts,
            preferred_dir=0, candidate_idx=0,
            weights=(1.0, 10.0, 5.0),
        )
        assert score == pytest.approx(5.0)


class TestGreedySolver:
    def test_two_labels_no_overlap(self):
        labels = [
            LabelInfo(name='A', anchor=np.array([0.0, 0.0]), half_w=0.1, half_h=0.05),
            LabelInfo(name='B', anchor=np.array([2.0, 0.0]), half_w=0.1, half_h=0.05),
        ]
        result = _solve_greedy(labels, [], [], np.empty((0, 2)),
                               distance=0.25, padding=0.01, weights=(1, 10, 5))
        assert len(result) == 2

    def test_close_labels_avoid_overlap(self):
        labels = [
            LabelInfo(name='A', anchor=np.array([0.0, 0.0]), half_w=0.15, half_h=0.08),
            LabelInfo(name='B', anchor=np.array([0.3, 0.0]), half_w=0.15, half_h=0.08),
        ]
        result = _solve_greedy(labels, [], [], np.empty((0, 2)),
                               distance=0.2, padding=0.01, weights=(1, 10, 5))
        centers = {name: c for name, c, _ in result}
        overlap = _bbox_overlap_area(
            centers['A'][0], centers['A'][1], 0.15, 0.08,
            centers['B'][0], centers['B'][1], 0.15, 0.08,
        )
        assert overlap < 1e-10, f"Labels overlap with area {overlap}"

    def test_avoids_segment(self):
        """Label should avoid a segment passing through the default candidate."""
        segments = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        labels = [
            LabelInfo(name='A', anchor=np.array([0.0, 0.0]), half_w=0.1, half_h=0.05, preferred_dir=0),
        ]
        result = _solve_greedy(labels, segments, [], np.empty((0, 2)),
                               distance=0.25, padding=0.01, weights=(1, 10, 8))
        name, center, dir_idx = result[0]
        assert abs(center[1]) > 0.1, f"Label at y={center[1]:.3f}, should avoid y≈0 segment"


class TestComputeAngleLabelCenter:
    """compute_angle_label_center — bisector math used for per-frame angle tracking."""

    def _make_angle(self, p, v1, v2):
        """Build an Angle. ``compute_angle_label_center`` reads only [:2] slices."""
        return Angle(
            np.array([p[0], p[1]], dtype=float),
            np.array([v1[0], v1[1]], dtype=float),
            np.array([v2[0], v2[1]], dtype=float),
        )

    def test_90deg_at_origin(self):
        """90° angle with arms along +x/+y → center on 45° bisector."""
        ang = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))
        ap = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                         gap_arc_px=3, gap_sides_px=3)
        ptUnit = 100
        center = compute_angle_label_center(ang, ap, ptUnit)

        # For a 90° angle, base distance dominates (no narrow-angle clamp):
        # dist = arc_r/ptUnit + max(hw, hh) + gap/ptUnit
        expected_dist = 30 / 100 + max(0.1, 0.05) + 3 / 100
        expected_center = np.array([1, 1]) / np.sqrt(2) * expected_dist
        assert np.allclose(center, expected_center, atol=1e-9)

    def test_angle_offset_is_relative_to_renderer_label_base(self):
        """Auto-placement stores an offset from renderer label_pos, not vertex."""
        ang = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))
        ap = AngleParams(
            arc_r_px=30,
            render_r_px=30,
            half_w=0.1,
            half_h=0.05,
            gap_arc_px=0,
            gap_sides_px=0,
        )
        ptUnit = 100
        ptUnit_ggb = 100

        desired_center = compute_angle_label_center(ang, ap, ptUnit)
        renderer_base = compute_angle_label_base_center(ang, ap, ptUnit)
        offset_px = np.array(compute_angle_label_offset_px(ang, ap, ptUnit, ptUnit_ggb))
        actual_center = renderer_base + offset_px / ptUnit_ggb

        assert np.allclose(actual_center, desired_center, atol=1e-9)
        assert np.linalg.norm(offset_px / ptUnit_ggb) == pytest.approx(0.1)

    def test_angle_offset_uses_right_marker_render_radius(self):
        """Right-angle square marker has a smaller renderer label radius."""
        ang = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))
        ap = AngleParams(
            arc_r_px=25,
            render_r_px=20 / np.sqrt(2),
            half_w=0.1,
            half_h=0.05,
            gap_arc_px=0,
            gap_sides_px=0,
        )
        ptUnit = 100
        ptUnit_ggb = 100

        desired_center = compute_angle_label_center(ang, ap, ptUnit)
        renderer_base = compute_angle_label_base_center(ang, ap, ptUnit)
        offset_px = np.array(compute_angle_label_offset_px(ang, ap, ptUnit, ptUnit_ggb))

        assert np.allclose(renderer_base + offset_px / ptUnit_ggb, desired_center, atol=1e-9)

    def test_narrow_angle_clamp(self):
        """10° angle → narrow-angle clamp kicks in, label pushed further along bisector."""
        # Construct a 10° angle with arms symmetric around +x axis
        half = np.radians(5)
        ang = self._make_angle(
            p=(0, 0),
            v1=(np.cos(-half), np.sin(-half)),
            v2=(np.cos(half), np.sin(half)),
        )
        ap = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                         gap_arc_px=3, gap_sides_px=3)
        ptUnit = 100
        center = compute_angle_label_center(ang, ap, ptUnit)

        # The narrow clamp would push to (half_diag + gap/ptUnit) / sin(half_angle),
        # but for a very small angle that blows up — so it's capped at
        # base_dist * ANGLE_LABEL_NARROW_MAX_FACTOR to keep the label near the marker.
        half_diag = np.sqrt(0.1 ** 2 + 0.05 ** 2)
        min_clearance = half_diag + 3 / 100
        uncapped_dist = min_clearance / np.sin(ang.size / 2)
        base_dist = 30 / 100 + max(0.1, 0.05) + 3 / 100
        cap_dist = base_dist * ANGLE_LABEL_NARROW_MAX_FACTOR
        # this 10° angle is narrow enough that the clamp would exceed the cap
        assert uncapped_dist > cap_dist
        # Bisector is along +x; the label is pinned to the cap, not the blow-up.
        assert np.allclose(center, np.array([cap_dist, 0.0]), atol=1e-9)
        assert cap_dist > base_dist * 2

    def test_rotation_equivariance(self):
        """Rotating the whole angle by θ rotates the label center by θ."""
        ap = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                         gap_arc_px=3, gap_sides_px=3)
        ptUnit = 100
        ang0 = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))
        c0 = compute_angle_label_center(ang0, ap, ptUnit)

        theta = np.radians(37)
        ct, st = np.cos(theta), np.sin(theta)
        v1r = (ct, st)                         # (1, 0) rotated by θ
        v2r = (-st, ct)                        # (0, 1) rotated by θ
        ang1 = self._make_angle(p=(0, 0), v1=v1r, v2=v2r)
        c1 = compute_angle_label_center(ang1, ap, ptUnit)

        R = np.array([[ct, -st], [st, ct]])
        assert np.allclose(c1, R @ c0, atol=1e-9)

    def test_vertex_translation(self):
        """Moving the angle's vertex translates the label center by the same offset."""
        ap = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                         gap_arc_px=3, gap_sides_px=3)
        ptUnit = 100
        ang0 = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))
        c0 = compute_angle_label_center(ang0, ap, ptUnit)

        # Same geometry relative to vertex, vertex moved to (3, -2)
        ang1 = self._make_angle(p=(3, -2), v1=(1, 0), v2=(0, 1))
        c1 = compute_angle_label_center(ang1, ap, ptUnit)

        assert np.allclose(c1 - c0, np.array([3.0, -2.0]), atol=1e-9)

    def test_reflex_narrow_clamp_matches_supplementary(self):
        """Raw reflex angle (range_type=1, default) uses supplementary for the
        narrow-angle clamp — so a label on a 10°-visual arc is placed the
        same as a label on a 350°-raw arc (both render the 10° side).
        """
        ptUnit = 100
        # Visual ~10°, raw direct: v1=+x, v2=rotated 10° CCW.
        h = np.radians(5)
        ang_direct = self._make_angle(
            p=(0, 0),
            v1=(np.cos(-h), np.sin(-h)),
            v2=(np.cos(h), np.sin(h)),
        )
        # Visual ~10° but raw reflex: swap rays so CCW arc is 350°.
        ang_reflex = self._make_angle(
            p=(0, 0),
            v1=(np.cos(h), np.sin(h)),
            v2=(np.cos(-h), np.sin(-h)),
        )
        assert ang_direct.size == pytest.approx(np.radians(10), rel=1e-9)
        assert ang_reflex.size == pytest.approx(np.radians(350), rel=1e-9)

        ap = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                         gap_arc_px=3, gap_sides_px=3)
        c_direct = compute_angle_label_center(ang_direct, ap, ptUnit)
        c_reflex = compute_angle_label_center(ang_reflex, ap, ptUnit)
        # Both bisector formulas (v1n+v2n) yield the same narrow-side
        # midpoint, and the clamp now uses the supplementary — the
        # distances should match.
        assert np.linalg.norm(c_direct) == pytest.approx(
            np.linalg.norm(c_reflex), rel=1e-9
        )

    def test_arc_gap_and_sides_gap_are_independent(self):
        """Increasing arc gap affects base distance; sides gap only kicks in for narrow angles."""
        ptUnit = 100
        ang_wide = self._make_angle(p=(0, 0), v1=(1, 0), v2=(0, 1))   # 90°, no clamp
        half_narrow = np.radians(5)
        ang_narrow = self._make_angle(
            p=(0, 0),
            v1=(np.cos(-half_narrow), np.sin(-half_narrow)),
            v2=(np.cos(half_narrow), np.sin(half_narrow)),
        )

        # Baseline
        ap0 = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                          gap_arc_px=3, gap_sides_px=3)
        wide0 = np.linalg.norm(compute_angle_label_center(ang_wide, ap0, ptUnit))
        narrow0 = np.linalg.norm(compute_angle_label_center(ang_narrow, ap0, ptUnit))

        # This 10° angle is narrow enough that the clamp hits the cap
        # (base_dist * ANGLE_LABEL_NARROW_MAX_FACTOR), so the binding constraints
        # invert vs. the un-capped regime.
        # Bump arc gap only — wide-angle distance grows; narrow grows too, because
        # arc gap enters base_dist and so raises the cap.
        ap_arc = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                             gap_arc_px=15, gap_sides_px=3)
        wide_arc = np.linalg.norm(compute_angle_label_center(ang_wide, ap_arc, ptUnit))
        narrow_arc = np.linalg.norm(compute_angle_label_center(ang_narrow, ap_arc, ptUnit))
        assert wide_arc > wide0                         # arc gap moves wide outward
        assert narrow_arc > narrow0                     # arc gap raises the narrow-clamp cap

        # Bump sides gap only — wide unchanged (base path dominates); narrow also
        # unchanged here because it's already pinned to the cap, so the larger
        # sides-gap clearance is clamped away.
        ap_sides = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                               gap_arc_px=3, gap_sides_px=15)
        wide_sides = np.linalg.norm(compute_angle_label_center(ang_wide, ap_sides, ptUnit))
        narrow_sides = np.linalg.norm(compute_angle_label_center(ang_narrow, ap_sides, ptUnit))
        assert wide_sides == pytest.approx(wide0)       # wide unaffected by sides gap
        assert narrow_sides == pytest.approx(narrow0)   # narrow pinned to the cap


class TestAngleEffectiveArcRadius:
    """Multi-arc angles (elem.style['tick_count'] > 1) expand the outer visual radius;
    label placement must push the label out by the same amount.
    """

    def test_helper_single_arc_returns_base(self):
        from animageo.label_placement import _angle_effective_arc_r_px

        assert _angle_effective_arc_r_px(30, lines=1, ang_rshift_px=5.0) == 30

    def test_helper_multi_arc_adds_rshift_per_extra_arc(self):
        from animageo.label_placement import _angle_effective_arc_r_px

        # (3 - 1) * 5 = 10 pixels of extra outer radius
        assert _angle_effective_arc_r_px(30, lines=3, ang_rshift_px=5.0) == 40

    def test_helper_handles_none_lines(self):
        from animageo.label_placement import _angle_effective_arc_r_px

        # elem.style.get('lines', 1) may legitimately be None; treat as 1
        assert _angle_effective_arc_r_px(30, lines=None, ang_rshift_px=5.0) == 30

    def test_multi_arc_pushes_label_outward(self):
        """With 3 concentric arcs, label sits further out than with 1."""
        ap_single = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                                gap_arc_px=3, gap_sides_px=3)
        # Effective radius for lines=3 with ang_rshift_px=5: 30 + 2*5 = 40
        ap_triple = AngleParams(arc_r_px=40, half_w=0.1, half_h=0.05,
                                gap_arc_px=3, gap_sides_px=3)
        ang = Angle(
            np.array([0.0, 0.0]),
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        )
        ptUnit = 100
        d_single = np.linalg.norm(compute_angle_label_center(ang, ap_single, ptUnit))
        d_triple = np.linalg.norm(compute_angle_label_center(ang, ap_triple, ptUnit))
        # Extra 10 pixels of radius / ptUnit = 0.1 scene MU along bisector
        assert d_triple - d_single == pytest.approx(10 / ptUnit, rel=1e-9)


class TestComputeEffectiveArcSizePx:
    """Auto-scaling of angle arc radius by angle measure.

    Uses lightweight stand-ins for Angle and GeoStyle to avoid manim imports.
    """

    def _ang(self, angle_rad, arm_len=1.0):
        class _A:
            pass
        a = _A()
        a.size = angle_rad
        a.side1 = np.array([arm_len, 0.0])
        a.side2 = np.array([arm_len * np.cos(angle_rad), arm_len * np.sin(angle_rad)])
        return a

    def _elem(self, arc_size_px=30, auto_radius=None):
        class _E:
            style = {'arc_size_px': arc_size_px}
        if auto_radius is not None:
            _E.style['auto_radius'] = auto_radius
        return _E()

    def _style(self, enabled=False, **overrides):
        class _S:
            export = {'ptUnit': 50}
            style_config = None
        if enabled:
            cfg = {'enabled': True}
            cfg.update(overrides)
            class _Overlay:
                angle_radius = cfg
            class _Cfg:
                overlay = _Overlay()
            _S.style_config = _Cfg()
        return _S()

    def test_disabled_passes_through_base(self):
        from animageo.label_placement import compute_effective_arc_size_px
        r = compute_effective_arc_size_px(
            self._elem(30), self._ang(np.pi / 4), self._style(enabled=False),
        )
        assert r == 30

    def test_pivot_angle_returns_base(self):
        """At pivot_rad the scale factor is 1, result = base_arc_px (clamps permitting)."""
        from animageo.label_placement import compute_effective_arc_size_px
        r = compute_effective_arc_size_px(
            self._elem(30),
            self._ang(np.pi / 2),
            self._style(enabled=True, pivot_rad=np.pi / 2, min_px=0, max_arm_fraction=10.0),
        )
        assert r == pytest.approx(30, rel=1e-9)

    def test_narrow_angle_scales_up(self):
        """Narrower than pivot → bigger radius (bounded by max_arm_fraction)."""
        from animageo.label_placement import compute_effective_arc_size_px
        narrow = self._ang(np.pi / 12, arm_len=10.0)  # 15°, long arms so cap is loose
        r = compute_effective_arc_size_px(
            self._elem(30),
            narrow,
            self._style(enabled=True, exp=0.25, pivot_rad=np.pi / 2,
                        min_px=0, max_arm_fraction=10.0),
        )
        expected = 30 * (np.pi / 2 / (np.pi / 12)) ** 0.25
        assert r == pytest.approx(expected, rel=1e-9)
        assert r > 30

    def test_wide_angle_scales_down(self):
        """Wider than pivot → smaller radius."""
        from animageo.label_placement import compute_effective_arc_size_px
        wide = self._ang(np.pi * 0.9)
        r = compute_effective_arc_size_px(
            self._elem(30),
            wide,
            self._style(enabled=True, exp=0.25, pivot_rad=np.pi / 2,
                        min_px=0, max_arm_fraction=10.0),
        )
        assert r < 30

    def test_min_px_floor(self):
        """Floor activates when the scale factor would produce < min_px."""
        from animageo.label_placement import compute_effective_arc_size_px
        r = compute_effective_arc_size_px(
            self._elem(30),
            self._ang(np.pi * 0.99),  # near-flat → strong shrink
            self._style(enabled=True, exp=2.0, min_px=25, max_arm_fraction=10.0),
        )
        assert r == 25

    def test_max_arm_fraction_ceiling(self):
        """Ceiling caps at max_arm_fraction * min_arm_len * ptUnit."""
        from animageo.label_placement import compute_effective_arc_size_px
        # arm_len = 0.5 scene MU, ptUnit = 50 → arm_px = 25
        # max_arm_fraction 0.65 → cap = 16.25 px
        ang = self._ang(np.pi / 12, arm_len=0.5)
        r = compute_effective_arc_size_px(
            self._elem(200),  # large base that blows past cap
            ang,
            self._style(enabled=True, exp=0.25, min_px=0, max_arm_fraction=0.65),
        )
        assert r == pytest.approx(0.65 * 0.5 * 50, rel=1e-9)

    def test_per_element_opt_out(self):
        """elem.style['auto_radius'] = False bypasses scaling even when global is on."""
        from animageo.label_placement import compute_effective_arc_size_px
        narrow = self._ang(np.pi / 12)
        r = compute_effective_arc_size_px(
            self._elem(30, auto_radius=False),
            narrow,
            self._style(enabled=True, exp=0.25, min_px=0, max_arm_fraction=10.0),
        )
        assert r == 30

    def test_zero_angle_does_not_crash(self):
        """Degenerate angle (ang.size ≈ 0) falls back to safe floor."""
        from animageo.label_placement import compute_effective_arc_size_px
        r = compute_effective_arc_size_px(
            self._elem(30),
            self._ang(0.0, arm_len=10.0),
            self._style(enabled=True, min_px=5, max_arm_fraction=10.0),
        )
        # Very narrow fallback (0.01 rad cap inside the helper) → large scale
        assert np.isfinite(r) and r > 30

    def test_reflex_uses_supplementary(self):
        """For range_type=1 (default) a reflex raw angle renders as its
        supplementary on the narrow side. Auto-scaling must use that
        supplementary, not the raw reflex.
        """
        from animageo.label_placement import compute_effective_arc_size_px
        narrow_direct = self._ang(np.radians(10), arm_len=10.0)
        narrow_reflex = self._ang(np.radians(350), arm_len=10.0)  # same visual
        st = self._style(enabled=True, exp=0.25, pivot_rad=np.pi / 2,
                         min_px=0, max_arm_fraction=10.0)
        r_direct = compute_effective_arc_size_px(self._elem(30), narrow_direct, st)
        r_reflex = compute_effective_arc_size_px(self._elem(30), narrow_reflex, st)
        assert r_direct == pytest.approx(r_reflex, rel=1e-9)
        # And both should be scaled UP (narrow visual angle → bigger arc)
        assert r_direct > 30

    def test_angle_range_reflex_reverses_supplementary(self):
        """angle_range='reflex' renders the reflex side. When raw is non-reflex,
        the rendered side is 2π - raw (reflex); narrow clamp effectively
        disables (wide rendered angle). Auto-scaling therefore scales DOWN
        for narrow raw under angle_range='reflex' (because rendered side is wide).
        """
        from animageo.label_placement import compute_effective_arc_size_px
        narrow_raw = self._ang(np.radians(10), arm_len=10.0)
        elem2 = self._elem(30)
        elem2.style['angle_range'] = 'reflex'
        st = self._style(enabled=True, exp=0.25, pivot_rad=np.pi / 2,
                         min_px=0, max_arm_fraction=10.0)
        r2 = compute_effective_arc_size_px(elem2, narrow_raw, st)
        # rendered angle = 350°, scale = (π/2 / 350°)^0.25 < 1 → shrink
        assert r2 < 30


class TestMCAnchorEquivalence:
    """MC canonicalization must preserve the label's visual center.

    The invariant: rendering (anchor=A, offset=O_A) and rendering
    (anchor=MC, offset=O_mc=O_A - edge_A*halfExtent*scale) place the label
    at the exact same visual position. Under canonicalization in
    compute_label_layout this rewriting is applied automatically.
    """

    def _visual_center(self, pos, edge, half_extent, offset_ggb, ptUnit_ggb):
        """Mirror ui.create_label placement math."""
        # move_to(pos, aligned_edge=edge): bbox point at `edge * half_extent`
        # relative to center ends up at pos. So bbox center = pos - edge*half_extent.
        # Then tex.shift([offset_ggb/ptUnit_ggb]).
        center = np.asarray(pos, dtype=float) - np.asarray(edge, dtype=float) * np.asarray(half_extent, dtype=float)
        center = center + np.asarray(offset_ggb, dtype=float) / ptUnit_ggb
        return center

    @pytest.mark.parametrize("anchor_name,edge", [
        ('TL', (-1,  1)), ('TC', ( 0,  1)), ('TR', ( 1,  1)),
        ('ML', (-1,  0)), ('MC', ( 0,  0)), ('MR', ( 1,  0)),
        ('BL', (-1, -1)), ('BC', ( 0, -1)), ('BR', ( 1, -1)),
    ])
    def test_anchor_to_mc_equivalence(self, anchor_name, edge):
        pos = np.array([2.0, 3.0])
        half_extent = np.array([0.7, 0.3])
        ptUnit_ggb = 120.0
        offset_A = np.array([4.0, -5.0])  # arbitrary ggb-units offset

        center_A = self._visual_center(pos, edge, half_extent, offset_A, ptUnit_ggb)

        # Canonicalize: O_mc = O_A - edge_A * halfExtent * ptUnit_ggb
        edge_np = np.asarray(edge, dtype=float)
        offset_MC = offset_A - edge_np * half_extent * ptUnit_ggb
        center_MC = self._visual_center(pos, (0, 0), half_extent, offset_MC, ptUnit_ggb)

        assert np.allclose(center_A, center_MC, atol=1e-12)


class TestBboxCacheThreadSafety:
    """The module-level bbox cache is shared between concurrent render jobs
    in the same process. Writes must serialize via the lock."""

    def test_concurrent_writes_do_not_corrupt_dict(self):
        import threading
        from animageo.label_placement import _bbox_cache, _bbox_lock, clear_bbox_cache

        clear_bbox_cache()
        errors = []

        def writer(i):
            try:
                for j in range(500):
                    key = (f"label_{i}_{j}", float(j), 0)
                    with _bbox_lock:
                        _bbox_cache[key] = (float(j), float(j))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert not errors
        assert len(_bbox_cache) == 8 * 500
        clear_bbox_cache()

    def test_clear_bbox_cache_is_locked(self):
        from animageo.label_placement import _bbox_cache, _bbox_lock, clear_bbox_cache

        clear_bbox_cache()
        with _bbox_lock:
            _bbox_cache[('x', 1.0, 0)] = (1.0, 2.0)
        clear_bbox_cache()
        assert _bbox_cache == {}
