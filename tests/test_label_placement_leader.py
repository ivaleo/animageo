"""P2-A leader lines — Step 1: detection + LeaderSpec data model + displaced
placement. Config-gated (`label_overflow`, default 'overplot' → no leaders).
Rendering is a later step; here we lock the core: a genuinely-stuck label is moved
to a free spot and given a connector ``attach → anchor``; a free label is untouched.
"""
import numpy as np

from animageo.label_placement import (
    LabelInfo,
    LeaderSpec,
    _leader_layout_pass,
    _bbox_edge_toward,
    _candidate_has_overlap,
)

EMPTY = np.empty((0, 2))


class TestBboxEdgeToward:
    def test_east_hits_right_edge(self):
        # target to the east → exit at the right edge (cx+hw, cy)
        p = _bbox_edge_toward(0.0, 0.0, 0.5, 0.3, 10.0, 0.0)
        assert p[0] == 0.5 and abs(p[1]) < 1e-9

    def test_north_hits_top_edge(self):
        p = _bbox_edge_toward(0.0, 0.0, 0.5, 0.3, 0.0, 10.0)
        assert abs(p[0]) < 1e-9 and abs(p[1] - 0.3) < 1e-9

    def test_point_on_boundary(self):
        # the returned point is on the bbox boundary (one coord at +-half)
        p = _bbox_edge_toward(0.0, 0.0, 0.5, 0.3, 2.0, 1.0)
        on = abs(abs(p[0]) - 0.5) < 1e-9 or abs(abs(p[1]) - 0.3) < 1e-9
        assert on


class TestLeaderLayoutPass:
    def _setup(self):
        # label P at the origin; its placed centre (0.05, 0) overlaps a short
        # horizontal segment [0,0]–[0.15,0]; free space is further east.
        lbl = LabelInfo(name='P', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 0
        segs = [(np.array([0.0, 0.0]), np.array([0.15, 0.0]))]
        result = [('P', np.array([0.05, 0.0]), 0)]
        return [lbl], result, segs

    def test_stuck_label_moved_and_gets_leader(self):
        labels, result, segs = self._setup()
        specs = _leader_layout_pass(None, labels, result, segs, [], EMPTY,
                                    0.05, 0.0, 50.0, max_push=1.0)
        assert 'P' in specs and isinstance(specs['P'], LeaderSpec)
        # leader points at the object
        assert specs['P'].anchor == (0.0, 0.0)
        # the label was moved to an overlap-free spot
        moved = result[0][1]
        assert not _candidate_has_overlap(moved, 0.1, 0.1, segs, [], EMPTY)
        # attach lies on the moved label's bbox edge
        ax, ay = specs['P'].attach
        on_edge = (abs(abs(ax - moved[0]) - 0.1) < 1e-6
                   or abs(abs(ay - moved[1]) - 0.1) < 1e-6)
        assert on_edge

    def test_free_label_untouched(self):
        lbl = LabelInfo(name='Q', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        result = [('Q', np.array([0.0, 1.0]), 2)]   # far from any geometry
        before = result[0][1].copy()
        specs = _leader_layout_pass(None, [lbl], result, [], [], EMPTY,
                                    0.05, 0.0, 50.0, max_push=1.0)
        assert specs == {}
        assert np.allclose(result[0][1], before)


class TestApplyLeaderToStyle:
    """Step 3 wiring: apply_label_layout carries the LeaderSpec into
    ``elem.style['_leader']`` (which the renderer/exporters read) and clears it
    when a later layout has no leader."""

    def test_apply_writes_and_clears_leader(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.label_placement import (
            apply_label_layout, LabelPlacement, LeaderSpec,
        )
        sc = AnimaGeoScene()
        sc.putCode("A = Point(0, 0)\n")
        sc.element('A').style['label_visible'] = True
        sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})

        with_leader = {'A': LabelPlacement(
            name='A', offset_ggb=(20.0, 0.0), label_anchor='ML',
            leader=LeaderSpec(anchor=(0.0, 0.0), attach=(0.4, 0.0)))}
        apply_label_layout(sc, with_leader, rerender=False)
        assert sc.element('A').style.get('_leader') == ((0.0, 0.0), (0.4, 0.0))

        no_leader = {'A': LabelPlacement(
            name='A', offset_ggb=(20.0, 0.0), label_anchor='ML')}
        apply_label_layout(sc, no_leader, rerender=False)
        assert '_leader' not in sc.element('A').style


class TestLeaderExporters:
    """Step 4: the leader connector reaches the semantic exporters (TikZ, JSXGraph)
    — they read ``elem.style['_leader']`` directly (not manim mobjects)."""

    def _scene(self, with_leader):
        from animageo.animageo import AnimaGeoScene
        sc = AnimaGeoScene()
        sc.putCode("A = Point(0, 0)\nB = Point(1, 1)\nC = Point(2, 0)\n"
                   "p = Polygon(A, B, C)\n")
        sc.element('A').style['label_visible'] = True
        sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
        if with_leader:
            sc.element('A').style['_leader'] = ((0.0, 0.0), (0.4, 0.2))
        return sc

    def test_tikz_emits_leader_draw(self):
        assert "line width=0.4pt" in self._scene(True).exportTikZ()
        assert "line width=0.4pt" not in self._scene(False).exportTikZ()

    def test_jsxgraph_emits_leader_segment(self):
        import json
        spec = json.loads(self._scene(True).exportJSXGraph(output="spec"))
        leaders = [e for e in spec["elements"]
                   if str(e.get("name", "")).startswith("__leader_")]
        assert len(leaders) == 1
        assert leaders[0]["engine"] == "segment"
        # eval-free: parents are JSON coordinate pairs, not raw JS
        assert leaders[0]["parents"] == [[0.4, 0.2], [0.0, 0.0]]
        spec0 = json.loads(self._scene(False).exportJSXGraph(output="spec"))
        assert not any(str(e.get("name", "")).startswith("__leader_")
                       for e in spec0["elements"])


class TestLeaderSidewaysSearch:
    """Round-15: a stuck label whose radial direction stays blocked must still find
    a free spot to the SIDE (scene19 A_1=A_7 overlapped a line; a radial push
    missed its sideways free space)."""

    def test_sideways_free_spot_found(self):
        from animageo.label_placement import LabelInfo, _leader_layout_pass
        lbl = LabelInfo(name='P', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 0  # East
        # a long wall ALONG the East ray (y=0): pushing East never clears it,
        # but North/South does.
        segs = [(np.array([0.0, 0.0]), np.array([5.0, 0.0]))]
        result = [('P', np.array([0.2, 0.0]), 0)]   # on the wall, dir East
        specs = _leader_layout_pass(None, [lbl], result, segs, [], EMPTY,
                                    0.05, 0.0, 50.0, max_push=2.0)
        assert 'P' in specs
        moved = result[0][1]
        assert not _candidate_has_overlap(moved, 0.1, 0.1, segs, [], EMPTY)
        assert abs(moved[1]) > 0.05   # moved sideways off the East ray, not radially


class TestLeaderPointsOnly:
    """Round-16: leaders are for POINT labels (fixed anchor). A segment/line label
    can slide along its own geometry, so a leader back to it is redundant clutter
    (scene6a l_2/n_2). `points_only` (default True) skips non-point labels."""

    def test_segment_label_not_leadered(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.label_placement import LabelInfo, _leader_layout_pass
        sc = AnimaGeoScene()
        sc.putCode("A = Point(0, 0)\nB = Point(2, 0)\ns = Segment(A, B)\n")
        la = LabelInfo(name='A', anchor=np.array([0.0, 0.5]),
                       half_w=0.1, half_h=0.1)
        ls = LabelInfo(name='s', anchor=np.array([1.0, 0.5]),
                       half_w=0.1, half_h=0.1)
        la.preferred_dir = ls.preferred_dir = 2   # N
        # each label centre sits on a short wall (overlaps); free further out
        segs = [(np.array([-0.1, 0.5]), np.array([0.1, 0.5])),
                (np.array([0.9, 0.5]), np.array([1.1, 0.5]))]
        result = [('A', np.array([0.0, 0.5]), 2),
                  ('s', np.array([1.0, 0.5]), 2)]
        specs = _leader_layout_pass(sc, [la, ls], result, segs, [], EMPTY,
                                    0.05, 0.0, 50.0, max_push=2.0)
        assert 'A' in specs        # point label → leader
        assert 's' not in specs    # segment label → skipped

        # points_only=False leaders both
        result2 = [('A', np.array([0.0, 0.5]), 2),
                   ('s', np.array([1.0, 0.5]), 2)]
        specs2 = _leader_layout_pass(sc, [la, ls], result2, segs, [], EMPTY,
                                     0.05, 0.0, 50.0, max_push=2.0,
                                     points_only=False)
        assert 's' in specs2
