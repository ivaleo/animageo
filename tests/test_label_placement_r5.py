"""Round-5 feedback fix: compact respect.

The dominant round-4 visual regression was "labels drift far from their points"
("почему все разъезжается?"). Root cause: ``respect_current_position`` pinned a
label at the anchor plus the FULL GGB ``label_offset_px`` — and GGB frequently
stores offsets that sit far from the feature. The fix keeps the offset's SIDE
(sector) but clamps its magnitude to the same compact center-distance auto would
produce, so a respected label stays close to its point.
"""
import math
import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene
from animageo import label_placement as lp
from animageo.label_placement import _bisector_of_gap_nearest


def _ang(v):
    return math.degrees(math.atan2(v[1], v[0])) % 360


def _d(deg):
    return (math.cos(math.radians(deg)), math.sin(math.radians(deg)))


class TestGapNudge:
    """Round-11 direction resolution: a vertex label sits on the WIDEST free gap's
    bisector (= auto's external bisector). The GGB ``preferred`` direction only
    breaks TIES between near-equal gaps (a symmetric crossing)."""
    # a 4-way crossing: edges east/north/west/south → 4 EQUAL gaps (a tie)
    CROSS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    # a clear widest gap: edges at 60° and 300° → 240° gap @180° vs 120° gap @0°
    WIDE = [_d(60), _d(300)]

    def test_tie_broken_by_preferred(self):
        # 4 equal gaps → pick the one the GGB direction points into (50° → 45°)
        assert _ang(_bisector_of_gap_nearest(self.CROSS, _d(50))) == \
            pytest.approx(45.0, abs=0.5)

    def test_open_offset_snaps_to_bisector(self):
        # a GGB direction in the OPEN of the wide wedge (130°, 70° off both edges)
        # snaps to the clean external bisector (180°) — keeps scene4 A/B/C/K &
        # scene23 B on the bisector like auto (their GGB sits far from any edge).
        assert _ang(_bisector_of_gap_nearest(self.WIDE, _d(130))) == \
            pytest.approx(180.0, abs=0.5)

    def test_edge_hugging_offset_keeps_user_side(self):
        # P-REGION (round-17): a GGB direction HUGGING the 60° edge of the wide
        # wedge (75°, 15° off it) is a deliberate "this side" choice — keep it,
        # nudged align_deg (28°) off the edge → 88°, NOT snapped to the centre
        # (180°). This is the scene27_3 A fix (deliberate up-left preserved).
        assert _ang(_bisector_of_gap_nearest(self.WIDE, _d(75))) == \
            pytest.approx(88.0, abs=1.0)

    def test_widest_gap_chosen_over_narrow(self):
        # edges 0°/40° → gaps 40°@20° and 320°@200°; widest (320°) wins
        dirs = [_d(0), _d(40)]
        assert _ang(_bisector_of_gap_nearest(dirs, _d(5))) == \
            pytest.approx(200.0, abs=0.5)

    def test_needs_two_edges(self):
        assert _bisector_of_gap_nearest([(1, 0)], (0, 1)) is None


def _scene():
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                            'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
    sc.putCode("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
    for n in ('A', 'B', 'C'):
        sc.element(n).style['label_visible'] = True
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return sc


def _mag(off):
    return math.hypot(off[0], off[1])


class TestCompactRespect:
    def test_far_offset_pulled_compact_same_side(self):
        """A far (60px) manual offset keeps its direction but is pulled in."""
        sc = _scene()
        sc.element('B').style['label_offset_px'] = [-60.0, 0.0]   # far, left
        layout = lp.compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        off = layout['B'].offset_ggb
        assert off[0] < 0                 # still on the left (sector preserved)
        assert abs(off[1]) < abs(off[0])  # still essentially horizontal
        assert _mag(off) < 60.0 - 1e-6    # NOT pinned at the far magnitude
        assert _mag(off) < 30.0           # genuinely compact, not just trimmed

    def test_compact_offset_stays_compact(self):
        """A moderate offset stays near its manual value: the clamp never blows
        it far out (push-clear may nudge it a few px to clear the marker, but it
        remains compact, not relocated to a distant position)."""
        sc = _scene()
        sc.element('B').style['label_offset_px'] = [0.0, 10.0]    # north, modest
        layout = lp.compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        off = layout['B'].offset_ggb
        assert off[1] > 0                 # still north
        assert _mag(off) < 20.0           # stays compact (small marker-clear nudge ok)

    def test_vertex_offset_alongside_edge_snaps_to_free_gap(self):
        """FP-11: at a crossing, a GGB offset that runs ALONGSIDE an incident
        edge is snapped to the bisector of the free gap it points into, so the
        label lands in open space (reads as the POINT's label), not parallel to
        the edge. Mirrors rhombus point M offset straight down next to MD."""
        sc = AnimaGeoScene()
        sc.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                                'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
        sc.putCode("A = Point(-3, 0)\nC = Point(3, 0)\n"
                   "B = Point(0, 2)\nD = Point(0, -2)\nM = Point(0, 0)\n"
                   "ac = Segment(A, C)\nbd = Segment(B, D)\n")
        sc.element('M').style['label_visible'] = True
        sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
        # GGB dumped M's label nearly straight down (alongside MD), slightly right.
        sc.element('M').style['label_offset_px'] = [3.0, -38.0]
        layout = lp.compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'point_bisector': True, 'directional_placement': True,
                     'respect_min_offset_px': 6.0})
        off = layout['M'].offset_ggb
        assert off[0] > 0 and off[1] < 0          # kept the lower-right SECTOR
        # but on the gap bisector (~45°), NOT alongside the vertical edge
        assert abs(off[0]) > 0.5 * abs(off[1])    # not steep/parallel-to-edge
        assert _mag(off) < 30.0                   # compact, not dragged out

    def test_far_offsets_in_opposite_directions_stay_opposite(self):
        """Two far offsets in opposite directions both pull compact but keep
        their (opposite) sides — the clamp is purely radial."""
        sc = _scene()
        sc.element('A').style['label_offset_px'] = [0.0, 50.0]    # far north
        sc.element('C').style['label_offset_px'] = [0.0, -50.0]   # far south
        layout = lp.compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        assert layout['A'].offset_ggb[1] > 0
        assert layout['C'].offset_ggb[1] < 0
        assert _mag(layout['A'].offset_ggb) < 50.0 - 1e-6
        assert _mag(layout['C'].offset_ggb) < 50.0 - 1e-6
