"""Tests for ``ElementProxy`` arithmetic operators.

``A - B``, ``-A``, ``A * 2`` etc. register Sub/USub/Mult commands in
the active Construction, returning a proxy for the new phantom.
Matches the legacy parser's ast.BinOp handling.
"""

import numpy as np

from animageo.geo.construction import Construction
from animageo.parsers import dsl


class TestBinaryOps:
    def test_point_minus_point_gives_vector(self):
        c = Construction()
        dsl.run(c, """
            P = Point(3, 4)
            Q = Point(0, 0)
            V = P - Q
        """)
        # The result should be a Point-like offset (depends on
        # lib_commands.sub_pp implementation).
        assert c.element("V") is not None

    def test_point_plus_point(self):
        c = Construction()
        dsl.run(c, """
            A = Point(1, 2)
            B = Point(3, 4)
            S = A + B
        """)
        assert c.element("S") is not None

    def test_scalar_times_proxy(self):
        c = Construction()
        dsl.run(c, """
            P = Point(2, 3)
            Q = 2 * P
        """)
        assert c.element("Q") is not None

    def test_proxy_divided_by_scalar(self):
        c = Construction()
        dsl.run(c, """
            P = Point(4, 8)
            Q = P / 2
        """)
        assert c.element("Q") is not None


class TestUnaryOps:
    def test_negation(self):
        c = Construction()
        dsl.run(c, """
            P = Point(3, 4)
            N = -P
        """)
        assert c.element("N") is not None

    def test_abs(self):
        c = Construction()
        # abs() on a scalar-carrying var works via Command('Abs', ...).
        dsl.run(c, """
            x = 3
            y = abs(x)
        """)
        # y is a Python local bound to the phantom; construction var exists.
        assert c.var("y") is not None


class TestArithmeticSnapshots:
    """Arithmetic operators produce the expected geometric result.

    (Previously parity tests vs the legacy parser; after short_parser
    removal these are direct snapshot assertions.)"""

    def test_sub_gives_expected_point(self):
        c = Construction()
        dsl.run(c, "A = Point(3, 4)\nB = Point(1, 1)\nD = A - B")
        assert np.allclose(c.element("D").data.coords, [2, 3])

    def test_neg_gives_expected_point(self):
        c = Construction()
        dsl.run(c, "A = Point(3, 4)\nN = -A")
        assert np.allclose(c.element("N").data.coords, [-3, -4])
