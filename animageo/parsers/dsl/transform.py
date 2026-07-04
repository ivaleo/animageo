"""AST transformer for the exec-based DSL.

Rewrites user code so every Construction-level binding routes through
a registrar (see :mod:`animageo.parsers.dsl.registrar`). Plain Python
control flow (``for``, ``if``, ``def``, comprehensions, ``return``,
attribute writes to existing proxies) is preserved untouched.

Transformations
---------------

*   ``A = expr``
       → ``A = __reg__("A", expr)``        (top level)
       → ``A = __reg_loop__("A", expr)``   (inside For/While/Def/Lambda)

*   ``A, B = expr``
       → ``(A, B) = __reg_tuple__(("A","B"), expr)``
       → ``(A, B) = __reg_loop_tuple__(("A","B"), expr)``

Forbidden constructs (raise :class:`DSLSyntaxError`)
----------------------------------------------------

* ``import`` / ``from … import``
* ``global`` / ``nonlocal``
* ``A += expr``, ``A: T = expr`` for Construction-bound names —
  can't meaningfully be wrapped; raise with clear message
* ``(A := expr)`` walrus — same reason
"""

from __future__ import annotations

import ast
from typing import Optional


class DSLSyntaxError(SyntaxError):
    """Raised when user DSL code uses a forbidden construct."""


_LOOP_SCOPE_NODES: tuple = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)

# All top-level imports are treated as IDE-only hints and dropped at
# transform time (see ``visit_Import``/``visit_ImportFrom``). Runtime
# names come from the exec namespace, not from Python's import system.


class _Rewriter(ast.NodeTransformer):
    """Wraps every top-level ``Assign`` with a registrar call.

    Tracks a scope depth so the transformer knows which registrar to
    use (``__reg__`` at module level, ``__reg_loop__`` inside a
    loop-like construct).
    """

    def __init__(self) -> None:
        self._loop_depth = 0

    # ── forbidden nodes ──────────────────────────────────────────

    def visit_Import(self, node: ast.Import):
        # All top-level imports are dropped at transform time — they
        # exist purely for IDE static analysis (from scene_stubs
        # import *, from animageo.dsl import *, etc.). Runtime names
        # come from the exec namespace: built-in factories, math
        # exports, and live construction elements via
        # ``FactoryDict.__missing__``. Imports that reach the
        # exec'd code would need ``__import__`` in SAFE_BUILTINS
        # anyway, which we deliberately withhold.
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom):
        return None

    def visit_If(self, node: ast.If):
        # Normal If — counts as a scope (for uniformity with For/While).
        # ``if TYPE_CHECKING:`` / ``if False:`` are still supported
        # but no longer special-cased: their bodies transform like
        # regular code, and the imports inside would be dropped too.
        return self._visit_scoped(node)

    def visit_Global(self, node: ast.Global):
        raise DSLSyntaxError.from_node(
            node, "'global' is not allowed in DSL code"
        )

    def visit_Nonlocal(self, node: ast.Nonlocal):
        raise DSLSyntaxError.from_node(
            node, "'nonlocal' is not allowed in DSL code"
        )

    def visit_AugAssign(self, node: ast.AugAssign):
        # e.g. A += Point(0,0). Can't sensibly mean "extend an element".
        # Allow AugAssign against plain Python locals, but we can't
        # tell those apart from Construction names at AST time, so
        # forbid uniformly. Future work: allow when target isn't a
        # known construction name.
        raise DSLSyntaxError.from_node(
            node, "augmented assignment (+=, -=, …) is not supported in DSL"
        )

    def visit_NamedExpr(self, node: ast.NamedExpr):
        raise DSLSyntaxError.from_node(
            node, "walrus operator (:=) is not supported in DSL"
        )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value is not None:
            raise DSLSyntaxError.from_node(
                node, "annotated assignment (x: T = …) is not supported in DSL"
            )
        # Bare ``x: T`` with no value is a no-op — safe to drop.
        return None

    # ── loop-scope tracking ──────────────────────────────────────

    def _visit_scoped(self, node):
        self._loop_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self._loop_depth -= 1
        return node

    visit_For = _visit_scoped
    visit_AsyncFor = _visit_scoped
    visit_While = _visit_scoped
    visit_FunctionDef = _visit_scoped
    visit_AsyncFunctionDef = _visit_scoped
    visit_Lambda = _visit_scoped
    visit_ListComp = _visit_scoped
    visit_SetComp = _visit_scoped
    visit_DictComp = _visit_scoped
    visit_GeneratorExp = _visit_scoped
    # ``visit_If`` has its own override above (dead-code detection).

    # ── the actual rewrite ───────────────────────────────────────

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)  # walk RHS first
        if len(node.targets) != 1:
            # Chained assignment (A = B = expr). Rare in DSL; forbid.
            raise DSLSyntaxError.from_node(
                node, "chained assignment (a = b = ...) is not supported in DSL"
            )
        target = node.targets[0]

        if isinstance(target, ast.Name):
            return self._wrap_single(node, target)
        if isinstance(target, (ast.Tuple, ast.List)):
            return self._wrap_tuple(node, target)
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            # A.style.stroke = '#f00'  →  leave alone; the proxy's
            # __setattr__ handles it at runtime.
            return node
        raise DSLSyntaxError.from_node(
            node, f"unsupported assignment target: {type(target).__name__}"
        )

    def _wrap_single(self, node: ast.Assign, target: ast.Name):
        reg_name = "__reg_loop__" if self._loop_depth > 0 else "__reg__"
        call = ast.Call(
            func=ast.Name(id=reg_name, ctx=ast.Load()),
            args=[
                ast.Constant(value=target.id),
                node.value,
            ],
            keywords=[],
        )
        new_node = ast.Assign(targets=[target], value=call)
        return ast.copy_location(new_node, node)

    def _wrap_tuple(self, node: ast.Assign, target):
        names: list[str] = []
        for el in target.elts:
            if not isinstance(el, ast.Name):
                raise DSLSyntaxError.from_node(
                    node,
                    "only simple names are supported in tuple unpacking, "
                    f"got {type(el).__name__}",
                )
            names.append(el.id)

        # If the RHS is a direct factory call, inject ``_outputs=N`` so
        # the factory allocates N phantom names upfront (before apply).
        # This is the bridge between the flat Command model (outputs
        # baked in at registration) and tuple-unpacking user syntax.
        rhs = node.value
        if isinstance(rhs, ast.Call):
            rhs.keywords = list(rhs.keywords) + [
                ast.keyword(
                    arg="_outputs",
                    value=ast.Constant(value=len(names)),
                )
            ]

        reg_name = "__reg_loop_tuple__" if self._loop_depth > 0 else "__reg_tuple__"
        call = ast.Call(
            func=ast.Name(id=reg_name, ctx=ast.Load()),
            args=[
                ast.Tuple(
                    elts=[ast.Constant(value=n) for n in names],
                    ctx=ast.Load(),
                ),
                rhs,
            ],
            keywords=[],
        )
        new_node = ast.Assign(targets=[target], value=call)
        return ast.copy_location(new_node, node)


def _make_syntax_error(node: ast.AST, message: str) -> DSLSyntaxError:
    err = DSLSyntaxError(message)
    err.lineno = getattr(node, "lineno", None)
    err.offset = getattr(node, "col_offset", None)
    return err


DSLSyntaxError.from_node = staticmethod(_make_syntax_error)  # type: ignore[attr-defined]


def transform(code: str) -> ast.Module:
    """Parse ``code`` and return a rewritten ``ast.Module`` ready for compile."""
    tree = ast.parse(code)
    tree = _Rewriter().visit(tree)
    ast.fix_missing_locations(tree)
    return tree
