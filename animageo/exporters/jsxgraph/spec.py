"""Declarative, versioned board spec — ``animageo-board/v1``.

The structured, **eval-free** representation of a board: a topologically-ordered
list of elements plus an interactive-input schema. Each element carries its
AnimaGeo *semantic* identity (``role`` / ``kind`` / source ``detail`` /
``tracksDrag``) **and** a concrete engine render-instruction (``engine`` creator
+ structured ``parents`` + ``attrs``).

The framework-agnostic JS runtime consumes this directly: it builds every entry
in ``elements`` in order, and reads ``inputs`` to know which elements are
stateful (and their kinds/bounds) for ``getState`` / ``setState``. No JS strings
need to be evaluated by the consumer — the only embedded JS is a contained
``{"fn": …}`` for live function-valued parents (e.g. a slider-driven radius) and
a ``{"js": …}`` / ``bind`` / ``stmt`` escape hatch for the few advanced live
constructs (transforms, polygon-border binding).

``builder.build_board`` records these alongside the legacy JS ``statements``
(which still drive the ``html`` / ``js`` outputs); ``document.render``
serialises them for ``output="spec"``.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .context import Raw

SPEC_FORMAT = "animageo-board/v1"
SCHEMA_FILENAME = "board.schema.json"


def load_schema() -> Dict[str, Any]:
    """Return the JSON Schema for ``animageo-board/v1`` as a dict.

    Read from the packaged ``board.schema.json`` via ``importlib.resources`` so
    it works from an installed wheel, not just a source checkout."""
    from importlib.resources import files
    text = (files(__package__) / SCHEMA_FILENAME).read_text(encoding="utf-8")
    return json.loads(text)

# Exactly ``S["name"]`` — a reference to a previously-created element.
_REF_RE = re.compile(r'S\[("(?:[^"\\]|\\.)*")\]\Z')


def classify_parent(p: Any) -> Any:
    """Turn a builder parent (a JS-expression string or :class:`Raw`) into a
    structured, JSON-serialisable form for the spec.

    Forms emitted: ``{"ref": name}`` (element reference), a number, a coordinate
    pair / sampled polyline (``[x, y]`` / ``[[…], [null, …]]`` — ``NaN`` → null
    poly break), a bare string literal, ``{"fn": body}`` (live function
    parent), or ``{"js": expr}`` (verbatim escape hatch)."""
    if isinstance(p, Raw):
        return {"fn": p.js}
    s = str(p)
    m = _REF_RE.match(s)
    if m:
        return {"ref": json.loads(m.group(1))}
    if s[:1] == "[" and s[-1:] == "]":
        try:
            return json.loads(s.replace("NaN", "null"))
        except ValueError:
            return {"js": s}
    if s == "true" or s == "false":
        return s == "true"
    try:
        f = float(s)
    except ValueError:
        f = None
    if f is not None:
        # A non-finite scalar (NaN/Infinity) would serialise to invalid JSON
        # (bare ``NaN``/``Infinity``) that JS ``JSON.parse`` rejects — keep the
        # spec strictly JSON-valid by routing it through the {"js": …} hatch.
        if not math.isfinite(f):
            return {"js": s}
        # Preserve integers (e.g. an intersection branch index) as ints.
        if "." not in s and "e" not in s and "E" not in s and f.is_integer():
            return int(f)
        return f
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except ValueError:
            pass
    return {"js": s}


def _jsonable_attrs(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Copy an attribute dict, turning any stray :class:`Raw` into ``{"js": …}``
    and recursing into nested dicts (e.g. ``label``)."""
    out: Dict[str, Any] = {}
    for k, v in attrs.items():
        if isinstance(v, Raw):
            out[k] = {"js": v.js}
        elif isinstance(v, dict):
            out[k] = _jsonable_attrs(v)
        else:
            out[k] = v
    return out


@dataclass
class SpecElement:
    """One board entry. ``form`` discriminates:

    - ``create`` — ``board.create(engine, parents, attrs)``;
    - ``bind``   — ``S[name] = <bind>`` (a reference to a sub-object, e.g. a
      polygon border);
    - ``stmt``   — a verbatim JS statement (anonymous; advanced live constructs).
    """

    name: str
    form: str = "create"
    role: str = "aux"               # input | live | static | skip | aux
    kind: str = ""                  # AnimaGeo semantic kind
    engine: str = ""                # JSXGraph creator (form=create)
    parents: List[Any] = field(default_factory=list)
    attrs: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    tracks_drag: Optional[bool] = None
    bind: str = ""                  # form=bind
    stmt: str = ""                  # form=stmt

    def to_json(self) -> Dict[str, Any]:
        if self.form == "stmt":
            return {"form": "stmt", "js": self.stmt}
        d: Dict[str, Any] = {"name": self.name, "role": self.role}
        if self.kind:
            d["kind"] = self.kind
        if self.form == "bind":
            d["form"] = "bind"
            d["bind"] = self.bind
        else:
            d["engine"] = self.engine
            d["parents"] = self.parents
            if self.attrs:
                d["attrs"] = self.attrs
        if self.detail:
            d["detail"] = self.detail
        if self.tracks_drag is not None:
            d["tracksDrag"] = self.tracks_drag
        return d


@dataclass
class InputSpec:
    """Schema for one interactive input — the unit of state and of
    ``change``/``commit`` signals."""

    name: str
    kind: str                       # point | number | angle | boolean | glider
    value: Any = None               # number/angle/boolean current value
    x: Optional[float] = None       # point/glider
    y: Optional[float] = None
    on: Optional[str] = None        # glider: parent curve name
    t: Optional[float] = None       # glider: parameter (informational)
    min: Optional[float] = None     # number/angle slider bounds
    max: Optional[float] = None
    step: Optional[float] = None

    def to_json(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name, "kind": self.kind}
        for key in ("value", "x", "y", "on", "t", "min", "max", "step"):
            v = getattr(self, key)
            if v is not None:
                d[key] = v
        return d


def chrome_to_json(chrome) -> Dict[str, Any]:
    """Serialise board chrome (axes/grid/background/…) — shared with the legacy
    ``json`` output so the two stay consistent."""
    return {
        "axis": chrome.axis,
        "grid": chrome.grid,
        "background": chrome.background,
        "axesColor": chrome.axes_color,
        "gridColor": chrome.grid_color,
        "showXAxis": chrome.show_x_axis,
        "showYAxis": chrome.show_y_axis,
        "keepAspectRatio": chrome.keep_aspect,
        "gridBold": chrome.grid_bold,
        "gridStep": list(chrome.grid_step) if chrome.grid_step else None,
        "xShowNumbers": chrome.x_show_numbers,
        "yShowNumbers": chrome.y_show_numbers,
        "xTickDistance": chrome.x_tick_distance,
        "yTickDistance": chrome.y_tick_distance,
    }


def board_to_spec(model, opt, *, width: int, height: int) -> Dict[str, Any]:
    """Assemble the full ``animageo-board/v1`` document from a ``BoardModel``."""
    return {
        "format": SPEC_FORMAT,
        "boundingbox": [round(float(v), 6) for v in model.boundingbox],
        "size": [int(width), int(height)],
        "chrome": chrome_to_json(model.chrome),
        "options": {
            "mathjax": opt.mathjax,
            "showNavigation": opt.shownavigation,
            "jsxgraphVersion": opt.jsxgraph_version,
            "divId": opt.div_id,
        },
        "inputs": [i.to_json() for i in model.input_schema],
        "elements": [e.to_json() for e in model.elements],
        "coverage": [
            {"name": n, "kind": k, "detail": d} for n, k, d in model.coverage
        ],
        # GeoGebra px-per-unit the label `offset`s were authored at, so a live
        # board can rescale them to its own render scale (see BoardModel).
        "ptUnitGgb": round(model.ptunit_ggb, 6) if model.ptunit_ggb else None,
        # Export px-per-unit; lets a live board reproduce the absolute pixel size
        # of pixel-sized decorations (angle arcs) the static frame used.
        "ptUnitExport": round(model.ptunit_export, 6) if model.ptunit_export else None,
    }
