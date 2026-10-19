"""Final label text resolution for GeoGebra-like label display modes."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from .style.resolver import resolve as _resolve_style
from .style.resolver import trace as _trace_style


LABEL_MODE_LABEL = "label"
LABEL_MODE_VALUE = "value"
LABEL_MODE_LABEL_VALUE = "label_value"
DEFAULT_LABEL_VALUE_PRECISION = 1
LABEL_MODES = frozenset({
    LABEL_MODE_LABEL,
    LABEL_MODE_VALUE,
    LABEL_MODE_LABEL_VALUE,
})


@dataclass(frozen=True)
class LabelValue:
    value: Any
    kind: str = "number"


@dataclass(frozen=True)
class LabelSpec:
    """Structured label description for fast (DecimalNumber-based) rendering.

    ``resolve_label_text`` collapses everything into a single TeX string and is
    what the static renderer and the TikZ/JSXGraph exporters consume. For the
    manim renderer's animation path we instead want the *parts* so the numeric
    portion can be drawn with :class:`~manim.DecimalNumber` (cached digit
    glyphs, no LaTeX recompile when the value changes). This dataclass carries
    those parts while ``text`` stays identical to ``resolve_label_text`` so the
    Tex fallback path is byte-for-byte unchanged.

    Attributes
    ----------
    text:
        Full TeX string, identical to :func:`resolve_label_text`.
    mode:
        ``"label"`` / ``"value"`` / ``"label_value"``.
    prefix_tex:
        Static leading TeX (label name + separator) for ``label_value`` mode,
        already wrapped in ``$…$``; ``None`` for pure ``value`` / ``label``.
    value:
        The live numeric value to display, or ``None`` when there is no numeric
        value to track (mode ``label``, boolean, or a non-finite value).
    kind:
        ``"number"`` / ``"angle"`` / ``"boolean"``.
    num_decimal_places:
        Fixed decimal places for the DecimalNumber.
    strip_zeros:
        Whether trailing zeros are stripped (``label_value_strip_zeros``):
        the Tex label and, since 1.11.0rc3, the DecimalNumber of the video
        (``ui.ValueLabel``) print the same text.
    suffix_tex:
        Static trailing TeX (e.g. ``^{\\circ}``) or ``None``.
    suffix_raised:
        Align the suffix to the top of the number (degree superscript) vs the
        baseline (regular unit).
    """

    text: str
    mode: str = LABEL_MODE_LABEL
    prefix_tex: str | None = None
    value: float | None = None
    kind: str = "number"
    num_decimal_places: int = DEFAULT_LABEL_VALUE_PRECISION
    strip_zeros: bool = True
    suffix_tex: str | None = None
    suffix_raised: bool = False

    @property
    def has_dynamic_value(self) -> bool:
        """True when a DecimalNumber can carry this label's value."""
        return self.value is not None


def normalize_label_mode(value: Any) -> str:
    """Normalize user/GGB label-mode values to AnimaGeo string modes."""
    if value is None:
        return LABEL_MODE_LABEL
    if isinstance(value, bool):
        return LABEL_MODE_LABEL
    if isinstance(value, (int, float)):
        return geogebra_label_mode_to_style(int(value))
    text = str(value).strip().lower().replace("-", "_")
    aliases = {
        "name": LABEL_MODE_LABEL,
        "caption": LABEL_MODE_LABEL,
        "label": LABEL_MODE_LABEL,
        "value": LABEL_MODE_VALUE,
        "name_value": LABEL_MODE_LABEL_VALUE,
        "name_and_value": LABEL_MODE_LABEL_VALUE,
        "caption_value": LABEL_MODE_LABEL_VALUE,
        "caption_and_value": LABEL_MODE_LABEL_VALUE,
        "label_value": LABEL_MODE_LABEL_VALUE,
        "label_and_value": LABEL_MODE_LABEL_VALUE,
    }
    return aliases.get(text, LABEL_MODE_LABEL)


def geogebra_label_mode_to_style(value: int) -> str:
    """Map GeoGebra <labelMode val="..."> to AnimaGeo label modes.

    GeoGebra uses 0=name, 1=name+value, 2=value, 3=caption,
    9=caption+value. Caption text itself remains in ``label_text``.
    """
    if value in (1, 9):
        return LABEL_MODE_LABEL_VALUE
    if value == 2:
        return LABEL_MODE_VALUE
    return LABEL_MODE_LABEL


def _display_name(scene, elem) -> str:
    """Human/display name for an element.

    GeoGebra labels with primes or braced subscripts (``U'''``, ``F_{ab}``) are
    mangled into Python identifiers (``U_Prime_Prime_Prime``, ``F_ab``) at parse
    time (``geo.construction.normalize_name``). Rendering the mangled identifier
    produces wrong labels (e.g. ``U_Prime_Prime_Prime``). The original GeoGebra
    label is preserved in ``scene.geo.name_mapping`` (original → normalized), so
    we recover it for display. An explicit ``display_name`` style wins; falls
    back to ``elem.name`` for DSL elements / fake scenes (no name_mapping).
    """
    explicit = elem.style.get("display_name") if hasattr(elem, "style") else None
    if explicit:
        return str(explicit)
    nm = getattr(getattr(scene, "geo", None), "name_mapping", None)
    if nm:
        for original, normalized in nm.items():
            if normalized == elem.name and original != normalized:
                return str(original)
    return elem.name


def _default_label_text(scene, elem) -> str:
    """``$...$`` fallback label text using the display name (primes/subscripts,
    the underscore by :func:`name_tex`)."""
    return "$" + name_tex(_display_name(scene, elem)) + "$"


# ── Names as TeX and labels as parts (1.11.0) ──────────────────────────────
#
# A name is read as TeX reads it in math mode, as GeoGebra shows it: ``_x``
# indexes the one character (or command) after it — ``A_1`` is A₁, ``A_12``
# is A₁2 — and ``_{…}`` the group; ``^`` likewise raises. An underscore or a
# caret with nothing to index (at the end, before a space, another script
# sign or a closing brace, before an unclosed brace) is the character itself,
# and so is a brace without its pair: the name always compiles.

_LITERAL_SCRIPT = {'_': r'\_', '^': r'\text{\textasciicircum}'}


def _balanced_braces(name: str) -> set:
    """Positions of the braces of ``name`` that have their pair (an escaped
    ``\\{`` or ``\\}`` is no brace)."""
    paired, stack, i = set(), [], 0
    while i < len(name):
        ch = name[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '{':
            stack.append(i)
        elif ch == '}' and stack:
            paired.add(stack.pop())
            paired.add(i)
        i += 1
    return paired


def _command_end(name: str, i: int) -> int:
    """End of the TeX command starting with the backslash at ``i``."""
    j = i + 1
    if j < len(name) and name[j].isascii() and name[j].isalpha():
        while j < len(name) and name[j].isascii() and name[j].isalpha():
            j += 1
        return j
    return min(j + 1, len(name))


def _script_takes(name: str, i: int, paired: set) -> bool:
    """Whether the ``_`` or ``^`` at ``i`` has something to index."""
    if i + 1 >= len(name):
        return False
    nxt = name[i + 1]
    if nxt.isspace() or nxt in '_^}':
        return False
    return nxt != '{' or (i + 1) in paired


def name_tex(name: str) -> str:
    """The TeX (inside ``$…$``) of a label name: the name as it is, with an
    underscore, a caret or a brace that would not compile written as the
    character itself (module notes above)."""
    paired = _balanced_braces(name)
    out, i = [], 0
    while i < len(name):
        ch = name[i]
        if ch == '\\':
            if i + 1 >= len(name):
                out.append(r'\backslash')
                i += 1
                continue
            end = _command_end(name, i)
            out.append(name[i:end])
            i = end
            continue
        if ch in '{}':
            out.append(ch if i in paired else '\\' + ch)
        elif ch in '_^':
            out.append(ch if _script_takes(name, i, paired) else _LITERAL_SCRIPT[ch])
        else:
            out.append(ch)
        i += 1
    return ''.join(out)


_GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ϵ', 'varepsilon': 'ε', 'zeta': 'ζ',
    'eta': 'η', 'theta': 'θ', 'vartheta': 'ϑ', 'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν',
    'xi': 'ξ', 'pi': 'π', 'varpi': 'ϖ', 'rho': 'ρ', 'varrho': 'ϱ', 'sigma': 'σ', 'varsigma': 'ς', 'tau': 'τ',
    'upsilon': 'υ', 'phi': 'ϕ', 'varphi': 'φ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ',
    'Upsilon': 'Υ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
}
_COMMAND_CHARS = dict(_GREEK, prime='′', infty='∞', circ='°', degree='°', cdot='·', times='×', approx='≈',
                      neq='≠', ne='≠', leq='≤', le='≤', geq='≥', ge='≥', pm='±', angle='∠', triangle='△',
                      perp='⊥', parallel='∥', sim='∼')
_ESCAPED_CHARS = {'_': '_', '{': '{', '}': '}', ' ': ' ', ',': ' ', ';': ' ', '!': '', '%': '%', '#': '#',
                  '&': '&', '$': '$'}
# math italic: Latin letters and lowercase Greek; digits, capital Greek,
# Cyrillic (set upright in \text) and signs are upright
_ITALIC_GREEK = frozenset('αβγδϵεζηθϑικλμνξπϖρϱσςτυϕφχψω')


def _italic(ch: str) -> bool:
    return (ch.isascii() and ch.isalpha()) or ch in _ITALIC_GREEK


class _NoParts(Exception):
    pass


def _parse_name(name, i, end, script, paired, out):
    """Append ``(char, script)`` of ``name[i:end]`` to ``out``."""
    while i < end:
        i = _parse_atom(name, i, end, script, paired, out)


def _parse_atom(name, i, end, script, paired, out) -> int:
    ch = name[i]
    if ch == '\\':
        if i + 1 >= end:
            out.append(('\\', script))
            return i + 1
        stop = _command_end(name, i)
        word = name[i + 1:stop]
        char = _COMMAND_CHARS.get(word) if word[:1].isalpha() else _ESCAPED_CHARS.get(word)
        if char is None:
            raise _NoParts
        if char:
            out.append((char, script))
        return stop
    if ch == '{':
        if i not in paired:
            out.append(('{', script))
            return i + 1
        close = next(j for j in sorted(paired) if j > i and name[j] == '}' and _group_close(name, i) == j)
        _parse_name(name, i + 1, close, script, paired, out)
        return close + 1
    if ch == '}':
        if i in paired:         # the end of a group handled by its opening brace
            return i + 1
        out.append(('}', script))
        return i + 1
    if ch in '_^':
        if not _script_takes(name, i, paired):
            out.append((ch, script))
            return i + 1
        if script is not None:
            raise _NoParts      # a script of a script
        return _parse_atom(name, i + 1, end, 'sub' if ch == '_' else 'sup', paired, out)
    if ch == "'":
        out.append(('′', script))
        return i + 1
    out.append((ch, script))
    return i + 1


def _group_close(name, i) -> int:
    depth, j = 0, i
    while j < len(name):
        c = name[j]
        if c == '\\':
            j += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def _merge_parts(chars) -> list:
    parts = []
    for char, script, italic in chars:
        if parts and parts[-1]['italic'] == italic and parts[-1]['script'] == script:
            parts[-1]['text'] += char
        else:
            parts.append({'text': char, 'italic': italic, 'script': script})
    return parts


def label_parts_of_name(name: str):
    """The parts of a label name as TeX sets it (:func:`name_tex`):
    ``[{"text", "italic", "script"}]`` — ``script`` ``"sub"``, ``"sup"`` or
    ``None``, adjacent characters of one look merged; Latin letters and
    lowercase Greek italic, the rest upright, a prime ``′``. ``None`` when the
    name holds a TeX command other than a Greek letter or a common sign, or a
    script inside a script."""
    out = []
    try:
        _parse_name(name, 0, len(name), None, _balanced_braces(name), out)
    except _NoParts:
        return None
    return _merge_parts((char, script, _italic(char)) for char, script in out)


def label_parts_of_value(tex: str):
    """The parts of a formatted value (:func:`format_label_value`): upright,
    a minus sign ``−``, ``°`` for the degree, ``∞``; ``None`` for TeX it does
    not know."""
    text = str(tex)
    unit = ''
    if text.endswith(r'^{\circ}'):
        text, unit = text[:-len(r'^{\circ}')], '°'
    mrm = re.fullmatch(r'\\mathrm\{([^{}\\]*)\}', text)
    if mrm:
        text = mrm.group(1)
    elif text in (r'\infty', r'-\infty'):
        text = text.replace(r'\infty', '∞')
    elif '\\' in text or '{' in text or '^' in text or '_' in text:
        return None
    if text.startswith('-'):
        text = '−' + text[1:]
    return _merge_parts((c, None, False) for c in text + unit)


def _separator_parts(separator: str):
    out = []
    try:
        _parse_name(separator, 0, len(separator), None, _balanced_braces(separator), out)
    except _NoParts:
        return None
    return _merge_parts((char, script, False) for char, script in out)


def resolve_label_parts(scene, elem):
    """The parts of the label :func:`resolve_label_text` gives (name, value or
    both with the separator) — see :func:`label_parts_of_name` — or ``None``
    when its text is not made of them (a caption, a dynamic caption, TeX the
    parts do not cover)."""
    is_name = _label_text(scene, elem) == _default_label_text(scene, elem)
    name = label_parts_of_name(_display_name(scene, elem)) if is_name else None
    mode = normalize_label_mode(_resolve_style(scene, elem, "label_mode", default=LABEL_MODE_LABEL))
    if mode == LABEL_MODE_LABEL:
        return name
    formatted = format_label_value(scene, elem)
    if formatted is None:
        return name
    value = label_parts_of_value(formatted)
    if mode == LABEL_MODE_VALUE:
        return value
    separator = _separator_parts(str(_resolve_style(scene, elem, "label_value_separator", default=" = ")))
    if name is None or value is None or separator is None:
        return None
    return _merge_parts((p['text'], p['script'], p['italic']) for p in name + separator + value)


# ── The halo of a label (1.11.0) ───────────────────────────────────────────

DEFAULT_LABEL_HALO_PX = 0.0


def resolve_label_halo(scene, elem) -> dict:
    """``{"widthPx", "color", "opacity"}`` of the halo of a label: a stroke of
    ``widthPx`` style pixels (half of it outside the glyphs) drawn under the
    glyphs. The keys ``label_halo_px``, ``label_halo_color``,
    ``label_halo_opacity`` of the element (its style chain), else of the
    ``rendering`` section, else ``0`` (no halo), the background colour and
    ``1``."""
    from .style.colorspace import as_hex
    cfg = getattr(scene, 'style_config', None)
    rendering = getattr(cfg, 'rendering', None) or {}
    presets = getattr(cfg, 'presets', None) or {}
    background = (presets.get('color') or {}).get('background') or '#ffffff'

    def expand(value):
        if isinstance(value, str) and hasattr(cfg, 'resolve_ref'):
            return cfg.resolve_ref(value)
        return value

    def number(value, fallback):
        try:
            out = float(value)
        except (TypeError, ValueError):
            return fallback
        return out if math.isfinite(out) else fallback

    width = number(_resolve_style(scene, elem, 'label_halo_px',
                                  default=expand(rendering.get('label_halo_px', DEFAULT_LABEL_HALO_PX))),
                   DEFAULT_LABEL_HALO_PX)
    color = _resolve_style(scene, elem, 'label_halo_color', default=expand(rendering.get('label_halo_color')))
    color = as_hex(color) or as_hex(background) or '#ffffff'
    opacity = number(_resolve_style(scene, elem, 'label_halo_opacity',
                                    default=expand(rendering.get('label_halo_opacity', 1.0))), 1.0)
    return {'widthPx': max(width, 0.0), 'color': color, 'opacity': min(max(opacity, 0.0), 1.0)}


def _label_text(scene, elem) -> str:
    """Resolve imported dynamic captions without bypassing style priority.

    The import layer stores a text-object name. Read its current content on
    every call so hidden sources and animation updates work, while explicit
    label_text, overlays, disabled import and import-policy overrides retain
    their existing semantics. Invalid references use the ordinary fallback.
    """
    label_text = _resolve_style(scene, elem, 'label_text',
                                default=_default_label_text(scene, elem))
    if not (getattr(elem, 'ggb_style', None) or {}).get('label_dynamic_caption'):
        return str(label_text)
    source, _ = _trace_style(scene, elem, 'label_text')
    if source not in ('elem.style', 'overlay.per_name', 'overlay.per_type'):
        ref = _resolve_style(scene, elem, 'label_dynamic_caption')
        construction = getattr(scene, 'geo', None)
        if ref and construction is not None:
            from .geo.lib_elements import Text, text_to_display_latex

            name = getattr(construction, 'name_mapping', {}).get(ref, ref)
            obj = construction.objectByName(name)
            data = getattr(obj, 'data', None)
            if isinstance(data, Text):
                content = text_to_display_latex(
                    construction, data, getattr(construction, 'ggb_decimals', 2))
                # Captions are inline labels even if their source text uses
                # display delimiters. Keep JSXGraph and value-label joins valid.
                if data.is_latex and _math_inner(content) != content:
                    return _math_wrap(_math_inner(content))
                return content
    return str(label_text)


def resolve_label_text(scene, elem) -> str:
    """Return the final TeX label text for an element."""
    label_text = _label_text(scene, elem)
    mode = normalize_label_mode(_resolve_style(scene, elem, "label_mode", default=LABEL_MODE_LABEL))
    if mode == LABEL_MODE_LABEL:
        return str(label_text)

    formatted_value = format_label_value(scene, elem)
    if formatted_value is None:
        return str(label_text)
    if mode == LABEL_MODE_VALUE:
        return _math_wrap(formatted_value)

    separator = _resolve_style(scene, elem, "label_value_separator", default=" = ")
    return _math_wrap(_math_inner(str(label_text)) + str(separator) + _math_inner(formatted_value))


def resolve_label_spec(scene, elem) -> LabelSpec:
    """Return a :class:`LabelSpec` for an element.

    ``text`` is delegated to :func:`resolve_label_text` so the Tex fallback is
    byte-for-byte identical; the remaining fields expose the numeric value and
    its static prefix/suffix for the DecimalNumber render path.
    """
    text = resolve_label_text(scene, elem)
    mode = normalize_label_mode(
        _resolve_style(scene, elem, "label_mode", default=LABEL_MODE_LABEL)
    )
    if mode == LABEL_MODE_LABEL:
        return LabelSpec(text=text, mode=mode)

    lv = label_value_of(elem)
    if lv is None:
        # Mode requested a value but the element has none — behaves as label.
        return LabelSpec(text=text, mode=mode)

    # Booleans (and any non-numeric value) are cheap and only have a couple of
    # states; keep them on the Tex path (no dynamic value).
    if lv.kind == "boolean":
        return LabelSpec(text=text, mode=mode, kind="boolean")

    precision = _resolve_style(
        scene, elem, "label_value_precision",
        default=_rendering_default(scene, "label_value_precision", DEFAULT_LABEL_VALUE_PRECISION),
    )
    try:
        num_decimal_places = max(0, int(precision))
    except (TypeError, ValueError):
        num_decimal_places = DEFAULT_LABEL_VALUE_PRECISION
    strip_zeros = bool(_resolve_style(scene, elem, "label_value_strip_zeros", default=True))

    suffix_tex = None
    suffix_raised = False
    if lv.kind == "angle":
        angle_value = _display_angle_value(scene, elem, float(lv.value))
        unit = _resolve_style(scene, elem, "label_angle_unit", default="degree")
        if unit == "radian":
            display_value = angle_value
        else:
            display_value = angle_value * 180.0 / math.pi
            suffix_tex = r"^{\circ}"
            suffix_raised = True
    else:
        try:
            display_value = float(lv.value)
        except (TypeError, ValueError):
            # Non-numeric scalar: fall back to Tex.
            return LabelSpec(text=text, mode=mode, kind=lv.kind)

    # Non-finite values render much better through TeX (\infty, NaN), so leave
    # them on the fallback path.
    if not math.isfinite(display_value):
        return LabelSpec(text=text, mode=mode, kind=lv.kind)

    prefix_tex = None
    if mode == LABEL_MODE_LABEL_VALUE:
        label_text = _label_text(scene, elem)
        separator = _resolve_style(scene, elem, "label_value_separator", default=" = ")
        prefix_tex = _math_wrap(_math_inner(str(label_text)) + str(separator))

    return LabelSpec(
        text=text,
        mode=mode,
        prefix_tex=prefix_tex,
        value=display_value,
        kind=lv.kind,
        num_decimal_places=num_decimal_places,
        strip_zeros=strip_zeros,
        suffix_tex=suffix_tex,
        suffix_raised=suffix_raised,
    )


def format_label_value(scene, elem) -> str | None:
    """Format the value part of a label as TeX-safe text."""
    lv = label_value_of(elem)
    if lv is None:
        return None
    if lv.kind == "boolean":
        return r"\mathrm{" + ("true" if bool(lv.value) else "false") + "}"

    precision = _resolve_style(
        scene,
        elem,
        "label_value_precision",
        default=_rendering_default(
            scene,
            "label_value_precision",
            DEFAULT_LABEL_VALUE_PRECISION,
        ),
    )
    strip_zeros = bool(_resolve_style(scene, elem, "label_value_strip_zeros", default=True))
    if lv.kind == "angle":
        unit = _resolve_style(scene, elem, "label_angle_unit", default="degree")
        angle_value = _display_angle_value(scene, elem, float(lv.value))
        if unit == "radian":
            return _format_number(angle_value, precision, strip_zeros)
        degrees = angle_value * 180.0 / math.pi
        return _format_number(degrees, precision, strip_zeros) + r"^{\circ}"
    try:
        return _format_number(float(lv.value), precision, strip_zeros)
    except (TypeError, ValueError):
        return str(lv.value)


def label_value_of(elem) -> LabelValue | None:
    """Extract a scalar display value from an element or variable."""
    from .geo.lib_elements import Angle, Circle, Element, Polygon, Segment, Vector
    from .geo.lib_vars import AngleSize, Boolean, Measure, Var

    data = getattr(elem, "data", elem)
    if isinstance(elem, Var):
        data = elem.data
    if isinstance(elem, Element):
        data = elem.data

    if isinstance(data, AngleSize):
        return LabelValue(data.value, "angle")
    if isinstance(data, Angle):
        return LabelValue(data.value, "angle")
    if isinstance(data, Boolean):
        return LabelValue(data.value, "boolean")
    if isinstance(data, Measure):
        return LabelValue(data.value, "number")
    if isinstance(data, Segment):
        return LabelValue(data.length, "number")
    if isinstance(data, Vector):
        return LabelValue(float(np.linalg.norm(data.direction)), "number")
    if isinstance(data, Circle):
        return LabelValue(data.radius, "number")
    if isinstance(data, Polygon):
        return LabelValue(data.area, "number")
    if isinstance(data, (int, float)):
        return LabelValue(data, "number")
    return None


def _format_number(value: float, precision: Any, strip_zeros: bool) -> str:
    if not math.isfinite(value):
        if math.isnan(value):
            return r"\mathrm{NaN}"
        return r"\infty" if value > 0 else r"-\infty"
    try:
        precision_int = max(0, int(precision))
    except (TypeError, ValueError):
        precision_int = DEFAULT_LABEL_VALUE_PRECISION
    if abs(value) < 0.5 * 10 ** (-precision_int):
        value = 0.0
    text = f"{value:.{precision_int}f}"
    if strip_zeros and "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _rendering_default(scene, key: str, default: Any) -> Any:
    cfg = getattr(scene, "style_config", None)
    if cfg is None and hasattr(scene, "rendering"):
        cfg = scene
    rendering = getattr(cfg, "rendering", None)
    if isinstance(rendering, dict) and key in rendering:
        return rendering[key]
    return default


def _display_angle_value(scene, elem, value: float) -> float:
    data = getattr(elem, "data", None)
    if type(data).__name__ != "Angle":
        return value
    angle_range = _resolve_style(scene, elem, "angle_range", default="minor") or "minor"
    if angle_range == "minor" and value > math.pi:
        return 2 * math.pi - value
    if angle_range == "reflex" and value < math.pi:
        return 2 * math.pi - value
    return value


def _math_inner(text: str) -> str:
    if len(text) >= 4 and text.startswith('$$') and text.endswith('$$'):
        return text[2:-2]
    if len(text) >= 2 and text[0] == "$" and text[-1] == "$":
        return text[1:-1]
    if ((text.startswith(r'\(') and text.endswith(r'\)'))
            or (text.startswith(r'\[') and text.endswith(r'\]'))):
        return text[2:-2]
    return text


def _math_wrap(text: str) -> str:
    if len(text) >= 2 and text[0] == "$" and text[-1] == "$":
        return text
    return "$" + text + "$"


# ── Label TeX (shared by the manim renderer and the native label layout) ──

# Unicode ← TeX symbol mappings for label text
_TEX_SYMBOLS = {
    '\\cdot': '·', '\\times': '×', '\\neq': '≠', '\\approx': '≈', '\\sim': '~',
    '\\leqslant': '⩽', '\\geqslant': '⩾',
    '\\degree': '°', '\\Rightarrow': '⇒', '\\Leftarrow': '⇐',
    '\\rightarrow': '→', '\\to': '→', '\\gets': '←',
    '\\mathbf': '∠', '\\triangle': '△', '\\perp': '⊥',
    '\\parallel': '∥', '\\nparralel': '∦',
    '\\in': '∈', '\\notin': '∉', '\\cap': '∩', '\\cup': '∪',
    '\\subset': '⊂', '\\supset': '⊃', '\\subseteq': '⊆', '\\supseteq': '⊇',
    '\\forall': '∀', '\\exists': '∃',
    '\\Longleftrightarrow': '⟺', '\\Leftrightarrow': '⟺',
    '\\pm': '±', '\\varnothing': '∅', '\\infty': '∞',
    '\\mathrm A': 'Α', '\\alpha': 'α',
    '\\mathrm B': 'Β', '\\beta': 'β',
    '\\Gamma': 'Γ', '\\gamma': 'γ',
    '\\Delta': 'Δ', '\\delta': 'δ',
    '\\mathrm E': 'Ε', '\\varepsilon': 'ε',
    '\\mathrm Z': 'Ζ', '\\zeta': 'ζ',
    '\\mathrm H': 'Η', '\\eta': 'η',
    '\\Theta': 'Θ', '\\theta': 'ϑ', '\\vartheta': 'ϑ',
    '\\mathrm I': 'Ι', '\\iota': 'ι',
    '\\mathrm K': 'Κ', '\\kappa': 'κ',
    '\\Lambda': 'Λ', '\\lambda': 'λ',
    '\\mathrm M': 'Μ', '\\mu': 'μ',
    '\\mathrm N': 'Ν', '\\nu': 'ν',
    '\\Xi': 'Ξ', '\\xi': 'ξ',
    '\\mathrm O': 'Ο', '\\mathrm o': 'ο',
    '\\Pi': 'Π', '\\pi': 'π', '\\varpi': 'ϖ',
    '\\mathrm P': 'Ρ', '\\rho': 'ρ',
    '\\Sigma': 'Σ', '\\sigma': 'σ', '\\varsigma': 'ς',
    '\\mathrm T': 'Τ', '\\tau': 'τ',
    '\\Upsilon': 'Υ', '\\upsilon': 'υ',
    '\\Phi': 'Φ', '\\varphi': 'φ',
    '\\mathrm X': 'Χ', '\\chi': 'χ',
    '\\Psi': 'Ψ', '\\psi': 'ψ',
    '\\Omega': 'Ω', '\\omega': 'ω',
}


def correctedLabel(label):
    """Replace Unicode math symbols with their TeX equivalents in a label string."""
    from .geo.lib_elements import textify_cyrillic
    for tex, unicode_char in _TEX_SYMBOLS.items():
        label = re.sub(re.escape(unicode_char), re.sub(r'\\', r'\\\\', tex), label)
    return _brace_nonascii_scripts(textify_cyrillic(label))


# Any other stray non-ASCII character is more than one token under utf8/T2A, so
# a bare ``A_∡`` makes LaTeX stop at "! Missing { inserted". Braces make it one
# argument. ASCII scripts (``A_1``, ``x^2``, ``A_\alpha``) already are.
_NONASCII_SCRIPT_RE = re.compile(r'(?<!\\)([_^])([^\x00-\x7F])')


def _brace_nonascii_scripts(label):
    """Wrap a non-ASCII sub/superscript argument in braces: ``A_∡`` → ``A_{∡}``."""
    return _NONASCII_SCRIPT_RE.sub(r'\1{\2}', label)
