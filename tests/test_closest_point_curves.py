"""ClosestPoint of a conic and of a graph in the classic library
(``closest_point_Kp``, ``closest_point_Fp``): the projection of the kernel
(``animageo/native/kernel/paths.py``)."""
import math

import numpy as np
import pytest

from animageo.geo.lib_commands import COMMAND_REGISTRY, closest_point_Fp, closest_point_Kp
from animageo.geo.lib_conic import Conic
from animageo.geo.lib_elements import Point
from animageo.geo.lib_function import Function


def near(point, want):
    assert point is not None
    assert np.allclose(point.coords, want, atol=1e-9), (point.coords, want)


def test_the_signatures_are_commands():
    assert {'closest_point_Kp', 'closest_point_Fp'} <= set(COMMAND_REGISTRY)


def test_ellipse():
    k = Conic.from_string('x^2/25 + y^2/9 = 1')
    near(closest_point_Kp(k, Point([6, 0])), [5, 0])
    near(closest_point_Kp(k, Point([0, -7])), [0, -3])
    q = 5 / 16
    near(closest_point_Kp(k, Point([1, 0])), [5 * q, 3 * math.sqrt(1 - q * q)])


def test_a_turned_ellipse_and_a_circle():
    k = Conic.from_string('x^2/9 + y^2/25 = 1')        # the major axis along y
    near(closest_point_Kp(k, Point([0, 7])), [0, 5])
    c = Conic.from_string('x^2 + y^2 = 4')
    near(closest_point_Kp(c, Point([3, 4])), [1.2, 1.6])


def test_hyperbola_takes_the_nearest_branch():
    h = Conic.from_string('x^2/9 - y^2/16 = 1')
    near(closest_point_Kp(h, Point([5, 0])), [3, 0])
    near(closest_point_Kp(h, Point([-5, 0])), [-3, 0])


def test_parabola():
    q = Conic.from_string('y = x^2/4')
    near(closest_point_Kp(q, Point([0, -3])), [0, 0])
    p = closest_point_Kp(q, Point([0, 5]))
    assert abs(p.coords[1] - 3) < 1e-9 and abs(abs(p.coords[0]) - 2 * math.sqrt(3)) < 1e-9


def test_a_degenerate_conic_has_none():
    assert closest_point_Kp(Conic.from_string('x^2 - y^2 = 0'), Point([1, 2])) is None


def test_graph():
    f = Function.from_string('y = x^2')
    p = closest_point_Fp(f, Point([0, 3]))
    assert p.coords[1] == pytest.approx(2.5, abs=1e-7) and abs(p.coords[0]) == pytest.approx(math.sqrt(2.5), abs=1e-7)
    near(closest_point_Fp(f, Point([2, 4])), [2, 4])


def test_graph_stays_in_its_domain():
    f = Function('y = x^2', domain=(-1, 2))
    near(closest_point_Fp(f, Point([5, 5])), [2, 4])
    near(closest_point_Fp(f, Point([-5, 0])), [-1, 1])


def test_a_graph_without_a_value_has_none():
    f = Function('y = sqrt(x)', domain=(-5, -1))
    assert closest_point_Fp(f, Point([0, 0])) is None
