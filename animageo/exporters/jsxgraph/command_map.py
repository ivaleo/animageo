"""Command → JSXGraph element mapping (the transpiler core).

Each emitter turns one AnimaGeo ``Command`` into a JSXGraph ``board.create``
call referencing its parents' JS objects, so JSXGraph's engine recomputes the
element when an ancestor (a draggable point / slider / glider) moves.

Phase 1 = the school/competition core (Tier A, single-output, native
constructors). Multi-output ``intersect``, gliders and free inputs are handled
in the builder; everything unmapped falls back to static geometry there.

An emitter returns:
- ``Emit`` — a single ``board.create`` for the command's (single) output;
- ``None`` — not mappable in this phase → static fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...geo.lib_commands import strCommand
from .context import JsxContext, Raw
from .style_map import arrow_attrs


# ── Tier-V: live numeric value expressions ───────────────────────────────────

def _bin(parts, op):
    if not parts or any(p is None for p in parts):
        return None
    return "(" + f" {op} ".join(parts) + ")"


def value_expr(ctx, inp, depth: int = 0):
    """A JS numeric expression for a command input that is a number/measure,
    inlined down to emitted leaves (points → ``.X()``/``.Dist()``, sliders →
    ``.Value()``) and literals. Returns None if it can't be expressed."""
    if depth > 12:
        return None
    if ctx.is_number(inp):
        return ctx.num(float(inp))
    name = ctx.name_of(inp)
    if ctx.is_independent_value(name):
        return f"{ctx.ref(name)}.Value()"
    cmd = ctx.geo.commandByElementName(name)
    if cmd is None:
        return None
    base = strCommand(cmd.name)
    ins = cmd.inputs

    def E(i):
        return value_expr(ctx, i, depth + 1)

    if base in ("value", "assign"):
        return E(ins[0]) if ins else None
    if base == "add":
        return _bin([E(i) for i in ins], "+")
    if base == "sub":
        return _bin([E(i) for i in ins], "-")
    if base == "mult":
        return _bin([E(i) for i in ins], "*")
    if base == "div":
        return _bin([E(i) for i in ins], "/")
    if base == "pow":
        a, b = E(ins[0]), E(ins[1])
        return f"Math.pow({a}, {b})" if a and b else None
    if base == "abs":
        a = E(ins[0])
        return f"Math.abs({a})" if a else None
    if base == "sqrt":
        a = E(ins[0])
        return f"Math.sqrt({a})" if a else None
    if base in ("sin", "cos", "tan"):
        a = E(ins[0])
        return f"Math.{base}({a})" if a else None
    if base == "distance":
        if len(ins) >= 2 and all(ctx.data_typename(ctx.input_elem(i)) == "Point" for i in ins[:2]):
            return f"{ctx.ref(ins[0])}.Dist({ctx.ref(ins[1])})"
        return None
    if base == "radius":
        if ins and ctx.data_typename(ctx.input_elem(ins[0])) == "Circle":
            return f"{ctx.ref(ins[0])}.Radius()"
        return None
    if base == "length":
        if ins and ctx.data_typename(ctx.input_elem(ins[0])) in ("Segment", "Vector"):
            return f"{ctx.ref(ins[0])}.L()"
        return None
    return None


@dataclass
class Emit:
    jsx_type: str
    parents: List[str]              # JS reference / literal strings
    attrs: Dict[str, object] = field(default_factory=dict)


def _two_points(ctx: JsxContext, cmd):
    ins = cmd.inputs
    if len(ins) < 2:
        return None
    return [ctx.ref(ins[0]), ctx.ref(ins[1])]


def _midpoint(ctx, cmd) -> Optional[Emit]:
    """Midpoint of two points, or of a single segment/line (JSXGraph accepts
    both parent forms)."""
    ins = cmd.inputs
    if len(ins) >= 2 and all(ctx.data_typename(ctx.input_elem(i)) == "Point" for i in ins[:2]):
        return Emit("midpoint", [ctx.ref(ins[0]), ctx.ref(ins[1])])
    if len(ins) == 1 and ctx.data_typename(ctx.input_elem(ins[0])) in ("Segment", "Line"):
        return Emit("midpoint", [ctx.ref(ins[0])])
    return None


def emit_midpoint(ctx, cmd) -> Optional[Emit]:
    return _midpoint(ctx, cmd)


def emit_center(ctx, cmd) -> Optional[Emit]:
    # Center of points/segment == midpoint; centre of a conic has no direct
    # creator → static fallback.
    return _midpoint(ctx, cmd)


def emit_segment(ctx, cmd) -> Optional[Emit]:
    p = _two_points(ctx, cmd)
    return Emit("segment", p) if p else None


def emit_line(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) < 2:
        return None
    types = [ctx.data_typename(ctx.input_elem(i)) for i in ins]
    # Line(point, line) / Line(line, point) → parallel line through the point.
    if "Line" in types and "Point" in types:
        line = ins[types.index("Line")]
        point = ins[types.index("Point")]
        return Emit("parallel", [ctx.ref(line), ctx.ref(point)])
    if types[0] == "Point" and types[1] == "Point":
        return Emit("line", [ctx.ref(ins[0]), ctx.ref(ins[1])])
    return None


def emit_ray(ctx, cmd) -> Optional[Emit]:
    p = _two_points(ctx, cmd)
    if not p:
        return None
    # Ray from the first point through the second: don't extend before start.
    return Emit("line", p, {"straightFirst": False})


def emit_vector(ctx, cmd) -> Optional[Emit]:
    p = _two_points(ctx, cmd)
    if not p:
        return None
    # Arrowhead sized from the resolved GGB arrow_length_px (live; native head).
    oe = ctx.element(ctx.name_of(cmd.outputs[0])) if cmd.outputs else None
    attrs = arrow_attrs(ctx, oe) if oe is not None else {}
    return Emit("arrow", p, attrs)


def emit_polygon(ctx, cmd) -> Optional[Emit]:
    verts = [ctx.ref(i) for i in cmd.inputs
             if ctx.data_typename(ctx.input_elem(i)) == "Point"]
    return Emit("polygon", verts) if len(verts) >= 3 else None


def emit_circle(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) != 2:
        return None
    center, second = ins[0], ins[1]
    if ctx.data_typename(ctx.input_elem(center)) != "Point":
        return None
    # center + through-point
    if ctx.data_typename(ctx.input_elem(second)) == "Point":
        return Emit("circle", [ctx.ref(center), ctx.ref(second)])
    # center + numeric literal radius
    if ctx.is_number(second):
        return Emit("circle", [ctx.ref(center), ctx.num(float(second))])
    # center + numeric radius (slider / derived value) → live function radius
    expr = value_expr(ctx, second)
    if expr is not None:
        return Emit("circle", [ctx.ref(center), Raw(f"function(){{return {expr};}}")])
    # center + (unexpressible) radius → freeze at current value
    out = ctx.element(cmd.outputs[0]) if cmd.outputs else None
    if out is not None and hasattr(out.data, "radius"):
        return Emit("circle", [ctx.ref(center), ctx.num(float(out.data.radius))])
    return None


def emit_perpendicular(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    types = [ctx.data_typename(ctx.input_elem(i)) for i in ins]
    line_types = {"Line", "Segment", "Ray"}
    if "Point" in types and any(t in line_types for t in types):
        point = ins[types.index("Point")]
        line = ins[next(k for k, t in enumerate(types) if t in line_types)]
        return Emit("perpendicular", [ctx.ref(line), ctx.ref(point)])
    return None


def emit_angular_bisector(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) == 3 and all(ctx.data_typename(ctx.input_elem(i)) == "Point" for i in ins):
        return Emit("bisector", [ctx.ref(ins[0]), ctx.ref(ins[1]), ctx.ref(ins[2])])
    return None


def _angle_radius_px(ctx, oe, angle_range) -> float:
    """Effective angle-arc radius in pixels, mirroring ``_render_angle``:
    the resolved ``arc_size_px`` run through ``compute_effective_arc_size_px``
    (a no-op unless ``overlay.angle_radius`` is enabled) plus the multi-arc
    expansion ``(tick_count - 1) * arc_shift_px``. Falls back to the raw
    resolved size on any error so it can never make the angle worse."""
    base = float(ctx.resolve(oe, "arc_size_px", default=17.0))
    try:
        from ...label_placement import compute_effective_arc_size_px
        auto_radius = ctx.resolve(oe, "auto_radius", default=True)
        # Pass the scene (not scene.style): the overlay.angle_radius config is
        # read off `.style_config`, which lives on the scene.
        r = compute_effective_arc_size_px(
            oe, oe.data, ctx.scene, base_px=base,
            angle_range=angle_range, auto_radius=auto_radius,
        )
        tick_count = int(ctx.resolve(oe, "tick_count", default=1) or 1)
        if tick_count > 1:
            shift = float(ctx.scene.style_config.defaults.get(
                "angle", "arc_shift_px", 0.0))
            r += (tick_count - 1) * shift
        return round(float(r), 4)
    except Exception:
        return round(base, 4)


def emit_angle(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) == 3 and all(ctx.data_typename(ctx.input_elem(i)) == "Point" for i in ins):
        # JSXGraph's plain `angle` always sweeps counterclockwise from the first
        # to the third point, so it cannot honour GeoGebra's "which side of the
        # plane" setting on its own. Mirror the SVG renderer, which keys off the
        # resolved `angle_range` ('minor' = non-reflex ≤180°, 'reflex' = >180°),
        # by emitting the dedicated reflex/non-reflex element types — these pick
        # the correct sector regardless of point order.
        oe = ctx.element(ctx.name_of(cmd.outputs[0])) if cmd.outputs else None
        angle_range = (ctx.resolve(oe, "angle_range", default="minor") or "minor")
        jsx_type = "reflexangle" if angle_range == "reflex" else "nonreflexangle"
        # Carry the arc radius (GeoGebra `arcSize`, in pixels) over to JSXGraph,
        # whose angle `radius` is in user units → divide by ptUnit. JSXGraph
        # already draws a right angle as a square automatically (type 'auto').
        attrs: dict = {}
        export = getattr(ctx.scene.style, "export", {}) or {}
        ptUnit = float(export.get("ptUnit", 1) or 1)
        attrs["radius"] = _angle_radius_px(ctx, oe, angle_range) / ptUnit
        return Emit(jsx_type, [ctx.ref(ins[0]), ctx.ref(ins[1]), ctx.ref(ins[2])], attrs)
    return None


def emit_semicircle(ctx, cmd) -> Optional[Emit]:
    p = _two_points(ctx, cmd)
    return Emit("semicircle", p) if p else None


def _conic_third(ctx, inp):
    """Third parent of an ellipse/hyperbola: a number, a slider/derived value,
    or a point on the conic. None if it can't be expressed cleanly (→ static)."""
    if ctx.is_number(inp):
        return ctx.num(float(inp))
    if ctx.data_typename(ctx.input_elem(inp)) == "Point":
        return ctx.ref(inp)
    expr = value_expr(ctx, inp)
    if expr is not None:
        return Raw(f"function(){{return {expr};}}")
    return None


def _emit_focal_conic(ctx, cmd, jsx_type) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) != 3:
        return None
    if any(ctx.data_typename(ctx.input_elem(ins[k])) != "Point" for k in (0, 1)):
        return None
    third = _conic_third(ctx, ins[2])
    if third is None:
        return None
    return Emit(jsx_type, [ctx.ref(ins[0]), ctx.ref(ins[1]), third])


def emit_ellipse(ctx, cmd) -> Optional[Emit]:
    return _emit_focal_conic(ctx, cmd, "ellipse")


def emit_hyperbola(ctx, cmd) -> Optional[Emit]:
    return _emit_focal_conic(ctx, cmd, "hyperbola")


def emit_parabola(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) != 2:
        return None
    if ctx.data_typename(ctx.input_elem(ins[0])) != "Point":
        return None
    if ctx.data_typename(ctx.input_elem(ins[1])) not in ("Line", "Segment", "Ray"):
        return None
    return Emit("parabola", [ctx.ref(ins[0]), ctx.ref(ins[1])])


def emit_conic(ctx, cmd) -> Optional[Emit]:
    pts = [i for i in cmd.inputs if ctx.data_typename(ctx.input_elem(i)) == "Point"]
    if len(pts) == 5:
        return Emit("conic", [ctx.ref(p) for p in pts])
    return None


_REFLECTABLE = ("Point", "Segment", "Line", "Ray", "Circle", "Polygon", "Vector")


def emit_reflect(ctx, cmd) -> Optional[Emit]:
    ins = cmd.inputs
    if len(ins) != 2:
        return None
    obj, across = ins
    if ctx.data_typename(ctx.input_elem(obj)) not in _REFLECTABLE:
        return None
    at = ctx.data_typename(ctx.input_elem(across))
    if at == "Point":
        return Emit("mirrorelement", [ctx.ref(obj), ctx.ref(across)])
    if at in ("Line", "Segment", "Ray"):
        return Emit("reflection", [ctx.ref(obj), ctx.ref(across)])
    return None


COMMAND_EMITTERS = {
    "midpoint": emit_midpoint,
    "center": emit_center,
    "segment": emit_segment,
    "line": emit_line,
    "ray": emit_ray,
    "vector": emit_vector,
    "polygon": emit_polygon,
    "circle": emit_circle,
    "semicircle": emit_semicircle,
    "perpendicular_line": emit_perpendicular,
    "orthogonal_line": emit_perpendicular,
    "angular_bisector": emit_angular_bisector,
    "angle": emit_angle,
    "ellipse": emit_ellipse,
    "hyperbola": emit_hyperbola,
    "parabola": emit_parabola,
    "conic": emit_conic,
    "reflect": emit_reflect,
    "mirror": emit_reflect,
}


def emitter_for(command_name: str):
    return COMMAND_EMITTERS.get(command_name)
