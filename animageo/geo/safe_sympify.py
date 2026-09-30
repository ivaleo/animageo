"""Parse formula text from a file with sympy without handing it Python.

``sympy.sympify(text)`` evaluates the text with Python's ``eval`` in a
namespace that includes builtins such as ``__import__``; a .ggb file is
untrusted input (the web service parses uploads). Formula text needs
arithmetic, names and calls only, so text with dunders, quotes, attribute
access or statements is refused, and the evaluation namespace is sympy's
public names plus the few builtins a formula can mean — no ``__builtins__``.

Parsing also evaluates, and sympy evaluates exactly: ``7^(9^9)`` or
``factorial(10^7)`` would take minutes. So a formula calls only math
functions (:data:`MATH_FUNCTIONS`; any other name it calls is an object of
the construction), every power and factorial is checked for size before it
is computed, and the text length is bounded.
"""
import ast
import builtins
import keyword
import re
from tokenize import NAME, NUMBER, OP, TokenError

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor, standard_transformations, stringify_expr,
)

_UNSAFE = re.compile(
    r"__|['\"`;\\@]|\.\s*[A-Za-z_]"
    r"|\b(?:lambda|import|exec|eval|compile|open|globals|locals|vars"
    r"|getattr|setattr|delattr|breakpoint|input)\b"
)


def _implicit_products(tokens, local_dict, global_dict):
    """Insert the ``*`` a formula may leave out, only where Python would fail:
    ``2x``, ``2 x``, ``k x``, ``2(x + 1)``, ``(x + 1)(x − 1)``, ``(x + 1) x``,
    and ``x (x + 1)`` where ``x`` is a symbol of the formula (not a function:
    ``g(x)``, ``sin(x)``, ``xcoord(A)`` stay calls)."""
    result = []
    for tok in tokens:
        if result and _implied_product(result[-1], tok, local_dict):
            result.append((OP, '*'))
        result.append(tok)
    return result


def _is_word(tok):
    return tok[0] == NAME and not keyword.iskeyword(tok[1])


def _implied_product(left, right, local_dict):
    if not (left[0] == NUMBER or left in ((OP, ')'), (OP, '!'))
            or _is_word(left)):
        return False
    if _is_word(right):
        return True
    if right[0] == NUMBER:
        return left[0] != NUMBER
    if right == (OP, '('):
        if left[0] == NAME:
            return isinstance(local_dict.get(left[1]), sp.Expr)
        return True
    return False


_TRANSFORMATIONS = ((_implicit_products,) + standard_transformations
                    + (convert_xor,))

MAX_LENGTH = 4000


def check_length(text):
    """``ValueError`` for formula text longer than :data:`MAX_LENGTH` —
    parsers call it first, as their text rewriting is not linear either."""
    if len(text) > MAX_LENGTH:
        raise ValueError(f'formula longer than {MAX_LENGTH} characters')


# Typographic characters GeoGebra shows (and a copied formula keeps). π and
# ℯ become what means the constant in every parser — ``e`` is an ordinary
# name in a conic, ``E`` may be a point — padded with spaces, so ``2π``,
# ``πx``, ``sin(πx)``, ``2ℯ`` stay implicit products and ``πx(A)`` still
# reads the coordinate of ``A``.
_TYPOGRAPHIC = str.maketrans({
    '−': '-',              # − minus sign
    '·': '*',              # · middle dot
    '⋅': '*',              # ⋅ dot operator
    '×': '*',              # × multiplication sign
    '÷': '/',              # ÷ division sign
    'π': ' pi ',           # π
    'ℯ': ' exp(1) ',       # ℯ
})


def normalize_formula_text(text):
    """Formula text with typographic characters replaced by what the
    parsers read. Every entry point that looks at formula text — the
    parsers and the passes that find the names a formula mentions — calls
    it before its first regular expression."""
    return text.translate(_TYPOGRAPHIC)


# The sympy functions a formula may call; the caller's ``local_dict`` adds
# its own. Any other called name — ``k(x + 1)``, ``g(t)``, ``N(x)`` — is an
# undefined function, i.e. an object of the construction, even where sympy
# has that name (``N``, ``S``, ``solve``, ``fibonacci``).
MATH_FUNCTIONS = frozenset('''
    sin cos tan cot sec csc asin acos atan acot asec acsc atan2
    sinh cosh tanh coth sech csch asinh acosh atanh acoth asech acsch
    exp log ln sqrt cbrt root real_root Abs abs sign floor ceiling frac
    re im arg conjugate Max Min max min pow round Piecewise Heaviside
    erf erfc gamma
'''.split())

# Names the parser's own generated code calls (numbers, auto-symbols, ``n!``).
# In the text they are refused: ``Float(1, 10^9)`` asks for a billion digits.
_GENERATED = frozenset({'Symbol', 'Function', 'Integer', 'Float', 'Rational'})

_NAME = re.compile(r'[^\W\d]\w*')
_OPEN = re.compile(r'\s*\(')


def _text_names(text, local_dict):
    """Symbols for the names ``text`` uses as values and undefined functions
    for the names it calls that are not math functions; names the caller
    defines are left alone."""
    names = {}
    for m in _NAME.finditer(text):
        name = m.group()
        if name in local_dict or keyword.iskeyword(name):
            continue
        if name in _GENERATED:
            raise _Refused(f'{name} is not a formula name')
        if not _OPEN.match(text, m.end()):
            names[name] = sp.Symbol(name)
        elif name not in MATH_FUNCTIONS and name not in names:
            names[name] = sp.Function(name)
    return names


# Sympy evaluates numbers exactly, so a short formula can ask for a huge
# computation. Each way found is bounded where it starts:
# - an exact power: bits of the result (some 30 000 digits);
_MAX_POWER_BITS = 100_000
# - a power of an irrational or complex base, or with an irrational
#   exponent (``E^(n log 7)`` is ``7^n``; ``re()`` multiplies powers out
#   term by term): the exponent;
_MAX_EXPONENT = 1000
# - a root of a rational number (sympy looks for its factors): its bits;
_MAX_ROOT_BITS = 1000
# - gamma / factorial of a rational number: the number.
_MAX_FACTORIAL = 1000
# floor(), round() … of a number above ~1e308 are refused as well: they
# compute every digit of it.
_POW = '__formula_pow__'


class _Refused(Exception):
    pass


def _size_bits(value):
    return max(1, sum(int(r.p).bit_length() + int(r.q).bit_length()
                      for r in value.atoms(sp.Rational)))


def _magnitude(value):
    """``|value|`` as a float — inf when it overflows or is not a number."""
    try:
        return abs(complex(value.evalf(3)))
    except (TypeError, ValueError, OverflowError):
        return float('inf')


def _check_power(base, exp):
    try:
        b, e = sp.sympify(base, strict=True), sp.sympify(exp, strict=True)
    except sp.SympifyError:
        return
    if not (getattr(b, 'is_number', False) and getattr(e, 'is_number', False)):
        return
    if b in (0, 1, -1):
        return
    if b.is_Rational and e.is_Rational:
        bits = _size_bits(b)
        if (abs(e) * bits > _MAX_POWER_BITS
                or (not e.is_Integer and bits > _MAX_ROOT_BITS)):
            raise _Refused(f'power too large: exponent {e}')
    elif _magnitude(e) > _MAX_EXPONENT:
        raise _Refused(f'power too large: exponent {e}')


def has_large_power(expr):
    """Whether ``expr`` holds a power that expanding would multiply out into
    too many terms — ``(1 + sqrt(2))^n``, ``(a + I)^n``; products of powers
    of one base are merged by sympy, so the guard on ``^`` misses them."""
    return any(p.exp.is_number and not p.base.is_Rational
               and _magnitude(p.exp) > _MAX_EXPONENT
               for p in expr.atoms(sp.Pow))


def _guarded_pow(base, exp, *mod):
    if not mod:
        _check_power(base, exp)
    return builtins.pow(base, exp, *mod)


def _guarded_root(fn, degree=None):
    def call(arg, *args, **kwargs):
        n = sp.sympify(degree if degree is not None else args[0])
        if getattr(n, 'is_number', False) and n != 0:
            _check_power(arg, 1 / n)
        return fn(arg, *args, **kwargs)
    return call


def _guarded(fn, refuse):
    def call(*args, **kwargs):
        for arg in args:
            if isinstance(arg, sp.Basic) and refuse(arg):
                raise _Refused(f'{fn.__name__}({arg}) too large')
        return fn(*args, **kwargs)
    return call


def _factorial_too_large(arg):
    return arg.is_Rational and abs(arg) > _MAX_FACTORIAL


def _exponent_too_large(arg):
    return arg.is_number and _magnitude(arg) > _MAX_EXPONENT


def _huge(arg):
    return arg.is_number and _magnitude(arg) == float('inf')


_MAX_ROUND_DIGITS = 100


def _round(value, digits=0):
    """GeoGebra's ``round(x)`` / ``round(x, n)``: half up, and symbolic —
    ``y = round(x)`` is a graph (Python's ``round`` refuses a symbol)."""
    value, digits = sp.sympify(value), sp.sympify(digits)
    if not digits.is_Integer or abs(digits) > _MAX_ROUND_DIGITS:
        raise _Refused(f'round to {digits} digits')
    if _huge(value):
        raise _Refused(f'round({value}) too large')
    scale = sp.Integer(10) ** digits
    return sp.floor(value * scale + sp.Rational(1, 2)) / scale


class _GuardPowers(ast.NodeTransformer):
    def visit_BinOp(self, node):
        self.generic_visit(node)
        if not isinstance(node.op, ast.Pow):
            return node
        call = ast.Call(func=ast.Name(id=_POW, ctx=ast.Load()),
                        args=[node.left, node.right], keywords=[])
        return ast.copy_location(call, node)


_GLOBALS = None


def _global_dict():
    global _GLOBALS
    if _GLOBALS is None:
        namespace = {}
        exec('from sympy import *', namespace)          # our code, not the file's
        namespace['__builtins__'] = {}
        # The builtins sympify would offer that a formula can mean.
        namespace.update(abs=builtins.abs, pow=_guarded_pow,
                         round=_round, max=sp.Max, min=sp.Min)
        namespace = {name: _with_guard(value)
                     for name, value in namespace.items()}
        namespace[_POW] = _guarded_pow
        _GLOBALS = namespace
    return dict(_GLOBALS)


_GUARDED = None


def _with_guard(value):
    """The guarded version of a sympy function, for the global namespace and
    the caller's ``local_dict`` alike (``{'sqrt': sp.sqrt}`` there too)."""
    global _GUARDED
    if _GUARDED is None:
        _GUARDED = {
            **{fn: _guarded(fn, _factorial_too_large)
               for fn in (sp.gamma, sp.factorial, sp.factorial2)},
            sp.exp: _guarded(sp.exp, _exponent_too_large),
            **{fn: _guarded(fn, _huge)
               for fn in (sp.floor, sp.ceiling, sp.frac)},
            **{fn: _guarded(fn, has_large_power)
               for fn in (sp.re, sp.im, sp.Abs, builtins.abs, sp.arg,
                          sp.conjugate, sp.sign)},
            sp.root: _guarded_root(sp.root),
            sp.real_root: _guarded_root(sp.real_root),
            sp.sqrt: _guarded_root(sp.sqrt, 2),
            sp.cbrt: _guarded_root(sp.cbrt, 3),
        }
    try:
        return _GUARDED.get(value, value)
    except TypeError:                                   # unhashable
        return value


def safe_sympify(text, local_dict=None):
    """``sympy.sympify(text, locals=local_dict)`` for untrusted formula text.

    Raises ``sympy.SympifyError`` for refused or malformed text, so callers
    that already catch sympify's errors keep working.
    """
    if len(text) > MAX_LENGTH:
        raise sp.SympifyError(text[:80] + '…', 'refused: too long')
    if _UNSAFE.search(text):
        raise sp.SympifyError(text, 'refused: not a formula')
    global_dict = _global_dict()
    local_dict = {name: _with_guard(value)
                  for name, value in (local_dict or {}).items()}
    try:
        local_dict = {**_text_names(text, local_dict), **local_dict}
        code = stringify_expr(text, local_dict, global_dict, _TRANSFORMATIONS)
        tree = ast.fix_missing_locations(
            _GuardPowers().visit(ast.parse(code, mode='eval')))
        return eval(compile(tree, '<formula>', 'eval'), global_dict, local_dict)
    except _Refused as e:
        raise sp.SympifyError(text, f'refused: {e}')
    except (TokenError, SyntaxError, NameError, AttributeError, ValueError,
            OverflowError, MemoryError, RecursionError) as e:
        raise sp.SympifyError(text, e)
