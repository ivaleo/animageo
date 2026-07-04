"""Performance hardening: obstacle culling (exact) + fast segment-bbox overlap.

The recommended placement preset (continuous sweep + repair) was O(candidates ×
ALL segments); a dense scene (244 segments) took ~2 s/layout — too slow for
static export and fatal for per-frame animation. Culling obstacles to each
label's reach is EXACT (every candidate bbox stays within reach of the anchor)
and cut dense layouts ~5×.
"""
import numpy as np

from animageo.label_placement import _cull_obstacles, _segment_bbox_overlap


class TestCullObstacles:
    def test_keeps_in_reach_drops_far(self):
        segs = [(np.array([0.0, 0.0]), np.array([1.0, 0.0])),        # near
                (np.array([100.0, 100.0]), np.array([101.0, 100.0]))]  # far
        dash = [False, True]
        circ = [(np.array([0.5, 0.5]), 0.3), (np.array([50.0, 50.0]), 0.3)]
        arc = np.array([[0.0, 0.2], [80.0, 80.0]])
        s, d, c, a = _cull_obstacles(segs, dash, circ, arc, (0.0, 0.0), reach=2.0)
        assert len(s) == 1 and d == [False]      # near segment + its dashed flag
        assert len(c) == 1                        # near circle only
        assert len(a) == 1                        # near arc point only

    def test_dashed_mask_stays_aligned(self):
        # dropping the middle segment must drop its dashed flag too
        segs = [(np.array([0.0, 0.0]), np.array([0.1, 0.0])),    # near
                (np.array([50.0, 0.0]), np.array([51.0, 0.0])),  # far
                (np.array([0.0, 0.1]), np.array([0.0, 0.2]))]    # near
        dash = [True, False, True]
        s, d, _, _ = _cull_obstacles(segs, dash, [], np.empty((0, 2)),
                                     (0.0, 0.0), reach=1.0)
        assert len(s) == 2 and d == [True, True]

    def test_none_dashed_passthrough(self):
        segs = [(np.array([0.0, 0.0]), np.array([1.0, 0.0]))]
        s, d, _, _ = _cull_obstacles(segs, None, [], np.empty((0, 2)),
                                     (0.0, 0.0), reach=5.0)
        assert len(s) == 1 and d is None


class TestSegmentBboxOverlap:
    def test_line_through_bbox_centre(self):
        # horizontal segment through a bbox of half-width 0.5 → ~1.0 inside
        ov = _segment_bbox_overlap((-2.0, 0.0), (2.0, 0.0), 0.0, 0.0, 0.5, 0.3)
        assert ov == 0.5 + 0.5  # full bbox width

    def test_segment_misses_bbox(self):
        ov = _segment_bbox_overlap((-2.0, 5.0), (2.0, 5.0), 0.0, 0.0, 0.5, 0.3)
        assert ov == 0.0

    def test_vertical_segment_inside(self):
        ov = _segment_bbox_overlap((0.0, -1.0), (0.0, 1.0), 0.0, 0.0, 0.5, 0.4)
        assert abs(ov - 0.8) < 1e-9   # 2*hh


class TestPlacementCarriesToExporters:
    """The placement the solver writes into ``elem.style['label_offset_px']`` must
    reach ALL output formats, not just SVG — TikZ and JSXGraph read the same
    resolved style. Guards against a placement change breaking non-SVG export.
    """
    PRESET = {"overlay": {"label_placement": {
        "enabled": True, "repair_iterations": 6, "soft_falloff_px": 0.0,
        "respect_current_position": True, "point_bisector": True,
        "geom_gap_px": 2.0, "directional_placement": False,
        "viewport_clamp": True, "declutter_labels": True, "label_gap_px": 2.5,
        "w_assoc": 3.0, "dashed_overlap_factor": 0.3,
        "continuous_placement": True, "continuous_steps": 72,
        "angle_label_max_arm_fraction": 0.45, "cluster_consistency": True}}}

    def _scene(self, place):
        from animageo.animageo import AnimaGeoScene
        sc = AnimaGeoScene()
        sc.putCode("A = Point(-3, 0)\nB = Point(0, 2)\nC = Point(3, 0)\n"
                   "p = Polygon(A, B, C)\n")
        for n in ('A', 'B', 'C'):
            sc.element(n).style['label_visible'] = True
        sc.applyStyle(style=self.PRESET)
        if place:
            sc.autoPlaceLabels()
        return sc

    def test_tikz_reflects_placement(self):
        placed = self._scene(True).exportTikZ()
        plain = self._scene(False).exportTikZ()
        assert placed != plain                       # offsets changed the output
        assert ("xshift" in placed or "yshift" in placed)  # node shifts present

    def test_jsxgraph_spec_exports(self):
        spec = self._scene(True).exportJSXGraph(output="spec")
        assert isinstance(spec, str) and len(spec) > 0
        import json
        json.loads(spec)                              # valid JSON spec
