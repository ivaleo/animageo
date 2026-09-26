"""Declarative board-spec tests (``animageo-board/v1``, output="spec").

The spec is the framework-agnostic integration contract: structured, eval-free
elements + an interactive-input schema. These tests pin its shape so the JS
runtime / Web Component can rely on it.
"""
import json
import os
import textwrap

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.exporters.jsxgraph.builder import build_board
from animageo.exporters.jsxgraph.context import Raw
from animageo.exporters.jsxgraph.options import JSXGraphOptions
from animageo.exporters.jsxgraph.spec import SPEC_FORMAT, classify_parent, load_schema

_FUNC5_GGB = os.path.join(os.path.dirname(__file__), "..", "examples", "func", "func5.ggb")

_EXAMPLE_GGB = os.path.join(os.path.dirname(__file__), "..", "examples", "ex_general.ggb")


def _scene(code, *, width=480, height=400, ptUnit=40):
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(export={"size": {"width": width, "height": height}})
    exp = s.style.export
    exp.update(ptUnit=ptUnit, ptUnit_style=ptUnit, ptUnit_ggb=ptUnit,
               ptWidth=width, ptHeight=height, ptXZero=width / 2, ptYZero=height / 2)
    s._set_camera_from_export(exp)
    return s


def _spec(scene):
    return json.loads(scene.exportJSXGraph(output="spec"))


def _el(spec, name):
    return next(e for e in spec["elements"] if e.get("name") == name)


class TestClassifyParent:
    """The parent classifier: JS-expression strings → structured data."""

    def test_ref(self):
        assert classify_parent('S["A"]') == {"ref": "A"}

    def test_ref_with_subscript(self):
        assert classify_parent('S["A_1"]') == {"ref": "A_1"}

    def test_int(self):
        assert classify_parent("3") == 3
        assert isinstance(classify_parent("3"), int)

    def test_float(self):
        assert classify_parent("3.5") == 3.5

    def test_negative(self):
        assert classify_parent("-2") == -2

    def test_coord_pair(self):
        assert classify_parent("[1.5,2]") == [1.5, 2]

    def test_polyline_nan_break(self):
        assert classify_parent("[1,2,NaN,3]") == [1, 2, None, 3]

    def test_fn(self):
        assert classify_parent(Raw("function(){return 1;}")) == {
            "fn": "function(){return 1;}"}

    def test_bool(self):
        assert classify_parent("true") is True
        assert classify_parent("false") is False

    def test_string_literal(self):
        assert classify_parent('"hello"') == "hello"

    def test_js_escape_hatch(self):
        assert classify_parent('S["p"].borders[1]') == {"js": 'S["p"].borders[1]'}

    def test_nonfinite_scalar_routed_to_js_hatch(self):
        # A bare NaN/Infinity must NOT become a float (json.dumps would emit
        # invalid JSON that JS JSON.parse rejects) — route to the js hatch.
        assert classify_parent("NaN") == {"js": "NaN"}
        assert classify_parent("Infinity") == {"js": "Infinity"}

    def test_spec_is_strict_json(self):
        # The whole spec must be strictly JSON-valid (no NaN/Infinity tokens),
        # so a JS consumer's JSON.parse never throws.
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nM=Midpoint(A,B)\nf(x) = x^2")
        text = s.exportJSXGraph(output="spec")
        assert "NaN" not in text and "Infinity" not in text
        json.loads(text)  # parses


class TestSpecStructure:
    def test_format_and_top_level_keys(self):
        spec = _spec(_scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)"))
        assert spec["format"] == SPEC_FORMAT == "animageo-board/v1"
        for key in ("boundingbox", "size", "chrome", "options",
                    "inputs", "elements", "coverage"):
            assert key in spec
        # eval-free: the declarative spec carries no top-level JS statement blob.
        assert "statements" not in spec

    def test_midpoint_is_declarative(self):
        spec = _spec(_scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)"))
        mid = _el(spec, "M")
        assert mid["engine"] == "midpoint"
        assert mid["parents"] == [{"ref": "A"}, {"ref": "B"}]
        assert mid["role"] == "live"
        assert mid["tracksDrag"] is True

    def test_circle_numeric_radius_parent(self):
        spec = _spec(_scene("A=Point(0,0)\nc=Circle(A,3)"))
        ce = _el(spec, "c")
        assert ce["engine"] == "circle"
        assert ce["parents"] == [{"ref": "A"}, 3]

    def test_elements_statements_lockstep(self):
        # Every JS statement has exactly one structured element (no desync).
        s = _scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)\nc=Circle(A,B)")
        model = build_board(s, JSXGraphOptions())
        assert len(model.elements) == len(model.statements)

    def test_static_curve_function(self):
        spec = _spec(_scene("A=Point(0,0)\nf(x) = x^2"))
        fe = _el(spec, "f")
        assert fe["engine"] == "curve"
        assert fe["role"] == "static"
        # sampled curve parents = two numeric arrays (xs, ys)
        assert isinstance(fe["parents"][0], list)
        assert isinstance(fe["parents"][1], list)
        # no draggable ancestor → tracksDrag omitted (not a desync risk)
        assert "tracksDrag" not in fe


class TestInputSchema:
    def test_dsl_number_is_a_slider_input(self):
        # Per the spike notes, a bare DSL number is a free independent.
        spec = _spec(_scene("A=Point(0,0)\nk=3"))
        ks = next((i for i in spec["inputs"] if i["name"] == "k"), None)
        assert ks is not None, "DSL free number should surface as an input"
        assert ks["kind"] == "number"
        assert ks["value"] == 3

    def test_slider_bounds_from_var_style(self):
        s = _scene("A=Point(0,0)\nk=3")
        var = s.geo.var("k")
        assert var is not None
        var.style["slider_min"] = 0.0
        var.style["slider_max"] = 10.0
        var.style["slider_step"] = 0.5
        spec = _spec(s)
        ks = next(i for i in spec["inputs"] if i["name"] == "k")
        assert ks["min"] == 0.0 and ks["max"] == 10.0 and ks["step"] == 0.5

    def test_distance_radius_is_live_fn(self):
        # A circle whose radius is a derived value (Distance) → the spec carries
        # a live function-valued parent ({"fn": …}), routed through value_expr.
        spec = _spec(_scene(
            "A=Point(0,0)\nB=Point(2,0)\nM=Point(1,1)\nc=Circle(M,Distance(A,B))"))
        ce = _el(spec, "c")
        assert ce["parents"][0] == {"ref": "M"}
        assert isinstance(ce["parents"][1], dict) and "fn" in ce["parents"][1]


class TestDashMapping:
    """The dash pattern in style px (ratio × period) maps to the nearest plain
    JSXGraph dash index — 1:[2,2] 2:[5,5] 3:[10,10] 4:[20,20]. The ratio is a
    0..1 share of the period, not a dash/width ratio: 0.65 of 10 px used to
    collapse to dots (1)."""

    def _dash_of(self, ratio, period=None, rendering=None):
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nm=Segment(A,B)")
        if rendering is not None:
            s.style.rendering["dash_period_px"] = rendering
        m = s.geo.element("m")
        m.style["stroke_dash_ratio"] = ratio
        if period is not None:
            m.style["stroke_dash_period_px"] = period
        return _el(_spec(s), "m").get("attrs", {}).get("dash")

    def test_default_ggb_dash_is_not_dotted(self):
        assert self._dash_of(0.65) == 2          # 6.5 / 3.5 px → [5, 5]

    def test_short_period_is_dotted(self):
        assert self._dash_of(0.5, period=4) == 1  # 2 / 2 px

    def test_period_20(self):
        assert self._dash_of(0.5, period=20) == 3  # 10 / 10 px

    def test_period_40(self):
        assert self._dash_of(0.5, period=40) == 4  # 20 / 20 px

    def test_rendering_period_is_the_fallback(self):
        assert self._dash_of(0.5, rendering=40) == 4

    def test_solid_has_no_dash_attr(self):
        assert self._dash_of(0) is None
        assert self._dash_of(1.0) is None


class TestLayerMapping:
    """The resolved z-index maps to a JSXGraph `layer` so the widget stacks like
    the renderer (fills below lines below points)."""

    def test_explicit_fill_tier_layer(self):
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nm=Segment(A,B)")
        s.geo.element("m").style["z_index"] = 0.01   # fill tier
        assert _el(_spec(s), "m").get("attrs", {}).get("layer") == 3

    def test_explicit_point_tier_layer(self):
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nm=Segment(A,B)")
        s.geo.element("m").style["z_index"] = 50      # point tier
        assert _el(_spec(s), "m").get("attrs", {}).get("layer") == 9

    def test_points_sit_above_segments(self):
        # The default resolved z-index already orders points above segments.
        s = _scene("A=Point(0,0)\nB=Point(2,1)\nm=Segment(A,B)")
        spec = _spec(s)
        seg_layer = _el(spec, "m").get("attrs", {}).get("layer")
        pt_layer = _el(spec, "A").get("attrs", {}).get("layer")
        assert seg_layer is not None and pt_layer is not None
        assert pt_layer > seg_layer


class TestAngleArcRadius:
    """Angle arc radius mirrors the renderer: a no-op base by default, multi-arc
    expansion when tick_count>1, and auto-scaling only when angle_radius is on."""

    def _angle_scene(self):
        return _scene("A=Point(2,0)\nB=Point(0,0)\nC=Point(0,2)\nal=Angle(A,B,C)")

    def _radius(self, scene):
        return _el(_spec(scene), "al").get("attrs", {}).get("radius")

    def test_default_radius_is_base_over_ptunit(self):
        # Byte-for-byte safe: with angle_radius disabled (default) and a single
        # arc, radius == resolved arc_size_px / ptUnit (ptUnit=40 in _scene).
        s = self._angle_scene()
        s.geo.element("al").style["arc_size_px"] = 20.0
        assert abs(self._radius(s) - 20.0 / 40) < 1e-6

    def test_multi_arc_expands_radius(self):
        s = self._angle_scene()
        s.geo.element("al").style["arc_size_px"] = 20.0
        base = self._radius(s)
        s.geo.element("al").style["tick_count"] = 3
        # arc_shift_px default may be 0 in builtin defaults; force a value so the
        # expansion is observable regardless of the shipped default.
        s.style_config.defaults.by_type.setdefault("angle", {})["arc_shift_px"] = 6.0
        expanded = self._radius(s)
        assert expanded > base

    def test_auto_radius_scales_narrow_angle_when_enabled(self):
        # A narrow angle with angle_radius enabled gets a bigger radius than the
        # raw base (so the arc doesn't vanish between close sides).
        s = _scene("A=Point(3,0)\nB=Point(0,0)\nC=Point(3,0.3)\nal=Angle(A,B,C)")
        s.geo.element("al").style["arc_size_px"] = 20.0
        base = _el(_spec(s), "al").get("attrs", {}).get("radius")
        s.style_config.overlay.angle_radius = {"enabled": True, "exp": 0.5, "min_px": 1}
        scaled = _el(_spec(s), "al").get("attrs", {}).get("radius")
        assert scaled > base


class TestArrowDecorations:
    """Vectors carry a JSXGraph arrowhead sized from the resolved GGB
    arrow_length_px; the arrow stays live (native head on the arrow element)."""

    def test_vector_has_lastarrow(self):
        spec = _spec(_scene("A=Point(0,0)\nB=Point(2,1)\nv=Vector(A,B)"))
        v = _el(spec, "v")
        assert v["engine"] == "arrow"
        la = v.get("attrs", {}).get("lastArrow")
        assert isinstance(la, dict) and "size" in la

    def test_arrow_size_scales_with_length(self):
        # Bigger arrow_length_px → bigger JSXGraph size.
        s1 = _scene("A=Point(0,0)\nB=Point(2,1)\nv=Vector(A,B)")
        s1.geo.element("v").style["arrow_length_px"] = 8
        s2 = _scene("A=Point(0,0)\nB=Point(2,1)\nv=Vector(A,B)")
        s2.geo.element("v").style["arrow_length_px"] = 22
        sz1 = _el(_spec(s1), "v")["attrs"]["lastArrow"]["size"]
        sz2 = _el(_spec(s2), "v")["attrs"]["lastArrow"]["size"]
        assert sz2 > sz1


class TestTickDecorations:
    """Congruence tick marks on a segment are emitted as live function-point
    segments (track drags); none appear when tick_count is unset/zero."""

    def _spec_with_ticks(self, n):
        s = _scene("A=Point(-3,-2)\nB=Point(3,2)\nm=Segment(A,B)")
        if n:
            s.geo.element("m").style["tick_count"] = n
        return _spec(s)

    def test_no_ticks_by_default(self):
        names = [e.get("name", "") for e in self._spec_with_ticks(0)["elements"]]
        assert not any(n.startswith("__tick_") for n in names)

    def test_two_ticks_emit_segments_and_points(self):
        spec = self._spec_with_ticks(2)
        names = [e.get("name", "") for e in spec["elements"]]
        # 2 ticks → __tick_m_0, __tick_m_1 (segments) + _p1/_p2 anchor points each.
        assert "__tick_m_0" in names and "__tick_m_1" in names
        assert "__tick_m_0_p1" in names and "__tick_m_0_p2" in names

    def test_tick_anchor_points_are_live_functions(self):
        spec = self._spec_with_ticks(1)
        p1 = _el(spec, "__tick_m_0_p1")
        # function-valued coordinates → {"fn": …} parents that read S["A"]/S["B"].
        assert all(isinstance(p, dict) and "fn" in p for p in p1["parents"])
        assert 'S["A"]' in p1["parents"][0]["fn"] and 'S["B"]' in p1["parents"][0]["fn"]

    def test_tick_segment_joins_its_anchor_points(self):
        spec = self._spec_with_ticks(1)
        seg = _el(spec, "__tick_m_0")
        assert seg["engine"] == "segment"
        assert {"ref": "__tick_m_0_p1"} in seg["parents"]
        assert {"ref": "__tick_m_0_p2"} in seg["parents"]


class TestLabelAnchor:
    """An explicit 9-point label anchor (from GGB import or the placement
    solver) maps to JSXGraph anchorX/anchorY, so the offset is applied relative
    to the same label corner the renderer uses."""

    def _label(self, name, anchor=None):
        s = _scene("P=Point(1,1)")
        s.geo.element("P").style["label_visible"] = True
        if anchor is not None:
            s.geo.element("P").style["label_anchor"] = anchor
        return _el(_spec(s), "P").get("attrs", {}).get("label", {})

    def test_bottom_left_anchor(self):
        lbl = self._label("P", "BL")
        assert lbl.get("anchorX") == "left" and lbl.get("anchorY") == "bottom"

    def test_center_anchor(self):
        lbl = self._label("P", "MC")
        assert lbl.get("anchorX") == "middle" and lbl.get("anchorY") == "middle"

    def test_top_right_anchor(self):
        lbl = self._label("P", "TR")
        assert lbl.get("anchorX") == "right" and lbl.get("anchorY") == "top"

    def test_no_anchor_leaves_default(self):
        lbl = self._label("P", None)
        assert "anchorX" not in lbl and "anchorY" not in lbl

    def test_solver_layout_flows_into_spec(self):
        # The label-placement solver writes label_anchor + offset into elem.style;
        # the spec must carry both so the widget matches the print layout.
        from animageo.label_placement import compute_label_layout, apply_label_layout
        s = _scene("A=Point(0,0)\nB=Point(2,0)\nC=Point(1,2)\np=Polygon(A,B,C)")
        for nm in ("A", "B", "C"):
            s.geo.element(nm).style["label_visible"] = True
        layout = compute_label_layout(s)
        apply_label_layout(s, layout, rerender=False)
        spec = _spec(s)
        lbl = _el(spec, "A").get("attrs", {}).get("label", {})
        assert "anchorX" in lbl and "anchorY" in lbl


@pytest.mark.skipif(not os.path.exists(_EXAMPLE_GGB), reason="example .ggb not present")
class TestGGBSpec:
    def test_free_point_inputs(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        spec = _spec(s)
        points = [i for i in spec["inputs"] if i["kind"] == "point"]
        assert points, "GGB free points should be point inputs"
        p = points[0]
        assert "x" in p and "y" in p
        # the input also appears in elements with role=input, engine=point
        el = _el(spec, p["name"])
        assert el["role"] == "input"
        assert el["engine"] == "point"

    def test_glider_input_records_parent_curve(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        spec = _spec(s)
        gliders = [i for i in spec["inputs"] if i["kind"] == "glider"]
        assert gliders
        assert "on" in gliders[0] and gliders[0]["on"]

    def test_elements_statements_lockstep(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        model = build_board(s, JSXGraphOptions())
        assert len(model.elements) == len(model.statements)

    def test_no_js_strings_in_inputs(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        spec = _spec(s)
        for i in spec["inputs"]:
            for k, v in i.items():
                assert not (isinstance(v, dict) and "js" in v)


jsonschema = pytest.importorskip("jsonschema", reason="jsonschema not installed")


class TestSchema:
    """The shipped JSON Schema is loadable and real exported specs validate
    against it — guards the integration contract against silent drift."""

    def test_load_schema(self):
        schema = load_schema()
        assert schema["$id"].endswith("animageo-board-v1.json")
        assert schema["properties"]["format"]["const"] == SPEC_FORMAT

    def test_dsl_spec_validates(self):
        s = _scene("A=Point(-2,-1)\nB=Point(2,1)\nM=Midpoint(A,B)\nc=Circle(A,B)")
        jsonschema.validate(_spec(s), load_schema())

    def test_curve_spec_validates(self):
        s = _scene("A=Point(0,0)\nf(x) = x^2 - 1")
        jsonschema.validate(_spec(s), load_schema())

    @pytest.mark.skipif(not os.path.exists(_EXAMPLE_GGB), reason="example .ggb not present")
    def test_ggb_spec_validates(self):
        s = AnimaGeoScene()
        s.loadGGB(_EXAMPLE_GGB)
        jsonschema.validate(_spec(s), load_schema())

    @pytest.mark.skipif(not os.path.exists(_FUNC5_GGB), reason="func5 .ggb not present")
    def test_func5_curve_heavy_spec_validates(self):
        s = AnimaGeoScene()
        s.loadGGB(_FUNC5_GGB)
        jsonschema.validate(_spec(s), load_schema())
