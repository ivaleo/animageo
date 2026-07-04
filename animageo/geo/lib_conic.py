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
from enum import Enum
from typing import Optional, List
import numpy as np

from .lib_elements import Line, Point
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
    def from_string(cls, equation: str) -> 'Conic':
        """Parse a conic equation string into the matrix form.

        Accepts the GGB-style equation forms:
            "x^2 + y^2 = 4"
            "y = x^2 - 1"
            "x^2 + 2·x·y + y^2 − 4 = 0"
            "g: x^2 + y^2 = 4"   (label prefix tolerated)

        Raises ``ValueError`` if sympy can't parse the expression or the
        expanded polynomial exceeds degree 2 (not a conic).
        """
        import re as _re
        import sympy as sp

        text = _re.sub(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*', '', equation)
        text = text.replace('^', '**')
        if '=' in text:
            lhs, rhs = text.split('=', 1)
            text = f"({lhs.strip()}) - ({rhs.strip()})"

        x = sp.Symbol('x')
        y = sp.Symbol('y')
        try:
            expr = sp.expand(sp.sympify(text, locals={'x': x, 'y': y}))
        except (sp.SympifyError, SyntaxError, TypeError) as e:
            raise ValueError(f"could not parse conic equation {equation!r}: {e}")

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
