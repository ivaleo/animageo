"""Conic sections as 3×3 symmetric matrices.

A conic is the zero set of a quadratic form
    A x² + 2B xy + C y² + 2D x + 2E y + F = 0
stored as
    M = [[A, B, D],
         [B, C, E],
         [D, E, F]],
so that the equation is (x, y, 1) · M · (x, y, 1)ᵀ = 0.

This matches GeoGebra's <matrix A0..A5> attribute layout:
    A0=A, A1=C, A2=F, A3=B, A4=D, A5=E.

Classification (into ConicType) uses the projective invariants rank(M) and
det(M₃₃) = AC − B². Canonical parametrizations (as_circle, as_ellipse,
as_parabola, as_hyperbola, as_lines, as_point) are computed lazily and
return only the geometric data needed for rendering and intersections —
no curve sampling happens here.
"""
import re
from enum import Enum
from typing import Optional, List
import numpy as np

from .formula_refs import (
    coordinate_calls, substitute_references, unbound_references,
)
from .lib_elements import Line, Point
from .safe_sympify import (
    check_length, has_large_power, normalize_formula_text, safe_sympify,
)
from ..constants import Z_LINE


class ConicType(Enum):
    CIRCLE = 'circle'
    ELLIPSE = 'ellipse'
    PARABOLA = 'parabola'
    HYPERBOLA = 'hyperbola'
    INTERSECTING_LINES = 'intersecting_lines'   # two real lines through one point
    PARALLEL_LINES = 'parallel_lines'           # two distinct real parallel lines
    DOUBLE_LINE = 'double_line'                 # one real line, multiplicity 2
    POINT = 'point'                             # single real point (imaginary line pair)
    EMPTY = 'empty'                             # no real points (imaginary conic)


def parse_conic_equation(equation: str):
    """Parse ``LHS = RHS`` (or a bare ``F``) into ``(sympy_expr, x, y)`` with
    the equation moved to one side. A ``label:`` prefix is tolerated."""
    import sympy as sp

    # The length is checked after π → ` pi `, ℯ → ` exp(1) `: those grow the text.
    text = normalize_formula_text(equation)
    check_length(text)
    text = re.sub(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*', '', text)
    text = text.replace('^', '**')
    if '=' in text:
        lhs, rhs = text.split('=', 1)
        text = f"({lhs.strip()}) - ({rhs.strip()})"
    text, refs = coordinate_calls(text)
    x = sp.Symbol('x')
    y = sp.Symbol('y')
    try:
        expr = safe_sympify(text, {'x': x, 'y': y, 'pi': sp.pi, **refs})
    except (sp.SympifyError, SyntaxError, TypeError) as e:
        raise ValueError(f"could not parse conic equation {equation!r}: {e}")
    return expr, x, y


# Terms above degree 2 may still cancel ((x + 1)^3 − x^3 …), so the
# equation is expanded when its degree bound is at most this.
_MAX_EXPAND_DEGREE = 6


def _degree_bound(expr, gens):
    """Upper bound on the total degree of ``expr`` in ``gens`` read off the
    expression tree, without expanding; ``None`` when ``expr`` is not a
    polynomial in them (a gen in a denominator, a root, ``sin(x)``)."""
    if not expr.has(*gens):
        return 0
    if expr in gens:
        return 1
    if expr.is_Add or expr.is_Mul:
        bounds = [_degree_bound(a, gens) for a in expr.args]
        if None in bounds:
            return None
        return max(bounds) if expr.is_Add else sum(bounds)
    if expr.is_Pow:
        e = expr.exp
        if not ((e.is_Integer or (e.is_Float and float(e).is_integer()))
                and e >= 0):
            return None
        base = _degree_bound(expr.base, gens)
        return None if base is None else base * int(e)
    return None


# GeoGebra's Kernel.STANDARD_PRECISION, used by ggb_frame()'s zero tests.
_GGB_EPS = 1e-8


def _ggb_solve_quadratic(c, b, a):
    """Roots of ``a x² + b x + c`` in GeoGebra's order
    (``EquationSolver.solveQuadraticS``) — the order picks the first axis."""
    eps = _GGB_EPS
    if abs(a) < eps:
        return [] if abs(b) < eps else [-c / b]
    if abs(b) < eps * abs(a):
        x2 = -c / a
        if abs(x2) < eps:
            return [0.0]
        if x2 < 0:
            return []
        return [np.sqrt(x2), -np.sqrt(x2)]
    d = b * b - 4.0 * a * c
    if abs(d) < eps * b * b:
        return [-b / (2.0 * a)]
    if d < 0.0:
        return []
    d = np.sqrt(d)
    if b < 0.0:
        d = -d
    q = (b + d) / -2.0
    return [q / a, c / q]


# Relative tolerance on entries of the scale-normalized matrix.
_TOL = 1e-9


class Conic:
    """A conic (degree-2 algebraic curve) in the plane."""

    def __init__(self, matrix):
        from ..style.proxy import StyleProxy
        arr = np.asarray(matrix, dtype=float)
        if arr.shape != (3, 3):
            raise ValueError(f"Conic matrix must be 3×3, got {arr.shape}")
        # Symmetrize to stay closed under repeated transforms.
        self.matrix = (arr + arr.T) / 2

        self.style = StyleProxy()
        self.style['fill_opacity'] = 0
        self.style['z_index'] = Z_LINE

        self._type: Optional[ConicType] = None
        # GeoGebra orients a Parabola(F, d) by the directrix normal; the
        # constructor stores it here for ggb_frame().
        self.ggb_axis_hint = None

    # ── Human-friendly accessor ──
    @property
    def kind(self): return self.type  # alias for ConicType

    # ── Constructors ───────────────────────────────────────────────────

    @classmethod
    def from_ggb_matrix(cls, A0, A1, A2, A3, A4, A5):
        """From GeoGebra <matrix A0..A5> attributes.

        Equation: A0 x² + 2 A3 xy + A1 y² + 2 A4 x + 2 A5 y + A2 = 0.
        """
        M = np.array([
            [A0, A3, A4],
            [A3, A1, A5],
            [A4, A5, A2],
        ], dtype=float)
        return cls(M)

    @classmethod
    def from_coeffs(cls, a=0.0, b=0.0, c=0.0, d=0.0, e=0.0, f=0.0):
        """From general form: a x² + b xy + c y² + d x + e y + f = 0."""
        M = np.array([
            [a,     b / 2, d / 2],
            [b / 2, c,     e / 2],
            [d / 2, e / 2, f    ],
        ], dtype=float)
        return cls(M)

    @classmethod
    def from_string(cls, equation: str, parameters=None) -> 'Conic':
        """Parse a conic equation string into the matrix form.

        Accepts the GGB-style equation forms:
            "x^2 + y^2 = 4"
            "y = x^2 - 1"
            "x^2 + 2·x·y + y^2 − 4 = 0"
            "g: x^2 + y^2 = 4"   (label prefix tolerated)

        ``parameters`` maps other names in the equation to their current
        values (``"y = a x^2"`` with ``{'a': 2}``; a point's coordinate pair
        for ``x(A)``/``y(A)``, see ``formula_refs``).

        Raises ``ValueError`` if sympy can't parse the expression, a name
        other than ``x``/``y`` stays unbound, or the expanded polynomial
        exceeds degree 2 (not a conic).
        """
        import sympy as sp

        expr, x, y = parse_conic_equation(equation)
        if parameters:
            # A polynomial has no use for a boolean: it counts as 0 / 1.
            expr = substitute_references(expr, {
                k: float(v) if isinstance(v, (bool, np.bool_)) else v
                for k, v in parameters.items()
            })
        unbound = unbound_references(expr, {x, y})
        if unbound:
            # Poly would silently treat them as coefficients, and their
            # float() below would fall back to 0 — a wrong conic.
            raise ValueError(
                f"conic equation {equation!r} has unbound names {unbound}"
            )
        # Expanding (x + y)^10000 takes seconds and grows with the power
        # (formula text is untrusted): bound the degree on the tree first.
        bound = _degree_bound(expr, (x, y))
        if bound is None:
            raise ValueError(
                f"conic equation {equation!r} is not polynomial in x, y")
        if bound > _MAX_EXPAND_DEGREE:
            raise ValueError(
                f"conic equation {equation!r} has degree up to {bound}, "
                "expected ≤ 2")
        if has_large_power(expr):
            raise ValueError(
                f"conic equation {equation!r} has too large a power")
        expr = sp.expand(expr)

        try:
            poly = sp.Poly(expr, x, y)
        except sp.PolynomialError as e:
            raise ValueError(
                f"conic equation {equation!r} is not polynomial in x, y: {e}"
            )
        if poly.total_degree() > 2:
            raise ValueError(
                f"conic equation {equation!r} has degree {poly.total_degree()}, "
                "expected ≤ 2"
            )

        def _coef(mx, my):
            try:
                return float(poly.coeff_monomial(x ** mx * y ** my))
            except Exception:
                return 0.0

        return cls.from_coeffs(
            a=_coef(2, 0), b=_coef(1, 1), c=_coef(0, 2),
            d=_coef(1, 0), e=_coef(0, 1), f=_coef(0, 0),
        )

    # ── Core operations ────────────────────────────────────────────────

    def evaluate(self, x, y):
        """Value of the left-hand side of the conic equation at (x, y)."""
        p = np.array([x, y, 1.0])
        return float(p @ self.matrix @ p)

    def contains(self, point):
        p = np.asarray(point)
        return bool(np.isclose(self.evaluate(p[0], p[1]), 0))

    def translate(self, vec):
        vx, vy = float(vec[0]), float(vec[1])
        # Substitute x → x - vx, y → y - vy (so the curve moves by +vec).
        T = np.array([[1, 0, -vx], [0, 1, -vy], [0, 0, 1]], dtype=float)
        self.matrix = T.T @ self.matrix @ T
        self._type = None

    def scale(self, ratio):
        if ratio == 0:
            raise ValueError("Scale ratio cannot be zero")
        # Substitute x → x/ratio, y → y/ratio (so the curve scales by ratio).
        S = np.diag([1 / ratio, 1 / ratio, 1]).astype(float)
        self.matrix = S.T @ self.matrix @ S
        self._type = None

    def ggb_frame(self):
        """GeoGebra's own frame of this conic — the one its path parameter
        (``Point(conic, t)``) is measured in.

        Port of ``GeoConicND.classifyConic`` in the default non-continuous
        mode: ``{'type', 'center', 'e0', 'e1', 'half_axes' | 'p'}`` where
        ``center`` is the midpoint (the vertex for a parabola) and a point
        with frame coordinates ``(u, v)`` is ``center + u·e0 + v·e1``.
        Unlike :meth:`as_ellipse`, the first axis and its sign follow
        GeoGebra (a tall ellipse gets ``e0 = (0, 1)``), and they depend on the
        sign of the matrix as GeoGebra's do. ``None`` for degenerate conics.
        """
        M = self.matrix
        A0, A1, A2 = float(M[0, 0]), float(M[1, 1]), float(M[2, 2])
        A3, A4, A5 = float(M[0, 1]), float(M[0, 2]), float(M[1, 2])
        if abs(A0 * A1 - A3 * A3) < _GGB_EPS:
            return self._ggb_parabola_frame(A0, A1, A2, A3, A4, A5)

        det_s = A0 * A1 - A3 * A3
        if abs(A3) < _GGB_EPS:
            ev = [A0, A1]
            ex, ey = 1.0, 0.0
        else:
            ev = _ggb_solve_quadratic(det_s, -(A0 + A1), 1.0)
            if not ev:
                return None
            if len(ev) == 1:
                ev = [ev[0], ev[0]]
            ex, ey = -A3, -ev[0] + A0
        bx = (A3 * A5 - A1 * A4) / det_s
        by = (A3 * A4 - A0 * A5) / det_s
        beta = A4 * bx + A5 * by + A2
        if abs(beta) < _GGB_EPS:
            return None                          # single point / line pair
        mu = [-ev[0] / beta, -ev[1] / beta]
        if det_s < 0:
            kind = 'hyperbola'
            if mu[0] < 0:
                mu = [mu[1], mu[0]]
                ex, ey = -ey, ex
            half_axes = (np.sqrt(1.0 / mu[0]), np.sqrt(-1.0 / mu[1]))
        else:
            if not (mu[0] > 0 and mu[1] > 0):
                return None                      # empty
            if abs(mu[0] / mu[1] - 1.0) < _GGB_EPS:
                kind = 'circle'
                ex, ey = 1.0, 0.0
            else:
                kind = 'ellipse'
                if mu[0] > mu[1]:
                    mu = [mu[1], mu[0]]
                    ex, ey = -ey, ex
            half_axes = (np.sqrt(1.0 / mu[0]), np.sqrt(1.0 / mu[1]))
        e0 = np.array([ex, ey]) / np.hypot(ex, ey)
        return {'type': kind, 'center': np.array([bx, by]), 'e0': e0,
                'e1': np.array([-e0[1], e0[0]]), 'half_axes': half_axes}

    def _ggb_parabola_frame(self, A0, A1, A2, A3, A4, A5):
        if abs(A3) < _GGB_EPS:
            if abs(A0) < _GGB_EPS:
                if abs(A1) < _GGB_EPS:
                    return None
                lam, ex, ey = A1, 1.0, 0.0
            else:
                lam, ex, ey = A0, 0.0, 1.0
        else:
            lam = A0 + A1
            length = np.hypot(A3, A0)
            ex, ey = A3 / length, -A0 / length
        hint = self.ggb_axis_hint
        if hint is not None and ex * hint[0] + ey * hint[1] < 0:
            ex, ey = -ex, -ey                    # GeoGebra's "avoid flip"
        cx = A4 * ex + A5 * ey
        cy = A5 * ex - A4 * ey
        if abs(cx) < _GGB_EPS:
            return None                          # line pair / empty
        t2 = cy / lam
        t1 = (cy * t2 - A2) / (2.0 * cx)
        vertex = np.array([ey * t2 + ex * t1, ey * t1 - ex * t2])
        e1 = np.array([-ey, ex])                 # set before the p-sign flip
        p = -cx / lam
        e0 = np.array([ex, ey])
        if p < 0:
            e0, p = -e0, -p
        return {'type': 'parabola', 'center': vertex, 'e0': e0, 'e1': e1, 'p': p}

    def equivalent(self, other):
        """Two conics are equivalent iff their matrices are proportional."""
        if not isinstance(other, Conic):
            return False
        a = self.matrix.flatten()
        b = other.matrix.flatten()
        idx = int(np.argmax(np.abs(a)))
        if abs(a[idx]) < _TOL:
            return bool(np.allclose(b, 0))
        if abs(b[idx]) < _TOL:
            return False
        return bool(np.allclose(b * a[idx], a * b[idx]))

    def __repr__(self):
        return f"Conic({self.type.value})"

    # ── Classification ─────────────────────────────────────────────────

    @property
    def type(self) -> ConicType:
        if self._type is None:
            self._type = self._classify()
        return self._type

    def is_degenerate(self) -> bool:
        return self.type in (
            ConicType.INTERSECTING_LINES, ConicType.PARALLEL_LINES,
            ConicType.DOUBLE_LINE, ConicType.POINT, ConicType.EMPTY,
        )

    def _classify(self) -> ConicType:
        scale = float(np.max(np.abs(self.matrix)))
        if scale == 0:
            return ConicType.EMPTY

        Mn = self.matrix / scale
        M33 = Mn[:2, :2]
        det_M33 = float(np.linalg.det(M33))
        rank_M = int(np.linalg.matrix_rank(Mn, tol=_TOL))

        if rank_M == 3:
            # Non-degenerate.
            if det_M33 > _TOL:
                # Ellipse vs imaginary ellipse: real iff trace(M33)·det(M) < 0.
                if np.trace(M33) * np.linalg.det(Mn) < 0:
                    # Circle when A0 = A1 and B = 0.
                    if (abs(Mn[0, 0] - Mn[1, 1]) < _TOL
                            and abs(Mn[0, 1]) < _TOL):
                        return ConicType.CIRCLE
                    return ConicType.ELLIPSE
                return ConicType.EMPTY
            if det_M33 < -_TOL:
                return ConicType.HYPERBOLA
            return ConicType.PARABOLA

        if rank_M == 2:
            if det_M33 < -_TOL:
                return ConicType.INTERSECTING_LINES
            if det_M33 > _TOL:
                # Two imaginary conjugate lines crossing at a real point.
                return ConicType.POINT
            # det_M33 ≈ 0: parallel / double / empty.
            return self._classify_parallel_family()

        # rank_M ≤ 1: one double line (or trivial).
        return ConicType.DOUBLE_LINE

    def _classify_parallel_family(self) -> ConicType:
        """Resolve the rank(M)=2, det(M₃₃)=0 case."""
        lines = self._decompose_parallel_family()
        if lines is None:
            # Inconsistency: likely should have been a parabola.
            return ConicType.PARABOLA
        if len(lines) == 2:
            return ConicType.PARALLEL_LINES
        if len(lines) == 1:
            return ConicType.DOUBLE_LINE
        return ConicType.EMPTY

    # ── Canonical parametrizations (non-degenerate) ────────────────────

    def as_circle(self):
        """If CIRCLE, return (center ndarray, radius float). Else None."""
        if self.type != ConicType.CIRCLE:
            return None
        A = self.matrix[0, 0]
        cx = -self.matrix[0, 2] / A
        cy = -self.matrix[1, 2] / A
        r_sq = cx * cx + cy * cy - self.matrix[2, 2] / A
        if r_sq < 0:
            return None
        return np.array([cx, cy]), float(np.sqrt(r_sq))

    def as_ellipse(self):
        """If ELLIPSE or CIRCLE, return dict(center, semi_axes, rotation).

        semi_axes = (a, b) are the semi-diameters along rotation-angle
        and rotation+π/2 respectively, with a ≥ b.
        """
        if self.type not in (ConicType.ELLIPSE, ConicType.CIRCLE):
            return None
        params = self._centered_axes_form()
        if params is None:
            return None
        # Convention: a ≥ b for ellipse.
        a, b = params['semi_axes']
        rot = params['rotation']
        if a < b:
            a, b = b, a
            rot = (rot + np.pi / 2) % np.pi
        return {'center': params['center'], 'semi_axes': (a, b), 'rotation': rot}

    def as_hyperbola(self):
        """If HYPERBOLA, return dict(center, semi_axes, rotation).

        semi_axes = (a, b) where a is the transverse half-axis (along
        rotation direction) and b is the conjugate half-axis.
        """
        if self.type != ConicType.HYPERBOLA:
            return None
        return self._centered_axes_form(hyperbolic=True)

    def _centered_axes_form(self, hyperbolic=False):
        """Shared centered-and-rotated canonical form for central conics.

        Returns {center, semi_axes, rotation} after:
        1. Solve M₃₃·center = −[D, E] for center.
        2. Translate to origin.
        3. Diagonalize the 2×2 quadratic block.
        4. For hyperbola, swap eigenvectors so first semi-axis is real.
        """
        M33 = self.matrix[:2, :2]
        rhs = -self.matrix[:2, 2]
        try:
            center = np.linalg.solve(M33, rhs)
        except np.linalg.LinAlgError:
            return None

        Tc = np.eye(3)
        Tc[0, 2] = center[0]
        Tc[1, 2] = center[1]
        M_centered = Tc.T @ self.matrix @ Tc

        eigvals, eigvecs = np.linalg.eigh(M_centered[:2, :2])
        K = M_centered[2, 2]

        a_sq = -K / eigvals[0]
        b_sq = -K / eigvals[1]

        if hyperbolic:
            # Put the positive semi-axis squared first (transverse axis).
            if a_sq < 0 < b_sq:
                a_sq, b_sq = b_sq, a_sq
                eigvecs = eigvecs[:, ::-1]

        a = float(np.sqrt(abs(a_sq)))
        b = float(np.sqrt(abs(b_sq)))
        rotation = float(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
        # Wrap rotation into [0, π) — direction of first eigvec doesn't matter.
        rotation = rotation % np.pi

        return {
            'center': center,
            'semi_axes': (a, b),
            'rotation': rotation,
        }

    def as_parabola(self):
        """If PARABOLA, return dict(vertex, axis, perp, focal_parameter).

        - vertex: point of the parabola's extreme (numpy shape (2,)).
        - axis: unit vector in the direction of opening.
        - perp: unit vector perpendicular to axis (the transverse direction).
        - focal_parameter: p in the canonical equation y² = 4 p x (always > 0).
        """
        if self.type != ConicType.PARABOLA:
            return None

        M33 = self.matrix[:2, :2]
        eigvals, eigvecs = np.linalg.eigh(M33)
        # Non-zero eigenvalue first by magnitude.
        if abs(eigvals[0]) < abs(eigvals[1]):
            eigvals = eigvals[::-1]
            eigvecs = eigvecs[:, ::-1]
        lam = eigvals[0]
        e_perp = eigvecs[:, 0]   # direction of quadratic variation
        e_axis = eigvecs[:, 1]   # kernel direction — parabola's opening axis

        D = self.matrix[0, 2]
        E = self.matrix[1, 2]
        F = self.matrix[2, 2]
        D_rot = e_perp[0] * D + e_perp[1] * E
        E_rot = e_axis[0] * D + e_axis[1] * E

        if abs(E_rot) < _TOL:
            return None  # Should not happen for a true parabola.

        # In (ũ, ṽ) = (e_perp·p, e_axis·p):
        #   lam·ũ² + 2·D_rot·ũ + 2·E_rot·ṽ + F = 0
        # complete the square → (ũ + D_rot/lam)² = -(2 E_rot / lam)·(ṽ − v_vertex)
        u_v = -D_rot / lam
        v_v = -(F - D_rot ** 2 / lam) / (2 * E_rot)
        vertex = u_v * e_perp + v_v * e_axis

        p = abs(E_rot) / (2 * abs(lam))
        # Open in direction of +ṽ iff -(2 E_rot / lam) > 0, i.e., E_rot/lam < 0.
        sign_open = -1.0 if (E_rot / lam) > 0 else 1.0
        axis = sign_open * e_axis

        return {
            'vertex': vertex,
            'axis': axis,
            'perp': e_perp,
            'focal_parameter': float(p),
        }

    # ── Canonical parametrizations (degenerate) ────────────────────────

    def as_lines(self) -> Optional[List[Line]]:
        """For degenerate conics, return the line components as Line objects.

        Returns:
            - 2 lines for INTERSECTING_LINES and PARALLEL_LINES
            - 1 line for DOUBLE_LINE
            - [] for POINT and EMPTY
            - None for non-degenerate conics
        """
        t = self.type
        if t == ConicType.INTERSECTING_LINES:
            return self._decompose_intersecting_lines()
        if t in (ConicType.PARALLEL_LINES, ConicType.DOUBLE_LINE):
            return self._decompose_parallel_family() or []
        if t in (ConicType.POINT, ConicType.EMPTY):
            return []
        return None

    def as_point(self) -> Optional[Point]:
        """If POINT type, return the single real intersection point."""
        if self.type != ConicType.POINT:
            return None
        M33 = self.matrix[:2, :2]
        try:
            center = np.linalg.solve(M33, -self.matrix[:2, 2])
        except np.linalg.LinAlgError:
            return None
        return Point(center)

    def _decompose_intersecting_lines(self) -> Optional[List[Line]]:
        """rank(M)=2, det(M₃₃) < 0 → two real intersecting lines.

        Diagonalize M = Σ λᵢ vᵢ vᵢᵀ and use the signature-(+,−,0)
        factorization
            M = (√λ₁ v₁ + √(−λ₂) v₂)·(√λ₁ v₁ − √(−λ₂) v₂)ᵀ (symmetrized)
        where λ₁ > 0 > λ₂.
        """
        eigvals, eigvecs = np.linalg.eigh(self.matrix)
        order = np.argsort(-np.abs(eigvals))
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        lam1, lam2 = eigvals[0], eigvals[1]
        v1 = eigvecs[:, 0]
        v2 = eigvecs[:, 1]

        if lam1 * lam2 >= 0:
            return None
        if lam1 < 0:
            lam1, lam2 = lam2, lam1
            v1, v2 = v2, v1

        s1 = np.sqrt(lam1)
        s2 = np.sqrt(-lam2)
        lines = []
        for n_full in (s1 * v1 + s2 * v2, s1 * v1 - s2 * v2):
            n = n_full[:2]
            c = -n_full[2]
            if np.linalg.norm(n) > _TOL:
                lines.append(Line(n, c))
        return lines

    def _decompose_parallel_family(self) -> Optional[List[Line]]:
        """rank(M)≤2, det(M₃₃)=0 → parallel / double / empty.

        Rotate so M₃₃ is diagonal with non-zero eigenvalue λ and kernel
        direction e_axis. In rotated coords:
            λ·ũ² + 2·D_rot·ũ + 2·E_rot·ṽ + F = 0
        For this family (not parabola) E_rot must be 0, reducing to a
        quadratic in ũ alone:
            ũ = (−D_rot ± √(D_rot² − λ·F)) / λ

        The special case M₃₃ = 0 (happens as a degenerate pencil member
        in Conic ∩ Conic) collapses to a single linear equation
        ``2·D·x + 2·E·y + F = 0``; returned as one Line.
        """
        M33 = self.matrix[:2, :2]
        eigvals, eigvecs = np.linalg.eigh(M33)
        if abs(eigvals[0]) >= abs(eigvals[1]):
            lam = eigvals[0]
            u_hat = eigvecs[:, 0]
            perp_hat = eigvecs[:, 1]
        else:
            lam = eigvals[1]
            u_hat = eigvecs[:, 1]
            perp_hat = eigvecs[:, 0]

        D = self.matrix[0, 2]
        E = self.matrix[1, 2]
        F = self.matrix[2, 2]

        if abs(lam) < _TOL:
            # M₃₃ is the zero matrix. The "conic" is really a single
            # line:  2·D·x + 2·E·y + F = 0.
            if abs(D) < _TOL and abs(E) < _TOL:
                return []
            return [Line([D, E], -F / 2)]
        D_rot = u_hat[0] * D + u_hat[1] * E
        E_rot = perp_hat[0] * D + perp_hat[1] * E

        scale = max(np.max(np.abs(self.matrix)), _TOL)
        if abs(E_rot) > _TOL * scale:
            # Non-zero E_rot means this is actually a parabola.
            return None

        disc = D_rot * D_rot - lam * F
        if disc < -_TOL * scale * scale:
            return []
        if disc < _TOL * scale * scale:
            return [Line(u_hat, -D_rot / lam)]

        sqrt_disc = np.sqrt(disc)
        t_plus = (-D_rot + sqrt_disc) / lam
        t_minus = (-D_rot - sqrt_disc) / lam
        return [Line(u_hat, t_plus), Line(u_hat, t_minus)]
