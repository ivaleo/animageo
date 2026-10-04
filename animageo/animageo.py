import re
import os
import json
import math
import logging
import traceback
from contextlib import contextmanager
from types import SimpleNamespace
import numpy as np
import tempfile

from .geo import construction as geo
from .geo.lib_conic import ConicType
from .geo.curve_sampling import (
    sample_parametric,
    viewport_t_ranges_parabola,
    viewport_t_range_hyperbola_branch,
    make_parabola_param,
    make_hyperbola_branch_param,
    marching_squares,
    stitch_segments,
)
from .dash import (
    apply_cairo_dash, dash_pattern, dash_ratio, element_dash_px, get_dash,
    path_length, rendering_dash_period_px, set_dash,
)
from .style import GeoStyle, isnan, getColorFromDict, updateMin, updateMax, hasParam, GGB_FONT_SCALE, Z_FILL, Z_FILL_LABEL, Z_ANGLE, Z_STROKE, Z_POINT, Z_LABEL, _is_concrete_color
from .style.scaling import (
    ggb_font_px_to_manim_fontsize,
    stroke_width_to_manim,
)
from .style.import_policy import ImportPolicy
from .style.config import StyleConfig, resolve_style_input
from .style.resolver import resolve as _resolve_style
from .style.colorspace import COLOR_SPACES
from .labels import resolve_label_text, resolve_label_spec
from .ui import (
    RusTex, correctedLabel, create_label, round_corners_vmobject,
    ShowText, NumberedFrame, FixedLabel, CustomArrowTip, LABEL_ANCHORS,
    prewarm_decimal_glyphs, ValueLabel, install_cyrillic_tex_template,
    textify_cyrillic,
)
from manim import *

from .parsers.svg_parser import *
from .parsers.svg_parser import CAIRO_LINE_WIDTH_MULTIPLE
from .parsers import ggb_parser
from .keyframes import KeyframeSequence, apply_parsed_value
from .render_config import configure_render, install_gif_palette_fix, OUTPUT_FORMATS
from .export_layout import compute_export_layout
from .export_layout import compute_reference_export_layout
from .export_layout import normalize_content_options
from .export_layout import normalize_export_options
from .export_layout import resolve_auto_size
from .export_layout import size_from_config

import xml.etree.ElementTree as ET

SQRT2 = np.sqrt(2)

logger = logging.getLogger(__name__)


def _reference_size_from_config(reference):
    if not isinstance(reference, dict):
        return None
    size = size_from_config(reference.get('size'))
    if size is None or size[0] is None or size[1] is None:
        return None
    return size


def _style_ptUnit(style):
    export = getattr(style, 'export', {}) or {}
    return export.get('ptUnit_style', export.get('ptUnit', 1))


def _validate_rendered_bounds_policy(value):
    value = str(value)
    if value not in {'clip', 'ignore'}:
        raise ValueError("content.infinite_policy must be 'clip' or 'ignore'")
    return value


def _source_bounds_px_from_config(value):
    """Normalize an explicit rendered-bounds rectangle in source pixels."""
    if value is None:
        return None
    if isinstance(value, dict):
        keys = ('left', 'top', 'right', 'bottom')
        if all(k in value for k in keys):
            raw = [value[k] for k in keys]
        else:
            alt = ('sourceLeftPx', 'sourceTopPx', 'sourceRightPx', 'sourceBottomPx')
            if not all(k in value for k in alt):
                raise ValueError(
                    "content.bounds must have left/top/right/bottom "
                    "or sourceLeftPx/sourceTopPx/sourceRightPx/sourceBottomPx"
                )
            raw = [value[k] for k in alt]
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        raw = list(value)
    else:
        raise ValueError("content.bounds must be [left, top, right, bottom] or an object")

    try:
        left, top, right, bottom = [float(v) for v in raw]
    except (TypeError, ValueError):
        raise ValueError("content.bounds values must be numbers") from None
    if not all(math.isfinite(v) for v in (left, top, right, bottom)):
        raise ValueError("content.bounds values must be finite")
    return [left, top, right, bottom]


def _style_path_for_geostyle(style):
    """Return the style input shape supported by GeoStyle."""
    if isinstance(style, StyleConfig):
        return style.source
    if isinstance(style, dict):
        return style
    if isinstance(style, (str, os.PathLike)):
        return str(style)
    return None


def _merge_reference(style_reference, runtime_reference):
    ref = {}
    if isinstance(style_reference, dict):
        ref.update(style_reference)
    if isinstance(runtime_reference, dict):
        merged_size = {}
        if isinstance(ref.get('size'), dict):
            merged_size.update(ref['size'])
        if isinstance(runtime_reference.get('size'), dict):
            merged_size.update(runtime_reference['size'])
        ref.update(runtime_reference)
        if merged_size:
            ref['size'] = merged_size
    return ref


# Cap/joint lookups used by CreateMObject — lifted to module level so
# every render call doesn't re-allocate the dicts.
_JOINT_MAP = {
    None:      LineJointType.AUTO,
    "auto":    LineJointType.AUTO,
    "bevel":   LineJointType.BEVEL,
    "miter":   LineJointType.MITER,
    "round":   LineJointType.ROUND,
}
_CAP_MAP = {
    None:      CapStyleType.AUTO,
    "auto":    CapStyleType.AUTO,
    "round":   CapStyleType.ROUND,
    "butt":    CapStyleType.BUTT,
    "square":  CapStyleType.SQUARE,
}

# Automatic z-index tier by element type. Applied in ``_build_render_ctx``
# only when ``z_auto=True`` and ``elem.style['z_index']`` is unset.
_Z_AUTO_BY_TYPE = {
    geo.Polygon:      Z_FILL,
    geo.CircleSector: Z_FILL,
    geo.Angle:        Z_ANGLE,
    geo.Segment:      Z_STROKE,
    geo.Circle:       Z_STROKE,
    geo.Arc:          Z_STROKE,
    geo.Point:        Z_POINT,
    geo.Text:         Z_LABEL,
}

# Tie-break equal z-index tiers by construction order. Manim sorts flattened
# family members by z_index and otherwise keeps insertion order; polygons are
# recreated via remove+add during updates, so relying on insertion order makes
# MP4 layer order drift while keyframes play.
_Z_ORDER_EPSILON = 1e-6



def _scaled_triangle(pos, radius, rotation, col_s, col_f, op_f, op_s, lw, zz):
    """Equilateral triangle scaled so circumradius = *radius*, rotated."""
    tri = Triangle(
        color=col_s, fill_color=col_f, fill_opacity=op_f,
        stroke_width=lw, stroke_opacity=op_s,
    )
    verts = tri.get_vertices()
    cr = float(np.max(np.linalg.norm(verts - tri.get_center(), axis=1)))
    tri.scale(radius / cr)
    tri.move_to(pos)
    if rotation:
        tri.rotate(rotation)
    return tri.set_z_index(zz)


def reorder_objects_by_name(scene, name_order):
    ordered_objects = []
    other_objects = []
    
    for obj in scene.mobjects:
        if hasattr(obj, 'name') and obj.name in name_order:
            ordered_objects.append(obj)
        else:
            other_objects.append(obj)
    
    ordered_objects.sort(key=lambda x: name_order.index(x.name))
    scene.mobjects = ordered_objects + other_objects


def _import_map_lookup(mapping, *values):
    """Find an import-map entry by raw or already-scaled style value."""
    for value in values:
        if value is None:
            continue
        keys = [str(value)]
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = None
        if numeric is not None and numeric.is_integer():
            keys.append(str(int(numeric)))
        for key in keys:
            if key in mapping:
                return mapping[key]
    return None


def _coerce_import_number(value):
    if isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return value
        return int(numeric) if numeric.is_integer() else numeric
    return value
    
class NamedValueTracker(ValueTracker):
    def __init__(self, name: str = None, value: float = 0):
        super().__init__(value)
        self.name = name


class DashCamera(MovingCamera):
    """``MovingCamera`` that strokes a mobject's own dash pattern.

    A dashed stroke is one path carrying an ``animageo.dash.DashPattern``
    (in MU, the camera context's user space); manim's camera knows nothing
    about it, so set the cairo dash around each stroke and reset it after.
    """

    def apply_stroke(self, ctx, vmobject, background=False):
        dashed = apply_cairo_dash(ctx, vmobject)
        try:
            return super().apply_stroke(ctx, vmobject, background)
        finally:
            if dashed:
                ctx.set_dash([])


class AnimaGeoScene(MovingCameraScene):
    def __init__(self):
        # Video frames go through DashCamera: dashes are a stroke property,
        # not a path cut into pieces, so the camera has to apply them.
        super().__init__(camera_class=DashCamera)
        # Cyrillic-capable TeX template as the process-wide manim default, so
        # no Tex path — ours, manim's own, future or degradational — can fall
        # back to the stock template and die on "Unicode character … not set
        # up". Idempotent; safe to run per scene (see ui.py for why this is
        # NOT the Mobject.set_default footgun).
        install_cyrillic_tex_template()
        # GIF export: keep the adaptive palettegen palette (pal8) instead of
        # manim's rgb8 (fixed 3-3-2 grid) which scrambles colors into
        # yellow/green artifacts. Idempotent; see render_config.py.
        install_gif_palette_fix()
        self.geo = geo.Construction()
        self.style = GeoStyle()
        # New-style unified config. Always populated with builtin defaults so
        # the resolver has a baseline even when applyStyle() is never called.
        # User JSON/dict merges on top when applyStyle(style=...) runs.
        self.style_config = StyleConfig.load()

        self._styles_back = {}
        self._shade_mobjects = {}
        self._construction_source = {'kind': 'unknown'}

        self.cuts = 0
        self._label_tracker = None  # Set by autoPlaceLabels(dynamic=True)
        # When True, value-bearing labels rebuilt during animation use the fast
        # DecimalNumber-backed ValueLabel (no LaTeX recompile per frame) instead
        # of a full Tex. Toggled around animation playback; static render/export
        # keeps the Tex path for trailing-zero fidelity. See _value_labels_fast.
        self._value_labels_dynamic = False
        
    def mobject(self, name): 
        for mobj in self.mobjects: 
            if mobj.name == name: return mobj
        return None
    
    def element(self, name):
        return self.geo.element(name)
    
    def addOrdered(self, mobj):
        name_order = [elem.name for elem in self.geo.elements]
        if mobj.name not in name_order:
            self.add(mobj)
            return
        self.add(mobj)
    
    def addGeoElement(self, elem):
        mobj = self.CreateMObject(elem, z_auto = True)
        if mobj is not None and self._element_visible(elem):
            self.add(mobj)

    def addAllGeometry(self, show = False):
        if not show:
            for el in self.geo.elements: el.visible = False
        self.addCoordinateBackground()

        element_types = [
            [geo.CircleSector, geo.Polygon],
            [geo.Angle],
            [geo.Circle, geo.Arc, geo.Segment, geo.Vector, geo.Line, geo.Ray,
             geo.LocusCurve, geo.Conic, geo.Function, geo.ImplicitCurve],
            [geo.Point],
            [geo.Text],
        ]

        for el_types in element_types:
            for el in self.geo.elements:
                if type(el.data) in el_types: self.addGeoElement(el)

    def _element_visible(self, elem):
        return bool(_resolve_style(self, elem, 'visible', default=getattr(elem, 'visible', True)))

    def _import_enabled(self, style=None):
        style = style or self.style
        return (style.imp or {}).get('enabled', True) is not False

    def getAllGeometryBounds(self, ptUnit = 1):
        bounds = [None,None,None,None]
        for elem in self.geo.elements:
            if self._element_visible(elem) and not isinstance(elem.data, (geo.Line, geo.Ray)):
                mobj = self.CreateMObject(elem, z_auto = True)
                if mobj is not None:
                    bounds[0] = updateMin(bounds[0], mobj.get_left()[0])
                    bounds[1] = updateMin(bounds[1], mobj.get_bottom()[1])
                    bounds[2] = updateMax(bounds[2], mobj.get_right()[0])
                    bounds[3] = updateMax(bounds[3], mobj.get_top()[1])
                    
        if bounds[0] is None:
            bounds = [-10,-10,10,10]
        
        for i in range(4): bounds[i] *= ptUnit
                    
        return bounds

    def _set_camera_from_export(self, export):
        """Set camera frame from an export dict without accumulating shifts."""
        ptUnit = export['ptUnit']
        ratio = float(config.pixel_width) / float(config.pixel_height)
        if export['ptWidth'] / export['ptHeight'] >= ratio:
            self.camera.frame.set(width=export['ptWidth'] / ptUnit)
            dx = self.camera.frame.width / 2 - export['ptXZero'] / ptUnit
            dy = export['ptHeight'] / (2 * ptUnit) - export['ptYZero'] / ptUnit
        else:
            self.camera.frame.set(width=ratio * export['ptHeight'] / ptUnit)
            dx = export['ptWidth'] / (2 * ptUnit) - export['ptXZero'] / ptUnit
            dy = self.camera.frame.height / 2 - export['ptYZero'] / ptUnit
        self.camera.frame.move_to(ORIGIN)
        self.camera.frame.shift(dx * RIGHT + dy * DOWN)

    def _rendered_bounds_source_view(
        self,
        source_view,
        *,
        padding_px=0,
        infinite_policy='ignore',
        label_bounds='reserve',
    ):
        """Return a source_view based on rendered visible mobject bounds.

        Bounds are measured in scene MU after style resolution, then converted
        back to source pixel coordinates using the original GeoGebra view. For
        ``infinite_policy='ignore'`` skips ``Line``/``Ray`` objects so finite
        geometry drives the measured rectangle. ``'clip'`` measures them after
        clipping to the current source camera.

        ``label_bounds`` controls whether point/element labels count toward the
        crop. ``'reserve'`` (default) includes them so an outward-placed label
        does not clip on export (the historical behaviour). ``'exclude'`` crops
        to the geometry alone — a label above/beside the drawing no longer pushes
        the frame out, at the cost of possibly clipping that label.
        """
        infinite_policy = _validate_rendered_bounds_policy(infinite_policy)
        exclude_labels = (label_bounds == 'exclude')
        padding_px = max(float(padding_px or 0), 0.0)

        def geometry_extent(mobj):
            """(left, bottom, right, top) of *mobj*'s drawn geometry, excluding
            label submobjects. Element mobjects are ``VGroup([geometry, label])``
            (see ``ui.create_label``, which tags labels ``_animageo_is_label``);
            measuring the group directly lets a label — e.g. a vertex label that
            sits above the drawing — inflate the crop past the geometry. Framing
            crops to the geometry alone; labels are placed within the resolved
            scale afterwards."""
            lefts, bottoms, rights, tops = [], [], [], []

            def visit(node):
                if getattr(node, '_animageo_is_label', False):
                    return
                subs = getattr(node, 'submobjects', None) or ()
                if subs:
                    for sub in subs:
                        visit(sub)
                    return
                points = getattr(node, 'points', None)
                if points is None or len(points) == 0:
                    return
                try:
                    lefts.append(float(node.get_left()[0]))
                    bottoms.append(float(node.get_bottom()[1]))
                    rights.append(float(node.get_right()[0]))
                    tops.append(float(node.get_top()[1]))
                except Exception:
                    return

            visit(mobj)
            if not lefts:
                return None
            return min(lefts), min(bottoms), max(rights), max(tops)

        bounds = [None, None, None, None]
        for elem in self.geo.elements:
            if not self._element_visible(elem):
                continue
            if infinite_policy == 'ignore' and isinstance(elem.data, (geo.Line, geo.Ray)):
                continue
            mobj = self.CreateMObject(elem, z_auto=True)
            if mobj is None:
                continue
            if exclude_labels:
                extent = geometry_extent(mobj)
                if extent is None:
                    continue
                left, bottom, right, top = extent
            else:
                left = float(mobj.get_left()[0])
                bottom = float(mobj.get_bottom()[1])
                right = float(mobj.get_right()[0])
                top = float(mobj.get_top()[1])
            bounds[0] = updateMin(bounds[0], left)
            bounds[1] = updateMin(bounds[1], bottom)
            bounds[2] = updateMax(bounds[2], right)
            bounds[3] = updateMax(bounds[3], top)

        if bounds[0] is None:
            return dict(source_view)

        left_mu, bottom_mu, right_mu, top_mu = bounds
        unit = float(source_view.get('ptUnit', 1))
        xzero = float(source_view.get('ptXZero', 0))
        yzero = float(source_view.get('ptYZero', 0))

        left_px = xzero + left_mu * unit - padding_px
        right_px = xzero + right_mu * unit + padding_px
        top_px = yzero - top_mu * unit - padding_px
        bottom_px = yzero - bottom_mu * unit + padding_px

        width = max(right_px - left_px, 1.0)
        height = max(bottom_px - top_px, 1.0)
        rendered_view = dict(source_view)
        rendered_view.update({
            'ptWidth': width,
            'ptHeight': height,
            'ptXZero': xzero - left_px,
            'ptYZero': yzero - top_px,
            'sourceLeftPx': left_px,
            'sourceTopPx': top_px,
            'sourceRightPx': right_px,
            'sourceBottomPx': bottom_px,
            'boundsPaddingPx': padding_px,
            'boundsInfinitePolicy': infinite_policy,
        })
        return rendered_view

    def _source_view_from_bounds_px(
        self,
        source_view,
        bounds_px,
        *,
        padding_px=0,
        infinite_policy='ignore',
    ):
        """Return a source_view from explicit source-pixel bounds."""
        left_px, top_px, right_px, bottom_px = _source_bounds_px_from_config(bounds_px)
        padding_px = max(float(padding_px or 0), 0.0)
        left_px -= padding_px
        top_px -= padding_px
        right_px += padding_px
        bottom_px += padding_px

        xzero = float(source_view.get('ptXZero', 0))
        yzero = float(source_view.get('ptYZero', 0))
        width = max(right_px - left_px, 1.0)
        height = max(bottom_px - top_px, 1.0)
        rendered_view = dict(source_view)
        rendered_view.update({
            'ptWidth': width,
            'ptHeight': height,
            'ptXZero': xzero - left_px,
            'ptYZero': yzero - top_px,
            'sourceLeftPx': left_px,
            'sourceTopPx': top_px,
            'sourceRightPx': right_px,
            'sourceBottomPx': bottom_px,
            'boundsPaddingPx': padding_px,
            'boundsInfinitePolicy': _validate_rendered_bounds_policy(infinite_policy),
            'boundsSource': 'explicit',
        })
        return rendered_view

    #пауза для обрезки видео + отображение ярлыка слева
    def waitCut(self, msg = None, **kwargs):
        self.cuts += 1

        rect = Rectangle(color = RED, fill_opacity = 1, height = self.camera.frame_height, width = self.camera.frame_width/4).move_to(self.camera.frame_center).shift( (3/8) * self.camera.frame_width * LEFT)
        txt = Text(str(msg) if msg is not None else str(self.cuts)).set_color(BLACK).scale(3).move_to(rect)
        
        self.add(rect, txt)
        self.wait(**kwargs)

        self.remove(rect)
        self.remove(txt)

    def updateAllGeometry(self):
        self.updateGeoElements()
    
    def updateGeoElements(self, updates = None):
        for elem in self.geo.elements:
            if updates: 
                if elem.name not in updates: continue

            mobj = self.mobject(elem.name)   
            mobj_new = self.CreateMObject(elem)
            
            if mobj is None and mobj_new is None: continue
         
            needRemove = False if mobj is None     else (mobj_new is None) or (type(elem.data) == geo.Polygon) or (not self._element_visible(elem))
            needAdd = False    if mobj_new is None else (mobj is None)     or (type(elem.data) == geo.Polygon)

            if needRemove:
                mobj.set_opacity(0)
                self.remove(mobj)
            if needAdd:
                self.addOrdered(mobj_new)
            if not needRemove and not needAdd:
                mobj.become(mobj_new)
                # become() copies points/draw style but not z_index, the cap
                # or the dash pattern — carry them so style changes (incl.
                # keyframe tracks, solid <-> dashed) take effect.
                for sub_old, sub_new in zip(mobj.get_family(), mobj_new.get_family()):
                    sub_old.z_index = sub_new.z_index
                    if hasattr(sub_new, 'cap_style'):
                        sub_old.cap_style = sub_new.cap_style
                    set_dash(sub_old, get_dash(sub_new))

    def addVar(self, name, value = 0):
        new_tracker = NamedValueTracker(name, value)
        self.add(new_tracker)
        if not self.geo.var(name):
            self.geo.add(geo.Var(name, value))
        else:
            self.geo.update(name, value)

        self.geo.rebuild(full = True)
        self.updateAllGeometry()
        return new_tracker
    
    @contextmanager
    def _dynamic_value_labels(self):
        """Enable fast DecimalNumber-backed value labels for the duration.

        Per-frame rebuilds of value-bearing labels then use ``ValueLabel``
        instead of recompiling a ``Tex`` each frame. Saves/restores the prior
        flag so nesting (e.g. ``animating`` inside ``play_keyframes``) is safe."""
        if self._value_labels_fast():
            prewarm_decimal_glyphs()
        prev = self._value_labels_dynamic
        self._value_labels_dynamic = True
        try:
            yield
        finally:
            self._value_labels_dynamic = prev

    def addUpdater(self, tracker):
        # Animation is starting: route value labels through the fast path.
        if self._value_labels_fast():
            prewarm_decimal_glyphs()
        self._value_labels_dynamic = True
        tracker.add_updater(lambda v, self = self: self.updateVar(tracker))
    def clearUpdater(self, tracker):
        tracker.clear_updaters()
        self._value_labels_dynamic = False

    @contextmanager
    def animating(self, tracker):
        """Context manager for addUpdater/play/clearUpdater pattern.

        Usage:
            x = self.addVar('x', 0)
            with self.animating(x):
                self.play(x.animate.set_value(1), run_time=3)
        """
        self.addUpdater(tracker)
        try:
            yield tracker
        finally:
            self.clearUpdater(tracker)

    def loadCode(self, filepath, debug = False, show = True):
        logger.info("Loading DSL code from %s", filepath)
        with open(filepath) as f:
            code = f.read()
        from .parsers import dsl
        dsl.run(self.geo, code, debug=debug, show=show)
        self._construction_source = {
            'kind': 'dsl_file',
            'name': os.path.basename(filepath),
            'path': os.path.abspath(filepath),
        }
        self.geo.rebuild(debug=debug, full=True)
        self.updateAllGeometry()

    def putCode(self, code, debug = False, show = True):
        """Parse DSL ``code`` against this scene's Construction.

        Uses the exec-based engine in :mod:`animageo.parsers.dsl` —
        full Python (for/if/def/comprehensions/kwargs/tuple-unpack,
        ``A.style.stroke = '#f00'``, field access ``A.x``). See
        ``docs/python_dsl.md`` for the full surface.
        """
        logger.info("Executing DSL code (%d chars)", len(code))
        from .parsers import dsl
        dsl.run(self.geo, code, debug=debug, show=show)
        self._construction_source = {'kind': 'dsl_inline'}
        self.geo.rebuild(debug=debug, full=True)
        self.updateAllGeometry()

    def applyStyle(
        self,
        style = None,
        import_policy = None,
        reference = None,
        content = None,
        export = None,
    ):
        """Apply style and configure the scene viewport.

        The current layout pipeline is:

        ``style.reference`` / runtime ``reference`` -> ``content`` placement
        into that reference canvas -> physical ``export`` size.

        ``content`` controls which source rectangle is placed into the
        reference canvas (``source_view``/``ggb_view``/``rendered_bounds``).
        ``export`` controls the final SVG/PNG/MP4 canvas. Construction
        coordinates and style dictionaries are not mutated by layout.
        """
        style = resolve_style_input(style)
        style_path = _style_path_for_geostyle(style)
        if style_path == '':
            style_path = None
        style_obj = GeoStyle(style=style_path)
        if isinstance(style_path, dict):
            style_label = style_path.get('name') or '<dict>'
        else:
            style_label = style_path or 'builtin'
        logger.info("Applying style: %s", style_label)
        # Reload unified StyleConfig — merges builtin.json with the optional
        # style input. Resolver and renderer read from this going forward.
        self.style_config = StyleConfig.load(style)

        # Keep scene-level GeoStyle fields in sync for renderer paths that
        # still use the scene container for defaults and export metadata.
        colors = self.style_config.presets.get('color', {})
        style_obj.col              = colors.get('main',         style_obj.col)
        style_obj.col_light        = colors.get('light',        style_obj.col_light)
        style_obj.col_accent       = colors.get('accent',       style_obj.col_accent)
        style_obj.col_accent_light = colors.get('accent_light', style_obj.col_accent_light)
        style_obj.col_shade        = colors.get('shade',        style_obj.col_shade)
        style_obj.strong           = colors.get('strong',       style_obj.strong)
        style_obj.background       = colors.get('background',   style_obj.background)

        # Background resolution — style primary, GeoGebra secondary (opt-in),
        # white fallback. "Cleared" style background (not background_explicit)
        # falls through to the GeoGebra <bgColor>, which ggb_parser.load wrote
        # into self.style.export (self.style is still the *previous* style here;
        # the new style_obj is installed later via setStyle()).
        rendering_bg = self.style_config.rendering.get('background')
        if style_obj.background_explicit:
            if _is_concrete_color(rendering_bg):
                style_obj.background = rendering_bg
            # else: the explicit presets.color.background set just above stands.
        else:
            ggb_bg = self.style.export.get('background')
            style_obj.background = ggb_bg if _is_concrete_color(ggb_bg) else '#ffffff'

        # Mirror the effective background into presets so fill refs and the
        # rendering.background self-ref resolve to it.
        self.style_config.presets.setdefault('color', {})['background'] = style_obj.background

        if 'polygon_boundary_layer' in style_obj.rendering:
            if style_obj.rendering['polygon_boundary_layer'] == 'top':
                for comm in self.geo.commands:
                    if comm.name == 'Polygon':
                        for segm in comm.outputs[1:]:
                            if self.geo.element(segm):
                                self.geo.element(segm).style['z_index'] = 10
                            
        import_enabled = self._import_enabled(style_obj)

        if import_enabled and 'colors' in style_obj.imp:
            ggb_colors = style_obj.imp['colors']
            for elem in self.geo.elements:
                ggb_style = getattr(elem, 'ggb_style', None)
                if not ggb_style:
                    continue
                col = ggb_style.get('stroke')
                col_opacity = ggb_style.get('stroke_opacity')
                col_new = getColorFromDict(ggb_colors, [col, col_opacity])
                if col_new is not None: 
                    ggb_style['stroke'] = col_new.color
                    if col_new.opacity is not None:
                        ggb_style['stroke_opacity'] = col_new.opacity
            
                col = ggb_style.get('fill')
                col_opacity = ggb_style.get('fill_opacity')
                col_new = getColorFromDict(ggb_colors, [col, col_opacity])
                if col_new is not None: 
                    ggb_style['fill'] = col_new.color
                    if col_new.opacity is not None:
                        ggb_style['fill_opacity'] = col_new.opacity

        point_size_map = style_obj.imp.get('point_size') if import_enabled else None
        if point_size_map:
            for elem in self.geo.elements:
                ggb_style = getattr(elem, 'ggb_style', None)
                if not ggb_style:
                    continue
                raw_size = (getattr(elem, 'ggb_raw', {}) or {}).get('point_size')
                style_size = ggb_style.get('size_px')
                size_new = _import_map_lookup(point_size_map, raw_size, style_size)
                if size_new is not None:
                    ggb_style['size_px'] = _coerce_import_number(size_new)
                        
        line_width_map = style_obj.imp.get('line_width') if import_enabled else None
        if line_width_map:
            for elem in self.geo.elements:
                ggb_style = getattr(elem, 'ggb_style', None)
                if not ggb_style:
                    continue
                raw_wid = (getattr(elem, 'ggb_raw', {}) or {}).get('line_thickness')
                style_wid = ggb_style.get('stroke_width_px')
                wid_new = _import_map_lookup(line_width_map, raw_wid, style_wid)
                if wid_new is not None:
                    ggb_style['stroke_width_px'] = _coerce_import_number(wid_new)

        # Carry over GGB-specific keys before replacing the export dict
        ggb_font_px = self.style.export.get('fontSize')
        ggb_ptUnit = self.style.export.get('ptUnit_ggb')

        def preserve_ggb_metadata():
            export_dict = style_obj.export
            if ggb_font_px:
                export_dict['fontSize'] = ggb_font_px
            if ggb_ptUnit:
                export_dict.setdefault('ptUnit_ggb', ggb_ptUnit)

        def apply_ggb_font_size():
            if not ggb_font_px:
                return
            style_obj.font_size = ggb_font_px_to_manim_fontsize(ggb_font_px, _style_ptUnit(style_obj))
            if import_enabled:
                for elem in self.geo.elements:
                    if getattr(elem, 'ggb_raw', None):
                        # Global GGB fontSize is only a *fallback* for elements the
                        # import policy did not size: `setdefault`, never overwrite.
                        # A plain assignment clobbered the faithful per-element font
                        # (`ImportPolicy.resolve_overrides_only` → `font_size_px`),
                        # and because this runs LAST only on the rendered_bounds path
                        # (repeated `_finalize_layout`) but the import override runs
                        # last on ggb_view/source_view/manual, label size ended up
                        # depending on the «Кадр» — a point/stroke-free divergence
                        # that made «Крупность» of labels jump when the frame changed.
                        elem.ggb_style.setdefault('font_size_px', ggb_font_px)

        policy_applied = False
        source_view = dict(self.style.export)
        self._export_source_view = dict(source_view)
        style_reference = getattr(self.style_config, 'reference', {})
        runtime_reference = _merge_reference(style_reference, reference)
        explicit_reference_size = size_from_config(_reference_size_from_config(runtime_reference))
        reference_size = explicit_reference_size or [source_view.get('ptWidth'), source_view.get('ptHeight')]
        reference_size = resolve_auto_size(reference_size, [source_view.get('ptWidth'), source_view.get('ptHeight')])
        # Decoration density is a property of the *drawing on the style's reference
        # canvas*, NOT of the crop: it must stay fixed when content.source (the
        # «Кадр») changes. Preserve the style reference size + source view here,
        # before rendered_bounds overwrites reference_size with the tight crop.
        style_density_source_view = dict(source_view)
        style_density_reference_size = list(reference_size)

        export_options = normalize_export_options(export)
        export_size = resolve_auto_size(
            size_from_config(export_options.get('size')),
            reference_size,
        )

        content_options = normalize_content_options(content)
        _validate_rendered_bounds_policy(content_options.get('infinite_policy', 'ignore'))
        use_rendered_bounds = content_options['source'] == 'rendered_bounds'
        base_content_options = content_options

        if use_rendered_bounds:
            # Establish the source-view camera + import overrides once up front so
            # the rendered-bounds measurement inside _finalize_layout() sees
            # fully-styled mobjects.
            style_obj.export = dict(source_view)
            preserve_ggb_metadata()
            self.setStyle(style_obj)
            self._set_camera_from_export(style_obj.export)
            apply_ggb_font_size()
            self._active_import_policy = self._resolve_import_policy(
                import_policy, import_enabled=import_enabled)
            self._apply_import_policy_overrides(self._active_import_policy)
            policy_applied = True

        def _finalize_layout():
            """Resolve and apply the export layout from the current scene state.

            For ``rendered_bounds`` the camera is reset to the source view first
            so label/Tex extents convert MU→source-px at one consistent
            ``ptUnit``. Idempotent and safe to call more than once: a later call
            picks up auto-placed label offsets (written to ``elem.style``) so the
            measured crop reserves room for the labels themselves — otherwise
            outward-shifted edge/corner labels get clipped off the canvas.

            Camera frame setup is the 2D path only. Switching to ThreeDScene will
            require rewriting both branches to use the 3D camera's
            orientation/zoom instead of MovingCameraScene.frame.
            """
            nonlocal reference_size
            layout_source_view = source_view
            content_opts = base_content_options
            if use_rendered_bounds:
                self._set_camera_from_export(dict(source_view))
                explicit_bounds = base_content_options.get('bounds')
                if explicit_bounds is not None:
                    layout_source_view = self._source_view_from_bounds_px(
                        source_view,
                        explicit_bounds,
                        padding_px=0,
                        infinite_policy=base_content_options.get('infinite_policy', 'ignore'),
                    )
                else:
                    # Crop tight to the rendered bounds (no source-view expansion);
                    # content.padding is now a canvas-edge margin applied by the
                    # reference→export layout stage, not a source crop inset.
                    layout_source_view = self._rendered_bounds_source_view(
                        source_view,
                        padding_px=0,
                        infinite_policy=base_content_options.get('infinite_policy', 'ignore'),
                        label_bounds=base_content_options.get('label_bounds', 'reserve'),
                    )
                if explicit_reference_size is None:
                    reference_size = [
                        layout_source_view.get('ptWidth'),
                        layout_source_view.get('ptHeight'),
                    ]
                content_opts = base_content_options

            layout = compute_reference_export_layout(
                layout_source_view,
                reference_size=reference_size,
                export_size=export_size,
                content=content_opts,
                export=export_options,
            )
            style_obj.export = dict(layout_source_view)
            style_obj.export.update(layout.to_export_dict())
            style_obj.export['reference'] = runtime_reference

            # Preserve GGB keys + font size in the new export dict, then point the
            # camera at the resolved export frame.
            preserve_ggb_metadata()
            apply_ggb_font_size()
            self._set_camera_from_export(style_obj.export)
            self.setStyle(style_obj)

        _finalize_layout()

        # The rendered-bounds crop is measured before label auto-placement, which
        # then shifts labels outward from the geometry — pushing labels of edge/
        # corner elements outside the just-frozen canvas so they clip on export.
        # Place labels at the resolved scale, then re-fit the crop so the final
        # canvas includes them. Offsets are pixel-based, so the re-fit's small
        # uniform scale change does not move labels relative to their points (no
        # re-placement, no oscillation). Tex bbox measurements are cached, so the
        # extra pass is cheap.
        if use_rendered_bounds and self.style_config.overlay.label_placement.get('enabled'):
            try:
                self.autoPlaceLabels()
            except Exception:
                logger.warning(
                    "autoPlaceLabels failed during rendered_bounds fit", exc_info=True)
            else:
                _finalize_layout()

        # Decoration density (`ptUnit_style`) is finalised here — after the layout,
        # crop and autoPlaceLabels are frozen, before CreateMObject reads sizes.
        #
        # Framing-independence (opt-in via content.decoration_scale_source ==
        # 'reference'): ggb_view/source_view/manual already size decorations against
        # the full source view, but rendered_bounds sizes them against the *tight
        # crop*, which makes «Крупность» depend on the frame. Re-base the
        # rendered_bounds density on the style reference over the full source view
        # so switching the «Кадр» no longer changes how large points/strokes/labels
        # look relative to the drawing.
        #
        # Gated because it needs a STABLE source view: fitView() iterates
        # applyStyle(rendered_bounds) where each pass's source view IS the previous
        # pass's crop, so re-basing there would freeze decorations to a stale scale
        # and break convergence. It stays on 'frame' (default) and keeps decorations
        # tracking the tight fit; only the config-driven (web) path, which applies
        # the real viewport exactly once, opts into 'reference'.
        #
        # «Element prominence» then divides that density, scaling all decorations
        # together, in place — geometry, crop and label positions untouched.
        prominence = content_options.get('prominence', 1.0) or 1.0
        decoration_source = content_options.get('decoration_scale_source')
        export_dict = getattr(self.style, 'export', None)
        if isinstance(export_dict, dict):
            base = export_dict.get('ptUnit_style')
            if decoration_source == 'output':
                # Decorations are a FIXED OUTPUT size, controlled ONLY by
                # «Крупность» (prominence) — the «Кадр» must scale the geometry
                # alone. Anchor the density to the geometry's export zoom
                # (`ptUnit`): then decoration_px = authored_px * ptUnit /
                # ptUnit_style = authored_px * prominence, independent of how the
                # frame is sized or typed. (Contrast 'reference', which fixes the
                # decoration/geometry *proportion* and so lets absolute px grow as
                # the frame zooms in.)
                geom_zoom = export_dict.get('ptUnit')
                if geom_zoom:
                    base = geom_zoom
            elif decoration_source == 'ggb':
                # «Как в GeoGebra»: decorations keep the relative size they have in
                # the applet and scale with the OUTPUT canvas, but not with the
                # «Кадр»/crop. Anchor ptUnit_style to the geometry's export zoom
                # scaled by (ggb_view_width / output_width); the export-zoom factor
                # then cancels in decoration_px = authored * ptUnit / ptUnit_style,
                # leaving authored * (output_width / ggb_view_width) * prominence —
                # crop-independent, output-proportional, = applet px at that width.
                geom_zoom = export_dict.get('ptUnit')
                out_w = export_dict.get('ptWidth')
                ggb_w = (style_density_source_view or {}).get('ptWidth')
                try:
                    if geom_zoom and out_w and ggb_w and float(out_w) > 0:
                        base = float(geom_zoom) * float(ggb_w) / float(out_w)
                except (TypeError, ValueError):
                    pass
            elif use_rendered_bounds and decoration_source == 'reference':
                try:
                    density = compute_export_layout(
                        style_density_source_view,
                        export_size=style_density_reference_size,
                        fit='contain',
                        source_rect='source_view',
                    ).ptUnit
                except Exception:
                    logger.debug("framing-independent density failed; keeping crop-based ptUnit_style", exc_info=True)
                    density = None
                if density:
                    base = density
            if base:
                export_dict['ptUnit_style'] = base / prominence
                if prominence != 1.0:
                    export_dict['elementProminence'] = prominence

        # ImportPolicy: GGB-only raw→import-style transforms
        # (scale:/quantize:/remap:) layered into elem.ggb_style. Skipped for DSL-built
        # elements (empty ggb_raw). Cross-origin stylisation lives in
        # StyleOverlay and is read lazily by the resolver.
        if not policy_applied:
            self._active_import_policy = self._resolve_import_policy(
                import_policy, import_enabled=import_enabled)
            self._apply_import_policy_overrides(self._active_import_policy)

    def fitView(self, width=800, height=600, *, padding=40, style=None,
                passes=2):
        """Frame the visible construction on a ``width``x``height`` px canvas.

        The canonical fit for DSL-built scenes: a scene without a GGB
        viewport has no meaningful default one, so raw ``exportSVG``/render
        output is blank or wildly mis-scaled. ``fitView`` measures the
        rendered bounds of the currently *visible* elements and configures
        the ``reference -> content -> export`` layout so the content fills
        the canvas with a uniform ``padding`` px margin.

        Runs ``passes`` rounds of ``applyStyle(content='rendered_bounds')``
        + ``updateAllGeometry()``: the first round measures mobjects built
        at the previous scale and fixes the pixel-style scale
        (``ptUnit_style``); the next round re-measures with correctly sized
        points/labels so the crop is tight. Two passes converge for typical
        scenes.

        Call it after the construction is built and while the elements to
        frame are visible (before ``HideAll`` in an animation flow). For
        animations, budget extra ``padding`` (or hidden extent points) so
        moving geometry stays inside the fitted frame.

        Args:
            width: export (and reference) canvas width in pixels.
            height: export (and reference) canvas height in pixels.
            padding: uniform canvas-edge margin in pixels.
            style: optional style (path / dict / ``StyleConfig``) to apply;
                by default the scene's current style configuration is kept.
            passes: number of measure+rebuild rounds (>= 1).
        """
        if int(passes) < 1:
            raise ValueError('fitView requires passes >= 1')
        if style is None:
            style = self.style_config
        kwargs = dict(
            style=style,
            reference={'size': {'width': width, 'height': height}},
            content={'source': 'rendered_bounds', 'padding': padding},
            export={'size': {'width': width, 'height': height}},
        )
        for _ in range(int(passes)):
            self.applyStyle(**kwargs)
            self.updateAllGeometry()

    def _resolve_import_policy(self, import_policy, import_enabled=True):
        if not import_enabled:
            return None
        if import_policy is not None:
            return import_policy
        cfg = (self.style.imp or {}).get('policy')
        if cfg:
            return ImportPolicy.from_dict(cfg)
        return ImportPolicy.faithful()

    def _apply_import_policy_overrides(self, policy):
        """Layer ``policy.resolve_overrides_only()`` on top of ``elem.ggb_style``.

        Only GGB-imported elements are touched — the guard on ``ggb_raw``
        skips DSL-built elements because their raw-GGB values don't exist.
        Cross-origin stylisation (per_type/per_name) is the job of
        :class:`StyleOverlay`, read lazily by the resolver.
        Faithful policy (default) returns an empty override dict.
        """
        if policy is None:
            return
        ptUnit = _style_ptUnit(self.style)
        for elem in self.geo.elements:
            if isinstance(elem, geo.Var):
                continue
            if not getattr(elem, 'ggb_raw', None):
                continue
            overrides = policy.resolve_overrides_only(elem, defaults={}, ptUnit=ptUnit)
            ggb_style = getattr(elem, 'ggb_style', None)
            if ggb_style is None:
                continue
            for key, value in overrides.items():
                if key == 'visible':
                    elem.set_visible(value, explicit=False)
                else:
                    ggb_style[key] = value

    def reloadPolicy(self, import_policy):
        """Apply a new ImportPolicy without re-parsing the .ggb XML.

        Requires a prior loadGGB so elements carry ``ggb_raw``. Rebuilds
        the geometry and recreates mobjects so the new style takes effect.
        """
        self._active_import_policy = import_policy
        self._apply_import_policy_overrides(import_policy)
        self.addAllGeometry(show = True)

    def resetScene(self):
        """Reset construction and rendered state so the scene can load fresh input.

        Wipes ``self.geo`` (Construction), rendered mobjects, and the label
        tracker. Called by ``loadGGB`` so consecutive loads don't bleed
        geometry from earlier files into later renders. Safe to call
        directly when reusing an ``AnimaGeoScene`` across jobs.
        """
        self.geo = geo.Construction()
        self._label_tracker = None
        self._construction_source = {'kind': 'unknown'}
        try:
            self.clear()  # manim Scene.clear() — drop accumulated mobjects
        except Exception:
            pass
        from .label_placement import clear_bbox_cache
        clear_bbox_cache()

    def loadGGB(self, filepath, style = None, import_policy = None,
                debug = False, generate_stubs = True, strict = False,
                reference = None, content = None, export = None):
        """Load a GeoGebra ``.ggb`` file into this scene's Construction.

        Replaces any previously loaded geometry — call ``resetScene`` first
        is not required. To compose multiple sources, load the first via
        ``loadGGB`` then extend with ``putCode``/``loadCode`` which are
        additive.

        ``strict`` controls unsupported GGB command handling. In the default
        non-strict mode unsupported root commands are collected in
        ``scene.geo.command_diagnostics`` and dependency cascades are quiet.
        With ``strict=True`` the first unsupported root command raises.

        ``generate_stubs`` (default True) additionally writes
        ``<basename>_stubs.pyi`` next to the ``.ggb`` with type
        declarations for every loaded element. DSL files can then
        do ``from <basename>_stubs import *`` for one-line IDE
        autocomplete (see ``docs/python_dsl.md``). Pass False to
        disable.

        Layout follows :meth:`applyStyle`: ``style`` provides visual defaults
        and optional authoring ``reference``; runtime ``content`` places the
        construction into that reference canvas; runtime ``export`` chooses the
        physical output.
        """
        self.resetScene()
        logger.info("Loading GGB: %s", filepath)
        self._construction_source = {
            'kind': 'ggb',
            'name': os.path.basename(filepath),
            'path': os.path.abspath(filepath),
        }
        ggb_parser.load(self.geo, self.style.export, filepath, debug = debug, strict = strict)
        old_strict = self.geo.strict_unsupported
        old_log = self.geo.log_unsupported
        self.geo.strict_unsupported = bool(strict)
        self.geo.log_unsupported = bool(debug or strict)
        try:
            self.geo.rebuild(debug = debug, full = True)
        finally:
            self.geo.strict_unsupported = old_strict
            self.geo.log_unsupported = old_log
        self.applyStyle(
            style=style,
            import_policy = import_policy,
            reference = reference,
            content = content,
            export = export,
        )
        self.addAllGeometry(show = True)
        if generate_stubs:
            from .parsers.dsl.stub_gen import write_ggb_stubs
            write_ggb_stubs(self.geo, filepath)
        if self.style_config.overlay.label_placement.get('enabled'):
            self.autoPlaceLabels()

    def loadDocument(self, doc, style=None, import_policy=None,
                     reference=None, content=None, export=None, *,
                     inputs=None, debug=False):
        """Load an ``animageo-construction/v1`` document (``animageo.native``).

        The analogue of :meth:`loadGGB`: the source view comes from the
        document's ``viewDefaults.bounds`` (``native.source_view``) instead of
        the applet window, the construction from the bridge
        (``animageo.native.kernel.bridge``: element ``e_<id>`` per document
        element, ``self.native_names`` maps IDs and names), and
        ``appearance`` (visibility, labels, style overrides) is applied before
        :meth:`applyStyle`. ``inputs`` override free input values.
        ``style``/``reference``/``content``/``export`` are as in
        :meth:`loadGGB`. Issues of ``appearance`` are kept in
        ``self.native_diagnostics``.
        """
        from .native.document import as_document
        from .native.kernel.bridge import build_construction
        from .native.rendering import appearance_plan, source_view

        doc = as_document(doc)
        self.resetScene()
        view = source_view(doc)
        # Replaces what an earlier .ggb left (background, fontSize); the source
        # unit doubles as ptUnit_ggb, so label offsets are world units.
        self.style.export = dict(view)
        self.style.export['ptUnit_ggb'] = view['ptUnit']
        construction, names = build_construction(doc, inputs=inputs)
        self.geo = construction
        self.native_names = names
        self._construction_source = {'kind': 'native', 'documentId': doc.document_id}
        construction.log_unsupported = bool(debug)
        construction.rebuild(debug=debug, full=True)
        plan, diagnostics = appearance_plan(doc, view['ptUnit'], inputs=inputs)
        for el_id, entry in plan.items():
            elem = construction.objectByName(names.by_id[el_id])
            if isinstance(elem, geo.Element):   # a Var (free number) is not drawn
                elem.visible = entry['visible']
            for key, value in entry['style'].items():
                elem.style[key] = value
        self.native_diagnostics = diagnostics
        self.applyStyle(
            style=style,
            import_policy=import_policy,
            reference=reference,
            content=content,
            export=export,
        )
        self.addAllGeometry(show=True)
        if self.style_config.overlay.label_placement.get('enabled'):
            self.autoPlaceLabels()

    def autoPlaceLabels(self, dynamic: bool = False):
        """Run automatic label placement to minimize overlaps.

        Args:
            dynamic: when ``True``, after the initial placement installs a
                ``LabelTracker`` on the scene. Subsequent ValueTracker-driven
                animations (``addUpdater(x); play(x.animate.set_value(...))``)
                will re-run the solver per frame with EMA smoothing and
                anchor hysteresis so labels track moving geometry without
                jumping. Off by default.
        """
        from .label_placement import (
            auto_place_labels, compute_label_layout, apply_label_layout,
        )
        if not dynamic:
            auto_place_labels(self)
            return

        cfg = dict(self.style_config.overlay.label_placement or {})
        # A direct API call is an explicit opt-in even when the style overlay's
        # automation flag is false in the builtin defaults.
        cfg['enabled'] = True
        canonicalize = bool(cfg.get('canonicalize_anchor', False))

        layout = compute_label_layout(self, cfg=cfg, canonicalize=canonicalize)
        if layout:
            apply_label_layout(self, layout, rerender=True)
        self._seed_label_tracker(layout, cfg)

    def _seed_label_tracker(self, layout, cfg):
        """Seed dynamic label state from an already-applied layout."""
        prev_offset = {}
        prev_anchor = {}
        target_offset = {}
        target_anchor = {}
        kinds = {}
        angle_params = {}

        for name, pl in layout.items():
            elem = self.geo.element(name)
            if elem is None:
                continue
            off = _resolve_style(self, elem, 'label_offset_px', default=pl.offset_ggb)
            prev_offset[name] = np.array([float(off[0]), float(off[1])])
            prev_anchor[name] = _resolve_style(self, elem, 'label_anchor', default=pl.label_anchor)
            target_offset[name] = np.asarray(pl.offset_ggb, dtype=float)
            target_anchor[name] = pl.label_anchor
            kinds[name] = pl.kind
            if pl.kind == 'dynamic_angle':
                angle_params[name] = pl.angle_params

        solver_every_n = max(1, int(cfg.get('solver_every_n_frames', 2)))
        self._label_tracker = {
            'prev_offset': prev_offset,
            'prev_anchor': prev_anchor,
            'anchor_flip_counter': {},
            'angle_params': angle_params,
            'cfg': cfg,
            # Make the next updateVar frame recompute the target layout. The
            # immediate sync below seeds current values, but moving geometry
            # should not spend one frame following a stale target.
            'frame_counter': solver_every_n - 1,
            'last_target_offset': target_offset,
            'last_target_anchor': target_anchor,
            'last_kinds': kinds,
        }

    def _sync_auto_labels(self, *, rerender_visible=True, seed_tracker=True,
                          smooth=False):
        """Synchronize dynamic auto-label layout with current scene state.

        Used around visibility transitions, before newly visible mobjects are
        created. The layout is applied to element styles immediately; only
        mobjects that already exist and are still visible are rebuilt here, so
        a staged ``Show`` does not accidentally materialize future elements.
        """
        tracker = self._label_tracker
        if tracker is None:
            return {}
        cfg = tracker.get('cfg') or {}
        if not cfg.get('enabled', False):
            return {}

        from .label_placement import (
            compute_label_layout, apply_label_layout,
        )

        canonicalize = bool(cfg.get('canonicalize_anchor', False))
        layout = compute_label_layout(self, cfg=cfg, canonicalize=canonicalize)
        apply_label_layout(self, layout, rerender=False)

        if seed_tracker:
            self._seed_label_tracker(layout, cfg)

        if rerender_visible:
            updates = []
            for name in layout:
                elem = self.geo.element(name)
                if elem is None or not self._element_visible(elem):
                    continue
                if self.mobject(name) is not None:
                    updates.append(name)
            if updates:
                self.updateGeoElements(updates)

        return layout

    def clearLabelTracker(self):
        """Detach the label tracker. Subsequent updateVar calls skip the per-frame solver."""
        self._label_tracker = None

    def _apply_dynamic_labels(self):
        """Re-run the placement solver and apply smoothed updates. Called from updateVar."""
        tracker = self._label_tracker
        if tracker is None:
            return
        from .label_placement import (
            compute_label_layout, compute_angle_label_offset_px,
            apply_ema_step, anchor_hysteresis_step,
        )

        cfg = tracker['cfg']
        canonicalize = bool(cfg.get('canonicalize_anchor', False))
        ema_alpha = float(cfg.get('ema_alpha', 0.2))
        anchor_flip_frames = int(cfg.get('anchor_flip_frames', 6))
        solver_every_n = max(1, int(cfg.get('solver_every_n_frames', 2)))

        tracker['frame_counter'] += 1
        run_solver = (tracker['frame_counter'] % solver_every_n) == 0

        ptUnit = _style_ptUnit(self.style)
        ptUnit_ggb = self.style.export.get('ptUnit_ggb', ptUnit)

        # Solver target (only recompute when due). Between solver runs, the
        # EMA step still advances static labels toward the last target.
        if run_solver or 'last_target_offset' not in tracker:
            layout = compute_label_layout(self, cfg=cfg, canonicalize=canonicalize)
            target_offset = {}
            target_anchor = {}
            kinds = {}
            angle_params = dict(tracker['angle_params'])
            for name, pl in layout.items():
                target_offset[name] = np.asarray(pl.offset_ggb, dtype=float)
                target_anchor[name] = pl.label_anchor
                kinds[name] = pl.kind
                if pl.kind == 'dynamic_angle':
                    angle_params[name] = pl.angle_params
            tracker['last_target_offset'] = target_offset
            tracker['last_target_anchor'] = target_anchor
            tracker['last_kinds'] = kinds
            tracker['angle_params'] = angle_params
        else:
            target_offset = tracker['last_target_offset']
            target_anchor = tracker['last_target_anchor']
            kinds = tracker['last_kinds']
            angle_params = tracker['angle_params']

        changed = []
        prev_offset = tracker['prev_offset']
        prev_anchor = tracker['prev_anchor']
        flip_counter = tracker['anchor_flip_counter']

        for name, kind in kinds.items():
            elem = self.geo.element(name)
            if elem is None or not self._element_visible(elem):
                continue

            if kind == 'dynamic_angle':
                # Continuous bisector — no EMA, no hysteresis.
                ap = angle_params.get(name)
                if ap is None:
                    continue
                new_offset = np.array(
                    compute_angle_label_offset_px(elem.data, ap, ptUnit, ptUnit_ggb),
                    dtype=float,
                )
                new_anchor = target_anchor.get(name, 'MC')
            else:
                tgt = target_offset[name]
                prev = prev_offset.get(name, tgt)
                new_offset = apply_ema_step(prev, tgt, ema_alpha)

                # Anchor hysteresis: require `anchor_flip_frames` consecutive
                # frames of the solver proposing a different anchor before
                # switching. Under canonicalize_anchor=True this is a no-op
                # because every anchor is 'MC'.
                proposed_anchor = target_anchor[name]
                current_anchor = prev_anchor.get(name, proposed_anchor)
                new_anchor, flip_counter[name] = anchor_hysteresis_step(
                    current_anchor, proposed_anchor,
                    flip_counter.get(name, 0), anchor_flip_frames,
                )

            old_off = prev_offset.get(name)
            old_anchor = prev_anchor.get(name)
            if (old_off is None
                    or not np.allclose(old_off, new_offset, atol=1e-6)
                    or old_anchor != new_anchor):
                elem.style['label_offset_px'] = [float(new_offset[0]), float(new_offset[1])]
                elem.style['label_anchor'] = new_anchor
                elem.style['_auto_placed'] = True
                changed.append(name)

            prev_offset[name] = new_offset
            prev_anchor[name] = new_anchor

        if changed:
            self.updateGeoElements(changed)

    def updateVar(self, tracker):
        var_name = tracker.name
        if self.geo.var(var_name).data != tracker.get_value():
            self.geo.update(var_name, float(tracker.get_value()))
            updates = self.geo.rebuild()
            self.updateGeoElements(updates)
            if self._label_tracker is not None:
                self._apply_dynamic_labels()

    def setStyle(self, style):
        self.style = style

        self.camera.background_color = self.style.background
        # Never call Text/MathTex/MarkupText.set_default here: manim wraps the
        # *current* __init__ in a new functools.partialmethod on every call
        # (no flattening), so per-render calls grew the chain until any label
        # hit RecursionError after ~1000 renders in one process. Label colour
        # is always passed explicitly (col_label in _build_render_ctx).
    
    def Hide(self, names, **kwargs):
        plays = []
        hidden = []

        for name in names:
            elem = self.element(name)
            if not elem: continue
            if not self._element_visible(elem): continue
            
            elem.visible = False
            hidden.append(name)
            
            mobj = self.mobject(name)
            self.remove(mobj)
            
            if mobj: plays.append(FadeOut(mobj))
        if hidden:
            self._sync_auto_labels(rerender_visible=True, seed_tracker=True)
        return plays
    
    def HideAll(self, **kwargs):
        return self.Hide([elem.name for elem in self.geo.elements], **kwargs)

    def Update(self, names, **kwargs):
        plays = []

        for name in names:
            elem = self.element(name)
            if not elem: continue
            
            mobj = self.mobject(name)
            self.remove(mobj)
            
            if mobj: plays.append(FadeOut(mobj))

            mobj_new = self.CreateMObject(elem)
            if mobj_new: self.addOrdered(mobj_new)
            
            if mobj_new: plays.append(FadeIn(mobj_new))
            
        return plays
    
    def UpdateAll(self, **kwargs):
        return self.Update([elem.name for elem in self.geo.elements], **kwargs)
    
    def ShowCreate(self, name, **kwargs):
        """Return animations that draw an element: ``Create`` for strokes,
        ``FadeIn`` for the filled first sub-mobject (for types with both)."""
        elem = self.element(name)
        mobj = self.mobject(name)
        if not elem or not mobj: return []
        
        if type(elem.data) in [geo.Polygon, geo.Circle, geo.Angle]:
            plays = [FadeIn(mobj[0], **kwargs)]
            for mo in mobj[1:]:
                plays.append(Create(mo, **kwargs))
            return plays
        else:
            return [Create(mobj, **kwargs)]

    def Show(self, names, mode = 'Fade', **kwargs):
        plays = []
        to_show = []

        for name in names:
            elem = self.element(name)
            if not elem: continue
            if self._element_visible(elem): continue
            
            elem.visible = True
            to_show.append(name)

        if to_show:
            self._sync_auto_labels(rerender_visible=True, seed_tracker=True)

        for name in to_show:
            elem = self.element(name)
            if not elem: continue
            mobj_new = self.CreateMObject(elem)
            if mobj_new: self.addOrdered(mobj_new)
            
            if mobj_new: 
                if mode == 'Create':
                    plays += self.ShowCreate(name, **kwargs)
                else:
                    plays.append(FadeIn(mobj_new, **kwargs))
            
        return plays
    
    def ShowAll(self, **kwargs):
        return self.Show([elem.name for elem in self.geo.elements], **kwargs)
    
    def Shade(self, names, **kwargs):
        plays = []
        for name in names:
            mobj = self.mobject(name)
            if not mobj: continue
            elem = self.geo.element(name)
            if not elem: continue

            self._styles_back[name] = {}

            if elem.style.get('z_index'): 
                self._styles_back[name]['z_index'] = elem.style['z_index']
                elem.style['z_index'] = 0

            if elem.style.get('stroke'): 
                self._styles_back[name]['stroke'] = elem.style['stroke']
                elem.style['stroke'] = self.style.col_shade

            if elem.style.get('fill'):
                self._styles_back[name]['fill'] = elem.style['fill']
                elem.style['fill'] = self.style.col_shade

            if elem.style.get('label_visible'):
                self._styles_back[name]['label_color'] = elem.style['label_color'] if ('label_color' in elem.style) else self.style.strong
                elem.style['label_color'] = self.style.col_shade

            if type(elem.data) == geo.Point:
                self._styles_back[name]['fill_opacity'] = elem.style['fill_opacity'] if ('fill_opacity' in elem.style) else 1
                elem.style['fill_opacity'] = 0

            self._shade_mobjects['_shade_' + name] = self.CreateMObject(elem)
            plays.extend(self.Hide([name], **kwargs))
            plays.append(FadeIn(self._shade_mobjects['_shade_' + name], **kwargs))

        return plays

    def Restore(self, names, **kwargs):
        plays = []
        for name in names:
            mobj = self.mobject(name)
            if not mobj: continue
            if name not in self._styles_back: continue
            elem = self.geo.element(name)
            style_back = self._styles_back[name]
            if (not elem) or (not style_back): continue

            for key in style_back: elem.style[key] = style_back[key]

            plays.extend(self.Show([name], **kwargs))
            plays.append(FadeOut(self._shade_mobjects['_shade_' + name], **kwargs))
            del self._shade_mobjects['_shade_' + name]

        return plays

    def setElementStyle(self, names, *, update=True, **props):
        """Set style properties on multiple elements at once.

        By default, mobjects for the touched elements are rerendered
        immediately so the change is visible in the next frame. Pass
        ``update=False`` to batch several setter calls and then trigger
        one combined rerender via ``updateAllGeometry`` or
        ``updateGeoElements(names)``.

        Example:
            self.setElementStyle(['a', 'b', 'c'], stroke='#ff0000', fill_opacity=0.5)
        """
        touched = []
        for name in names:
            elem = self.element(name)
            if elem is None:
                continue
            for key, value in props.items():
                elem.style[key] = value
            touched.append(name)
        if update and touched:
            self.updateGeoElements(updates=touched)

    def setVisible(self, names, visible, *, update=True):
        """Set visibility on multiple elements at once.

        Rerenders by default — geometry appears/disappears immediately.
        Pass ``update=False`` to defer rendering (combine with explicit
        ``updateGeoElements`` for bulk operations).
        """
        touched = []
        for name in names:
            elem = self.element(name)
            if elem is None:
                continue
            elem.visible = visible
            touched.append(name)
        if update and touched:
            self._sync_auto_labels(rerender_visible=True, seed_tracker=True)
            self.updateGeoElements(updates=touched)

    def playHide(self, names, **kwargs):
        plays = self.Hide(names, **kwargs)
        if plays: self.play(*plays)
        
    def playUpdate(self, names, **kwargs):
        plays = self.Update(names, **kwargs)
        if plays: self.play(*plays)

    def playShow(self, names, mode = 'Fade', **kwargs):
        plays = self.Show(names, mode, **kwargs)
        if plays: self.play(*plays)

    def playShade(self, names, mode = 'Fade', **kwargs):
        plays = self.Shade(names, mode, **kwargs)
        if plays: self.play(*plays)

    def playRestore(self, names, mode = 'Fade', **kwargs):
        plays = self.Restore(names, mode, **kwargs)
        if plays: self.play(*plays)

    # ── Keyframe animation ────────────────────────────────────────────

    def get_independent_elements(self):
        """Return dict of independent (animatable) elements for keyframe UI.

        Returns dict: name -> {type, value/coords/tparam, constraint, ...}.
        Designed for web service to build a keyframe editing interface.
        """
        return self.geo.get_independents()

    def get_element_states(self):
        """Per-element snapshot for the web keyframe-state inspector: every
        non-axis element's type, current visibility, and resolved animatable
        style values (the keys in ``ANIMATABLE_STYLE_KEYS``). Symmetric to
        ``get_independent_elements()``; read-only.
        """
        from .style.animatable import ANIMATABLE_STYLE_KEYS
        states = {}
        for elem in self.geo.elements:
            if elem.name in ('xAxis', 'yAxis'):
                continue
            style = {}
            for key in ANIMATABLE_STYLE_KEYS:
                val = _resolve_style(self, elem, key, default=None)
                if val is not None:
                    style[key] = val
            states[elem.name] = {
                'type': type(elem.data).__name__,
                'visible': self._element_visible(elem),
                'style': style,
            }
        return states

    def _apply_interp_value(self, name, kind, val):
        """Apply a single parsed (kind, val) to the construction in place.

        Shared between ``on_frame`` during keyframe playback and the
        snapshot pass that pre-computes per-keyframe label layouts.
        """
        apply_parsed_value(self.geo, name, kind, val)

    def _snapshot_independents(self):
        """Capture current values of every independent element as raw JSON.

        Returns a dict suitable for feeding back through _parse_value +
        _apply_interp_value to restore state after the snapshot pass.
        """
        info_map = self.geo.get_independents()
        raw = {}
        for name, info in info_map.items():
            etype = info['type']
            if etype == 'free_point':
                raw[name] = list(info['coords'])
            elif etype == 'free_text':
                raw[name] = list(info['position'])
            elif etype == 'tparam_point':
                t = info['tparam']
                raw[name] = {
                    'tparam': list(t) if isinstance(t, (list, tuple)) else float(t)
                }
            elif etype in ('number', 'measure', 'angle'):
                raw[name] = float(info['value'])
            elif etype == 'boolean':
                raw[name] = bool(info['value'])
        return raw, info_map

    def _apply_camera(self, cam):
        """Apply a ``{center?, width?}`` dict to ``self.camera.frame``.

        No-op for an empty/falsy dict. Only moves/resizes the camera frame —
        never mutates construction or style state.
        """
        if not cam:
            return
        if 'center' in cam:
            cx, cy = cam['center']
            self.camera.frame.move_to([float(cx), float(cy), 0.0])
        if 'width' in cam:
            self.camera.frame.set(width=float(cam['width']))

    def _apply_keyframe_state(self, kf, element_info, *, update_scene=True):
        """Apply one keyframe's values and visibility before playback starts."""
        from .keyframes import _parse_value

        touched = set()
        for name, raw_value in kf.values.items():
            info = element_info.get(name)
            if info is None:
                logger.warning(
                    "play_keyframes: skipping initial value for '%s' — element "
                    "is no longer independent",
                    name,
                )
                continue
            try:
                kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "play_keyframes: bad initial keyframe value for '%s' (%r): %s",
                    name, raw_value, e,
                )
                continue
            self._apply_interp_value(name, kind, val)
            touched.add(name)

        for name, props in kf.styles.items():
            elem = self.geo.element(name)
            if elem is None:
                logger.warning(
                    "play_keyframes: skipping styles for '%s' — element not found",
                    name,
                )
                continue
            for key, value in props.items():
                if value is None:
                    continue   # null at keyframe 0 has nothing to revert
                elem.style[key] = value
            touched.add(name)

        for name in kf.show:
            elem = self.geo.element(name)
            if elem is not None:
                elem.visible = True
                touched.add(name)
        for name in kf.hide:
            elem = self.geo.element(name)
            if elem is not None:
                elem.visible = False
                touched.add(name)

        for name, vis in kf.visible.items():
            elem = self.geo.element(name)
            if elem is not None:
                elem.visible = bool(vis)
                touched.add(name)

        self._apply_camera(kf.camera)

        updates = self.geo.rebuild()
        touched.update(updates.keys())
        if update_scene and touched:
            self.updateGeoElements(touched)

    def _compute_keyframe_label_layouts(self, seq, cfg, indices=None):
        """Run ``compute_label_layout`` at every keyframe. Restores state after.

        Walks keyframes carrying-forward values and visibility (matching the
        semantics of ``_build_intervals``). At each keyframe: apply, rebuild,
        snapshot layout. After the pass, restore saved values + visibility
        and do a full rebuild so the scene is identical to before the call.
        """
        from .label_placement import compute_label_layout, clear_bbox_cache
        from .keyframes import _parse_value

        canonicalize = bool(cfg.get('canonicalize_anchor', False))

        saved_raw, element_info = self._snapshot_independents()
        saved_visibility = {e.name: e.visible for e in self.geo.elements}

        # Snapshot the original value of every (name, key) that ANY keyframe's
        # 'styles' animates, so it can be restored byte-for-byte afterward
        # (the pre-pass must be side-effect-free on elem.style).
        animated_keys = {
            (name, key)
            for kf in seq.keyframes
            for name, props in kf.styles.items()
            for key in props
        }
        saved_styles = {}
        for name, key in animated_keys:
            elem = self.geo.element(name)
            if elem is None:
                continue
            saved_styles[(name, key)] = (key in elem.style, elem.style.get(key))

        clear_bbox_cache()

        # Carry-forward running state, starting from current construction values
        running_raw = dict(saved_raw)
        running_vis = dict(saved_visibility)
        running_styles = {}

        layouts = []
        for kf_index, kf in enumerate(seq.keyframes):
            # Override with this keyframe's values
            for name, raw_value in kf.values.items():
                running_raw[name] = raw_value
            for name in kf.show:
                running_vis[name] = True
            for name in kf.hide:
                running_vis[name] = False
            for name, props in kf.styles.items():
                running_styles.setdefault(name, {}).update(props)

            # Apply to geo
            for name, raw_value in running_raw.items():
                info = element_info.get(name) or seq.element_info.get(name)
                if info is None:
                    logger.warning(
                        "play_keyframes: skipping value for '%s' — element "
                        "is no longer independent (was it rebound or removed "
                        "between sequence parse and playback?)",
                        name,
                    )
                    continue
                try:
                    kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(
                        "play_keyframes: bad keyframe value for '%s' (%r): %s",
                        name, raw_value, e,
                    )
                    continue
                self._apply_interp_value(name, kind, val)
            for name, vis in running_vis.items():
                e = self.geo.element(name)
                if e is not None:
                    e.visible = vis
            for name, props in running_styles.items():
                elem = self.geo.element(name)
                if elem is None:
                    continue
                for k, v in props.items():
                    if v is not None:
                        elem.style[k] = v

            if indices is not None and kf_index not in indices:
                # A single-frame preview needs only its interval's two ends.
                layouts.append({})
                continue
            self.geo.rebuild()
            layouts.append(compute_label_layout(
                self, cfg=cfg, canonicalize=canonicalize,
            ))

        # Restore original state
        for (name, key), (had, val) in saved_styles.items():
            elem = self.geo.element(name)
            if elem is None:
                continue
            if had:
                elem.style[key] = val
            else:
                elem.style.pop(key, None)
        for name, raw_value in saved_raw.items():
            info = element_info.get(name)
            if info is None:
                logger.warning(
                    "play_keyframes: cannot restore '%s' — element disappeared "
                    "from the construction during the snapshot pass",
                    name,
                )
                continue
            try:
                kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "play_keyframes: restore parse error for '%s' (%r): %s",
                    name, raw_value, e,
                )
                continue
            self._apply_interp_value(name, kind, val)
        for name, vis in saved_visibility.items():
            e = self.geo.element(name)
            if e is not None:
                e.visible = vis
        self.geo.rebuild(full=True)

        return layouts

    def _style_track_baseline(self, elem, key):
        """Resolved value a keyframe style track starts from / reverts to.

        The dash period falls back to ``rendering.dash_period_px`` (the drawn
        value), so an element without its own period still lerps from it.
        """
        default = rendering_dash_period_px(self) if key == 'stroke_dash_period_px' else None
        return _resolve_style(self, elem, key, default=default)

    def play_keyframes(self, keyframes_data):
        """Play keyframe animation from JSON data or KeyframeSequence.

        When ``overlay.label_placement.keyframe_snapshots`` is true, runs a
        pre-pass to compute an auto-placed label layout at every keyframe;
        labels then interpolate smoothly between those layouts during
        playback. Angle labels additionally track their bisector per frame
        when ``dynamic_angles`` is true.

        Args:
            keyframes_data: dict (JSON) or KeyframeSequence instance
        """
        if isinstance(keyframes_data, dict):
            seq = KeyframeSequence.from_json(keyframes_data, self.geo)
        else:
            seq = keyframes_data
        logger.info("Playing %d keyframes", len(seq.keyframes))

        if seq.has_style_tracks():
            color_space = self.style.rendering.get('color_interpolation', 'oklab')
            if color_space not in COLOR_SPACES:
                raise ValueError(
                    f"rendering.color_interpolation must be one of {COLOR_SPACES}, "
                    f"got {color_space!r}"
                )
            seq.bind_style_tracks(
                get_element=self.geo.element,
                resolve=self._style_track_baseline,
                color_space=color_space,
            )

        use_v2_visibility = (seq.version >= 2)
        if use_v2_visibility:
            seq.bind_visibility(get_element=self.geo.element)

        layouts = self._bind_label_snapshots(seq)
        use_snapshots = layouts is not None

        # Value-bearing labels animate via fast DecimalNumber-backed ValueLabels
        # for the whole sequence (no LaTeX recompile per frame, no engine swap
        # mid-animation). Pre-warm the digit glyph cache before the first frame.
        with self._dynamic_value_labels():
            self._apply_keyframe_state(seq.keyframes[0], seq.element_info)

            if use_snapshots and layouts and layouts[0]:
                from .label_placement import apply_label_layout
                apply_label_layout(self, layouts[0], rerender=True)

            for i, interval in enumerate(seq.intervals):
                if use_v2_visibility and (interval.enter_effects or interval.exit_effects):
                    self._play_keyframe_interval_v2(interval)
                    self._finalize_style_interval(interval)
                    continue

                # Legacy visibility path (v1, and v2 intervals with no effects)
                if interval.show:
                    plays = self.Show(interval.show)
                    if plays:
                        self.play(*plays, run_time=0.4)
                if interval.hide:
                    plays = self.Hide(interval.hide)
                    if plays:
                        self.play(*plays, run_time=0.4)

                has_labels = bool(interval.label_interps) or bool(interval.dynamic_angle_params)
                has_styles = bool(interval.style_interps)
                if (not interval.interpolators and not has_labels and not has_styles
                        and interval.camera_interp is None and not interval.events):
                    if interval.duration > 0:
                        self.wait(interval.duration)
                    self._finalize_style_interval(interval)
                    continue

                self._play_keyframe_interval(interval)
                self._finalize_style_interval(interval)

    def _bind_label_snapshots(self, seq, indices=None):
        """Auto-place labels at every keyframe and let them interpolate.

        Snapshots ARE auto-placement, only sampled at keyframes, so they run
        only when ``overlay.label_placement.enabled`` is on (and
        ``keyframe_snapshots`` asks for them). With auto-placement off a
        label keeps the offset the user gave it; the snapshots used to
        override that and fly an applet-placed label off-frame.

        Once attached, the snapshots own every label position: a keyframe's
        own ``label_offset_px`` only fed the solver at that keyframe. As a
        style track it fought the snapshot interpolators (both write the
        offset) and, in an interval with no snapshot interpolator, put a
        solver-placed label back to the raw applet offset — onto its line.

        A label first placed at a LATER keyframe only ever receives offsets
        from the interpolators, so it gets the snapshot's anchor and the
        auto-placed flag up front — otherwise the renderer reads the solver's
        offset as an applet labelOffset. ``indices`` limits the snapshots to
        those keyframes (a single-frame preview needs only its interval).

        Returns the per-keyframe layouts, or ``None`` when snapshots are off.
        """
        cfg = self.style_config.overlay.label_placement
        if not (cfg.get('enabled', False) and cfg.get('keyframe_snapshots', False)):
            return None
        layouts = self._compute_keyframe_label_layouts(seq, cfg, indices=indices)
        seq.attach_label_layouts(layouts)
        seq.drop_style_key('label_offset_px')
        flagged = set()
        for layout in layouts:
            for name, pl in (layout or {}).items():
                if name in flagged:
                    continue
                flagged.add(name)
                elem = self.geo.element(name)
                if elem is not None:
                    elem.style['label_anchor'] = pl.label_anchor
                    elem.style['_auto_placed'] = True
        return layouts

    def apply_keyframes_at(self, keyframes_data, t):
        """Statically place the scene at playhead time ``t`` (no animation) —
        for a single-frame preview (e.g. then exportSVG). Idempotent."""
        from .keyframes import KeyframeSequence
        seq = (KeyframeSequence.from_json(keyframes_data, self.geo)
               if isinstance(keyframes_data, dict) else keyframes_data)
        if seq.has_style_tracks():
            cs = self.style.rendering.get('color_interpolation', 'oklab')
            seq.bind_style_tracks(get_element=self.geo.element,
                                  resolve=self._style_track_baseline,
                                  color_space=cs)
        seq.bind_visibility(get_element=self.geo.element)
        kfs = seq.keyframes
        t = max(kfs[0].t, min(float(t), kfs[-1].t))
        # find interval containing t
        idx = 0
        for i, iv in enumerate(seq.intervals):
            if iv.start_t <= t <= iv.end_t:
                idx = i
                break
        interval = seq.intervals[idx]
        # Labels exactly as playback places them: the snapshots of this
        # interval's two keyframes, interpolated (only these two are computed).
        layouts = self._bind_label_snapshots(seq, indices={idx, idx + 1})
        self._apply_keyframe_state(kfs[idx], seq.element_info, update_scene=False)
        p = 0.0 if interval.duration <= 0 else (t - interval.start_t) / interval.duration
        touched = set()
        for interp in interval.interpolators:
            self._apply_interp_value(interp.name, interp.kind, interp.at(p))
            touched.add(interp.name)
        # apply visibility state at end-keyframe if p>=1 else start already set
        updates = self.geo.rebuild()
        for name in touched:
            updates[name] = updates.get(name, True)
        for name in self._apply_style_interps(interval, p):
            updates[name] = updates.get(name, True)
        if layouts is not None:
            from .label_placement import apply_label_layout, compute_angle_label_offset_px
            if layouts[idx]:
                apply_label_layout(self, layouts[idx], rerender=False)
                for name in layouts[idx]:
                    updates[name] = updates.get(name, True)
            for li in interval.label_interps:
                elem = self.geo.element(li.name)
                if elem is None or not self._element_visible(elem):
                    continue
                ox, oy = li.at(p)
                elem.style['label_offset_px'] = [float(ox), float(oy)]
                updates[li.name] = updates.get(li.name, True)
            ptUnit = _style_ptUnit(self.style)
            ptUnit_ggb = self.style.export.get('ptUnit_ggb', ptUnit)
            for name, ap in interval.dynamic_angle_params.items():
                elem = self.geo.element(name)
                if elem is None or not self._element_visible(elem):
                    continue
                elem.style['label_offset_px'] = list(
                    compute_angle_label_offset_px(elem.data, ap, ptUnit, ptUnit_ggb))
                updates[name] = updates.get(name, True)
        if interval.camera_interp:
            self._apply_camera(interval.camera_interp.at(p))
        self.updateGeoElements(updates)

    def reveal_construction(self, lag=0.3, duration=0.5, effect=None, play=True):
        """Stage a dependency-ordered, staggered reveal of the whole
        construction (GeoGebra Construction-Protocol style). Returns the
        generated v2 keyframes; plays them when ``play`` is True.
        """
        from .keyframes import build_reveal_keyframes
        from . import geo as _geo
        per_type = {
            _geo.Point: 'fade', _geo.Segment: 'create', _geo.Line: 'create',
            _geo.Ray: 'create', _geo.Vector: 'create', _geo.Circle: 'create',
            _geo.Arc: 'create', _geo.Polygon: 'fade', _geo.CircleSector: 'fade',
            _geo.Angle: 'fade', _geo.Text: 'write',
            _geo.Conic: 'create', _geo.Function: 'create', _geo.ImplicitCurve: 'create',
        }
        names, type_effects = [], {}
        for elem in self.geo.elements:
            if elem.name in ('xAxis', 'yAxis'):
                continue
            if self.CreateMObject(elem) is None:
                continue
            names.append(elem.name)
            if effect is None:
                type_effects[elem.name] = per_type.get(type(elem.data), 'create')
            else:
                type_effects[elem.name] = effect
        kfs = build_reveal_keyframes(names, type_effects, lag=lag,
                                     duration=duration,
                                     default_effect=effect or 'create')
        if play:
            self.play_keyframes(kfs)
        return kfs

    def _play_keyframe_interval(self, interval):
        """Animate a single keyframe interval using ValueTracker + sentinel updater.

        The updater lives on a sentinel Mobject (not on the animated tracker),
        because manim does not deliver intermediate values to updaters attached
        to the mobject being animated.

        Order within ``on_frame``: geometry rebuild first, then label offsets
        (so ``ang.side1/2/p`` are fresh when ``compute_angle_label_center`` runs).
        Label names are merged into the ``updates`` dict so a single
        ``updateGeoElements`` call rebuilds both geometry and labels.
        """
        from .label_placement import compute_angle_label_offset_px

        progress = ValueTracker(0)
        sentinel = Mobject()   # invisible carrier for the updater
        interps = interval.interpolators
        label_interps = interval.label_interps
        dynamic_angle_params = interval.dynamic_angle_params
        geo_ref = self.geo
        scene_ref = self

        ptUnit = _style_ptUnit(self.style)
        ptUnit_ggb = self.style.export.get('ptUnit_ggb', ptUnit)

        active_events = {}

        def on_frame(mob):
            t = progress.get_value()
            t_abs = t * interval.duration
            touched = set()
            for interp in interps:
                val = interp.at(t)
                scene_ref._apply_interp_value(interp.name, interp.kind, val)
                touched.add(interp.name)

            updates = geo_ref.rebuild()
            for name in touched:
                updates[name] = updates.get(name, True)

            for name in scene_ref._apply_style_interps(interval, t):
                updates[name] = updates.get(name, True)

            # Label offsets must be written AFTER geo.rebuild so that
            # ang.side1/2/p are up to date for compute_angle_label_center.
            for li in label_interps:
                elem = geo_ref.element(li.name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                ox, oy = li.at(t)
                elem.style['label_offset_px'] = [float(ox), float(oy)]
                updates[li.name] = updates.get(li.name, True)

            for name, ap in dynamic_angle_params.items():
                elem = geo_ref.element(name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                elem.style['label_offset_px'] = list(
                    compute_angle_label_offset_px(elem.data, ap, ptUnit, ptUnit_ggb)
                )
                updates[name] = updates.get(name, True)

            # Ensure emphasis-event targets are (re)rendered this frame so
            # the adapter always transforms a fresh mobject — otherwise a
            # target that isn't otherwise touched is never re-become'd, and
            # the transform (e.g. indicate's scale) compounds every frame
            # instead of self-restoring once the event window closes.
            for spec in interval.events:
                for _nm in spec.targets:
                    updates[_nm] = updates.get(_nm, True)

            scene_ref.updateGeoElements(updates)

            if interval.camera_interp:
                scene_ref._apply_camera(interval.camera_interp.at(t))

            # Emphasis events LAST — transform the freshly rebuilt mobjects.
            scene_ref._apply_events(interval, t_abs, active_events)

        sentinel.add_updater(on_frame)
        self.add(progress, sentinel)
        self.play(
            progress.animate(rate_func=linear).set_value(1),
            run_time=interval.duration,
        )
        sentinel.clear_updaters()
        self.remove(progress, sentinel)
        for m in list(active_events.values()):
            self.remove(m)

    def _play_keyframe_interval_v2(self, interval):
        """v2 interval playback: geometry + style + labels + enter/exit effects
        in one exact-duration play(). Entering elements are made present at the
        interval start (transparent until their effect starts); exiting elements
        are removed at the interval end.
        """
        from .label_placement import compute_angle_label_offset_px

        # Lifecycle: reveal entering elements now (present-but-faded); their
        # first-frame alpha keeps them invisible until the effect starts.
        for e in interval.enter_effects:
            elem = self.geo.element(e.name)
            if elem is not None:
                elem.visible = True
        entering = [e.name for e in interval.enter_effects]
        if entering:
            self.updateGeoElements(entering)

        progress = ValueTracker(0)
        sentinel = Mobject()
        interps = interval.interpolators
        label_interps = interval.label_interps
        dynamic_angle_params = interval.dynamic_angle_params
        enter_effects = interval.enter_effects
        exit_effects = interval.exit_effects
        duration = interval.duration
        geo_ref = self.geo
        scene_ref = self
        ptUnit = _style_ptUnit(self.style)
        ptUnit_ggb = self.style.export.get('ptUnit_ggb', ptUnit)
        active_events = {}

        def on_frame(mob):
            t = progress.get_value()
            t_abs = t * duration
            touched = set()
            for interp in interps:
                scene_ref._apply_interp_value(interp.name, interp.kind, interp.at(t))
                touched.add(interp.name)

            updates = geo_ref.rebuild()
            for name in touched:
                updates[name] = updates.get(name, True)
            for name in scene_ref._apply_style_interps(interval, t):
                updates[name] = updates.get(name, True)

            for li in label_interps:
                elem = geo_ref.element(li.name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                ox, oy = li.at(t)
                elem.style['label_offset_px'] = [float(ox), float(oy)]
                updates[li.name] = updates.get(li.name, True)
            for name, ap in dynamic_angle_params.items():
                elem = geo_ref.element(name)
                if elem is None or not scene_ref._element_visible(elem):
                    continue
                elem.style['label_offset_px'] = list(
                    compute_angle_label_offset_px(elem.data, ap, ptUnit, ptUnit_ggb))
                updates[name] = updates.get(name, True)

            # Ensure effect targets are (re)rendered this frame so the adapter
            # transforms a fresh full-opacity mobject.
            for e in enter_effects:
                updates[e.name] = updates.get(e.name, True)
            for e in exit_effects:
                updates[e.name] = updates.get(e.name, True)

            # Same for emphasis-event targets — otherwise a target that isn't
            # otherwise touched is never re-become'd, and the transform (e.g.
            # indicate's scale) compounds every frame instead of
            # self-restoring once the event window closes.
            for spec in interval.events:
                for _nm in spec.targets:
                    updates[_nm] = updates.get(_nm, True)

            scene_ref.updateGeoElements(updates)

            # Effects LAST — multiply over the freshly-become'd mobjects.
            for e in enter_effects:
                scene_ref._apply_effect_alpha(e.name, e.kind, scene_ref._effect_alpha(e, t_abs))
            for e in exit_effects:
                scene_ref._apply_effect_alpha(e.name, e.kind, scene_ref._effect_alpha(e, t_abs))

            if interval.camera_interp:
                scene_ref._apply_camera(interval.camera_interp.at(t))

            # Emphasis events LAST — transform the freshly rebuilt mobjects.
            scene_ref._apply_events(interval, t_abs, active_events)

        sentinel.add_updater(on_frame)
        self.add(progress, sentinel)
        self.play(progress.animate(rate_func=linear).set_value(1), run_time=duration)
        sentinel.clear_updaters()
        self.remove(progress, sentinel)
        for m in list(active_events.values()):
            self.remove(m)

        # Lifecycle end: hide + remove exited elements.
        for e in exit_effects:
            elem = self.geo.element(e.name)
            if elem is not None:
                elem.visible = False
            m = self.mobject(e.name)
            if m is not None:
                self.remove(m)

    def _effect_alpha(self, spec, t_abs):
        """Visible-fraction of an enter/exit effect at absolute interval time.

        1.0 = fully present, 0.0 = fully absent. 'in' ramps up, 'out' ramps down.
        """
        if spec.duration <= 0:
            raw = 1.0 if t_abs >= spec.start else 0.0
        else:
            raw = (t_abs - spec.start) / spec.duration
            raw = 0.0 if raw < 0 else (1.0 if raw > 1 else raw)
        return raw if spec.direction == 'in' else 1.0 - raw

    def _effect_fade(self, mobj, alpha):
        """Multiply every family member's stroke & fill opacity by *alpha*."""
        for sub in mobj.family_members_with_points():
            try:
                sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
            except Exception:
                pass
            try:
                sub.set_fill(opacity=sub.get_fill_opacity() * alpha)
            except Exception:
                pass

    def _effect_partial(self, mobj, alpha):
        """Progressive stroke reveal (manim Create semantics): draw only the
        first *alpha* fraction of each stroke sub-mobject; fade filled parts.
        """
        alpha = 0.0 if alpha < 0 else (1.0 if alpha > 1 else alpha)
        for sub in mobj.family_members_with_points():
            has_fill = getattr(sub, 'get_fill_opacity', lambda: 0)() > 0
            if has_fill:
                # Filled sub-mobject: fade it in rather than partial-draw.
                try:
                    sub.set_fill(opacity=sub.get_fill_opacity() * alpha)
                    sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
                except Exception:
                    pass
                continue
            try:
                full = sub.copy()
                sub.pointwise_become_partial(full, 0, alpha)
            except Exception:
                # Fallback: fade if partial draw isn't supported for this sub.
                try:
                    sub.set_stroke(opacity=sub.get_stroke_opacity() * alpha)
                except Exception:
                    pass

    def _effect_scale(self, mobj, alpha):
        """Grow-from / shrink-to the element's own centre by *alpha*.

        Element mobjects are ``VGroup([geometry…, label])``. Scaling the whole
        group about its bbox centre pulled a labelled point towards its label,
        so the dot slid into place while growing. Scale the geometry about the
        geometry's centre; the label stays where it stands and fades instead.
        """
        factor = max(float(alpha), 1e-3)
        parts = list(getattr(mobj, 'submobjects', None) or [])
        labels = [p for p in parts if getattr(p, '_animageo_is_label', False)]
        if not labels:
            try:
                mobj.scale(factor, about_point=mobj.get_center())
            except Exception:
                pass
            return
        geometry = [p for p in parts if not getattr(p, '_animageo_is_label', False)]
        if geometry:
            try:
                center = VGroup(*geometry).get_center()
                for part in geometry:
                    part.scale(factor, about_point=center)
            except Exception:
                pass
        for label in labels:
            self._effect_fade(label, alpha)

    def _effect_write(self, mobj, alpha):
        """Progressive glyph reveal (manim Write/AddTextLetterByLetter): show
        the first ``alpha`` fraction of the glyph leaves, hide the rest.
        Operates on leaf VMobjects (a Tex/label's glyphs live below its
        top-level submobject), so it is genuinely progressive for real
        single-Tex labels, not all-or-nothing. Falls back to a plain fade for
        a mobject with no glyph substructure.
        """
        alpha = 0.0 if alpha < 0 else (1.0 if alpha > 1 else alpha)
        leaves = list(mobj.family_members_with_points())
        if not leaves:
            self._effect_fade(mobj, alpha)
            return
        n = len(leaves)
        show = int(round(alpha * n))
        for i, leaf in enumerate(leaves):
            self._effect_fade(leaf, 1.0 if i < show else 0.0)

    def _apply_effect_alpha(self, name, kind, alpha):
        """Transform the current mobject for *name* by *alpha* per effect *kind*.

        Phase-2 Task 3 implements 'fade'/'none'; Task 4 adds 'create'/
        'uncreate' (progressive stroke draw); Task 5 adds 'grow'/'shrink'
        (scale about center). Phase-3 Task 2 adds 'write' (progressive
        glyph reveal, enter-only).
        """
        mobj = self.mobject(name)
        if mobj is None:
            return
        if kind == 'none':
            # step visibility: fully shown iff alpha >= 1 (in) / > 0 (already
            # handled by _effect_alpha stepping); hide when alpha == 0.
            if alpha <= 0:
                self._effect_fade(mobj, 0.0)
            return
        if kind in ('create', 'uncreate'):
            self._effect_partial(mobj, alpha)
            return
        if kind in ('grow', 'shrink'):
            self._effect_scale(mobj, alpha)
            return
        if kind == 'write':
            self._effect_write(mobj, alpha)
            return
        # 'fade' and (for now) any not-yet-implemented kind
        self._effect_fade(mobj, alpha)

    def _event_envelope(self, spec, t_abs):
        """There-and-back bump in [0, 1] for one ``EventSpec`` window.

        0.0 at both edges of ``[spec.start, spec.start + spec.duration]``,
        1.0 at the midpoint (``sin(pi * local)``), and EXACTLY 0.0 outside
        the window — this is what makes emphasis events self-restoring:
        once the interval's absolute time passes the window, no transform
        is applied at all and the mobject renders at its normal geometry.
        """
        if spec.duration <= 0:
            return 0.0
        local = (t_abs - spec.start) / spec.duration
        if local < 0.0 or local > 1.0:
            return 0.0
        return math.sin(math.pi * local)

    def _event_indicate(self, mobj, env, spec):
        """Scale *mobj* about its center by ``1 + (spec.scale - 1) * env`` and
        nudge its stroke/fill colour toward ``spec.color`` by ``env``.

        At ``env <= 0`` this is a strict no-op (identity) so the mobject is
        left exactly as ``updateGeoElements`` rendered it — the self-restoring
        half of the indicate pulse.
        """
        if env <= 0 or mobj is None:
            return
        factor = 1.0 + (spec.scale - 1.0) * env
        try:
            mobj.scale(factor, about_point=mobj.get_center())
        except Exception:
            pass
        col = spec.color or '#ff8800'
        try:
            from .style.colorspace import lerp_color
            for sub in mobj.family_members_with_points():
                try:
                    if sub.get_stroke_opacity() > 0:
                        cur = sub.get_stroke_color().to_hex()
                        sub.set_stroke(color=lerp_color(cur, col, env))
                except Exception:
                    pass
                try:
                    if sub.get_fill_opacity() > 0:
                        cur_fill = sub.get_fill_color().to_hex()
                        sub.set_fill(color=lerp_color(cur_fill, col, env))
                except Exception:
                    pass
        except Exception:
            pass

    def _make_event_overlay(self, spec, target):
        """Build the temp decoration mobject for a flash/circumscribe event
        from *target*'s current geometry (centre / bounding box).

        Returns ``None`` if construction fails for any reason (degenerate
        target, zero-size bbox, ...) — the caller then simply skips adding
        an overlay this frame instead of crashing.
        """
        try:
            center = target.get_center()
            width = float(target.width)
            height = float(target.height)
            if not math.isfinite(width) or width <= 0:
                width = 0.2
            if not math.isfinite(height) or height <= 0:
                height = 0.2

            if spec.effect == 'flash':
                color = spec.color or '#ffcc00'
                radius = max(width, height) / 2.0
                flash_radius = radius + 0.05
                line_length = max(radius * 0.6, 0.1)
                num_lines = 12
                lines = VGroup()
                for i in range(num_lines):
                    angle = i * (2 * math.pi / num_lines)
                    line = Line(center, center + line_length * RIGHT)
                    line.shift(flash_radius * RIGHT)
                    line.rotate(angle, about_point=center)
                    lines.add(line)
                lines.set_stroke(color=color, width=3, opacity=1.0)
                lines.set_z_index(60)
                return lines

            if spec.effect == 'circumscribe':
                color = spec.color or '#ff8800'
                pad = 0.15
                rect = Rectangle(
                    width=width + 2 * pad, height=height + 2 * pad,
                    color=color, fill_opacity=0.0,
                    stroke_opacity=1.0, stroke_width=3,
                )
                rect.move_to(center)
                rect.set_z_index(60)
                return rect
        except Exception:
            return None
        return None

    def _event_additive(self, spec, env, t_abs, active):
        """Additive (overlay) emphasis events: ``flash`` / ``circumscribe``.

        Unlike ``_event_indicate`` (which transforms the target's own
        mobject in place, self-restoring because ``updateGeoElements``
        re-``become()``s it every frame), these effects add a NEW temp
        decoration mobject on top of the target and fade it in/out with
        the envelope bump (see ``_event_envelope``) — it persists across
        frames on its own, so it must be explicitly removed once the
        window closes to keep the scene byte-identical to the no-event
        case.

        Keyed by ``id(spec)`` (unique per event/interval, stable across
        the whole window) rather than target name, so two concurrent
        events on the same target can't collide.

        Never touches ``elem.style``, the target mobject, or construction
        state — only creates/updates/removes its own overlay mobject.
        """
        key = id(spec)
        temp = active.get(key)

        if env <= 0:
            if temp is not None:
                try:
                    self.remove(temp)
                except Exception:
                    pass
                active.pop(key, None)
            return

        if temp is None:
            if not spec.targets:
                return
            target = self.mobject(spec.targets[0])
            if target is None:
                return
            temp = self._make_event_overlay(spec, target)
            if temp is None:
                return
            try:
                self.add(temp)
            except Exception:
                return
            active[key] = temp

        try:
            temp.set_stroke(opacity=env)
        except Exception:
            pass
        try:
            if temp.get_fill_opacity() > 0:
                temp.set_fill(opacity=env)
        except Exception:
            pass

    def _apply_events(self, interval, t_abs, active):
        """Apply every ``EventSpec`` in *interval* at absolute time *t_abs*.

        Must run LAST in the frame loop (after ``updateGeoElements`` and
        after visibility/enter-exit effects) so it transforms the freshly
        rebuilt mobject. Never writes ``elem.style`` or construction state —
        only mutates the live mobject, which is why the effect vanishes on
        its own once the event window (see ``_event_envelope``) closes.
        """
        for spec in getattr(interval, 'events', []):
            env = self._event_envelope(spec, t_abs)
            if spec.effect == 'indicate':
                for name in spec.targets:
                    self._event_indicate(self.mobject(name), env, spec)
            else:
                self._event_additive(spec, env, t_abs, active)   # Task 3

    def _apply_style_interps(self, interval, t):
        """Write interpolated style-track values for *interval* at progress t.

        Returns the set of touched element names (callers merge it into the
        ``updateGeoElements`` updates dict).
        """
        touched = set()
        for si in interval.style_interps:
            elem = self.geo.element(si.name)
            if elem is None:
                continue
            elem.style[si.key] = si.at(t)
            touched.add(si.name)
        return touched

    def _finalize_style_interval(self, interval):
        """Pin exact end-of-interval style values and run null-reverts.

        'set' writes the exact target value (deterministic end state even if
        the last updater frame landed slightly before t=1); 'revert' restores
        the element's pre-animation ``elem.style`` entry, deleting the key if
        there was none (the resolver then falls back to overlay/defaults —
        visually identical to the interpolated baseline target).
        """
        touched = set()
        for fin in interval.style_finalizers:
            op, name, key = fin[0], fin[1], fin[2]
            elem = self.geo.element(name)
            if elem is None:
                continue
            if op == 'set':
                elem.style[key] = fin[3]
            else:   # 'revert'
                had_explicit, explicit_val = fin[3], fin[4]
                if had_explicit:
                    elem.style[key] = explicit_val
                elif key in elem.style:
                    del elem.style[key]
            touched.add(name)
        if touched:
            self.updateGeoElements(touched)

    def _export_cairo(self, filepath, *, surface, dpi, label):
        """Write the current frame to a cairo vector ``surface``.

        Shared by ``exportSVG`` / ``exportPDF`` / ``exportEPS``: identical
        mobject walk, differing only in the cairo surface kind and (for
        PDF/EPS) the px→pt scale governed by ``dpi``.
        """
        if filepath is None:
            fd, filepath = tempfile.mkstemp(suffix="." + surface)
            os.close(fd)
        filepath = os.path.abspath(filepath)
        logger.info("Exporting %s to %s", label, filepath)

        if surface == "eps":
            self._warn_eps_transparency()

        with _get_cairo_context(filepath, self.style, surface=surface, dpi=dpi) as ctx:
            for mobj in extract_mobject_family_members(self.mobjects, True, True):
                if isinstance(mobj, ValueTracker): continue
                _create_svg_from_vmobject_internal(mobj, ctx, style = self.style)
        try:
            size = os.path.getsize(filepath)
            logger.info("%s exported: %s (%d bytes)", label, filepath, size)
        except OSError:
            logger.info("%s exported: %s", label, filepath)
        return filepath

    def _warn_eps_transparency(self):
        """Warn once if the scene has semi-transparent elements.

        EPS has no native transparency; cairo flattens/rasterises any
        ``0 < opacity < 1`` fill or stroke, which bloats the file and softens
        edges. PDF and SVG preserve opacity.
        """
        try:
            for elem in self.geo.elements:
                if not self._element_visible(elem):
                    continue
                for key in ("fill_opacity", "stroke_opacity"):
                    op = _resolve_style(self, elem, key, default=1.0)
                    if op is not None and 0.0 < float(op) < 1.0:
                        logger.warning(
                            "EPS has no transparency: semi-transparent elements "
                            "(e.g. '%s' %s=%.2f) will be flattened/rasterised. "
                            "Use PDF or SVG to preserve opacity.",
                            getattr(elem, "name", "?"), key, float(op),
                        )
                        return
        except Exception:
            pass

    def exportSVG(self, filepath):
        return self._export_cairo(filepath, surface="svg", dpi=96.0, label="SVG")

    def exportPDF(self, filepath, *, dpi=96.0):
        """Export the current frame as a vector PDF (single page).

        Args:
            filepath: Output ``.pdf`` path.
            dpi: Pixels-per-inch governing the physical page size. The default
                (96) reproduces the on-screen SVG size; the figure stays vector
                and is rescaled by ``\\includegraphics[width=...]`` in LaTeX.
        """
        return self._export_cairo(filepath, surface="pdf", dpi=dpi, label="PDF")

    def exportEPS(self, filepath, *, dpi=96.0):
        """Export the current frame as vector EPS (Encapsulated PostScript).

        EPS is preferred by some journals/LaTeX workflows. Note: EPS has no
        transparency — semi-transparent fills are flattened (a warning is
        logged). Use ``exportPDF`` to preserve opacity.
        """
        return self._export_cairo(filepath, surface="eps", dpi=dpi, label="EPS")

    def exportTikZ(self, filepath=None, *, standalone=False, options=None, **kwargs):
        """Export the construction as TikZ for inclusion in a LaTeX document.

        Produces semantic, editable TikZ: native ``\\draw circle`` / ``ellipse``
        / ``(a)--(b)`` / ``arc`` primitives, real LaTeX ``\\node`` labels, and
        ``\\draw plot coordinates`` for sampled curves (parabola/hyperbola/
        function/implicit/locus). Coordinates are math units; the picture's
        ``x=/y=`` unit reproduces the SVG physical size.

        Args:
            filepath: Optional ``.tex`` output path. The TikZ string is always
                returned.
            standalone: Wrap the picture in a compilable
                ``\\documentclass{standalone}`` document (Cyrillic-ready
                preamble). Default emits a bare ``tikzpicture`` snippet for
                ``\\input{}``.
            options: A ``TikZOptions`` instance. When given, ``**kwargs`` and
                ``standalone`` must not be passed.
            **kwargs: Forwarded to ``TikZOptions`` (e.g. ``dpi``, ``clip``,
                ``background``, ``emit_font_size``).

        Returns:
            The generated TikZ text.
        """
        from .exporters.tikz import export_tikz, TikZOptions
        logger.info("Exporting TikZ to %s", filepath)
        if options is not None:
            if kwargs or standalone:
                raise TypeError("pass either `options=` or keyword options, not both")
            return export_tikz(self, filepath, options=options)
        return export_tikz(self, filepath, options=TikZOptions(standalone=standalone, **kwargs))

    def exportJSXGraph(self, filepath=None, *, options=None, **kwargs):
        """Export the construction as an interactive JSXGraph board.

        Transpiles the *construction graph* (not the rendered frame): free
        points become draggable points, points-on-curves become gliders,
        numbers become sliders, and derived elements are created in terms of
        their parents so JSXGraph recomputes them live on drag. Commands with no
        native JSXGraph creator fall back to static geometry and are listed in a
        coverage report (logged at INFO).

        Args:
            filepath: Optional output path (``.html`` / ``.js`` / ``.json``);
                the text is always returned.
            options: A ``JSXGraphOptions`` instance. When given, ``**kwargs``
                must not be passed.
            **kwargs: Forwarded to ``JSXGraphOptions`` (e.g. ``output="js"``,
                ``mathjax=False``, ``axis=False``).

        Returns:
            The generated HTML / JS / JSON text.
        """
        from .exporters.jsxgraph import export_jsxgraph, JSXGraphOptions
        logger.info("Exporting JSXGraph to %s", filepath)
        if options is not None:
            if kwargs:
                raise TypeError("pass either `options=` or keyword options, not both")
            return export_jsxgraph(self, filepath, options=options)
        return export_jsxgraph(self, filepath, options=JSXGraphOptions(**kwargs))

    def exportStylePromptSummary(self, filepath=None, **kwargs):
        """Export a compact construction summary for AI style generation.

        The summary is versioned as ``animageo-construction-summary/v1`` and
        contains element names, canonical types, compact geometry, visibility,
        selected ``ggb_style`` keys, optional explicit/resolved style layers,
        and parser diagnostics. It deliberately omits raw ``.ggb`` XML.

        Args:
            filepath: optional JSON output path. If omitted, only returns the
                summary dict.
            **kwargs: forwarded to
                :func:`animageo.exporters.construction_summary.construction_to_ai_summary`.

        Returns:
            The summary dict.
        """
        from .exporters.construction_summary import (
            construction_to_ai_summary,
            write_ai_summary,
        )
        from .style.resolver import resolved_style

        viewport = kwargs.pop('viewport', None)
        if viewport is None:
            export = getattr(self.style, 'export', {}) or {}
            viewport = {
                'size': [
                    export.get('ptWidth'),
                    export.get('ptHeight'),
                ],
                'ptUnit': export.get('ptUnit'),
                'ptUnit_style': export.get('ptUnit_style'),
                'ptUnit_ggb': export.get('ptUnit_ggb'),
                'ptXZero': export.get('ptXZero'),
                'ptYZero': export.get('ptYZero'),
                'reference_size': [
                    export.get('referenceWidth'),
                    export.get('referenceHeight'),
                ],
                'contentScale': export.get('contentScale'),
                'fontSize': export.get('fontSize'),
            }

        source = kwargs.pop('source', None) or getattr(self, '_construction_source', None)
        kwargs.setdefault('resolved_style_fn', lambda elem: resolved_style(self, elem))

        if filepath is None:
            return construction_to_ai_summary(
                self.geo,
                source=source,
                viewport=viewport,
                **kwargs,
            )
        return write_ai_summary(
            self.geo,
            filepath,
            source=source,
            viewport=viewport,
            **kwargs,
        )
    
    def addGrid(self, x_range=(-10, 10, 1), y_range=(-10, 10, 1)):
        grid = NumberPlane(
            x_range = x_range,
            y_range = y_range,
            x_length = x_range[1] - x_range[0],
            y_length = y_range[1] - y_range[0],
            background_line_style = {
                "stroke_color": BLACK,
                "stroke_width": stroke_width_to_manim(
                    self.style_config.defaults.get('line', 'stroke_width_px', 1),
                    _style_ptUnit(self.style),
                ),
                "stroke_opacity": 0.1
            },
            x_axis_config = {"stroke_opacity": 0},
            y_axis_config = {"stroke_opacity": 0}
        )

        self.add(grid.shift(-grid.get_origin()))
        return grid

    def addCoordinateBackground(self):
        """Render imported GeoGebra grid/axes as a quiet background layer."""
        export = self.style.export
        if not (export.get('showGrid') or export.get('showAxes')):
            return None

        old = self.mobject('_coordinate_background')
        if old is not None:
            self.remove(old)

        bounds = self._get_scene_bounds(padding=0)
        left, bottom, right, top = bounds
        ptUnit = _style_ptUnit(self.style)

        grid_color = export.get('gridColor', '#c0c0c0')
        axes_color = export.get('axesColor', '#252525')
        grid_width = 0.65 if not export.get('gridIsBold') else 0.9
        axis_width = 1.25
        x_grid_step = float(export.get('gridDistX') or export.get('gridStep', 1) or 1)
        y_grid_step = float(export.get('gridDistY') or export.get('gridStep', 1) or 1)
        if x_grid_step <= 0:
            x_grid_step = 1.0
        if y_grid_step <= 0:
            y_grid_step = 1.0

        group = VGroup(name='_coordinate_background')

        def values_between(lo, hi, step):
            first = np.ceil(lo / step) * step
            last = np.floor(hi / step) * step
            if first > last:
                return []
            count = int(round((last - first) / step)) + 1
            if count > 1000:
                step *= np.ceil(count / 1000)
                first = np.ceil(lo / step) * step
                last = np.floor(hi / step) * step
                count = int(round((last - first) / step)) + 1
            return [first + i * step for i in range(max(count, 0))]

        axes = export.get('axes') or {}
        def axis_visible(axis_key):
            value = (axes.get(axis_key) or {}).get('show')
            return bool(export.get('showAxes') if value is None else value)

        show_x_axis = axis_visible('x')
        show_y_axis = axis_visible('y')

        if export.get('showGrid'):
            for x in values_between(left, right, x_grid_step):
                if show_y_axis and np.isclose(x, 0):
                    continue
                group.add(Line(
                    [x, bottom, 0], [x, top, 0],
                    color=grid_color,
                    stroke_width=stroke_width_to_manim(grid_width, ptUnit),
                    stroke_opacity=0.38,
                ).set_z_index(-20))
            for y in values_between(bottom, top, y_grid_step):
                if show_x_axis and np.isclose(y, 0):
                    continue
                group.add(Line(
                    [left, y, 0], [right, y, 0],
                    color=grid_color,
                    stroke_width=stroke_width_to_manim(grid_width, ptUnit),
                    stroke_opacity=0.38,
                ).set_z_index(-20))

        def add_axis_numbers(axis_key, values, line_coord, horizontal=True):
            axis_cfg = axes.get(axis_key) or {}
            if axis_cfg.get('showNumbers') is False:
                return
            step = x_grid_step if axis_key == 'x' else y_grid_step
            if len(values) > 40 or ptUnit * step < 24:
                return
            font_size = 10 * GGB_FONT_SCALE / ptUnit
            offset = 10 / ptUnit
            for value in values:
                if np.isclose(value, 0):
                    continue
                text = str(int(round(value))) if np.isclose(value, round(value)) else f"{value:.2f}".rstrip('0').rstrip('.')
                label = Text(text, font_size=font_size, color=axes_color)
                label.set_opacity(0.72)
                if horizontal:
                    label.move_to([value, line_coord - offset, 0])
                else:
                    label.move_to([line_coord - offset, value, 0])
                    label.shift(LEFT * label.width / 2)
                group.add(label.set_z_index(-9))

        if export.get('showAxes'):
            tick = 4 / ptUnit
            x_tick_step = float((axes.get('x') or {}).get('tickDistance') or x_grid_step)
            y_tick_step = float((axes.get('y') or {}).get('tickDistance') or y_grid_step)
            if x_tick_step <= 0:
                x_tick_step = x_grid_step
            if y_tick_step <= 0:
                y_tick_step = y_grid_step
            x_values = values_between(left, right, x_tick_step)
            y_values = values_between(bottom, top, y_tick_step)
            if show_x_axis and bottom <= 0 <= top:
                group.add(Line(
                    [left, 0, 0], [right, 0, 0],
                    color=axes_color,
                    stroke_width=stroke_width_to_manim(axis_width, ptUnit),
                    stroke_opacity=0.82,
                ).set_z_index(-10))
                for x in x_values:
                    if np.isclose(x, 0):
                        continue
                    group.add(Line(
                        [x, -tick, 0], [x, tick, 0],
                        color=axes_color,
                        stroke_width=stroke_width_to_manim(0.75, ptUnit),
                        stroke_opacity=0.58,
                    ).set_z_index(-9))
                add_axis_numbers('x', x_values, 0, horizontal=True)

            if show_y_axis and left <= 0 <= right:
                group.add(Line(
                    [0, bottom, 0], [0, top, 0],
                    color=axes_color,
                    stroke_width=stroke_width_to_manim(axis_width, ptUnit),
                    stroke_opacity=0.82,
                ).set_z_index(-10))
                for y in y_values:
                    if np.isclose(y, 0):
                        continue
                    group.add(Line(
                        [-tick, y, 0], [tick, y, 0],
                        color=axes_color,
                        stroke_width=stroke_width_to_manim(0.75, ptUnit),
                        stroke_opacity=0.58,
                    ).set_z_index(-9))
                add_axis_numbers('y', y_values, 0, horizontal=False)

        if len(group) == 0:
            return None
        self.add(group)
        return group
    
    def _get_scene_bounds(self, padding=0.1):
        """Return (left, bottom, right, top) of the current camera viewport in
        scene coordinates.

        Used by Line/Ray clipping to compute endpoints that safely extend
        beyond the visible area. ``padding`` (scene units) is added on each
        side so the stroke's cap never lands on the frame edge. Reads from
        ``self.camera.frame`` (set up by ``applyStyle``), so the bounds
        always reflect the active export size and zero offset.
        """
        frame = self.camera.frame
        return (
            frame.get_left()[0] - padding,
            frame.get_bottom()[1] - padding,
            frame.get_right()[0] + padding,
            frame.get_top()[1] + padding,
        )

    def _getAngRadius(self, ang: geo.Angle):
        r = self.style.ang_rdefault / _style_ptUnit(self.style)
        max_r = min(np.linalg.norm(ang.side1), np.linalg.norm(ang.side2)) * 0.65
        if ang.size > 0.01:
            return min(max_r, r / ang.size**0.25)
        else:
            return min(max_r, r / 0.01**0.25)
 
    def _getRightAngSize(self, ang: geo.Angle):
        r = self.style.ang_right / _style_ptUnit(self.style)
        max_r = min(np.linalg.norm(ang.side1), np.linalg.norm(ang.side2)) * 0.65
        return min(max_r, r)

    # ── CreateMObject helpers ─────────────────────────────────────────

    def _build_render_ctx(self, elem, z_auto):
        """Compute per-element render context: colours, opacities, stroke
        width, label properties, z-index. Called once per ``CreateMObject``;
        values are then read by type-specific ``_render_<type>`` methods.
        """
        style = self.style
        ptUnit = style.export['ptUnit']
        ptUnit_style = _style_ptUnit(style)
        ptUnit_ggb = style.export.get('ptUnit_ggb', ptUnit_style)

        # Colours / opacities through the resolver (elem.style -> overlay ->
        # defaults). Fallback `default=` covers types/keys not yet fully
        # described in builtin defaults.
        stroke_default = str(style.strong)
        fill_default = str(style.strong if type(elem.data) == geo.Point else style.background)
        col_s = ManimColor(_resolve_style(self, elem, 'stroke', default=stroke_default))
        col_f = ManimColor(_resolve_style(self, elem, 'fill', default=fill_default))
        op_s = _resolve_style(self, elem, 'stroke_opacity', default=1)
        op_f = _resolve_style(self, elem, 'fill_opacity', default=1)
        col_label = ManimColor(_resolve_style(self, elem, 'label_color', default=str(style.strong)))

        # Stroke width and all visual sizes below are canonical pixel-unit
        # fields resolved from StyleConfig + GGB import + overlay + explicit
        # elem.style. Scene-level GeoStyle fields are import-time context only
        # and are not a render-time fallback.
        lw = _resolve_style(self, elem, 'stroke_width_px', default=1.0)
        lw = stroke_width_to_manim(lw, ptUnit_style)

        fs_px = _resolve_style(self, elem, 'font_size_px', default=14.0)
        font_size = fs_px * GGB_FONT_SCALE / ptUnit_style
        label_anchor = _resolve_style(
            self, elem, 'label_anchor',
            default=style.rendering.get('label_anchor'),
        )
        ggb_font_px = self.style.export.get('fontSize')
        has_label = (_resolve_style(self, elem, 'label_visible', default=False) is True)
        label_spec = resolve_label_spec(self, elem) if has_label else None
        label_text = label_spec.text if label_spec is not None else resolve_label_text(self, elem)
        label_dynamic = (
            has_label
            and self._value_labels_fast()
            and getattr(self, '_value_labels_dynamic', False)
            and label_spec is not None
            and label_spec.has_dynamic_value
        )
        label_offset_px = _resolve_style(self, elem, 'label_offset_px', default=None)
        auto_placed = bool(elem.style.get('_auto_placed'))
        lr_px = _resolve_style(self, elem, 'label_radial_offset_px', default=0.0)
        label_roff = float(lr_px) / ptUnit_style

        # GGB-faithful placement of imported manual labels: the applet starts
        # each label from a per-type
        # base point (label_anchor.py — one rule table for every type it can
        # reproduce), left edge on the baseline, then adds the stored
        # labelOffset. Applies only when neither the placement solver
        # (_auto_placed) nor an explicit per-element/overlay/defaults anchor
        # took over; the style-wide rendering.label_anchor is an aesthetic
        # default and deliberately does NOT reach these labels (it enters
        # ctx.label_anchor via `default=` above, so resolving with
        # default=None isolates the explicit layers).
        ggb_manual_base_px = None
        ggb_label_point = None
        ggb_label_attach = None
        if has_label and not auto_placed:
            ggb_raw = getattr(elem, 'ggb_raw', None) or {}
            explicit_anchor = _resolve_style(self, elem, 'label_anchor', default=None)
            if ggb_raw and explicit_anchor is None:
                from .label_anchor import ggb_label_anchor, nearest_point
                spot = ggb_label_anchor(elem, self.geo, ptUnit_ggb=ptUnit_ggb)
                if spot is not None:
                    ggb_label_point, ggb_manual_base_px = spot
                    # where on the element the label sits scales with the figure
                    ggb_label_attach = (
                        lambda xy, _elem=elem: nearest_point(_elem, xy, self.geo))

        # Dash: ratio + period in style px (animageo/dash.py). Like every other
        # decoration the period becomes MU through ptUnit_style, so it follows
        # the style prominence, not the zoom of the geometry.
        dash = dash_ratio(_resolve_style(self, elem, 'stroke_dash_ratio', default=None))
        dash_px = element_dash_px(self, elem) if dash is not None else None
        cap = _resolve_style(
            self, elem, 'stroke_linecap',
            default=style.rendering.get('line_cap', 'butt'),
        )
        ra_joint = _resolve_style(
            self, elem, 'right_angle_joint',
            default=style.rendering.get('right_angle_joint', 'auto'),
        )

        # Decoration geometry (tick length/shift, vector arrows) uses scene
        # coordinates, so pixel values become MU via /ptUnit_style. Tick width is
        # different: it is passed to Manim's stroke_width/set_stroke(width=...),
        # the same render-unit system as stroke_width_px.
        def _px(elem_key, fallback_px=0.0):
            return float(_resolve_style(self, elem, elem_key, default=fallback_px) or 0.0) / ptUnit_style

        strich_len_mu    = _px('tick_length_px')
        tick_width_px    = _resolve_style(self, elem, 'tick_width_px', default=0.0)
        strich_width     = stroke_width_to_manim(tick_width_px or 0.0, ptUnit_style)
        strich_rshift_mu = _px('tick_shift_px')
        arrow_w_mu       = _px('arrow_width_px')
        arrow_h_mu       = _px('arrow_length_px')

        tick_count = int(_resolve_style(self, elem, 'tick_count', default=0) or 0)
        tick_style = _resolve_style(self, elem, 'tick_style', default='line')
        tick_radius_px = _resolve_style(self, elem, 'tick_radius_px', default=None)
        angle_range = _resolve_style(self, elem, 'angle_range', default='minor') or 'minor'
        arc_shift_px = _resolve_style(self, elem, 'arc_shift_px', default=0.0)
        right_angle_marker = _resolve_style(self, elem, 'right_angle_marker', default=None)
        auto_radius = _resolve_style(self, elem, 'auto_radius', default=True)

        zz = _resolve_style(self, elem, 'z_index', default=None)
        zz_fill = _resolve_style(self, elem, 'z_index_fill', default=Z_FILL)
        if zz is None and z_auto:
            zz = _Z_AUTO_BY_TYPE.get(type(elem.data))
        if zz is None:
            zz = Z_FILL

        try:
            elem_order = self.geo.elements.index(elem)
        except ValueError:
            elem_order = 0
        z_tie = elem_order * _Z_ORDER_EPSILON

        def _ordered_z(value):
            try:
                return float(value) + z_tie
            except (TypeError, ValueError):
                return value

        zz_label = Z_FILL_LABEL if zz == Z_FILL else Z_LABEL
        zz = _ordered_z(zz)
        zz_fill = _ordered_z(zz_fill)
        zz_stroke = Z_STROKE + z_tie
        zz_label = zz_label + z_tie

        return SimpleNamespace(
            style=style,
            ptUnit=ptUnit, ptUnit_style=ptUnit_style, ptUnit_ggb=ptUnit_ggb,
            col_s=col_s, col_f=col_f,
            op_s=op_s, op_f=op_f,
            col_label=col_label,
            lw=lw,
            font_size=font_size,
            label_anchor=label_anchor,
            label_text=label_text,
            label_offset_px=label_offset_px,
            auto_placed=auto_placed,
            ggb_manual_base_px=ggb_manual_base_px,
            ggb_label_point=ggb_label_point,
            ggb_label_attach=ggb_label_attach,
            ggb_font_px=ggb_font_px,
            has_label=has_label,
            label_spec=label_spec,
            label_dynamic=label_dynamic,
            label_roff=label_roff,
            strich_len=strich_len_mu,
            strich_width=strich_width,
            strich_rshift=strich_rshift_mu,
            arrow_width=arrow_w_mu,
            arrow_height=arrow_h_mu,
            tick_count=tick_count,
            tick_style=tick_style,
            tick_radius_px=tick_radius_px,
            angle_range=angle_range,
            arc_shift_px=arc_shift_px,
            right_angle_marker=right_angle_marker,
            auto_radius=auto_radius,
            dash=dash, dash_px=dash_px, cap=cap, ra_joint=ra_joint,
            zz=zz, zz_fill=zz_fill,
            zz_stroke=zz_stroke, zz_label=zz_label,
        )

    def _renderer_for(self, elem):
        """Look up ``_render_<typename>`` on self, or None if no renderer."""
        return getattr(self, '_render_' + type(elem.data).__name__.lower(), None)

    def _dash_stroke(self, vm, ctx, fit='none', *, phase_mu=0.0):
        """Attach the element's dash pattern (``ctx.dash_px``) to stroke ``vm``.

        The stroke stays one path; the pattern is fixed here in MU, so Create /
        partial reveals uncover finished dashes. ``fit``: ``'ends'`` — open
        path of finite length, a dash on both ends; ``'closed'`` — a whole
        number of periods, no seam; ``'none'`` — the nominal pattern from the
        path start (lines clipped by the viewport, sampled curves). Round and
        square caps lengthen every dash by the line width; ``dash_pattern``
        shortens the drawn dash so the visible one stays nominal.
        """
        if not ctx.dash_px:
            return vm
        on_px, off_px = ctx.dash_px
        cap_extent = 0.0
        if getattr(vm, 'cap_style', None) in (CapStyleType.ROUND, CapStyleType.SQUARE):
            cap_extent = vm.get_stroke_width() * CAIRO_LINE_WIDTH_MULTIPLE
        length = path_length(vm.points) if fit != 'none' else 0.0
        set_dash(vm, dash_pattern(
            length, on_px / ctx.ptUnit_style, off_px / ctx.ptUnit_style,
            closed=(fit == 'closed'), fit_ends=(fit == 'ends'),
            cap_extent_mu=cap_extent, phase_mu=phase_mu,
        ))
        return vm

    def _curve_polyline(self, pts, ctx):
        """Stroke-only VMobject through ``pts`` (sampled curves), dashed when
        the element is: closed polylines get whole periods, open ones the
        nominal pattern."""
        pts_3d = [[float(p[0]), float(p[1]), 0] for p in pts]
        vm = VMobject(
            color=ctx.col_s, stroke_opacity=ctx.op_s,
            stroke_width=ctx.lw, fill_opacity=0,
        )
        vm.set_points_as_corners(pts_3d)
        vm.set_z_index(ctx.zz)
        closed = len(pts_3d) > 2 and np.allclose(pts_3d[0], pts_3d[-1])
        return self._dash_stroke(vm, ctx, 'closed' if closed else 'none')

    def _value_labels_fast(self):
        """Master switch for DecimalNumber-backed value labels (default on)."""
        rendering = getattr(self.style_config, 'rendering', None)
        if isinstance(rendering, dict):
            return rendering.get('fast_value_labels', True) is not False
        return True

    def _append_label(self, arr, elem, pos, ctx):
        """Append the element's label to its mobject list, if one could be built.

        ``_make_label`` returns None when the label's LaTeX cannot be compiled
        even as plain text; the element is then drawn without it instead of
        being dropped entirely.
        """
        label = self._make_label(elem, pos, ctx)
        if label is not None:
            arr.append(label)
        return label

    def _make_label(self, elem, pos, ctx):
        """Shortcut for ``create_label`` wiring the ctx fields."""
        if ctx.ggb_manual_base_px is not None and ctx.ggb_label_point is not None:
            # An applet-placed label hangs off GeoGebra's own base point for
            # this type, not off the renderer's generic label spot.
            pos = [float(ctx.ggb_label_point[0]), float(ctx.ggb_label_point[1]), 0]
        col_label = ctx.col_label
        if self._label_contrast_mode() == 'auto':
            col_label = self._contrast_adjusted_label_color(
                col_label, self._label_center_2d(pos, ctx))
        label = create_label(
            elem, pos, col_label, ctx.font_size, ctx.zz_label,
            ctx.ptUnit_style, ptUnit_ggb=ctx.ptUnit_ggb, anchor=ctx.label_anchor,
            ggb_font_px=ctx.ggb_font_px, label_text=ctx.label_text,
            label_offset_px=ctx.label_offset_px, auto_placed=ctx.auto_placed,
            label_spec=ctx.label_spec, dynamic=ctx.label_dynamic,
            ggb_manual_base_px=ctx.ggb_manual_base_px,
            ggb_label_attach=ctx.ggb_label_attach,
        )
        if label is None:
            return None
        # The spot the label is attached to (scene units), for render reports.
        label._animageo_label_anchor = (float(pos[0]), float(pos[1]))
        # P2-A: draw the leader connector (attach → anchor, scene MU) for a
        # displaced label. Thin, label-coloured, just under the text z-tier.
        leader = elem.style.get('_leader') if hasattr(elem, 'style') else None
        if leader is not None:
            try:
                (ax, ay), (attx, atty) = leader
                line = Line([float(attx), float(atty), 0.0],
                            [float(ax), float(ay), 0.0],
                            stroke_width=stroke_width_to_manim(0.6, ctx.ptUnit_style),
                            color=col_label)
                line.set_z_index(ctx.zz_label - 1)
                label.add(line)
            except Exception:
                logger.debug("leader render failed for %s",
                             getattr(elem, 'name', '?'), exc_info=True)
        return label

    # ── Contrast-aware label colour (P1-C, rendering half) ───────────────
    def _label_contrast_mode(self) -> str:
        """``rendering.label_contrast``: 'off' (default) | 'auto'. In 'auto' a
        label that would sit on a low-contrast background (e.g. a dark label on a
        dense dark fill) is recoloured to a readable black/white."""
        rendering = getattr(self.style_config, 'rendering', None)
        return (rendering.get('label_contrast', 'off') if rendering else 'off') or 'off'

    def _label_contrast_threshold(self) -> float:
        rendering = getattr(self.style_config, 'rendering', None)
        val = rendering.get('label_contrast_threshold', 0.35) if rendering else 0.35
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.35

    def _label_center_2d(self, pos, ctx):
        """Approximate final label centre (base pos + offset) in scene MU."""
        import numpy as _np
        c = _np.asarray(pos, dtype=float)[:2].copy()
        off = getattr(ctx, 'label_offset_px', None)
        if off is not None:
            scale = ctx.ptUnit_ggb or ctx.ptUnit_style
            c = c + _np.array([off[0] / scale, off[1] / scale])
        return c

    def _label_background_luminance(self, p) -> float:
        """Composite-over-canvas luminance of the fills under point ``p``."""
        from .label_placement import (
            _collect_fills, _point_in_polygon, _point_in_disk, _color_luminance,
        )
        try:
            bg_hex = ManimColor(getattr(self.style, 'background', '#ffffff')).to_hex()
        except Exception:
            bg_hex = '#ffffff'
        lum = _color_luminance(bg_hex, default=1.0)
        for kind, geom, op, fl in _collect_fills(self):
            inside = (_point_in_polygon(p, geom) if kind == 'poly'
                      else _point_in_disk(p, geom[0], geom[1]))
            if inside:
                lum = (1.0 - op) * lum + op * fl   # alpha-composite fill over bg
        return lum

    def _contrast_adjusted_label_color(self, col_label, center_2d):
        """Return a readable colour for a label at ``center_2d``: keep
        ``col_label`` if it contrasts with the background, else switch to
        black/white (whichever contrasts with the composited background)."""
        from .label_placement import _color_luminance
        try:
            lab = _color_luminance(ManimColor(col_label).to_hex(), default=0.2)
        except Exception:
            lab = 0.2
        bg = self._label_background_luminance(center_2d)
        if abs(lab - bg) < self._label_contrast_threshold():
            return ManimColor('#FFFFFF') if bg < 0.5 else ManimColor('#000000')
        return col_label

    # ── Per-type renderers ────────────────────────────────────────────

    def _render_polygon(self, elem, ctx):
        pp = [[p[0], p[1], 0] for p in elem.data.vertices]
        fill_layer = Polygon(
            *pp,
            color=ctx.col_s, fill_color=ctx.col_f, fill_opacity=ctx.op_f,
            stroke_width=0, stroke_opacity=0,
        ).set_z_index(ctx.zz)
        stroke_layer = Polygon(
            *pp, joint_type=LineJointType.ROUND,
            color=ctx.col_s, fill_opacity=0,
            stroke_width=ctx.lw, stroke_opacity=ctx.op_s,
        ).set_z_index(max(ctx.zz_stroke, ctx.zz + 0.1))
        arr = [fill_layer, stroke_layer]
        if ctx.has_label:
            center = np.mean(elem.data.vertices, axis=0)
            self._append_label(arr, elem, [center[0], center[1], 0], ctx)
        return VGroup(*arr, name=elem.name)

    def _render_angle(self, elem, ctx):
        style = ctx.style
        ptUnit = ctx.ptUnit_style
        arr = []

        angle_range = ctx.angle_range
        angle = elem.data.size
        is_clockwise = False
        # angle_range='minor': render the non-reflex (≤π) supplementary
        # angle. angle_range='reflex': render the reflex (>π) one.
        # Supplement is 2π − angle (NOT angle − π).
        if angle_range == 'minor' and angle > PI:
            is_clockwise = True
            angle = 2 * PI - angle
        elif angle_range == 'reflex' and angle < PI:
            is_clockwise = True
            angle = 2 * PI - angle

        from .label_placement import compute_effective_arc_size_px
        arc_size_resolved = _resolve_style(self, elem, 'arc_size_px', default=17.0)
        r = compute_effective_arc_size_px(
            elem, elem.data, self, base_px=arc_size_resolved,
            angle_range=ctx.angle_range, auto_radius=ctx.auto_radius,
        ) / ptUnit
        arc_shift_px = ctx.arc_shift_px
        r += (ctx.tick_count - 1) \
             * arc_shift_px / ptUnit
        if r < 0.001:
            r = 0.2

        p = [elem.data.vertex[0], elem.data.vertex[1], 0]
        lines = [None, None]
        lines[0 + is_clockwise] = Line(
            [p[0], p[1], 0],
            [p[0] + elem.data.side1[0], p[1] + elem.data.side1[1], 0],
        )
        lines[1 - is_clockwise] = Line(
            [p[0], p[1], 0],
            [p[0] + elem.data.side2[0], p[1] + elem.data.side2[1], 0],
        )
        # Sector starting direction must match the stroke arc direction:
        # non-flipped — CCW from v1 to v2; flipped — CCW from v2 to v1.
        if is_clockwise:
            rotation_angle = float(np.arctan2(elem.data.side2[1], elem.data.side2[0]))
        else:
            rotation_angle = elem.data.start_angle

        right_mark = ctx.right_angle_marker
        if right_mark is None:
            right_mark = np.isclose(angle, PI / 2)

        if right_mark:
            ar_cfg = self.style_config.overlay.angle_radius
            if ar_cfg.get('enabled', False) and ar_cfg.get('apply_to_right', False):
                base_px = compute_effective_arc_size_px(
                    elem, elem.data, self, base_px=arc_size_resolved,
                    angle_range=ctx.angle_range, auto_radius=ctx.auto_radius,
                )
                r = base_px / SQRT2 / ptUnit
            else:
                right_size_px = _resolve_style(
                    self, elem, 'right_angle_size_px', default=arc_size_resolved,
                )
                r = right_size_px / SQRT2 / ptUnit

            n1 = elem.data.side1 * (r / np.linalg.norm(elem.data.side1))
            n2 = elem.data.side2 * (r / np.linalg.norm(elem.data.side2))
            p1 = [p[0] + n1[0], p[1] + n1[1], 0]
            p2 = [p1[0] + n2[0], p1[1] + n2[1], 0]
            p3 = [p[0] + n2[0], p[1] + n2[1], 0]
            arr.append(Polygon(
                p, p1, p2, p3,
                color=ctx.col_f, stroke_width=0, fill_opacity=ctx.op_f,
            ).set_z_index(ctx.zz))
            arr.append(VMobject(
                color=ctx.col_s, fill_opacity=0,
                stroke_width=ctx.lw, stroke_opacity=ctx.op_s,
                joint_type=_JOINT_MAP[ctx.ra_joint],
            ).set_points_as_corners([p1, p2, p3]).set_z_index(ctx.zz + 0.1))
        else:
            arr.append(AnnularSector(
                inner_radius=0, outer_radius=r, angle=angle,
                color=ctx.col_f, fill_opacity=ctx.op_f,
            ).set_z_index(ctx.zz)
             .rotate(rotation_angle, about_point=ORIGIN)
             .shift([p[0], p[1], 0]))
            for i in range(ctx.tick_count):
                arr.append(Angle(
                    *lines, radius=r - i * arc_shift_px / ptUnit,
                    other_angle=False,
                    color=ctx.col_s, fill_opacity=0,
                    stroke_width=ctx.lw, stroke_opacity=ctx.op_s,
                ).set_z_index(ctx.zz + 0.1))

        if ctx.has_label:
            r += ctx.label_roff
            label_pos = Angle(*lines, radius=r).point_from_proportion(0.5)
            self._append_label(arr, elem, label_pos, ctx)
        return VGroup(*arr, name=elem.name)

    def _append_tick_marks(self, arr, p1, p2, m, normal, ctx):
        """Append segment/vector equality tick decorations to ``arr``.

        Tick geometry uses MU, but tick stroke width is already converted to
        Manim stroke units in ``_build_render_ctx``.
        """
        if not ctx.tick_count:
            return

        num = ctx.tick_count
        delta = p2 - p1
        delta_norm = np.linalg.norm(delta)
        normal_norm = np.linalg.norm(normal)
        if np.isclose(delta_norm, 0) or np.isclose(normal_norm, 0):
            return

        v = delta / delta_norm
        n = normal / normal_norm
        dn = n * ctx.strich_len / 2

        if ctx.tick_style == 'wave':
            s = ctx.strich_rshift * 1.7
            l = ctx.strich_len * 0.8
            radius = ctx.tick_radius_px / ctx.ptUnit_style if ctx.tick_radius_px is not None else s * 0.45
            t = (l - 2 * radius) / (s - 2 * radius)
            offset = t * s / 2
            sign = 1

            points = []
            d = s * ((1 - num) * 0.5) + s / 2 - l / (2 * t)
            points.append(list(m + v * d + n * (l / 2) * sign) + [0])
            sign = -sign
            for i in range(1, num, 1):
                d = s * ((1 - num) * 0.5 + i)
                points.append(list(m + v * d + n * offset * sign) + [0])
                sign = -sign
            d = s * ((1 + num) * 0.5) - s / 2 + l / (2 * t)
            points.append(list(m + v * d + n * (l / 2) * sign) + [0])

            arr.append(round_corners_vmobject(
                points, radius=radius, components_per_rounded_corner=8,
            ).set_stroke(
                color=ctx.col_s, width=ctx.strich_width, opacity=ctx.op_s,
            ).set_z_index(ctx.zz))
            return

        line = Line(
            [m[0] + dn[0], m[1] + dn[1], 0],
            [m[0] - dn[0], m[1] - dn[1], 0],
            color=ctx.col_s, stroke_width=ctx.strich_width,
            stroke_opacity=ctx.op_s,
        ).set_z_index(ctx.zz)
        for i in range(num):
            d = ctx.strich_rshift * ((1 - num) * 0.5 + i)
            arr.append(line.copy().shift([v[0] * d, v[1] * d, 0]))

    def _render_segment(self, elem, ctx):
        style = ctx.style
        p1, p2 = elem.data.endpoints
        m = (p1 + p2) / 2
        arr = []

        arr.append(self._dash_stroke(Line(
            [p1[0], p1[1], 0], [p2[0], p2[1], 0],
            color=ctx.col_s, stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
            cap_style=_CAP_MAP[ctx.cap],
        ).set_z_index(ctx.zz), ctx, 'ends'))

        self._append_tick_marks(arr, p1, p2, m, elem.data.normal, ctx)

        if ctx.has_label:
            self._append_label(arr, elem, [m[0], m[1], 0], ctx)
        return VGroup(*arr, name=elem.name)

    def _render_line(self, elem, ctx):
        """Render geo.Line; also handles geo.Ray (shared implementation —
        see ``_render_ray`` alias below).
        """
        left, bottom, right, top = self._get_scene_bounds()
        endpoints = elem.data.get_endpoints([(left, bottom), (right, top)])
        if endpoints is None:
            return None
        p1, p2 = endpoints
        arr = []
        phase = 0.0
        if ctx.dash_px and isinstance(elem.data, geo.Ray):
            # Dashes start at the vertex, also when the viewport clips it
            # away: run the path away from the vertex and phase the pattern
            # by the clipped-off distance.
            d = np.asarray(elem.data.direction, dtype=float)
            d = d / (np.linalg.norm(d) or 1.0)
            s1, s2 = (float(np.dot(d, np.asarray(p) - elem.data.start)) for p in (p1, p2))
            if s2 < s1:
                p1, p2, s1 = p2, p1, s2
            phase = max(0.0, s1)
        arr.append(self._dash_stroke(Line(
            [p1[0], p1[1], 0], [p2[0], p2[1], 0],
            color=ctx.col_s, stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
            cap_style=_CAP_MAP[ctx.cap],
        ).set_z_index(ctx.zz), ctx, 'none', phase_mu=phase))
        if ctx.has_label:
            m = (p1 + p2) / 2
            self._append_label(arr, elem, [m[0], m[1], 0], ctx)
        return VGroup(*arr, name=elem.name)

    # Ray shares Line's clipping/rendering logic verbatim.
    _render_ray = _render_line

    def _render_vector(self, elem, ctx):
        style = ctx.style
        p1, p2 = elem.data.endpoints
        m = (p1 + p2) / 2
        arr = []

        # A dashed vector keeps its tip: the pattern goes on the Arrow's own
        # path (the stem); the tip is a separate, always solid submobject.
        arr.append(self._dash_stroke(Arrow(
            [p1[0], p1[1], 0], [p2[0], p2[1], 0],
            buff=0, tip_shape=CustomArrowTip,
            tip_style={'width': ctx.arrow_width,
                       'height': ctx.arrow_height,
                       'fill': ctx.col_s},
            color=ctx.col_s, stroke_opacity=ctx.op_s,
            stroke_width=ctx.lw, cap_style=_CAP_MAP[ctx.cap],
        ).set_z_index(ctx.zz), ctx, 'ends'))

        normal = np.array([p1[1] - p2[1], p2[0] - p1[0]])
        self._append_tick_marks(arr, p1, p2, m, normal, ctx)

        if ctx.has_label:
            self._append_label(arr, elem, [m[0], m[1], 0], ctx)
        return VGroup(*arr, name=elem.name)

    def _render_circle(self, elem, ctx):
        c = [elem.data.center[0], elem.data.center[1], 0]
        circ_fill = Circle(
            name=elem.name, arc_center=c, radius=elem.data.radius,
            fill_color=ctx.col_f, fill_opacity=ctx.op_f,
            stroke_opacity=0, stroke_width=0,
        ).set_z_index(ctx.zz_fill)
        circ_stroke = Circle(
            name=elem.name, arc_center=c, radius=elem.data.radius,
            color=ctx.col_s, fill_opacity=0,
            stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
        ).set_z_index(ctx.zz)
        self._dash_stroke(circ_stroke, ctx, 'closed')
        arr = [circ_fill, circ_stroke]
        if ctx.has_label:
            # Circles drew no label at all. The applet-placed one hangs off
            # GeoGebra's circle base (_make_label); a solver-placed one off
            # the centre, the anchor label_placement._get_anchor uses.
            self._append_label(arr, elem, c, ctx)
        return VGroup(*arr, name=elem.name)

    def _render_arc(self, elem, ctx):
        c = [elem.data.center[0], elem.data.center[1], 0]
        a1, a2 = elem.data.angles
        angle = (a2 - a1) % (2 * np.pi)
        arr = [
            Arc(arc_center=c, radius=elem.data.radius,
                start_angle=a1, angle=angle,
                fill_color=ctx.col_f, fill_opacity=ctx.op_f,
                stroke_width=0).set_z_index(ctx.zz_fill),
            self._dash_stroke(
                Arc(arc_center=c, radius=elem.data.radius,
                    start_angle=a1, angle=angle,
                    color=ctx.col_s, fill_opacity=0,
                    stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
                    cap_style=_CAP_MAP[ctx.cap]).set_z_index(ctx.zz),
                ctx, 'ends'),
        ]
        if ctx.has_label:
            label_pos = Arc(
                arc_center=c, radius=elem.data.radius + 0.7,
                start_angle=a1, angle=a2 - a1,
            ).point_from_proportion(0.5)
            self._append_label(arr, elem, label_pos, ctx)
        return VGroup(*arr, name=elem.name)

    def _render_circlesector(self, elem, ctx):
        c = [elem.data.center[0], elem.data.center[1], 0]
        a1, a2 = elem.data.angles
        angle_diff = a2 - a1

        arr = [
            Sector(arc_center=c, radius=elem.data.radius,
                   start_angle=a1, angle=angle_diff,
                   fill_color=ctx.col_f, fill_opacity=ctx.op_f,
                   stroke_width=0).set_z_index(ctx.zz_fill),
            Arc(arc_center=c, radius=elem.data.radius,
                start_angle=a1, angle=angle_diff,
                color=ctx.col_s, fill_opacity=0,
                stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
                cap_style=_CAP_MAP[ctx.cap]).set_z_index(ctx.zz),
        ]
        if ctx.has_label:
            mid_angle = a1 + angle_diff / 2
            label_pos = c + elem.data.radius * 0.7 * np.array(
                [np.cos(mid_angle), np.sin(mid_angle), 0],
            )
            self._append_label(arr, elem, label_pos, ctx)
        return VGroup(*arr, name=elem.name)

    # ── Point shape helper ─────────────────────────────────────────────

    @staticmethod
    def _make_point_mobject(shape, pos, radius, col_s, col_f, op_f, op_s, lw, zz):
        """Create a manim Mobject for a point with the given shape.

        All shapes are sized so their circumradius equals *radius*.
        """
        if shape is None or shape == 'circle':
            return Circle(
                arc_center=pos, radius=radius,
                color=col_s, fill_color=col_f, fill_opacity=op_f,
                stroke_opacity=op_s, stroke_width=lw,
            ).set_z_index(zz)
        if shape == 'square':
            side = radius * np.sqrt(2)
            return Square(
                side_length=side,
                color=col_s, fill_color=col_f, fill_opacity=op_f,
                stroke_opacity=op_s, stroke_width=lw,
            ).move_to(pos).set_z_index(zz)
        if shape == 'diamond':
            side = radius * np.sqrt(2)
            return Square(
                side_length=side,
                color=col_s, fill_color=col_f, fill_opacity=op_f,
                stroke_opacity=op_s, stroke_width=lw,
            ).rotate(PI / 4).move_to(pos).set_z_index(zz)
        if shape == 'triangle_up':
            return _scaled_triangle(pos, radius, 0, col_s, col_f, op_f, op_s, lw, zz)
        if shape == 'triangle_down':
            return _scaled_triangle(pos, radius, PI, col_s, col_f, op_f, op_s, lw, zz)
        if shape == 'triangle_right':
            return _scaled_triangle(pos, radius, -PI / 2, col_s, col_f, op_f, op_s, lw, zz)
        if shape == 'triangle_left':
            return _scaled_triangle(pos, radius, PI / 2, col_s, col_f, op_f, op_s, lw, zz)
        if shape == 'cross':
            d = radius
            return VGroup(
                Line(
                    [pos[0] - d, pos[1] + d, 0],
                    [pos[0] + d, pos[1] - d, 0],
                    color=col_s, stroke_width=lw, stroke_opacity=op_s,
                ),
                Line(
                    [pos[0] - d, pos[1] - d, 0],
                    [pos[0] + d, pos[1] + d, 0],
                    color=col_s, stroke_width=lw, stroke_opacity=op_s,
                ),
            ).set_z_index(zz)
        if shape == 'plus':
            d = radius
            return VGroup(
                Line(
                    [pos[0] - d, pos[1], 0],
                    [pos[0] + d, pos[1], 0],
                    color=col_s, stroke_width=lw, stroke_opacity=op_s,
                ),
                Line(
                    [pos[0], pos[1] - d, 0],
                    [pos[0], pos[1] + d, 0],
                    color=col_s, stroke_width=lw, stroke_opacity=op_s,
                ),
            ).set_z_index(zz)
        # Unknown shape — fall back to circle
        return Circle(
            arc_center=pos, radius=radius,
            color=col_s, fill_color=col_f, fill_opacity=op_f,
            stroke_opacity=op_s, stroke_width=lw,
        ).set_z_index(zz)

    def _render_point(self, elem, ctx):
        style = ctx.style
        ptUnit = ctx.ptUnit_style
        radius = _resolve_style(self, elem, 'size_px', default=style.dot_size) \
                 / 2 / ptUnit
        point_shape = _resolve_style(self, elem, 'point_shape', default='circle')

        pos = [elem.data.coords[0], elem.data.coords[1], 0]
        mobj = self._make_point_mobject(
            point_shape, pos, radius,
            ctx.col_s, ctx.col_f, ctx.op_f, ctx.op_s, ctx.lw, ctx.zz,
        )
        arr = [mobj]

        if style.rendering.get('points_display') == 'only_labels':
            arr[0].set_fill(opacity=0)
            arr[0].set_stroke(opacity=0)
            arr[0].set_phantom(True)

        if ctx.has_label:
            label = self._append_label(arr, elem, pos, ctx)
            if label is not None and style.rendering.get('points_display') == 'only_points':
                label.set_fill(opacity=0)
                label.set_phantom(True)

        return VGroup(*arr, name=elem.name)

    def _render_conic(self, elem, ctx):
        ptUnit = ctx.ptUnit
        conic = elem.data
        ctype = conic.type
        if ctype == ConicType.EMPTY:
            return None

        left, bottom, right_x, top_y = self._get_scene_bounds()
        viewport = (left, bottom, right_x, top_y)
        segment_mu = 3.0 / ptUnit   # adaptive sampler: ~3 px per segment

        arr = []

        if ctype == ConicType.POINT:
            p = conic.as_point()
            if p is not None:
                pos = [float(p.coords[0]), float(p.coords[1]), 0]
                arr.append(Dot(
                    point=pos, color=ctx.col_s, fill_opacity=ctx.op_f,
                ).set_z_index(ctx.zz))

        elif ctype == ConicType.CIRCLE:
            res = conic.as_circle()
            if res is not None:
                center, radius = res
                circ = Circle(
                    arc_center=[float(center[0]), float(center[1]), 0],
                    radius=radius,
                    color=ctx.col_s, fill_color=ctx.col_f,
                    fill_opacity=ctx.op_f, stroke_opacity=ctx.op_s,
                    stroke_width=ctx.lw,
                ).set_z_index(ctx.zz)
                arr.append(self._dash_stroke(circ, ctx, 'closed'))

        elif ctype == ConicType.ELLIPSE:
            params = conic.as_ellipse()
            if params is not None:
                a_semi, b_semi = params['semi_axes']
                cx, cy = params['center']
                rot = params['rotation']
                ell = Ellipse(
                    width=2 * a_semi, height=2 * b_semi,
                    color=ctx.col_s, fill_color=ctx.col_f,
                    fill_opacity=ctx.op_f, stroke_opacity=ctx.op_s,
                    stroke_width=ctx.lw,
                ).rotate(rot).move_to([float(cx), float(cy), 0]).set_z_index(ctx.zz)
                arr.append(self._dash_stroke(ell, ctx, 'closed'))

        elif ctype == ConicType.PARABOLA:
            params = conic.as_parabola()
            if params is not None:
                param_func = make_parabola_param(
                    params['vertex'], params['axis'],
                    params['perp'], params['focal_parameter'],
                )
                t_ranges = viewport_t_ranges_parabola(
                    params['vertex'], params['axis'], params['perp'],
                    params['focal_parameter'], viewport,
                )
                for tr in t_ranges:
                    polys = sample_parametric(
                        param_func, tr, viewport, segment_mu=segment_mu,
                    )
                    for poly in polys:
                        if len(poly) < 2:
                            continue
                        arr.append(self._curve_polyline(poly, ctx))

        elif ctype == ConicType.HYPERBOLA:
            params = conic.as_hyperbola()
            if params is not None:
                a_semi, b_semi = params['semi_axes']
                center_xy = params['center']
                rot = params['rotation']
                axis_u = np.array([np.cos(rot), np.sin(rot)])
                axis_v = np.array([-np.sin(rot), np.cos(rot)])
                for sign in (+1, -1):
                    tr = viewport_t_range_hyperbola_branch(
                        center_xy, axis_u, axis_v,
                        a_semi, b_semi, sign, viewport,
                    )
                    if tr is None:
                        continue
                    param_func = make_hyperbola_branch_param(
                        center_xy, axis_u, axis_v,
                        a_semi, b_semi, sign,
                    )
                    polys = sample_parametric(
                        param_func, tr, viewport, segment_mu=segment_mu,
                    )
                    for poly in polys:
                        if len(poly) < 2:
                            continue
                        arr.append(self._curve_polyline(poly, ctx))

        elif ctype in (ConicType.INTERSECTING_LINES,
                       ConicType.PARALLEL_LINES,
                       ConicType.DOUBLE_LINE):
            lines = conic.as_lines() or []
            corners = [(left, bottom), (right_x, top_y)]
            for ln in lines:
                endpoints = ln.get_endpoints(corners)
                if endpoints is None:
                    continue
                p1, p2 = endpoints
                arr.append(self._dash_stroke(Line(
                    [float(p1[0]), float(p1[1]), 0],
                    [float(p2[0]), float(p2[1]), 0],
                    color=ctx.col_s, stroke_opacity=ctx.op_s,
                    stroke_width=ctx.lw,
                ).set_z_index(ctx.zz), ctx, 'none'))

        if not arr:
            return None
        if ctx.has_label and ctx.ggb_label_point is not None:
            # Ellipse/circle conics drew no label. Only the applet-placed one is
            # reproducible: the placement solver has no anchor for conics.
            self._append_label(arr, elem, [0.0, 0.0, 0], ctx)
        return VGroup(*arr, name=elem.name)

    def _render_function(self, elem, ctx):
        ptUnit = ctx.ptUnit
        func = elem.data
        left, bottom, right_x, top_y = self._get_scene_bounds()
        viewport = (left, bottom, right_x, top_y)
        segment_mu = 3.0 / ptUnit

        x_range = (left, right_x)
        if func.explicit_domain is not None:
            dom_lo, dom_hi = func.explicit_domain
            x_range = (max(x_range[0], dom_lo), min(x_range[1], dom_hi))
        if x_range[0] >= x_range[1]:
            return None

        def _fparam(t, f=func):
            return (float(t), float(f(t)))

        # Split x_range at every singularity that lies inside, stepping
        # back by ε so the sampler never calls f at the exact asymptote.
        sings = sorted(
            s for s in func.natural_singularities
            if x_range[0] < s < x_range[1]
        )
        width = x_range[1] - x_range[0]
        eps = max(width * 1e-3, 1e-6)
        edges = [x_range[0]] + sings + [x_range[1]]

        arr = []
        for k in range(len(edges) - 1):
            lo = edges[k] + (eps if k > 0 else 0.0)
            hi = edges[k + 1] - (eps if k < len(edges) - 2 else 0.0)
            if lo >= hi:
                continue
            polys = sample_parametric(
                _fparam, (lo, hi), viewport, segment_mu=segment_mu,
            )
            for poly in polys:
                if len(poly) < 2:
                    continue
                arr.append(self._curve_polyline(poly, ctx))
        if not arr:
            return None
        return VGroup(*arr, name=elem.name)

    def _render_implicitcurve(self, elem, ctx):
        curve = elem.data
        left, bottom, right_x, top_y = self._get_scene_bounds()
        viewport = (left, bottom, right_x, top_y)

        segments = marching_squares(curve, viewport, grid_n=128)
        if ctx.dash_px:
            # A pattern restarts on every separate path: dash the stitched
            # polylines, not the hundreds of cell-sized pieces (which would
            # read as solid).
            arr = [self._curve_polyline(poly, ctx)
                   for poly in stitch_segments(segments) if len(poly) >= 2]
            return VGroup(*arr, name=elem.name) if arr else None
        arr = []
        for seg in segments:
            if seg.shape[0] < 2:
                continue
            p1, p2 = seg[0], seg[1]
            ln = Line(
                [float(p1[0]), float(p1[1]), 0],
                [float(p2[0]), float(p2[1]), 0],
                color=ctx.col_s, stroke_opacity=ctx.op_s, stroke_width=ctx.lw,
            ).set_z_index(ctx.zz)
            arr.append(ln)
        if not arr:
            return None
        return VGroup(*arr, name=elem.name)

    def _render_locuscurve(self, elem, ctx):
        locus = elem.data
        if len(locus.points) < 2:
            return None
        if ctx.dash_px:
            return VGroup(self._curve_polyline(locus.points, ctx), name=elem.name)
        pts_3d = [[float(p[0]), float(p[1]), 0] for p in locus.points]
        vm = VMobject(
            color=ctx.col_s, stroke_opacity=ctx.op_s,
            stroke_width=ctx.lw, fill_opacity=0,
        )
        vm.set_points_as_corners(pts_3d)
        vm.set_z_index(ctx.zz)
        return VGroup(vm, name=elem.name)

    def _render_text(self, elem, ctx):
        """Render a GeoGebra free-text object.

        Resolves the (possibly dynamic) content against the live construction,
        builds a ``Tex`` (LaTeX passed through, plain text escaped), and anchors
        its top-left corner at the start point — GeoGebra's convention — plus
        the optional ``labelOffset`` (px → MU via ``ptUnit_ggb``). Anchor points
        make the position track their point live.
        """
        text = elem.data
        decimals = getattr(self.geo, 'ggb_decimals', 2)
        tex_str = geo.text_to_display_latex(self.geo, text, decimals)
        if not tex_str:
            return None
        # Cyrillic inside the text's own ``$…$`` would compile to nothing —
        # the T2A math alphabet has no Cyrillic glyphs. Text mode has them.
        # Renderer-only: the TikZ/JSXGraph exporters keep the raw string.
        tex_str = textify_cyrillic(tex_str)

        try:
            mobj = Tex(tex_str, color=ctx.col_label, tex_template=RusTex)
        except Exception as e:
            # A malformed LaTeX text must not kill the render — fall back to
            # showing the raw content escaped as plain text.
            raw = geo.resolve_text_string(self.geo, text, decimals).replace('\xa0', ' ')
            logger.warning("Text '%s': LaTeX compile failed (%s); "
                           "falling back to escaped plain text", elem.name, e)
            mobj = Tex(geo.latex_escape_text(raw), color=ctx.col_label,
                       tex_template=RusTex)
        mobj.set(font_size=ctx.font_size)
        mobj.set_z_index(ctx.zz)

        base = geo.resolve_text_position(self.geo, text)
        pos = np.array([float(base[0]), float(base[1]), 0.0])
        off = ctx.label_offset_px
        if off:
            pos = pos + np.array([off[0] / ctx.ptUnit_ggb,
                                  off[1] / ctx.ptUnit_ggb, 0.0])
        # Anchor the text's top-left corner at the (offset) start point.
        mobj.shift(pos - mobj.get_corner(UL))

        return VGroup(mobj, name=elem.name)

    def CreateMObject(self, elem, z_auto = False, debug = False):
        """Build a manim Mobject for a geometry element.

        Thin dispatcher: delegates to ``_render_<typename>`` for the
        per-type work. The shared preamble (colours, stroke, z-index,
        labels, cap/joint/dash) is computed once by
        ``_build_render_ctx`` and passed through a SimpleNamespace.
        All exceptions are caught and logged — failure to render one
        element must not abort the rest of the scene.
        """
        try:
            if not self._element_visible(elem):
                return None
            ctx = self._build_render_ctx(elem, z_auto)
            renderer = self._renderer_for(elem)
            if renderer is None:
                logger.warning(
                    'CreateMObject: no renderer for "%s" (type %s)',
                    elem.name, type(elem.data).__name__,
                )
                return None
            return renderer(elem, ctx)
        except Exception as e:
            hint = ''
            if isinstance(e, RecursionError):
                hint = (
                    '\nRecursionError here usually means process-wide state '
                    'corruption, not a defect in this element — e.g. a '
                    'partialmethod chain accumulated on MathTex/Text.__init__ '
                    'by repeated Mobject.set_default calls (docs/gotchas.md).'
                )
            logger.warning(
                'CreateMObject failed for "%s" (%s): %s%s\n%s',
                elem.name,
                type(elem.data).__name__ if elem.data else 'None',
                e,
                hint,
                traceback.format_exc(),
            )
            return None
