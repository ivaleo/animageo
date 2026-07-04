"""Regression tests for the shared/D8aiQbzcqXQ import bugs.

1. ``Point(Polygon)`` — a point constrained to a polygon boundary was
   unsupported (the parser recognised points on Circle/Line/Ray/Segment/
   Conic/Locus/Function only). The output point never built, and every
   segment depending on it cascaded to ``depends_on_unsupported``. Now the
   point is created at its serialized coordinates so the geometry renders.

2. ``type="conicpart"`` fill — a ``CircleArc``'s ``<objColor alpha="0">``
   was ignored because ``conicpart`` was missing from the fill-import type
   list. With no ``fill_opacity`` in ``ggb_style`` the resolver fell back to
   the builtin ``defaults.arc.fill_opacity = 1`` and the transparent arc
   rendered filled.
"""
import numpy as np
from xml.etree import ElementTree

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Point, Segment, Polygon, Arc
from animageo.geo.lib_commands import point_P
from animageo.parsers import ggb_parser
from animageo.style.ggb_resolver import resolve_ggb_style
from animageo.style.config import StyleConfig
from animageo.style.resolver import resolve


def _parse_xml(xml_str: str):
    root = ElementTree.fromstring(xml_str)
    return root.find("construction")


# ── Bug 1: Point(Polygon) ──────────────────────────────────────────────

class TestPointOnPolygon:
    XML = """
    <geogebra>
      <construction>
        <element type="point" label="A"><coords x="0" y="0" z="1"/></element>
        <element type="point" label="B"><coords x="4" y="0" z="1"/></element>
        <element type="point" label="C"><coords x="0" y="3" z="1"/></element>
        <command name="Polygon">
          <input a0="A" a1="B" a2="C"/>
          <output a0="t1"/>
        </command>
        <element type="polygon" label="t1">
          <show object="true" label="false"/>
        </element>
        <command name="Point">
          <input a0="t1"/>
          <output a0="N"/>
        </command>
        <element type="point" label="N">
          <show object="true" label="true"/>
          <coords x="2" y="0" z="1"/>
        </element>
        <command name="Segment">
          <input a0="A" a1="N"/>
          <output a0="j"/>
        </command>
        <element type="segment" label="j">
          <show object="true" label="false"/>
        </element>
      </construction>
    </geogebra>
    """

    def test_point_on_polygon_builds_at_coords(self):
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(self.XML))
        n = constr.element('N')
        assert n is not None
        assert isinstance(n.data, Point)
        assert np.allclose(n.data.coords, [2, 0])

    def test_polygon_point_leaves_no_unsupported_diagnostics(self):
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(self.XML))
        assert constr.command_diagnostics == []

    def test_segment_on_polygon_point_unblocked(self):
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(self.XML))
        j = constr.element('j')
        assert j is not None
        assert isinstance(j.data, Segment)


class TestPointPCreator:
    """The ``point_P`` perimeter creator (the tparam branch the parser does
    not yet exercise — coords→perimeter inverse is not implemented)."""

    POLY = Polygon([[0, 0], [4, 0], [0, 3]])  # right triangle

    def test_default_is_first_vertex(self):
        assert np.allclose(point_P(self.POLY).coords, [0, 0])

    def test_fractional_param_interpolates_along_edge(self):
        assert np.allclose(point_P(self.POLY, 0.5).coords, [2, 0])

    def test_integer_param_lands_on_vertex(self):
        assert np.allclose(point_P(self.POLY, 1).coords, [4, 0])

    def test_param_wraps_around_perimeter(self):
        assert np.allclose(point_P(self.POLY, 3).coords, [0, 0])

    def test_empty_polygon_returns_none(self):
        assert point_P(Polygon([])) is None


# ── Bug 2: type="conicpart" transparent fill ───────────────────────────

class TestConicPartFill:
    XML = """
    <geogebra>
      <construction>
        <element type="point" label="A"><coords x="0" y="0" z="1"/></element>
        <element type="point" label="B"><coords x="1" y="0" z="1"/></element>
        <element type="point" label="C"><coords x="0" y="1" z="1"/></element>
        <command name="CircleArc">
          <input a0="A" a1="B" a2="C"/>
          <output a0="c_1"/>
        </command>
        <element type="conicpart" label="c_1">
          <show object="true" label="false"/>
          <objColor r="110" g="109" b="115" alpha="0"/>
          <lineStyle thickness="5" type="0" opacity="204"/>
        </element>
      </construction>
    </geogebra>
    """

    def test_conicpart_alpha_imported_to_ggb_style(self):
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(self.XML))
        c1 = constr.element('c_1')
        assert c1 is not None
        assert isinstance(c1.data, Arc)
        assert c1.ggb_style.get('fill_opacity') == 0.0
        assert c1.ggb_style.get('fill') == '#6e6d73'

    def test_conicpart_resolves_to_transparent_fill(self):
        # End-to-end: with builtin defaults loaded, a transparent GGB arc
        # must resolve to fill_opacity 0 — not the arc default of 1.
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(self.XML))
        c1 = constr.element('c_1')
        cfg = StyleConfig.load()
        assert resolve(cfg, c1, 'fill_opacity', default=1) == 0.0

    def test_resolve_ggb_style_conicpart_alpha(self):
        raw = {
            'elem_type': 'conicpart',
            'obj_color': {'r': 110, 'g': 109, 'b': 115,
                          'alpha': 0.0, 'opacity': 0.0, 'hex': '#6e6d73'},
        }
        result = resolve_ggb_style(raw)
        assert result.get('fill_opacity') == 0.0
        assert result.get('fill') == '#6e6d73'
