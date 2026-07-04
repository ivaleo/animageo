"""Path-B exec-based DSL engine for AnimaGeo.

Entry point: :func:`run`. Transforms the user's code so every
Construction-level assignment routes through the registrar, then execs
the compiled result against a sandboxed namespace.

Pipeline::

    code: str
      │
      ├─► dsl.transform  ── ast.parse + NodeTransformer
      │     • wrap Assign → __reg__("name", expr)        (top-level)
      │     •              → __reg_loop__("name", expr)  (inside For/Def/…)
      │     • tuple forms  → __reg_tuple__ / __reg_loop_tuple__
      │     • forbid Import/Global/Nonlocal/AugAssign/Walrus
      │
      ├─► dsl.namespace  ── registrars + factories + math + SAFE_BUILTINS
      │
      └─► exec(compiled, ns, {})
            │
            └─ factories register commands via ContextVar
               and rebuild eagerly so `A.x` mid-exec sees fresh data
"""

from __future__ import annotations

import logging
import textwrap
from contextlib import contextmanager

from .namespace import build_namespace
from .sugar import preprocess_dsl_sugar as _preprocess_sugar
from .registrar import reset_current_construction, set_current_construction
from .transform import DSLSyntaxError
from .transform import transform as _transform_fn

logger = logging.getLogger(__name__)


def run(constr, code: str, *, debug: bool = False, show: bool = True) -> None:
    """Execute ``code`` against ``constr`` using the exec-based engine.

    Parameters
    ----------
    constr : Construction
        Graph to register commands into.
    code : str
        DSL source. Standard Python syntax plus the namespace factories.
    debug : bool
        Passes through to ``Construction.add_and_build``.
    show : bool
        If False, hide all elements bound at module top level by this call.
    """
    # Strip a common leading indent so triple-quoted DSL blocks work
    # naturally inside indented Python methods.
    code = textwrap.dedent(code)
    # Sugar: ``f(x) = x^2 + 1`` → ``f = Function("y = x^2 + 1")``.
    # Runs before ``ast.parse``, so the transform below never sees the
    # non-Python ``name(var) = expr`` form.
    code = _preprocess_sugar(code)
    module = _transform_fn(code)

    compiled = compile(module, "<dsl>", "exec")
    ns = build_namespace(constr)

    # Observe which names get bound at top level, for ``show=False``.
    top_level_names: list[str] = _collect_top_level_names(module)

    token = set_current_construction(constr)
    try:
        # ``exec(code, ns)`` — single-dict form uses ``ns`` as both
        # globals and locals. This is critical for FactoryDict: when
        # a separate locals dict is passed, LOAD_NAME is emitted
        # instead of LOAD_GLOBAL and ``__missing__`` is not invoked
        # for module-level CamelCase lookups.
        exec(compiled, ns)
    finally:
        reset_current_construction(token)

    # Final sort — commands were appended in user order (topologically
    # valid by construction), but sort anyway for stability downstream.
    constr.sortCommands()

    if not show:
        for name in top_level_names:
            elem = constr.element(name)
            if elem is not None:
                elem.visible = False


def _collect_top_level_names(module) -> list[str]:
    """Return names bound at the module top level (outside any scope)."""
    import ast

    names: list[str] = []
    for stmt in module.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                names.append(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for el in target.elts:
                    if isinstance(el, ast.Name):
                        names.append(el.id)
    return names


@contextmanager
def scope(constr):
    """Bind ``constr`` as the active Construction for direct factory use.

    Companion to :func:`run` for callers who want the DSL namespace
    available inside a regular Python block, with full IDE
    autocomplete. ``run`` does AST rewriting so ``A = Point(...)``
    captures the LHS name into the Construction; ``scope`` does not
    — pass ``name=`` explicitly when you want a specific element
    name in the graph::

        from animageo.parsers.dsl.namespace import Point, Midpoint

        c = Construction()
        with dsl.scope(c):
            A = Point(3, 4, name='A')       # element "A" in c
            M = Midpoint(A, Point(0, 0, name='O'), name='M')
            print(M.x, M.y)                 # live proxy reads

    Without ``name=`` the element gets a phantom name (``_1``,
    ``_2``…) — the Python variable still holds a proxy but the
    Construction name is anonymous.
    """
    token = set_current_construction(constr)
    try:
        yield constr
    finally:
        reset_current_construction(token)


__all__ = ["run", "scope", "DSLSyntaxError"]
