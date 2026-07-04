"""Phase 1 — AST transformer tests."""

import ast

import pytest

from animageo.parsers.dsl.transform import DSLSyntaxError, transform


def _dump(module: ast.Module) -> str:
    return ast.unparse(module)


class TestBasicRewrite:
    def test_simple_assign_wrapped_with_reg(self):
        out = _dump(transform("A = Point(0, 0)"))
        assert "__reg__('A', Point(0, 0))" in out

    def test_tuple_unpack_wrapped_with_reg_tuple(self):
        out = _dump(transform("A, B = Intersect(c, L)"))
        assert "__reg_tuple__(('A', 'B')" in out
        # Transform also injects _outputs=N so the factory allocates
        # the right number of phantom output names.
        assert "_outputs=2" in out

    def test_list_unpack_like_tuple(self):
        out = _dump(transform("[A, B] = Intersect(c, L)"))
        assert "__reg_tuple__(('A', 'B')" in out
        assert "_outputs=2" in out

    def test_multiple_top_level_assigns(self):
        out = _dump(transform("A = Point(0, 0)\nB = Point(1, 1)"))
        assert "__reg__('A'" in out
        assert "__reg__('B'" in out


class TestLoopScope:
    def test_for_uses_reg_loop(self):
        out = _dump(transform("for i in range(3):\n    p = Point(i, 0)"))
        assert "__reg_loop__('p'" in out
        assert "__reg__(" not in out  # no top-level assign here

    def test_while_uses_reg_loop(self):
        out = _dump(transform("while True:\n    p = Point(0, 0)\n    break"))
        assert "__reg_loop__('p'" in out

    def test_def_uses_reg_loop(self):
        out = _dump(transform("def make():\n    A = Point(0, 0)\n    return A"))
        assert "__reg_loop__('A'" in out

    def test_nested_for_stays_loop(self):
        out = _dump(transform(
            "for i in range(3):\n    for j in range(3):\n        p = Point(i, j)"
        ))
        assert "__reg_loop__('p'" in out
        assert "__reg__(" not in out

    def test_top_level_before_loop_remains_reg(self):
        out = _dump(transform(
            "A = Point(0, 0)\nfor i in range(3):\n    p = Point(i, 0)"
        ))
        assert "__reg__('A'" in out
        assert "__reg_loop__('p'" in out

    def test_loop_tuple_unpack(self):
        out = _dump(transform(
            "for i in range(3):\n    a, b = Intersect(c, L)"
        ))
        assert "__reg_loop_tuple__(('a', 'b')" in out


class TestForbidden:
    # Imports are no longer *forbidden* — they're dropped silently
    # at transform time. See TestIDEStubs for the expected behavior.
    pass


class TestIDEStubs:
    """IDE-hint imports are dropped at transform time — runtime uses namespace."""

    def test_typing_import_dropped(self):
        out = _dump(transform("from typing import TYPE_CHECKING\nA = 1"))
        assert "from typing import" not in out
        assert "__reg__('A', 1)" in out

    def test_future_import_dropped(self):
        out = _dump(transform("from __future__ import annotations\nA = 1"))
        assert "from __future__ import" not in out

    def test_arbitrary_from_import_dropped(self):
        # User can star-import any stub module without a TYPE_CHECKING guard.
        out = _dump(transform("from scene10_stubs import *\nA = Point(0, 0)"))
        assert "import" not in out
        assert "__reg__('A', Point(0, 0))" in out

    def test_plain_import_dropped(self):
        out = _dump(transform("import math\nA = 1"))
        assert "import math" not in out
        assert "__reg__('A', 1)" in out

    def test_animageo_dsl_star_import_dropped(self):
        out = _dump(transform("from animageo.dsl import *\nA = Point(0, 0)"))
        assert "import" not in out

    def test_global_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="global"):
            transform("def f():\n    global x\n    x = 1")

    def test_nonlocal_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="nonlocal"):
            transform(
                "def f():\n    x = 1\n    def g():\n        nonlocal x\n        x = 2"
            )

    def test_aug_assign_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="augmented"):
            transform("A += 1")

    def test_walrus_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="walrus"):
            transform("if (x := 5) > 0: pass")

    def test_annotated_assign_with_value_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="annotated"):
            transform("A: int = 5")

    def test_bare_annotation_dropped(self):
        # `x: int` with no value is a no-op type hint; we just drop it.
        out = _dump(transform("x: int"))
        assert "x" not in out or out.strip() == ""

    def test_chained_assign_forbidden(self):
        with pytest.raises(DSLSyntaxError, match="chained"):
            transform("A = B = Point(0, 0)")


class TestPreserved:
    def test_if_statement_unchanged(self):
        out = _dump(transform("if x > 0:\n    pass"))
        assert "if x > 0" in out

    def test_attribute_assignment_passed_through(self):
        out = _dump(transform("A.style.stroke = '#f00'"))
        assert "__reg" not in out
        assert "A.style.stroke" in out

    def test_subscript_assignment_passed_through(self):
        out = _dump(transform("arr[0] = 5"))
        assert "__reg" not in out

    def test_function_call_without_assign_untouched(self):
        out = _dump(transform("hide(A, B)"))
        assert "hide(A, B)" in out
        assert "__reg" not in out

    def test_return_preserved(self):
        out = _dump(transform("def f():\n    return 42"))
        assert "return 42" in out
