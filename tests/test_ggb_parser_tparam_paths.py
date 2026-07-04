"""Parser: tparam detection for points on function graphs (and the
dispatcher-backed conic path, regression)."""
import os
import tempfile
import zipfile

import numpy as np

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser


def _make_ggb(body: str) -> str:
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<geogebra format="5.0">
<euclidianView>
    <size width="600" height="400"/>
    <coordSystem xZero="300" yZero="200" scale="50" yscale="50"/>
    <evSettings axes="false" grid="false"/>
    <bgColor r="255" g="255" b="255"/>
</euclidianView>
<construction>
{body}
</construction>
</geogebra>
"""
    fd, path = tempfile.mkstemp(suffix=".ggb")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("geogebra.xml", xml)
    return path


def _load(body: str) -> Construction:
    path = _make_ggb(body)
    try:
        c = Construction()
        view = {"ptUnit": 1, "ptWidth": 600, "ptHeight": 400,
                "ptXZero": 300, "ptYZero": 200}
        ggb_parser.load(c, view, path, debug=False)
        return c
    finally:
        os.remove(path)


FUNCTION_POINT = """
    <expression label="f" exp="f(x) = x^2" type="function"/>
    <element type="function" label="f">
        <show object="true" label="true"/>
        <objColor r="0" g="0" b="0" alpha="0"/>
    </element>
    <command name="Point">
        <input a0="f"/>
        <output a0="P"/>
    </command>
    <element type="point" label="P">
        <show object="true" label="true"/>
        <coords x="1.5" y="2.25" z="1"/>
    </element>
"""


def test_point_on_function_gets_tparam():
    c = _load(FUNCTION_POINT)
    p = c.element("P")
    assert p is not None
    assert p.tparam is not None
    assert np.isclose(p.tparam, 1.5)


def test_point_on_function_rebuilds_on_graph():
    c = _load(FUNCTION_POINT)
    c.update_tparam("P", 2.0)
    c.rebuild()
    assert np.allclose(c.element("P").data.coords, [2.0, 4.0])
