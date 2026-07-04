"""Registrar functions injected into the exec namespace.

Every user-level assignment in the DSL is rewritten by
:mod:`animageo.parsers.dsl.transform` into a call to one of the
``__reg_*`` functions here. They are the only place that promotes
phantom names into user-chosen names and that detects in-loop name
collisions.

Call-site matrix
----------------

Top-level, single target::

    A = Point(0, 0)                → A = __reg__("A", Point(0, 0))

Top-level, tuple unpacking::

    a, b = Intersect(c, L)         → (a, b) = __reg_tuple__(("a","b"), ...)

Inside a For / While / FunctionDef / Lambda / comprehension::

    for i in range(3):             → for i in range(3):
        p = Point(i, 0)                p = __reg_loop__("p", Point(i, 0))

Rules
-----

1. If ``value`` is an :class:`ElementProxy` with ``_explicit_name``
   set (factory called with ``name=`` kwarg), keep the existing
   construction name — just bind the Python variable. Rationale: the
   user asked for a specific name, don't clobber it with the LHS.
2. If ``value`` is an :class:`ElementProxy` pointing at a phantom,
   rename the phantom to the target name.
3. If ``value`` is a literal (number, bool, list), write it via
   ``constr.update(name, value)`` and return a fresh proxy.
"""

from __future__ import annotations

import contextvars
import logging

from .proxy import ElementProxy

logger = logging.getLogger(__name__)

# ── Context variable for the current Construction ────────────────
#
# Set by dsl.run() around the exec call. Factories consult it to
# find the construction graph they should register commands into.
_CURRENT_CONSTRUCTION: contextvars.ContextVar = contextvars.ContextVar(
    "animageo_current_construction", default=None
)


def _current_construction():
    return _CURRENT_CONSTRUCTION.get()


def set_current_construction(constr):
    """Bind ``constr`` as the active construction, returning a token.

    Caller must pass the token back to :func:`reset_current_construction`.
    """
    return _CURRENT_CONSTRUCTION.set(constr)


def reset_current_construction(token) -> None:
    _CURRENT_CONSTRUCTION.reset(token)


# ── Registrar helpers ────────────────────────────────────────────

def _is_literal(value) -> bool:
    return isinstance(value, (int, float, bool, str, list, tuple)) and not isinstance(
        value, ElementProxy
    )


_SCALAR_LITERALS = (int, float, bool, str, bytes, type(None))


def _bind(constr, target: str, value):
    """Core binding logic shared by top-level and in-loop registrars."""
    if isinstance(value, ElementProxy):
        if value._explicit_name:
            # Factory already chose a name; keep it, just hand the
            # proxy back to Python.
            return value
        if value._name == target:
            return value
        constr.rename(value._name, target)
        return ElementProxy(constr, target, explicit=False)

    # Literal / Python value — write into a var so the Construction
    # graph sees it, but return the raw value so Python expressions
    # like ``x * deg`` keep working naturally. (Returning a proxy
    # would force ``x`` to participate in ElementProxy arithmetic
    # which it doesn't currently support.)
    constr.update(target, value)
    if isinstance(value, _SCALAR_LITERALS) or isinstance(value, (list, tuple)):
        return value
    return ElementProxy(constr, target, explicit=False)


def __reg__(name: str, value):
    """Top-level binding.

    If ``name`` is already taken, :meth:`Construction.rename` below
    raises ``ValueError``; the caller sees a clear conflict instead of a
    silent mutation.
    """
    constr = _current_construction()
    if constr is None:
        raise RuntimeError(
            "__reg__ called outside dsl.run — no active Construction"
        )

    # If the same name already holds an element and the incoming value
    # is an ElementProxy for a phantom, we'd be renaming _N → already
    # taken. Clear the old entry first (update semantics).
    if (
        isinstance(value, ElementProxy)
        and not value._explicit_name
        and constr.objectByName(name) is not None
        and value._name != name
    ):
        # Drop the stale binding so rename() can install the fresh one.
        _forget(constr, name)

    return _bind(constr, name, value)


def __reg_loop__(base: str, value):
    """In-loop binding: always picks a unique name.

    Sequence: ``base``, ``base_2``, ``base_3``, … Starts from ``_2``
    (skipping ``base``) if ``base`` is already in the construction
    from outside the loop — so top-level ``p = Point(...)`` followed
    by ``for i: p = Point(...)`` produces ``p, p_2, p_3, …`` exactly
    as the user would expect.
    """
    constr = _current_construction()
    if constr is None:
        raise RuntimeError("__reg_loop__ called outside dsl.run")

    counter = constr.naming_counters
    n = counter.get(base, 0) + 1
    while True:
        candidate = base if n == 1 else f"{base}_{n}"
        if constr.objectByName(candidate) is None:
            break
        n += 1
    counter[base] = n

    return _bind(constr, candidate, value)


def __reg_tuple__(names: tuple, value):
    """Top-level tuple unpacking: ``A, B = Intersect(...)``."""
    return _reg_tuple_impl(names, value, looping=False)


def __reg_loop_tuple__(names: tuple, value):
    """In-loop tuple unpacking."""
    return _reg_tuple_impl(names, value, looping=True)


def _reg_tuple_impl(names, value, *, looping: bool):
    if not isinstance(value, (tuple, list)):
        raise TypeError(
            f"tuple unpacking expected iterable of {len(names)} proxies, "
            f"got {type(value).__name__}"
        )
    if len(value) != len(names):
        raise ValueError(
            f"tuple unpacking: expected {len(names)} values, got {len(value)}"
        )
    reg = __reg_loop__ if looping else __reg__
    return tuple(reg(n, v) for n, v in zip(names, value))


def _forget(constr, name: str) -> None:
    """Remove an existing binding by name. Helper for overwrite semantics."""
    constr.elements = [e for e in constr.elements if e.name != name]
    constr.vars = [v for v in constr.vars if v.name != name]
    constr.commands = [
        c for c in constr.commands if name not in c.outputs
    ]
    constr.state.pop(name, None)
    for entry in constr.state.values():
        entry['inputs'] = [x for x in entry['inputs'] if x != name]
        entry['outputs'] = [x for x in entry['outputs'] if x != name]
