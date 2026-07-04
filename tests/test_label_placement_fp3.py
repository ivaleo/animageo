"""FP-3: point labels on the bisector of the widest free gap between incident
sides (external bisector / symmetric placement). Pure-geometry.
"""
import math

import numpy as np

from animageo.label_placement import (
    _bisector_of_largest_gap,
    _incident_directions,
)


def _deg(v):
    return round(math.degrees(math.atan2(float(v[1]), float(v[0]))) % 360, 1)


class TestBisectorOfLargestGap:
    def test_empty_is_none(self):
        assert _bisector_of_largest_gap([]) is None

    def test_single_edge_points_opposite(self):
        b = _bisector_of_largest_gap([np.array([1.0, 0.0])])
        assert _deg(b) == 180.0

    def test_point_on_line_is_perpendicular(self):
        b = _bisector_of_largest_gap([np.array([1.0, 0.0]), np.array([-1.0, 0.0])])
        assert _deg(b) in (90.0, 270.0)

    def test_corner_uses_external_bisector(self):
        # sides leaving the vertex toward E and N → label on the *external*
        # bisector (away from the interior), i.e. SW.
        b = _bisector_of_largest_gap([np.array([1.0, 0.0]), np.array([0.0, 1.0])])
        assert _deg(b) == 225.0

    def test_four_perpendicular_edges_diagonal(self):
        dirs = [np.array([1.0, 0.0]), np.array([0.0, 1.0]),
                np.array([-1.0, 0.0]), np.array([0.0, -1.0])]
        assert _deg(_bisector_of_largest_gap(dirs)) == 45.0


class TestIncidentDirections:
    def test_at_endpoint_one_direction(self):
        segs = [(np.array([0.0, 0.0]), np.array([2.0, 0.0]))]
        dirs = _incident_directions(np.array([0.0, 0.0]), segs)
        assert len(dirs) == 1 and _deg(dirs[0]) == 0.0

    def test_at_interior_two_directions(self):
        segs = [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        dirs = _incident_directions(np.array([0.0, 0.0]), segs)
        assert sorted(_deg(d) for d in dirs) == [0.0, 180.0]

    def test_not_on_segment_none(self):
        segs = [(np.array([5.0, 5.0]), np.array([6.0, 5.0]))]
        assert _incident_directions(np.array([0.0, 0.0]), segs) == []

    def test_combines_crossing_segments(self):
        # vertical + horizontal crossing at origin → 4 directions (N/S/E/W)
        segs = [(np.array([0.0, -1.0]), np.array([0.0, 1.0])),
                (np.array([-1.0, 0.0]), np.array([1.0, 0.0]))]
        dirs = _incident_directions(np.array([0.0, 0.0]), segs)
        assert sorted(_deg(d) for d in dirs) == [0.0, 90.0, 180.0, 270.0]
        assert _deg(_bisector_of_largest_gap(dirs)) == 45.0
