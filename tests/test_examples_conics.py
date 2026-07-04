"""Smoke-test for examples/conics_functions/*.py.

Constructs each example's scene and verifies its DSL resolves into the
expected set of named elements. We don't run the full manim render
pipeline here (that's expensive and out of scope for unit tests) —
just the ``putCode``/``Construction`` side, which is where the DSL
and new commands live.
"""
import os
import sys

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene
from animageo.geo.lib_elements import (
    Conic, Function, ImplicitCurve, Line, Point,
)
from animageo.geo.lib_conic import ConicType


def _scene():
    """Fresh AnimaGeoScene with a camera frame sized for the tests."""
    s = AnimaGeoScene()
    s.camera.frame.set(width=12)
    return s


# ── 01 conic gallery ─────────────────────────────────────────────────

def test_example_01_gallery_creates_five_conics():
    s = _scene()
    s.putCode('''
        circle     = Conic("(x + 4)^2 + (y - 1)^2 = 1")
        ellipse    = Conic("(x + 2)^2 / 1 + (y - 1)^2 / 0.6 = 1")
        parabola   = Conic("y - 1 = (x - 0.3)^2")
        hyperbola  = Conic("(x - 2.6)^2 / 0.5 - (y - 1)^2 / 0.5 = 1")
        pair       = Conic("(x - 5)^2 - (y - 1)^2 / 4 = 0")
    ''')
    expected_types = {
        'circle': ConicType.CIRCLE,
        'ellipse': ConicType.ELLIPSE,
        'parabola': ConicType.PARABOLA,
        'hyperbola': ConicType.HYPERBOLA,
        'pair': ConicType.INTERSECTING_LINES,
    }
    for name, kind in expected_types.items():
        elem = s.element(name)
        assert elem is not None, f"{name} not created"
        assert isinstance(elem.data, Conic)
        assert elem.data.type == kind


# ── 02 functions + piecewise ─────────────────────────────────────────

def test_example_02_functions():
    s = _scene()
    s.putCode('''
        quad   = Function("y = x^2 - 3")
        sinu   = Function("y = 2 * sin(x)")
        abs_fn = Function("y = -abs(x) + 4")
        piecew = Function("y = If[-1 <= x <= 1, x^2]")
    ''')
    for name in ('quad', 'sinu', 'abs_fn', 'piecew'):
        elem = s.element(name)
        assert elem is not None
        assert isinstance(elem.data, Function)
    # sanity evaluation
    assert np.isclose(s.element('quad').data(2), 1.0)
    assert np.isclose(s.element('abs_fn').data(0), 4.0)
    assert np.isnan(s.element('piecew').data(2))


# ── 03 implicit curves ───────────────────────────────────────────────

def test_example_03_implicit():
    s = _scene()
    s.putCode('''
        lemniscate = ImplicitCurve("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")
        folium     = ImplicitCurve("x^3 + y^3 - 3.6 * x * y = 0")
    ''')
    for name in ('lemniscate', 'folium'):
        elem = s.element(name)
        assert elem is not None
        assert isinstance(elem.data, ImplicitCurve)


# ── 04 intersections ─────────────────────────────────────────────────

def test_example_04_function_conic():
    s = _scene()
    s.putCode('''
        f = Function("y = -abs(x) + 4")
        g = Conic("y = x^2 - 1")
        J, K = Intersect(f, g)
    ''')
    J = s.element('J')
    K = s.element('K')
    assert J is not None and isinstance(J.data, Point)
    assert K is not None and isinstance(K.data, Point)


def test_example_04_conic_conic():
    s = _scene()
    s.putCode('''
        g = Conic("y = x^2 - 1")
        h = Conic("x^2 + y^2 = 4")
        C, D = Intersect(g, h)
    ''')
    C = s.element('C')
    D = s.element('D')
    assert C is not None and D is not None
    # func5.ggb reference values for (g ∩ h).
    xs = sorted([C.data.coords[0], D.data.coords[0]])
    assert np.isclose(xs[0], -1.5174899135519797, atol=1e-4)
    assert np.isclose(xs[1],  1.5174899135519797, atol=1e-4)


# ── 05 conic properties ──────────────────────────────────────────────

def test_example_05_ellipse_properties():
    s = _scene()
    s.putCode('''
        e = Conic("x^2 / 9 + y^2 / 4 = 1")
        O = Center(e)
        F1, F2 = Focus(e)
        V1, V2, V3, V4 = Vertex(e)
    ''')
    assert np.allclose(s.element('O').data.coords, [0, 0])
    xs = sorted([s.element('F1').data.coords[0], s.element('F2').data.coords[0]])
    assert np.allclose(xs, [-np.sqrt(5), np.sqrt(5)], atol=1e-9)


def test_example_05_parabola_properties():
    s = _scene()
    s.putCode('''
        p = Conic("y = x^2 / 2")
        V = Vertex(p)
        F = Focus(p)
    ''')
    assert np.allclose(s.element('V').data.coords, [0, 0], atol=1e-9)
    # y = x²/2 → p = 1/2 → focus at (0, 0.5)
    assert np.allclose(s.element('F').data.coords, [0, 0.5], atol=1e-9)


# ── 06 geometric constructors ────────────────────────────────────────

def test_example_06_ellipse_from_foci():
    s = _scene()
    s.putCode('''
        F1 = Point(-3, 0)
        F2 = Point(3, 0)
        ell = Ellipse(F1, F2, 5)
        hyp = Hyperbola(F1, F2, 2)
    ''')
    assert s.element('ell').data.type == ConicType.ELLIPSE
    assert s.element('hyp').data.type == ConicType.HYPERBOLA


def test_example_06_parabola_from_focus_directrix():
    s = _scene()
    s.putCode('''
        F = Point(0, 1)
        A = Point(-5, -1)
        B = Point(5, -1)
        d = Line(A, B)
        p = Parabola(F, d)
    ''')
    assert s.element('p').data.type == ConicType.PARABOLA
    params = s.element('p').data.as_parabola()
    assert np.allclose(params['vertex'], [0, 0], atol=1e-9)


# ── 07 conic through 5 points ────────────────────────────────────────

def test_example_07_conic_through_5():
    s = _scene()
    s.putCode('''
        A = Point(3, 0)
        B = Point(0, 2)
        C = Point(-3, 0)
        D = Point(0, -2)
        E = Point(2.294, 1.288)
        ell = Conic(A, B, C, D, E)
    ''')
    ell = s.element('ell')
    assert ell is not None
    assert ell.data.type == ConicType.ELLIPSE


# ── 08 tangent/polar ─────────────────────────────────────────────────

def test_example_08_tangents_from_external():
    s = _scene()
    s.putCode('''
        c = Conic("x^2 + y^2 = 1")
        P = Point(2.5, 1.0)
        polar_line = Polar(P, c)
        t = Tangent(P, c)
    ''')
    polar = s.element('polar_line')
    assert polar is not None
    assert isinstance(polar.data, Line)


def test_example_08_tangent_at_point():
    s = _scene()
    s.putCode('''
        e = Conic("x^2 / 4 + y^2 = 1")
        P = Point(1.414213, 0.707107)
        t = Tangent(P, e)
    ''')
    tangent = s.element('t')
    assert tangent is not None
    assert isinstance(tangent.data, Line)


# ── 09 DSL sugar ─────────────────────────────────────────────────────

def test_example_09_dsl_sugar_equivalent():
    s = _scene()
    s.putCode('long_form = Function("y = x^2 + 1")')
    s.putCode('sugar_x(x) = x^2 + 1')
    s.putCode('sugar_t(t) = t^2 + 1')
    for name in ('long_form', 'sugar_x', 'sugar_t'):
        assert s.element(name) is not None
        assert np.isclose(s.element(name).data(2), 5.0)
        assert np.isclose(s.element(name).data(0), 1.0)
