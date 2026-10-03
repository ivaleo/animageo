"""Classic geometry fixes of 1.8.1a1: a circle through collinear points and
an angle bisector with a degenerate side are undefined without an error."""
import logging
import warnings

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command, angular_bisector_ppp, circle_ppp
from animageo.geo.lib_elements import Element, Point


def P(x, y):
    return Point(np.array([x, y], dtype=float))


def construction(points, *commands):
    c = Construction(seed=0)
    for name, xy in points.items():
        c.add(Element(name, Point(xy)))
    for cmd in commands:
        c.add_and_build(cmd)
    return c


class TestCirclePPP:
    @pytest.mark.parametrize('pts', [
        ((0, 0), (1, 1), (3, 3)),           # collinear
        ((0, 0), (0, 0), (2, 1)),           # two coincide
        ((1, 2), (1, 2), (1, 2)),           # all coincide
    ])
    def test_degenerate_is_none(self, pts):
        assert circle_ppp(*(P(*p) for p in pts)) is None

    def test_general_circle(self):
        c = circle_ppp(P(0, 0), P(4, 0), P(0, 3))
        assert tuple(c.center) == pytest.approx((2.0, 1.5)) and c.radius == pytest.approx(2.5)

    def test_no_error_in_the_log(self, caplog):
        with caplog.at_level(logging.WARNING):
            c = construction({'A': (0, 0), 'B': (1, 1), 'C': (3, 3)}, Command('Circle', ['A', 'B', 'C'], ['k']))
        assert c.element('k').data is None
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestAngularBisectorPPP:
    @pytest.mark.parametrize('pts', [
        ((0, 0), (0, 0), (2, 1)),           # first side has zero length
        ((3, 1), (2, 5), (2, 5)),           # second side has zero length
        ((1, 1), (1, 1 + 1e-14), (4, 2)),   # zero up to rounding
    ])
    def test_degenerate_side_is_none(self, pts):
        with warnings.catch_warnings():
            warnings.simplefilter('error')      # no division by zero on the way
            assert angular_bisector_ppp(*(P(*p) for p in pts)) is None

    def test_general_bisector(self):
        line = angular_bisector_ppp(P(4, 0), P(0, 0), P(0, 4))
        n = line.normal / np.linalg.norm(line.normal)
        assert abs(float(np.dot(n, [1.0, 1.0]))) == pytest.approx(0.0, abs=1e-12)
        assert float(line.offset) == pytest.approx(0.0, abs=1e-12)
