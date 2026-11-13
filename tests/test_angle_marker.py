"""The marker of an angle: its fit to the sides (``rendering.angle_marker_fit``)
— manim-free (``animageo.angle_marker``)."""
import math
from types import SimpleNamespace

import pytest

from animageo import angle_marker as am

FIT = {'rendering': {'angle_marker_fit': True}}
K = 0.6                          # side_fraction by default


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
        assert am.fit_settings(self.scene(True)) == am.FitSettings(K, 3.0)
        assert am.fit_settings(self.scene({'enabled': True, 'side_fraction': 0.65, 'hide_below_px': 0})) == \
            am.FitSettings(0.65, 0.0)

    @pytest.mark.parametrize('bad', [0, -1, 'x', None, True, float('nan')])
    def test_bad_values_fall_back(self, bad):
        got = am.fit_settings(self.scene({'enabled': True, 'side_fraction': bad, 'hide_below_px': bad}))
        assert got.side_fraction == K
        assert got.hide_below_px == (0.0 if bad == 0 and not isinstance(bad, bool) else 3.0)

    def test_right_angle_tolerance_is_the_renderers(self):
        assert am.is_right_angle(math.pi / 2 + 1.5e-5)
        assert not am.is_right_angle(math.pi / 2 + 1.6e-5)


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

    @pytest.mark.parametrize('extra, support', [
        ('D = Point(1, 1)\ns = Segment(A, D)\n', math.sqrt(2)),
        ('D = Point(1, 1)\ns = Segment(D, A)\n', math.sqrt(2)),
        ('D = Point(1, 1)\nT = Polygon(A, B, D)\n', math.sqrt(2)),
        ('D = Point(0.1, 0.1)\ns = Segment(A, D)\n', math.hypot(0.2, 0.2)),
        ('D = Point(1, 2)\ns = Segment(A, D)\n', math.hypot(0.2, 0.2)),
        ('D = Point(1, 1)\nE = Point(0.1, 0.1)\ns = Segment(E, D)\n', math.hypot(0.2, 0.2)),
    ])
    def test_a_segment_from_the_vertex_past_the_point(self, extra, support):
        scene, constr = classic(BASE + extra)
        assert am.side_support(scene, constr.element('g'))[1] == pytest.approx(support)

    @pytest.mark.parametrize('c, support', [((0.2, 0.2), 2 * math.sqrt(2)), ((-0.2, -0.2), math.sqrt(2))])
    def test_a_segment_through_the_vertex(self, c, support):
        scene, constr = classic('X = Point(-1, -1)\nD = Point(2, 2)\ns = Segment(X, D)\nA = Point(s, 1 / 3)\n'
                                f'B = Point(4, 0)\nC = Point{c}\ng = Angle(B, A, C)\n')
        assert am.side_support(scene, constr.element('g')) == pytest.approx((4.0, support))

    def test_collinear_by_numbers_only(self):
        # a segment through the vertex that the graph does not put it on
        scene, constr = classic(BASE + 'X = Point(-1, -1)\nD = Point(1, 1)\ns = Segment(X, D)\n')
        assert am.side_support(scene, constr.element('g'))[1] == pytest.approx(math.hypot(0.2, 0.2))

    def test_hidden_segment(self):
        scene, constr = classic(BASE + 'D = Point(1, 1)\ns = Segment(A, D)\n')
        constr.element('s').style['visible'] = False
        assert am.side_support(scene, constr.element('g'))[1] == pytest.approx(math.hypot(0.2, 0.2))

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
        limit = K * math.hypot(0.2, 0.2) * 100
        assert fit.clamped and fit.limit_px == pytest.approx(limit)
        assert am.max_desired_px(scene, g) == pytest.approx(
            {'limitPx': limit, 'arcSizePx': limit, 'rightAngleSizePx': math.sqrt(2) * limit})
        off, constr = classic(BASE, rendering={})
        assert am.marker_fit(off, constr.element('g')) is None and am.max_desired_px(off, constr.element('g')) is None
