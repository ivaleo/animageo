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


# GeoGebra writes the path of a point-on-object inline when the path was never
# given a name of its own: ``Point(Circle(A, 1/2))`` rather than ``Point(c)``.
# The parser used to look the path up under that raw expression string, find
# nothing, and fall through to the plain-command branch — which skips the
# following <element> block carrying the serialized coordinates. The point then
# kept the arbitrary position ``point_c`` invents for a missing tparam
# (``get_direction(None)`` = a random angle in [0, 1) rad), so every load placed
# it somewhere else and the whole dependent figure came out rotated.
INLINE_CIRCLE_POINT = """
    <element type="point" label="A">
        <show object="true" label="true"/>
        <coords x="-5" y="-1" z="1"/>
    </element>
    <command name="Point">
        <input a0="Circle[A, 1 / 2]"/>
        <output a0="O"/>
    </command>
    <element type="point" label="O">
        <show object="true" label="true"/>
        <coords x="-4.5" y="-1" z="1"/>
    </element>
"""


def test_point_on_inline_circle_keeps_serialized_position():
    c = _load(INLINE_CIRCLE_POINT)
    o = c.element("O")
    assert o is not None
    assert np.allclose(o.data.coords, [-4.5, -1.0])


def test_point_on_inline_circle_gets_tparam():
    c = _load(INLINE_CIRCLE_POINT)
    o = c.element("O")
    assert o is not None
    assert o.tparam is not None
    assert np.isclose(o.tparam, 0.0)


def test_point_on_inline_circle_is_deterministic():
    first = _load(INLINE_CIRCLE_POINT).element("O").data.coords
    second = _load(INLINE_CIRCLE_POINT).element("O").data.coords
    assert np.allclose(first, second)
