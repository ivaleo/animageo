"""Tests for GeoGebra free-text objects (Text element, value formatting,
parsing, rendering, export).
"""
import os

import numpy as np
import pytest

from animageo.geo.lib_elements import (
    Text, Point, Polygon, Segment, Element,
    format_number, format_object_value, resolve_text_string,
    resolve_text_position,
)
from animageo.geo.lib_vars import AngleSize, Boolean, Measure, Var
from animageo.geo.construction import Construction


# ── format_number: GeoGebra rounding + trailing-zero stripping ──

@pytest.mark.parametrize("value,decimals,expected", [
    (2.0, 1, "2"),
    (2.5, 1, "2.5"),
    (12.34, 1, "12.3"),
    (3.0, 2, "3"),
    (-0.04, 1, "0"),        # rounds to -0.0 → "0", not "-0"
    (42, 1, "42"),
    (1.239, 2, "1.24"),
])
def test_format_number(value, decimals, expected):
    assert format_number(value, decimals) == expected


# ── format_object_value: type-dependent GeoGebra value string ──

def test_format_point_is_coord_pair():
    assert format_object_value(Point([1.23, -2.0]), 1) == "(1.2, -2)"


def test_format_polygon_is_area():
    square = Polygon([[0, 0], [1, 0], [1, 1], [0, 1]])
    assert format_object_value(square, 1) == "1"


def test_format_segment_is_length():
    seg = Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))
    assert format_object_value(seg, 1) == "5"


def test_format_anglesize_is_degrees():
    assert format_object_value(AngleSize(np.pi / 2), 1) == "90°"


def test_format_boolean():
    assert format_object_value(Boolean(True), 1) == "true"
    assert format_object_value(Boolean(False), 1) == "false"


def test_format_measure_and_number():
    assert format_object_value(Measure(5.25), 1) == "5.3" or \
           format_object_value(Measure(5.25), 1) == "5.2"  # half-even tolerated
    assert format_object_value(42, 1) == "42"
    assert format_object_value(3.5, 1) == "3.5"


# ── Text element data model ──

def test_text_static_plain():
    t = Text([("str", "hello")], position=[1.0, 2.0])
    assert t.is_latex is False
    assert list(t.position) == [1.0, 2.0]
    assert t.anchor_point is None


def test_text_latex_flag():
    t = Text([("str", r"$\sqrt2$")], position=[0, 0], is_latex=True)
    assert t.is_latex is True


def test_text_has_label_z_index():
    t = Text([("str", "x")], position=[0, 0])
    assert t.style["z_index"] is not None


# ── resolve_text_string against a real construction ──

def _mini_construction():
    c = Construction()
    c.add(Element("A", Point([1.23, -2.0])))
    c.add(Element("t1", Polygon([[0, 0], [1, 0], [1, 1], [0, 1]])))
    c.add(Element("a", Segment(np.array([0.0, 0.0]), np.array([3.0, 4.0]))))
    return c


def test_resolve_static_string():
    c = _mini_construction()
    t = Text([("str", "hello world")], position=[0, 0])
    assert resolve_text_string(c, t, 1) == "hello world"


def test_resolve_dynamic_polygon_area():
    c = _mini_construction()
    # GGB: "Площадь = " + t1 + " "
    t = Text([("str", "area = "), ("obj", "t1"), ("str", " ")], position=[0, 0])
    assert resolve_text_string(c, t, 1) == "area = 1 "


def test_resolve_dynamic_point_and_segment():
    c = _mini_construction()
    # GGB: "point " + A + ", side " + a + ""
    t = Text([("str", "point "), ("obj", "A"),
              ("str", ", side "), ("obj", "a"), ("str", "")], position=[0, 0])
    assert resolve_text_string(c, t, 1) == "point (1.2, -2), side 5"


def test_resolve_missing_object_is_empty():
    c = _mini_construction()
    t = Text([("str", "v="), ("obj", "nonexistent")], position=[0, 0])
    assert resolve_text_string(c, t, 1) == "v="


# ── resolve_text_position: literal coords or anchor point ──

def test_resolve_position_literal():
    c = _mini_construction()
    t = Text([("str", "x")], position=[3.5, -1.0])
    assert list(resolve_text_position(c, t)) == [3.5, -1.0]


def test_resolve_position_anchor_point():
    c = _mini_construction()
    t = Text([("str", "x")], anchor_point="A")
    pos = resolve_text_position(c, t)
    assert list(pos) == [1.23, -2.0]


# ── Parser: GGB text objects → Text elements ──────────────────────────────

import re

from animageo.parsers import ggb_parser

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load(fixture):
    constr = Construction()
    view = {}
    ggb_parser.load(constr, view, os.path.join(FIXTURES, fixture))
    return constr


def _texts(constr):
    return [e for e in constr.elements if isinstance(e.data, Text)]


def test_parse_static_text_count():
    constr = _load('text_static.ggb')
    texts = _texts(constr)
    assert len(texts) == 2


def test_parse_static_latex_and_plain():
    constr = _load('text_static.ggb')
    resolved = {resolve_text_string(constr, e.data, 1) for e in _texts(constr)}
    assert r'$math=\sqrt2$' in resolved
    assert 'text' in resolved
    latex_texts = [e for e in _texts(constr) if e.data.is_latex]
    assert len(latex_texts) == 1
    assert resolve_text_string(constr, latex_texts[0].data, 1) == r'$math=\sqrt2$'


def test_parse_static_position_literal():
    constr = _load('text_static.ggb')
    for e in _texts(constr):
        pos = resolve_text_position(constr, e.data)
        assert pos.shape == (2,)
        assert e.data.anchor_point is None


def test_parse_kernel_decimals():
    constr = _load('text_dynamic.ggb')
    assert getattr(constr, 'ggb_decimals', None) == 1


def test_parse_dynamic_count():
    constr = _load('text_dynamic.ggb')
    assert len(_texts(constr)) == 4


def test_parse_dynamic_polygon_area_text():
    constr = _load('text_dynamic.ggb')
    # GeoGebra serializes non-breaking spaces (\xa0) around operators.
    resolved = [resolve_text_string(constr, e.data, 1).replace('\xa0', ' ')
                for e in _texts(constr)]
    area_texts = [r for r in resolved if r.startswith('Площадь = ')]
    assert len(area_texts) == 1
    assert re.fullmatch(r'Площадь = -?[\d.]+ ', area_texts[0])


def test_parse_dynamic_point_and_segment_text():
    constr = _load('text_dynamic.ggb')
    resolved = [resolve_text_string(constr, e.data, 1).replace('\xa0', ' ')
                for e in _texts(constr)]
    elem_texts = [r for r in resolved if r.startswith('элементы: точка ')]
    assert len(elem_texts) == 1
    assert re.fullmatch(
        r'элементы: точка \(-?[\d.]+, -?[\d.]+\), сторона -?[\d.]+', elem_texts[0])


def test_parse_anchored_text_has_anchor_point():
    constr = _load('text_dynamic.ggb')
    anchored = [e for e in _texts(constr) if e.data.anchor_point is not None]
    assert len(anchored) == 1
    # anchor point A must resolve to a real point's coords
    pos = resolve_text_position(constr, anchored[0].data)
    assert pos.shape == (2,)


# ── Renderer: _render_text produces a positioned mobject ──────────────────

from animageo.animageo import AnimaGeoScene


@pytest.fixture
def scene():
    s = AnimaGeoScene()
    s.camera.frame.set(width=12)
    return s


def _render(scene, text, name='txt'):
    elem = Element(name, text)
    scene.geo.add(elem)
    return scene.CreateMObject(elem, z_auto=True)


def test_render_plain_text_non_empty(scene):
    mobj = _render(scene, Text([("str", "hello")], position=[1.0, 2.0]))
    assert mobj is not None
    assert len(mobj.submobjects) >= 1


def test_render_latex_text_non_empty(scene):
    mobj = _render(scene, Text([("str", r"$\sqrt{2}$")], position=[0, 0], is_latex=True))
    assert mobj is not None
    assert len(mobj.submobjects) >= 1


def test_render_top_left_anchored_at_start_point(scene):
    # GeoGebra anchors a text's top-left corner at its start point.
    from manim import UL
    pos = [1.5, -0.5]
    mobj = _render(scene, Text([("str", "Ax")], position=pos))
    ul = mobj.get_corner(UL)
    assert ul[0] == pytest.approx(pos[0], abs=0.05)
    assert ul[1] == pytest.approx(pos[1], abs=0.05)


def test_render_empty_text_is_none(scene):
    mobj = _render(scene, Text([("str", "")], position=[0, 0]))
    assert mobj is None


def test_add_all_geometry_includes_text(scene):
    scene.geo.add(Element('txt1', Text([("str", "hello")], position=[1.0, 2.0])))

    scene.addAllGeometry(show=True)

    assert scene.mobject('txt1') is not None


def test_render_full_static_ggb(scene):
    scene.loadGGB(os.path.join(FIXTURES, 'text_static.ggb'), generate_stubs=False)
    scene.applyStyle()
    rendered = [scene.CreateMObject(e, z_auto=True)
                for e in scene.geo.elements if isinstance(e.data, Text)]
    assert len(rendered) == 2
    assert all(m is not None for m in rendered)


# ── Dynamic texts are live: they track construction changes ───────────────

def _area_text(constr):
    for e in _texts(constr):
        r = resolve_text_string(constr, e.data, 1)
        if r.startswith('Площадь'):
            return r


def test_dynamic_text_updates_when_point_moves():
    constr = _load('text_dynamic.ggb')
    before = _area_text(constr)
    constr.update('A', Point([-8.0, -6.0]))
    constr.rebuild()
    after = _area_text(constr)
    assert before is not None and after is not None
    assert before != after   # polygon area recomputed after A moved


# ── Exporters: TikZ + JSXGraph include text ───────────────────────────────

def test_tikz_export_emits_text_nodes(scene):
    scene.loadGGB(os.path.join(FIXTURES, 'text_dynamic.ggb'), generate_stubs=False)
    scene.applyStyle()
    scene.fitView(800, 600, padding=40)
    tex = scene.exportTikZ()
    assert r'{$math=\sqrt2$}' in tex        # LaTeX passthrough
    assert '{text}' in tex                  # plain text
    assert 'anchor=north west' in tex       # top-left anchoring
    assert 'Площадь = 13.7' in tex          # dynamic value


def test_jsxgraph_spec_emits_text_elements(scene):
    import json as _json
    scene.loadGGB(os.path.join(FIXTURES, 'text_dynamic.ggb'), generate_stubs=False)
    scene.applyStyle()
    scene.fitView(800, 600, padding=40)
    spec = scene.exportJSXGraph(output='spec')
    data = _json.loads(spec) if isinstance(spec, str) else spec
    texts = [e for e in data['elements'] if e.get('engine') == 'text']
    assert len(texts) == 4
    # the LaTeX text requests MathJax
    latex = [t for t in texts if t.get('attrs', {}).get('useMathJax')]
    assert len(latex) == 1
    # each text carries [x, y, content-string] parents
    for t in texts:
        assert len(t['parents']) == 3
        assert isinstance(t['parents'][2], str)


def test_jsxgraph_spec_free_text_is_input(scene):
    import json as _json
    scene.geo.add(Element('txt1', Text([("str", "move me")], position=[1.0, 2.0])))
    scene.applyStyle()
    scene.fitView(800, 600, padding=40)
    data = _json.loads(scene.exportJSXGraph(output='spec'))
    inp = next(i for i in data['inputs'] if i['name'] == 'txt1')
    assert inp['kind'] == 'text'
    assert inp['x'] == 1.0
    assert inp['y'] == 2.0
    elem = next(e for e in data['elements'] if e.get('name') == 'txt1')
    assert elem['engine'] == 'text'
    assert elem['role'] == 'input'
    assert elem['attrs']['fixed'] is False


def test_jsxgraph_spec_with_text_validates_schema(scene):
    jsonschema = pytest.importorskip('jsonschema')
    import json as _json
    from animageo.exporters.jsxgraph.spec import load_schema
    scene.loadGGB(os.path.join(FIXTURES, 'text_dynamic.ggb'), generate_stubs=False)
    scene.applyStyle()
    scene.fitView(800, 600, padding=40)
    spec = scene.exportJSXGraph(output='spec')
    data = _json.loads(spec) if isinstance(spec, str) else spec
    jsonschema.validate(data, load_schema())
