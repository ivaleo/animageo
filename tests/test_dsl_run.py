"""Phase 1 — end-to-end tests for the exec DSL engine."""

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.parsers import dsl
from animageo.parsers.dsl.transform import DSLSyntaxError


# ── Basic parity with legacy parser ──────────────────────────────

class TestBasic:
    def test_single_point(self):
        c = Construction()
        dsl.run(c, "A = Point(3, 4)")
        assert c.element("A") is not None
        assert np.allclose(c.element("A").data.coords, [3, 4])

    def test_two_points_and_midpoint(self):
        c = Construction()
        dsl.run(c, "A = Point(0, 0)\nB = Point(4, 0)\nM = Midpoint(A, B)")
        assert np.allclose(c.element("M").data.coords, [2, 0])

    def test_segment(self):
        c = Construction()
        dsl.run(c, "A = Point(0, 0)\nB = Point(3, 4)\ns = Segment(A, B)")
        assert c.element("s") is not None
        assert np.isclose(c.element("s").data.length, 5.0)

    def test_nested_expression(self):
        c = Construction()
        dsl.run(c, "M = Midpoint(Point(0, 0), Point(4, 0))")
        assert np.allclose(c.element("M").data.coords, [2, 0])
        # The inner Points are phantom names.
        assert c.element("M") is not None

    def test_trilinear(self):
        # Auto-discovered command: Trilinear(A, B, C, 1, 1, 1) → incenter.
        c = Construction()
        dsl.run(c, "A = Point(0, 0)\nB = Point(4, 0)\nC = Point(0, 3)\n"
                   "I = Trilinear(A, B, C, 1, 1, 1)")
        assert np.allclose(c.element("I").data.coords, [1, 1])

    def test_tier_a_b_commands(self):
        # Smoke-test the auto-discovered Tier A/B commands end-to-end.
        c = Construction()
        dsl.run(c, "\n".join([
            "A = Point(0, 0)",
            "B = Point(4, 0)",
            "C = Point(2, 6)",
            "sl = Slope(Line(A, C))",         # 3.0
            "u = UnitVector(Line(A, B))",     # unit
            "cp = ClosestPoint(Line(A, B), Point(2, 5))",   # [2, 0]
            "D = Dilate(C, 2, A)",            # [4, 12]
        ]))
        assert np.isclose(c.var("sl").data.value, 3.0)
        assert np.isclose(np.linalg.norm(c.element("u").data.direction), 1.0)
        assert np.allclose(c.element("cp").data.coords, [2, 0])
        assert np.allclose(c.element("D").data.coords, [4, 12])

    def test_tier_c_tangent(self):
        # Tangent(Line, Conic) → 2 parallel tangents; Tangent(Point, Function).
        c = Construction()
        dsl.run(c, "\n".join([
            "k = Conic(1, 1, -1, 0, 0, 0)",           # unit circle
            "g = Line(Point(0, 0), Point(1, 0))",     # x-axis direction
            "t1, t2 = Tangent(g, k)",                 # y = ±1
            "tf = Tangent(Point(1, 0), Function(\"y = x^2\"))",
        ]))
        offs = sorted(
            (l.data.offset if l.data.normal[1] > 0 else -l.data.offset)
            for l in (c.element("t1"), c.element("t2")))
        assert np.allclose(offs, [-1, 1])
        assert c.element("tf").data.contains(np.array([2.0, 3.0]))

    def test_tier_c_tangent_circles(self):
        # Tangent(Circle, Circle) → 4 common tangents for separated circles.
        c = Construction()
        dsl.run(c, "\n".join([
            "a = Circle(Point(0, 0), 1)",
            "b = Circle(Point(6, 0), 2)",
            "t1, t2, t3, t4 = Tangent(a, b)",
        ]))
        for nm in ("t1", "t2", "t3", "t4"):
            line = c.element(nm).data
            nn = np.linalg.norm(line.normal)
            assert np.isclose(abs(np.dot(line.normal, [0, 0]) - line.offset) / nn, 1)
            assert np.isclose(abs(np.dot(line.normal, [6, 0]) - line.offset) / nn, 2)


# ── Python control flow: the whole point of Path B ───────────────

class TestLoops:
    def test_for_creates_multiple_points(self):
        c = Construction()
        dsl.run(c, "for i in range(3):\n    p = Point(i, 0)")
        # Names: p, p_2, p_3
        assert np.allclose(c.element("p").data.coords, [0, 0])
        assert np.allclose(c.element("p_2").data.coords, [1, 0])
        assert np.allclose(c.element("p_3").data.coords, [2, 0])

    def test_loop_with_explicit_names(self):
        c = Construction()
        code = (
            "for i in range(3):\n"
            "    p = Point(i, 0, name=f'P{i}')"
        )
        dsl.run(c, code)
        # Need f-strings — but SAFE_BUILTINS has str. f-string is a Python
        # expression, not a builtin call, so it should work.
        assert c.element("P0") is not None
        assert c.element("P1") is not None
        assert c.element("P2") is not None

    def test_condition_controls_creation(self):
        c = Construction()
        code = (
            "for i in range(5):\n"
            "    if i % 2 == 0:\n"
            "        p = Point(i, 0)"
        )
        dsl.run(c, code)
        # Even iterations: i=0, 2, 4 → p, p_2, p_3
        assert c.element("p") is not None
        assert c.element("p_2") is not None
        assert c.element("p_3") is not None
        assert c.element("p_4") is None


class TestFunctions:
    def test_def_with_name_kwarg(self):
        c = Construction()
        code = (
            "def triangle(prefix, side):\n"
            "    A = Point(0, 0, name=f'{prefix}_A')\n"
            "    B = Point(side, 0, name=f'{prefix}_B')\n"
            "    return A, B\n"
            "triangle('t1', 3)\n"
            "triangle('t2', 5)"
        )
        dsl.run(c, code)
        assert np.allclose(c.element("t1_A").data.coords, [0, 0])
        assert np.allclose(c.element("t1_B").data.coords, [3, 0])
        assert np.allclose(c.element("t2_A").data.coords, [0, 0])
        assert np.allclose(c.element("t2_B").data.coords, [5, 0])

    def test_def_without_explicit_names_uniquifies(self):
        # Body of def is loop-scope, so calling twice must create unique
        # elements. Each def call runs the body — loop counter on
        # Construction.naming_counters advances.
        c = Construction()
        code = (
            "def make():\n"
            "    A = Point(1, 0)\n"
            "    return A\n"
            "make()\n"
            "make()"
        )
        dsl.run(c, code)
        # First call: A. Second: A_2.
        assert c.element("A") is not None
        assert c.element("A_2") is not None


# ── Kwargs ───────────────────────────────────────────────────────

class TestKwargs:
    def test_name_kwarg_sets_element_name(self):
        c = Construction()
        dsl.run(c, "p = Point(1, 2, name='MyPoint')")
        # Construction has MyPoint, not p.
        assert c.element("MyPoint") is not None
        assert c.element("p") is None

    def test_name_collision_raises(self):
        c = Construction()
        code = (
            "A = Point(0, 0)\n"
            "B = Point(1, 1, name='A')"
        )
        with pytest.raises(ValueError, match="already in use"):
            dsl.run(c, code)


# ── Field access via ElementProxy ────────────────────────────────

class TestFieldAccess:
    def test_point_data_coord_access(self):
        c = Construction()
        # Use a captured proxy in a conditional — reads must be live.
        code = (
            "A = Point(3, 4)\n"
            "x_val = A.coords[0]\n"
            "y_val = A.coords[1]\n"
        )
        dsl.run(c, code)
        assert c.var("x_val").data == 3.0
        assert c.var("y_val").data == 4.0


# ── Forbidden constructs ─────────────────────────────────────────

class TestForbidden:
    def test_import_silently_dropped(self):
        """Imports are IDE-only hints and dropped at transform time."""
        c = Construction()
        # Should not raise — transform drops the import.
        dsl.run(c, "import math\nA = Point(0, 0)")
        assert c.element("A") is not None

    def test_aug_assign_raises(self):
        c = Construction()
        with pytest.raises(DSLSyntaxError, match="augmented"):
            dsl.run(c, "x = 1\nx += 1")


# ── show=False parity with legacy ────────────────────────────────

class TestShow:
    def test_show_false_hides_top_level(self):
        c = Construction()
        dsl.run(c, "A = Point(0, 0)\nB = Point(1, 1)", show=False)
        assert c.element("A").visible is False
        assert c.element("B").visible is False

    def test_show_true_default(self):
        c = Construction()
        dsl.run(c, "A = Point(0, 0)")
        assert c.element("A").visible is True


# ── Tuple unpack (Intersect / Polygon multi-output) ──────────────

class TestTupleUnpack:
    def test_polygon_unpack(self):
        c = Construction()
        code = (
            "A = Point(0, 0)\n"
            "B = Point(4, 0)\n"
            "C = Point(0, 3)\n"
            "p, s1, s2, s3 = Polygon(A, B, C)"
        )
        dsl.run(c, code)
        assert c.element("p") is not None
        assert c.element("s1") is not None
        assert c.element("s2") is not None
        assert c.element("s3") is not None
