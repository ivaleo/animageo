"""Imported GeoGebra formulas have an implicit math mode; Python Text does not."""
from xml.etree import ElementTree as ET

import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Text, text_to_display_latex
from animageo.parsers.ggb_parser import parse_constr


def imported_text(content, latex=True):
    xml = ET.Element("construction")
    ET.SubElement(xml, "expression", label="txt", exp='"' + content + '"')
    text = ET.SubElement(xml, "element", type="text", label="txt")
    ET.SubElement(text, "isLaTeX", val=str(latex).lower())
    ET.SubElement(text, "startPoint", x="0", y="0", z="1")
    constr = Construction()
    parse_constr(constr, xml)
    return constr.element("txt").data


@pytest.mark.parametrize("content", [r"\varphi", r"\dfrac{\alpha-\beta}2", "x_1", r"\text{текст}"])
def test_bare_geogebra_formulas_get_math_mode(content):
    assert text_to_display_latex(None, imported_text(content), 2) == "$" + content + "$"


@pytest.mark.parametrize("content", [
    r"$\varphi$", r"$$\varphi$$", r"\(\varphi\)", r"\[\varphi\]",
    r"текст $x_1$ после", r"текст \(x_1\) после",
    r"\begin{equation}x=1\end{equation}",
    r"\begin{align*}x&=1\end{align*}",
])
def test_existing_math_scopes_and_mixed_text_are_preserved(content):
    assert text_to_display_latex(None, imported_text(content), 2) == content


def test_escaped_dollar_is_not_a_math_delimiter():
    text = imported_text(r"\text{price \$5}")
    assert text_to_display_latex(None, text, 2) == r"$\text{price \$5}$"


def test_plain_geogebra_text_keeps_escaping_and_spaces():
    text = imported_text("обычный текст: a_b & 50%", latex=False)
    assert text_to_display_latex(None, text, 2) == r"обычный текст: a\_b \& 50\%"


@pytest.mark.parametrize("content", ["plain prose", r"\textbf{bold}", r"$x_1$", r"text $x$ after"])
def test_python_latex_text_keeps_existing_semantics(content):
    text = Text([("str", content)], is_latex=True)
    assert text_to_display_latex(None, text, 2) == content


def test_empty_geogebra_formula_is_not_wrapped():
    assert text_to_display_latex(None, imported_text("  "), 2) == ""


def test_bare_formula_renders_as_same_glyphs_as_explicit_math():
    from manim import Tex
    from animageo.animageo import AnimaGeoScene
    from animageo.geo.lib_elements import Element
    from animageo.ui import RusTex

    scene = AnimaGeoScene()
    elem = Element("formula", imported_text(r"\varphi"))
    scene.geo.add(elem)
    rendered = scene.CreateMObject(elem)
    expected = Tex(r"$\varphi$", tex_template=RusTex)
    expected.set(font_size=scene._build_render_ctx(elem, z_auto=False).font_size)
    assert rendered is not None
    assert rendered.width == pytest.approx(expected.width)
    assert rendered.height == pytest.approx(expected.height)


def test_tikz_export_uses_math_mode_for_imported_bare_formula():
    from animageo.animageo import AnimaGeoScene
    from animageo.geo.lib_elements import Element

    scene = AnimaGeoScene()
    scene.geo.add(Element("formula", imported_text(r"\varphi")))
    scene.fitView(480, 320)
    assert r"{$\varphi$}" in scene.exportTikZ()
