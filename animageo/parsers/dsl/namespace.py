"""Exec namespace for the DSL engine.

Design
------

The globals dict passed to ``exec`` is a :class:`FactoryDict` — a
dict subclass that resolves missing CamelCase keys on demand. Any
CamelCase identifier used in DSL code is matched against
``geo/lib_commands.py``: if a dispatchable function exists for that
command name, a factory is created, cached, and returned. Otherwise
the lookup raises ``KeyError`` and Python surfaces the standard
``NameError``.

This replaces the "enumerate every command up-front" approach — no
hand-maintained list to drift out of sync with ``lib_commands``.

Factory contract
----------------

Each auto-generated factory:

1. Reads the active :class:`Construction` from the registrar's
   ``ContextVar``.
2. Converts any :class:`ElementProxy` positional arg to its
   ``._name`` (a string) — the command layer expects names.
3. Normalizes command-specific semantic kwargs into positional command
   inputs; currently ``Intersect(index=n)`` becomes ``Intersect(..., n)``.
4. Allocates ``_outputs`` output names (default 1; injected by the
   transform when the call is on the RHS of a tuple-unpack). The
   first slot can be an explicit ``name=`` kwarg; remaining slots
   are phantoms.
5. Builds a :class:`Command` and hands it to
   :meth:`Construction.add_and_build` (eager mode).
6. Returns a single :class:`ElementProxy` for ``_outputs == 1``,
   otherwise a tuple of proxies.

Dispatch validation
-------------------

``_can_dispatch(name)`` checks ``lib_commands`` for any function
matching ``snake_case(name)`` exactly, or ``snake_case(name)_SUFFIX``
where ``SUFFIX`` is a valid shortcut string. Unknown names are
rejected at lookup time with ``NameError`` instead of a silent
"no implementation" warning.
"""

from __future__ import annotations

import builtins as _builtins
import math

from ...geo import lib_commands as _lib_commands
from ...geo.lib_commands import Command
from .proxy import ElementProxy
from .registrar import (
    __reg__,
    __reg_loop__,
    __reg_loop_tuple__,
    __reg_tuple__,
    _current_construction,
)

# ── Shortcut chars mirrored from lib_commands.type_to_shortcut ────

_SHORTCUT_CHARS = frozenset("plrscCSavPimAbKLFIT")
_SEMANTIC_KWARGS: dict[str, frozenset[str]] = {
    "Intersect": frozenset({"index"}),
}


def _camel_to_snake(name: str) -> str:
    out: list[str] = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.lower())
    return "".join(out)


def _is_shortcut_suffix(s: str) -> bool:
    return bool(s) and all(c in _SHORTCUT_CHARS for c in s)


def _can_dispatch(camel_name: str) -> bool:
    """True if ``lib_commands`` has any function matching the command name.

    Matches either the bare snake_case form (no-suffix commands like
    ``polygon``) or ``snake_case_SUFFIX`` for a valid shortcut SUFFIX.
    """
    snake = _camel_to_snake(camel_name)
    # Exact match — no-suffix commands.
    fn = getattr(_lib_commands, snake, None)
    if callable(fn):
        return True
    # Suffix match.
    prefix_dash = snake + "_"
    for fname in dir(_lib_commands):
        if not fname.startswith(prefix_dash):
            continue
        suffix = fname[len(prefix_dash):]
        if _is_shortcut_suffix(suffix):
            return True
    return False


# ── Factory generator ────────────────────────────────────────────

def _coerce_arg(a):
    if isinstance(a, ElementProxy):
        return a._name
    return a


def _normalize_factory_args(command_name: str, args: tuple, kwargs: dict) -> list:
    """Fold supported semantic kwargs into the positional command inputs."""
    allowed = _SEMANTIC_KWARGS.get(command_name, frozenset())
    for kw in kwargs:
        if kw not in allowed:
            raise TypeError(
                f"{command_name}() got an unexpected keyword argument {kw!r}"
            )

    normalized = list(args)
    if command_name == "Intersect" and "index" in kwargs:
        if len(normalized) >= 3:
            raise TypeError(
                "Intersect() got both positional and keyword intersection index"
            )
        index = kwargs["index"]
        if index is not None:
            normalized.append(index)

    return normalized


def _make_factory(command_name: str):
    """Build a factory for ``command_name``. Caller must verify dispatch."""

    def factory(*args, name: str | None = None, _outputs: int = 1, **kwargs):
        normalized_args = _normalize_factory_args(command_name, args, kwargs)
        constr = _current_construction()
        if constr is None:
            raise RuntimeError(
                f"{command_name}() called outside dsl.run — no active Construction"
            )
        if _outputs < 1:
            raise ValueError(
                f"{command_name}(_outputs={_outputs}): must be >= 1"
            )
        converted = [_coerce_arg(a) for a in normalized_args]

        out_names: list[str] = []
        explicit_flags: list[bool] = []
        for i in range(_outputs):
            if i == 0 and name is not None:
                if constr.objectByName(name) is not None:
                    raise ValueError(
                        f"{command_name}(name={name!r}): name already in use"
                    )
                out_names.append(name)
                explicit_flags.append(True)
            else:
                out_names.append(constr.add_new_phantom())
                explicit_flags.append(False)

        cmd = Command(command_name, converted, out_names)
        constr.add_and_build(cmd)

        proxies = tuple(
            ElementProxy(constr, out_names[i], explicit=explicit_flags[i])
            for i in range(_outputs)
        )
        return proxies[0] if _outputs == 1 else proxies

    factory.__name__ = command_name
    factory.__qualname__ = f"dsl.namespace.{command_name}"
    factory.__doc__ = (
        f"DSL factory auto-generated for command '{command_name}'. "
        f"Dispatches to lib_commands at Construction.apply time."
    )
    return factory


# ── FactoryDict: the exec globals object ─────────────────────────

class FactoryDict(dict):
    """Globals dict with lazy CamelCase → factory resolution.

    Python's ``exec`` accepts any ``dict`` for globals, including
    subclasses. ``__missing__`` is called on key lookup miss; we use
    it to create factories on demand for CamelCase identifiers that
    have a dispatchable command in ``lib_commands``.

    Cached factories are stored in the dict itself so subsequent
    lookups are O(1). Pre-discovered factories live in
    :data:`_FACTORIES` and are seeded into every FactoryDict up-front
    (so ``from ...namespace import Point`` also works).
    """

    def __missing__(self, key: str):
        if not key or not key.isidentifier():
            raise KeyError(key)

        # 0a) Name is whitelisted as a safe builtin (range, abs, …)
        #     — raise KeyError so LOAD_GLOBAL falls through to the
        #     sandboxed ``__builtins__`` entry.
        if key in SAFE_BUILTINS:
            raise KeyError(key)
        # 0b) Name IS a real Python builtin but we intentionally
        #     excluded it (open, eval, exec, __import__, …). Raise
        #     KeyError → NameError, preserving the sandbox.
        if hasattr(_builtins, key):
            raise KeyError(key)

        # 1) CamelCase → auto-discovered factory.
        if key[0].isupper() and _can_dispatch(key):
            factory = _make_factory(key)
            self[key] = factory  # memoize
            return factory

        constr = _current_construction()
        if constr is not None:
            # 2) Existing construction element → proxy onto it.
            #    Lets DSL code reference names produced by an earlier
            #    ``dsl.run`` or by ``loadGGB`` — e.g. ``scene10.py``
            #    using ``R`` and ``Q`` from the preceding loadGGB.
            if constr.objectByName(key) is not None:
                proxy = ElementProxy(constr, key, explicit=True)
                self[key] = proxy
                return proxy

            # 3) Unknown lowercase name → create a **forward-reference**
            #    Var with no data yet. Supports the common pattern:
            #        scene.loadGGB(...)           # populates R, Q, …
            #        scene.loadCode('scene.py')   # references x
            #        scene.addVar('x', 115)       # x gets its value
            #    GeoGebra parser stores names as strings in Commands.
            #    and deferred resolution to rebuild-time; exec needs
            #    a proxy at the reference site, but Command-inputs
            #    still record the NAME (via ``_coerce``), so
            #    rebuild-time resolution works once the Var gets real
            #    data (i.e. after addVar).
            #
            #    Restricted to lowercase names: CamelCase typos like
            #    ``Rotat`` stay visible as NameError (via the
            #    downstream ``'ElementProxy' is not callable``), and
            #    CamelCase names that should come from loadGGB
            #    (``A``, ``R``) are already caught in step 2.
            if key[0].islower():
                from ...geo.lib_vars import Var
                constr.add(Var(key, None))
                proxy = ElementProxy(constr, key, explicit=True)
                self[key] = proxy
                return proxy

        raise KeyError(key)


# ── Pre-discovered factory registry ──────────────────────────────

def _discover_command_names() -> set[str]:
    """Scan lib_commands for dispatchable commands, return CamelCase set."""
    names: set[str] = set()
    for fname in dir(_lib_commands):
        if fname.startswith("_"):
            continue
        fn = getattr(_lib_commands, fname, None)
        if not callable(fn):
            continue
        # Skip classes / helpers (CamelCase in lib_commands).
        if fname[0].isupper():
            continue
        if "_" in fname:
            prefix, suffix = fname.rsplit("_", 1)
            if not all(c.islower() or c.isdigit() or c == "_" for c in prefix):
                continue
            if not prefix:
                continue
            if _is_shortcut_suffix(suffix):
                camel = "".join(w.capitalize() for w in prefix.split("_"))
                names.add(camel)
        # else: no-underscore helpers (toObjArray, strCommand, etc.) are
        # skipped — they either CamelCase-filtered above or are utilities.
    return names


_DISCOVERED_COMMANDS: frozenset[str] = frozenset(_discover_command_names())
_FACTORIES: dict[str, callable] = {
    _cmd: _make_factory(_cmd) for _cmd in _DISCOVERED_COMMANDS
}

# Expose at module level so ``from animageo.parsers.dsl.namespace
# import Point, Midpoint, …`` works for direct file-mode use.
globals().update(_FACTORIES)


# ── Safe builtins ────────────────────────────────────────────────

# Builtins exposed to DSL code. Deliberately excludes:
# - ``type``  — ``type(x).__mro__[-1].__subclasses__()`` is a classic
#   sandbox escape that reaches ``object`` → the full runtime. Use
#   ``isinstance(x, Cls)`` or the ``type_name(x)`` helper below instead.
# - ``getattr`` — even restricted to string names it lets user code
#   walk dunders (``__class__``, ``__globals__``). Use direct ``x.attr``
#   access; if you need a default, wrap the access in ``try/except``.
#
# This is a *soft* sandbox aimed at reducing the footgun surface for the
# web-service context where user DSL comes over the wire. It is NOT a
# security boundary — a determined attacker can still reach ``object``
# via class-body tricks enabled by ``__build_class__``. Run untrusted
# DSL in a subprocess with resource limits (CPU, memory, wall-clock)
# and, ideally, filesystem isolation. See ``docs/python_dsl.md``.
_SAFE_BUILTIN_NAMES = (
    "True", "False", "None",
    "abs", "min", "max", "sum", "round", "divmod", "pow",
    "int", "float", "bool", "str",
    "list", "tuple", "dict", "set", "frozenset",
    "range", "enumerate", "zip", "len", "reversed", "sorted", "filter", "map",
    "any", "all",
    "isinstance", "issubclass",
    "print", "repr",
    "hasattr",
    # ``__build_class__`` is needed for ``class Foo:`` in DSL files.
    # Known soft-sandbox hole; documented. Removing would break legitimate
    # DSL code that defines helper dataclasses etc.
    "__build_class__",
)

SAFE_BUILTINS = {n: getattr(_builtins, n) for n in _SAFE_BUILTIN_NAMES}


def _type_name(x):
    """Return ``type(x).__name__`` — a safe stand-in for common ``type()``
    checks that only need the class name as a string (e.g. debug prints,
    dispatch-by-kind). Does NOT return the class object, so the classic
    ``type(x).__mro__[-1].__subclasses__()`` escape is unavailable."""
    return type(x).__name__


SAFE_BUILTINS["type_name"] = _type_name


# ── Math exposure ────────────────────────────────────────────────

_MATH_EXPORTS = {
    "math": math,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "nan": math.nan,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "exp": math.exp,
    "log": math.log,
    "floor": math.floor,
    "ceil": math.ceil,
    # ``TYPE_CHECKING`` is False at runtime — lets DSL files wrap
    # IDE-only stub imports in ``if TYPE_CHECKING:`` blocks.
    "TYPE_CHECKING": False,
}


# ── Stylistic / utility helpers ──────────────────────────────────

def _style(*elements, **props):
    """Batch-apply style props. ``style(A, B, stroke='#f00', width=2)``."""
    for e in elements:
        if not isinstance(e, ElementProxy):
            raise TypeError(f"style(): expected ElementProxy, got {type(e).__name__}")
        holder = e._element()
        if holder is None:
            continue
        for k, v in props.items():
            holder.style[k] = v


def _hide(*elements):
    for e in elements:
        if isinstance(e, ElementProxy):
            e.visible = False


def _show(*elements):
    for e in elements:
        if isinstance(e, ElementProxy):
            e.visible = True


_HELPERS = {
    "style": _style,
    "hide": _hide,
    "show": _show,
}

# Expose helpers at module level too, so
# ``from animageo.parsers.dsl.namespace import style, hide, show``
# mirrors the DSL-namespace lookup inside ``dsl.run``.
style = _style
hide = _hide
show = _show


# ── Namespace builder ────────────────────────────────────────────

def build_namespace(constr) -> FactoryDict:
    """Return the :class:`FactoryDict` passed as exec's globals.

    Pre-populated with: registrar symbols, safe ``__builtins__``,
    math helpers, stylistic helpers. CamelCase factories are resolved
    on demand via :meth:`FactoryDict.__missing__`.
    """
    ns = FactoryDict()
    # Seed with pre-discovered factories so ``Point`` etc. are available
    # without triggering ``__missing__``. (Equivalent behavior, faster.)
    ns.update(_FACTORIES)
    ns.update({
        "__reg__": __reg__,
        "__reg_loop__": __reg_loop__,
        "__reg_tuple__": __reg_tuple__,
        "__reg_loop_tuple__": __reg_loop_tuple__,
        "__builtins__": SAFE_BUILTINS,
    })
    ns.update(_MATH_EXPORTS)
    ns.update(_HELPERS)
    return ns
