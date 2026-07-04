"""Tests for Function (lib_function.py) + render + intersect_Fl.

Covers parsing (incl. GGB ``label:`` prefix), numeric evaluation,
Function ∩ Line intersections (symbolic & numeric paths), render
dispatch, and GGB loading of ``<expression type="function">``.
"""
import logging
import os

import numpy as np
import pytest
import sympy as sp

from animageo.geo.lib_function import Function, parse_function_expression
from animageo.geo.lib_elements import Line, Point, Element
from animageo.geo.lib_commands import (
    intersect_Fl, intersect_lF, intersect_Fli, type_to_shortcut,
)


# ── Parsing ──────────────────────────────────────────────────────────

class TestParseExpression:
    def test_basic_polynomial(self):
        expr, var = parse_function_expression('x^2 + 1')
        assert str(var) == 'x'
        # Evaluate at x=2 → 5
        assert sp.simplify(expr.subs(var, 2) - 5) == 0

    def test_y_equals_form(self):
        expr, var = parse_function_expression('y = x^3 - 2*x')
        assert sp.simplify(expr.subs(var, 2) - 4) == 0

    def test_named_function_form(self):
        expr, var = parse_function_expression('f(x) = x + 1')
        assert sp.simplify(expr.subs(var, 5) - 6) == 0

    def test_ggb_label_prefix(self):
        # GGB writes some expressions with "label: y = ..." prefix.
        expr, var = parse_function_expression('i: y = -abs(x) + 4')
        # At x=3: y = -3 + 4 = 1.
        assert sp.simplify(expr.subs(var, 3) - 1) == 0
        # At x=-3: y = -3 + 4 = 1.
        assert sp.simplify(expr.subs(var, -3) - 1) == 0

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            parse_function_expression('(((')


# ── Function class ───────────────────────────────────────────────────

class TestFunction:
    def test_from_string(self):
        f = Function.from_string('y = x**2 + 1')
        assert f(2) == pytest.approx(5.0)
        assert f(0) == pytest.approx(1.0)

    def test_abs_function(self):
        f = Function.from_string('y = -abs(x) + 4')
        assert f(0) == pytest.approx(4.0)
        assert f(3) == pytest.approx(1.0)
        assert f(-3) == pytest.approx(1.0)

    def test_trig(self):
        f = Function.from_string('y = sin(x)')
        assert f(0) == pytest.approx(0.0, abs=1e-12)
        assert f(np.pi / 2) == pytest.approx(1.0)

    def test_undefined_returns_nan(self):
        # sqrt(x) at x < 0 is complex → treated as NaN.
        f = Function.from_string('y = sqrt(x)')
        v = f(-1)
        assert np.isnan(v) or (isinstance(v, complex) and abs(v.imag) > 0)

    def test_natural_singularities(self):
        # 1/x has singularity at x=0.
        f = Function.from_string('y = 1/x')
        assert 0.0 in f.natural_singularities or any(
            abs(s) < 1e-12 for s in f.natural_singularities
        )

    def test_sample_shape(self):
        f = Function.from_string('y = x**2')
        pts = f.sample((-2, 2), n=5)
        assert pts.shape == (5, 2)
        # y = x²
        for x, y in pts:
            assert np.isclose(y, x * x)

    def test_translate(self):
        f = Function.from_string('y = x**2')
        f.translate([1, 2])
        # After translate by (1, 2): new vertex at (1, 2), so y = (x-1)^2 + 2.
        assert f(1) == pytest.approx(2.0)
        assert f(2) == pytest.approx(3.0)  # 1 + 2 = 3
        assert f(0) == pytest.approx(3.0)  # 1 + 2

    def test_contains(self):
        f = Function.from_string('y = x**2')
        assert f.contains([2, 4])
        assert f.contains([0, 0])
        assert not f.contains([1, 0])


# ── Type system registration ─────────────────────────────────────────

class TestTypeRegistration:
    def test_shortcut_is_F(self):
        assert type_to_shortcut[Function] == 'F'

    def test_is_drawable(self):
        f = Function.from_string('y = x**2')
        elem = Element('f', f)
        assert elem.is_drawable()


# ── intersect_Fl ─────────────────────────────────────────────────────

class TestIntersectFl:
    def test_parabola_intersects_xaxis(self):
        # y = x² ∩ y = 0 → (0, 0) single tangent.
        f = Function.from_string('y = x**2')
        line = Line([0, 1], 0)   # y = 0
        result = intersect_Fl(f, line)
        assert result is not None
        # Could be a Point (tangent) or a list with one point.
        if isinstance(result, Point):
            assert np.allclose(result.coords, [0, 0], atol=1e-9)
        else:
            assert len(result) == 1
            assert np.allclose(result[0].coords, [0, 0], atol=1e-9)

    def test_parabola_intersects_horizontal_above(self):
        # y = x² ∩ y = 4 → (±2, 4).
        f = Function.from_string('y = x**2')
        line = Line([0, 1], 4)
        result = intersect_Fl(f, line)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.isclose(xs[0], -2, atol=1e-9)
        assert np.isclose(xs[1],  2, atol=1e-9)
        for p in result:
            assert np.isclose(p.coords[1], 4)

    def test_abs_function_intersects_line(self):
        # y = -|x| + 4 ∩ y = 0 → x = ±4 (at y = 0).
        f = Function.from_string('y = -abs(x) + 4')
        line = Line([0, 1], 0)
        result = intersect_Fl(f, line)
        assert isinstance(result, list) and len(result) == 2
        xs = sorted([p.coords[0] for p in result])
        assert np.isclose(xs[0], -4, atol=1e-6)
        assert np.isclose(xs[1],  4, atol=1e-6)

    def test_vertical_line(self):
        # y = x² ∩ x = 3 → (3, 9).
        f = Function.from_string('y = x**2')
        line = Line([1, 0], 3)  # x = 3
        result = intersect_Fl(f, line)
        assert isinstance(result, Point)
        assert np.isclose(result.coords[0], 3)
        assert np.isclose(result.coords[1], 9)

    def test_no_intersection(self):
        # y = x² + 10 ∩ y = 0: no real solution.
        f = Function.from_string('y = x**2 + 10')
        line = Line([0, 1], 0)
        assert intersect_Fl(f, line) is None

    def test_reverse_dispatch(self):
        f = Function.from_string('y = x**2')
        line = Line([0, 1], 4)
        r1 = intersect_Fl(f, line)
        r2 = intersect_lF(line, f)
        assert len(r1) == len(r2)

    def test_index_selection(self):
        f = Function.from_string('y = x**2')
        line = Line([0, 1], 4)
        p1 = intersect_Fli(f, line, 1)
        p2 = intersect_Fli(f, line, 2)
        assert p1 is not None and p2 is not None
        assert not np.allclose(p1.coords, p2.coords)

    def test_transcendental_via_numerical(self):
        # y = sin(x) ∩ y = 0.5 — sympy might return a single transcendental
        # root; numerical fallback should find the π/6 solution.
        f = Function.from_string('y = sin(x)')
        line = Line([0, 1], 0.5)
        result = intersect_Fl(f, line)
        assert result is not None
        # At least one solution in [-10, 10].
        pts = result if isinstance(result, list) else [result]
        assert any(np.isclose(p.coords[1], 0.5, atol=1e-6) for p in pts)


# ── Render dispatch ──────────────────────────────────────────────────

class TestRender:
    @pytest.fixture
    def scene(self, caplog):
        from animageo.animageo import AnimaGeoScene
        caplog.set_level(logging.WARNING, logger='animageo.animageo')
        s = AnimaGeoScene()
        s.camera.frame.set(width=12)
        return s

    def test_parabola_renders(self, scene, caplog):
        f = Function.from_string('y = x**2')
        elem = Element('p', f)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        assert len(mobj.submobjects) >= 1
        assert len(caplog.records) == 0

    def test_abs_function_renders(self, scene, caplog):
        # func5's function i.
        f = Function.from_string('y = -abs(x) + 4')
        elem = Element('i', f)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        assert len(mobj.submobjects) >= 1
        assert len(caplog.records) == 0


# ── GGB integration ──────────────────────────────────────────────────

class TestGGBFunctionExpression:
    def test_expression_type_function_parsed(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser
        from xml.etree import ElementTree

        xml = """
        <geogebra>
          <construction>
            <expression label="i" exp="i: y = (-abs(x)) + 4" type="function"/>
            <element type="function" label="i">
              <show object="true" label="false"/>
              <objColor r="0" g="103" b="88" alpha="0"/>
              <lineStyle thickness="5" type="0" opacity="178"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, ElementTree.fromstring(xml).find("construction"))
        i = constr.element('i')
        assert i is not None
        assert isinstance(i.data, Function)
        assert i.data(0) == pytest.approx(4.0)
        assert i.data(3) == pytest.approx(1.0)


FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5Functions:
    def test_function_i_loaded(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        constr = Construction()
        ggb_parser.load(constr, {}, FUNC5)
        i = constr.element('i')
        assert i is not None
        assert isinstance(i.data, Function)
        # i: y = -|x| + 4.
        assert i.data(0) == pytest.approx(4.0)
        assert i.data(2) == pytest.approx(2.0)
