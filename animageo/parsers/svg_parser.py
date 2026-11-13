#from __future__ import annotations

import itertools
import tempfile
from contextlib import contextmanager
from pathlib import Path

import cairo
import numpy as np
from manim import ManimColor, VGroup, VMobject, constants
from manim.utils.family import extract_mobject_family_members

from ..dash import apply_cairo_dash

CAIRO_LINE_WIDTH_MULTIPLE: float = 0.01

# Default pixels-per-inch for vector PDF/EPS export. 96 dpi is the CSS pixel
# convention (matches the TikZ exporter's ``DEFAULT_DPI``), so a PDF reproduces
# the on-screen SVG size.
DEFAULT_DPI: float = 96.0

# Vector surface kinds understood by ``_get_cairo_context`` / ``_make_cairo_surface``.
CAIRO_SURFACES = ("svg", "pdf", "ps", "eps")

__all__ = ["create_svg_from_vmobject", "create_svg_from_vgroup", "_get_cairo_context", "extract_mobject_family_members", "_create_svg_from_vmobject_internal", "_draw_with_knockout"]


def _make_cairo_surface(kind: str, file_name: str | Path, width: float, height: float):
    """Create a cairo vector surface of the requested ``kind``.

    SVG surfaces are measured in CSS pixels; PDF/PS surfaces in PostScript
    points (1/72"). ``width``/``height`` must already be in the surface's
    native unit. ``eps`` is a single-page Encapsulated PostScript surface.
    """
    if kind == "svg":
        return cairo.SVGSurface(file_name, width, height)
    if kind == "pdf":
        return cairo.PDFSurface(file_name, width, height)
    if kind in ("ps", "eps"):
        surface = cairo.PSSurface(file_name, width, height)
        if kind == "eps":
            surface.set_eps(True)
        return surface
    raise ValueError(f"unsupported cairo surface kind: {kind!r} (expected one of {CAIRO_SURFACES})")


@contextmanager
def _get_cairo_context(
    file_name: str | Path,
    style=None,
    *,
    surface: str = "svg",
    dpi: float = DEFAULT_DPI,
    background: bool = True,
) -> cairo.Context:
    """Yield a cairo context drawing into ``file_name`` as ``surface``.

    The drawing CTM maps math units (MU) to the surface's device units, with
    the Y axis flipped (same convention for every surface kind). For SVG the
    device unit is the pixel; for PDF/EPS it is the PostScript point, so the
    MU→px transform is scaled by ``k = 72/dpi`` and the page size by the same
    factor — this reproduces the SVG's physical size at ``dpi``.
    ``background`` — paint the background of the style (``False`` — a
    transparent sheet).
    """
    if style is None:
        from manim import config
        export = {
            'ptUnit': 1,
            'ptWidth': config.pixel_width,
            'ptHeight': config.pixel_height,
            'ptXZero': 0,
            'ptYZero': 0,
        }
    else:
        export = style.export
    scale = export['ptUnit']
    pw = int(export['ptWidth'])
    ph = int(export['ptHeight'])
    dx = export['ptXZero']
    dy = export['ptYZero']

    if surface == "svg":
        # Preserve the historical SVG output byte-for-byte: integer px canvas,
        # unit MU→px transform.
        k = 1.0
        surf = _make_cairo_surface("svg", file_name, pw, ph)
        bg_w, bg_h = pw, ph
    else:
        k = 72.0 / float(dpi)
        bg_w, bg_h = pw * k, ph * k
        surf = _make_cairo_surface(surface, file_name, bg_w, bg_h)

    ctx = cairo.Context(surf)
    if background:
        _paint_background(ctx, bg_w, bg_h, style)
    ctx.set_matrix(cairo.Matrix(scale * k, 0, 0, -scale * k, dx * k, dy * k))
    yield ctx
    surf.finish()


def _paint_background(ctx: cairo.Context, width: int, height: int, style) -> None:
    rgba = _background_rgba(style)
    if rgba is None:
        return
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_rgba(*rgba)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()
    ctx.restore()


def _background_rgba(style):
    if style is None:
        return None
    color = getattr(style, 'background', None)
    if color is None:
        return None
    try:
        if hasattr(color, 'to_rgba'):
            return color.to_rgba()
        return ManimColor(color).to_rgba()
    except Exception:
        return None

def _set_cairo_context_color(ctx: cairo.Context, rgbas: np.ndarray, vmobject: VMobject):
    if len(rgbas) == 1:
        ctx.set_source_rgba(*rgbas[0])
    else:
        points = vmobject.get_gradient_start_and_end_points()
        pat = cairo.LinearGradient(*itertools.chain(*(point[:2] for point in points)))
        step = 1.0 / (len(rgbas) - 1)
        offsets = np.arange(0, 1 + step, step)
        for rgba, offset in zip(rgbas, offsets):
            pat.add_color_stop_rgba(offset, *rgba)
        ctx.set_source(pat)

def _apply_stroke(ctx: cairo.Context, vmobject: VMobject, style = None):
    width = vmobject.get_stroke_width()
    if width == 0: return
    
    _set_cairo_context_color(ctx, vmobject.get_stroke_rgbas(), vmobject)
    ctx.set_line_width(width * CAIRO_LINE_WIDTH_MULTIPLE)

    linecap = {
        None: cairo.LINE_CAP_BUTT,
        constants.CapStyleType.AUTO: cairo.LINE_CAP_BUTT,
        constants.CapStyleType.BUTT: cairo.LINE_CAP_BUTT,
        constants.CapStyleType.ROUND: cairo.LINE_CAP_ROUND,
        constants.CapStyleType.SQUARE: cairo.LINE_CAP_SQUARE
    }
    # manim 0.20+ dropped ``get_cap_style`` in favour of direct attribute
    # access. Both still work at present but only the attribute read is
    # warning-free.
    cap = getattr(vmobject, 'cap_style', None)
    ctx.set_line_cap(linecap[cap])
        
    joint_map = {
        None: cairo.LINE_JOIN_MITER,
        constants.LineJointType.AUTO: cairo.LINE_JOIN_MITER,
        constants.LineJointType.BEVEL: cairo.LINE_JOIN_BEVEL,
        constants.LineJointType.MITER: cairo.LINE_JOIN_MITER,
        constants.LineJointType.ROUND: cairo.LINE_JOIN_ROUND
    }
    
    ctx.set_line_join(joint_map[vmobject.joint_type])
    # A dashed stroke is one path with a dash pattern (animageo/dash.py):
    # cairo writes it as a single <path stroke-dasharray=...> in SVG and a
    # native dash in PDF/EPS. Reset afterwards so it never leaks.
    dashed = apply_cairo_dash(ctx, vmobject)
    ctx.stroke_preserve()
    if dashed:
        ctx.set_dash([])

def _apply_fill(ctx: cairo.Context, vmobject: VMobject, style = None):
    _set_cairo_context_color(ctx, vmobject.get_fill_rgbas(), vmobject)
    ctx.fill_preserve()

def _trace_path(ctx: cairo.Context, vmobject: VMobject):
    """Add the path of ``vmobject`` to the current path of ``ctx``."""
    subpaths = vmobject.gen_subpaths_from_points_2d(vmobject.points)
    for subpath in subpaths:
        quads = vmobject.gen_cubic_bezier_tuples_from_points(subpath)
        ctx.new_sub_path()
        start = subpath[0]
        ctx.move_to(*start[:2])
        for _p0, p1, p2, p3 in quads:
            ctx.curve_to(*p1[:2], *p2[:2], *p3[:2])
        if vmobject.consider_points_equals_2d(subpath[0], subpath[-1]):
            ctx.close_path()


def _create_svg_from_vmobject_internal(vmobject: VMobject, ctx: cairo.Context, style = None):
    points = vmobject.points
    if len(points) == 0: return

    ctx.new_path()
    _trace_path(ctx, vmobject)

    _apply_fill(ctx, vmobject, style = style)
    _apply_stroke(ctx, vmobject, style = style)


def _draw_with_knockout(mobjects, ctx: cairo.Context, style = None):
    """Draw ``mobjects`` (in drawing order) on a transparent sheet: a hole
    (a mobject tagged ``_animageo_hole`` — the inside of a hollow point) is
    not painted, it is cut out of every mobject drawn before it (under it),
    so the sheet shows through. Each hole clips with the even-odd rule
    (the canvas minus the hole); several holes clip one after another."""
    holes = [(i, _bbox(m)) for i, m in enumerate(mobjects) if getattr(m, '_animageo_hole', False) and len(m.points)]
    for i, mobj in enumerate(mobjects):
        if getattr(mobj, '_animageo_hole', False):
            continue
        box = _bbox(mobj) if holes and len(mobj.points) else None
        # only the holes over it (the stroke may reach a little past its path)
        later = [mobjects[j] for j, hole in holes
                 if j > i and box is not None and _overlap(box, hole, _reach(mobj))]
        if not later:
            _create_svg_from_vmobject_internal(mobj, ctx, style = style)
            continue
        ctx.save()
        x0, y0, x1, y1 = ctx.clip_extents()     # the sheet, in user units
        for hole in later:
            ctx.new_path()
            ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
            _trace_path(ctx, hole)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            ctx.clip()
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
        _create_svg_from_vmobject_internal(mobj, ctx, style = style)
        ctx.restore()


def _bbox(mobject):
    pts = np.asarray(mobject.points)[:, :2]
    return pts.min(axis=0), pts.max(axis=0)


def _reach(mobject):
    """Half the stroke width (in user units, MU) — how far it paints past the path."""
    return mobject.get_stroke_width() * CAIRO_LINE_WIDTH_MULTIPLE


def _overlap(a, b, pad):
    return bool(np.all(a[0] - pad <= b[1]) and np.all(b[0] <= a[1] + pad))

def create_svg_from_vmobject(vmobject: VMobject, file_name: str | Path = None, style = None) -> Path:
    if file_name is None:
        file_name = tempfile.mktemp(suffix=".svg")
    file_name = Path(file_name).absolute()

    with _get_cairo_context(file_name, style) as ctx:
        for _vmobject in extract_mobject_family_members([vmobject], True, True):
            _create_svg_from_vmobject_internal(_vmobject, ctx, style = style)
            
    return file_name

def create_svg_from_vgroup(vgroup: VGroup, file_name: str | Path = None, style = None) -> Path:
    if file_name is None:
        file_name = tempfile.mktemp(suffix=".svg")
    file_name = Path(file_name).absolute()
    
    with _get_cairo_context(file_name, style) as ctx:
        for _vmobject in extract_mobject_family_members(vgroup, True, True):
            _create_svg_from_vmobject_internal(_vmobject, ctx, style = style)

    return file_name
