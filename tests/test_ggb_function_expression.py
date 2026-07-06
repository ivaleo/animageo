"""Regression tests for GeoGebra function expressions.

GeoGebra can serialize a function's equation without ``type="function"`` on
the ``<expression>`` itself and put the type only on the following
``<element type="function">``. The function may also reference sliders.
"""
from xml.etree import ElementTree

import numpy as np

from animageo.geo.construction import Construction
from animageo.geo.lib_function import Function
from animageo.parsers import ggb_parser


def _parse_xml(xml_str: str):
    root = ElementTree.fromstring(xml_str)
    return root.find("construction")


def test_companion_function_element_and_slider_value_build_function():
    xml = """
    <geogebra>
      <construction>
        <element type="numeric" label="a">
          <value val="-3.18"/>
          <show object="false" label="true"/>
        </element>
        <expression label="f" exp="f(x) = (((2 * a) - 1) * x^(2)) + (6 * (a * x)) + 1"/>
        <element type="function" label="f">
          <show object="true" label="false"/>
          <objColor r="0" g="103" b="88" alpha="0"/>
          <lineStyle thickness="5" type="0" opacity="178"/>
        </element>
      </construction>
    </geogebra>
    """
    constr = Construction()
    ggb_parser.parse_constr(constr, _parse_xml(xml))

    elem = constr.element("f")
    assert elem is not None
    assert isinstance(elem.data, Function)
    assert np.isclose(elem.data(0), 1.0)
    assert np.isclose(elem.data(1), -25.44)
    assert elem.ggb_style["stroke"] == "#006758"
    assert elem.ggb_style["stroke_opacity"] == 178 / 255
