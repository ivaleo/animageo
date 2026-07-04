"""Angle markers as label-placement obstacles (R1) + sector exclusion (R2).

A point label whose anchor sits at an angle's vertex must not be steered into
the sector where the angle marker (right-angle square / arc) is drawn — the
marker would sit "in the line of sight" between the label and its point. See
docs/archive/TZ-label-placement-angle-markers.md.

All behaviour is gated behind ``angle_marker_obstacle`` (default False →
byte-identical to the legacy coarse-arc approximation).
"""
import math

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.label_placement import (
    _angle_in_arc,
    _bisector_of_largest_gap,
    _bisector_of_gap_nearest,
    _collect_obstacles,
    _collect_angle_marker_wedges,
    _angle_marker_obstacle_segments,
    compute_label_layout,
)


def _deg(v):
    return round(math.degrees(math.atan2(float(v[1]), float(v[0]))) % 360, 1)


def _scene(code):
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 800, 'ptHeight': 800,
                            'ptXZero': 400, 'ptYZero': 400, 'ptUnit_ggb': 50})
    sc.putCode(code)
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return sc


# A point E on the horizontal segment A--C, a radius E--D going north, and a
# right angle C-E-D whose square marker is drawn in the NE quadrant ([0°,90°]).
RIGHT_ANGLE_SCENE = (
    "A = Point(-3, 0)\n"
    "C = Point(3, 0)\n"
    "E = Point(0, 0)\n"
    "D = Point(0, 3)\n"
    "sAC = Segment(A, C)\n"
    "rED = Segment(E, D)\n"
    "ang = Angle(C, E, D)\n"
)


# ── R3: _angle_in_arc (CCW arc membership, incl. wrap) ──────────────────

class TestAngleInArc:
    def test_inside(self):
        assert _angle_in_arc(math.radians(45), 0.0, math.radians(90)) is True

    def test_outside(self):
        assert _angle_in_arc(math.radians(135), 0.0, math.radians(90)) is False

    def test_on_edges_inclusive(self):
        assert _angle_in_arc(0.0, 0.0, math.radians(90)) is True
        assert _angle_in_arc(math.radians(90), 0.0, math.radians(90)) is True

    def test_wraps_through_zero(self):
        # arc [350°, 80°] (90° wide, crossing 0°)
        s, e = math.radians(350), math.radians(80)
        assert _angle_in_arc(math.radians(10), s, e) is True
        assert _angle_in_arc(math.radians(200), s, e) is False


# ── R2: sector exclusion in the two direction resolvers ─────────────────

class TestBisectorOfLargestGapBlocked:
    # dirs at E (0°) and S (270°): gaps are [0°,270°] (270° wide) and
    # [270°,360°] (90° wide). The wide gap's bisector is 135°.
    DIRS = [np.array([1.0, 0.0]), np.array([0.0, -1.0])]

    def test_unblocked_picks_widest(self):
        assert _deg(_bisector_of_largest_gap(self.DIRS)) == 135.0

    def test_blocking_widest_picks_next_free_gap(self):
        # Block the 270° gap (its bisector 135° falls inside) → the only free
        # gap left is [270°,360°], bisector 315°.
        blocked = [(0.0, math.radians(270))]
        assert _deg(_bisector_of_largest_gap(self.DIRS, blocked_arcs=blocked)) == 315.0

    def test_all_blocked_falls_back_to_widest(self):
        blocked = [(0.0, math.radians(270)), (math.radians(270), 2 * math.pi)]
        # graceful: still returns a direction (the overall-widest bisector)
        assert _deg(_bisector_of_largest_gap(self.DIRS, blocked_arcs=blocked)) == 135.0

    def test_none_blocked_is_byte_identical(self):
        a = _bisector_of_largest_gap(self.DIRS)
        b = _bisector_of_largest_gap(self.DIRS, blocked_arcs=None)
        assert np.allclose(a, b)


class TestBisectorOfGapNearestBlocked:
    # E (0°), N (90°), W (180°): the marker wedge is [0°,90°] (NE quadrant).
    DIRS = [np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([-1.0, 0.0])]
    NE = np.array([math.cos(math.radians(45)), math.sin(math.radians(45))])

    def test_unblocked_honours_hint_into_wedge(self):
        # GGB hint NE → label centred on the NE wedge bisector (45°) = INTO the
        # marker. This is the bug.
        assert _deg(_bisector_of_gap_nearest(self.DIRS, self.NE)) == 45.0

    def test_blocked_wedge_falls_back_to_free_external_gap(self):
        # Block [0°,90°] → the hint is unusable; place on the widest free gap
        # [180°,360°], bisector 270° (S, external — away from the wedge).
        blocked = [(0.0, math.radians(90))]
        out = _bisector_of_gap_nearest(self.DIRS, self.NE, blocked_arcs=blocked)
        assert _deg(out) == 270.0
        # the placed direction must point AWAY from the wedge bisector
        assert float(out[0] * self.NE[0] + out[1] * self.NE[1]) < 0

    def test_none_blocked_is_byte_identical(self):
        a = _bisector_of_gap_nearest(self.DIRS, self.NE)
        b = _bisector_of_gap_nearest(self.DIRS, self.NE, blocked_arcs=None)
        assert np.allclose(a, b)


# ── R1: marker geometry in the obstacle set ─────────────────────────────

class TestAngleMarkerObstacleSegments:
    def test_right_angle_square_outer_edges_at_render_radius(self):
        sc = _scene(RIGHT_ANGLE_SCENE)
        ang = sc.geo.element('ang')
        segs = _angle_marker_obstacle_segments(sc, ang)
        # right angle → exactly the two OUTER edges of the square marker, sharing
        # the far corner p2 = vertex + n1 + n2 (the two inner edges lie along the
        # arms, already obstacles). Vertex is (0,0); arms are east (side1) and
        # north (side2), so p1 = (r,0), p2 = (r,r), p3 = (0,r) for square side r.
        assert len(segs) == 2
        (p1, p2a), (p2b, p3) = segs
        assert np.allclose(p2a, p2b)                  # shared far corner
        r = float(p1[0])
        assert r > 0
        assert np.allclose(p1, [r, 0.0], atol=1e-9)   # along the east arm
        assert np.allclose(p3, [0.0, r], atol=1e-9)   # along the north arm
        assert np.allclose(p2a, [r, r], atol=1e-9)    # NE corner = p1 + p3
        # r must equal the renderer's right-angle radius: right_angle_size_px/√2.
        from animageo.label_placement import _angle_drawn_sector
        *_, is_right, radius_mu, _, _ = _angle_drawn_sector(sc, ang)
        assert is_right
        assert r == pytest.approx(radius_mu)


class TestCollectObstaclesGating:
    def test_marker_absent_by_default_uses_legacy_arc(self):
        sc = _scene(RIGHT_ANGLE_SCENE)
        segs_off, *_ = _collect_obstacles(sc)
        segs_on, *_ = _collect_obstacles(sc, angle_marker_obstacle=True)
        # the two collections must differ (legacy coarse arc vs real square)
        assert len(segs_off) != len(segs_on) or not all(
            np.allclose(a, b) for sa, sb in zip(segs_off, segs_on)
            for a, b in zip(sa, sb))

    def test_marker_present_when_enabled(self):
        sc = _scene(RIGHT_ANGLE_SCENE)
        segs_on, *_ = _collect_obstacles(sc, angle_marker_obstacle=True)
        # the square marker's outer edges (NE quadrant, near the vertex) appear
        marker = _angle_marker_obstacle_segments(sc, sc.geo.element('ang'))
        for (p1, p2) in marker:
            assert any(np.allclose(p1, q1) and np.allclose(p2, q2)
                       for (q1, q2) in segs_on)


class TestCollectAngleMarkerWedges:
    def test_right_angle_wedge_at_vertex(self):
        sc = _scene(RIGHT_ANGLE_SCENE)
        wedges = _collect_angle_marker_wedges(sc)
        assert len(wedges) == 1
        v, start, end = wedges[0]
        assert np.allclose(v, [0.0, 0.0])
        assert round(math.degrees(start)) % 360 == 0       # along E->C (east)
        assert round(math.degrees(end)) % 360 == 90        # along E->D (north)


# ── Acceptance criterion #2: full layout regression ─────────────────────

class TestLayoutAvoidsMarkerSector:
    """E carries a GGB label offset pointing INTO the marker wedge (NE). With
    the flag off the label stays in the wedge (cos(offset, E->D) > 0 — the bug);
    with the flag on it is placed in the free external sector (cos < 0)."""

    CFG = {
        'enabled': True, 'point_bisector': True,
        'respect_current_position': True, 'respect_min_offset_px': 6.0,
        'continuous_placement': True, 'continuous_steps': 72,
        'geom_gap_px': 2.0,
    }

    def _layout(self, marker_obstacle):
        sc = _scene(RIGHT_ANGLE_SCENE)
        E = sc.geo.element('E')
        E.style['label_visible'] = True
        E.style['label_offset_px'] = [10.0, 10.0]   # NE, into the marker wedge
        cfg = {**self.CFG, 'angle_marker_obstacle': marker_obstacle}
        return compute_label_layout(sc, cfg=cfg)['E']

    @staticmethod
    def _cos_with_ED(offset_ggb):
        # E->D is +y (north); offset_ggb is in GGB px (y up). cos > 0 → toward D.
        off = np.asarray(offset_ggb, dtype=float)
        n = np.linalg.norm(off)
        return float(off[1] / n) if n > 1e-9 else 0.0

    def test_bug_present_without_flag(self):
        place = self._layout(marker_obstacle=False)
        assert self._cos_with_ED(place.offset_ggb) > 0   # label in the wedge

    def test_fixed_with_flag(self):
        place = self._layout(marker_obstacle=True)
        assert self._cos_with_ED(place.offset_ggb) < 0   # label external, away from D
