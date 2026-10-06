"""GeoGebra captions linked to hidden, possibly changing text objects."""
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Text
from animageo.labels import resolve_label_spec, resolve_label_text
from animageo.parsers.ggb_parser import parse_constr
from animageo.style.config import StyleConfig
from animageo.style.import_policy import ImportPolicy


def caption_scene(mode=3, content=r"\beta", latex=True, source="текст_{1}"):
    xml = ET.fromstring('''<construction>
      <element type="numeric" label="n"><value val="2"/></element>
      <element type="point" label="A"><coords x="0" y="0" z="1"/></element>
      <element type="point" label="B"><coords x="3" y="0" z="1"/></element>
      <command name="Segment"><input a0="A" a1="B"/><output a0="s"/></command>
      <element type="segment" label="s">
        <show object="true" label="true"/><caption val="Static"/>
      </element>
    </construction>''')
    owner = xml.find("element[@label='s']")
    ET.SubElement(owner, "labelMode", val=str(mode))
    ET.SubElement(owner, "dynamicCaption", val=source)
    ET.SubElement(xml, "expression", label="текст_{1}", exp='"' + content + '"')
    text = ET.SubElement(xml, "element", type="text", label="текст_{1}")
    ET.SubElement(text, "show", object="false", label="false")
    ET.SubElement(text, "isLaTeX", val=str(latex).lower())
    ET.SubElement(text, "startPoint", x="0", y="0", z="1")
    constr = Construction()
    parse_constr(constr, xml)
    return SimpleNamespace(geo=constr, style_config=StyleConfig.load())


def test_caption_resolves_forward_reference_to_hidden_normalized_text():
    scene = caption_scene()
    owner = scene.geo.element("s")
    text = scene.geo.element(scene.geo.name_mapping["текст_{1}"])
    assert isinstance(text.data, Text)
    assert not text.visible
    assert resolve_label_text(scene, owner) == r"$\beta$"
    assert owner.ggb_raw["label_dynamic_caption"] == "текст_{1}"


@pytest.mark.parametrize("mode,expected", [
    (0, "$s$"), (1, "$s = 3$"), (2, "$3$"),
    (3, r"$\beta$"), (9, r"$\beta = 3$"),
])
def test_dynamic_caption_obeys_geogebra_caption_modes(mode, expected):
    scene = caption_scene(mode=mode)
    assert resolve_label_text(scene, scene.geo.element("s")) == expected


@pytest.mark.parametrize("content", [r"\[\beta\]", r"\(\beta\)", r"$\beta$"])
def test_caption_value_accepts_existing_math_delimiters(content):
    scene = caption_scene(mode=9, content=content)
    owner = scene.geo.element("s")
    assert resolve_label_text(scene, owner) == r"$\beta = 3$"
    spec = resolve_label_spec(scene, owner)
    assert spec.prefix_tex == r"$\beta = $"
    assert spec.value == 3


def test_caption_reads_current_text_value_on_each_resolution():
    scene = caption_scene()
    owner = scene.geo.element("s")
    text = scene.geo.element(scene.geo.name_mapping["текст_{1}"]).data
    text.segments = [("str", r"\varphi + "), ("obj", "n")]
    assert resolve_label_text(scene, owner) == r"$\varphi + 2$"
    scene.geo.update("n", 5)
    scene.geo.rebuild()
    assert resolve_label_text(scene, owner) == r"$\varphi + 5$"


def test_plain_caption_escapes_tex_without_turning_prose_into_math():
    scene = caption_scene(content="a_b & 50%", latex=False)
    assert resolve_label_text(scene, scene.geo.element("s")) == r"a\_b \& 50\%"


def test_empty_caption_remains_empty():
    scene = caption_scene(content="")
    assert resolve_label_text(scene, scene.geo.element("s")) == ""


@pytest.mark.parametrize("source", ["missing", "A"])
def test_invalid_caption_reference_falls_back_to_static_caption(source):
    scene = caption_scene(source=source)
    assert resolve_label_text(scene, scene.geo.element("s")) == "$Static$"


@pytest.mark.parametrize("layer", ["explicit", "per_name", "per_type"])
def test_explicit_and_overlay_label_text_keep_priority(layer):
    scene = caption_scene()
    owner = scene.geo.element("s")
    if layer == "explicit":
        owner.style["label_text"] = "$Chosen$"
    elif layer == "per_name":
        scene.style_config.overlay.per_name["s"] = {"label_text": "$Chosen$"}
    else:
        scene.style_config.overlay.per_type["segment"] = {"label_text": "$Chosen$"}
    assert resolve_label_text(scene, owner) == "$Chosen$"


def test_disabled_import_does_not_use_dynamic_caption():
    scene = caption_scene()
    scene.style_config = StyleConfig.load({"import": {"enabled": False}})
    assert resolve_label_text(scene, scene.geo.element("s")) == "$s$"


def test_faithful_policy_preserves_reference_and_custom_policy_overrides_it():
    scene = caption_scene()
    owner = scene.geo.element("s")
    owner.ggb_style = ImportPolicy.faithful().resolve(owner)
    assert resolve_label_text(scene, owner) == r"$\beta$"
    owner.ggb_style.update(ImportPolicy(label_text="$Policy$").resolve_overrides_only(owner))
    assert resolve_label_text(scene, owner) == "$Policy$"


def test_style_only_policy_does_not_import_dynamic_caption():
    scene = caption_scene()
    owner = scene.geo.element("s")
    owner.ggb_style = ImportPolicy.style_only().resolve(owner)
    assert resolve_label_text(scene, owner) == "$s$"


def test_renderer_refreshes_caption_and_keeps_source_hidden():
    from animageo.animageo import AnimaGeoScene, NamedValueTracker

    scene = AnimaGeoScene()
    scene.geo = caption_scene(content=r"\varphi + ").geo
    scene.putCode("Q = Point(n, 1)", show=False)
    text = scene.geo.element(scene.geo.name_mapping["текст_{1}"])
    text.data.segments.append(("obj", "n"))
    scene.applyStyle()
    scene.addAllGeometry(show=True)
    owner = scene.geo.element("s")
    assert scene._build_render_ctx(owner, False).label_text == r"$\varphi + 2$"
    assert scene.mobject(text.name) is None
    initial_label_width = scene.mobject("s").submobjects[-1].width
    # Same selective refresh used by the animation tracker: s's geometry has
    # no dependency on n, but its caption does and must still be redrawn.
    scene.updateVar(NamedValueTracker("n", 123))
    assert scene._build_render_ctx(owner, False).label_text == r"$\varphi + 123$"
    assert scene.mobject("s") is not None
    assert scene.mobject(text.name) is None
    assert scene.mobject("s").submobjects[-1].width > initial_label_width


def test_tikz_and_jsxgraph_export_dynamic_caption_as_formula():
    import json
    from animageo.animageo import AnimaGeoScene

    scene = AnimaGeoScene()
    scene.geo = caption_scene(content=r"\[\beta\]").geo
    scene.applyStyle()
    scene.fitView(480, 320)
    assert r"{$\beta$}" in scene.exportTikZ()
    spec = json.loads(scene.exportJSXGraph(output="spec"))
    segment = next(e for e in spec["elements"] if e["name"] == "s")
    assert segment["attrs"]["name"] == r"\(\beta\)"
