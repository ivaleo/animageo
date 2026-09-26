"""Compact construction summaries for AI style-generation prompts.

The output intentionally avoids raw ``.ggb`` XML. It keeps only the structural
and visual facts that help an LLM decide which style layer to use: element
names, canonical types, compact geometry, visibility, imported GGB style, and
optional explicit/resolved style layers.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from ..geo import construction as geo


SCHEMA_ID = "animageo-construction-summary/v1"

DEFAULT_STYLE_KEYS = (
    "visible",
    "label_visible",
    "label_text",
    "label_mode",
    "label_value_precision",
    "label_value_strip_zeros",
    "label_angle_unit",
    "label_value_separator",
    "label_color",
    "label_anchor",
    "label_offset_px",
    "label_radial_offset_px",
    "font_size_px",
    "stroke",
    "stroke_width_px",
    "stroke_opacity",
    "stroke_dash_ratio",
    "stroke_dash_period_px",
    "stroke_linecap",
    "fill",
    "fill_opacity",
    "size_px",
    "point_shape",
    "angle_range",
    "arc_size_px",
    "arc_shift_px",
    "right_angle_size_px",
    "right_angle_marker",
    "tick_count",
    "tick_style",
    "tick_length_px",
    "tick_width_px",
    "tick_shift_px",
    "tick_radius_px",
    "arrow_length_px",
    "arrow_width_px",
    "z_index",
    "z_index_fill",
)


def construction_to_ai_summary(
    construction,
    *,
    source: dict[str, Any] | None = None,
    viewport: dict[str, Any] | None = None,
    include_geometry: bool = True,
    include_ggb_style: bool = True,
    include_style: bool = False,
    include_resolved_style: bool = False,
    resolved_style_fn: Callable[[Any], dict[str, Any]] | None = None,
    include_axes: bool = False,
    max_elements: int | None = None,
    style_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a compact JSON-serializable construction summary.

    Args:
        construction: ``geo.Construction`` or any object exposing
            ``.elements``, ``.commands`` and ``.command_diagnostics``.
        source: Optional source metadata, e.g. ``{"kind": "ggb",
            "name": "scene.ggb"}``.
        viewport: Optional export/view metadata such as ``size`` and
            ``ptUnit_ggb``.
        include_geometry: Include compact geometry payloads.
        include_ggb_style: Include selected ``elem.ggb_style`` keys.
        include_style: Include explicit/intrinsic ``elem.style`` keys. This
            can be noisy; off by default because global AI style generation
            usually cares about imported style and names/types.
        include_resolved_style: Include effective style via ``resolved_style_fn``.
            Use from scene-level APIs where the resolver is available.
        resolved_style_fn: Callable receiving an element and returning a dict.
        include_axes: Include default hidden ``xAxis``/``yAxis`` elements.
        max_elements: Optional cap for large constructions. Elements after the
            cap are omitted but counted in ``truncated``.
        style_keys: Optional allow-list for style payloads. Defaults to
            ``DEFAULT_STYLE_KEYS``.
    """

    keys = tuple(style_keys or DEFAULT_STYLE_KEYS)
    all_elements = [
        elem for elem in getattr(construction, "elements", [])
        if include_axes or elem.name not in {"xAxis", "yAxis"}
    ]
    included_elements = all_elements
    truncated = None
    if max_elements is not None and max_elements >= 0 and len(all_elements) > max_elements:
        included_elements = all_elements[:max_elements]
        truncated = {
            "max_elements": int(max_elements),
            "omitted_count": len(all_elements) - max_elements,
            "omitted_names": [elem.name for elem in all_elements[max_elements:]],
        }

    output_to_command = _command_index(getattr(construction, "commands", []))
    elements = [
        _serialize_element(
            elem,
            output_to_command=output_to_command,
            include_geometry=include_geometry,
            include_ggb_style=include_ggb_style,
            include_style=include_style,
            include_resolved_style=include_resolved_style,
            resolved_style_fn=resolved_style_fn,
            style_keys=keys,
        )
        for elem in included_elements
    ]

    stats = dict(sorted(Counter(item["type"] for item in elements).items()))
    groups = {
        f"{type_name}s": [item["name"] for item in elements if item["type"] == type_name]
        for type_name in stats
    }

    summary: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "source": source or {"kind": "unknown"},
        "viewport": _json_safe(viewport or {}),
        "stats": stats,
        "elements": elements,
        "groups": groups,
        "warnings": _json_safe(getattr(construction, "command_diagnostics", []) or []),
    }
    if truncated is not None:
        summary["truncated"] = truncated

    vars_payload = _serialize_vars(getattr(construction, "vars", []))
    if vars_payload:
        summary["vars"] = vars_payload

    return summary


def write_ai_summary(
    construction,
    filepath: str | Path,
    **kwargs,
) -> dict[str, Any]:
    """Write :func:`construction_to_ai_summary` output to ``filepath``.

    Returns the same summary dict that was written.
    """

    summary = construction_to_ai_summary(construction, **kwargs)
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return summary


def _serialize_element(
    elem,
    *,
    output_to_command,
    include_geometry: bool,
    include_ggb_style: bool,
    include_style: bool,
    include_resolved_style: bool,
    resolved_style_fn,
    style_keys,
) -> dict[str, Any]:
    etype = _etype(elem)
    item: dict[str, Any] = {
        "name": str(elem.name),
        "type": etype,
        "visible": bool(getattr(elem, "visible", True)),
        "label_visible": _style_bool(elem, "label_visible"),
    }

    command = output_to_command.get(elem.name)
    if command is not None:
        item["construction"] = {
            "command": str(getattr(command, "name", "")),
            "inputs": [_json_safe(_name_of_input(x)) for x in getattr(command, "inputs", [])],
            "outputs": [_json_safe(_name_of_input(x)) for x in getattr(command, "outputs", [])],
        }

    if include_geometry:
        geometry = _geometry_payload(elem)
        if geometry:
            item["geometry"] = geometry

    if include_ggb_style:
        ggb_style = _filter_style(getattr(elem, "ggb_style", {}) or {}, style_keys)
        if ggb_style:
            item["ggb_style"] = ggb_style

    if include_style:
        style = _filter_style(getattr(elem, "style", {}) or {}, style_keys)
        if style:
            item["style"] = style

    if include_resolved_style and resolved_style_fn is not None:
        resolved = _filter_style(resolved_style_fn(elem) or {}, style_keys)
        if resolved:
            item["resolved_style"] = resolved

    raw = getattr(elem, "ggb_raw", {}) or {}
    if raw:
        item["ggb_raw_summary"] = _ggb_raw_summary(raw)

    return item


def _serialize_vars(vars_):
    out = []
    for var in vars_:
        payload = {
            "name": str(getattr(var, "name", "")),
            "type": type(getattr(var, "data", None)).__name__.lower(),
            "value": _json_safe(_value_of_var(getattr(var, "data", None))),
        }
        out.append(payload)
    return out


def _value_of_var(data):
    if hasattr(data, "value"):
        return data.value
    return data


def _command_index(commands):
    out = {}
    for command in commands:
        for output in getattr(command, "outputs", []) or []:
            out[str(_name_of_input(output))] = command
    return out


def _name_of_input(value):
    return getattr(value, "name", value)


def _etype(elem) -> str:
    data = getattr(elem, "data", None)
    if data is None:
        raw_type = (getattr(elem, "ggb_raw", {}) or {}).get("elem_type")
        return str(raw_type or "unknown")
    return type(data).__name__.lower()


def _style_bool(elem, key: str):
    for source in (getattr(elem, "ggb_style", None), getattr(elem, "style", None)):
        if source is not None and key in source:
            return bool(source[key])
    return None


def _filter_style(style: dict[str, Any], keys) -> dict[str, Any]:
    if not isinstance(style, dict):
        return {}
    return {
        key: _json_safe(style[key])
        for key in keys
        if key in style and _json_safe(style[key]) is not None
    }


def _ggb_raw_summary(raw: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "elem_type",
        "point_size",
        "point_style",
        "line_thickness",
        "line_opacity",
        "line_type",
        "arc_size",
        "angle_style",
        "decoration_lines",
        "show_object",
        "show_label",
        "label_caption",
        "label_offset_px",
    )
    out = {key: _json_safe(raw[key]) for key in keep if key in raw}
    obj_color = raw.get("obj_color")
    if isinstance(obj_color, dict):
        out["obj_color"] = {
            key: _json_safe(obj_color[key])
            for key in ("hex", "opacity", "alpha")
            if key in obj_color
        }
    return out


def _geometry_payload(elem) -> dict[str, Any]:
    data = getattr(elem, "data", None)
    if data is None:
        return {}

    if isinstance(data, geo.Point):
        return {"coords": _json_safe(data.coords)}
    if isinstance(data, geo.Segment):
        return {
            "endpoints": _json_safe(data.endpoints),
            "length": _json_safe(data.length),
        }
    if isinstance(data, geo.Ray):
        return {
            "start": _json_safe(data.start),
            "direction": _json_safe(data.direction),
        }
    if isinstance(data, geo.Line):
        return {
            "normal": _json_safe(data.normal),
            "direction": _json_safe(getattr(data, "direction", None)),
            "offset": _json_safe(data.offset),
        }
    if isinstance(data, geo.Angle):
        return {
            "vertex": _json_safe(data.vertex),
            "side1": _json_safe(data.side1),
            "side2": _json_safe(data.side2),
            "size_rad": _json_safe(data.size),
            "size_deg": _json_safe(data.size * 180 / math.pi),
            "start_angle": _json_safe(data.start_angle),
            "end_angle": _json_safe(data.end_angle),
        }
    if isinstance(data, geo.Polygon):
        return {
            "vertices": _json_safe(data.vertices),
            "vertex_count": int(len(data.vertices)),
        }
    if isinstance(data, geo.CircleSector):
        return {
            "center": _json_safe(data.center),
            "radius": _json_safe(data.radius),
            "angles": _json_safe(data.angles),
        }
    if isinstance(data, geo.Arc):
        return {
            "center": _json_safe(data.center),
            "radius": _json_safe(data.radius),
            "angles": _json_safe(data.angles),
        }
    if isinstance(data, geo.Circle):
        return {
            "center": _json_safe(data.center),
            "radius": _json_safe(data.radius),
        }
    if isinstance(data, geo.Vector):
        return {
            "endpoints": _json_safe(data.endpoints),
            "direction": _json_safe(data.direction),
        }
    if isinstance(data, geo.Conic):
        return {
            "kind": getattr(data.type, "value", str(data.type)),
            "matrix": _json_safe(data.matrix),
        }
    if isinstance(data, geo.Function):
        return {
            "source": _json_safe(getattr(data, "source", None)),
            "expr": str(getattr(data, "expr", "")),
            "var": str(getattr(data, "var", "")),
            "domain": _json_safe(getattr(data, "explicit_domain", None)),
        }
    if isinstance(data, geo.ImplicitCurve):
        return {
            "source": _json_safe(getattr(data, "source", None)),
            "expr": str(getattr(data, "expr", "")),
            "var_x": str(getattr(data, "var_x", "")),
            "var_y": str(getattr(data, "var_y", "")),
        }
    return {"repr": repr(data)}


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
