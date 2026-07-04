"""GeoGebra conditional visibility (`<condition showObject="b"/>`).

GeoGebra lets an object's visibility depend on a boolean: even with
``<show object="true"/>`` the object is drawn only while the referenced
boolean is true. The ``.ggb`` stores this as a sibling
``<condition showObject="expr"/>`` plus a ``<element type="boolean">`` whose
``<value val="true|false"/>`` holds the current state.

The parser must honour this for static export: when the boolean is false the
conditioned object is hidden, regardless of its own ``<show object>``.
Regression fixture for the shared construction ``gGqlphuIE_0`` (куб и тетраэдр),
where boolean ``b=false`` should hide the dotted edges but they exported anyway.
"""
import os
import tempfile
import zipfile

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser


def _make_ggb(boolean_value: str, condition_expr: str = "b") -> str:
    """Write a minimal .ggb: points A/B/C, boolean ``b``, a conditioned dotted
    segment ``f`` (show=true, condition=``condition_expr``) and an
    unconditioned solid segment ``g``. Returns the temp path."""
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<geogebra format="5.0">
<euclidianView>
    <size width="600" height="400"/>
    <coordSystem xZero="300" yZero="200" scale="50" yscale="50"/>
    <evSettings axes="false" grid="false"/>
    <bgColor r="255" g="255" b="255"/>
</euclidianView>
<construction>
    <element type="point" label="A">
        <show object="true" label="true"/>
        <coords x="0" y="0" z="1"/>
    </element>
    <element type="point" label="B">
        <show object="true" label="true"/>
        <coords x="2" y="0" z="1"/>
    </element>
    <element type="point" label="C">
        <show object="true" label="true"/>
        <coords x="2" y="2" z="1"/>
    </element>
    <element type="boolean" label="b">
        <value val="{boolean_value}"/>
        <show object="false" label="true"/>
    </element>
    <command name="Segment">
        <input a0="A" a1="B"/>
        <output a0="f"/>
    </command>
    <element type="segment" label="f">
        <show object="true" label="false"/>
        <condition showObject="{condition_expr}"/>
        <lineStyle thickness="5" type="20"/>
    </element>
    <command name="Segment">
        <input a0="B" a1="C"/>
        <output a0="g"/>
    </command>
    <element type="segment" label="g">
        <show object="true" label="false"/>
        <lineStyle thickness="5" type="0"/>
    </element>
</construction>
</geogebra>
"""
    fd, path = tempfile.mkstemp(suffix=".ggb")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("geogebra.xml", xml)
    return path


def _load(boolean_value: str, condition_expr: str = "b") -> Construction:
    path = _make_ggb(boolean_value, condition_expr)
    try:
        c = Construction()
        view = {"ptUnit": 1, "ptWidth": 600, "ptHeight": 400,
                "ptXZero": 300, "ptYZero": 200}
        ggb_parser.load(c, view, path, debug=False)
        return c
    finally:
        os.remove(path)


def test_condition_false_hides_object():
    """boolean b=false → conditioned segment hidden, unconditioned stays visible."""
    c = _load("false")
    assert c.element("f").visible is False, "conditioned segment must be hidden when b=false"
    assert c.element("g").visible is True, "unconditioned segment must stay visible"


def test_condition_true_keeps_object_visible():
    """boolean b=true → conditioned segment follows its own <show object=true>."""
    c = _load("true")
    assert c.element("f").visible is True
    assert c.element("g").visible is True


def test_boolean_value_is_parsed_as_var():
    """The boolean element is parsed into a Var carrying its bool value."""
    from animageo.geo.lib_vars import Boolean

    c = _load("false")
    b = c.var("b")
    assert b is not None, "boolean element must be registered as a Var"
    assert isinstance(b.data, Boolean)
    assert b.data.value is False


def test_unrecognized_condition_leaves_object_visible():
    """A condition that is not a plain boolean reference is ignored (fail-safe:
    object left visible), never crashes the load."""
    c = _load("false", condition_expr="A == B")
    assert c.element("f").visible is True
