"""``viewport_clamp`` keeps a label in the frame without laying it on its point.

The frame used to be a post-processing step: after the solver, ``np.clip`` of
the label's solver centre into the frame. That centre is the label's anchor
corner, not the middle of the box the renderer draws (``center − edge·half``),
so the clamped box could stay half outside the frame and land on its own
point — ``circle_through_point`` of the web corpus, P on the top edge of the
frame. Now a label whose drawn box leaves the frame takes the best solver
candidate that lies wholly in the frame, clears its point and touches no more
geometry than before; the plain clip is only the fallback.
"""
import math

import numpy as np
import pytest

from animageo import native
from animageo.label_placement import (
    ANCHOR_EDGES,
    LabelInfo,
    compute_label_layout,
    label_size,
    _drawn_box_harm,
    _segment_bbox_overlap,
    _viewport_clamp_pass,
)
from tests.native.conftest import DocBuilder

SIZE = (800, 600)
LAYOUT = {
    'reference': {'prominence': 4 / 3, 'prominence_basis': 'output'},
    'content': {'source': 'source_view', 'fit': 'contain', 'padding': 0},
    'export': {'size': list(SIZE), 'fit': 'contain', 'scale_basis': 'fit'},
}
# The recommended preset of the library docs, as the web canvas passes it.
PRESET = {
    'distance_px': 7, 'padding_px': 2, 'angle_gap_arc_px': 5, 'angle_gap_sides_px': 4,
    'w_anchor': 0.5, 'w_label': 10.0, 'w_geom': 2.0, 'canonicalize_anchor': True,
    'repair_iterations': 6, 'soft_falloff_px': 0.0, 'respect_current_position': True,
    'point_bisector': True, 'geom_gap_px': 2.0, 'directional_placement': False,
    'viewport_clamp': True, 'declutter_labels': True, 'label_gap_px': 2.5, 'w_assoc': 3.0,
    'dashed_overlap_factor': 0.3, 'continuous_placement': True, 'continuous_steps': 72,
    'angle_label_max_arm_fraction': 0.45, 'cluster_consistency': True,
    'compact_labels': True, 'compact_gap_px': 1.0, 'compact_max_push_px': 4.0,
    'overlap_tol_px': 2.5, 'angle_marker_obstacle': True,
}
GENERAL = {'O': (1, 1), 'P': (4, 5)}
FRACTIONAL = {'O': (0.3, -0.7), 'P': (-2.9, 1.1)}


def circle_through_point(inputs, bounds):
    """The web corpus scene ``circle_through_point``: O, P, the circle about O
    through P, the segment OP, its midpoint M, the circle about M through O and
    the line OP."""
    b = DocBuilder('circle_through_point', bounds=bounds)
    b.free('O', *inputs['O']).free('P', *inputs['P'])
    b.circle('c', 'O', 'P').segment('r', 'O', 'P').midpoint('M', 'O', 'P')
    b.circle('c2', 'M', 'O').line('d', 'O', 'P')
    return b.doc


def layout(inputs, bounds, clamp, size=SIZE):
    lp = dict(PRESET, viewport_clamp=clamp)
    export_layout = dict(LAYOUT, export=dict(LAYOUT['export'], size=list(size)))
    return native.layout_labels(
        circle_through_point(inputs, bounds),
        style_config={'overlay': {'label_placement': lp}},
        export_layout=export_layout, backend='metrics', place=True)


def to_px(entries, inputs):
    """World → output px of the frame, from the two placed points O and P."""
    (ox, oy), (px, py) = inputs['O'], inputs['P']
    (ux, uy), (vx, vy) = entries['O']['point'], entries['P']['point']
    u = math.hypot(vx - ux, vy - uy) / math.hypot(px - ox, py - oy)
    return lambda x, y: (ux + (x - ox) * u, uy - (y - oy) * u)


def geometry_hits(box, inputs, px):
    """Names of the curves of the scene that cross the drawn ``box`` (px)."""
    x0, y0, x1, y1 = box
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    o, p = px(*inputs['O']), px(*inputs['P'])
    m = ((o[0] + p[0]) / 2, (o[1] + p[1]) / 2)
    hits = set()
    for name, centre, radius in (('c', o, math.dist(o, p)), ('c2', m, math.dist(m, o))):
        near = math.hypot(centre[0] - min(max(centre[0], x0), x1),
                          centre[1] - min(max(centre[1], y0), y1))
        far = max(math.hypot(centre[0] - x, centre[1] - y) for x in (x0, x1) for y in (y0, y1))
        if near <= radius <= far:
            hits.add(name)
    if _segment_bbox_overlap(o, p, cx, cy, hw, hh) > 0:
        hits.add('r')
    sides = {np.sign((p[0] - o[0]) * (y - o[1]) - (p[1] - o[1]) * (x - o[0]))
             for x in (x0, x1) for y in (y0, y1)}
    if len(sides - {0.0}) > 1:
        hits.add('d')
    return hits


def inside_frame(box, tol=0.5, size=SIZE):
    x0, y0, x1, y1 = box
    return x0 >= -tol and y0 >= -tol and x1 <= size[0] + tol and y1 <= size[1] + tol


class TestCircleThroughPoint:
    def test_label_on_the_top_edge_stays_off_its_point(self):
        """P on the top edge of the frame: the clamp used to pull the label
        down onto P itself, the box still half outside the frame."""
        bounds = [-7.4, -6.4, 2.6, 1.1]                 # 10 × 7.5, P on the top edge
        on, off = layout(FRACTIONAL, bounds, True), layout(FRACTIONAL, bounds, False)
        assert not inside_frame(off['P']['box'])        # the solver puts it above the frame
        px = to_px(on, FRACTIONAL)
        for name, entry in on.items():
            assert name not in entry['pointOverlaps'], (name, entry['box'])
            assert inside_frame(entry['box']), (name, entry['box'])
            assert geometry_hits(entry['box'], FRACTIONAL, px) <= geometry_hits(
                off[name]['box'], FRACTIONAL, px), name

    def test_web_frame(self):
        """The frame of the web revision (``viewDefaults.bounds``), P (4, 5)
        on the top edge."""
        bounds = [-5, -5, 5, 5]
        on, off = layout(GENERAL, bounds, True), layout(GENERAL, bounds, False)
        px = to_px(on, GENERAL)
        for name, entry in on.items():
            assert name not in entry['pointOverlaps'], (name, entry['box'])
            assert inside_frame(entry['box']), (name, entry['box'])
            assert geometry_hits(entry['box'], GENERAL, px) <= geometry_hits(
                off[name]['box'], GENERAL, px), name

    @pytest.mark.parametrize('inputs, bounds, size', [
        (FRACTIONAL, [-2.9, -4.5, 7.1, 3], (800, 600)),     # 4:3, P on the left edge
        (GENERAL, [-6, -1.5, 4, 6], (800, 600)),            # 4:3, P on the right edge
        (FRACTIONAL, [-2.9, -4.0, 3.1, 4.0], (600, 800)),   # 3:4, P on the left edge
        (GENERAL, [-2, -2, 4, 6], (600, 800)),              # 3:4, P on the right edge
    ], ids=['4:3-left', '4:3-right', '3:4-left', '3:4-right'])
    def test_side_edges_of_the_picture(self, inputs, bounds, size):
        """The frame is the exported picture, not the 16:9 camera frame
        around it: a point on its left or right edge keeps its label inside
        the picture and off the point."""
        on, off = layout(inputs, bounds, True, size), layout(inputs, bounds, False, size)
        assert not inside_frame(off['P']['box'], size=size)   # the solver puts it outside
        px = to_px(on, inputs)
        for name, entry in on.items():
            assert name not in entry['pointOverlaps'], (name, entry['box'])
            assert inside_frame(entry['box'], size=size), (name, entry['box'])
            assert geometry_hits(entry['box'], inputs, px) <= geometry_hits(
                off[name]['box'], inputs, px), name

    def test_labels_inside_the_frame_are_untouched(self):
        """Frame by the points (+20 %): every label is already in the frame,
        the clamp changes nothing."""
        bounds = [-0.7, 0.6, 5.7, 5.4]
        on, off = layout(GENERAL, bounds, True), layout(GENERAL, bounds, False)
        assert all(inside_frame(e['box']) for e in off.values())
        assert on == off

    def test_point_far_outside_falls_back_to_the_clip(self):
        """No candidate of the solver reaches into the frame (P 1.5 units
        above it): the drawn box is clipped into the frame."""
        bounds = [-5, -4, 5, 3.5]
        on = layout(GENERAL, bounds, True)
        assert inside_frame(on['P']['box'])


class TestClassicScene:
    """The same scene through ``AnimaGeoScene`` (DSL), as ``autoPlaceLabels``."""

    CODE = ('O = Point(0.3, -0.7)\nP = Point(-2.9, 1.1)\nc = Circle(O, P)\n'
            'r = Segment(O, P)\nM = Midpoint(O, P)\nc2 = Circle(M, O)\nd = Line(O, P)\n')

    # 80 px per unit; the picture of ``style.export`` puts a point on its edge.
    EXPORTS = {
        'P top 4:3': ('P', {'ptWidth': 800, 'ptHeight': 600, 'ptXZero': 592, 'ptYZero': 88}),
        'P left 4:3': ('P', {'ptWidth': 800, 'ptHeight': 600, 'ptXZero': 232, 'ptYZero': 300}),
        'O right 3:4': ('O', {'ptWidth': 600, 'ptHeight': 800, 'ptXZero': 576, 'ptYZero': 400}),
    }

    def _scene(self, export):
        from animageo.animageo import AnimaGeoScene
        sc = AnimaGeoScene()
        sc.style.export.update(dict(export, ptUnit=80, ptUnit_ggb=80))
        sc.putCode(self.CODE)
        sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
        for name in ('O', 'P', 'M'):
            sc.element(name).style['label_visible'] = True
        return sc

    @staticmethod
    def _box(sc, name, placement):
        """Drawn box (scene units) as ``ui.create_label`` places it."""
        elem = sc.element(name)
        w, h = label_size(sc, elem)
        edge = ANCHOR_EDGES[placement.label_anchor]
        x, y = elem.data.coords[:2]
        cx = x + placement.offset_ggb[0] / 80 - edge[0] * w / 2
        cy = y + placement.offset_ggb[1] / 80 - edge[1] * h / 2
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2

    @pytest.mark.parametrize('edge', list(EXPORTS))
    def test_label_stays_off_its_point_and_in_the_picture(self, edge):
        """The frame is the SVG picture of ``style.export``, not the wider
        16:9 camera frame around it."""
        point, ex = self.EXPORTS[edge]
        sc = self._scene(ex)
        left, top = -ex['ptXZero'] / 80, ex['ptYZero'] / 80
        right, bottom = left + ex['ptWidth'] / 80, top - ex['ptHeight'] / 80

        def inside(box):
            x0, y0, x1, y1 = box
            return (x0 >= left - 1e-6 and x1 <= right + 1e-6
                    and y0 >= bottom - 1e-6 and y1 <= top + 1e-6)

        off = compute_label_layout(sc, cfg=dict(PRESET, enabled=True, viewport_clamp=False))
        assert not inside(self._box(sc, point, off[point]))     # the solver puts it outside
        on = compute_label_layout(sc, cfg=dict(PRESET, enabled=True))
        for name in ('O', 'P', 'M'):
            x0, y0, x1, y1 = self._box(sc, name, on[name])
            assert inside((x0, y0, x1, y1)), name
            px_, py_ = sc.element(name).data.coords[:2]
            r = sc.element(name).style.get('size_px', 6.0) / 2 / 80
            near = math.hypot(px_ - min(max(px_, x0), x1), py_ - min(max(py_, y0), y1))
            assert near >= r, name


class TestClampPass:
    """``_viewport_clamp_pass`` on hand-made labels and obstacles."""

    NONE = np.empty((0, 2))
    WEIGHTS = (1.0, 10.0, 8.0)

    @classmethod
    def _pass(cls, segments, bounds=(-10.0, -10.0, 10.0, 3.0),
              anchor=(0.0, 5.0), center=(0.0, 5.3)):
        lbl = LabelInfo('P', np.array(anchor), 0.5, 0.2, clear_radius=0.05)
        result = [('P', np.array(center), 2)]          # N: drawn box above P
        _viewport_clamp_pass([lbl], result, bounds, segments, [], cls.NONE,
                             0.1, 0.02, cls.WEIGHTS, 100.0)
        return result[0]

    @staticmethod
    def _drawn(center, di, hw=0.5, hh=0.2):
        from animageo.label_placement import _DIR_TO_ANCHOR
        ex, ey = ANCHOR_EDGES[_DIR_TO_ANCHOR[di]]
        return np.array([center[0] - ex * hw, center[1] - ey * hh])

    @staticmethod
    def _fan(anchor, n=37, length=5.0):
        """Lines from ``anchor`` over the lower half-plane and across it."""
        x, y = anchor
        segs = [(np.array([x - 10.0, y]), np.array([x + 10.0, y]))]
        for k in range(n):
            t = -math.pi * k / (n - 1)
            segs.append((np.array([x, y]),
                         np.array([x + length * math.cos(t), y + length * math.sin(t)])))
        return segs

    def test_other_point_marker_counts(self):
        """A box that enters another point's marker touches it, even when
        the point itself lies outside the box; its own marker is not counted."""
        markers = np.array([[1.2, 0.0, 0.3], [0.0, 0.0, 0.1]])
        assert _drawn_box_harm((0.0, 0.0), 1.0, 0.5, [], [], markers, [],
                               (0.0, 0.0)) == (1, 0)
        far = np.array([[1.4, 0.0, 0.3]])
        assert _drawn_box_harm((0.0, 0.0), 1.0, 0.5, [], [], far, [],
                               (0.0, 0.0)) == (0, 0)

    def test_clip_into_the_frame_as_the_fallback(self):
        """P two units above the frame: no candidate reaches into it, the
        drawn box is clipped in at the top edge."""
        name, center, di = self._pass([])
        ex, ey = ANCHOR_EDGES['BC']                     # the anchor of N
        assert di == 2
        assert center[1] - ey * 0.2 == pytest.approx(3.0 - 0.2)   # drawn top = 3

    def test_point_outside_the_frame_keeps_its_label_out(self):
        """P above the frame is not drawn: its label is not pulled in onto a
        line it was clear of (no candidate reaches into the frame)."""
        line = [(np.array([-10.0, 2.9]), np.array([10.0, 2.9]))]
        name, center, di = self._pass(line)
        assert (di, tuple(center)) == (2, (0.0, 5.3))

    def test_partly_visible_keeps_the_solver_place(self):
        """The solver's box straddles the top edge and every place inside
        touches more lines: the label stays where it was, partly visible
        (as much of it outside as before the clamp, no more)."""
        anchor = (0.0, 2.9)
        name, center, di = self._pass(self._fan(anchor), anchor=anchor,
                                      center=(0.0, 2.95))
        assert (di, tuple(center)) == (2, (0.0, 2.95))

    def test_wholly_outside_near_its_point_takes_the_cheapest_place_inside(self):
        """test0/t3 A, B: the point just inside the top edge, lines fan out
        below it, the solver's box wholly above the frame. Every place in the
        frame touches lines; the label takes the cheapest of them, off its
        own point, instead of staying invisible."""
        anchor = (0.0, 2.9)
        name, center, di = self._pass(self._fan(anchor), anchor=anchor,
                                      center=(0.0, 3.3))
        drawn = self._drawn(center, di)
        left, bottom, right, top = -10.0, -10.0, 10.0, 3.0
        assert left <= drawn[0] - 0.5 and drawn[0] + 0.5 <= right
        assert bottom <= drawn[1] - 0.2 and drawn[1] + 0.2 <= top + 1e-12
        near = math.hypot(max(abs(drawn[0] - anchor[0]) - 0.5, 0.0),
                          max(abs(drawn[1] - anchor[1]) - 0.2, 0.0))
        assert near >= 0.05                                       # off its point
