"""The marker of an angle: its fit to the sides (``rendering.angle_marker_fit``)
and its display mode — manim-free (``animageo.angle_marker``, native paint)."""
import math
from types import SimpleNamespace

import pytest

from animageo import angle_marker as am
from animageo import native
from animageo.native.registry import REGISTRY_VERSION
from tests.native.conftest import DocBuilder, num, ref, ref_list

FIT = {'rendering': {'angle_marker_fit': True}}
BOUNDS = (-1, -1, 7, 5)          # ptUnit 100 = ptUnitStyle


def doc(c=(0.2, 0.2), bounds=BOUNDS):
    b = DocBuilder('fit', bounds=bounds, registry_version=REGISTRY_VERSION)
    b.free('A', 0, 0).free('B', 4, 0).free('C', *c)
    return b


def paint(b, style=FIT, **kw):
    return native.resolve_paint(b.doc, style, **kw)


def angle_of(p, el_id):
    return p['elements'][el_id]['angle']


# ── pure parts ───────────────────────────────────────────────────────────

class TestFitExtent:
    def test_no_bound_or_room_leaves_it(self):
        assert am.fit_extent(20, 17, None, 3) == (0.0, False, False)
        assert am.fit_extent(20, 17, 20, 3) == (0.0, False, False)

    def test_arcs_move_in_together(self):
        delta, clamped, hidden = am.fit_extent(20, 17, 12, 3)
        assert (delta, clamped, hidden) == (8.0, True, False)

    def test_hidden_when_the_inner_arc_is_too_small(self):
        assert am.fit_extent(20, 17, 5.9, 3) == pytest.approx((14.1, True, True))
        assert am.fit_extent(20, 17, 6, 3) == (14.0, True, False)

    def test_square(self):
        delta, clamped, hidden = am.fit_extent(12.0, 12.0, 11.7, 3)
        assert delta == pytest.approx(0.3) and clamped and not hidden

    def test_a_small_desired_marker_that_fits_stays(self):
        assert am.fit_extent(2, 2, 10, 3) == (0.0, False, False)


class TestSettings:
    @staticmethod
    def scene(value):
        return SimpleNamespace(style=SimpleNamespace(rendering={'angle_marker_fit': value}))

    def test_off_by_default(self):
        assert am.fit_settings(SimpleNamespace(style=SimpleNamespace(rendering={}))) is None
        assert am.fit_settings(self.scene(False)) is None
        assert am.fit_settings(self.scene({'side_fraction': 0.6})) is None

    def test_on(self):
        assert am.fit_settings(self.scene(True)) == am.FitSettings(0.5, 3.0)
        assert am.fit_settings(self.scene({'enabled': True, 'side_fraction': 0.65, 'hide_below_px': 0})) == \
            am.FitSettings(0.65, 0.0)

    @pytest.mark.parametrize('bad', [0, -1, 'x', None, True, float('nan')])
    def test_bad_values_fall_back(self, bad):
        got = am.fit_settings(self.scene({'enabled': True, 'side_fraction': bad, 'hide_below_px': bad}))
        assert got.side_fraction == 0.5
        assert got.hide_below_px == (0.0 if bad == 0 and not isinstance(bad, bool) else 3.0)

    def test_right_angle_tolerance_is_the_renderers(self):
        assert am.is_right_angle(math.pi / 2 + 1.5e-5)
        assert not am.is_right_angle(math.pi / 2 + 1.6e-5)


# ── supports of the sides (native graph) ─────────────────────────────────

class TestNativeSupport:
    def test_defining_points(self):
        b = doc().angle('g', 'B', 'A', 'C')
        fit = angle_of(paint(b), 'g')['fit']
        assert fit['supportWorld'] == pytest.approx([4.0, math.hypot(0.2, 0.2)])

    def test_a_visible_line_through_vertex_and_point_lifts_the_bound(self):
        b = doc().angle('g', 'B', 'A', 'C').line('l', 'A', 'C')
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] is None
        b.doc['appearance'] = {'l': {'visible': False}}
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_a_ray_counts_only_from_the_vertex(self):
        b = doc().angle('g', 'B', 'A', 'C').ray('r', 'A', 'C')
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] is None
        b = doc().angle('g', 'B', 'A', 'C').ray('r', 'C', 'A')
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_a_segment_keeps_the_bound(self):
        b = doc().angle('g', 'B', 'A', 'C').segment('s', 'A', 'C')
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_a_point_put_on_the_line_by_an_operation(self):
        b = doc().free('D', 3, 3).line('l', 'A', 'D').line('m', 'B', 'C').intersect('P', 'l', 'm')
        b.angle('g', 'B', 'A', 'P')
        support = angle_of(paint(b), 'g')['fit']['supportWorld']
        assert support[0] == pytest.approx(4.0) and support[1] is None

    def test_a_line_through_the_point_but_not_the_vertex(self):
        b = doc().free('D', 3, 3).line('l', 'C', 'D').angle('g', 'B', 'A', 'C')
        assert angle_of(paint(b), 'g')['fit']['supportWorld'][1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_between_lines_has_no_bound(self):
        b = doc().line('l', 'A', 'B').line('m', 'A', 'C')
        b.op('op_g', 'angle.between_lines', {'first': ref('l'), 'second': ref('m')}, [('angle', 'g', 'angle')])
        fit = angle_of(paint(b), 'g')['fit']
        assert fit['supportWorld'] == [None, None] and fit['limitPx'] is None and not fit['clamped']

    def test_by_size(self):
        b = doc()
        b.op('op_g', 'angle.by_size', {'vertex': ref('A'), 'a': ref('C'), 'size': num(1.0)},
             [('angle', 'g', 'angle'), ('point', 'P', 'point')])
        assert angle_of(paint(b), 'g')['fit']['supportWorld'] == pytest.approx([math.hypot(0.2, 0.2)] * 2)

    def test_polygon_angles(self):
        b = doc().polygon('T', 'A', 'B', 'C')
        b.op('op_angles', 'measure.polygon_angles', {'polygon': ref('T')},
             [('angle.1', 'a1', 'angle'), ('angle.2', 'a2', 'angle'), ('angle.3', 'a3', 'angle')])
        p = paint(b)
        assert sorted(angle_of(p, 'a1')['fit']['supportWorld']) == pytest.approx(
            sorted([4.0, math.hypot(0.2, 0.2)]))
        assert sorted(angle_of(p, 'a2')['fit']['supportWorld']) == pytest.approx(
            sorted([4.0, math.hypot(3.8, 0.2)]))


# ── the fit in paint ─────────────────────────────────────────────────────

class TestPaint:
    def test_without_the_key_nothing_changes(self):
        b = doc().angle('g', 'B', 'A', 'C')
        assert 'fit' not in angle_of(native.resolve_paint(b.doc), 'g')
        assert native.resolve_paint(b.doc) == native.resolve_paint(b.doc, {'rendering': {}})

    def test_clamped_arcs(self):
        b = doc().angle('g', 'B', 'A', 'C')
        g = angle_of(paint(b), 'g')
        limit = 0.5 * math.hypot(0.2, 0.2) * 100
        assert g['fit']['limitPx'] == pytest.approx(limit) and g['fit']['clamped'] and not g['fit']['hidden']
        assert g['arcSizePx'] == 17                     # the desired size is kept
        assert g['radiusPx'] == pytest.approx(limit)
        assert g['arcRadiiPx'] == pytest.approx([limit])

    def test_spacing_of_several_arcs_is_kept(self):
        b = doc().angle('g', 'B', 'A', 'C')
        b.doc['appearance'] = {'g': {'overrides': {'tick_count': 3, 'arc_shift_px': 2}}}
        g = angle_of(paint(b), 'g')
        limit = 0.5 * math.hypot(0.2, 0.2) * 100
        assert g['arcRadiiPx'] == pytest.approx([limit, limit - 2, limit - 4])

    def test_unclamped_matches_the_default(self):
        b = doc(c=(1, 3)).angle('g', 'B', 'A', 'C')
        with_fit, without = angle_of(paint(b), 'g'), angle_of(native.resolve_paint(b.doc), 'g')
        fit = with_fit.pop('fit')
        assert with_fit == without and not fit['clamped']

    def test_hidden_marker_keeps_its_label_radius(self):
        b = doc(c=(0.04, 0.04)).angle('g', 'B', 'A', 'C')
        b.doc['appearance'] = {'g': {'label': {'mode': 'name'}}}
        p = paint(b)
        g = angle_of(p, 'g')
        limit = 0.5 * math.hypot(0.04, 0.04) * 100
        assert g['fit']['hidden'] and g['arcRadiiPx'] == [] and g['radiusPx'] == pytest.approx(limit)
        spot = p['elements']['g']['label']['spotWorld']
        assert math.hypot(*spot) * 100 == pytest.approx(limit)

    def test_label_of_a_clamped_marker(self):
        b = doc().angle('g', 'B', 'A', 'C')
        b.doc['appearance'] = {'g': {'label': {'mode': 'name'}, 'overrides': {'label_radial_offset_px': 2}}}
        spot = paint(b)['elements']['g']['label']['spotWorld']
        assert math.hypot(*spot) * 100 == pytest.approx(0.5 * math.hypot(0.2, 0.2) * 100 + 2)

    def test_zoom_brings_the_desired_radius_back(self):
        b = doc().angle('g', 'B', 'A', 'C')
        small = paint(b)
        b.doc['viewDefaults']['bounds'] = [-0.5, -0.5, 3.5, 2.5]
        big = paint(b)
        assert (small['ptUnitStyle'], big['ptUnitStyle']) == (100.0, 200.0)
        assert angle_of(small, 'g')['fit']['clamped'] and angle_of(small, 'g')['radiusPx'] < 17
        assert not angle_of(big, 'g')['fit']['clamped'] and angle_of(big, 'g')['radiusPx'] == 17

    def test_square(self):
        b = doc(c=(0, 0.2)).right_mark('ra', 'B', 'A', 'C')
        ra = angle_of(paint(b), 'ra')
        s = 0.5 * 0.2 * 100
        assert ra['right'] and ra['fit']['clamped'] and ra['rightSizePx'] == pytest.approx(s * math.sqrt(2))
        assert ra['square'][0] == pytest.approx([0.1, 0])

    def test_hidden_square(self):
        b = doc(c=(0, 0.04)).right_mark('ra', 'B', 'A', 'C')
        ra = angle_of(paint(b), 'ra')
        assert ra['fit']['hidden'] and 'square' not in ra

    def test_fraction(self):
        b = doc().angle('g', 'B', 'A', 'C')
        style = {'rendering': {'angle_marker_fit': {'enabled': True, 'side_fraction': 0.65}}}
        g = angle_of(paint(b, style), 'g')
        assert g['fit']['limitPx'] == pytest.approx(0.65 * math.hypot(0.2, 0.2) * 100)


# ── modes ────────────────────────────────────────────────────────────────

def test_explicit_null_on_a_right_angle_mark_is_the_square():
    b = doc(c=(0.5, 3)).right_mark('ra', 'B', 'A', 'C')          # not right: the check fails
    assert angle_of(native.resolve_paint(b.doc), 'ra')['right'] is True
    b.doc['appearance'] = {'ra': {'overrides': {'right_angle_marker': None}}}
    assert angle_of(native.resolve_paint(b.doc), 'ra')['right'] is True
    b.doc['appearance'] = {'ra': {'overrides': {'right_angle_marker': False}}}
    assert angle_of(native.resolve_paint(b.doc), 'ra')['right'] is False


# ── classic constructions (GGB, DSL) ─────────────────────────────────────

def classic(code, rendering=None):
    from animageo.geo.construction import Construction
    from animageo.label_placement import LayoutInput
    from animageo.parsers import dsl
    from animageo.style.config import StyleConfig
    constr = Construction()
    dsl.run(constr, code)
    constr.rebuild()
    export = {'ptUnit': 100.0, 'ptUnit_style': 100.0}
    rendering = FIT['rendering'] if rendering is None else rendering
    scene = LayoutInput(geo=constr, style=SimpleNamespace(export=export, rendering=rendering),
                        style_config=StyleConfig.load(None))
    return scene, constr


BASE = 'A = Point(0, 0)\nB = Point(4, 0)\nC = Point(0.2, 0.2)\ng = Angle(B, A, C)\n'


class TestClassicSupport:
    def test_defining_points(self):
        scene, constr = classic(BASE)
        assert am.side_support(scene, constr.element('g')) == pytest.approx((4.0, math.hypot(0.2, 0.2)))

    @pytest.mark.parametrize('extra, unbounded', [
        ('l = Line(A, C)\n', True),
        ('r = Ray(A, C)\n', True),
        ('r = Ray(C, A)\n', False),
        ('s = Segment(A, C)\n', False),
        ('D = Point(3, 3)\nl = Line(C, D)\n', False),
        ('D = Point(1, 1)\nl = Line(A, D)\nm = Line(C, B)\n', False),       # collinear by numbers only
    ])
    def test_lines(self, extra, unbounded):
        scene, constr = classic(BASE + extra)
        support = am.side_support(scene, constr.element('g'))
        assert (support[1] is None) == unbounded

    def test_intersection_on_a_line(self):
        scene, constr = classic('A = Point(0, 0)\nB = Point(4, 0)\nD = Point(3, 3)\nE = Point(4, 1)\n'
                                'l = Line(A, D)\nm = Line(B, E)\nP = Intersect(l, m)\ng = Angle(B, A, P)\n')
        support = am.side_support(scene, constr.element('g'))
        assert support[0] == pytest.approx(4.0) and support[1] is None

    def test_hidden_line(self):
        scene, constr = classic(BASE + 'l = Line(A, C)\n')
        constr.element('l').style['visible'] = False
        assert am.side_support(scene, constr.element('g'))[1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_fit_and_max_desired(self):
        scene, constr = classic(BASE)
        g = constr.element('g')
        fit = am.marker_fit(scene, g)
        limit = 0.5 * math.hypot(0.2, 0.2) * 100
        assert fit.clamped and fit.limit_px == pytest.approx(limit)
        assert am.max_desired_px(scene, g) == pytest.approx(
            {'limitPx': limit, 'arcSizePx': limit, 'rightAngleSizePx': math.sqrt(2) * limit})
        off, constr = classic(BASE, rendering={})
        assert am.marker_fit(off, constr.element('g')) is None and am.max_desired_px(off, constr.element('g')) is None
