"""Type stubs for DSL-visible types.

**Runtime reality:** a single concrete class ``ElementProxy`` with
``__getattr__`` forwarding to the underlying geometric data.

**Stub fiction:** ``Point``, ``Line``, ``Circle`` etc. are declared
as separate classes with precise constructors, fields, and operator
signatures. The IDE treats ``A = Point(3, 4)`` as constructing a
``Point`` instance; at runtime the same call hits a factory function
in ``namespace.py`` that returns an ``ElementProxy``. Both paths
agree that ``A.x: float`` — the ``ElementProxy.__getattr__`` handles
the lookup against the underlying ``Point`` data class's ``@property
x``, and the stub declares ``x: float`` directly.

This means:
* IDE autocomplete shows ``Point``, ``Line``, ``Circle`` — not
  ``PointProxy``, ``LineProxy``, ``CircleProxy`` — which reads more
  naturally in user DSL code.
* ``isinstance(A, Point)`` would raise ``TypeError`` at runtime
  because stub ``Point`` doesn't exist as a real class. Use
  ``isinstance(A.data, lib_elements.Point)`` instead if you need a
  runtime type check (uncommon in DSL code).
"""

from typing import Any, Optional, Sequence, overload

import numpy as np

from ...style.proxy import StyleProxy


# ── Base ─────────────────────────────────────────────────────────

class ElementProxy:
    """Runtime base. DSL users should see the per-type subclasses."""

    name: str
    visible: bool
    tparam: Optional[float]     # curve/locus parameter
    style: StyleProxy
    data: Any

    def __init__(self, constr: Any, name: str, *, explicit: bool = ...) -> None: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __getattr__(self, attr: str) -> Any: ...


# ── Points / vars ────────────────────────────────────────────────

class Point(ElementProxy):
    """A 2D point in the construction."""
    x: float
    y: float
    coords: np.ndarray

    @overload
    def __init__(self, x: float, y: float, *, name: Optional[str] = ...) -> None: ...
    @overload
    def __init__(self, coords: Sequence[float], *, name: Optional[str] = ...) -> None: ...

    def __add__(self, other: Any) -> Point: ...
    def __sub__(self, other: Any) -> Point: ...
    def __mul__(self, other: Any) -> Point: ...
    def __truediv__(self, other: Any) -> Point: ...
    def __neg__(self) -> Point: ...


class Measure(ElementProxy):
    """A dimensioned numeric value."""
    value: float
    dimension: int

    def __init__(self, x: float, dim: int = ...,
                 *, name: Optional[str] = ...) -> None: ...


class Boolean(ElementProxy):
    """A boolean value."""
    value: bool

    def __init__(self, b: bool, *, name: Optional[str] = ...) -> None: ...


# ── Lines / segments / rays ──────────────────────────────────────

class Line(ElementProxy):
    """A line in the plane, ``normal · x = offset``."""
    normal: np.ndarray
    direction: np.ndarray
    offset: float

    def __init__(self, *args: Any, name: Optional[str] = ...) -> None: ...


class Segment(Line):
    """A finite segment between two endpoints."""
    start: np.ndarray
    end: np.ndarray
    length: float

    def __init__(self, p1: Any, p2: Any, *, name: Optional[str] = ...) -> None: ...


class Ray(Line):
    """A half-line starting from ``start`` in direction ``direction``."""
    start: np.ndarray

    def __init__(self, start_pt: Any, through_or_dir: Any, *,
                 name: Optional[str] = ...) -> None: ...


# ── Circles / arcs / sectors ─────────────────────────────────────

class Circle(ElementProxy):
    """A circle centred at ``center`` with ``radius``."""
    center: np.ndarray
    radius: float

    @overload
    def __init__(self, center: Point, radius: float, *,
                 name: Optional[str] = ...) -> None: ...
    @overload
    def __init__(self, center: Point, through: Point, *,
                 name: Optional[str] = ...) -> None: ...


class Arc(Circle):
    angle_start: float
    angle_end: float

    def __init__(self, *args: Any, name: Optional[str] = ...) -> None: ...


class CircleSector(Circle):
    angle_start: float
    angle_end: float

    def __init__(self, *args: Any, name: Optional[str] = ...) -> None: ...


# ── Other primitives ─────────────────────────────────────────────

class Angle(ElementProxy):
    vertex: np.ndarray
    value: float       # size in radians
    arc_radius: float
    side1: np.ndarray
    side2: np.ndarray

    def __init__(self, a: Point, b: Point, c: Point,
                 *, name: Optional[str] = ...) -> None: ...


class Polygon(ElementProxy):
    vertices: np.ndarray

    def __init__(self, *points: Point, name: Optional[str] = ...) -> None: ...


class Vector(ElementProxy):
    start: np.ndarray
    end: np.ndarray
    direction: np.ndarray

    def __init__(self, start: Point, end: Point,
                 *, name: Optional[str] = ...) -> None: ...


class LocusCurve(ElementProxy):
    points: np.ndarray

    def __init__(self, *args: Any, name: Optional[str] = ...) -> None: ...


# ── Algebraic curves ─────────────────────────────────────────────

class Conic(ElementProxy):
    matrix: np.ndarray
    kind: Any           # ConicType enum

    def __init__(self, equation_or_matrix: Any,
                 *, name: Optional[str] = ...) -> None: ...


class Function(ElementProxy):
    expression: Any     # sympy Expr
    variable: Any       # sympy Symbol
    source: str

    def __init__(self, expression: str,
                 *, name: Optional[str] = ...) -> None: ...
    def __call__(self, x: Any) -> Measure:
        """``f(1)`` — the value at ``x``, live: it follows the function."""
        ...


class ImplicitCurve(ElementProxy):
    expression: Any
    x_var: Any
    y_var: Any
    source: str

    def __init__(self, expression: str,
                 *, name: Optional[str] = ...) -> None: ...
