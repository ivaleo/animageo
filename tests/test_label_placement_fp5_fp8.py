"""Round-4 feedback fixes:

FP-5/FP-7 — sector preservation: a label keeps the ORIGINAL side of its feature
(derived from the GGB offset direction, even a small/default one) when collision
free, instead of being relocated by the density/bisector heuristic.

FP-8 — angle external attachment: a manual angle label placed OUTSIDE the wedge
stays outside (not snapped back inside onto the arms).

FP-9 — viewport clamp: a label never extends past the rendered canvas edge.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    AngleParams,
    LabelInfo,
    compute_angle_label_center,
    compute_label_layout,
    _declutter_pass,
)
from animageo.geo.lib_elements import Angle

EMPTY = np.empty((0, 2))


def _scene(code):
    from animageo.animageo import AnimaGeoScene
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                            'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
    sc.putCode(code)
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return sc


# ── FP-5/FP-7: sector preservation ────────────────────────────────────

class TestSectorPreservation:
    def test_trivial_offset_sets_direction(self):
        """A sub-threshold offset (no pin) still biases the label to the same
        side: a tiny NORTH offset keeps the label north of the point."""
        sc = _scene("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
        for n in ('A', 'B', 'C'):
            sc.element(n).style['label_visible'] = True
        sc.element('B').style['label_offset_px'] = [0.0, 2.0]   # tiny, NORTH
        layout = compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        ox, oy = layout['B'].offset_ggb
        assert oy > abs(ox)          # placed to the north
        # but laid out fresh at a real distance (not pinned at 2px)
        assert (ox ** 2 + oy ** 2) ** 0.5 > 6.0

    def test_opposite_trivial_offsets_go_opposite_ways(self):
        """Two identical points with opposite tiny offsets end up on opposite
        sides — proving the direction comes from the offset, not a global rule."""
        sc = _scene("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
        for n in ('A', 'B', 'C'):
            sc.element(n).style['label_visible'] = True
        sc.element('A').style['label_offset_px'] = [0.0, 2.0]    # north
        sc.element('C').style['label_offset_px'] = [0.0, -2.0]   # south
        layout = compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        assert layout['A'].offset_ggb[1] > 0
        assert layout['C'].offset_ggb[1] < 0

    def test_no_respect_ignores_direction(self):
        """Without respect_current the offset direction is NOT consulted (the
        density heuristic runs) — byte-compatible default behaviour."""
        sc = _scene("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
        for n in ('A', 'B', 'C'):
            sc.element(n).style['label_visible'] = True
        sc.element('B').style['label_offset_px'] = [0.0, 2.0]
        base = compute_label_layout(sc, cfg={'enabled': True})
        # same as a run with no offset at all
        sc.element('B').style['label_offset_px'] = [0.0, 0.0]
        ref = compute_label_layout(sc, cfg={'enabled': True})
        assert np.allclose(base['B'].offset_ggb, ref['B'].offset_ggb)


# ── FP-8: angle external attachment ───────────────────────────────────

class TestAngleExterior:
    def test_exterior_flag_flips_bisector(self):
        ang = Angle(np.array([0.0, 0.0]), np.array([1.0, 0.0]),
                    np.array([0.0, 1.0]))
        ap_in = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                            gap_arc_px=3, gap_sides_px=3)
        ap_out = AngleParams(arc_r_px=30, half_w=0.1, half_h=0.05,
                             gap_arc_px=3, gap_sides_px=3, exterior=True)
        c_in = compute_angle_label_center(ang, ap_in, 100)
        c_out = compute_angle_label_center(ang, ap_out, 100)
        # interior is on the +,+ bisector; exterior is on the -,- bisector
        assert c_in[0] > 0 and c_in[1] > 0
        assert c_out[0] < 0 and c_out[1] < 0

    def test_arm_cap_pulls_narrow_angle_label_in(self):
        """Round-10 (scene4): a narrow angle's wide value label is capped to a
        fraction of the shorter arm so it stays near ITS vertex instead of
        flying down the bisector toward a neighbouring angle."""
        # ~11° angle, long arms (~5), wide label
        ang = Angle(np.array([0.0, 0.0]), np.array([5.0, 0.5]),
                    np.array([5.0, -0.5]))
        common = dict(arc_r_px=30, half_w=0.4, half_h=0.1,
                      gap_arc_px=3, gap_sides_px=3)
        ap_far = AngleParams(**common)
        ap_cap = AngleParams(**common, max_arm_fraction=0.45)
        v = ang.vertex[:2]
        d_far = np.linalg.norm(compute_angle_label_center(ang, ap_far, 50) - v)
        d_cap = np.linalg.norm(compute_angle_label_center(ang, ap_cap, 50) - v)
        arm = min(np.linalg.norm(ang.side1[:2]), np.linalg.norm(ang.side2[:2]))
        assert d_cap < d_far                 # cap pulled it in
        assert d_cap <= 0.45 * arm + 1e-6    # within the arm fraction

    def test_arm_cap_none_is_unchanged(self):
        ang = Angle(np.array([0.0, 0.0]), np.array([5.0, 0.5]),
                    np.array([5.0, -0.5]))
        common = dict(arc_r_px=30, half_w=0.4, half_h=0.1,
                      gap_arc_px=3, gap_sides_px=3)
        a = compute_angle_label_center(ang, AngleParams(**common), 50)
        b = compute_angle_label_center(
            ang, AngleParams(**common, max_arm_fraction=None), 50)
        assert np.allclose(a, b)

    def test_exterior_label_hugs_vertex(self):
        """Round-6: an exterior angle label sits close to the vertex (its own
        half-extent + gap), NOT at the interior ``arc_r + narrow-clamp`` distance
        (which made the 45° label fly far off the apex)."""
        # narrow angle opening to the right (~22°), big arc radius
        ang = Angle(np.array([0.0, 0.0]), np.array([1.0, 0.2]),
                    np.array([1.0, -0.2]))
        ap_out = AngleParams(arc_r_px=40, half_w=0.1, half_h=0.05,
                             gap_arc_px=3, gap_sides_px=3, exterior=True)
        c = compute_angle_label_center(ang, ap_out, 100)
        d = float(np.linalg.norm(c - ang.vertex[:2]))
        # ~ max(hw, hh) + gap = 0.1 + 0.03 = 0.13, far below arc_r/ptUnit = 0.40
        assert d < 0.2
        assert c[0] < 0          # still on the exterior (left) side

    def test_manual_exterior_offset_kept_outside(self):
        """An angle whose manual label was dragged outside the wedge keeps it
        outside when respecting current positions."""
        sc = _scene(
            "A = Point(0, 0)\nB = Point(3, 0)\nC = Point(3, 1)\n"
            "ang = Angle(B, A, C)\n")
        ang_el = sc.element('ang')
        ang_el.style['label_visible'] = True
        v = ang_el.data
        v1 = v.side1[:2] / np.linalg.norm(v.side1[:2])
        v2 = v.side2[:2] / np.linalg.norm(v.side2[:2])
        bis = v1 + v2
        bis = bis / np.linalg.norm(bis)
        # drag the label well onto the EXTERIOR side (opposite the bisector)
        ext = -bis * 30.0   # ggb px
        ang_el.style['label_offset_px'] = [float(ext[0]), float(ext[1])]

        layout = compute_label_layout(
            sc, cfg={'enabled': True, 'respect_current_position': True,
                     'respect_min_offset_px': 6.0})
        pl = layout['ang']
        # reconstruct the RENDERED center exactly as _render_angle does: it
        # measures label_offset_px from the INTERIOR base point (exterior=False).
        from animageo.label_placement import compute_angle_label_base_center
        base = compute_angle_label_base_center(
            v, AngleParams(arc_r_px=pl.angle_params.arc_r_px,
                           half_w=pl.angle_params.half_w,
                           half_h=pl.angle_params.half_h,
                           gap_arc_px=pl.angle_params.gap_arc_px,
                           gap_sides_px=pl.angle_params.gap_sides_px,
                           render_r_px=pl.angle_params.render_r_px,
                           exterior=False), 50)
        center = base + np.array([pl.offset_ggb[0] / 50, pl.offset_ggb[1] / 50])
        assert pl.angle_params.exterior is True
        assert float(np.dot(center - v.vertex[:2], bis)) < 0  # outside the wedge

    def test_default_angle_stays_interior(self):
        """Without respect_current, the exterior detection never fires."""
        sc = _scene(
            "A = Point(0, 0)\nB = Point(3, 0)\nC = Point(3, 1)\n"
            "ang = Angle(B, A, C)\n")
        sc.element('ang').style['label_visible'] = True
        sc.element('ang').style['label_offset_px'] = [-30.0, -30.0]
        layout = compute_label_layout(sc, cfg={'enabled': True})
        assert layout['ang'].angle_params.exterior is False


# ── FP-9: viewport clamp ──────────────────────────────────────────────

class TestViewportClamp:
    def test_label_kept_inside_viewport(self):
        sc = _scene("P = Point(5.7, 0)\n")  # near right edge (=6.0)
        sc.element('P').style['label_visible'] = True
        left, bottom, right, top = sc._get_scene_bounds(padding=0)
        anchor = sc.element('P').data.coords[:2]

        def cx(layout):
            o = layout['P'].offset_ggb
            return float((anchor + np.array([o[0] / 50, o[1] / 50]))[0])

        no_clamp = compute_label_layout(sc, cfg={'enabled': True})
        clamped = compute_label_layout(
            sc, cfg={'enabled': True, 'viewport_clamp': True})
        # without clamp the eastward label spills past the edge; with clamp it
        # is pulled back inside.
        assert cx(clamped) <= right + 1e-6
        assert cx(clamped) <= cx(no_clamp) + 1e-6

    def test_clamp_off_by_default(self):
        sc = _scene("P = Point(5.7, 0)\n")
        sc.element('P').style['label_visible'] = True
        a = compute_label_layout(sc, cfg={'enabled': True})
        b = compute_label_layout(sc, cfg={'enabled': True, 'viewport_clamp': False})
        assert np.allclose(a['P'].offset_ggb, b['P'].offset_ggb)


# ── FP-6: declutter near-coincident labels ────────────────────────────

class TestDeclutter:
    def _lbl(self, name):
        l = LabelInfo(name=name, anchor=np.array([0.0, 0.0]),
                      half_w=0.2, half_h=0.1)
        return l

    def test_separates_overlapping_pair_in_free_space(self):
        la, lb = self._lbl('A'), self._lbl('B')
        result = [('A', np.array([0.0, 0.30]), 2),
                  ('B', np.array([0.0, 0.35]), 2)]   # overlapping vertically
        _declutter_pass([la, lb], result, [], [], EMPTY, padding=0.0, gap=0.1)
        ya, yb = result[0][1][1], result[1][1][1]
        assert abs(yb - ya) >= 0.3 - 1e-9   # pushed to hha+hhb+gap apart

    def test_does_not_push_label_onto_geometry(self):
        la, lb = self._lbl('A'), self._lbl('B')
        result = [('A', np.array([0.0, 0.30]), 2),
                  ('B', np.array([0.0, 0.35]), 2)]
        # a horizontal line exactly where A would be pushed (y≈0.175)
        seg = [(np.array([-1.0, 0.175]), np.array([1.0, 0.175]))]
        _declutter_pass([la, lb], result, seg, [], EMPTY, padding=0.0, gap=0.1)
        # A is never pushed ONTO the line — its bbox stays clear of y=0.175
        # (the guard refuses any move that would newly hit geometry).
        from animageo.label_placement import _candidate_has_overlap
        assert not _candidate_has_overlap(result[0][1], la.half_w, la.half_h,
                                          seg, [], EMPTY)

    def test_noop_when_already_clear(self):
        la, lb = self._lbl('A'), self._lbl('B')
        result = [('A', np.array([0.0, 1.0]), 2),
                  ('B', np.array([0.0, -1.0]), 6)]   # far apart
        before = [c.copy() for _, c, _ in result]
        _declutter_pass([la, lb], result, [], [], EMPTY, padding=0.0, gap=0.1)
        assert np.allclose(result[0][1], before[0])
        assert np.allclose(result[1][1], before[1])
