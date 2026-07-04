"""Tests for DSL sugar and string-arg constructors.

1. String-arg dispatch (``Function("y = x^2")``, ``Conic("x^2+y^2=4")``,
   ``ImplicitCurve("sin(x)+cos(y)=0.5")``) through ``putCode``.
2. ``f(x) = expr`` sugar pre-processor.
3. Variable-renaming sugar (``f(t) = t^2 + 1`` → works via internal rename).
4. Conic.from_string classmethod.
"""
import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.parsers.dsl import run as putCode_exec
from animageo.parsers.dsl.sugar import preprocess_dsl_sugar
from animageo.geo.lib_elements import Function, Conic, ImplicitCurve, Point
from animageo.geo.lib_conic import ConicType


def putCode(constr, code, **kw):
    """Shim: run DSL code through the exec engine (short_parser removed)."""
    kw = {k: v for k, v in kw.items() if k in ('debug', 'show')}
    return putCode_exec(constr, code, **kw)


# ── Conic.from_string ─────────────────────────────────────────────────

class TestConicFromString:
    def test_circle_equation(self):
        c = Conic.from_string('x^2 + y^2 = 1')
        assert c.type == ConicType.CIRCLE
        center, r = c.as_circle()
        assert np.allclose(center, [0, 0])
        assert np.isclose(r, 1)

    def test_parabola_explicit(self):
        c = Conic.from_string('y = x^2 - 1')
        assert c.type == ConicType.PARABOLA
        p = c.as_parabola()
        assert np.allclose(p['vertex'], [0, -1], atol=1e-9)

    def test_ellipse(self):
        c = Conic.from_string('x^2/4 + y^2/9 = 1')
        assert c.type == ConicType.ELLIPSE

    def test_with_label_prefix(self):
        c = Conic.from_string('g: x^2 + y^2 = 4')
        assert c.type == ConicType.CIRCLE
        _, r = c.as_circle()
        assert np.isclose(r, 2)

    def test_non_polynomial_rejected(self):
        with pytest.raises(ValueError):
            Conic.from_string('sin(x) + y = 1')

    def test_degree_too_high_rejected(self):
        with pytest.raises(ValueError):
            Conic.from_string('x^3 + y^2 = 1')


# ── String-arg dispatch through putCode ───────────────────────────────

class TestStringDispatch:
    def test_function_via_putcode(self):
        constr = Construction()
        putCode(constr, 'f = Function("y = x^2")')
        f = constr.element('f')
        assert f is not None
        assert isinstance(f.data, Function)
        assert f.data(2) == pytest.approx(4.0)

    def test_conic_via_putcode(self):
        constr = Construction()
        putCode(constr, 'g = Conic("x^2 + y^2 = 4")')
        g = constr.element('g')
        assert g is not None
        assert isinstance(g.data, Conic)
        assert g.data.type == ConicType.CIRCLE

    def test_implicit_via_putcode(self):
        constr = Construction()
        putCode(constr, 'h = ImplicitCurve("sin(x) + cos(y) = 0.5")')
        h = constr.element('h')
        assert h is not None
        assert isinstance(h.data, ImplicitCurve)


# ── f(x) = expr sugar ─────────────────────────────────────────────────

class TestFunctionSugar:
    def test_preprocess_simple(self):
        out = preprocess_dsl_sugar('f(x) = x^2 + 1')
        assert 'Function' in out
        assert 'x^2 + 1' in out or 'x**2 + 1' in out or 'y = x^2 + 1' in out

    def test_preprocess_var_rename(self):
        # Sugar with variable 't' → should rewrite to use 'x' inside.
        out = preprocess_dsl_sugar('f(t) = t^2 + 1')
        assert 'x' in out
        # 't' as standalone variable should have been renamed to 'x'.
        assert ' t^' not in out and '(t' not in out.split('=', 1)[1]

    def test_sugar_dispatched_via_putcode(self):
        constr = Construction()
        putCode(constr, 'f(x) = x^2 + 1')
        f = constr.element('f')
        assert f is not None
        assert isinstance(f.data, Function)
        assert f.data(0) == pytest.approx(1.0)
        assert f.data(2) == pytest.approx(5.0)

    def test_sugar_with_other_var_name(self):
        constr = Construction()
        putCode(constr, 'g(t) = 2*t + 1')
        g = constr.element('g')
        assert g is not None
        assert isinstance(g.data, Function)
        assert g.data(0) == pytest.approx(1.0)
        assert g.data(3) == pytest.approx(7.0)

    def test_sugar_with_abs(self):
        constr = Construction()
        putCode(constr, 'h(x) = -abs(x) + 4')
        h = constr.element('h')
        assert h is not None
        assert h.data(0) == pytest.approx(4.0)
        assert h.data(3) == pytest.approx(1.0)

    def test_non_sugar_lines_unchanged(self):
        # Regular Python-ish DSL unaffected.
        code = 'A = Point(1, 2)\nB = Point(3, 4)\ns = Segment(A, B)'
        out = preprocess_dsl_sugar(code)
        assert out.strip() == code.strip()

    def test_mixed_sugar_and_normal(self):
        constr = Construction()
        code = '''
A = Point(1, 2)
B = Point(3, 4)
f(x) = x^2
'''
        putCode(constr, code)
        assert constr.element('A') is not None
        assert constr.element('B') is not None
        f = constr.element('f')
        assert f is not None
        assert isinstance(f.data, Function)


# ── End-to-end construction with DSL ──────────────────────────────────

class TestEndToEndDSL:
    def test_construction_with_intersections(self):
        constr = Construction()
        code = '''
f(x) = x^2 - 1
g = Conic("x^2 + y^2 = 4")
A, B = Intersect(f, g)
'''
        # Intersect(Function, Conic) dispatches to intersect_FK.
        # (F, K) shortcut for 2-point result.
        putCode(constr, code)
        f = constr.element('f')
        g = constr.element('g')
        A = constr.element('A')
        B = constr.element('B')
        assert f is not None and g is not None
        assert A is not None and isinstance(A.data, Point)
        assert B is not None and isinstance(B.data, Point)
        # Expected x ≈ ±1.5175 (same g ∩ h intersections as func5.ggb).
        xs = sorted([A.data.coords[0], B.data.coords[0]])
        assert np.isclose(xs[0], -1.5174899135519797, atol=1e-4)
        assert np.isclose(xs[1],  1.5174899135519797, atol=1e-4)
