"""Explicit function y = f(x) as a first-class geometry element.

A Function stores a sympy expression for the dependent variable together
with a fast numerical callable produced by ``sympy.lambdify``. Only the
parsing and classification pass uses sympy — rendering and intersections
use the numpy callable, so there is no sympy in the hot path.

Scope (PR 6): explicit y = f(x) only, smooth sub-domains. Piecewise
expressions (``If[cond, expr]`` from GeoGebra, ``Piecewise`` from
sympy) and asymptote-aware splitting are handled in PR 7.
"""
import logging
import re
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import sympy as sp

from ..constants import Z_LINE
from .formula_refs import (
    coordinate_calls, substitute_references, unbound_references,
)
from .safe_sympify import check_length, normalize_formula_text, safe_sympify


logger = logging.getLogger(__name__)


# Characters stripped from GGB expressions that sympy can't parse.
_GGB_CLEANUPS = (
    ('^', '**'),      # GGB power → Python
    ('≤', '<='),      # Unicode comparators used in GGB conditionals
    ('≥', '>='),
    ('≠', '!='),
)

# Sympy lookup for functions. Maps the lower-case name (as the expression
# uses) to the sympy callable.
_SYMPY_FUNCS = {
    'abs': sp.Abs,
    'sqrt': sp.sqrt,
    'sin': sp.sin,  'cos': sp.cos,  'tan': sp.tan,
    'asin': sp.asin, 'acos': sp.acos, 'atan': sp.atan,
    'sinh': sp.sinh, 'cosh': sp.cosh, 'tanh': sp.tanh,
    # GeoGebra and NumPy spellings of the same functions.
    'arcsin': sp.asin, 'arccos': sp.acos, 'arctan': sp.atan,
    'asinh': sp.asinh, 'acosh': sp.acosh, 'atanh': sp.atanh,
    'arcsinh': sp.asinh, 'arccosh': sp.acosh, 'arctanh': sp.atanh,
    'sgn': sp.sign, 'sign': sp.sign, 'ceil': sp.ceiling, 'floor': sp.floor,
    'exp': sp.exp,
    'log': sp.log, 'ln': sp.log,
    'lg': lambda v: sp.log(v, 10), 'log10': lambda v: sp.log(v, 10),
    'ld': lambda v: sp.log(v, 2), 'log2': lambda v: sp.log(v, 2),
    'pi': sp.pi, 'e': sp.E,
    'Piecewise': sp.Piecewise,
    'nan': sp.nan,
    'true': sp.true, 'false': sp.false,
}


def _strip_label_prefix(s: str) -> str:
    """Remove GGB's leading ``label:`` tag (e.g. ``"i: y = -|x| + 4"``)."""
    m = re.match(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*(.*)$', s)
    if m:
        return m.group(1)
    return s


def _normalize_expression(s: str) -> str:
    """Apply GGB → sympy string rewrites that don't need the AST."""
    for old, new in _GGB_CLEANUPS:
        s = s.replace(old, new)
    s = _translate_if_to_piecewise(s)
    s = _rewrite_chain_comparisons(s)
    return s


# Pattern: `A OP1 B OP2 C` — a chained relational. Sympy sympify calls
# Python's bool() on `A OP1 B` when it sees the chain, which errors out
# on symbolic relationals. We expand to `((A OP1 B) & (B OP2 C))` so the
# result parses as a conjunction of two comparisons.
#
# The character classes deliberately exclude logical connectives and
# brackets so the pattern stays within one relational subexpression.
#
# A coordinate ``xcoord(A)`` (see ``formula_refs``) is one operand:
# ``x(A) ≤ x ≤ x(B)`` — a graph between two points; so is ``exp(1)``, the
# ℯ of ``ℯ ≤ x ≤ 3`` (see ``normalize_formula_text``).
_CHAIN_OPERAND = r'(?:[xy]coord\(\s*\w+\s*\)|exp\(1\)|[^<>=&|(),])'
_CHAIN_COMP_RE = re.compile(
    rf'({_CHAIN_OPERAND}+?)\s*(<=|>=|<|>)\s*({_CHAIN_OPERAND}+?)\s*(<=|>=|<|>)'
    rf'\s*({_CHAIN_OPERAND}+)'
)


def _rewrite_chain_comparisons(s: str) -> str:
    """Rewrite chained comparisons like ``a <= x <= b`` into
    ``((a <= x) & (x <= b))`` so sympy can parse them as conjunctions.

    Applied repeatedly until the string stabilizes — handles longer
    chains (rare in practice) by pairwise expansion.
    """
    for _ in range(5):
        new_s = _CHAIN_COMP_RE.sub(
            lambda m: (
                f'(({m.group(1).strip()} {m.group(2)} {m.group(3).strip()}) '
                f'& ({m.group(3).strip()} {m.group(4)} {m.group(5).strip()}))'
            ),
            s,
        )
        if new_s == s:
            break
        s = new_s
    return s


def _split_top_level_commas(s: str) -> List[str]:
    """Split on commas at bracket-depth 0 — respects nested [], ()."""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in s:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return parts


def _find_matching_bracket(s: str, open_index: int) -> int:
    """Return the index just after the matching bracket, or ``-1``."""
    pairs = {'[': ']', '(': ')'}
    opener = s[open_index]
    if opener not in pairs:
        return -1
    stack = [pairs[opener]]
    j = open_index + 1
    while j < len(s) and stack:
        ch = s[j]
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in (']', ')'):
            if ch != stack[-1]:
                return -1
            stack.pop()
        j += 1
    return j if not stack else -1


def _translate_if_to_piecewise(s: str) -> str:
    """Rewrite GGB ``If[cond, then]`` / ``If[cond, then, else]`` as
    sympy ``Piecewise((then, cond), (fallback, True))``.

    Recursive: handles nested ``If[]`` at any depth. Works by
    bracket-matching rather than regex so conditions can contain
    balanced brackets ("If[0 ≤ x ≤ 1, f(x)]"). Also accepts ``If(...)``
    because the GeoGebra XML converter normalizes square brackets to
    parentheses before function parsing in some import paths.
    """
    out: List[str] = []
    i = 0
    n = len(s)
    while i < n:
        # Match "If[" or "If(" (word-boundary check — don't match inside names).
        if (
            s[i:i + 2] == 'If'
            and i + 2 < n
            and s[i + 2] in '[('
            and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == '_'))
        ):
            j = _find_matching_bracket(s, i + 2)
            if j < 0:
                out.append(s[i])
                i += 1
                continue
            inner = s[i + 3:j - 1]
            args = [_translate_if_to_piecewise(a.strip())
                    for a in _split_top_level_commas(inner)]
            if len(args) == 2:
                cond, then = args
                out.append(f"Piecewise(({then}, {cond}), (nan, True))")
            elif len(args) == 3:
                cond, then, else_ = args
                out.append(f"Piecewise(({then}, {cond}), ({else_}, True))")
            else:
                # Unsupported arity — leave as-is; sympify will complain loudly.
                out.append(s[i:j])
            i = j
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


_DEFINITION_LHS_RE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*([A-Za-z_]\w*)\s*\)\s*$')


def _split_definition(expr_str: str) -> Tuple[str, Optional[str]]:
    """``(rhs, variable)`` of ``y = ...`` / ``f(t) = ...`` / a bare ``...``;
    ``variable`` is the one named on the left (``t``), else ``None``."""
    if '=' not in expr_str:
        return expr_str, None
    lhs, rhs = expr_str.split('=', 1)
    # For other left sides ("2*x = y") solving for the free var is the
    # caller's problem: the right-hand side is taken anyway.
    m = _DEFINITION_LHS_RE.match(lhs)
    return rhs.strip(), (m.group(1) if m else None)


def parse_function_expression(
    raw: str, var_name: str = 'x'
) -> Tuple[sp.Expr, sp.Symbol]:
    """Parse a function-expression string into ``(sympy_expr, symbol)``.

    Accepts forms:
      - ``"x^2 + 1"``
      - ``"y = x^2 + 1"``
      - ``"f(x) = sin(x)"``
      - ``"g(t) = t^2"`` — the variable named on the left is renamed to
        ``var_name``, so the result is ``x**2``
      - ``"i: y = -abs(x) + 4"`` (GGB label-prefixed)

    ``x(A)`` / ``y(A)`` are coordinates of ``A``, never the variable (see
    ``formula_refs``). Raises ``ValueError`` when sympy can't parse the RHS.
    """
    check_length(raw)
    text = _strip_label_prefix(normalize_formula_text(raw))
    text, refs = coordinate_calls(text)
    text = _normalize_expression(text)
    text, lhs_var = _split_definition(text)
    name = lhs_var or var_name
    var = sp.Symbol(name)
    try:
        expr = safe_sympify(text, {**_SYMPY_FUNCS, name: var, **refs})
    except (sp.SympifyError, SyntaxError, TypeError) as e:
        raise ValueError(f"could not parse function expression {raw!r}: {e}")
    if name != var_name:
        target = sp.Symbol(var_name)
        if target in expr.free_symbols:
            raise ValueError(
                f"function expression {raw!r} of {name} also mentions {var_name}")
        expr = expr.xreplace({var: target})
        var = target
    return expr, var


# A periodic function has infinitely many singularities: sympy gives those
# of tan(x) as ``ImageSet(Lambda(n, 2nπ + π/2), Integers) ∪ …``, and
# iterating that set never ends. Of each such family only the real members
# within this distance of the origin are kept, at most _FAMILY_MEMBERS of
# them (those of the smallest |n|).
SINGULARITY_WINDOW = 1000.0
_FAMILY_MEMBERS = 1000


def real_singularities(sings) -> List[float]:
    """Sorted finite real points of a sympy set of singularities: every
    point of a finite set, the members of periodic families (ImageSets
    over the integers) within :data:`SINGULARITY_WINDOW`; other sets — a
    ``ConditionSet`` sympy could not solve — contribute nothing."""
    values: List[complex] = []
    for part in (sings.args if isinstance(sings, sp.Union) else (sings,)):
        if isinstance(part, sp.FiniteSet):
            for s in part.args:
                try:
                    values.append(complex(s))
                except (TypeError, ValueError):
                    continue
        elif (isinstance(part, sp.ImageSet) and part.base_sets == (sp.S.Integers,)
              and len(part.lamda.variables) == 1):
            values.extend(_family_members(part.lamda))
    out = sorted(
        v.real for v in values
        if abs(v.imag) <= 1e-9 and np.isfinite(v.real)
        and abs(v.real) <= SINGULARITY_WINDOW
    )
    unique: List[float] = []
    for v in out:
        if not unique or v - unique[-1] > 1e-9 * max(1.0, abs(v)):
            unique.append(float(v))
    return unique


def _family_members(lamda) -> List[complex]:
    half = _FAMILY_MEMBERS // 2
    ns = np.arange(-half, _FAMILY_MEMBERS - half).astype(complex)
    try:
        f = sp.lambdify(lamda.variables[0], lamda.expr, modules='numpy')
        with np.errstate(all='ignore'):
            vals = np.broadcast_to(np.asarray(f(ns), dtype=complex), ns.shape)
    except Exception:
        return []
    return list(vals)


class Function:
    """Explicit y = f(x) curve.

    Attributes:
        expr: sympy expression for the dependent variable.
        var: sympy symbol for the independent variable.
        original: the raw string this was built from (for debugging/repr).
        natural_singularities: sorted list of real finite points where
            the expression is undefined (division by zero, log of 0…).
            Used by the renderer in PR 7 to split the sampling range.
        explicit_domain: optional user-provided ``(x_min, x_max)`` —
            overrides the renderer's default viewport-driven range.
    """

    def __init__(
        self,
        expr,
        var: Optional[sp.Symbol] = None,
        *,
        source: Optional[str] = None,
        domain: Optional[Tuple[float, float]] = None,
    ):
        if isinstance(expr, str):
            parsed, sym = parse_function_expression(expr, 'x' if var is None else var.name)
            self.expr = parsed
            self.var = sym
            self.source = expr
        else:
            if var is None:
                free = list(expr.free_symbols)
                if len(free) != 1:
                    raise ValueError(
                        f"Function expression has {len(free)} free symbols; "
                        "explicit `var` required"
                    )
                var = free[0]
            self.expr = expr
            self.var = var
            self.source = source or str(expr)

        self.explicit_domain = domain
        self.natural_singularities = self._compute_singularities()

        self._callable = sp.lambdify(
            self.var, self.expr, modules=['numpy', {'Abs': np.abs}],
        )

        from ..style.proxy import StyleProxy
        self.style = StyleProxy()
        self.style['fill_opacity'] = 0
        self.style['z_index'] = Z_LINE

    # ── Human-friendly accessors ──
    @property
    def expression(self): return self.expr
    @property
    def variable(self): return self.var
    @property
    def callable(self): return self._callable

    # ── Construction helpers ──────────────────────────────────────────

    @classmethod
    def from_string(
        cls,
        raw: str,
        var_name: str = 'x',
        parameters: Optional[Mapping[str, float]] = None,
    ) -> 'Function':
        expr, sym = parse_function_expression(raw, var_name)
        if parameters:
            # A boolean stays a boolean: ``If(b, …)`` needs one.
            expr = substitute_references(
                expr, {k: v for k, v in parameters.items() if str(k) != sym.name})
        unbound = unbound_references(expr, {sym})
        if unbound:
            # lambdify would build a callable that fails on every call.
            raise ValueError(
                f"function expression {raw!r} has unbound names {unbound}")
        return cls(expr, sym, source=raw)

    # ── Evaluation ────────────────────────────────────────────────────

    def __call__(self, x):
        """Numeric evaluation. Silently maps domain errors to NaN so the
        viewport-aware sampler can break polylines at undefined regions.
        """
        try:
            v = self._callable(x)
        except (ValueError, ZeroDivisionError, FloatingPointError):
            return float('nan')
        # lambdify may return complex when the expression passes through
        # negative-arg sqrt/log on a real input. Treat as undefined.
        if isinstance(v, complex):
            if abs(v.imag) < 1e-12:
                return float(v.real)
            return float('nan')
        return v

    # ── Sampling ──────────────────────────────────────────────────────

    def sample(
        self, x_range: Tuple[float, float], n: int = 200,
    ) -> np.ndarray:
        """Return an ``(n, 2)`` array of ``(x, f(x))`` for uniform x.

        Cheap baseline for quick inspection; production rendering goes
        through ``curve_sampling.sample_parametric`` for adaptive,
        viewport-aware output.
        """
        xs = np.linspace(x_range[0], x_range[1], n)
        ys = np.array([self(float(x)) for x in xs], dtype=float)
        return np.column_stack([xs, ys])

    # ── Inspection helpers ────────────────────────────────────────────

    def _compute_singularities(self) -> List[float]:
        """Return finite real x where the expression is undefined.

        Uses ``sympy.singularities`` and discards complex/infinite
        values (see :func:`real_singularities` for periodic ones). Never
        raises — an opaque expression simply returns an empty list.
        """
        try:
            sings = sp.singularities(self.expr, self.var)
        except Exception:
            return []
        return real_singularities(sings)

    # ── Standard element protocol ─────────────────────────────────────

    def contains(self, point) -> bool:
        p = np.asarray(point)
        try:
            return bool(np.isclose(float(self(p[0])), float(p[1])))
        except Exception:
            return False

    def translate(self, vec):
        dx, dy = float(vec[0]), float(vec[1])
        x = self.var
        self.expr = self.expr.subs(x, x - dx) + dy
        self._callable = sp.lambdify(
            self.var, self.expr, modules=['numpy', {'Abs': np.abs}],
        )
        self.natural_singularities = self._compute_singularities()

    def scale(self, ratio):
        if ratio == 0:
            raise ValueError("Scale ratio cannot be zero")
        x = self.var
        self.expr = ratio * self.expr.subs(x, x / ratio)
        self._callable = sp.lambdify(
            self.var, self.expr, modules=['numpy', {'Abs': np.abs}],
        )
        self.natural_singularities = self._compute_singularities()

    def equivalent(self, other) -> bool:
        if not isinstance(other, Function):
            return False
        try:
            return bool(sp.simplify(self.expr - other.expr) == 0)
        except Exception:
            return False

    def __repr__(self):
        return f"Function(y = {self.expr})"
