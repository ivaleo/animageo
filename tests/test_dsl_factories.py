"""Phase 2 — auto-discovered factories and FactoryDict behaviour."""

import pytest

from animageo.geo.construction import Construction
from animageo.parsers import dsl
from animageo.parsers.dsl.namespace import (
    FactoryDict,
    _can_dispatch,
    _camel_to_snake,
    build_namespace,
)


class TestCanDispatch:
    def test_point_dispatchable(self):
        assert _can_dispatch("Point")

    def test_midpoint_dispatchable(self):
        assert _can_dispatch("Midpoint")

    def test_intersect_dispatchable(self):
        assert _can_dispatch("Intersect")

    def test_polygon_dispatchable(self):
        assert _can_dispatch("Polygon")

    def test_conic_dispatchable(self):
        assert _can_dispatch("Conic")

    def test_function_dispatchable(self):
        assert _can_dispatch("Function")

    def test_implicit_curve_dispatchable(self):
        assert _can_dispatch("ImplicitCurve")

    def test_are_collinear_dispatchable(self):
        assert _can_dispatch("AreCollinear")

    def test_unknown_name_rejected(self):
        assert not _can_dispatch("Nonsense")

    def test_helper_names_rejected(self):
        # strCommand is a helper, not a command — different casing anyway.
        assert not _can_dispatch("StrCommand")


class TestCamelToSnake:
    def test_single_word(self):
        assert _camel_to_snake("Point") == "point"

    def test_two_words(self):
        assert _camel_to_snake("Midpoint") == "midpoint"

    def test_are_collinear(self):
        assert _camel_to_snake("AreCollinear") == "are_collinear"

    def test_implicit_curve(self):
        assert _camel_to_snake("ImplicitCurve") == "implicit_curve"


class TestFactoryDict:
    def test_common_factories_pre_seeded(self):
        # Phase 4: common factories (discovered at module load) are
        # seeded into every ns up-front so direct import works.
        c = Construction()
        ns = build_namespace(c)
        assert "Point" in ns
        assert callable(ns["Point"])

    def test_missing_creates_factory_for_undiscovered_command(self):
        # Hand-crafted empty dict → __missing__ path.
        from animageo.parsers.dsl.namespace import FactoryDict
        d = FactoryDict()
        assert "Point" not in d
        factory = d["Point"]
        assert callable(factory)
        assert "Point" in d  # cached after first lookup

    def test_missing_raises_for_unknown(self):
        c = Construction()
        ns = build_namespace(c)
        with pytest.raises(KeyError):
            _ = ns["NotACommand"]

    def test_missing_raises_for_lowercase(self):
        c = Construction()
        ns = build_namespace(c)
        with pytest.raises(KeyError):
            _ = ns["midpoint"]  # lowercase — not a factory

    def test_missing_raises_for_dunder(self):
        c = Construction()
        ns = build_namespace(c)
        with pytest.raises(KeyError):
            _ = ns["__spam__"]


class TestUnknownNameRules:
    """Unknown names: lowercase auto-create (forward ref), uppercase error."""

    def test_unknown_lowercase_auto_creates_var(self):
        # ``scene.loadCode('scene.py')`` references ``x`` which
        # ``scene.addVar('x', 115)`` will fill later.
        c = Construction()
        dsl.run(c, "y = x * 2")
        # Forward-ref Var for x exists; y is Command('Mult', [x, 2]).
        assert c.var("x") is not None

    def test_unknown_camelcase_still_errors(self):
        # CamelCase typo for a command name should surface clearly.
        # ``Nonsense`` isn't dispatchable, isn't in construction;
        # calling it returns ``ElementProxy`` not-callable at runtime.
        c = Construction()
        with pytest.raises((NameError, TypeError)):
            dsl.run(c, "A = Nonsense(0, 0)")


class TestBreadthOfCommands:
    """Smoke-test factories that weren't in Phase 1's hand list."""

    def test_are_collinear(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "B = Point(1, 1)\n"
            "C = Point(2, 2)\n"
            "flag = AreCollinear(A, B, C)",
        )
        var = c.var("flag")
        assert var is not None

    def test_distance(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "B = Point(3, 4)\n"
            "d = Distance(A, B)",
        )
        var = c.var("d")
        assert var is not None
        # Distance returns a Measure; .value is its scalar value.
        assert abs(var.data.value - 5.0) < 1e-9

    def test_circle(self):
        c = Construction()
        dsl.run(
            c,
            "O = Point(0, 0)\n"
            "A = Point(1, 0)\n"
            "circ = Circle(O, A)",
        )
        assert c.element("circ") is not None

    def test_line(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "B = Point(1, 1)\n"
            "L = Line(A, B)",
        )
        assert c.element("L") is not None


class TestIntersectKeywordIndex:
    BASE = (
        "O = Point(0, 0)\n"
        "A = Point(1, 0)\n"
        "B = Point(-2, 0)\n"
        "C = Point(2, 0)\n"
        "circle = Circle(O, A)\n"
        "line = Line(B, C)\n"
    )

    def test_keyword_index_runs(self):
        c = Construction()
        dsl.run(c, self.BASE + "P = Intersect(line, circle, index=1)")
        assert c.element("P") is not None
        assert c.element("P").data is not None

    def test_keyword_index_matches_positional_index(self):
        c = Construction()
        dsl.run(
            c,
            self.BASE
            + "P_keyword = Intersect(line, circle, index=1)\n"
            + "P_positional = Intersect(line, circle, 1)\n",
        )
        assert c.element("P_keyword").data.coords.tolist() == pytest.approx(
            c.element("P_positional").data.coords.tolist()
        )

    def test_zero_index_keeps_legacy_first_point_behavior(self):
        c = Construction()
        dsl.run(
            c,
            self.BASE
            + "P_zero = Intersect(line, circle, index=0)\n"
            + "P_one = Intersect(line, circle, index=1)\n",
        )
        assert c.element("P_zero").data.coords.tolist() == pytest.approx(
            c.element("P_one").data.coords.tolist()
        )

    def test_multi_output_intersection_still_works(self):
        c = Construction()
        dsl.run(c, self.BASE + "P1, P2 = Intersect(line, circle)")
        assert c.element("P1").data is not None
        assert c.element("P2").data is not None

    def test_unique_intersection_still_works_without_index(self):
        c = Construction()
        dsl.run(
            c,
            self.BASE
            + "V = Point(0, 1)\n"
            + "x_axis = Line(O, A)\n"
            + "y_axis = Line(O, V)\n"
            + "D = Intersect(x_axis, y_axis)\n",
        )
        assert c.element("D").data is not None
        assert c.element("D").data.coords.tolist() == pytest.approx([0, 0])

    def test_unsupported_keyword_still_fails_clearly(self):
        c = Construction()
        with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
            dsl.run(c, self.BASE + "P = Intersect(line, circle, foo=1)")


class TestHelpersInNamespace:
    def test_style_batch(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "B = Point(1, 1)\n"
            "style(A, B, stroke='#ff0000', size=10)",
        )
        assert c.element("A").style["stroke"] == "#ff0000"
        assert c.element("A").style["size"] == 10
        assert c.element("B").style["stroke"] == "#ff0000"

    def test_hide_show(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "hide(A)",
        )
        assert c.element("A").visible is False

        c2 = Construction()
        dsl.run(
            c2,
            "A = Point(0, 0)\n"
            "hide(A)\n"
            "show(A)",
        )
        assert c2.element("A").visible is True


class TestMathExposure:
    def test_sqrt_in_expression(self):
        c = Construction()
        dsl.run(c, "A = Point(sqrt(2), sqrt(3))")
        import math
        import numpy as np
        assert np.isclose(c.element("A").data.coords[0], math.sqrt(2))
        assert np.isclose(c.element("A").data.coords[1], math.sqrt(3))

    def test_pi_constant(self):
        c = Construction()
        dsl.run(c, "A = Point(pi, 0)")
        import math
        assert abs(c.element("A").data.coords[0] - math.pi) < 1e-9

    def test_sin_cos(self):
        c = Construction()
        dsl.run(c, "A = Point(cos(0), sin(0))")
        assert c.element("A").data.coords.tolist() == [1.0, 0.0]


class TestSandboxing:
    def test_open_not_available(self):
        c = Construction()
        with pytest.raises(NameError, match="open"):
            dsl.run(c, "f = open('/etc/passwd')")

    def test_eval_not_available(self):
        c = Construction()
        with pytest.raises(NameError, match="eval"):
            dsl.run(c, "x = eval('1 + 1')")

    def test_exec_not_available(self):
        c = Construction()
        with pytest.raises(NameError, match="exec"):
            dsl.run(c, "exec('x = 1')")
