"""Final label text resolution for GeoGebra-like label display modes."""
from __future__ import annotations

import math
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
        Whether the Tex fallback strips trailing zeros (DecimalNumber keeps
        fixed decimals so animated labels do not jitter in width).
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
    """``$...$`` fallback label text using the display name (primes/subscripts)."""
    return "$" + _display_name(scene, elem) + "$"


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
