"""Kinds of marks in the manim renderer and the cairo SVG export (the
manim-free geometry: ``tests/test_mark_shapes.py``)."""
import math
import re
import textwrap

import numpy as np
import pytest

pytest.importorskip('manim')

from animageo.animageo import AnimaGeoScene  # noqa: E402
from animageo.dash import get_dash  # noqa: E402

PT = 80.0


def framed(code, style=None):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(style=style, export={'size': {'width': 480, 'height': 400}})
    exp = s.style.export
    exp.update(ptUnit=PT, ptUnit_style=PT, ptUnit_ggb=PT, ptWidth=480, ptHeight=400, ptXZero=120, ptYZero=340)
    s._set_camera_from_export(exp)
    return s


def built(scene, name):
    return scene.CreateMObject(scene.geo.element(name))


def angle_code(c=(1, 2), extra=''):
    return f'A = Point(0, 0)\nB = Point(3, 0)\nC = Point({c[0]}, {c[1]})\na = Angle(B, A, C)\n' + extra


def radii(mobj):
    pts = mobj.points[:, :2]
    return np.hypot(pts[:, 0], pts[:, 1]) * PT


def svg(scene, tmp_path, name='out', **kw):
    path = tmp_path / f'{name}.svg'
    scene.exportSVG(str(path), **kw)
    return path.read_bytes()


DEFAULTS = """
a.style.arc_style = 'solid'
a.style.arc_tick_count = 0
a.style.arrow_head = 'none'
s.style.arrow_head = 'none'
s.style.parallel_count = 0
A.style.point_fill = 'solid'
"""


def test_default_values_draw_as_before(tmp_path):
    code = angle_code() + 's = Segment(B, C)\n'
    plain = svg(framed(code), tmp_path, 'plain')
    given = svg(framed(code + DEFAULTS), tmp_path, 'given')
    assert plain == given


class TestArcs:
    def test_wave(self):
        group = built(framed(angle_code(extra="a.style.arc_style = 'wave'\na.style.tick_count = 2\n")), 'a')
        outer, inner = group.submobjects[1:3]
        # the waves step max(s, 2A + 2) = 4 px apart: 2 px between the crests
        assert radii(outer).max() == pytest.approx(17 + 4 + 1, abs=1e-6)
        assert radii(inner).min() == pytest.approx(17 - 1, abs=1e-6)
        assert radii(outer).min() - radii(inner).max() == pytest.approx(2, abs=1e-6)

    def test_dashed_arcs_are_fitted_each(self):
        group = built(framed(angle_code(extra="a.style.arc_style = 'dashed'\na.style.tick_count = 2\n")), 'a')
        arcs = group.submobjects[1:3]
        dashes = [get_dash(arc) for arc in arcs]
        assert all(d is not None for d in dashes)
        assert dashes[0].on != pytest.approx(dashes[1].on)
        assert all(d.on * PT == pytest.approx(2, rel=0.3) for d in dashes)

    def test_ticks_and_head(self):
        group = built(framed(angle_code(extra="a.style.arc_tick_count = 2\na.style.arrow_head = 'end'\n")), 'a')
        kinds = [type(m).__name__ for m in group.submobjects]
        assert kinds == ['AnnularSector', 'Arc', 'Line', 'Line', 'Polygon']
        tick = group.submobjects[2]
        assert radii(tick).max() == pytest.approx(17 + 4.5, abs=1e-6)
        assert radii(tick).min() == pytest.approx(17 - 4.5, abs=1e-6)
        # the outer arc stops at the base of the head
        span = group.submobjects[1].get_angle() if hasattr(group.submobjects[1], 'get_angle') else None
        c = math.atan2(2, 1)
        assert span == pytest.approx(c - 6 / 17)

    def test_no_arcs_no_decoration(self):
        group = built(framed(angle_code(extra="a.style.arc_style = 'wave'\na.style.arc_tick_count = 2\n"
                                              "a.style.arrow_head = 'both'\na.style.tick_count = 0\n")), 'a')
        assert [type(m).__name__ for m in group.submobjects] == ['AnnularSector']

    def test_a_decorated_right_angle_is_arcs(self):
        right = built(framed(angle_code((0, 2))), 'a')
        assert type(right.submobjects[0]).__name__ == 'Polygon'
        arcs = built(framed(angle_code((0, 2), "a.style.arc_tick_count = 1\n")), 'a')
        assert type(arcs.submobjects[0]).__name__ == 'AnnularSector'
        square = built(framed(angle_code((0, 2), "a.style.arc_tick_count = 1\n"
                                                 "a.style.right_angle_marker = True\n")), 'a')
        assert [type(m).__name__ for m in square.submobjects] == ['Polygon', 'VMobject']

    def test_hatch(self):
        group = built(framed(angle_code(extra="a.style.fill_pattern = 'hatch'\n")), 'a')
        layer = group.submobjects[0]
        assert type(layer).__name__ == 'VMobject' and layer.get_stroke_width() > 0
        square = built(framed(angle_code((0, 2), "a.style.fill_pattern = 'crosshatch'\n")), 'a')
        assert type(square.submobjects[0]).__name__ == 'VMobject'

    def test_label_clears_the_decoration(self):
        code = angle_code(extra='a.style.label_visible = True\n')
        plain = built(framed(code), 'a')
        waved = built(framed(code + "a.style.arc_tick_count = 1\n"), 'a')
        lab = [m for m in plain.submobjects if getattr(m, '_animageo_is_label', False)][0]
        lab2 = [m for m in waved.submobjects if getattr(m, '_animageo_is_label', False)][0]
        d1, d2 = (float(np.hypot(*m.get_center()[:2])) * PT for m in (lab, lab2))
        assert d2 - d1 == pytest.approx(4.5, abs=0.05)


class TestLines:
    def test_segment_heads(self):
        group = built(framed(angle_code() + "s = Segment(A, B)\ns.style.arrow_head = 'both'\n"), 's')
        stem, h1, h2 = group.submobjects[:3]
        assert stem.get_start()[0] * PT == pytest.approx(11)
        assert stem.get_end()[0] * PT == pytest.approx(3 * PT - 11)
        assert {type(h1).__name__, type(h2).__name__} == {'Polygon'}

    def test_dashed_stem_is_fitted(self):
        group = built(framed(angle_code() + "s = Segment(A, B)\ns.style.arrow_head = 'end'\n"
                                            "s.style.stroke_dash_ratio = 0.5\n"), 's')
        dash = get_dash(group.submobjects[0])
        stem = 3 * PT - 11
        n = round((stem / PT + dash.off) / (dash.on + dash.off))
        assert n * dash.on + (n - 1) * dash.off == pytest.approx(stem / PT)

    def test_chevrons(self):
        group = built(framed(angle_code() + "s = Segment(A, B)\ns.style.parallel_count = 2\n"), 's')
        chevrons = group.submobjects[1:]
        assert len(chevrons) == 2
        tips = sorted(float(c.points[3][0]) for c in chevrons)      # the tip ends the first piece
        assert (tips[1] - tips[0]) * PT == pytest.approx(3.5)
        assert np.mean(tips) == pytest.approx(1.5 + 2 / PT)

    def test_chevrons_backward_and_on_a_line(self):
        s = framed(angle_code() + "l = Line(A, B)\nl.style.parallel_count = 1\n"
                                  "l.style.parallel_direction = 'backward'\n")
        line = built(s, 'l')
        (chevron,) = line.submobjects[1:]
        arm, tip = chevron.points[0], chevron.points[3]
        assert tip[0] < arm[0]                                       # pointing to −x

    def test_zero_segment_has_no_chevrons(self):
        group = built(framed("A = Point(0, 0)\nB = Point(0, 0)\ns = Segment(A, B)\ns.style.parallel_count = 2\n"
                             "s.style.arrow_head = 'end'\n"), 's')
        assert len(group.submobjects) == 1


class TestHollowPoint:
    def test_hole(self):
        group = built(framed("A = Point(1, 1)\nA.style.point_fill = 'hollow'\nA.style.size_px = 8\n"), 'A')
        outer, hole = group.submobjects[:2]
        assert getattr(hole, '_animageo_hole', False)
        assert hole.width == pytest.approx(outer.width / 2)
        assert hole.get_fill_opacity() == 1

    def test_a_small_hollow_triangle_grows_until_its_hole_shows(self):
        code = "A = Point(1, 1)\nA.style.point_fill = '{}'\nA.style.point_shape = 'triangle_up'\nA.style.size_px = 8\n"
        hollow = built(framed(code.format('hollow')), 'A').submobjects[0]
        solid = built(framed(code.format('solid')), 'A').submobjects[0]
        assert hollow.width == pytest.approx(solid.width * 12 / 8)

    def test_cross_ignores_it(self):
        group = built(framed("A = Point(1, 1)\nA.style.point_fill = 'hollow'\nA.style.point_shape = 'cross'\n"),
                      'A')
        assert not any(getattr(m, '_animageo_hole', False) for m in group.submobjects)

    def test_transparent_sheet_cuts_the_hole(self, tmp_path):
        code = "A = Point(0, 0)\nB = Point(3, 0)\ns = Segment(A, B)\nP = Point(1.5, 0)\nP.style.point_fill = 'hollow'\n"
        scene = framed(code)
        solid = svg(scene, tmp_path, 'solid')
        clear = svg(scene, tmp_path, 'clear', transparent=True)
        assert b'<rect' in solid and b'clipPath' not in solid
        assert b'<rect' not in clear and b'clip-rule="evenodd"' in clear
        # the hole is not painted; it cuts the segment and the ring of the point
        assert drawn_paths(clear) == drawn_paths(solid) - 1

    def test_transparent_without_holes_only_drops_the_sheet(self, tmp_path):
        scene = framed(angle_code())
        solid = svg(scene, tmp_path, 'solid')
        clear = svg(scene, tmp_path, 'clear', transparent=True)
        assert b'clipPath' not in clear and b'<rect' not in clear
        assert drawn_paths(clear) == drawn_paths(solid)


def drawn_paths(data):
    """The painted paths of an SVG (not those of its clip paths)."""
    return re.sub(rb'<clipPath.*?</clipPath>', b'', data, flags=re.S).count(b'<path')
