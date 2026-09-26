"""Transformations of formula curves: Conic, Function, ImplicitCurve.

GeoGebra applies Dilate / Translate / Reflect / Rotate to conics and graphs;
with a slider as the factor (``Dilate(f, a, O)``) the image must follow it.
"""
import numpy as np
import pytest

from animageo.geo.lib_commands import (
    dilate_Kip, dilate_Fip, dilate_Iip, dilate_Fi, dilate_Kmp,
    translate_Kv, translate_Fv, translate_Iv,
    reflect_Kp, reflect_Fp, reflect_Kl, rotate_KAp, rotate_Kip,
)
from animageo.geo.lib_conic import Conic
from animageo.geo.lib_elements import Point, Vector, Line
from animageo.geo.lib_function import Function
from animageo.geo.lib_implicit import ImplicitCurve
from animageo.geo.lib_vars import AngleSize, Measure

O = Point([0, 0])
C = Point([1, 1])


def parabola():
    return Conic.from_string('y = x^2')


def test_dilate_conic_about_origin():
    k = dilate_Kip(parabola(), 2.0, O)          # (x, y) -> (2x, 2y): y = x²/2
    assert k.evaluate(2.0, 2.0) == pytest.approx(0.0)


def test_dilate_conic_about_point_and_measure_factor():
    k = dilate_Kmp(parabola(), Measure(2.0, 0), C)
    # (0, 0) on the parabola -> C + 2((0, 0) - C) = (-1, -1)
    assert k.evaluate(-1.0, -1.0) == pytest.approx(0.0)


def test_dilate_zero_factor_is_undefined():
    assert dilate_Kip(parabola(), 0.0, O) is None
    assert dilate_Fip(Function.from_string('y = x^2'), 0.0, O) is None


def test_dilate_function():
    g = dilate_Fip(Function.from_string('y = x^2'), 2.0, O)
    assert g(2.0) == pytest.approx(2.0)
    g = dilate_Fi(Function.from_string('y = x^2'), -1.0)
    assert g(1.0) == pytest.approx(-1.0)


def test_dilate_function_keeps_input_unchanged():
    f = Function.from_string('y = x^2')
    dilate_Fip(f, 3.0, C)
    assert f(2.0) == pytest.approx(4.0)


def test_dilate_function_maps_explicit_domain():
    f = Function('x**2', domain=(0.0, 1.0))
    assert dilate_Fip(f, -2.0, O).explicit_domain == (-2.0, 0.0)


def test_dilate_implicit():
    h = dilate_Iip(ImplicitCurve.from_string('x^2 + y^2 = 1'), 2.0, O)
    assert h(2.0, 0.0) == pytest.approx(0.0)


def test_translate_curves():
    v = Vector([[0, 0], [1, 2]])
    assert translate_Kv(parabola(), v).evaluate(1.0, 2.0) == pytest.approx(0.0)
    assert translate_Fv(Function.from_string('y = x^2'), v)(1.0) == pytest.approx(2.0)
    assert translate_Iv(ImplicitCurve.from_string('x^2 + y^2 = 1'), v)(1.0, 3.0) == pytest.approx(0.0)


def test_reflect_curves_in_point():
    assert reflect_Kp(parabola(), O).evaluate(1.0, -1.0) == pytest.approx(0.0)
    assert reflect_Fp(Function.from_string('y = x^2'), O)(1.0) == pytest.approx(-1.0)


def test_reflect_conic_in_line():
    k = reflect_Kl(parabola(), Line([0, 1], 0))   # mirror in y = 0
    assert k.evaluate(1.0, -1.0) == pytest.approx(0.0)
    k = reflect_Kl(parabola(), Line([0, 1], 1))   # mirror in y = 1: (0,0) -> (0,2)
    assert k.evaluate(0.0, 2.0) == pytest.approx(0.0)


def test_rotate_conic():
    k = rotate_KAp(parabola(), AngleSize(np.pi / 2), O)   # (1, 1) -> (-1, 1)
    assert k.evaluate(-1.0, 1.0) == pytest.approx(0.0)
    k = rotate_Kip(parabola(), np.pi, C)                  # (0, 0) -> (2, 2)
    assert k.evaluate(2.0, 2.0) == pytest.approx(0.0)
