"""Element proxies returned from DSL factories.

A proxy is a thin, name-addressed view onto an entry in a
:class:`Construction`. Attribute reads forward to the underlying
``elem.data`` at access time so values stay fresh after rebuilds.

Runtime shape (Phase 1):

* ``ElementProxy`` — single class that covers every element type via
  ``__getattr__``. Per-type subclasses (``PointProxy`` etc.) land in
  Phase 3 alongside human-friendly ``@property``\\s on the geometry
  classes; until then ``A.a[0]`` is how you read the x-coord of a
  Point, same as the underlying data.

* ``_explicit_name`` — set ``True`` when the factory was called with
  an explicit ``name=`` kwarg. Tells the registrar "this proxy already
  carries a user-chosen name — don't rename it on the next binding".
"""

from __future__ import annotations


class ElementProxy:
    """Name-addressed view onto a Construction entry."""

    __slots__ = ("_name", "_constr", "_explicit_name")

    def __init__(self, constr, name: str, *, explicit: bool = False) -> None:
        object.__setattr__(self, "_constr", constr)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_explicit_name", explicit)

    # ── identity ─────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"<ElementProxy '{self._name}'>"

    def __eq__(self, other) -> bool:
        if isinstance(other, ElementProxy):
            return self._name == other._name and self._constr is other._constr
        return NotImplemented

    def __hash__(self) -> int:
        return hash((id(self._constr), self._name))

    # ── live accessors ───────────────────────────────────────────

    def _element(self):
        return self._constr.element(self._name)

    def _var(self):
        return self._constr.var(self._name)

    def _holder(self):
        """Return the wrapper (``Element`` or ``Var``) by name."""
        return self._element() or self._var()

    @property
    def data(self):
        h = self._holder()
        return h.data if h is not None else None

    @property
    def visible(self) -> bool:
        h = self._element()
        return h.visible if h is not None else False

    @visible.setter
    def visible(self, value: bool) -> None:
        h = self._element()
        if h is not None:
            h.visible = bool(value)

    @property
    def style(self):
        h = self._element()
        return h.style if h is not None else None

    @property
    def tparam(self):
        """Curve/locus parameter for a point constrained on circle/
        segment/line/ray. Angle (radians) for circles; linear t for
        segments/lines/rays.
        """
        h = self._element()
        return h.tparam if h is not None else None

    @tparam.setter
    def tparam(self, value):
        h = self._element()
        if h is not None:
            h.tparam = value

    # ── transparent attribute forwarding ─────────────────────────

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)
        data = self.data
        if data is None:
            raise AttributeError(
                f"ElementProxy('{self._name}'): no underlying data"
            )
        try:
            return getattr(data, attr)
        except AttributeError:
            raise AttributeError(
                f"ElementProxy('{self._name}'): "
                f"{type(data).__name__} has no attribute '{attr}'"
            ) from None

    # ── arithmetic operators ─────────────────────────────────────
    #
    # ``A - B``, ``-A``, ``A * 2``, etc. register ``Sub``/``USub``/
    # ``Mult`` commands in the construction and return a fresh proxy
    # for the result. GGB-emitted expressions like ``P - Q`` (vector
    # from Q to P), ``-v`` (reverse vector), ``x / 2`` (scalar div)
    # all rely on this path.

    def __add__(self, other): return _binop(self, other, 'Add')
    def __radd__(self, other): return _binop(other, self, 'Add')
    def __sub__(self, other): return _binop(self, other, 'Sub')
    def __rsub__(self, other): return _binop(other, self, 'Sub')
    def __mul__(self, other): return _binop(self, other, 'Mult')
    def __rmul__(self, other): return _binop(other, self, 'Mult')
    def __truediv__(self, other): return _binop(self, other, 'Div')
    def __rtruediv__(self, other): return _binop(other, self, 'Div')
    def __pow__(self, other): return _binop(self, other, 'Pow')
    def __rpow__(self, other): return _binop(other, self, 'Pow')
    def __neg__(self): return _unary(self, 'USub')
    def __abs__(self): return _unary(self, 'Abs')


def _coerce(value):
    """Convert a proxy to its construction name; pass other values through."""
    if isinstance(value, ElementProxy):
        return value._name
    return value


def _binop(lhs, rhs, cmd_name: str) -> "ElementProxy":
    """Register a binary-op command and return a proxy for the result."""
    # Lazy import — ``Command`` lives in ``geo.lib_commands`` which
    # imports through the parsers layer. Importing at module top
    # would create a cycle.
    from ...geo.lib_commands import Command

    # Pick the construction from whichever operand is a proxy.
    constr = (lhs if isinstance(lhs, ElementProxy) else rhs)._constr
    phantom = constr.add_new_phantom()
    constr.add_and_build(
        Command(cmd_name, [_coerce(lhs), _coerce(rhs)], [phantom])
    )
    return ElementProxy(constr, phantom, explicit=False)


def _unary(operand: "ElementProxy", cmd_name: str) -> "ElementProxy":
    from ...geo.lib_commands import Command
    constr = operand._constr
    phantom = constr.add_new_phantom()
    constr.add_and_build(Command(cmd_name, [_coerce(operand)], [phantom]))
    return ElementProxy(constr, phantom, explicit=False)
