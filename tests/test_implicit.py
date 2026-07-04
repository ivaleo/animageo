"""Tests for ImplicitCurve (lib_implicit.py) + marching_squares render.

Covers:
- Parsing F(x,y) from string and equation forms.
- Evaluation (scalar and vectorized).
- Marching-squares on analytic F: unit circle x²+y²-1 and a saddle.
- Render dispatch.
- GGB ``<expression type="implicitpoly">`` handling and func5.ggb's
  ``sqrt(-4·y) + sqrt|x − 1| = 5`` fixture.
"""
import logging
import os

import numpy as np
import pytest

from animageo.geo.lib_implicit import ImplicitCurve, parse_implicit_expression
from animageo.geo.lib_elements import Element
from animageo.geo.curve_sampling import marching_squares


# ── Parsing ──────────────────────────────────────────────────────────

class TestParse:
    def test_implicit_zero_form(self):
        expr, x, y = parse_implicit_expression('x**2 + y**2 - 1')
        assert float(expr.subs([(x, 1), (y, 0)])) == pytest.approx(0)
        assert float(expr.subs([(x, 0.5), (y, 0)])) < 0

    def test_equation_form(self):
        expr, x, y = parse_implicit_expression('x**2 + y**2 = 1')
        # After A = B → (A) - (B) form: on the curve F = 0.
        assert float(expr.subs([(x, 1), (y, 0)])) == pytest.approx(0)

    def test_ggb_implicitpoly(self):
        # Non-polynomial despite the name — sqrt + abs.
        expr, x, y = parse_implicit_expression(
            'sqrt((-4 * y)) + sqrt(abs(x - 1)) = 5'
        )
        # At (1, -9): sqrt(36) + sqrt(0) = 6 + 0 ≠ 5. So F != 0 there.
        # At x=1, sqrt|0|=0, need sqrt(-4y)=5, so y = -25/4 = -6.25.
        val = expr.subs([(x, 1), (y, -6.25)])
        assert float(val) == pytest.approx(0, abs=1e-6)

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            parse_implicit_expression('(((')


# ── ImplicitCurve class ──────────────────────────────────────────────

class TestImplicitCurve:
    def test_unit_circle_on_curve(self):
        F = ImplicitCurve.from_string('x^2 + y^2 = 1')
        assert F(1, 0) == pytest.approx(0, abs=1e-9)
        assert F(0, 1) == pytest.approx(0, abs=1e-9)
        assert F(0, 0) == pytest.approx(-1)
        assert F(2, 0) == pytest.approx(3)

    def test_vectorized_eval(self):
        F = ImplicitCurve.from_string('x^2 + y^2 - 1')
        xs = np.array([0.0, 1.0, 2.0])
        ys = np.array([0.0, 0.0, 0.0])
        result = F(xs, ys)
        assert np.allclose(result, [-1, 0, 3])

    def test_contains(self):
        F = ImplicitCurve.from_string('x^2 + y^2 - 1')
        assert F.contains([1, 0])
        assert F.contains([0, 1])
        assert not F.contains([0, 0])

    def test_translate(self):
        F = ImplicitCurve.from_string('x^2 + y^2 - 1')
        F.translate([3, -2])
        # Now curve is (x-3)^2 + (y+2)^2 = 1, so F(3, -2) = -1, F(4, -2) = 0.
        assert F(3, -2) == pytest.approx(-1, abs=1e-9)
        assert F(4, -2) == pytest.approx(0, abs=1e-9)


# ── marching_squares ─────────────────────────────────────────────────

class TestMarchingSquares:
    def test_unit_circle_contour(self):
        def F(x, y):
            return x * x + y * y - 1

        viewport = (-2.0, -2.0, 2.0, 2.0)
        segments = marching_squares(F, viewport, grid_n=64)
        # Expect ~100 segments for a decent circle discretization.
        assert len(segments) > 50

        # Every segment endpoint should lie on (or very near) the circle.
        for seg in segments:
            for p in seg:
                r = np.sqrt(p[0] ** 2 + p[1] ** 2)
                assert abs(r - 1.0) < 0.1  # grid discretization gives some slack

    def test_saddle(self):
        # Saddle at origin: contains both branches of x² − y² = 0.
        def F(x, y):
            return x * x - y * y

        viewport = (-2.0, -2.0, 2.0, 2.0)
        segments = marching_squares(F, viewport, grid_n=64)
        assert len(segments) > 10
        # Points satisfy |x| ≈ |y|.
        for seg in segments:
            for p in seg:
                assert abs(abs(p[0]) - abs(p[1])) < 0.2

    def test_empty_level_set(self):
        def F(x, y):
            return x * x + y * y + 1  # always positive, F = 0 has no points

        viewport = (-2.0, -2.0, 2.0, 2.0)
        assert marching_squares(F, viewport, grid_n=32) == []

    def test_nan_regions_skipped(self):
        def F(x, y):
            return np.sqrt(y) - x  # NaN for y < 0

        viewport = (-2.0, -2.0, 2.0, 2.0)
        segments = marching_squares(F, viewport, grid_n=32)
        # Should render without crashing. No valid crossings for y<0.
        for seg in segments:
            for p in seg:
                assert p[1] >= -0.2  # all on valid side


# ── Render ───────────────────────────────────────────────────────────

class TestRender:
    @pytest.fixture
    def scene(self, caplog):
        from animageo.animageo import AnimaGeoScene
        caplog.set_level(logging.WARNING, logger='animageo.animageo')
        s = AnimaGeoScene()
        s.camera.frame.set(width=10)
        return s

    def test_implicit_renders(self, scene, caplog):
        F = ImplicitCurve.from_string('x^2 + y^2 = 4')
        elem = Element('c', F)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        assert len(mobj.submobjects) > 10
        assert len(caplog.records) == 0


# ── GGB integration ──────────────────────────────────────────────────

class TestGGBImplicitpolyExpression:
    def test_parse_from_xml(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser
        from xml.etree import ElementTree

        xml = """
        <geogebra>
          <construction>
            <expression label="j" exp="sqrt((-4 * y)) + sqrt(abs(x - 1)) = 5" type="implicitpoly"/>
            <element type="implicitpoly" label="j">
              <show object="true" label="false"/>
              <objColor r="110" g="109" b="115" alpha="0"/>
            </element>
          </construction>
        </geogebra>
        """
        constr = Construction()
        ggb_parser.parse_constr(constr, ElementTree.fromstring(xml).find("construction"))
        j = constr.element('j')
        assert j is not None
        assert isinstance(j.data, ImplicitCurve)


FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5Implicit:
    def test_implicit_j_loads(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        constr = Construction()
        ggb_parser.load(constr, {}, FUNC5)
        j = constr.element('j')
        assert j is not None
        assert isinstance(j.data, ImplicitCurve)
