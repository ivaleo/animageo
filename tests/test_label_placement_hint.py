"""``label_hint_px`` — a soft, non-locking desired label position.

The hint says where the author would like the label to sit: the offset of the
label CENTRE from the element's label anchor (the point itself, a segment's
midpoint, an angle's vertex), in the same pixels as ``label_offset_px``, y up.
Unlike ``label_offset_px`` + ``label_placement_locked`` it does not freeze the
label — auto-placement treats it as the label's "current position": it keeps
the hinted side/sector and still moves the label off obstacles.

Two priorities outrank the hint:

* an angle label stays inside its angle while it fits there;
* the label of a figure vertex stays outside the figure while there is room.

Every path is gated on the presence of a hint — a scene without one is laid
out exactly as before.
"""
import math

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.label_placement import (
    _collect_labels,
    _point_in_polygon,
    _sectors_for_hint,
    _segment_bbox_overlap,
    compute_label_layout,
)

RESPECT = {'enabled': True, 'respect_current_position': True}
# The configuration the web app ships (style_migration.RECOMMENDED_LABEL_PLACEMENT).
RECOMMENDED = {
    'enabled': True, 'distance_px': 7, 'padding_px': 2, 'angle_gap_arc_px': 5,
    'angle_gap_sides_px': 4, 'w_anchor': 0.5, 'w_label': 10, 'w_geom': 2,
    'canonicalize_anchor': True, 'repair_iterations': 6,
    'respect_current_position': True, 'point_bisector': True, 'geom_gap_px': 2,
    'viewport_clamp': True, 'declutter_labels': True, 'label_gap_px': 2.5,
    'w_assoc': 3, 'dashed_overlap_factor': 0.3, 'continuous_placement': True,
    'angle_label_max_arm_fraction': 0.45, 'cluster_consistency': True,
    'compact_labels': True, 'angle_marker_obstacle': True,
}
CONFIGS = pytest.mark.parametrize('cfg', [RESPECT, RECOMMENDED],
                                  ids=['respect', 'recommended'])


def _scene(code, labelled=()):
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 800, 'ptHeight': 800,
                            'ptXZero': 400, 'ptYZero': 400, 'ptUnit_ggb': 50})
    sc.putCode(code)
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    for name in labelled:
        sc.element(name).style['label_visible'] = True
    return sc


def _offset(sc, cfg, name):
    """Label centre minus the element's anchor, px, y up."""
    layout = compute_label_layout(sc, cfg=cfg, canonicalize=True)
    return np.array(layout[name].offset_ggb, dtype=float)


def _deg(v):
    return math.degrees(math.atan2(float(v[1]), float(v[0]))) % 360


def _turn(v, deg):
    return abs((_deg(v) - deg + 180) % 360 - 180)


ROW = "A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n"
SQUARE = (
    "A = Point(0, 0)\nB = Point(4, 0)\nC = Point(4, 4)\nD = Point(0, 4)\n"
    "ab = Segment(A, B)\nbc = Segment(B, C)\ncd = Segment(C, D)\nda = Segment(D, A)\n"
)
SQUARE_XY = np.array([[0, 0], [4, 0], [4, 4], [0, 4]], dtype=float)


# ── a free point: the hint chooses the side ───────────────────────────

class TestPointHint:
    @CONFIGS
    def test_hint_sets_the_side(self, cfg):
        sc = _scene(ROW, 'ABC')
        sc.element('A').style['label_hint_px'] = [0.0, 14.0]     # above
        sc.element('C').style['label_hint_px'] = [0.0, -14.0]    # below
        assert _turn(_offset(sc, cfg, 'A'), 90) < 20
        assert _turn(_offset(sc, cfg, 'C'), 270) < 20

    @CONFIGS
    def test_hint_is_read_after_a_previous_pass(self, cfg):
        """A label already laid out by auto-placement (``_auto_placed``) and
        without a GeoGebra original has no "current position" of its own —
        this is every label created by ``putCode``. The hint still applies."""
        sc = _scene(ROW, 'ABC')
        style = sc.element('B').style
        style['label_offset_px'] = [10.0, 10.0]
        style['label_anchor'] = 'MC'
        style['_auto_placed'] = True
        without = _offset(sc, cfg, 'B')
        style['label_hint_px'] = [0.0, -14.0]
        assert _turn(_offset(sc, cfg, 'B'), 270) < 20
        assert _turn(without, 270) > 45      # the hint is what moved it

    @CONFIGS
    def test_hint_outranks_an_unlocked_offset(self, cfg):
        sc = _scene(ROW, 'ABC')
        sc.element('B').style['label_offset_px'] = [0.0, 14.0]
        sc.element('B').style['label_hint_px'] = [0.0, -14.0]
        assert _turn(_offset(sc, cfg, 'B'), 270) < 20

    def test_lock_outranks_the_hint(self):
        sc = _scene(ROW, 'ABC')
        sc.element('B').style['label_hint_px'] = [0.0, -14.0]
        sc.element('B').style['label_placement_locked'] = True
        assert 'B' not in compute_label_layout(sc, cfg=RECOMMENDED)

    def test_hint_works_without_respect_mode(self):
        sc = _scene(ROW, 'ABC')
        sc.element('B').style['label_hint_px'] = [0.0, -14.0]
        assert _turn(_offset(sc, {'enabled': True}, 'B'), 270) < 20

    @pytest.mark.parametrize('value', [None, [0.0, 0.0], 'left', [1.0]])
    def test_empty_or_broken_hint_changes_nothing(self, value):
        sc = _scene(ROW, 'ABC')
        before = compute_label_layout(sc, cfg=RECOMMENDED)
        sc.element('B').style['label_hint_px'] = value
        after = compute_label_layout(sc, cfg=RECOMMENDED)
        for name in before:
            assert np.allclose(before[name].offset_ggb, after[name].offset_ggb)
            assert before[name].label_anchor == after[name].label_anchor

    @CONFIGS
    def test_hint_does_not_lock(self, cfg):
        """A hint that puts the label on a line is honoured as a side, not as a
        position: the label ends up next to the line, not on it."""
        sc = _scene("B = Point(0, 0)\nD = Point(0, -3)\nbd = Segment(B, D)\n", 'B')
        sc.element('B').style['label_hint_px'] = [0.0, -14.0]    # on the segment
        off = _offset(sc, cfg, 'B') / 50.0
        lbl = next(l for l in _collect_labels(sc, 14.0) if l.name == 'B')
        assert _segment_bbox_overlap(np.array([0.0, 0.0]), np.array([0.0, -3.0]),
                                     off[0], off[1], lbl.half_w, lbl.half_h) == 0


# ── a vertex: the hinted direction, and "outside the figure" ──────────

class TestVertexHint:
    @CONFIGS
    def test_hint_keeps_its_own_direction(self, cfg):
        """At a square's corner the free sector is 270° wide; an unhinted or
        GeoGebra-positioned label is centred on its bisector (225° at A). A
        hint "to the left" stays to the left."""
        sc = _scene(SQUARE, 'ABCD')
        sc.element('A').style['label_hint_px'] = [-14.0, 0.0]
        assert _turn(_offset(sc, cfg, 'A'), 180) < 15

    @CONFIGS
    def test_hint_into_the_figure_lands_outside(self, cfg):
        sc = _scene(SQUARE, 'ABCD')
        sc.element('A').style['label_hint_px'] = [12.0, 5.0]     # inside the square
        off = _offset(sc, cfg, 'A')
        assert not _point_in_polygon(off / 50.0, SQUARE_XY)
        # …on the outside next to where the hint pointed: below the side AB
        assert off[0] > 0 and off[1] < 0

    @CONFIGS
    def test_polygon_element_is_a_figure_too(self, cfg):
        sc = _scene(
            "A = Point(0, 0)\nB = Point(4, 0)\nC = Point(4, 4)\nD = Point(0, 4)\n"
            "q = Polygon(A, B, C, D)\n", 'ABCD')
        sc.element('A').style['label_hint_px'] = [12.0, 5.0]
        off = _offset(sc, cfg, 'A')
        assert not _point_in_polygon(off / 50.0, SQUARE_XY)

    @CONFIGS
    def test_hint_inside_is_kept_when_there_is_no_outside(self, cfg):
        """A point inside the figure has no outside sector: the hint stands."""
        sc = _scene(
            SQUARE + "O = Point(2, 2)\n"
            "oa = Segment(O, A)\nob = Segment(O, B)\noc = Segment(O, C)\nod = Segment(O, D)\n",
            'ABCDO')
        sc.element('O').style['label_hint_px'] = [0.0, 14.0]     # sector between OC and OD
        assert _turn(_offset(sc, cfg, 'O'), 90) < 20

    @CONFIGS
    def test_point_on_a_side_goes_outside(self, cfg):
        sc = _scene(SQUARE + "M = Point(2, 0)\n", 'ABCDM')
        sc.element('M').style['label_hint_px'] = [0.0, 14.0]     # into the square
        off = _offset(sc, cfg, 'M')
        assert off[1] < 0


# ── a segment: the hint chooses the side of the segment ───────────────

class TestSegmentHint:
    SEGMENT = "A = Point(-3, 0)\nB = Point(3, 0)\ns = Segment(A, B)\n"

    @CONFIGS
    @pytest.mark.parametrize('hint, sign', [
        ([0.0, 14.0], 1), ([0.0, -14.0], -1),
        ([-20.0, 4.0], 1), ([20.0, -4.0], -1),      # mostly along the segment
    ])
    def test_hint_sets_the_side_of_the_segment(self, cfg, hint, sign):
        sc = _scene(self.SEGMENT, 'ABs')
        sc.element('s').style['label_hint_px'] = hint
        off = _offset(sc, cfg, 's')
        assert off[1] * sign > 0
        lbl = next(item for item in _collect_labels(sc, 30) if item.name == 's')
        assert _segment_bbox_overlap(np.array([-3.0, 0.0]), np.array([3.0, 0.0]),
                                     off[0] / 50.0, off[1] / 50.0,
                                     lbl.half_w, lbl.half_h) == 0


# ── the sectors a hinted label may take ───────────────────────────────

class TestSectorsForHint:
    CORNER = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]   # edges at 0° and 90°

    def test_directions_run_from_the_hint_toward_the_bisector(self):
        """The 270° sector of a corner, hint at 174°: the hinted direction
        first, then steps toward the bisector (225°), 45° at most."""
        sectors = _sectors_for_hint(self.CORNER, np.array([-1.0, 0.1]))
        angles = [_deg(d) for d in sectors[0][0]]
        assert abs(angles[0] - 174.3) < 0.1
        assert angles == sorted(angles)
        assert abs(angles[-1] - (174.3 + 45.0)) < 0.1
        assert max(b - a for a, b in zip(angles, angles[1:])) <= 15.0 + 1e-6

    def test_hint_is_held_off_the_sector_edges(self):
        sectors = _sectors_for_hint(self.CORNER, np.array([0.1, -1.0]))   # 276°
        first = _deg(sectors[0][0][0])
        assert abs(first - 276.0) < 1.0           # 84° from the edge at 0°: kept
        sectors = _sectors_for_hint(self.CORNER, np.array([1.0, -0.1]))   # 354°
        assert abs(_deg(sectors[0][0][0]) - 332.0) < 0.5   # 28° off the edge

    def test_sectors_outside_a_figure_come_first(self):
        def inside(theta):
            return 0.0 < theta % (2 * math.pi) < math.pi / 2
        sectors = _sectors_for_hint(self.CORNER, np.array([1.0, 1.0]),
                                    is_interior=inside)
        assert [flag for _dirs, flag in sectors] == [False, True]

    def test_a_point_without_two_edges_has_no_sectors(self):
        assert _sectors_for_hint([np.array([1.0, 0.0])], np.array([0.0, 1.0])) == []


# ── large labels: the place the hint leads to must be a real, clear one ──

TRIANGLE = (
    "A = Point(0, 0)\nB = Point(6, 0)\nC = Point(3, 5)\n"
    "ab = Segment(A, B)\nbc = Segment(B, C)\nca = Segment(C, A)\n"
)
TRIANGLE_SIDES = [((0, 0), (6, 0)), ((6, 0), (3, 5)), ((3, 5), (0, 0))]
# A parallelogram whose base and right side are also drawn as full lines: at D
# the outside below the base is cut into a narrow and a wide sector.
PARALLELOGRAM = (
    "A = Point(0, 0)\nD = Point(6, 0)\nC = Point(8, 5)\nB = Point(2, 5)\n"
    "ab = Segment(A, B)\nbc = Segment(B, C)\ncd = Segment(C, D)\nda = Segment(D, A)\n"
    "base = Line(A, D)\nside = Line(D, C)\n"
)
PARALLELOGRAM_XY = np.array([[0, 0], [6, 0], [8, 5], [2, 5]], dtype=float)
PARALLELOGRAM_LINES = [
    ((0, 0), (2, 5)), ((2, 5), (8, 5)),
    ((-20, 0), (20, 0)),                       # base, as a line
    ((6 - 8, 0 - 20), (6 + 8, 0 + 20)),        # side DC, as a line
]


def _big(sc, names, px=40.0):
    """Large labels: taller than the base distance from the point."""
    for name in names:
        sc.element(name).style['font_size_px'] = px


def _crossed(sc, cfg, name, lines):
    """Total length of ``lines`` under the label box of ``name``, scene MU."""
    off = _offset(sc, cfg, name) / 50.0
    centre = np.array(sc.element(name).data.coords[:2], dtype=float) + off
    lbl = next(l for l in _collect_labels(sc, 14.0) if l.name == name)
    return sum(
        _segment_bbox_overlap(np.array(p1, dtype=float), np.array(p2, dtype=float),
                              centre[0], centre[1], lbl.half_w, lbl.half_h)
        for p1, p2 in lines)


class TestLargeLabels:
    @CONFIGS
    def test_base_vertices_take_the_hinted_side_alike(self, cfg):
        """A label taller than the base distance cannot sit at that distance
        below a base vertex — it would cover the vertex and the base. It is
        moved out along the hinted direction, not round to another side; the
        two mirror-image base vertices end up alike."""
        sc = _scene(TRIANGLE, 'ABC')
        _big(sc, 'ABC', 56.0)
        sc.element('A').style['label_hint_px'] = [0.0, -40.0]
        sc.element('B').style['label_hint_px'] = [0.0, -40.0]
        for name in 'AB':
            assert _turn(_offset(sc, cfg, name), 270) < 15, name
            assert _crossed(sc, cfg, name, TRIANGLE_SIDES) == 0, name

    @CONFIGS
    def test_narrow_hinted_sector_never_sends_the_label_into_the_figure(self, cfg):
        """The hint points below-left of D, into the sector between the base and
        the continuation of the side — tight for a large label. Whether the
        label still fits there or moves to the next outside sector, it stays
        outside the figure, off the lines and on the hinted side of the base."""
        sc = _scene(PARALLELOGRAM, 'ABCD')
        _big(sc, 'ABCD')
        sc.element('D').style['label_hint_px'] = [-18.0, -37.0]
        off = _offset(sc, cfg, 'D') / 50.0
        centre = np.array([6.0, 0.0]) + off
        assert not _point_in_polygon(centre, PARALLELOGRAM_XY)
        assert _crossed(sc, cfg, 'D', PARALLELOGRAM_LINES) == 0
        assert off[1] < 0          # still below the base, as hinted

    @CONFIGS
    def test_no_room_outside_keeps_the_hinted_place_inside(self, cfg):
        """"Outside the figure" holds while there is room. A circle running
        close along the side leaves none: outside, the label would have to sit
        beyond the circle, away from its point. The hint — inside — stands."""
        sc = _scene(SQUARE + "M = Point(2, 0)\nO = Point(2, 2)\nc = Circle(O, 2.65)\n",
                    'ABCDM')
        _big(sc, 'M')
        sc.element('M').style['size_px'] = 10.0
        sc.element('M').style['label_hint_px'] = [0.0, 40.0]     # into the square
        off = _offset(sc, cfg, 'M')
        assert off[1] > 0
        assert _turn(off, 90) < 20


# ── an angle: inside while it fits ────────────────────────────────────

WIDE ="A = Point(0, 0)\nB = Point(3, 0)\nC = Point(1.5, 2.6)\nang = Angle(B, A, C)\n"
NARROW = "A = Point(0, 0)\nB = Point(3, 0)\nC = Point(3, 0.3)\nang = Angle(B, A, C)\n"


def _bisector(sc, name='ang'):
    ang = sc.element(name).data
    v1 = ang.side1[:2] / np.linalg.norm(ang.side1[:2])
    v2 = ang.side2[:2] / np.linalg.norm(ang.side2[:2])
    bis = v1 + v2
    return bis / np.linalg.norm(bis)


class TestAngleHint:
    @CONFIGS
    def test_hint_outside_a_roomy_angle_stays_inside(self, cfg):
        sc = _scene(WIDE, ['ang'])
        out = -_bisector(sc) * 20.0
        sc.element('ang').style['label_hint_px'] = [float(out[0]), float(out[1])]
        layout = compute_label_layout(sc, cfg=cfg)
        assert layout['ang'].angle_params.exterior is False

    @CONFIGS
    def test_hint_outside_a_cramped_angle_goes_outside(self, cfg):
        sc = _scene(NARROW, ['ang'])
        out = -_bisector(sc) * 20.0
        sc.element('ang').style['label_hint_px'] = [float(out[0]), float(out[1])]
        layout = compute_label_layout(sc, cfg=cfg)
        assert layout['ang'].angle_params.exterior is True

    @CONFIGS
    def test_hint_inside_a_cramped_angle_stays_inside(self, cfg):
        sc = _scene(NARROW, ['ang'])
        inside = _bisector(sc) * 60.0
        sc.element('ang').style['label_hint_px'] = [float(inside[0]), float(inside[1])]
        layout = compute_label_layout(sc, cfg=cfg)
        assert layout['ang'].angle_params.exterior is False

    @CONFIGS
    def test_cramped_angle_without_a_hint_is_unchanged(self, cfg):
        sc = _scene(NARROW, ['ang'])
        assert compute_label_layout(sc, cfg=cfg)['ang'].angle_params.exterior is False

    @CONFIGS
    def test_hint_outranks_a_manual_exterior_offset(self, cfg):
        """FP-8 keeps a manually dragged-out angle label outside; a hint is a
        newer, explicit statement and is judged by the inside-first rule."""
        sc = _scene(WIDE, ['ang'])
        bis = _bisector(sc)
        sc.element('ang').style['label_offset_px'] = [float(-bis[0] * 40), float(-bis[1] * 40)]
        assert compute_label_layout(sc, cfg=cfg)['ang'].angle_params.exterior is True
        sc.element('ang').style['label_hint_px'] = [float(bis[0] * 30), float(bis[1] * 30)]
        assert compute_label_layout(sc, cfg=cfg)['ang'].angle_params.exterior is False

    @CONFIGS
    def test_other_labels_avoid_the_outside_angle_label(self, cfg):
        """The solver registers the angle label where it will really be drawn."""
        sc = _scene(NARROW, ['ang', 'A'])
        out = -_bisector(sc) * 20.0
        sc.element('ang').style['label_hint_px'] = [float(out[0]), float(out[1])]
        labels = {l.name: l for l in _collect_labels(sc, 14.0)}
        layout = compute_label_layout(sc, cfg=cfg, canonicalize=True)
        a = np.array(layout['A'].offset_ggb) / 50.0
        from animageo.label_placement import compute_angle_label_center
        ang_c = compute_angle_label_center(sc.element('ang').data,
                                           layout['ang'].angle_params, 50)
        dx, dy = abs(a[0] - ang_c[0]), abs(a[1] - ang_c[1])
        assert (dx >= labels['A'].half_w + labels['ang'].half_w
                or dy >= labels['A'].half_h + labels['ang'].half_h)
