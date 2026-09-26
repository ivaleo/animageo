"""JSXGraph export tests (require manim).

The top-level ``from animageo.animageo import AnimaGeoScene`` makes ``conftest``
skip this whole module when manim is unavailable. Covers the command→creator
mapping (via DSL constructions), the document layer (hand-built board model),
and the coverage report.
"""
import json
import os
import textwrap

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.exporters.jsxgraph.builder import BoardModel, build_board
from animageo.exporters.jsxgraph.document import render
from animageo.exporters.jsxgraph.options import JSXGraphOptions
from animageo.exporters.jsxgraph.style_map import label_name

_EXAMPLE_GGB = os.path.join(os.path.dirname(__file__), "..", "examples", "ex_general.ggb")
_FUNC5_GGB = os.path.join(os.path.dirname(__file__), "..", "examples", "func", "func5.ggb")


def _scene(code, *, width=480, height=400, ptUnit=40):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(export={"size": {"width": width, "height": height}})
    exp = s.style.export
    exp.update(ptUnit=ptUnit, ptUnit_style=ptUnit, ptUnit_ggb=ptUnit,
               ptWidth=width, ptHeight=height, ptXZero=width / 2, ptYZero=height / 2)
    s._set_camera_from_export(exp)
    return s


class TestCommandMapping:
    """Derived elements become live JSXGraph creators referencing parents.

    (DSL free points carry a literal command, so they emit as fixed points; the
    derived-element create calls — the mapping under test — are unaffected.)
    """

    def test_midpoint(self):
        js = _scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)").exportJSXGraph(output="js")
        assert 'board.create("midpoint", [S["A"], S["B"]]' in js

    def test_segment(self):
        js = _scene("A=Point(-2,-1)\nB=Point(2,1)\nm=Segment(A,B)").exportJSXGraph(output="js")
        assert 'board.create("segment", [S["A"], S["B"]]' in js

    def test_circle_center_through_point(self):
        js = _scene("A=Point(0,0)\nB=Point(2,0)\nc=Circle(A,B)").exportJSXGraph(output="js")
        assert 'board.create("circle", [S["A"], S["B"]]' in js

    def test_circle_numeric_radius(self):
        js = _scene("A=Point(0,0)\nc=Circle(A,3)").exportJSXGraph(output="js")
        assert 'board.create("circle", [S["A"], 3]' in js

    def test_line_two_points(self):
        js = _scene("A=Point(0,0)\nB=Point(2,1)\nL=Line(A,B)").exportJSXGraph(output="js")
        assert 'board.create("line", [S["A"], S["B"]]' in js

    def test_intersection_indexed(self):
        js = _scene("""
            A=Point(0,0)
            B=Point(4,0)
            C=Point(1,3)
            L1=Line(A,B)
            L2=Line(A,C)
            P=Intersect(L1,L2)
        """).exportJSXGraph(output="js")
        assert 'board.create("intersection"' in js
        assert ', 0]' in js  # branch index

    def test_polygon_emitted(self):
        js = _scene("A=Point(0,0)\nB=Point(2,0)\nC=Point(0,2)\np=Polygon(A,B,C)").exportJSXGraph(output="js")
        assert 'board.create("polygon"' in js

    def test_ellipse_live(self):
        js = _scene("A=Point(-2,0)\nB=Point(2,0)\ne=Ellipse(A,B,3)").exportJSXGraph(output="js")
        assert 'board.create("ellipse", [S["A"], S["B"], 3]' in js

    def test_parabola_live(self):
        js = _scene("""
            F=Point(0,1)
            l=Line(Point(-1,0),Point(1,0))
            p=Parabola(F,l)
        """).exportJSXGraph(output="js")
        assert 'board.create("parabola"' in js

    def test_semicircle_live(self):
        js = _scene("A=Point(0,0)\nB=Point(2,0)\ns=Semicircle(A,B)").exportJSXGraph(output="js")
        assert 'board.create("semicircle", [S["A"], S["B"]]' in js

    def test_reflect_across_line(self):
        js = _scene("""
            A=Point(1,1)
            l=Line(Point(0,0),Point(1,0))
            B=Reflect(A,l)
        """).exportJSXGraph(output="js")
        assert 'board.create("reflection"' in js

    def test_perpendicular_bisector_composite(self):
        js = _scene("A=Point(0,0)\nB=Point(4,2)\ng=PerpendicularBisector(A,B)").exportJSXGraph(output="js")
        assert 'board.create("perpendicular"' in js
        assert 'board.create("midpoint"' in js  # hidden aux

    def test_function_drawn_as_curve(self):
        js = _scene("f(x) = x^2 - 1").exportJSXGraph(output="js")
        assert 'board.create("curve"' in js

    def test_angle_defaults_to_nonreflex(self):
        # JSXGraph's plain `angle` ignores GeoGebra's reflex/non-reflex setting
        # (it always sweeps CCW from p1 to p3). The exporter must instead emit a
        # dedicated reflex/non-reflex element. Default angle_range is 'minor'.
        js = _scene("A=Point(-2,0)\nB=Point(0,0)\nC=Point(2,1)\nang=Angle(A,B,C)").exportJSXGraph(output="js")
        assert 'board.create("nonreflexangle", [S["A"], S["B"], S["C"]]' in js
        assert 'board.create("angle"' not in js

    def test_angle_reflex_setting_honoured(self):
        js = _scene(
            "A=Point(-2,0)\nB=Point(0,0)\nC=Point(2,1)\n"
            "ang=Angle(A,B,C)\nang.style.angle_range = 'reflex'"
        ).exportJSXGraph(output="js")
        assert 'board.create("reflexangle", [S["A"], S["B"], S["C"]]' in js


class TestVisibility:
    """Hidden objects must be emitted as ``visible: false`` (kept in the board
    for dependencies, but not drawn) rather than rendered like visible ones."""

    def test_hidden_object_marked_invisible(self):
        js = _scene(
            "A=Point(-2,0)\nC=Point(2,1)\nseg=Segment(A,C)\nseg.style.visible = False"
        ).exportJSXGraph(output="js")
        seg_line = next(l for l in js.splitlines() if 'S["seg"]' in l)
        assert "visible: false" in seg_line

    def test_visible_object_has_no_visible_attr(self):
        js = _scene("P=Point(1,1)").exportJSXGraph(output="js")
        p_line = next(l for l in js.splitlines() if 'S["P"]' in l)
        assert "visible: false" not in p_line


class TestChrome:
    """Board chrome imported from the GeoGebra euclidianView: grid boldness /
    spacing, per-axis tick numbering / spacing, and keep-aspect from the x/y
    unit scales — mirroring what the SVG renderer honours."""

    def _scene_with_view(self, **view):
        s = _scene("A=Point(0,0)")
        s.style.export.update(view)
        return s

    def test_grid_bold_and_spacing(self):
        js = self._scene_with_view(
            showGrid=True, gridIsBold=True, gridDistX=2, gridDistY=0.5,
        ).exportJSXGraph(output="js")
        grid_line = next(l for l in js.splitlines() if "board.grids" in l)
        assert "strokeWidth: 1.5" in grid_line
        assert "majorStep: [2, 0.5]" in grid_line

    def test_axis_hide_numbers(self):
        js = self._scene_with_view(
            showAxes=True,
            axes={"x": {"show": True, "showNumbers": False}, "y": {"show": True}},
        ).exportJSXGraph(output="js")
        assert "defaultTicks.setAttribute({drawLabels: false})" in js

    def test_axis_tick_distance(self):
        js = self._scene_with_view(
            showAxes=True,
            axes={"x": {"show": True, "tickDistance": 0.5}, "y": {"show": True}},
        ).exportJSXGraph(output="js")
        assert "ticksDistance: 0.5" in js
        assert "insertTicks: false" in js

    def test_keepaspectratio_false_for_unequal_scale(self):
        js = self._scene_with_view(ptUnit_ggb=50, ptYUnit_ggb=25).exportJSXGraph(output="js")
        assert "keepaspectratio: false" in js

    def test_keepaspectratio_true_for_equal_scale(self):
        js = self._scene_with_view(ptUnit_ggb=40, ptYUnit_ggb=40).exportJSXGraph(output="js")
        assert "keepaspectratio: true" in js

    def test_keepaspectratio_option_overrides(self):
        from animageo.exporters.jsxgraph.options import JSXGraphOptions
        js = self._scene_with_view(ptUnit_ggb=50, ptYUnit_ggb=25).exportJSXGraph(
            options=JSXGraphOptions(output="js", keepaspectratio=True)
        )
        assert "keepaspectratio: true" in js


class TestPhase3:
    """Live transforms (rotate/translate of a point) and Tier-V live numeric
    values (a derived measure feeding a creator)."""

    def test_rotate_live(self):
        js = _scene("A=Point(2,0)\nC=Point(0,0)\nB=Rotate(A,1.5708,C)").exportJSXGraph(output="js")
        assert 'type: "rotate"' in js
        assert 'board.create("point", [S["A"]' in js  # transformed point

    def test_translate_live(self):
        js = _scene("""
            A=Point(0,0)
            P=Point(1,1)
            Q=Point(3,2)
            v=Vector(P,Q)
            B=Translate(A,v)
        """).exportJSXGraph(output="js")
        assert 'type: "translate"' in js
        assert "point2.X()" in js  # tracks the live vector

    def test_distance_radius_live(self):
        # A circle whose radius is Distance(A,B) → live JS function radius.
        js = _scene("""
            A=Point(0,0)
            B=Point(3,1)
            M=Point(1,1)
            d=Distance(A,B)
            c=Circle(M,d)
        """).exportJSXGraph(output="js")
        assert 'S["A"].Dist(S["B"])' in js

    def test_translate_segment_live(self):
        js = _scene("""
            A=Point(0,0)
            B=Point(2,1)
            seg=Segment(A,B)
            P=Point(-1,2)
            Q=Point(0,4)
            v=Vector(P,Q)
            seg2=Translate(seg,v)
        """).exportJSXGraph(output="js")
        assert 'board.create("segment", [S["seg"], S["__tf_seg2"]]' in js

    def test_translate_circle_live(self):
        js = _scene("""
            O=Point(-3,-2)
            c=Circle(O,1.5)
            P=Point(-1,2)
            Q=Point(0,4)
            v=Vector(P,Q)
            c2=Translate(c,v)
        """).exportJSXGraph(output="js")
        assert 'board.create("circle", [S["c"], S["__tf_c2"]]' in js


class TestCoverage:
    def test_polygon_is_live(self):
        # Phase 2: polygon emits a live 'polygon' referencing its vertices.
        # (A bare DSL Polygon has no named edges; edge→border binding is
        # exercised by the GGB integration test where the polygon is
        # multi-output.)
        js = _scene("A=Point(0,0)\nB=Point(2,0)\nC=Point(0,2)\np=Polygon(A,B,C)").exportJSXGraph(output="js")
        assert 'board.create("polygon", [S["A"], S["B"], S["C"]]' in js

    def test_counts_sum(self):
        s = _scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)\nm=Segment(A,B)")
        model = build_board(s, JSXGraphOptions())
        assert sum(model.counts().values()) == len(model.coverage)


class TestLabelName:
    """MathJax labels: resolve_label_text returns ``$…$`` (TikZ convention);
    JSXGraph needs ``\\(…\\)``. Regression for the double-wrap bug that rendered
    a literal ``$A$``."""

    def test_strips_dollar_and_wraps(self):
        assert label_name("$A$", True) == "\\(A\\)"

    def test_keeps_existing_paren(self):
        assert label_name("\\(x_1\\)", True) == "\\(x_1\\)"

    def test_plain_when_mathjax_off(self):
        assert label_name("$A$", False) == "A"

    def test_wraps_bare_text(self):
        assert label_name("AB", True) == "\\(AB\\)"

    def test_no_dollar_in_emitted_names(self):
        import re
        js = _scene("A=Point(0,0)\nA.style.label_visible = True").exportJSXGraph(output="js")
        names = re.findall(r'name: "([^"]*)"', js)
        assert names and all("$" not in n for n in names)


class TestDocument:
    """Document assembly — exercised with a hand-built board model (manim is
    only needed for module import skip-gating)."""

    def _model(self):
        m = BoardModel(boundingbox=(-5, 5, 5, -5))
        m.statements = ['S["A"] = board.create("point", [0, 0], {});']
        m.coverage = [("A", "input", "free point")]
        return m

    def test_html_scaffold(self):
        html = render(self._model(), JSXGraphOptions(output="html"), width=640, height=480)
        assert "JXG.JSXGraph.initBoard" in html
        assert "jsxgraph@1.10.1" in html
        assert "MathJax" in html
        assert 'id="agbox"' in html
        assert "640px" in html and "480px" in html

    def test_js_is_iife(self):
        js = render(self._model(), JSXGraphOptions(output="js"), width=1, height=1)
        assert js.lstrip().startswith("(function ()")
        assert "initBoard" in js
        assert "MathJax" not in js  # js fragment assumes host provides libs

    def test_json_valid(self):
        out = render(self._model(), JSXGraphOptions(output="json"), width=1, height=1)
        data = json.loads(out)
        assert data["format"].startswith("animageo-jsxgraph")
        assert data["boundingbox"] == [-5, 5, 5, -5]
        assert data["coverage"][0]["name"] == "A"

    def test_mathjax_can_be_disabled(self):
        html = render(self._model(), JSXGraphOptions(output="html", mathjax=False),
                      width=1, height=1)
        assert "MathJax" not in html

    def test_moodle_output(self):
        out = render(self._model(), JSXGraphOptions(output="moodle"), width=640, height=480)
        assert out.lstrip().startswith("<jsxgraph")
        assert "BOARDID" in out                  # filter-provided board id
        assert "window.agboard" not in out       # no debug globals in moodle
        assert out.rstrip().endswith("</jsxgraph>")


class TestSceneAPI:
    def test_returns_text_and_writes_file(self, tmp_path):
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nm=Segment(A,B)")
        out = tmp_path / "board.html"
        text = s.exportJSXGraph(str(out))
        assert out.exists()
        assert text.startswith("<!DOCTYPE html>")

    def test_options_and_kwargs_conflict(self, tmp_path):
        s = _scene("A=Point(0,0)")
        with pytest.raises(TypeError):
            s.exportJSXGraph(options=JSXGraphOptions(), output="js")


@pytest.mark.skipif(not os.path.exists(_EXAMPLE_GGB), reason="example .ggb not present")
class TestGGBIntegration:
    """Free points → draggable points, points-on-curves → gliders (needs a GGB
    file, since DSL points are not independents)."""

    def test_free_points_and_glider(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        js = s.exportJSXGraph(output="js")
        assert 'S["A"] = board.create("point"' in js
        assert 'board.create("glider"' in js

    def test_polygon_edges_bind_to_borders(self):
        # GGB Polygon is multi-output (polygon + named edge segments) → the
        # edges are bound to the polygon's live .borders.
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        js = s.exportJSXGraph(output="js")
        assert 'board.create("polygon"' in js
        assert ".borders[" in js

    def test_fully_interactive_no_static(self):
        # With live polygon, ex_general has no static/skip elements left.
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        model = build_board(s, JSXGraphOptions())
        counts = model.counts()
        assert counts.get("static", 0) == 0
        assert counts.get("skip", 0) == 0
        assert counts.get("live", 0) > 0


@pytest.mark.skipif(not os.path.exists(_FUNC5_GGB), reason="func5 .ggb not present")
class TestConicsFunctionsIntegration:
    """func5.ggb has conics/functions/implicit curves defined directly — they
    must all be drawn (static curves), with no drawable type silently dropped."""

    def test_curves_drawn(self):
        s = AnimaGeoScene()
        s.loadGGB(_FUNC5_GGB)
        js = s.exportJSXGraph(output="js")
        assert 'board.create("curve"' in js   # functions/conics/implicit sampled

    def test_only_empty_outputs_skipped(self):
        s = AnimaGeoScene()
        s.loadGGB(_FUNC5_GGB)
        model = build_board(s, JSXGraphOptions())
        # Any skipped element must have no real geometry (None data).
        for name, kind, _detail in model.coverage:
            if kind == "skip":
                el = s.geo.element(name)
                assert el is None or el.data is None


class TestHyperbolaGlider:
    """A point constrained to a hyperbola has a ``(branch, t)`` path
    parameter (not a scalar) — the glider export must not try to
    ``float()`` it."""

    def _hyperbola_glider_scene(self):
        s = _scene('K=Conic("x^2/4 - y^2/9 = 1")\nD=Point(K)\nD.tparam = (1.0, 0.5)')
        return s

    def test_export_does_not_raise(self):
        s = self._hyperbola_glider_scene()
        js = s.exportJSXGraph(output="js")  # used to raise TypeError: float() ... 'list'
        assert 'board.create("glider"' in js

    def test_input_schema_t_is_none(self):
        s = self._hyperbola_glider_scene()
        model = build_board(s, JSXGraphOptions())
        gliders = [i for i in model.input_schema if i.kind == "glider"]
        assert gliders, "expected a glider input for the hyperbola point"
        assert gliders[0].name == "D"
        assert gliders[0].t is None


def _chrome_scene(code="A=Point(0,0)", **export_extra):
    """A DSL scene with explicit GeoGebra-view export settings (showAxes/…)."""
    s = _scene(code)
    s.style.export.update(export_extra)
    return s


class TestBoardChrome:
    """Background / axes / grid are imported from the GeoGebra scene (or option
    overrides) instead of being hard-coded board chrome."""

    def test_axes_grid_follow_scene(self):
        js = _chrome_scene(showAxes=True, showGrid=True).exportJSXGraph(output="js")
        init = next(l for l in js.splitlines() if "initBoard" in l)
        assert "axis: true" in init and "grid: true" in init

    def test_axes_hidden_when_scene_hides_them(self):
        js = _chrome_scene(showAxes=False, showGrid=False).exportJSXGraph(output="js")
        init = next(l for l in js.splitlines() if "initBoard" in l)
        assert "axis: false" in init and "grid: false" in init

    def test_geogebra_defaults_when_scene_silent(self):
        # No showAxes/showGrid keys (bare DSL scene) → GeoGebra defaults: axes
        # on, grid off.
        js = _scene("A=Point(0,0)").exportJSXGraph(output="js")
        init = next(l for l in js.splitlines() if "initBoard" in l)
        assert "axis: true" in init and "grid: false" in init

    def test_option_overrides_scene(self):
        js = _chrome_scene(showAxes=True, showGrid=True).exportJSXGraph(
            options=JSXGraphOptions(output="js", axis=False, grid=False))
        init = next(l for l in js.splitlines() if "initBoard" in l)
        assert "axis: false" in init and "grid: false" in init

    def test_background_emitted(self):
        js = _chrome_scene(background="#fffdf0").exportJSXGraph(output="js")
        assert 'board.containerObj.style.background = "#FFFDF0"' in js

    def test_background_in_html_css(self):
        html = _chrome_scene(background="#fffdf0").exportJSXGraph(output="html")
        assert "background: #FFFDF0" in html

    def test_background_disabled_by_empty_option(self):
        js = _chrome_scene(background="#fffdf0").exportJSXGraph(
            options=JSXGraphOptions(output="js", background=""))
        assert "containerObj" not in js

    def test_axes_color_and_per_axis_visibility(self):
        js = _chrome_scene(showAxes=True, axesColor="#cc3333",
                           axes={"x": {"show": True}, "y": {"show": False}}
                           ).exportJSXGraph(output="js")
        assert "board.defaultAxes" in js
        assert 'strokeColor: "#CC3333"' in js
        y_line = next(l for l in js.splitlines() if "defaultAxes.y" in l)
        assert "visible: false" in y_line

    def test_grid_color_emitted(self):
        js = _chrome_scene(showGrid=True, gridColor="#dddddd").exportJSXGraph(output="js")
        assert "board.grids" in js
        assert 'strokeColor: "#DDDDDD"' in js

    def test_chrome_in_json(self):
        out = _chrome_scene(showAxes=True, showGrid=True,
                            background="#ffffff").exportJSXGraph(output="json")
        chrome = json.loads(out)["chrome"]
        assert chrome["axis"] is True and chrome["grid"] is True
        assert chrome["background"] == "#FFFFFF"


class TestElementStyleFidelity:
    """Sizes/colours/labels of elements are carried over via the resolver."""

    def test_point_color_size_shape(self):
        js = _scene("A=Point(0,0)\nA.style.fill='#ff0000'\nA.style.size_px=12\n"
                    "A.style.point_shape='square'").exportJSXGraph(output="js")
        line = next(l for l in js.splitlines() if 'S["A"]' in l)
        assert 'fillColor: "#FF0000"' in line
        assert "size: 6" in line          # size_px / 2
        assert 'face: "[]"' in line

    def test_angle_radius_from_arc_size(self):
        # arc_size_px / ptUnit (ptUnit=40) → radius in user units.
        js = _scene("A=Point(2,0)\nB=Point(0,0)\nC=Point(0,2)\n"
                    "ang=Angle(A,B,C)\nang.style.arc_size_px=20").exportJSXGraph(output="js")
        line = next(l for l in js.splitlines() if "nonreflexangle" in l)
        assert "radius: 0.5" in line

    def test_label_offset_carried_when_nontrivial(self):
        js = _scene("A=Point(0,0)\nA.style.label_visible=True\n"
                    "A.style.label_offset_px=[18, 12]").exportJSXGraph(output="js")
        line = next(l for l in js.splitlines() if 'S["A"]' in l)
        assert "offset: [18" in line and "12" in line

    def test_label_offset_skipped_when_near_zero(self):
        js = _scene("A=Point(0,0)\nA.style.label_visible=True\n"
                    "A.style.label_offset_px=[0, 0]").exportJSXGraph(output="js")
        line = next(l for l in js.splitlines() if 'S["A"]' in l)
        assert "offset:" not in line

    def test_dashed_stroke(self):
        # 0.5 of the default 10 px period = 5 / 5 px → JSXGraph's [5, 5] (2);
        # see TestDashMapping in test_jsxgraph_spec.py.
        js = _scene("A=Point(-2,0)\nB=Point(2,0)\nm=Segment(A,B)\n"
                    "m.style.stroke_dash_ratio=0.5").exportJSXGraph(output="js")
        line = next(l for l in js.splitlines() if 'S["m"]' in l)
        assert "dash: 2" in line
