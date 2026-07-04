"""Implicit curve F(x, y) = 0 as a first-class geometry element.

Where Function handles explicit y = f(x) and Conic handles quadratic
F(x, y) = 0 in matrix form, ImplicitCurve covers everything else —
arbitrary sympy expressions equated to zero, including non-polynomial
forms like ``sqrt(-4y) + sqrt|x - 1| = 5`` that appear in the func5.ggb
fixture.

Rendering uses marching-squares contouring on a bounded grid, so work
is O(grid_n²) and never hangs on pathological expressions. Intersection
with other curves is not implemented in this PR — numeric 2D
root-finding is deferred to a later pass.
"""
import logging
import re
from typing import Callable, List, Optional, Tuple

import numpy as np
import sympy as sp

from ..constants import Z_LINE
from .lib_function import (
    _normalize_expression, _strip_label_prefix, _SYMPY_FUNCS,
)


logger = logging.getLogger(__name__)


def _split_equation(raw: str) -> str:
    """Convert ``LHS = RHS`` into ``(LHS) - (RHS)`` so the expression is
    ready to be equated to zero. Returns the raw string if there is no
    ``=`` sign.
    """
    if '=' not in raw:
        return raw
    lhs, rhs = raw.split('=', 1)
    return f"({lhs.strip()}) - ({rhs.strip()})"


def parse_implicit_expression(
    raw: str,
) -> Tuple[sp.Expr, sp.Symbol, sp.Symbol]:
    """Parse a two-variable expression ``F(x, y) = 0`` or ``A = B`` into
    ``(sympy_expr, sym_x, sym_y)``.

    Accepts forms:
        - ``"x**2 + y**2 - 1"`` (implicit F=0)
        - ``"x**2 + y**2 = 1"`` (equation)
        - ``"sqrt(-4*y) + sqrt(abs(x - 1)) = 5"`` (GGB implicitpoly)
    """
    text = _strip_label_prefix(raw)
    text = _normalize_expression(text)
    text = _split_equation(text)

    x = sp.Symbol('x')
    y = sp.Symbol('y')
    try:
        expr = sp.sympify(text, locals={'x': x, 'y': y, **_SYMPY_FUNCS})
    except (sp.SympifyError, SyntaxError, TypeError) as e:
        raise ValueError(f"could not parse implicit expression {raw!r}: {e}")
    return expr, x, y


class ImplicitCurve:
    """A curve defined by F(x, y) = 0 for an arbitrary sympy expression.

    Attributes:
        expr: sympy expression (zero-level set).
        var_x, var_y: sympy symbols for the two variables.
        original: raw string this was built from.
    """

    def __init__(
        self,
        expr,
        var_x: Optional[sp.Symbol] = None,
        var_y: Optional[sp.Symbol] = None,
        *,
        source: Optional[str] = None,
    ):
        if isinstance(expr, str):
            parsed, sx, sy = parse_implicit_expression(expr)
            self.expr = parsed
            self.var_x = sx
            self.var_y = sy
            self.source = expr
        else:
            if var_x is None or var_y is None:
                # Try to infer from free symbols.
                free = sorted(expr.free_symbols, key=lambda s: str(s))
                if len(free) != 2:
                    raise ValueError(
                        f"Implicit expression has {len(free)} free symbols; "
                        "explicit var_x, var_y required"
                    )
                var_x, var_y = free[0], free[1]
            self.expr = expr
            self.var_x = var_x
            self.var_y = var_y
            self.source = source or str(expr)

        self._callable = sp.lambdify(
            (self.var_x, self.var_y), self.expr,
            modules=['numpy', {'Abs': np.abs}],
        )

        from ..style.proxy import StyleProxy
        self.style = StyleProxy()
        self.style['fill_opacity'] = 0
        self.style['z_index'] = Z_LINE

    # ── Human-friendly accessors ──
    @property
    def expression(self): return self.expr
    @property
    def x_var(self): return self.var_x
    @property
    def y_var(self): return self.var_y

    @classmethod
    def from_string(cls, raw: str) -> 'ImplicitCurve':
        expr, sx, sy = parse_implicit_expression(raw)
        return cls(expr, sx, sy, source=raw)

    # ── Evaluation ────────────────────────────────────────────────────

    def __call__(self, x, y):
        """Scalar / array evaluation. Any exception is mapped to NaN so
        the marching-squares contourer can skip undefined regions.
        """
        try:
            v = self._callable(x, y)
        except (ValueError, ZeroDivisionError, FloatingPointError, TypeError):
            if np.isscalar(x) and np.isscalar(y):
                return float('nan')
            return np.full_like(np.asarray(x, dtype=float), np.nan)
        if isinstance(v, complex):
            if abs(v.imag) < 1e-12:
                return float(v.real)
            return float('nan')
        if isinstance(v, np.ndarray) and np.iscomplexobj(v):
            real = v.real.copy()
            real[np.abs(v.imag) > 1e-12] = np.nan
            return real
        return v

    def contains(self, point) -> bool:
        p = np.asarray(point)
        try:
            return bool(np.isclose(float(self(p[0], p[1])), 0))
        except Exception:
            return False

    # ── Transforms ────────────────────────────────────────────────────

    def translate(self, vec):
        dx, dy = float(vec[0]), float(vec[1])
        self.expr = self.expr.subs([(self.var_x, self.var_x - dx),
                                    (self.var_y, self.var_y - dy)])
        self._callable = sp.lambdify(
            (self.var_x, self.var_y), self.expr,
            modules=['numpy', {'Abs': np.abs}],
        )

    def scale(self, ratio):
        if ratio == 0:
            raise ValueError("Scale ratio cannot be zero")
        self.expr = self.expr.subs([(self.var_x, self.var_x / ratio),
                                    (self.var_y, self.var_y / ratio)])
        self._callable = sp.lambdify(
            (self.var_x, self.var_y), self.expr,
            modules=['numpy', {'Abs': np.abs}],
        )

    def equivalent(self, other) -> bool:
        if not isinstance(other, ImplicitCurve):
            return False
        try:
            return bool(sp.simplify(self.expr - other.expr) == 0)
        except Exception:
            return False

    def __repr__(self):
        return f"ImplicitCurve({self.expr} = 0)"
