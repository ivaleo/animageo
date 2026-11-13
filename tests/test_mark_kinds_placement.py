"""Kinds of marks in the label placement: what they add to the obstacles,
the label radius of a decorated angle in the three copies of the renderer's
geometry, the rule «arcs instead of a square»."""
import math
import textwrap

import numpy as np
import pytest

pytest.importorskip('manim')

from animageo import label_placement as lp  # noqa: E402
from animageo.animageo import AnimaGeoScene  # noqa: E402

PT = 80.0


def framed(code, style=None):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(style=style, export={'size': {'width': 480, 'height': 400}})
    exp = s.style.export
    exp.update(ptUnit=PT, ptUnit_style=PT, ptUnit_ggb=PT, ptWidth=480, ptHeight=400, ptXZero=120, ptYZero=340)
    s._set_camera_from_export(exp)
    return s


def angle_code(c=(1, 2), extra=''):
    return f'A = Point(0, 0)\nB = Point(3, 0)\nC = Point({c[0]}, {c[1]})\na = Angle(B, A, C)\n' + extra


def obstacles(code):
    segments, *_ = lp._collect_obstacles(framed(code))
    return segments


def elem(scene, name):
    return scene.geo.element(name)


class TestObstacles:
    def test_no_new_keys_no_new_obstacles(self):
        code = angle_code() + 's = Segment(B, C)\nl = Line(A, C)\n'
        given = code + ("a.style.arc_style = 'solid'\na.style.arc_tick_count = 0\na.style.arrow_head = 'none'\n"
                        "s.style.arrow_head = 'none'\ns.style.parallel_count = 0\nl.style.parallel_count = 0\n")
        assert len(obstacles(code)) == len(obstacles(given))

    def test_arc_ticks_and_head(self):
        base = len(obstacles(angle_code()))
        ticks = obstacles(angle_code(extra='a.style.arc_tick_count = 2\n'))
        assert len(ticks) == base + 2
        (p, q) = ticks[-1]
        assert np.hypot(*q) * PT == pytest.approx(17 + 4.5)          # across the arc, half a tick past it
        head = obstacles(angle_code(extra="a.style.arrow_head = 'both'\n"))
        assert len(head) == base + 6                                  # two triangles

    def test_a_wave_is_the_arc(self):
        assert len(obstacles(angle_code(extra="a.style.arc_style = 'wave'\n"))) == len(obstacles(angle_code()))

    def test_segment_heads_and_chevrons(self):
        code = angle_code() + 's = Segment(B, C)\n'
        base = len(obstacles(code))
        assert len(obstacles(code + "s.style.arrow_head = 'both'\n")) == base + 6
        assert len(obstacles(code + 's.style.parallel_count = 2\n')) == base + 4

    def test_line_chevrons(self):
        code = angle_code() + 'l = Line(A, C)\n'
        base = len(obstacles(code))
        segs = obstacles(code + 'l.style.parallel_count = 3\n')
        assert len(segs) == base + 6

    def test_segment_ticks_stay_out(self):
        code = angle_code() + 's = Segment(B, C)\n'
        assert len(obstacles(code + 's.style.tick_count = 2\n')) == len(obstacles(code))


class TestLabelRadius:
    def test_the_label_clears_ticks_and_waves(self):
        plain = framed(angle_code())
        ticks = framed(angle_code(extra='a.style.arc_tick_count = 1\n'))
        wave = framed(angle_code(extra="a.style.arc_style = 'wave'\na.style.tick_count = 2\n"))
        r = [float(np.hypot(*lp.label_spot(s, elem(s, 'a')))) * PT for s in (plain, ticks, wave)]
        assert r[0] == pytest.approx(17)
        assert r[1] == pytest.approx(17 + 4.5)
        assert r[2] == pytest.approx(17 + 4 + 1)                    # the wave step max(s, 2A + 2), then A

    def test_label_spot_is_where_the_renderer_hangs_it(self):
        s = framed(angle_code(extra="a.style.arc_tick_count = 2\na.style.label_visible = True\n"
                                    "a.style.label_anchor = 'MC'\n"))
        group = s.CreateMObject(elem(s, 'a'))
        (label,) = [m for m in group.submobjects if getattr(m, '_animageo_is_label', False)]
        spot = lp.label_spot(s, elem(s, 'a'))
        assert np.hypot(*label.get_center()[:2]) == pytest.approx(np.hypot(*spot), abs=1e-6)

    def test_the_three_copies_agree(self):
        s = framed(angle_code(extra='a.style.arc_tick_count = 1\n'))
        a = elem(s, 'a')
        params = lp._angle_label_params(s, a, 0.0, 0.0)
        placement = lp._angle_placement_params(s, a, type('L', (), {'half_w': 0.0, 'half_h': 0.0})(),
                                               gap_arc_px=3, gap_sides_px=3, ang_rshift_px=1.5,
                                               max_arm_fraction=None)
        v, start, span, right, radius, *_ = lp._angle_drawn_sector(s, a)
        assert not right and radius * PT == pytest.approx(17)        # the arc itself
        assert params.render_r_px == placement.render_r_px == pytest.approx(21.5)
        assert params.arc_r_px == placement.arc_r_px == pytest.approx(21.5)

    def test_with_the_fit(self):
        fit = {'rendering': {'angle_marker_fit': True}}
        s = framed(angle_code((0.2, 0.2), "a.style.arc_tick_count = 1\n"), style=fit)
        a = elem(s, 'a')
        extent, marker = lp._fitted_angle_marker(s, a)
        assert marker.clamped                                         # 0.6·0.2828·80 = 13.6 < 17 + 4.5
        outer = 0.6 * math.hypot(0.2, 0.2) * PT - 4.5
        assert lp._angle_drawn_sector(s, a)[4] * PT == pytest.approx(outer)
        assert lp._angle_label_params(s, a, 0, 0).render_r_px == pytest.approx(outer + 4.5)


class TestArcsInsteadOfSquare:
    def test_rule(self):
        right = framed(angle_code((0, 2)))
        assert lp._angle_drawn_sector(right, elem(right, 'a'))[3]
        arcs = framed(angle_code((0, 2), 'a.style.arc_tick_count = 1\n'))
        assert not lp._angle_drawn_sector(arcs, elem(arcs, 'a'))[3]
        assert lp._angle_label_params(arcs, elem(arcs, 'a'), 0, 0).arc_r_px == pytest.approx(21.5)
        square = framed(angle_code((0, 2), 'a.style.arc_tick_count = 1\na.style.right_angle_marker = True\n'))
        assert lp._angle_drawn_sector(square, elem(square, 'a'))[3]
        assert len(lp._mark_obstacle_segments(square, elem(square, 'a'))) == 0

    def test_no_arcs_no_square(self):
        s = framed(angle_code((0, 2), 'a.style.arc_tick_count = 1\na.style.tick_count = 0\n'))
        assert not lp._angle_drawn_sector(s, elem(s, 'a'))[3]
        assert lp._mark_obstacle_segments(s, elem(s, 'a')) == []


class TestHollowPointSize:
    def test_labels_clear_the_drawn_hollow_point(self):
        """A hollow triangle of 8 px is drawn at 12 px (its hole holds 3 px):
        placement sees the drawn marker, a solid one keeps its size."""
        code = "P = Point(1, 1)\nP.style.point_shape = 'triangle_up'\nP.style.point_fill = '{}'\nP.style.size_px = {}\n"
        radius = lambda fill, size: lp._collect_point_markers(framed(code.format(fill, size)), PT)[0][2] * PT  # noqa
        assert radius('hollow', 8) == pytest.approx(6) == radius('solid', 12)
        assert radius('solid', 8) == pytest.approx(4)
