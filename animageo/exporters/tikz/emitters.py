"""Per-element TikZ emitters.

Each emitter mirrors the corresponding ``AnimaGeoScene._render_<type>`` method
but writes native TikZ instead of building manim mobjects. Geometry lines are
appended to ``ctx.doc``; label nodes are collected into ``labels`` and emitted
after all geometry so they stack on top (matching ``Z_LABEL``).

Coordinates are math units (MU); the picture's ``x=/y=`` unit scales them.
Geometric radii/axes are emitted unitless (MU); fixed-size markers, widths and
fonts use absolute ``pt`` via :class:`TikzContext`.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np

from ...geo.curve_sampling import (
    make_hyperbola_branch_param,
    make_parabola_param,
    marching_squares,
    sample_parametric,
    viewport_t_range_hyperbola_branch,
    viewport_t_ranges_parabola,
)
from ...geo.lib_conic import ConicType
from ...geo.lib_elements import resolve_text_position, text_to_display_latex
from ...label_placement import compute_effective_arc_size_px
from .context import TikzContext
from .document import fmt_num
from .style_map import (
    anchor_for,
    fill_options,
    stroke_default,
    stroke_options,
)


# ── shared helpers ──────────────────────────────────────────────────────

def _coord(ctx: TikzContext, x, y) -> str:
    return ctx.doc.coord(float(x), float(y))


def _fill_opacity(ctx: TikzContext, elem) -> float:
    try:
        return float(ctx.resolve(elem, "fill_opacity", default=0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _stroke_opacity(ctx: TikzContext, elem, default=1.0) -> float:
    try:
        return float(ctx.resolve(elem, "stroke_opacity", default=default))
    except (TypeError, ValueError):
        return default


def _polyline(ctx: TikzContext, opts: str, points) -> None:
    """Emit a ``\\draw[opts] plot coordinates {...};`` from MU points."""
    if len(points) < 2:
        return
    coords = "".join(_coord(ctx, p[0], p[1]) for p in points)
    ctx.doc.line(f"\\draw[{opts}] plot coordinates {{{coords}}};")


def emit_label(ctx: TikzContext, elem, x, y, labels: List[str],
               *, default_anchor: str | None = None,
               extra_shift_pt=(0.0, 0.0)) -> None:
    """Append a ``\\node`` label for ``elem`` at MU position (x, y)."""
    if ctx.resolve(elem, "label_visible", default=False) is not True:
        return
    text = ctx.label_text(elem)
    if not text:
        return

    opts: List[str] = []
    anchor = anchor_for(ctx, elem)
    if default_anchor is not None and ctx.resolve(elem, "label_anchor", default=None) is None:
        anchor = default_anchor
    opts.append(f"anchor={anchor}")

    col = ctx.resolve(elem, "label_color", default=stroke_default(ctx))
    opts.append(f"text={ctx.doc.color(col)}")

    xshift = float(extra_shift_pt[0])
    yshift = float(extra_shift_pt[1])
    off = ctx.resolve(elem, "label_offset_px", default=None)
    if off is not None:
        xshift += ctx.offset_pt(off[0])
        yshift += ctx.offset_pt(off[1])

    auto_placed = bool(elem.style.get("_auto_placed"))
    if ctx.ggb_font_px and not auto_placed:
        # GGB descender correction (see ui.create_label): push up by 0.25 em.
        yshift += ctx.size_pt(float(ctx.ggb_font_px) * 0.25)

    p = ctx.opt.size_precision
    if abs(xshift) > 1e-6:
        opts.append(f"xshift={fmt_num(xshift, p)}pt")
    if abs(yshift) > 1e-6:
        opts.append(f"yshift={fmt_num(yshift, p)}pt")

    if ctx.opt.emit_font_size:
        fs_px = ctx.resolve(elem, "font_size_px", default=14.0)
        fpt = ctx.size_pt(fs_px)
        if fpt > 0:
            opts.append(
                f"font=\\fontsize{{{fmt_num(fpt, p)}}}{{{fmt_num(fpt * 1.2, p)}}}\\selectfont"
            )

    # P2-A: a displaced label carries a leader connector (attach → anchor, MU).
    # Emit it BEFORE the node so the thin line sits under the text.
    leader = elem.style.get("_leader") if hasattr(elem, "style") else None
    if leader is not None:
        try:
            (ax, ay), (attx, atty) = leader
            labels.append(
                f"\\draw[{ctx.doc.color(col)}, line width=0.4pt] "
                f"{_coord(ctx, attx, atty)} -- {_coord(ctx, ax, ay)};"
            )
        except Exception:
            pass

    labels.append(f"\\node[{', '.join(opts)}] at {_coord(ctx, x, y)} {{{text}}};")


def _combined_fill_stroke(ctx: TikzContext, elem, *, fill_default=None) -> str:
    """Options for a path that is both filled (if opacity>0) and stroked."""
    opts = stroke_options(ctx, elem)
    if _fill_opacity(ctx, elem) > 0:
        opts += ", " + fill_options(ctx, elem, color_default=fill_default)
    return opts


# ── points ──────────────────────────────────────────────────────────────

def emit_point(ctx: TikzContext, elem, labels: List[str]) -> None:
    rendering = ctx.scene.style.rendering
    display = rendering.get("points_display")
    x, y = float(elem.data.coords[0]), float(elem.data.coords[1])

    size_px = ctx.resolve(elem, "size_px", default=ctx.scene.style.dot_size)
    R = ctx.size_pt(float(size_px) / 2)
    shape = ctx.resolve(elem, "point_shape", default="circle")
    scol = ctx.resolve(elem, "stroke", default=stroke_default(ctx))

    if display != "only_labels" and R > 0:
        stroke = stroke_options(ctx, elem, with_cap=False, with_dash=False)
        fill = f"fill={ctx.doc.color(ctx.resolve(elem, 'fill', default=scol))}"
        fop = _fill_opacity(ctx, elem)
        if fop <= 0:
            fop = 1.0  # a point marker is filled by default
        if fop < 1.0:
            fill += f", fill opacity={fmt_num(fop, 3)}"
        opts = f"{stroke}, {fill}"
        _emit_marker(ctx, x, y, R, shape, opts, stroke)

    if display != "only_points":
        emit_label(ctx, elem, x, y, labels)


def _shift(dx_pt, dy_pt, x, y, ctx) -> str:
    return f"([shift={{({fmt_num(dx_pt, 3)}pt,{fmt_num(dy_pt, 3)}pt)}}]{ctx.doc.num(x)},{ctx.doc.num(y)})"


def _emit_marker(ctx, x, y, R, shape, opts, stroke_only):
    if shape == "square":
        h = R / math.sqrt(2)
        ctx.doc.line(
            f"\\draw[{opts}] {_shift(-h, -h, x, y, ctx)} rectangle {_shift(h, h, x, y, ctx)};"
        )
        return
    if shape in ("triangle_up", "triangle_down", "triangle_left", "triangle_right"):
        base = {"triangle_up": 90, "triangle_down": -90,
                "triangle_left": 180, "triangle_right": 0}[shape]
        pts = []
        for k in range(3):
            ang = math.radians(base + 120 * k)
            pts.append(_shift(R * math.cos(ang), R * math.sin(ang), x, y, ctx))
        ctx.doc.line(f"\\draw[{opts}] {' -- '.join(pts)} -- cycle;")
        return
    if shape == "cross":
        ctx.doc.line(f"\\draw[{stroke_only}] {_shift(-R, R, x, y, ctx)} -- {_shift(R, -R, x, y, ctx)};")
        ctx.doc.line(f"\\draw[{stroke_only}] {_shift(-R, -R, x, y, ctx)} -- {_shift(R, R, x, y, ctx)};")
        return
    if shape == "plus":
        ctx.doc.line(f"\\draw[{stroke_only}] {_shift(-R, 0, x, y, ctx)} -- {_shift(R, 0, x, y, ctx)};")
        ctx.doc.line(f"\\draw[{stroke_only}] {_shift(0, -R, x, y, ctx)} -- {_shift(0, R, x, y, ctx)};")
        return
    # default: circle (radius in absolute pt → fixed marker)
    ctx.doc.line(f"\\draw[{opts}] ({ctx.doc.num(x)},{ctx.doc.num(y)}) circle ({fmt_num(R, 3)}pt);")


# ── tick decorations (segments / vectors) ────────────────────────────────

def _emit_ticks(ctx: TikzContext, elem, p1, p2, normal, labels=None) -> None:
    num = int(ctx.resolve(elem, "tick_count", default=0) or 0)
    if num <= 0:
        return
    delta = np.asarray(p2, float) - np.asarray(p1, float)
    dn = float(np.linalg.norm(delta))
    nn = float(np.linalg.norm(normal))
    if dn < 1e-9 or nn < 1e-9:
        return
    v = delta / dn
    n = np.asarray(normal, float) / nn

    ps = ctx.ptUnit_style
    length_mu = float(ctx.resolve(elem, "tick_length_px", default=0.0) or 0.0) / ps
    shift_mu = float(ctx.resolve(elem, "tick_shift_px", default=0.0) or 0.0) / ps
    width_px = ctx.resolve(elem, "tick_width_px", default=0.0) or 0.0
    if length_mu <= 0:
        return
    m = (np.asarray(p1, float) + np.asarray(p2, float)) / 2
    opts = stroke_options(ctx, elem, width_px=width_px, with_dash=False)
    half = n * length_mu / 2
    for i in range(num):
        d = shift_mu * ((1 - num) * 0.5 + i)
        c = m + v * d
        a = c + half
        b = c - half
        ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, a[0], a[1])} -- {_coord(ctx, b[0], b[1])};")


# ── 1D primitives ─────────────────────────────────────────────────────────

def emit_segment(ctx: TikzContext, elem, labels: List[str]) -> None:
    p1, p2 = elem.data.endpoints
    opts = stroke_options(ctx, elem)
    ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, p1[0], p1[1])} -- {_coord(ctx, p2[0], p2[1])};")
    _emit_ticks(ctx, elem, p1, p2, elem.data.normal)
    m = (np.asarray(p1, float) + np.asarray(p2, float)) / 2
    emit_label(ctx, elem, m[0], m[1], labels)


def emit_line(ctx: TikzContext, elem, labels: List[str]) -> None:
    left, bottom, right, top = ctx.viewport()
    endpoints = elem.data.get_endpoints([(left, bottom), (right, top)])
    if endpoints is None:
        return
    p1, p2 = endpoints
    opts = stroke_options(ctx, elem)
    ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, p1[0], p1[1])} -- {_coord(ctx, p2[0], p2[1])};")
    m = (np.asarray(p1, float) + np.asarray(p2, float)) / 2
    emit_label(ctx, elem, m[0], m[1], labels)


# Ray shares Line's viewport clipping.
emit_ray = emit_line


def emit_vector(ctx: TikzContext, elem, labels: List[str]) -> None:
    p1, p2 = elem.data.endpoints
    # Plain ``->`` needs no library, so snippets stay self-contained. Users who
    # load ``arrows.meta`` can restyle via the picture's default arrow option.
    opts = stroke_options(ctx, elem, extra=["->"])
    ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, p1[0], p1[1])} -- {_coord(ctx, p2[0], p2[1])};")
    normal = np.array([p1[1] - p2[1], p2[0] - p1[0]])
    _emit_ticks(ctx, elem, p1, p2, normal)
    m = (np.asarray(p1, float) + np.asarray(p2, float)) / 2
    emit_label(ctx, elem, m[0], m[1], labels)


# ── round primitives ─────────────────────────────────────────────────────

def emit_circle(ctx: TikzContext, elem, labels: List[str]) -> None:
    cx, cy = float(elem.data.center[0]), float(elem.data.center[1])
    r = float(elem.data.radius)
    opts = _combined_fill_stroke(ctx, elem, fill_default=ctx.scene.style.background)
    ctx.doc.line(f"\\draw[{opts}] ({ctx.doc.num(cx)},{ctx.doc.num(cy)}) circle ({ctx.doc.num(r)});")


def _arc_start(cx, cy, r, a_rad):
    return cx + r * math.cos(a_rad), cy + r * math.sin(a_rad)


def emit_arc(ctx: TikzContext, elem, labels: List[str]) -> None:
    cx, cy = float(elem.data.center[0]), float(elem.data.center[1])
    r = float(elem.data.radius)
    a1, a2 = elem.data.angles
    a1d, a2d = math.degrees(a1), math.degrees(a2)
    sx, sy = _arc_start(cx, cy, r, a1)
    if _fill_opacity(ctx, elem) > 0:
        fopts = fill_options(ctx, elem)
        ctx.doc.line(
            f"\\fill[{fopts}] {_coord(ctx, sx, sy)} arc ({ctx.doc.num(a1d)}:{ctx.doc.num(a2d)}:{ctx.doc.num(r)}) -- cycle;"
        )
    opts = stroke_options(ctx, elem)
    ctx.doc.line(
        f"\\draw[{opts}] {_coord(ctx, sx, sy)} arc ({ctx.doc.num(a1d)}:{ctx.doc.num(a2d)}:{ctx.doc.num(r)});"
    )
    mid = (a1 + a2) / 2
    lx, ly = _arc_start(cx, cy, r + 0.7, mid)
    emit_label(ctx, elem, lx, ly, labels, default_anchor="center")


def emit_circlesector(ctx: TikzContext, elem, labels: List[str]) -> None:
    cx, cy = float(elem.data.center[0]), float(elem.data.center[1])
    r = float(elem.data.radius)
    a1, a2 = elem.data.angles
    a1d, a2d = math.degrees(a1), math.degrees(a2)
    sx, sy = _arc_start(cx, cy, r, a1)
    if _fill_opacity(ctx, elem) > 0:
        fopts = fill_options(ctx, elem)
        ctx.doc.line(
            f"\\fill[{fopts}] ({ctx.doc.num(cx)},{ctx.doc.num(cy)}) -- {_coord(ctx, sx, sy)} "
            f"arc ({ctx.doc.num(a1d)}:{ctx.doc.num(a2d)}:{ctx.doc.num(r)}) -- cycle;"
        )
    opts = stroke_options(ctx, elem)
    ctx.doc.line(
        f"\\draw[{opts}] {_coord(ctx, sx, sy)} arc ({ctx.doc.num(a1d)}:{ctx.doc.num(a2d)}:{ctx.doc.num(r)});"
    )
    mid = (a1 + a2) / 2
    lx = cx + r * 0.7 * math.cos(mid)
    ly = cy + r * 0.7 * math.sin(mid)
    emit_label(ctx, elem, lx, ly, labels, default_anchor="center")


# ── polygon ───────────────────────────────────────────────────────────────

def emit_polygon(ctx: TikzContext, elem, labels: List[str]) -> None:
    verts = elem.data.vertices
    chain = " -- ".join(_coord(ctx, v[0], v[1]) for v in verts)
    if _fill_opacity(ctx, elem) > 0:
        ctx.doc.line(f"\\fill[{fill_options(ctx, elem)}] {chain} -- cycle;")
    if _stroke_opacity(ctx, elem, default=0.0) > 0:
        ctx.doc.line(f"\\draw[{stroke_options(ctx, elem)}] {chain} -- cycle;")
    if ctx.resolve(elem, "label_visible", default=False) is True:
        c = np.mean(verts, axis=0)
        emit_label(ctx, elem, c[0], c[1], labels, default_anchor="center")


# ── angle ─────────────────────────────────────────────────────────────────

def emit_angle(ctx: TikzContext, elem, labels: List[str]) -> None:
    data = elem.data
    ps = ctx.ptUnit_style
    angle = float(data.size)
    angle_range = ctx.resolve(elem, "angle_range", default="minor") or "minor"
    is_clockwise = False
    if angle_range == "minor" and angle > math.pi:
        is_clockwise = True
        angle = 2 * math.pi - angle
    elif angle_range == "reflex" and angle < math.pi:
        is_clockwise = True
        angle = 2 * math.pi - angle

    arc_size_resolved = ctx.resolve(elem, "arc_size_px", default=17.0)
    auto_radius = ctx.resolve(elem, "auto_radius", default=True)
    r = compute_effective_arc_size_px(
        elem, data, ctx.scene, base_px=arc_size_resolved,
        angle_range=angle_range, auto_radius=auto_radius,
    ) / ps
    arc_shift_mu = float(ctx.resolve(elem, "arc_shift_px", default=0.0) or 0.0) / ps
    tick_count = int(ctx.resolve(elem, "tick_count", default=1) or 1)
    r += (tick_count - 1) * arc_shift_mu
    if r < 0.001:
        r = 0.2

    px, py = float(data.vertex[0]), float(data.vertex[1])
    if is_clockwise:
        a0 = math.atan2(data.side2[1], data.side2[0])
    else:
        a0 = float(data.start_angle)
    a1 = a0 + angle
    a0d, a1d = math.degrees(a0), math.degrees(a1)

    right_marker = ctx.resolve(elem, "right_angle_marker", default=None)
    if right_marker is None:
        right_marker = bool(np.isclose(angle, math.pi / 2))

    has_fill = _fill_opacity(ctx, elem) > 0

    if right_marker:
        right_size_px = ctx.resolve(elem, "right_angle_size_px", default=arc_size_resolved)
        rr = float(right_size_px) / math.sqrt(2) / ps
        s1 = np.asarray(data.side1, float)
        s2 = np.asarray(data.side2, float)
        n1 = s1 * (rr / np.linalg.norm(s1))
        n2 = s2 * (rr / np.linalg.norm(s2))
        p0 = np.array([px, py])
        p1 = p0 + n1
        p2 = p1 + n2
        p3 = p0 + n2
        if has_fill:
            ctx.doc.line(
                f"\\fill[{fill_options(ctx, elem)}] {_coord(ctx, *p0)} -- {_coord(ctx, *p1)} "
                f"-- {_coord(ctx, *p2)} -- {_coord(ctx, *p3)} -- cycle;"
            )
        ctx.doc.line(
            f"\\draw[{stroke_options(ctx, elem, with_dash=False)}] "
            f"{_coord(ctx, *p1)} -- {_coord(ctx, *p2)} -- {_coord(ctx, *p3)};"
        )
    else:
        sx, sy = _arc_start(px, py, r, a0)
        if has_fill:
            ctx.doc.line(
                f"\\fill[{fill_options(ctx, elem)}] ({ctx.doc.num(px)},{ctx.doc.num(py)}) -- "
                f"{_coord(ctx, sx, sy)} arc ({ctx.doc.num(a0d)}:{ctx.doc.num(a1d)}:{ctx.doc.num(r)}) -- cycle;"
            )
        opts = stroke_options(ctx, elem, with_dash=False)
        for i in range(max(1, tick_count)):
            ri = r - i * arc_shift_mu
            if ri <= 0:
                continue
            ax, ay = _arc_start(px, py, ri, a0)
            ctx.doc.line(
                f"\\draw[{opts}] {_coord(ctx, ax, ay)} arc "
                f"({ctx.doc.num(a0d)}:{ctx.doc.num(a1d)}:{ctx.doc.num(ri)});"
            )

    if ctx.resolve(elem, "label_visible", default=False) is True:
        lr_px = ctx.resolve(elem, "label_radial_offset_px", default=0.0) or 0.0
        rl = r + float(lr_px) / ps
        mid = (a0 + a1) / 2
        lx = px + rl * math.cos(mid)
        ly = py + rl * math.sin(mid)
        emit_label(ctx, elem, lx, ly, labels, default_anchor="center")


# ── conic / function / implicit / locus ──────────────────────────────────

def emit_conic(ctx: TikzContext, elem, labels: List[str]) -> None:
    conic = elem.data
    ctype = conic.type
    if ctype == ConicType.EMPTY:
        return
    left, bottom, right_x, top_y = ctx.viewport()
    viewport = (left, bottom, right_x, top_y)
    segment_mu = 3.0 / ctx.ptUnit

    if ctype == ConicType.POINT:
        p = conic.as_point()
        if p is not None:
            opts = stroke_options(ctx, elem, with_dash=False)
            ctx.doc.line(
                f"\\fill[{opts}] ({ctx.doc.num(p.coords[0])},{ctx.doc.num(p.coords[1])}) circle (1.5pt);"
            )
        return

    if ctype == ConicType.CIRCLE:
        res = conic.as_circle()
        if res is not None:
            center, radius = res
            opts = _combined_fill_stroke(ctx, elem, fill_default=ctx.scene.style.background)
            ctx.doc.line(
                f"\\draw[{opts}] ({ctx.doc.num(center[0])},{ctx.doc.num(center[1])}) "
                f"circle ({ctx.doc.num(radius)});"
            )
        return

    if ctype == ConicType.ELLIPSE:
        params = conic.as_ellipse()
        if params is not None:
            a_semi, b_semi = params["semi_axes"]
            cx, cy = params["center"]
            rot_deg = math.degrees(params["rotation"])
            opts = _combined_fill_stroke(ctx, elem, fill_default=ctx.scene.style.background)
            opts += f", rotate around={{{ctx.doc.num(rot_deg)}:({ctx.doc.num(cx)},{ctx.doc.num(cy)})}}"
            ctx.doc.line(
                f"\\draw[{opts}] ({ctx.doc.num(cx)},{ctx.doc.num(cy)}) "
                f"ellipse ({ctx.doc.num(a_semi)} and {ctx.doc.num(b_semi)});"
            )
        return

    opts = stroke_options(ctx, elem)

    if ctype == ConicType.PARABOLA:
        params = conic.as_parabola()
        if params is not None:
            pf = make_parabola_param(params["vertex"], params["axis"],
                                     params["perp"], params["focal_parameter"])
            for tr in viewport_t_ranges_parabola(
                params["vertex"], params["axis"], params["perp"],
                params["focal_parameter"], viewport,
            ):
                for poly in sample_parametric(pf, tr, viewport, segment_mu=segment_mu):
                    _polyline(ctx, opts, poly)
        return

    if ctype == ConicType.HYPERBOLA:
        params = conic.as_hyperbola()
        if params is not None:
            a_semi, b_semi = params["semi_axes"]
            center_xy = params["center"]
            rot = params["rotation"]
            axis_u = np.array([np.cos(rot), np.sin(rot)])
            axis_v = np.array([-np.sin(rot), np.cos(rot)])
            for sign in (+1, -1):
                tr = viewport_t_range_hyperbola_branch(
                    center_xy, axis_u, axis_v, a_semi, b_semi, sign, viewport)
                if tr is None:
                    continue
                pf = make_hyperbola_branch_param(center_xy, axis_u, axis_v, a_semi, b_semi, sign)
                for poly in sample_parametric(pf, tr, viewport, segment_mu=segment_mu):
                    _polyline(ctx, opts, poly)
        return

    if ctype in (ConicType.INTERSECTING_LINES, ConicType.PARALLEL_LINES, ConicType.DOUBLE_LINE):
        corners = [(left, bottom), (right_x, top_y)]
        for ln in conic.as_lines() or []:
            endpoints = ln.get_endpoints(corners)
            if endpoints is None:
                continue
            p1, p2 = endpoints
            ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, p1[0], p1[1])} -- {_coord(ctx, p2[0], p2[1])};")


def emit_function(ctx: TikzContext, elem, labels: List[str]) -> None:
    func = elem.data
    left, bottom, right_x, top_y = ctx.viewport()
    viewport = (left, bottom, right_x, top_y)
    segment_mu = 3.0 / ctx.ptUnit

    x_range = (left, right_x)
    if func.explicit_domain is not None:
        dom_lo, dom_hi = func.explicit_domain
        x_range = (max(x_range[0], dom_lo), min(x_range[1], dom_hi))
    if x_range[0] >= x_range[1]:
        return

    def _fparam(t, f=func):
        return (float(t), float(f(t)))

    sings = sorted(s for s in func.natural_singularities if x_range[0] < s < x_range[1])
    width = x_range[1] - x_range[0]
    eps = max(width * 1e-3, 1e-6)
    edges = [x_range[0]] + sings + [x_range[1]]
    opts = stroke_options(ctx, elem)
    for k in range(len(edges) - 1):
        lo = edges[k] + (eps if k > 0 else 0.0)
        hi = edges[k + 1] - (eps if k < len(edges) - 2 else 0.0)
        if lo >= hi:
            continue
        for poly in sample_parametric(_fparam, (lo, hi), viewport, segment_mu=segment_mu):
            _polyline(ctx, opts, poly)


def emit_implicitcurve(ctx: TikzContext, elem, labels: List[str]) -> None:
    left, bottom, right_x, top_y = ctx.viewport()
    viewport = (left, bottom, right_x, top_y)
    opts = stroke_options(ctx, elem)
    for seg in marching_squares(elem.data, viewport, grid_n=128):
        if seg.shape[0] < 2:
            continue
        p1, p2 = seg[0], seg[1]
        ctx.doc.line(f"\\draw[{opts}] {_coord(ctx, p1[0], p1[1])} -- {_coord(ctx, p2[0], p2[1])};")


def emit_locuscurve(ctx: TikzContext, elem, labels: List[str]) -> None:
    if len(elem.data.points) < 2:
        return
    _polyline(ctx, stroke_options(ctx, elem), elem.data.points)


# ── free text ─────────────────────────────────────────────────────────────

def emit_text(ctx: TikzContext, elem, labels: List[str]) -> None:
    """Emit a GeoGebra free-text object as a ``\\node`` anchored top-left at its
    (offset) start point — mirrors ``AnimaGeoScene._render_text``."""
    text = elem.data
    decimals = getattr(ctx.scene.geo, "ggb_decimals", 2)
    content = text_to_display_latex(ctx.scene.geo, text, decimals)
    if not content:
        return

    base = resolve_text_position(ctx.scene.geo, text)
    x, y = float(base[0]), float(base[1])

    opts: List[str] = ["anchor=north west"]
    col = ctx.resolve(elem, "label_color", default=stroke_default(ctx))
    opts.append(f"text={ctx.doc.color(col)}")

    xshift = yshift = 0.0
    off = ctx.resolve(elem, "label_offset_px", default=None)
    if off is not None:
        xshift = ctx.offset_pt(off[0])
        yshift = ctx.offset_pt(off[1])
    p = ctx.opt.size_precision
    if abs(xshift) > 1e-6:
        opts.append(f"xshift={fmt_num(xshift, p)}pt")
    if abs(yshift) > 1e-6:
        opts.append(f"yshift={fmt_num(yshift, p)}pt")

    if ctx.opt.emit_font_size:
        fs_px = ctx.resolve(elem, "font_size_px", default=16.0)
        fpt = ctx.size_pt(fs_px)
        if fpt > 0:
            opts.append(
                f"font=\\fontsize{{{fmt_num(fpt, p)}}}{{{fmt_num(fpt * 1.2, p)}}}\\selectfont"
            )

    labels.append(f"\\node[{', '.join(opts)}] at {_coord(ctx, x, y)} {{{content}}};")


# ── dispatch table ────────────────────────────────────────────────────────

EMITTERS = {
    "point": emit_point,
    "segment": emit_segment,
    "line": emit_line,
    "ray": emit_ray,
    "vector": emit_vector,
    "circle": emit_circle,
    "arc": emit_arc,
    "circlesector": emit_circlesector,
    "polygon": emit_polygon,
    "angle": emit_angle,
    "conic": emit_conic,
    "function": emit_function,
    "implicitcurve": emit_implicitcurve,
    "locuscurve": emit_locuscurve,
    "text": emit_text,
}


def emitter_for(elem):
    """Return the emitter for ``elem`` (by lowercase ``elem.data`` class name)."""
    data = getattr(elem, "data", None)
    if data is None:
        return None
    return EMITTERS.get(type(data).__name__.lower())
