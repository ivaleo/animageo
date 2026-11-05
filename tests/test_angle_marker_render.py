"""``rendering.angle_marker_fit`` in the manim renderer, TikZ and JSXGraph
(the manim-free contract: ``tests/test_angle_marker.py``)."""
import math
import textwrap

import numpy as np
import pytest

pytest.importorskip('manim')

from animageo.animageo import AnimaGeoScene  # noqa: E402

PT = 80.0
FIT = {'rendering': {'angle_marker_fit': True}}


def framed(code, style=None):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(style=style, export={'size': {'width': 480, 'height': 400}})
    exp = s.style.export
    exp.update(ptUnit=PT, ptUnit_style=PT, ptUnit_ggb=PT, ptWidth=480, ptHeight=400, ptXZero=120, ptYZero=340)
    s._set_camera_from_export(exp)
    return s


def angle_code(c, extra=''):
    return f'A = Point(0, 0)\nB = Point(3, 0)\nC = Point({c[0]}, {c[1]})\na = Angle(B, A, C)\n' + extra


def reach(mobj):
    """Largest distance of the drawn marker from the vertex (scene units)."""
    pts = np.concatenate([m.points[:, :2] for m in mobj.family_members_with_points()])
    return float(np.max(np.hypot(pts[:, 0], pts[:, 1])))


def built(scene, name='a'):
    return scene.CreateMObject(scene.geo.element(name))


class TestRenderer:
    def test_clamped_arc(self):
        limit = 0.5 * math.hypot(0.2, 0.2) * PT
        assert reach(built(framed(angle_code((0.2, 0.2)), FIT))) == pytest.approx(limit / PT, rel=1e-3)
        assert reach(built(framed(angle_code((0.2, 0.2))))) == pytest.approx(17 / PT, rel=1e-3)

    def test_hidden_marker_keeps_the_label(self):
        code = angle_code((0.04, 0.04), 'a.style.label_visible = True\n')
        group = built(framed(code, FIT))
        assert len(group.submobjects) == 1                 # the label only
        unclamped = built(framed(code))
        assert len(unclamped.submobjects) > 1

    def test_square(self):
        code = angle_code((0, 0.2))
        side = 0.5 * 0.2 * PT
        assert reach(built(framed(code, FIT))) == pytest.approx(side * math.sqrt(2) / PT, rel=1e-3)

    def test_a_line_along_the_side_lifts_the_bound(self):
        group = built(framed(angle_code((0.2, 0.2), 'l = Line(A, C)\n'), FIT))
        assert reach(group) == pytest.approx(17 / PT, rel=1e-3)

    def test_svg_is_unchanged_without_the_key(self, tmp_path):
        code = angle_code((0.2, 0.2), 'a.style.label_visible = True\n')
        out = []
        for i, style in enumerate((None, {'rendering': {'angle_marker_fit': False}},
                                   {'rendering': {'angle_marker_fit': {'side_fraction': 0.5}}})):
            s = framed(code, style)
            s.clear()
            s.addAllGeometry(show=True)
            path = tmp_path / f'{i}.svg'
            s.exportSVG(str(path))
            out.append(path.read_bytes())
        assert out[0] == out[1] == out[2]


class TestExporters:
    def test_tikz(self):
        tex = framed(angle_code((0.2, 0.2)), FIT).exportTikZ()
        limit = 0.5 * math.hypot(0.2, 0.2)
        assert f':{limit:.4f})' in tex or f':{round(limit, 3)})' in tex or f'{limit:.3f}' in tex
        assert framed(angle_code((0.2, 0.2))).exportTikZ() == \
            framed(angle_code((0.2, 0.2)), {'rendering': {'angle_marker_fit': False}}).exportTikZ()

    def test_tikz_hidden(self):
        tex = framed(angle_code((0.04, 0.04)), FIT).exportTikZ()
        assert ' arc (' not in tex

    def test_jsxgraph_static_radius(self):
        from animageo.exporters.jsxgraph.builder import build_board
        from animageo.exporters.jsxgraph.options import JSXGraphOptions
        scene = framed(angle_code((0.2, 0.2)), FIT)
        model = build_board(scene, JSXGraphOptions())
        angle = next(e for e in model.elements if e.name == 'a')
        assert angle.attrs['radius'] == pytest.approx(round(0.5 * math.hypot(0.2, 0.2) * PT, 4) / PT)
        assert ('a', 'live', 'Angle: static marker radius fitted to the sides') in model.coverage
        plain = next(e for e in build_board(framed(angle_code((0.2, 0.2))), JSXGraphOptions()).elements
                     if e.name == 'a')
        assert plain.attrs['radius'] == pytest.approx(17 / PT)

    def test_jsxgraph_hidden_keeps_the_label(self):
        from animageo.exporters.jsxgraph.builder import build_board
        from animageo.exporters.jsxgraph.options import JSXGraphOptions
        angle = next(e for e in build_board(framed(angle_code((0.04, 0.04)), FIT), JSXGraphOptions()).elements
                     if e.name == 'a')
        assert angle.attrs['strokeOpacity'] == 0 and angle.attrs['fillOpacity'] == 0
