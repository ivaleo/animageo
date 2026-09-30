"""Build a JSXGraph board model from an AnimaGeo construction.

Walks the construction graph (independents → interactive widgets; commands in
topological order → live ``command_map`` creators, multi-output ``intersect``,
or static fallback) and produces the list of ``board.create`` statements plus a
coverage report.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ...geo.lib_commands import strCommand
from ...geo.lib_elements import Text, resolve_text_position, resolve_text_string
from .command_map import Emit, emitter_for, value_expr
from .context import JsxContext, Raw
from .spec import InputSpec, SpecElement, _jsonable_attrs, classify_parent
from .style_map import _hex, base_attrs, js_attrs, label_name, point_attrs


def _render_parent(p) -> str:
    """A command parent is either a ready JS-expression string (``S["A"]``,
    ``3``) or a ``Raw`` (a live function expression)."""
    return p.js if isinstance(p, Raw) else str(p)

logger = logging.getLogger(__name__)

_DRAGGABLE = (
    "free_point", "tparam_point", "free_text",
    "number", "measure", "angle", "boolean",
)


@dataclass
class BoardChrome:
    """Board-level appearance imported from the GeoGebra scene (or option
    overrides): axes/grid visibility, background, axes/grid colours, grid
    boldness/spacing, per-axis tick numbering/spacing, and aspect ratio.

    Mirrors what the SVG renderer honours (``animageo.py:_render_axes_grid``):
    ``gridIsBold`` → grid stroke width, ``gridDistX/Y`` → grid spacing, per-axis
    ``showNumbers`` → tick labels, ``tickDistance`` → tick spacing, and the
    GeoGebra x/y unit scale → keep-aspect-ratio. (GeoGebra polar/isometric
    grids and axis line dash/arrow styles have no JSXGraph equivalent and are
    not reproduced — same as the SVG renderer.)"""
    axis: bool = True
    grid: bool = False
    background: Optional[str] = None     # CSS hex, or None to leave unset
    axes_color: Optional[str] = None
    grid_color: Optional[str] = None
    show_x_axis: bool = True
    show_y_axis: bool = True
    # Grid appearance/spacing.
    grid_bold: bool = False
    grid_step: Optional[Tuple[float, float]] = None   # (distX, distY) in user units
    # Per-axis tick numbering + spacing.
    x_show_numbers: bool = True
    y_show_numbers: bool = True
    x_tick_distance: Optional[float] = None
    y_tick_distance: Optional[float] = None
    # True → equal px-per-unit on both axes (round circles). False reproduces a
    # GeoGebra scene whose x/y unit scales differ.
    keep_aspect: bool = True


@dataclass
class BoardModel:
    boundingbox: Tuple[float, float, float, float]
    statements: List[str] = field(default_factory=list)
    coverage: List[Tuple[str, str, str]] = field(default_factory=list)  # (name, kind, detail)
    chrome: BoardChrome = field(default_factory=BoardChrome)
    # Declarative spec (animageo-board/v1): structured mirror of `statements`,
    # consumed by the framework-agnostic JS runtime (output="spec").
    elements: List[SpecElement] = field(default_factory=list)
    input_schema: List[InputSpec] = field(default_factory=list)
    # GeoGebra px-per-unit the label offsets were authored at. Label `offset`
    # values are GeoGebra screen pixels at this scale; a live board renders the
    # bbox at a *different* px-per-unit, so a runtime can rescale the offsets
    # (offset_math = offset_px / ptunit_ggb) to keep labels at the same position
    # relative to the geometry as the static export. None when unknown.
    ptunit_ggb: Optional[float] = None
    # Export px-per-unit the static frame was sized at. Decorations whose size is
    # a pixel value (angle arcs, segment ticks) render at this scale in the SVG;
    # a live board can use it to reproduce the same absolute pixel size.
    ptunit_export: Optional[float] = None

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for _n, kind, _d in self.coverage:
            out[kind] = out.get(kind, 0) + 1
        return out


def _resolve_chrome(ctx) -> BoardChrome:
    """Resolve board chrome from the options (authoritative when set) falling
    back to the imported GeoGebra scene, then to GeoGebra's own defaults."""
    opt = ctx.opt
    export = getattr(ctx.scene.style, "export", {}) or {}

    def _tri(opt_val, scene_val, default):
        if opt_val is not None:
            return bool(opt_val)
        if scene_val is not None:
            return bool(scene_val)
        return default

    show_axes = _tri(opt.axis, export.get("showAxes"), True)
    show_grid = _tri(opt.grid, export.get("showGrid"), False)

    # Per-axis visibility (GeoGebra can hide a single axis while showAxes=True).
    axes_cfg = export.get("axes") or {}

    def _axis_show(key):
        v = (axes_cfg.get(key) or {}).get("show")
        return show_axes if v is None else bool(v)

    show_x = show_axes and _axis_show("x")
    show_y = show_axes and _axis_show("y")
    axis = show_x or show_y

    # Background: option override → scene bgColor → scene GeoStyle background.
    if opt.background is not None:
        bg = opt.background or None         # "" disables (page shows through)
    else:
        bg = export.get("background")
        if bg is None:
            sb = getattr(ctx.scene.style, "background", None)
            bg = sb if sb is not None else None

    axes_color = export.get("axesColor")
    grid_color = export.get("gridColor")

    # Grid spacing: GeoGebra <grid distX distY>. Only carry a deliberate,
    # positive spacing; absent → JSXGraph's automatic step.
    def _pos(v):
        try:
            f = float(v)
            return f if f > 0 else None
        except (TypeError, ValueError):
            return None

    gx, gy = _pos(export.get("gridDistX")), _pos(export.get("gridDistY"))
    grid_step = (gx, gy) if (gx is not None and gy is not None) else None

    # GeoGebra grid types: 0 = cartesian, 1 = isometric, 2 = polar,
    # 3 = cartesian + minor lines. JSXGraph only has a rectangular grid, so
    # isometric/polar fall back to it (same as the SVG renderer, which also
    # ignores grid type). Flag it so the difference isn't silent.
    if show_grid and export.get("gridType") in (1, 2):
        logger.warning(
            "JSXGraph export: GeoGebra %s grid has no JSXGraph equivalent; "
            "exporting a rectangular grid instead.",
            "isometric" if export.get("gridType") == 1 else "polar",
        )

    # Per-axis tick numbering + spacing.
    def _axis_numbers(key):
        return (axes_cfg.get(key) or {}).get("showNumbers") is not False

    def _axis_tick_dist(key):
        return _pos((axes_cfg.get(key) or {}).get("tickDistance"))

    # Keep-aspect: equal x/y unit scale → round circles (True). A GeoGebra
    # scene with yscale ≠ xscale is reproduced with keepaspectratio off (the
    # board's bbox is the GGB viewport, so unequal px/unit matches GeoGebra).
    xs, ys = _pos(export.get("ptUnit_ggb") or export.get("ptUnit")), _pos(export.get("ptYUnit_ggb"))
    equal_scale = ys is None or xs is None or abs(xs - ys) <= 1e-6 * max(abs(xs), 1.0)
    if opt.keepaspectratio is not None:
        keep_aspect = bool(opt.keepaspectratio)
    elif opt.boundingbox is not None:
        keep_aspect = True   # a custom bbox is not the GGB viewport → stay safe
    else:
        keep_aspect = equal_scale

    return BoardChrome(
        axis=axis,
        grid=show_grid,
        background=(_hex(bg) if bg else None),
        axes_color=(_hex(axes_color) if axes_color else None),
        grid_color=(_hex(grid_color) if grid_color else None),
        show_x_axis=show_x,
        show_y_axis=show_y,
        grid_bold=bool(export.get("gridIsBold")),
        grid_step=grid_step,
        x_show_numbers=_axis_numbers("x"),
        y_show_numbers=_axis_numbers("y"),
        x_tick_distance=_axis_tick_dist("x"),
        y_tick_distance=_axis_tick_dist("y"),
        keep_aspect=keep_aspect,
    )


def _dynamic_closure(geo, independents) -> set:
    """Names transitively dependent on a draggable independent."""
    seen = set(independents)
    frontier = list(seen)
    while frontier:
        n = frontier.pop()
        for out in geo.state.get(n, {}).get("outputs", []):
            if out not in seen:
                seen.add(out)
                frontier.append(out)
    return seen - set(independents)


def build_board(scene, options) -> BoardModel:
    ctx = JsxContext(scene, options)
    independents = scene.geo.get_independents()
    ctx.independents = independents
    dynamic = _dynamic_closure(scene.geo, independents)

    bbox = ctx.boundingbox()
    export = scene.style.export
    ptunit_ggb = export.get("ptUnit_ggb") or export.get("ptUnit")
    ptunit_export = export.get("ptUnit")
    model = BoardModel(
        boundingbox=bbox,
        chrome=_resolve_chrome(ctx),
        ptunit_ggb=float(ptunit_ggb) if ptunit_ggb else None,
        ptunit_export=float(ptunit_export) if ptunit_export else None,
    )
    emitted: set = set()
    kinds: Dict[str, str] = {}   # name -> JSXGraph element kind (for intersect)

    def create(name, jsx_type, parents, attrs):
        parents_js = ", ".join(_render_parent(p) for p in parents)
        model.statements.append(
            f"S[{json.dumps(name)}] = board.create("
            f"{json.dumps(jsx_type)}, [{parents_js}], {js_attrs(ctx, attrs)});"
        )
        el = SpecElement(
            name=name, form="create", engine=jsx_type,
            parents=[classify_parent(p) for p in parents],
            attrs=_jsonable_attrs(attrs),
        )
        model.elements.append(el)
        emitted.add(name)
        kinds[name] = jsx_type
        return el

    def raw(name, expr, kind="ref"):
        """Register ``S["name"] = <expr>;`` (e.g. a reference to a sub-object)."""
        model.statements.append(f"S[{json.dumps(name)}] = {expr};")
        model.elements.append(SpecElement(name=name, form="bind", bind=expr, kind=kind))
        emitted.add(name)
        kinds[name] = kind

    def raw_stmt(stmt):
        model.statements.append(stmt)
        model.elements.append(SpecElement(name="", form="stmt", stmt=stmt))

    # 1) Free inputs that have no command: free points, sliders, checkboxes.
    _emit_free_inputs(ctx, independents, bbox, create, model)

    # 1b) Level-0 drawables defined directly (functions/conics/lines given
    #     without a command, e.g. `f = Function(...)`) — emit early (static) so
    #     later command outputs can reference them.
    cmd_out_names = {ctx.name_of(o) for c in scene.geo.commands for o in c.outputs}
    for elem in scene.geo.elements:
        name = getattr(elem, "name", None)
        if not name or name in emitted or name in independents or name in cmd_out_names:
            continue
        if not ctx.is_visible(elem):
            continue
        if isinstance(elem.data, Text):
            _emit_text(ctx, elem, create, model)
            continue
        _emit_static(ctx, name, "direct", dynamic, options, create, model)

    # 2) Commands in dependency order.
    for cmd in scene.geo.commands:
        outs = [ctx.name_of(o) for o in cmd.outputs]
        if not outs:
            continue
        primary = outs[0]
        info = independents.get(primary)
        base = strCommand(cmd.name)   # GGB name ("Midpoint") → snake base ("midpoint")

        # 2a) glider (tparam_point) — emit on its parent curve.
        if info and info.get("type") == "tparam_point":
            if _emit_glider(ctx, cmd, primary, info, create, model):
                continue

        # 2b) intersection (possibly multiple outputs, indexed).
        if base == "intersect":
            _emit_intersections(ctx, cmd, outs, create, model, kinds)
            continue

        # 2b') live polygon — emit the polygon and bind its named edge outputs
        # to the polygon's live .borders, so the whole shape (and anything built
        # on its edges) tracks drags.
        if base == "polygon":
            if _emit_polygon_live(ctx, cmd, outs, create, raw, raw_stmt, emitted, model):
                continue

        # 2b'') perpendicular bisector (composite: hidden midpoint + perpendicular).
        if base in ("perpendicular_bisector", "line_bisector"):
            if _emit_perp_bisector(ctx, cmd, outs, create, emitted, model):
                continue

        # 2b''') live transforms of a point (translate / rotate) via a JSXGraph
        # transformation object.
        if base in ("translate", "rotate"):
            if _emit_transform(ctx, cmd, base, outs, create, raw_stmt, emitted, kinds, model):
                continue

        # 2c) live native creator (single-output only; remaining multi-output
        # commands emit extra named outputs that other commands may reference,
        # so they go through the static path which emits them all).
        em = emitter_for(base) if len(outs) == 1 else None
        result = em(ctx, cmd) if em else None
        if isinstance(result, Emit) and all(_parents_ready(result.parents, emitted, ctx)):
            out_elem = scene.geo.element(primary)
            attrs = _style_for(ctx, out_elem)
            attrs.update(result.attrs)
            create(primary, result.jsx_type, result.parents, attrs)
            model.coverage.append((primary, "live", cmd.name))
            # Live congruence tick marks on a segment (JSXGraph has no native
            # tick element → emit live perpendicular dashes tied to the parents).
            if result.jsx_type == "segment":
                _emit_segment_ticks(ctx, primary, result.parents, out_elem,
                                    create, raw_stmt, model)
            continue

        # 2d) static fallback for each drawable output.
        for oname in outs:
            _emit_static(ctx, oname, cmd.name, dynamic, options, create, model)

    # P2-A: leader connectors for displaced labels — fixed segments (coordinate
    # parents stay eval-free in the spec), thin, label-coloured, non-interactive.
    for elem in scene.geo.elements:
        name = getattr(elem, "name", None)
        if not name or not ctx.is_visible(elem):
            continue
        leader = getattr(elem, "style", {}).get("_leader") if hasattr(elem, "style") else None
        if leader is None:
            continue
        (ax, ay), (attx, atty) = leader
        col = _hex(ctx.resolve(elem, "label_color", default="#000000"))
        create(
            f"__leader_{name}", "segment",
            [f"[{float(attx)}, {float(atty)}]", f"[{float(ax)}, {float(ay)}]"],
            {"strokeColor": col, "strokeWidth": 0.5, "fixed": True,
             "highlight": False, "withLabel": False, "name": ""},
        )

    _annotate_spec(ctx, model, dynamic)
    return model


def _annotate_spec(ctx, model, dynamic) -> None:
    """Backfill semantic ``role`` / ``kind`` / ``detail`` / ``tracksDrag`` onto
    the structured spec elements from the coverage report and the dynamic
    closure. ``create`` already filled ``engine`` / ``parents`` / ``attrs`` and
    the input emitters set the semantic ``kind`` for widgets."""
    cov: Dict[str, Tuple[str, str]] = {}
    for n, k, d in model.coverage:
        cov[n] = (k, d)
    input_names = {i.name for i in model.input_schema}
    for el in model.elements:
        if not el.name:
            continue
        if el.name in cov:
            k, d = cov[el.name]
            el.role = k
            if not el.detail:
                el.detail = d
        # Every interactive widget (point / slider / checkbox / glider) is an
        # input for state purposes, even a glider whose coverage reads "live".
        if el.name in input_names:
            el.role = "input"
        if not el.kind:
            elem = ctx.element(el.name)
            el.kind = ctx.data_typename(elem) or el.engine
        # tracksDrag: True for live creators (recompute in-engine). For a static
        # (frozen) element it is only meaningful as a warning: False when it has
        # a draggable ancestor (so it will visibly desync); otherwise omitted.
        if el.role == "live":
            el.tracks_drag = True
        elif el.role == "static":
            el.tracks_drag = False if el.name in dynamic else None


# ── independents → widgets ───────────────────────────────────────────────

def _emit_free_inputs(ctx, independents, bbox, create, model):
    left, top, right, bottom = bbox
    span_y = (top - bottom) or 1.0
    span_x = (right - left) or 1.0
    slider_i = 0
    for name, info in independents.items():
        t = info["type"]
        elem = ctx.element(name)
        if t == "free_point":
            x, y = info["coords"][0], info["coords"][1]
            attrs = point_attrs(ctx, elem)
            el = create(name, "point", [ctx.num(x), ctx.num(y)], attrs)
            el.kind = "point"
            model.input_schema.append(
                InputSpec(name=name, kind="point", x=float(x), y=float(y)))
            model.coverage.append((name, "input", "free point"))
        elif t == "free_text" and elem is not None and isinstance(elem.data, Text):
            text = elem.data
            decimals = getattr(ctx.scene.geo, "ggb_decimals", 2)
            content = resolve_text_string(ctx.scene.geo, text, decimals).replace("\xa0", " ")
            if not content.strip():
                model.coverage.append((name, "skip", "Text: empty"))
                continue
            x, y = info["position"][0], info["position"][1]
            attrs = {
                "anchorX": "left", "anchorY": "top",
                "fixed": False, "highlight": False,
                "strokeColor": _hex(ctx.resolve(elem, "label_color", default="#000000")),
            }
            off = ctx.resolve(elem, "label_offset_px", default=None)
            if off:
                attrs["offset"] = [float(off[0]), float(off[1])]
            fs_px = ctx.resolve(elem, "font_size_px", default=16.0)
            if fs_px:
                attrs["fontSize"] = float(fs_px)
            if text.is_latex:
                attrs["useMathJax"] = True
            el = create(name, "text", [ctx.num(x), ctx.num(y), json.dumps(content)], attrs)
            el.kind = "text"
            model.input_schema.append(
                InputSpec(name=name, kind="text", x=float(x), y=float(y)))
            model.coverage.append((name, "input", "free text"))
        elif t in ("number", "measure", "angle"):
            start = float(info["value"])
            lo, hi, step = info.get("min"), info.get("max"), info.get("step")
            if lo is None or hi is None:
                lo, hi = _slider_range(t, start)
            y = top - 0.5 * span_y * 0.08 - slider_i * span_y * 0.08
            x1 = left + 0.04 * span_x
            x2 = left + 0.30 * span_x
            slider_i += 1
            attrs = {"name": label_name(name, ctx.opt.mathjax)}
            if ctx.opt.mathjax:
                attrs["label"] = {"useMathJax": True}
            parents = [f"[{ctx.num(x1)},{ctx.num(y)}]",
                       f"[{ctx.num(x2)},{ctx.num(y)}]",
                       f"[{ctx.num(lo)},{ctx.num(start)},{ctx.num(hi)}]"]
            kind = "angle" if t == "angle" else "number"
            el = create(name, "slider", parents, attrs)
            el.kind = kind
            model.input_schema.append(InputSpec(
                name=name, kind=kind, value=start, min=float(lo), max=float(hi),
                step=(float(step) if step is not None else None)))
            model.coverage.append((name, "input", t))
        elif t == "boolean":
            y = top - 0.5 * span_y * 0.08 - slider_i * span_y * 0.08
            slider_i += 1
            el = create(name, "checkbox",
                   [f"[{ctx.num(left + 0.04 * span_x)},{ctx.num(y)}]", json.dumps(name)],
                   {})
            el.kind = "boolean"
            model.input_schema.append(
                InputSpec(name=name, kind="boolean", value=bool(info["value"])))
            model.coverage.append((name, "input", "boolean"))


def _slider_range(kind, start):
    if kind == "angle":
        return 0.0, 2 * math.pi
    pad = max(abs(start), 5.0)
    return start - pad, start + pad


# ── glider ─────────────────────────────────────────────────────────────────

def _emit_glider(ctx, cmd, name, info, create, model) -> bool:
    """Emit a draggable glider on its parent curve; return True on success."""
    curve = None
    for inp in cmd.inputs:
        el = ctx.input_elem(inp)
        if ctx.data_typename(el) in ("Circle", "Line", "Segment", "Ray", "Conic", "Arc"):
            curve = inp
            break
    if curve is None:
        return False
    coords = info.get("coords", [0, 0])
    elem = ctx.element(name)
    attrs = point_attrs(ctx, elem)
    el = create(name, "glider",
           [ctx.num(coords[0]), ctx.num(coords[1]), ctx.ref(curve)], attrs)
    el.kind = "glider"
    tparam = info.get("tparam")
    model.input_schema.append(InputSpec(
        name=name, kind="glider", x=float(coords[0]), y=float(coords[1]),
        on=ctx.name_of(curve), t=(float(tparam) if isinstance(tparam, (int, float)) else None)))
    model.coverage.append((name, "live", "glider"))
    return True


# ── intersection ─────────────────────────────────────────────────────────

# JSXGraph kinds whose pairwise 'intersection' is reliable (lines & conics).
_LIVE_INTERSECTABLE = {
    "line", "segment", "arc", "circle", "semicircle", "ellipse", "hyperbola",
    "parabola", "conic", "perpendicular", "parallel", "bisector", "reflection",
}


def _emit_intersections(ctx, cmd, outs, create, model, kinds):
    objs = [i for i in cmd.inputs if ctx.input_elem(i) is not None
            and ctx.data_typename(ctx.input_elem(i)) != "Point"]
    # Live JSXGraph 'intersection' only when both parents are intersectable
    # objects (lines/conics). Otherwise (e.g. sampled 'curve') the points are
    # emitted statically at AnimaGeo's computed coordinates — more accurate than
    # intersecting two polylines.
    both_live = (
        len(objs) >= 2
        and kinds.get(ctx.name_of(objs[0])) in _LIVE_INTERSECTABLE
        and kinds.get(ctx.name_of(objs[1])) in _LIVE_INTERSECTABLE
    )
    if not both_live:
        for oname in outs:
            _emit_static(ctx, oname, "intersect", set(), ctx.opt, create, model)
        return
    a, b = ctx.ref(objs[0]), ctx.ref(objs[1])
    for i, oname in enumerate(outs):
        out_elem = ctx.element(oname)
        if out_elem is None:
            model.coverage.append((oname, "skip", "intersect: missing output"))
            continue
        create(oname, "intersection", [a, b, str(i)], point_attrs(ctx, out_elem))
        model.coverage.append((oname, "live", "intersect"))


# ── polygon (live, with edge → border binding) ──────────────────────────────

def _rc(coords):
    return (round(float(coords[0]), 6), round(float(coords[1]), 6))


def _stroke_only(ctx, elem):
    a = base_attrs(ctx, elem)
    return {k: v for k, v in a.items()
            if k in ("strokeColor", "strokeWidth", "strokeOpacity", "dash")}


def _emit_polygon_live(ctx, cmd, outs, create, raw, raw_stmt, emitted, model) -> bool:
    """Emit ``board.create('polygon', [verts])`` and bind each named edge output
    to ``poly.borders[i]`` (matched by endpoint coordinates). Returns False (→
    static fallback) if the vertices aren't all available yet."""
    vnames = [ctx.name_of(i) for i in cmd.inputs
              if ctx.data_typename(ctx.input_elem(i)) == "Point"]
    poly_name = outs[0]
    poly_elem = ctx.element(poly_name)
    if len(vnames) < 3 or ctx.data_typename(poly_elem) != "Polygon":
        return False
    if not all(n in emitted for n in vnames):
        return False

    create(poly_name, "polygon", [ctx.ref(v) for v in vnames], base_attrs(ctx, poly_elem))
    model.coverage.append((poly_name, "live", "Polygon"))

    n = len(vnames)
    vcoords = [_rc(ctx.element(nm).data.coords) for nm in vnames]
    border_by_pair = {
        frozenset((vcoords[i], vcoords[(i + 1) % n])): i for i in range(n)
    }
    for oname in outs[1:]:
        oe = ctx.element(oname)
        if ctx.data_typename(oe) != "Segment":
            _emit_static(ctx, oname, "Polygon", set(), ctx.opt, create, model)
            continue
        p1, p2 = oe.data.endpoints
        bi = border_by_pair.get(frozenset((_rc(p1), _rc(p2))))
        if bi is None:
            _emit_static(ctx, oname, "Polygon", set(), ctx.opt, create, model)
            continue
        raw(oname, f"{ctx.ref(poly_name)}.borders[{bi}]", kind="line")
        st = _stroke_only(ctx, oe)
        if st:
            raw_stmt(f"{ctx.ref(oname)}.setAttribute({js_attrs(ctx, st)});")
        model.coverage.append((oname, "live", "Polygon edge"))
    return True


# ── live congruence tick marks (segments) ───────────────────────────────────

def _emit_segment_ticks(ctx, seg_name, parents, elem, create, raw_stmt, model):
    """Emit live perpendicular congruence ticks on a live segment.

    JSXGraph has no native tick decoration, so each tick is a short ``line``
    (``straightFirst/Last:false``) whose two endpoints are JS functions of the
    segment's parent points — so the ticks track drags exactly like the segment.
    Mirrors the renderer/TikZ geometry: ``num`` dashes at the midpoint, length
    ``tick_length_px``, centred, spaced by ``tick_shift_px`` along the segment.
    """
    num = int(ctx.resolve(elem, "tick_count", default=0) or 0)
    if num <= 0:
        return
    # Endpoints must be the two parent point refs (S["A"], S["B"]).
    refs = [p for p in parents if isinstance(p, str) and p.startswith("S[")]
    if len(refs) < 2:
        return
    a, b = refs[0], refs[1]

    # Tick size stays in *pixels* and is divided by the board's live px-per-unit
    # inside the coordinate functions, so the dash keeps a fixed pixel length at
    # any zoom (like GeoGebra) instead of scaling with the geometry.
    length_px = float(ctx.resolve(elem, "tick_length_px", default=0.0) or 0.0)
    shift_px = float(ctx.resolve(elem, "tick_shift_px", default=0.0) or 0.0)
    if length_px <= 0:
        return
    half_px = length_px / 2.0

    stroke = _hex(ctx.resolve(elem, "stroke", default="#000000"))
    tw = ctx.resolve(elem, "tick_width_px", default=None)
    seg_attrs = {"strokeColor": stroke, "highlight": False, "fixed": True,
                 "withLabel": False, "layer": 8}
    try:
        if tw is not None:
            seg_attrs["strokeWidth"] = float(tw)
    except (TypeError, ValueError):
        pass
    # Hidden anchor points carry the live geometry; they must not be drawn.
    pt_attrs = {"visible": False, "fixed": True, "withLabel": False,
                "name": "", "showInfobox": False}

    ax, ay, bx, by = f"{a}.X()", f"{a}.Y()", f"{b}.X()", f"{b}.Y()"
    # Live unit tangent (tx,ty) and unit normal (nx,ny) of the segment, plus the
    # board's live px-per-unit U (read off a parent point) so pixel sizes below
    # convert to the current math scale on every redraw — keeping ticks a fixed
    # pixel length under zoom.
    pre = (f"var dx={bx}-{ax},dy={by}-{ay},L=Math.hypot(dx,dy)||1;"
           f"var tx=dx/L,ty=dy/L,nx=-ty,ny=tx;"
           f"var mx=({ax}+{bx})/2,my=({ay}+{by})/2;"
           f"var U=(({a}.board&&{a}.board.unitX)||1);")

    def _fn(axis, d_px, sign):
        # One coordinate of a tick endpoint = midpoint + t*(d_px/U) ± n*(half_px/U),
        # a JSXGraph function-valued coordinate (recomputes on drag *and* zoom).
        t, n = (("tx", "nx") if axis == "x" else ("ty", "ny"))
        return Raw(f"function(){{{pre}return (m{axis}+{t}*(({_n(d_px)})/U))"
                   f"{sign}{n}*(({_n(half_px)})/U);}}")

    for i in range(num):
        # offset of this dash along the segment from the midpoint (centred), px.
        d_px = shift_px * ((1 - num) * 0.5 + i)
        base = f"__tick_{seg_name}_{i}"
        # Two hidden function-points (the guaranteed JSXGraph idiom), joined by a
        # short segment — the visible tick.
        create(f"{base}_p1", "point", [_fn("x", d_px, "+"), _fn("y", d_px, "+")], dict(pt_attrs))
        create(f"{base}_p2", "point", [_fn("x", d_px, "-"), _fn("y", d_px, "-")], dict(pt_attrs))
        create(base, "segment",
               [ctx.ref(f"{base}_p1"), ctx.ref(f"{base}_p2")], dict(seg_attrs))
        model.coverage.append((base, "live", "segment tick"))


def _n(v) -> str:
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ── perpendicular bisector (composite) ──────────────────────────────────────

def _emit_perp_bisector(ctx, cmd, outs, create, emitted, model) -> bool:
    """Mediator of A,B = perpendicular to line AB through its midpoint. Emits
    hidden aux (line + midpoint) then the perpendicular as the output."""
    out = outs[0]
    oe = ctx.element(out)
    attrs = base_attrs(ctx, oe)
    pts = [i for i in cmd.inputs if ctx.data_typename(ctx.input_elem(i)) == "Point"]
    segs = [i for i in cmd.inputs if ctx.data_typename(ctx.input_elem(i)) in ("Segment", "Line")]

    if len(pts) >= 2 and all(ctx.name_of(p) in emitted for p in pts[:2]):
        a, b = ctx.ref(pts[0]), ctx.ref(pts[1])
        linen, midn = f"__pb_line_{out}", f"__pb_mid_{out}"
        create(linen, "line", [a, b], {"visible": False})
        create(midn, "midpoint", [a, b], {"visible": False})
        create(out, "perpendicular", [ctx.ref(linen), ctx.ref(midn)], attrs)
        model.coverage.append((out, "live", "PerpendicularBisector"))
        return True
    if len(segs) == 1 and ctx.name_of(segs[0]) in emitted:
        s = ctx.ref(segs[0])
        midn = f"__pb_mid_{out}"
        create(midn, "midpoint", [s], {"visible": False})
        create(out, "perpendicular", [s, ctx.ref(midn)], attrs)
        model.coverage.append((out, "live", "PerpendicularBisector"))
        return True
    return False


# ── live transforms (translate / rotate) ────────────────────────────────────

# AnimaGeo type → JSXGraph creator used for a transformed copy. JSXGraph builds
# a live transformed element from ``create(kind, [original, transform])``.
_TRANSFORM_CREATOR = {
    "Point": "point", "Segment": "segment", "Line": "line", "Ray": "line",
    "Vector": "arrow", "Circle": "circle", "Polygon": "polygon",
}


def _emit_transform(ctx, cmd, base, outs, create, raw_stmt, emitted, kinds, model) -> bool:
    """Emit a JSXGraph 'transform' and the transformed element (point, segment,
    line, vector, circle or polygon). Returns False (→ static) if the source
    isn't available or the type isn't transformable."""
    out = outs[0]
    oe = ctx.element(out)
    creator = _TRANSFORM_CREATOR.get(ctx.data_typename(oe))
    if creator is None:
        return False
    src = next((i for i in cmd.inputs
                if ctx.data_typename(ctx.input_elem(i)) in _TRANSFORM_CREATOR), None)
    if src is None or ctx.name_of(src) not in emitted:
        return False
    tname = f"__tf_{out}"
    tref = f"S[{json.dumps(tname)}]"

    if base == "translate":
        vecs = [i for i in cmd.inputs
                if ctx.data_typename(ctx.input_elem(i)) == "Vector"
                and ctx.name_of(i) != ctx.name_of(src)]
        if not vecs:
            return False
        vec = vecs[0]
        vn = ctx.name_of(vec)
        if vn in emitted and kinds.get(vn) == "arrow":
            r = ctx.ref(vec)
            dx = f"function(){{return {r}.point2.X()-{r}.point1.X();}}"
            dy = f"function(){{return {r}.point2.Y()-{r}.point1.Y();}}"
        else:
            p1, p2 = ctx.input_elem(vec).data.endpoints
            dx, dy = ctx.num(p2[0] - p1[0]), ctx.num(p2[1] - p1[1])
        raw_stmt(f'{tref} = board.create("transform", [{dx}, {dy}], {{type: "translate"}});')
    else:  # rotate(object, angle, center)
        center = next((i for i in cmd.inputs
                       if ctx.data_typename(ctx.input_elem(i)) == "Point"
                       and ctx.name_of(i) != ctx.name_of(src)), None)
        if center is None or ctx.name_of(center) not in emitted:
            return False
        ang = None
        for i in cmd.inputs:
            if ctx.is_number(i):
                ang = ctx.num(float(i)); break
            el = ctx.input_elem(i)
            if el is not None and type(el.data).__name__ == "AngleSize":
                ang = value_expr(ctx, i) or ctx.num(float(el.data.value)); break
        if ang is None:
            return False
        raw_stmt(f'{tref} = board.create("transform", [{ang}, {ctx.ref(center)}], '
                 f'{{type: "rotate"}});')

    emitted.add(tname)
    create(out, creator, [ctx.ref(src), tref], _style_for(ctx, oe))
    model.coverage.append((out, "live", base))
    return True


# ── curve sampling (static fallback for analytic curves) ─────────────────────

def _conic_polylines(ctx, conic, viewport):
    from ...geo.lib_conic import ConicType
    from ...geo.curve_sampling import (
        sample_parametric, make_parabola_param, make_hyperbola_branch_param,
        viewport_t_ranges_parabola, viewport_t_range_hyperbola_branch,
    )
    left, bottom, right, top = viewport
    ptUnit = float(ctx.scene.style.export.get("ptUnit", 1) or 1)
    seg_mu = 3.0 / max(ptUnit, 1e-6)
    ct = conic.type
    polys = []
    if ct in (ConicType.EMPTY, ConicType.POINT):
        return polys
    if ct == ConicType.CIRCLE:
        res = conic.as_circle()
        if res:
            c, r = res
            polys.append([(c[0] + r * math.cos(2 * math.pi * k / 96),
                           c[1] + r * math.sin(2 * math.pi * k / 96)) for k in range(97)])
        return polys
    if ct == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        if p:
            a, b = p["semi_axes"]; cx, cy = p["center"]; rot = p["rotation"]
            cs, sn = math.cos(rot), math.sin(rot)
            pts = []
            for k in range(97):
                th = 2 * math.pi * k / 96
                x, y = a * math.cos(th), b * math.sin(th)
                pts.append((cx + x * cs - y * sn, cy + x * sn + y * cs))
            polys.append(pts)
        return polys
    if ct == ConicType.PARABOLA:
        p = conic.as_parabola()
        if p:
            pf = make_parabola_param(p["vertex"], p["axis"], p["perp"], p["focal_parameter"])
            for tr in viewport_t_ranges_parabola(p["vertex"], p["axis"], p["perp"],
                                                 p["focal_parameter"], viewport):
                for poly in sample_parametric(pf, tr, viewport, segment_mu=seg_mu):
                    polys.append([(q[0], q[1]) for q in poly])
        return polys
    if ct == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        if p:
            a, b = p["semi_axes"]; c = p["center"]; rot = p["rotation"]
            au = np.array([math.cos(rot), math.sin(rot)])
            av = np.array([-math.sin(rot), math.cos(rot)])
            for sign in (+1, -1):
                tr = viewport_t_range_hyperbola_branch(c, au, av, a, b, sign, viewport)
                if tr is None:
                    continue
                pf = make_hyperbola_branch_param(c, au, av, a, b, sign)
                for poly in sample_parametric(pf, tr, viewport, segment_mu=seg_mu):
                    polys.append([(q[0], q[1]) for q in poly])
        return polys
    if ct in (ConicType.INTERSECTING_LINES, ConicType.PARALLEL_LINES, ConicType.DOUBLE_LINE):
        for ln in (conic.as_lines() or []):
            ep = ln.get_endpoints([(left, bottom), (right, top)])
            if ep:
                polys.append([(ep[0][0], ep[0][1]), (ep[1][0], ep[1][1])])
    return polys


def _curve_polylines(ctx, elem):
    """Polylines approximating an analytic curve element, for static drawing."""
    t = ctx.data_typename(elem)
    d = elem.data
    left, top, right, bottom = ctx.boundingbox()
    viewport = (left, bottom, right, top)

    if t == "LocusCurve":
        pts = list(getattr(d, "points", []))
        return [[(p[0], p[1]) for p in pts]] if len(pts) >= 2 else []
    if t in ("Arc", "CircleSector"):
        cx, cy = float(d.center[0]), float(d.center[1])
        r = float(d.radius); a1, a2 = d.angles
        arc = [(cx + r * math.cos(a1 + (a2 - a1) * k / 64),
                cy + r * math.sin(a1 + (a2 - a1) * k / 64)) for k in range(65)]
        return [[(cx, cy)] + arc + [(cx, cy)]] if t == "CircleSector" else [arc]
    if t == "Function":
        from ...geo.curve_sampling import sample_parametric
        ptUnit = float(ctx.scene.style.export.get("ptUnit", 1) or 1)
        seg_mu = 3.0 / max(ptUnit, 1e-6)
        x_range = (left, right)
        if getattr(d, "explicit_domain", None) is not None:
            lo, hi = d.explicit_domain
            x_range = (max(left, lo), min(right, hi))
        if x_range[0] >= x_range[1]:
            return []
        sings = sorted(s for s in d.natural_singularities if x_range[0] < s < x_range[1])
        width = x_range[1] - x_range[0]; eps = max(width * 1e-3, 1e-6)
        edges = [x_range[0]] + sings + [x_range[1]]
        polys = []

        def fp(tt, ff=d):
            return (float(tt), float(ff(tt)))

        for k in range(len(edges) - 1):
            lo = edges[k] + (eps if k > 0 else 0.0)
            hi = edges[k + 1] - (eps if k < len(edges) - 2 else 0.0)
            if lo >= hi:
                continue
            for poly in sample_parametric(fp, (lo, hi), viewport, segment_mu=seg_mu):
                polys.append([(q[0], q[1]) for q in poly])
        return polys
    if t == "ImplicitCurve":
        from ...geo.curve_sampling import marching_squares
        polys = []
        for seg in marching_squares(d, viewport, grid_n=128):
            if seg.shape[0] >= 2:
                polys.append([(seg[0][0], seg[0][1]), (seg[1][0], seg[1][1])])
        return polys
    if t == "Conic":
        return _conic_polylines(ctx, d, viewport)
    return []


# ── static fallback ─────────────────────────────────────────────────────────

def _coord(ctx, p) -> str:
    return f"[{ctx.num(p[0])},{ctx.num(p[1])}]"


def _emit_text(ctx, elem, create, model):
    """Emit a GeoGebra free-text object as a JSXGraph ``text`` element,
    anchored top-left at its (offset) start point. LaTeX texts request MathJax.
    """
    text = elem.data
    decimals = getattr(ctx.scene.geo, "ggb_decimals", 2)
    content = resolve_text_string(ctx.scene.geo, text, decimals).replace("\xa0", " ")
    if not content.strip():
        model.coverage.append((elem.name, "skip", "Text: empty"))
        return

    base = resolve_text_position(ctx.scene.geo, text)
    x, y = float(base[0]), float(base[1])

    attrs = {
        "anchorX": "left", "anchorY": "top",
        "fixed": True, "highlight": False,
        "strokeColor": _hex(ctx.resolve(elem, "label_color", default="#000000")),
    }
    off = ctx.resolve(elem, "label_offset_px", default=None)
    if off:
        # JSXGraph text ``offset`` is in px; our label_offset_px already has
        # GGB's screen-y flipped, so +y is up (JSXGraph's convention).
        attrs["offset"] = [float(off[0]), float(off[1])]
    fs_px = ctx.resolve(elem, "font_size_px", default=16.0)
    if fs_px:
        attrs["fontSize"] = float(fs_px)
    if text.is_latex:
        attrs["useMathJax"] = True

    create(elem.name, "text", [x, y, json.dumps(content)], attrs)
    model.coverage.append((elem.name, "live", "Text"))


def _emit_static(ctx, name, cmd_name, dynamic, options, create, model):
    elem = ctx.element(name)
    if elem is None:
        model.coverage.append((name, "skip", f"{cmd_name}: no element"))
        return
    t = ctx.data_typename(elem)
    flag = " — depends on a draggable input → will NOT track drags" if name in dynamic else ""

    if options.fallback == "skip":
        model.coverage.append((name, "skip", f"{t} ({cmd_name}) unmapped"))
        return

    d = elem.data
    try:
        if t == "Point":
            a = point_attrs(ctx, elem)
            a["fixed"] = True
            create(name, "point", [ctx.num(d.coords[0]), ctx.num(d.coords[1])], a)
        elif t == "Segment":
            p1, p2 = d.endpoints
            create(name, "segment", [_coord(ctx, p1), _coord(ctx, p2)], base_attrs(ctx, elem))
        elif t in ("Line", "Ray"):
            left, top, right, bottom = ctx.boundingbox()
            ep = d.get_endpoints([(left, bottom), (right, top)])
            if ep is None:
                model.coverage.append((name, "skip", f"{t} off-viewport"))
                return
            extra = {"straightFirst": False} if t == "Ray" else {}
            a = base_attrs(ctx, elem)
            a.update(extra)
            create(name, "line", [_coord(ctx, ep[0]), _coord(ctx, ep[1])], a)
        elif t == "Vector":
            p1, p2 = d.endpoints
            create(name, "arrow", [_coord(ctx, p1), _coord(ctx, p2)], base_attrs(ctx, elem))
        elif t == "Circle":
            create(name, "circle",
                   [f"[{ctx.num(d.center[0])},{ctx.num(d.center[1])}]", ctx.num(d.radius)],
                   base_attrs(ctx, elem))
        elif t == "Polygon":
            verts = [_coord(ctx, v) for v in d.vertices]
            create(name, "polygon", verts, base_attrs(ctx, elem))
        elif t in ("Conic", "Function", "ImplicitCurve", "LocusCurve", "Arc", "CircleSector"):
            polys = _curve_polylines(ctx, elem)
            if not polys:
                model.coverage.append((name, "skip", f"{t} ({cmd_name}) — empty"))
                return
            xs, ys = [], []
            for i, poly in enumerate(polys):
                if i > 0:
                    xs.append("NaN"); ys.append("NaN")
                for (x, y) in poly:
                    xs.append(ctx.num(x)); ys.append(ctx.num(y))
            cattrs = base_attrs(ctx, elem)
            if t != "CircleSector":
                # Open sampled curves must not be filled (JSXGraph would close
                # them across the endpoints). Sectors stay filled.
                cattrs.pop("fillColor", None)
                cattrs.pop("fillOpacity", None)
            create(name, "curve", [f"[{','.join(xs)}]", f"[{','.join(ys)}]"], cattrs)
        else:
            model.coverage.append((name, "skip", f"{t} ({cmd_name}) — not drawn"))
            return
    except Exception:
        logger.warning("JSXGraph static fallback failed for %r", name, exc_info=True)
        model.coverage.append((name, "skip", f"{t} ({cmd_name}) — error"))
        return

    model.coverage.append((name, "static", f"{t} ({cmd_name}){flag}"))


# ── helpers ─────────────────────────────────────────────────────────────────

def _parents_ready(parents, emitted, ctx):
    """Yield True for each parent that is a literal or an already-emitted ref."""
    for p in parents:
        if not isinstance(p, str):
            yield True   # Raw expression (e.g. a live function) — leaf refs in
            continue     # it are points/sliders already emitted in topo order.
        if not p.startswith("S["):
            yield True
        else:
            try:
                name = json.loads(p[2:-1])
            except Exception:
                yield True
                continue
            yield name in emitted


def _style_for(ctx, elem):
    t = ctx.data_typename(elem)
    return point_attrs(ctx, elem) if t == "Point" else base_attrs(ctx, elem)
