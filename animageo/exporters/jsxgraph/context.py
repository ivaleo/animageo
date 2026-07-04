"""Shared context for JSXGraph emitters.

Bundles the scene, options and the helpers every emitter needs: style
resolution (the same resolver the renderer/SVG/TikZ use), label text, number
formatting and JS-reference generation.

Unlike SVG/TikZ, geometry is emitted in **math units** directly (JSXGraph works
in MU with a ``boundingbox``); only style *sizes* (point size, stroke width)
are pixels — and those are pixels in JSXGraph too, so no conversion.

Elements are stored in a JS map ``S`` keyed by their AnimaGeo name, so parent
references are robust regardless of identifier-unsafe names (subscripts/primes):
``S["A"]`` rather than a bare ``A`` variable.
"""
from __future__ import annotations

import json
import math
from typing import Any

from ...labels import resolve_label_text
from ...style.resolver import resolve as _resolve
from .options import JSXGraphOptions


class Raw:
    """Marker for a verbatim JS expression in an attribute dict (not quoted)."""

    __slots__ = ("js",)

    def __init__(self, js: str):
        self.js = js


class JsxContext:
    def __init__(self, scene, options: JSXGraphOptions):
        self.scene = scene
        self.opt = options
        self.geo = scene.geo
        # The independents dict (from Construction.get_independents); set by the
        # builder so emitters can detect slider-driven values (e.g. a circle
        # whose radius is a draggable number → live function radius).
        self.independents: dict = {}

    # ── style / labels ───────────────────────────────────────────────────
    def resolve(self, elem, key: str, default: Any = None) -> Any:
        return _resolve(self.scene, elem, key, default=default)

    def label_text(self, elem) -> str:
        return resolve_label_text(self.scene, elem)

    def label_visible(self, elem) -> bool:
        return self.resolve(elem, "label_visible", default=False) is True

    # ── names / references ───────────────────────────────────────────────
    @staticmethod
    def name_of(obj) -> str:
        return getattr(obj, "name", obj) if not isinstance(obj, str) else obj

    def ref(self, obj) -> str:
        """JS reference to a previously-created element: ``S["name"]``."""
        return f"S[{json.dumps(self.name_of(obj))}]"

    # ── input resolution (for command emitters) ──────────────────────────
    def element(self, name):
        return self.geo.element(name)

    def input_elem(self, inp):
        """The AnimaGeo element for a command input (name/object), or None for
        a literal."""
        if isinstance(inp, (int, float)):
            return None
        return self.geo.element(self.name_of(inp))

    @staticmethod
    def is_number(x) -> bool:
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    def is_independent_value(self, name) -> bool:
        info = self.independents.get(self.name_of(name))
        return bool(info) and info.get("type") in ("number", "measure", "angle")

    @staticmethod
    def data_typename(elem) -> str:
        return type(elem.data).__name__ if elem is not None and hasattr(elem, "data") else ""

    # ── number / value formatting ─────────────────────────────────────────
    def num(self, value: float) -> str:
        p = self.opt.coordinate_precision
        if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
            return "0"
        v = float(value)
        if abs(v) < 0.5 * 10 ** (-p):
            return "0"
        s = f"{v:.{p}f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s

    def js_value(self, x) -> str:
        """Format a Python value as a JS literal (number/str/bool/Raw)."""
        if isinstance(x, Raw):
            return x.js
        if isinstance(x, bool):
            return "true" if x else "false"
        if isinstance(x, (int, float)):
            return self.num(x)
        return json.dumps(x)

    # ── geometry ──────────────────────────────────────────────────────────
    def boundingbox(self):
        if self.opt.boundingbox is not None:
            return tuple(self.opt.boundingbox)
        left, bottom, right, top = self.scene._get_scene_bounds(padding=0)
        return (left, top, right, bottom)  # JSXGraph order

    def is_visible(self, elem) -> bool:
        return self.scene._element_visible(elem)
