import logging
import os
import shutil
import re
import ast
import tempfile
from zipfile import ZipFile

import numpy as np

logger = logging.getLogger(__name__)
from xml.etree import ElementTree
from xml.etree.ElementTree import Element as XElement

from ..geo.construction import Construction
from ..geo.lib_commands import Command, COMMAND_REGISTRY, strCommand
from ..geo.formula_params import (
    formula_bindings, formula_objects, formula_parameters, mentioned_numbers,
    mentioned_objects, parametric_inputs,
)
from ..geo.lib_vars import *
from ..geo.lib_elements import *
from ..geo.safe_sympify import normalize_formula_text
from ..geo.utils import is_number, is_angle_degrees
from ..geo.tparam import (
    get_tparam_from_point_and_circle,
    get_tparam_from_point_and_line,
    get_tparam_from_point_and_segment,
    get_tparam_from_point_and_conic,
    get_tparam_from_point_and_locus,
    tparam_from_point_and_path,
)
from ..style.scaling import (
    ggb_point_size_to_style,
    ggb_thickness_to_stroke_width,
    ggb_arc_size_px,
    ggb_label_offset_to_style,
)
from ..style.enums import ggb_point_style_to_elem_style
from ..labels import geogebra_label_mode_to_style
def _ggb_parse(constr, code, debug=False):
    """Thin wrapper around ``dsl.run`` so the two call sites below
    stay readable. Lazy-imports to avoid a module-load cycle (``dsl``
    imports ``lib_commands`` which indirectly loads this module).

    The code is built from the expressions of a ``.ggb`` — untrusted input —
    so it is checked first (:func:`_check_ggb_code`)."""
    from .dsl import run as _dsl_run
    _check_ggb_code(code)
    _dsl_run(constr, code, debug=debug)


_GGB_CODE_FORBIDDEN = (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ListComp,
                       ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Import, ast.ImportFrom, ast.Global,
                       ast.Nonlocal, ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr)


def _check_ggb_code(code: str) -> None:
    """A GeoGebra expression converted to Python is one assignment of an
    expression: no attribute or name with a double underscore (``().__class__…``
    reaches ``object.__subclasses__``), no private attribute, no lambda,
    comprehension or definition. Raises ``ValueError`` — the callers record
    it as ``expression_parse_error`` (the object keeps its saved value)."""
    from .dsl.sugar import preprocess_dsl_sugar
    import textwrap
    try:
        tree = ast.parse(preprocess_dsl_sugar(textwrap.dedent(code)))
    except SyntaxError:
        return                      # ``dsl.run`` reports it the usual way
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
        raise ValueError('GeoGebra expression: one assignment expected')
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError(f'GeoGebra expression: attribute {node.attr!r} is not allowed')
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError(f'GeoGebra expression: name {node.id!r} is not allowed')
        if isinstance(node, _GGB_CODE_FORBIDDEN):
            raise ValueError(f'GeoGebra expression: {type(node).__name__} is not allowed')


temp_path = None  # created dynamically per call

#--------------------------------------------------------------------------

def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

_GGB_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024  # 256 MB hard cap against zip-bomb
_GGB_MAX_MEMBERS = 4096                           # reject bombs with millions of tiny files


def _safe_extract_ggb(ggb: ZipFile, dest_dir: str) -> None:
    """Extract a .ggb (ZIP) archive guarding against path traversal and zip-bomb.

    Raises ValueError on any member whose resolved path escapes ``dest_dir``,
    when the archive has too many entries, or when the total uncompressed size
    exceeds the cap. Only member paths are validated; content is written via
    ZipFile.extract which uses the already-sanitized sanitized name.
    """
    dest_real = os.path.realpath(dest_dir)
    infos = ggb.infolist()
    if len(infos) > _GGB_MAX_MEMBERS:
        raise ValueError(f"ggb archive has too many members ({len(infos)} > {_GGB_MAX_MEMBERS})")
    total = 0
    for info in infos:
        total += int(info.file_size)
        if total > _GGB_MAX_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"ggb archive uncompressed size exceeds cap ({total} > {_GGB_MAX_UNCOMPRESSED_BYTES})"
            )
        name = info.filename
        if not name or name.endswith('/'):
            continue  # directory entry — ZipFile.extract handles creation
        # Reject absolute paths and any traversal that escapes dest_dir.
        if os.path.isabs(name) or name.startswith(('/', '\\')):
            raise ValueError(f"ggb archive member has absolute path: {name!r}")
        target = os.path.realpath(os.path.join(dest_real, name))
        if target != dest_real and not target.startswith(dest_real + os.sep):
            raise ValueError(f"ggb archive member escapes extraction directory: {name!r}")
    ggb.extractall(dest_dir)


def get_xelems(ggb_path: str):
    tmp_dir = tempfile.mkdtemp(prefix="animageo_")
    try:
        with ZipFile(ggb_path, 'r') as ggb:
            _safe_extract_ggb(ggb, tmp_dir)

        tree = ElementTree.parse(os.path.join(tmp_dir, "geogebra.xml"))
        root = tree.getroot()
        constr_xelem = root.find("construction")

        # Expand custom-tool (macro) calls before the construction is parsed.
        macro_path = os.path.join(tmp_dir, "geogebra_macro.xml")
        if os.path.exists(macro_path):
            try:
                macro_tree = ElementTree.parse(macro_path)
                from .ggb_macro import parse_macros, expand_macros_in_construction
                macros = parse_macros(macro_tree.getroot())
                if macros:
                    expand_macros_in_construction(constr_xelem, macros)
            except Exception as e:
                logger.warning("Failed to expand macros from %s: %s", macro_path, e)

        view_xelem = root.find("euclidianView")
        if view_xelem is None:
            view_xelem = root.find("euclideanView")
        return constr_xelem, view_xelem, root.find("gui")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def _matching_paren(s, open_index):
    """Index of the ``)`` closing ``s[open_index]``, tracking ``()``/``[]``
    nesting; ``None`` if unbalanced or closed by a ``]``."""
    depth = 0
    for i in range(open_index, len(s)):
        ch = s[i]
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
            if depth == 0:
                return i if ch == ')' else None
    return None


def _top_level_parts(s):
    """Split ``s`` on the commas that are not nested in brackets."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return parts


def replace_with_point(expr_str):
    """Wrap every coordinate pair ``(a, b)`` in ``Point(...)``.

    A pair is a ``(`` not preceded by a word character (call arguments such
    as ``f(1, 2)`` stay intact) whose content has exactly two non-empty
    top-level comma parts. The parts may hold brackets of their own —
    ``(0, 1 / ((4 * a)))``, ``(1, f(1))`` — which the former single regular
    expression could not express: such a pair stayed a bare tuple, and the
    construction dropped the object. Pairs nested inside are wrapped too.
    """
    out, i = [], 0
    while i < len(expr_str):
        ch = expr_str[i]
        if ch == '(' and not (i > 0 and re.match(r'\w', expr_str[i - 1])):
            close = _matching_paren(expr_str, i)
            if close is not None:
                inner = expr_str[i + 1:close]
                parts = _top_level_parts(inner)
                is_pair = len(parts) == 2 and all(p.strip() for p in parts)
                out.append(('Point(' if is_pair else '(')
                           + replace_with_point(inner) + ')')
                i = close + 1
                continue
        out.append(ch)
        i += 1
    return ''.join(out)

 # Функция для извлечения идентификаторов из выражения
def extract_identifiers(expression):
    # Ищем идентификаторы, которые могут содержать фигурные скобки как часть имени
    # Это включает имена типа "M_{1}", "u_{1}" и т.д.
    identifier_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*\{[^}]*\}|[a-zA-Z_][a-zA-Z0-9_]*'
    
    # Находим все совпадения
    identifiers = set()
    for match in re.finditer(identifier_pattern, expression):
        ident = match.group(0)
        # Проверяем, что это не часть числа и не оператор
        if not re.match(r'^\d', ident) and ident not in ['and', 'or', 'not']:
            identifiers.add(ident)
    
    # Также ищем идентификаторы с специальными символами, которые могут быть пропущены
    # The degree sign is a postfix unit in expressions (``K°`` means the
    # numeric slider K measured in degrees), not part of the identifier.
    special_pattern = r'[a-zA-Z_][a-zA-Z0-9_{}\'&]*'
    for match in re.finditer(special_pattern, expression):
        ident = match.group(0)
        # Исключаем чисто числовые значения и операторы
        if not re.match(r'^\d', ident) and ident not in ['and', 'or', 'not']:
            identifiers.add(ident)
    
    # Исключаем ключевые слова Python и стандартные функции
    python_keywords = {'and', 'as', 'assert', 'break', 'class', 'continue', 
                      'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 
                      'for', 'from', 'global', 'if', 'import', 'in', 'is', 
                      'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 
                      'return', 'True', 'try', 'while', 'with', 'yield'}
    
    math_functions = {'sin', 'cos', 'tan', 'sqrt', 'log', 'ln', 'exp', 'abs', 
                     'round', 'floor', 'ceil', 'min', 'max', 'sum'}
    
    excluded = python_keywords.union(math_functions)
    return identifiers - excluded

_FORMULA_EXPR_TYPES = ('function', 'implicitpoly', 'conic', 'line')


def convert_ggb_expr_to_python(constr, expr_str, expr_type=None):
    # A curve's formula (``π``, ``ℯ``, ``−``, ``·``…) is read the way the
    # formula parsers read it before any name in it is looked for.
    if expr_type in _FORMULA_EXPR_TYPES:
        expr_str = normalize_formula_text(expr_str)
    # Извлекаем все идентификаторы из выражения
    identifiers = extract_identifiers(expr_str)
    
    # Добавляем новые идентификаторы в name_mapping, если они еще не там
    for identifier in identifiers:
        if identifier not in constr.name_mapping:
            constr.get_normalized_name(identifier)
    
    # Заменяем все имена согласно name_mapping.  ``\b`` works only when the
    # label ends in a word character; legal GeoGebra names such as ``K°`` do
    # not, and used to leak the degree sign into the generated Python DSL.
    # Longest-first also prevents a shorter mapped name from consuming the
    # prefix of a longer one.
    for original, normalized in sorted(
        constr.name_mapping.items(), key=lambda item: len(item[0]), reverse=True,
    ):
        expr_str = re.sub(
            rf'(?<!\w){re.escape(original)}(?!\w)', normalized, expr_str,
        )
        
    # Проверяем, является ли выражение простым вектором в формате (x, y)
    vector_match = re.match(r'^\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)\s*$', expr_str)
    if vector_match and expr_type == "vector":
        x, y = vector_match.groups()
        return f"Vector(Point({x}, {y}))"
    
    expr_str = replace_with_point(expr_str)
    
    # Заменяем квадратные скобки на круглые. Keep GeoGebra command names
    # in CamelCase: the exec DSL namespace resolves factories like
    # Line(...), Distance(...), Vector(...), not snake_case functions.
    expr_str = expr_str.replace('[', '(').replace(']', ')')

    # GeoGebra ``^`` is exponentiation; Python ``^`` is bitwise XOR. Translate
    # so the exec'd DSL raises no ``unsupported operand type(s) for ^`` on real
    # .ggb expressions like ``Circle[O, 5^(0.5) / 2]`` (radius = sqrt(5)/2).
    # Mirrors the conic parser (lib_conic.py); ``^``/``**`` are both
    # right-associative so operator semantics are preserved.
    expr_str = expr_str.replace('^', '**')

    # Заменяем градусы на radians-valued AngleSize construction.
    # The postfix may follow a literal (``90°``) or a numeric slider
    # (``K°``).  The latter is common in Rotate commands and must not be
    # mistaken for a GeoGebra object whose label literally contains ``°``.
    pattern_deg = r'(?<![\w.])(-?(?:\d+(?:\.\d+)?|[^\W\d]\w*))°'
    expr_str = re.sub(pattern_deg, r'AngleSize((\1) * pi / 180)', expr_str)
    
    return expr_str

def is_simple_value(s):
    if s is None:
        return True
    if is_number(s):
        return True
    if is_angle_degrees(s):
        return True
    if isinstance(s, str) and s.isidentifier():
        return True
    return False


def _element_types_by_label(constr_xelem: XElement) -> dict[str, str]:
    return {
        xelem.attrib["label"]: xelem.attrib["type"]
        for xelem in constr_xelem
        if xelem.tag == "element"
        and "label" in xelem.attrib
        and "type" in xelem.attrib
    }


_FORMULA_COMMANDS = {'function': 'Function', 'conic': 'Conic',
                     'line': 'Line', 'implicit': 'ImplicitCurve'}


def _same_curve(a, b) -> bool:
    if isinstance(a, Conic) and isinstance(b, Conic):
        # Scale both matrices to unit max entry first: Conic.equivalent
        # compares products with an absolute tolerance, under which two
        # matrices with tiny entries would always look proportional.
        sa, sb = np.max(np.abs(a.matrix)), np.max(np.abs(b.matrix))
        if sa == 0 or sb == 0:
            return sa == sb
        return Conic(a.matrix / sa).equivalent(Conic(b.matrix / sb))
    if isinstance(a, Line) and isinstance(b, Line):
        sign = 1.0 if np.dot(a.normal, b.normal) >= 0 else -1.0
        return bool(np.allclose(sign * a.normal, b.normal, atol=1e-7)
                    and np.isclose(sign * a.offset, b.offset, atol=1e-7))
    return False


def _add_formula_command(constr, name, kind, expr, saved=None, debug=False) -> bool:
    """Build a formula curve as a command on what it refers to — numbers,
    points through ``x()``/``y()``, functions it calls — so it follows them
    on rebuild (``f(x) = a x²`` with ``a`` animated, ``g(t) = y(A) t`` with
    ``A`` dragged).

    Returns False — the caller then keeps the frozen snapshot — when the
    formula mentions no construction object, can't be evaluated, or
    disagrees with the curve GeoGebra saved (``saved``: the conic from
    ``<matrix>`` / the line from ``<coords>``).
    """
    # A formula that mentions no construction object keeps the old import
    # path untouched: it isn't even parsed here.
    if not mentioned_objects(constr, expr):
        return False
    cmd_name = _FORMULA_COMMANDS[kind]
    try:
        params = parametric_inputs(constr, expr, kind)
        if not params:
            return False
        objects = formula_objects(constr)
        impl = COMMAND_REGISTRY[f'{strCommand(cmd_name)}_Tn']
        probe = impl(expr, *(objects[p] for p in params))
        if probe is None or (saved is not None and not _same_curve(probe, saved)):
            return False
    except Exception as e:           # never let a formula take the load down
        logger.warning("Formula %r of '%s' kept as a snapshot: %s", expr, name, e)
        return False
    command = Command(cmd_name, [expr, *params], [name])
    constr.add(command)
    constr.apply(command, debug=debug)
    return True


_PATH_TYPES = (Circle, Arc, Segment, Line, Ray, Conic, Function, LocusCurve, Polygon)


def _check_point_on_path(constr, name, source, coords_xelem) -> None:
    """``Point(path, t)`` is rebuilt from our port of GeoGebra's path
    parameter. If it disagrees with the position saved in the file, keep the
    saved point (fixed) and record why — the static frame then matches the
    applet, the point just won't follow ``t``."""
    try:
        x, y, z = (float(coords_xelem.attrib[k]) for k in ('x', 'y', 'z'))
    except (AttributeError, KeyError, ValueError):
        return
    if z == 0 or not np.isfinite([x, y, z]).all():
        return                                   # undefined in GeoGebra too
    saved = np.array([x / z, y / z])
    elem = constr.element(name)
    built = getattr(elem, 'data', None)
    if isinstance(built, Point) and np.allclose(built.coords, saved, rtol=1e-6, atol=1e-6):
        return
    if elem is None:
        constr.add(Element(name, Point(saved), fixed=True))
    else:
        elem.data = Point(saved)
        elem.fixed = True
    constr.record_expression_diagnostic(
        'parametric_dependency_frozen', name, source,
        parameters=mentioned_numbers(constr, source), command='Point',
        detail='the path parameter does not reproduce the saved position; '
               'kept the saved point')


def _formula_references(constr, expr, kind):
    """Construction objects a formula refers to: as parsed when it parses
    (the variable of ``g(t) = t²`` is not the slider ``t``), else by name."""
    mentioned = mentioned_objects(constr, expr)
    names = formula_parameters(expr, kind)
    return mentioned if names is None else [n for n in mentioned if n in names]


def _note_frozen_formula(constr, name, kind, expr, detail) -> None:
    """A formula that refers to construction objects but was imported as a
    snapshot will not follow them — record it so a client can tell the
    user."""
    mentioned = _formula_references(constr, expr, kind)
    if mentioned:
        constr.record_expression_diagnostic(
            'parametric_dependency_frozen', name, expr,
            parameters=mentioned, detail=detail)


def get_kernel_decimals(ggb_path: str, default: int = 2) -> int:
    """Read the kernel ``<decimals val>`` rounding setting from a .ggb file.

    Used to format dynamic-text object values (Polygon area, Segment length,
    numbers) the same way GeoGebra displays them. Returns ``default`` when the
    setting is absent or unreadable.
    """
    try:
        with ZipFile(ggb_path, 'r') as ggb:
            with ggb.open('geogebra.xml') as f:
                root = ElementTree.parse(f).getroot()
        kernel = root.find('kernel')
        if kernel is not None:
            dec = kernel.find('decimals')
            if dec is not None:
                return int(dec.attrib.get('val', default))
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("Could not read kernel decimals from %s: %s", ggb_path, e)
    return default


def split_text_parts(exp: str):
    """Split a GeoGebra text expression into ordered parts.

    A text ``exp`` (after XML unescaping) is a top-level ``+`` concatenation of
    string literals and object references, e.g. ``"Area = " + t1 + " "``.
    Returns a list of ``('str', literal)`` and ``('expr', raw_expression)``.
    Backslashes are preserved (LaTeX like ``\\sqrt2`` survives); only ``\\"``
    is treated as an escaped quote.
    """
    parts = []
    i, n = 0, len(exp)
    buf = ''
    depth = 0

    def flush_expr():
        nonlocal buf
        if buf.strip():
            parts.append(('expr', buf.strip()))
        buf = ''

    while i < n:
        c = exp[i]
        if c == '"':
            flush_expr()
            j = i + 1
            lit = ''
            while j < n:
                if exp[j] == '\\' and j + 1 < n and exp[j + 1] == '"':
                    lit += '"'
                    j += 2
                    continue
                if exp[j] == '"':
                    break
                lit += exp[j]
                j += 1
            parts.append(('str', lit))
            i = j + 1
            continue
        if c == '(':
            depth += 1
            buf += c
        elif c == ')':
            depth = max(0, depth - 1)
            buf += c
        elif c == '+' and depth == 0:
            flush_expr()
        else:
            buf += c
        i += 1
    flush_expr()
    return parts


def build_text_segments(constr, raw_exp, debug=False):
    """Turn a raw GeoGebra text ``exp`` into :class:`Text` segments.

    String literals become ``('str', s)``. Each object reference becomes
    ``('obj', name)`` — a bare identifier resolves to its normalized element
    name; a compound sub-expression is evaluated via a phantom Var so its
    value can be read live at render time.
    """
    segments = []
    for kind, value in split_text_parts(raw_exp):
        if kind == 'str':
            segments.append(('str', value))
            continue
        token = value.strip()
        if not token:
            continue
        norm = constr.get_normalized_name(token) if token.isidentifier() else None
        if norm is not None and constr.objectByName(norm) is not None:
            segments.append(('obj', norm))
            continue
        # Compound sub-expression (e.g. x(A)+1): materialise a phantom Var and
        # reference it — its value updates on rebuild like any dependent.
        try:
            ph = constr.add_new_phantom()
            converted = convert_ggb_expr_to_python(constr, token)
            _ggb_parse(constr, "{} = {}".format(ph, converted), debug=debug)
            segments.append(('obj', ph))
        except Exception as e:
            logger.warning("Text: could not evaluate segment '%s': %s", token, e)
    return segments


def parse_constr(constr: Construction, constr_xelem: XElement, debug = False):
    xelems_left_to_pass = 0
    fixed_element = False
    # Tracks the locus (Circle/Line/Ray/Segment) the next Point is
    # constrained to; used to compute its ``tparam``.
    tparam_locus = None
    # Output of a Point(path, t) command, checked against its saved <coords>.
    verify_point = None
    name_mapping = {}
    style = {}
    raw = {}  # raw GGB values per element, for ImportPolicy (Phase 3+)
    conditions = {}  # element name -> <condition showObject="expr"> raw expression
    formula_exprs = {}  # normalized name -> conic/line equation, deferred to its <element>
    text_exprs = {}  # normalized name -> raw text <expression> exp, deferred to
                     # the following <element type="text"> which carries position/style
    element_types = _element_types_by_label(constr_xelem)

    for xelem in constr_xelem:                    
        if xelem.tag == "element":                    
            name = xelem.attrib['label']
            type = xelem.attrib['type']

            name_mapping[name] = constr.get_normalized_name(name)
            name = name_mapping[name]
            
            style[name] = {}
            raw[name] = {'elem_type': type}

            elem = xelem.find("decoration")
            if elem is not None:
                style[name]['tick_count'] = int(elem.attrib['type'])
                if type == 'angle':
                    style[name]['tick_count'] += 1
                raw[name]['decoration_lines'] = int(elem.attrib['type'])

            elem = xelem.find("show")
            if elem is not None:
                style[name]['visible'] = (elem.attrib['object'] == 'true')
                style[name]['label_visible'] = (elem.attrib['label'] == 'true')
                raw[name]['show_object'] = (elem.attrib['object'] == 'true')
                raw[name]['show_label'] = (elem.attrib['label'] == 'true')

            # Conditional visibility: <condition showObject="expr"/>. GeoGebra
            # draws the object only while ``expr`` is true, overriding the
            # ``<show object>`` flag above. Captured here, resolved after the
            # whole construction is parsed (the referenced boolean may be
            # defined later in the file).
            cond_elem = xelem.find("condition")
            if cond_elem is not None and cond_elem.get("showObject"):
                conditions[name] = cond_elem.attrib["showObject"]

            caption = xelem.find("caption")
            if caption is not None:
                raw[name]['label_caption'] = caption.attrib['val']

            elem = xelem.find("labelMode")
            if elem is not None:
                label_mode = int(elem.attrib['val'])
                raw[name]['label_mode'] = label_mode
                style[name]['label_mode'] = geogebra_label_mode_to_style(label_mode)
                if label_mode in (3, 9) and caption is not None:
                    style[name]['label_text'] = '$' + caption.attrib['val'] + '$'

            elem = xelem.find("angleStyle")
            if elem is not None:
                if type == 'angle':
                    ggb_angle_style = int(elem.attrib['val'])
                    style[name]['angle_range'] = 'reflex' if ggb_angle_style == 2 else 'minor'
                    raw[name]['angle_style'] = ggb_angle_style

            elem = xelem.find("pointStyle")
            if elem is not None:
                if type == 'point':
                    raw[name]['point_style'] = int(elem.attrib['val'])

            elem = xelem.find("pointSize")
            if elem is not None:
                if type == 'point':
                    psize = float(elem.attrib['val'])
                    raw[name]['point_size'] = psize
                    style[name]['size_px'] = ggb_point_size_to_style(psize)

            elem = xelem.find("labelOffset")
            if elem is not None:
                x, y = float(elem.attrib['x']), float(elem.attrib['y'])
                raw[name]['label_offset_px'] = [x, y]
                style[name]['label_offset_px'] = ggb_label_offset_to_style(x, y)
            else:
                style[name]['label_offset_px'] = [0, 0]

            elem = xelem.find("arcSize")
            if elem is not None:
                if xelem.attrib['type'] == 'angle':
                    asize = float(elem.attrib['val'])
                    raw[name]['arc_size'] = asize
                    style[name]['arc_size_px'] = ggb_arc_size_px(asize)

            elem = xelem.find("objColor")
            if elem is not None:
                r, g, b, a = int(elem.attrib['r']), int(elem.attrib['g']), int(elem.attrib['b']), float(elem.attrib['alpha'])
                hex_color = rgb_to_hex(r, g, b)
                raw[name]['obj_color'] = {
                    'r': r,
                    'g': g,
                    'b': b,
                    'alpha': a,
                    'opacity': a,
                    'hex': hex_color,
                }
                style[name]['label_color'] = hex_color
                if xelem.attrib['type'] in ['angle', 'polygon', 'arc', 'conic', 'conicpart']:
                    style[name]['fill'] = hex_color
                    style[name]['fill_opacity'] = a
                if xelem.attrib['type'] == 'point':
                    # Decompose GGB pointStyle into (shape, fill, stroke) axes.
                    ggb_code = raw[name].get('point_style', 0)
                    style[name].update(ggb_point_style_to_elem_style(ggb_code, hex_color))

                lineStyle = xelem.find("lineStyle")
                if lineStyle is not None:
                    thick, tt = float(lineStyle.attrib['thickness']), float(lineStyle.attrib['type'])
                    op = float(lineStyle.attrib['opacity']) if 'opacity' in lineStyle.attrib else 255
                    raw[name]['line_thickness'] = thick
                    raw[name]['line_type'] = int(tt)
                    raw[name]['line_opacity'] = op
                    style[name]['stroke'] = hex_color
                    style[name]['stroke_opacity'] = op / 255
                    style[name]['stroke_width_px'] = ggb_thickness_to_stroke_width(thick)
                    if int(tt) > 0: style[name]['stroke_dash_ratio'] = 0.65
                        
        if xelems_left_to_pass:
            xelems_left_to_pass -= 1
            continue

        if xelem.tag == "expression":
            name = expr = None
            try:
                name = xelem.attrib['label']
                expr = xelem.attrib['exp']
                expr_type = xelem.attrib.get('type', None)
                if expr_type is None:
                    companion_type = element_types.get(name)
                    if companion_type in ('function', 'implicitpoly', 'conic', 'line'):
                        expr_type = companion_type
                name_mapping[name] = constr.get_normalized_name(name)

                # Free text object: a string-valued expression (no geometric
                # type, contains a string literal). Stash the raw exp and defer
                # to the following <element type="text">, which carries the
                # position, LaTeX flag, font and colour. (Numeric/point/conic
                # expressions never contain a '"'.)
                if expr_type is None and '"' in expr:
                    text_exprs[name_mapping[name]] = expr
                    continue

                converted_expr = convert_ggb_expr_to_python(constr, expr, expr_type)

                if expr.find('=') < 0:
                    logger.debug("Expression [%s]: %s >> %s", expr_type, expr, name)
                    _ggb_parse(constr, f"{name_mapping[name]} = {converted_expr}", debug=debug)
                    xelems_left_to_pass = 1
                    continue

                # Expression is an explicit equation (contains '='). For
                # GGB types that carry their geometric data in the
                # following <element>'s <matrix> / <coords>, defer to
                # the final element handler below (no xelems_left_to_pass
                # increment — we want the handler to run).
                if expr_type in ('conic', 'line'):
                    logger.debug("Deferred %s equation to element: %s",
                                 expr_type, expr)
                    formula_exprs[name_mapping[name]] = converted_expr
                    continue

                if expr_type == 'function':
                    # Parse the function directly from the expression
                    # string — the companion <element> has only style,
                    # no geometric data.
                    from ..geo.lib_function import Function as _Function
                    if _add_formula_command(constr, name_mapping[name], 'function',
                                            converted_expr, debug=debug):
                        xelems_left_to_pass = 1
                        continue
                    try:
                        func_obj = _Function.from_string(
                            converted_expr, parameters=formula_bindings(constr))
                        constr.add(Element(name_mapping[name], func_obj, fixed=True))
                        _note_frozen_formula(
                            constr, name_mapping[name], 'function', converted_expr,
                            'formula imported as a snapshot at the current values')
                    except ValueError as fe:
                        logger.warning("Could not parse function '%s': %s", expr, fe)
                        constr.record_expression_diagnostic(
                            'expression_parse_error', name_mapping[name], expr,
                            parameters=_formula_references(
                                constr, converted_expr, 'function'),
                            detail=str(fe))
                    xelems_left_to_pass = 1
                    continue

                if expr_type == 'implicitpoly':
                    from ..geo.lib_implicit import ImplicitCurve as _Implicit
                    if _add_formula_command(constr, name_mapping[name], 'implicit',
                                            converted_expr, debug=debug):
                        xelems_left_to_pass = 1
                        continue
                    try:
                        imp = _Implicit.from_string(
                            expr, parameters=formula_bindings(constr))
                        constr.add(Element(name_mapping[name], imp, fixed=True))
                        _note_frozen_formula(
                            constr, name_mapping[name], 'implicit', converted_expr,
                            'formula imported as a snapshot at the current values')
                    except ValueError as ie:
                        logger.warning("Could not parse implicitpoly '%s': %s",
                                       expr, ie)
                        constr.record_expression_diagnostic(
                            'expression_parse_error', name_mapping[name], expr,
                            parameters=_formula_references(
                                constr, converted_expr, 'implicit'),
                            detail=str(ie))
                    xelems_left_to_pass = 1
                    continue

                logger.warning("No implementation for expression '%s' (type=%s)",
                               expr, expr_type)
                xelems_left_to_pass = 1
                continue
            except Exception as e:
                logger.debug("Expression parse error: %s", e)
                if name is not None and expr is not None:
                    # The object is then built from its saved coordinates (if
                    # any) and will not follow what the expression refers to.
                    constr.record_expression_diagnostic(
                        'expression_parse_error', name_mapping.get(name, name), expr,
                        parameters=mentioned_numbers(constr, expr), detail=str(e))
                continue
        
        if xelem.tag == "command":            
            comm_name = xelem.attrib["name"]                        
            input_xelem, output_xelem = xelem.find("input"), xelem.find("output")
            inputs = list(input_xelem.attrib.values())
            outputs_raw = [output for output in output_xelem.attrib.values() if output]
            outputs = [constr.get_normalized_name(output) for output in outputs_raw]
            for i, inp in enumerate(inputs):
                if is_number(inp) or is_angle_degrees(inp):
                    inputs[i] = inp 
                elif inp in constr.name_mapping:
                    # References to already parsed GeoGebra objects may use
                    # non-Python label characters (subscripts, primes, degree
                    # signs), so resolve them through the established map.
                    inputs[i] = constr.name_mapping[inp]
                elif inp.isidentifier():
                    inputs[i] = constr.get_normalized_name(inp)
                else:
                    # Keep compound inputs intact.  Normalizing a whole
                    # expression such as ``4 * (alpha - 90°)`` turns it into
                    # an identifier-shaped string before the phantom-expression
                    # pass below and silently drops the calculation.
                    inputs[i] = inp
            
            # Обработка выражений во входных параметрах
            new_inputs = []
            for inp in inputs:
                if is_simple_value(inp):
                    new_inputs.append(inp)
                else:
                    # Создаем временную переменную для выражения
                    temp_name = constr.add_new_phantom()
                    converted_expr = convert_ggb_expr_to_python(constr, inp)
                    _ggb_parse(constr, f"{temp_name} = {converted_expr}", debug=debug)
                    new_inputs.append(temp_name)
            
            if comm_name == "Point" and len(new_inputs) == 2:
                # Point(f, t) on a graph: GeoGebra maps t onto the x-range of
                # the view, so the command carries the saved view's bounds.
                path_elem = constr.element(new_inputs[0])
                x_range = getattr(constr, 'ggb_view_x_range', None)
                if (x_range is not None and path_elem is not None
                        and isinstance(path_elem.data, Function)):
                    new_inputs = new_inputs + [repr(x_range[0]), repr(x_range[1])]

            command = Command(comm_name, new_inputs, outputs)
            constr.add(command)
            constr.apply(command, debug = debug)
            
            if comm_name == "Point":
                if len(inputs) == 1:
                    if debug:
                        logger.debug('Point FIXED by %s', inputs[0])
                    fixed_element = True
            
                    # Resolve the path through the *rebound* input. When the
                    # path has no name of its own GeoGebra writes it inline
                    # ("Circle[A, 1 / 2]"), and the phantom pass above has
                    # already parsed that expression into ``new_inputs[0]``.
                    # Looking it up under the raw expression string finds
                    # nothing, and the point then misses both its tparam and
                    # its serialized <coords> (skipped as a plain command
                    # output) — landing at the random angle ``point_c`` uses
                    # when no tparam is given.
                    path_ref = new_inputs[0] if new_inputs else inputs[0]
                    path_elem = constr.element(path_ref)
                    input0 = path_elem.data if path_elem else None
                    if isinstance(input0, (Circle, Line, Ray, Segment, Conic, LocusCurve, Function, Polygon)):
                        # ``Point(Polygon)`` is a point on the polygon boundary.
                        # animageo has no polygon-boundary tparam yet, so
                        # ``tparam_from_point_and_path`` returns ``None`` and the
                        # following <element> is materialised as a fixed point at
                        # its serialized coordinates — enough to render the point
                        # and unblock segments that depend on it.
                        tparam_locus = input0

            if comm_name == "Point" and len(inputs) == 2 and outputs:
                path_elem = constr.element(new_inputs[0])
                if path_elem is not None and isinstance(path_elem.data, _PATH_TYPES):
                    verify_point = (outputs[0], f"Point[{', '.join(inputs)}]")

            xelems_left_to_pass = (len(outputs_raw)
                                   if not (tparam_locus or verify_point) else 0)

            continue

        # Here xelem has to be a commandless point or numeric (Var)

        if xelem.tag == "element":
            name = name_mapping[xelem.attrib["label"]]
            if (verify_point is not None and name == verify_point[0]
                    and xelem.attrib["type"] == "point"):
                _check_point_on_path(constr, name, verify_point[1], xelem.find("coords"))
                verify_point = None
                continue
            if xelem.attrib["type"] == "point":
                coords = list(xelem.find("coords").attrib.values())
                coords.pop(-1) #  removing z coordinate
                tparam = None
                if tparam_locus:
                    tparam = tparam_from_point_and_path(Point(coords), tparam_locus)

                if tparam is not None:
                    fixed_element = False
                point_data = Point([float(x) for x in coords])
                elem = constr.element(name)
                if elem is None:
                    constr.add(Element(name, point_data, fixed=fixed_element, tparam=tparam))
                else:
                    # The output may already exist — e.g. a Point-on-path
                    # command created a default position at apply time. Mutate
                    # it in place rather than ``constr.add`` (which would append
                    # a duplicate Element with the same name). This is the only
                    # path that materialises a Point(Polygon): no perimeter
                    # tparam yet, so ``tparam`` is None and the point is fixed
                    # at its serialized coordinates.
                    elem.data = point_data
                    elem.fixed = fixed_element
                    elem.tparam = tparam

                fixed_element = False
                tparam_locus = None
                continue
            if xelem.attrib["type"] == "numeric":
                value_xelem = xelem.find("value")
                constr.add(Var(name, float(value_xelem.attrib["val"])))
                continue
            if xelem.attrib["type"] == "angle":
                value_xelem = xelem.find("value")
                constr.add(Var(name, AngleSize(float(value_xelem.attrib["val"]))))
                continue
            if xelem.attrib["type"] == "boolean":
                value_xelem = xelem.find("value")
                bval = BoolOrNone(value_xelem.attrib["val"]) if value_xelem is not None else False
                constr.add(Var(name, Boolean(bool(bval))))
                continue
            if xelem.attrib["type"] == "conic":
                if constr.element(name) is not None:
                    continue
                matrix_elem = xelem.find("matrix")
                if matrix_elem is None:
                    logger.warning("Conic element '%s' has no <matrix>", name)
                    continue
                a = matrix_elem.attrib
                try:
                    conic = Conic.from_ggb_matrix(
                        float(a['A0']), float(a['A1']), float(a['A2']),
                        float(a['A3']), float(a['A4']), float(a['A5']),
                    )
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse conic matrix for '%s': %s", name, e)
                    continue
                formula = formula_exprs.pop(name, None)
                if formula is not None:
                    if _add_formula_command(constr, name, 'conic', formula,
                                            saved=conic, debug=debug):
                        continue
                    _note_frozen_formula(
                        constr, name, 'conic', formula,
                        'kept the saved conic: the equation does not follow the '
                        'objects it refers to or does not reproduce the saved curve')
                constr.add(Element(name, conic, fixed=True))
                continue
            if xelem.attrib["type"] == "line":
                if constr.element(name) is not None:
                    continue
                coords_elem = xelem.find("coords")
                if coords_elem is None:
                    logger.warning("Line element '%s' has no <coords>", name)
                    continue
                try:
                    a = float(coords_elem.attrib['x'])
                    b = float(coords_elem.attrib['y'])
                    c = float(coords_elem.attrib['z'])
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse line coords for '%s': %s", name, e)
                    continue
                if abs(a) < 1e-12 and abs(b) < 1e-12:
                    logger.warning("Degenerate line coords for '%s': (%s, %s, %s)",
                                   name, a, b, c)
                    continue
                # GGB: a·x + b·y + c·z = 0 with z = 1.
                # animageo Line: n·p = c_line, with n = (a, b), c_line = -c.
                line = Line([a, b], -c)
                formula = formula_exprs.pop(name, None)
                if formula is not None:
                    if _add_formula_command(constr, name, 'line', formula,
                                            saved=line, debug=debug):
                        continue
                    _note_frozen_formula(
                        constr, name, 'line', formula,
                        'kept the saved line: the equation does not follow the '
                        'objects it refers to or does not reproduce the saved line')
                constr.add(Element(name, line, fixed=True))
                continue
            if xelem.attrib["type"] == "text":
                if constr.element(name) is not None:
                    continue
                raw_exp = text_exprs.get(name)
                if raw_exp is None:
                    logger.debug("Text element '%s' has no stashed expression", name)
                    continue
                segments = build_text_segments(constr, raw_exp, debug=debug)

                position = None
                anchor_point = None
                sp = xelem.find("startPoint")
                if sp is not None:
                    if 'exp' in sp.attrib:
                        anchor_point = constr.get_normalized_name(sp.attrib['exp'])
                    elif 'x' in sp.attrib and 'y' in sp.attrib:
                        position = [float(sp.attrib['x']), float(sp.attrib['y'])]

                latex_el = xelem.find("isLaTeX")
                is_latex = latex_el is not None and latex_el.attrib.get('val') == 'true'

                font_el = xelem.find("font")
                serif = font_el is not None and font_el.attrib.get('serif') == 'true'
                if font_el is not None:
                    # GGB text font: sizeM multiplies the default GUI font
                    # (16 px). `size` is a legacy pixel delta (0 = default).
                    try:
                        size_m = float(font_el.attrib.get('sizeM', 1.0))
                        size_delta = float(font_el.attrib.get('size', 0.0))
                    except (TypeError, ValueError):
                        size_m, size_delta = 1.0, 0.0
                    style[name]['font_size_px'] = 16.0 * size_m + size_delta

                constr.add(Element(name, Text(segments, position=position,
                                              anchor_point=anchor_point,
                                              is_latex=is_latex, serif=serif),
                                   fixed=True))
                continue

        logger.debug("Skipping unsupported XElement: <%s> %s", xelem.tag, xelem.attrib)

    constr.rebuild(debug = debug)

    # Styling elements. GGB visual values are stored in ``ggb_style`` rather
    # than ``style``; the style resolver decides later whether the import
    # layer participates in rendering.
    for name in style:
        elem = constr.element(name)
        if elem is None: continue
        if isinstance(elem, Var): continue
        if name in raw:
            elem.ggb_raw = raw[name]
        for key in style[name]:
            if debug: logger.debug("STYLE >> %s >> %s = %s", name, key, style[name][key])
            if key == 'visible':
                elem.set_visible(style[name][key], explicit=False)
                continue
            elem.ggb_style[key] = style[name][key]

    # Apply conditional visibility now that every element and boolean Var
    # exists. For static export we evaluate the condition once: only a bare
    # boolean reference (the common GeoGebra checkbox case) is resolved — when
    # that boolean is false the object is hidden regardless of its own
    # ``<show object>`` flag. Anything more complex is left visible with a
    # warning rather than guessed at.
    for name, expr in conditions.items():
        elem = constr.element(name)
        if elem is None or isinstance(elem, Var):
            continue
        ref = expr.strip()
        ref_var = constr.var(name_mapping.get(ref, ref))
        if ref_var is not None and isinstance(ref_var.data, Boolean):
            if ref_var.data.value is False:
                elem.set_visible(False, explicit=False)
        else:
            logger.warning(
                "Element %r has conditional visibility %r that is not a simple "
                "boolean reference; leaving it visible (static export).",
                name, expr,
            )

def FloatOrNone(txt):
    return float(txt) if txt is not None else None

def BoolOrNone(txt):
    if txt is None:
        return None
    return str(txt).lower() == 'true'

def IntOrNone(txt):
    return int(txt) if txt is not None else None

def _color_from_xelem(xelem):
    if xelem is None:
        return None
    try:
        return rgb_to_hex(
            int(xelem.attrib['r']),
            int(xelem.attrib['g']),
            int(xelem.attrib['b']),
        )
    except (KeyError, ValueError):
        return None

def parse_view(view, view_xelem: XElement, debug = False):    
    for xelem in view_xelem:            
        if xelem.tag == "size":
            view['ptWidth'], view['ptHeight'] = FloatOrNone(xelem.attrib['width']), FloatOrNone(xelem.attrib['height'])

        if xelem.tag == "coordSystem":
            view['ptXZero'], view['ptYZero'] = FloatOrNone(xelem.attrib['xZero']), FloatOrNone(xelem.attrib['yZero'])
            view['ptUnit'] = FloatOrNone(xelem.attrib['scale'])
            view['ptUnit_ggb'] = view['ptUnit']
            view['ptYUnit_ggb'] = FloatOrNone(xelem.attrib.get('yscale'))

        if xelem.tag == "evSettings":
            view['showAxes'] = BoolOrNone(xelem.attrib.get('axes'))
            view['showGrid'] = BoolOrNone(xelem.attrib.get('grid'))
            view['gridIsBold'] = BoolOrNone(xelem.attrib.get('gridIsBold'))
            view['gridType'] = IntOrNone(xelem.attrib.get('gridType'))

        if xelem.tag == "bgColor":
            col = _color_from_xelem(xelem)
            if col is not None:
                view['background'] = col

        if xelem.tag == "axesColor":
            col = _color_from_xelem(xelem)
            if col is not None:
                view['axesColor'] = col

        if xelem.tag == "gridColor":
            col = _color_from_xelem(xelem)
            if col is not None:
                view['gridColor'] = col

        if xelem.tag == "lineStyle":
            view['axesLineStyle'] = IntOrNone(xelem.attrib.get('axes'))
            view['gridLineStyle'] = IntOrNone(xelem.attrib.get('grid'))

        if xelem.tag == "axis":
            try:
                axis_id = int(xelem.attrib['id'])
            except (KeyError, ValueError):
                continue
            axes = view.setdefault('axes', {})
            key = 'x' if axis_id == 0 else 'y' if axis_id == 1 else str(axis_id)
            axes[key] = {
                'show': BoolOrNone(xelem.attrib.get('show')),
                'label': xelem.attrib.get('label', ''),
                'unitLabel': xelem.attrib.get('unitLabel', ''),
                'tickStyle': IntOrNone(xelem.attrib.get('tickStyle')),
                'tickDistance': FloatOrNone(xelem.attrib.get('tickDistance')),
                'axisCross': FloatOrNone(xelem.attrib.get('axisCross')),
                'positiveAxis': BoolOrNone(xelem.attrib.get('positiveAxis')),
                'showNumbers': BoolOrNone(xelem.attrib.get('showNumbers')),
            }

        if xelem.tag == "grid":
            view['gridDistX'] = FloatOrNone(xelem.attrib.get('distX'))
            view['gridDistY'] = FloatOrNone(xelem.attrib.get('distY'))
            view['gridDistTheta'] = FloatOrNone(xelem.attrib.get('distTheta'))

def parse_gui(view, gui_xelem: XElement, debug = False):
    """Parse GUI settings (font size, etc.) from GGB XML."""
    if gui_xelem is None:
        return
    font_elem = gui_xelem.find("font")
    if font_elem is not None:
        view['fontSize'] = int(font_elem.attrib.get('size', 16))

def _view_x_range(view_xelem):
    """x-range ``(x_min, x_max)`` of the saved graphics view, or ``None``.

    GeoGebra measures ``Point(f, t)`` on a function graph over the x-range
    of the view showing it (``GeoFunction.getMinParameter``)."""
    if view_xelem is None:
        return None
    size, coords = view_xelem.find('size'), view_xelem.find('coordSystem')
    try:
        width = float(size.attrib['width'])
        x_zero = float(coords.attrib['xZero'])
        scale = float(coords.attrib['scale'])
    except (AttributeError, KeyError, ValueError):
        return None
    if scale <= 0 or width <= 0:
        return None
    return (-x_zero / scale, (width - x_zero) / scale)


def load(constr: Construction, view, ggb_path: str, debug = False, strict = False):
    logger.info("Loading GGB: %s", ggb_path)
    old_strict = getattr(constr, 'strict_unsupported', False)
    old_log = getattr(constr, 'log_unsupported', True)
    constr.strict_unsupported = bool(strict)
    constr.log_unsupported = bool(debug or strict)
    constr.ggb_decimals = get_kernel_decimals(ggb_path)
    constr_xelem, view_xelem, gui_xelem = get_xelems(ggb_path)
    constr.ggb_view_x_range = _view_x_range(view_xelem)
    try:
        parse_constr(constr, constr_xelem, debug = debug)
        parse_view(view, view_xelem, debug = debug)
        parse_gui(view, gui_xelem, debug = debug)
    finally:
        constr.strict_unsupported = old_strict
        constr.log_unsupported = old_log
    n_elems = len(getattr(constr, 'elements', []))
    n_cmds = len(getattr(constr, 'commands', []))
    n_diag = len(getattr(constr, 'command_diagnostics', []))
    logger.info("Parsed %d elements, %d commands, %d unsupported", n_elems, n_cmds, n_diag)
