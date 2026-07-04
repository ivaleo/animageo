"""Tests for GGB parser handling of conic/line expressions with '='.

Verifies that:
- `<expression type="conic" ...>` followed by `<element type="conic">`
  with `<matrix A0..A5>` produces a Conic element with the exact matrix
  that GeoGebra emitted.
- `<expression type="line" exp="y = 2x + 1">` followed by
  `<element type="line"><coords x y z>` produces the animageo
  `Line(n=[a, b], c=-z)` equivalent.
- Styling (stroke color, opacity) is applied on the new elements.
- Real-world fixture ``examples/func/func5.ggb`` (if present) loads
  without regressions: both ``g`` (parabola) and ``h`` (circle) are
  created with correct types.
"""
import io
import os
import zipfile
import tempfile

import numpy as np
import pytest
from xml.etree import ElementTree

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Conic, Line, Point
from animageo.geo.lib_conic import ConicType
from animageo.parsers import ggb_parser


def _parse_xml(xml_str: str):
    """Parse a construction XML fragment and return its <construction> node."""
    root = ElementTree.fromstring(xml_str)
    return root.find("construction")


# ── Expression type="conic" with <matrix A0..A5> ───────────────────────

class TestConicExpression:
    def test_ggb_circle_from_matrix(self):
        # h: x² + y² = 4
        xml = """
        <geogebra>
          <construction>
            <expression label="h" exp="x^(2) + y^(2) = 4" type="conic"/>
            <element type="conic" label="h">
              <show object="true" label="false"/>
              <objColor r="100" g="100" b="200" alpha="0.2"/>
              <lineStyle thickness="5" type="0"/>
              <matrix A0="1" A1="1" A2="-4" A3="0" A4="0" A5="0"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        h = constr.element('h')
        assert h is not None
        assert isinstance(h.data, Conic)
        assert h.data.type == ConicType.CIRCLE
        center, radius = h.data.as_circle()
        assert np.allclose(center, [0, 0])
        assert np.isclose(radius, 2)

    def test_ggb_parabola_from_matrix(self):
        # g: y = x² − 1 (written as −x² + y + 1 = 0).
        xml = """
        <geogebra>
          <construction>
            <expression label="g" exp="y = x^(2) - 1" type="conic"/>
            <element type="conic" label="g">
              <show object="true" label="false"/>
              <objColor r="110" g="109" b="115" alpha="0"/>
              <lineStyle thickness="5" type="0" opacity="204"/>
              <matrix A0="-1" A1="0" A2="1" A3="0" A4="0" A5="0.5"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        g = constr.element('g')
        assert g is not None
        assert isinstance(g.data, Conic)
        assert g.data.type == ConicType.PARABOLA
        params = g.data.as_parabola()
        assert np.allclose(params['vertex'], [0, -1], atol=1e-9)

    def test_conic_styling_applied(self):
        xml = """
        <geogebra>
          <construction>
            <expression label="c" exp="x^(2) + y^(2) = 1" type="conic"/>
            <element type="conic" label="c">
              <show object="true" label="false"/>
              <objColor r="255" g="0" b="0" alpha="0.5"/>
              <lineStyle thickness="6" type="0" opacity="204"/>
              <matrix A0="1" A1="1" A2="-1" A3="0" A4="0" A5="0"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        c = constr.element('c')
        assert c is not None
        # Fill and stroke colors arrive from <objColor> into the GGB import layer.
        assert c.ggb_style.get('fill') == '#ff0000'
        assert c.ggb_style.get('stroke') == '#ff0000'
        # Conic type gets a fill alpha via the 'angle/polygon/arc/conic' rule.
        assert c.ggb_style.get('fill_opacity') == 0.5

    def test_missing_matrix_does_not_crash(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger='animageo.parsers.ggb_parser')
        xml = """
        <geogebra>
          <construction>
            <expression label="k" exp="x^(2) + y^(2) = 1" type="conic"/>
            <element type="conic" label="k">
              <show object="true" label="false"/>
              <objColor r="0" g="0" b="0" alpha="0"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        # No Conic created; warning logged; no exception.
        assert constr.element('k') is None

    def test_point_on_conic_command_uses_ggb_coordinates(self):
        xml = """
        <geogebra>
          <construction>
            <expression label="e" exp="x^(2) / 4 - y^(2) / 9 = 1" type="conic"/>
            <element type="conic" label="e">
              <show object="true" label="false"/>
              <matrix A0="0.25" A1="-0.1111111111111111" A2="-1" A3="0" A4="0" A5="0"/>
            </element>
            <command name="Point">
              <input a0="e"/>
              <output a0="G"/>
            </command>
            <element type="point" label="G">
              <show object="true" label="true"/>
              <coords x="-2" y="0" z="1"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))

        g = constr.element('G')
        assert constr.command_diagnostics == []
        assert g is not None
        assert isinstance(g.data, Point)
        assert np.allclose(g.data.coords, [-2, 0])
        assert g.fixed is False
        assert g.tparam[0] < 0


# ── Expression type="line" with <coords x y z> ─────────────────────────

class TestLineExpression:
    def test_ggb_line_from_coords(self):
        # f: y = 2x + 1 → 2x − y + 1 = 0 → GGB coords (−2, 1, −1).
        xml = """
        <geogebra>
          <construction>
            <expression label="f" exp="y = (2 * x) + 1" type="line"/>
            <element type="line" label="f">
              <show object="true" label="false"/>
              <objColor r="0" g="0" b="255" alpha="0"/>
              <lineStyle thickness="4" type="0"/>
              <coords x="-2" y="1" z="-1"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        f = constr.element('f')
        assert f is not None
        assert isinstance(f.data, Line)
        # Check the line passes through (0, 1) and (1, 3).
        assert f.data.contains(np.array([0, 1]))
        assert f.data.contains(np.array([1, 3]))

    def test_vertical_line_from_coords(self):
        # l: x = 4 → 1·x + 0·y − 4 = 0 → GGB coords (1, 0, −4).
        xml = """
        <geogebra>
          <construction>
            <expression label="l" exp="x = 4" type="line"/>
            <element type="line" label="l">
              <show object="true" label="false"/>
              <objColor r="0" g="0" b="0" alpha="0"/>
              <lineStyle thickness="3" type="0"/>
              <coords x="1" y="0" z="-4"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        l = constr.element('l')
        assert l is not None
        assert isinstance(l.data, Line)
        assert l.data.contains(np.array([4, 0]))
        assert l.data.contains(np.array([4, -5]))
        assert not l.data.contains(np.array([3, 0]))

    def test_line_styling_applied(self):
        xml = """
        <geogebra>
          <construction>
            <expression label="m" exp="y = 3 * x" type="line"/>
            <element type="line" label="m">
              <show object="true" label="false"/>
              <objColor r="21" g="101" b="192" alpha="0"/>
              <lineStyle thickness="5" type="0" opacity="204"/>
              <coords x="3" y="-1" z="0"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        m = constr.element('m')
        assert m is not None
        assert m.ggb_style.get('stroke') == '#1565c0'


# ── Backwards compatibility: non-= expressions unaffected ─────────────

class TestBackwardsCompatibility:
    def test_expression_without_equals_still_works(self):
        # A simple named point: no = sign → existing putCode path.
        xml = """
        <geogebra>
          <construction>
            <element type="point" label="A">
              <show object="true" label="true"/>
              <objColor r="0" g="0" b="0" alpha="0"/>
              <pointSize val="4"/>
              <coords x="1" y="2" z="1"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, _parse_xml(xml))
        a = constr.element('A')
        assert a is not None
        assert np.allclose(a.data.coords, [1, 2])


# ── Fixture: examples/func/func5.ggb (if available) ───────────────────

FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)

SCENE21 = os.path.join(
    os.path.dirname(__file__), '..', 'examples',
    '21 -  Задача Феди про линзы', 'scene21.ggb',
)

SCENE17 = os.path.join(
    os.path.dirname(__file__), '..', 'examples',
    '17 - Два луча в угле', 'scene17.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5Fixture:
    def test_func5_loads(self):
        constr = Construction()
        view = {}
        ggb_parser.load(constr, view, FUNC5)

        # g: parabola y = x² − 1.
        g = constr.element('g')
        assert g is not None
        assert isinstance(g.data, Conic)
        assert g.data.type == ConicType.PARABOLA

        # h: circle x² + y² = 4.
        h = constr.element('h')
        assert h is not None
        assert isinstance(h.data, Conic)
        assert h.data.type == ConicType.CIRCLE
        center, radius = h.data.as_circle()
        assert np.allclose(center, [0, 0])
        assert np.isclose(radius, 2)

        # f: line y = 2x + 1 (expression type="line").
        f = constr.element('f')
        assert f is not None
        assert isinstance(f.data, Line)
        # y = 2x + 1 → passes through (0, 1).
        assert f.data.contains(np.array([0, 1]))

        # l: vertical line x = 4.
        l = constr.element('l')
        assert l is not None
        assert isinstance(l.data, Line)
        assert l.data.contains(np.array([4, 0]))


@pytest.mark.skipif(not os.path.isfile(SCENE21), reason='scene21.ggb not available')
class TestScene21Fixture:
    def test_scene21_point_on_hyperbola_unblocks_dependents(self):
        constr = Construction()
        view = {}
        ggb_parser.load(constr, view, SCENE21)

        assert constr.command_diagnostics == []
        for name in ('G', 'H', 'I', 'J', 'd', 'r', 'p', 'q', 'α'):
            elem = constr.element(name)
            assert elem is not None, name
            assert elem.data is not None, name
        for name in ('IG', 'GJ', 'a'):
            var = constr.var(name)
            assert var is not None, name
            assert var.data is not None, name


@pytest.mark.skipif(not os.path.isfile(SCENE17), reason='scene17.ggb not available')
class TestScene17Fixture:
    def test_scene17_unicode_arc_intersections_build_red_segments(self):
        constr = Construction()
        view = {}
        ggb_parser.load(constr, view, SCENE17)

        assert constr.command_diagnostics == []
        expected = {
            'E': [-5.427571172216735, -1.5676736367231316],
            'F': [-3.5724288277832636, -1.567673636723131],
        }
        for name, coords in expected.items():
            elem = constr.element(name)
            assert elem is not None, name
            assert isinstance(elem.data, Point)
            assert np.allclose(elem.data.coords, coords, atol=1e-9)
        for name in ('m', 'n'):
            elem = constr.element(name)
            assert elem is not None, name
            assert elem.data is not None, name
