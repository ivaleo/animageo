"""Export-canvas layout helpers.

This module separates the source/reference canvas from the physical export
canvas. The renderer can then scale geometry to the requested output size
while resolving style pixel values against the original/reference scale.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


FIT_MODES = frozenset({'contain', 'cover', 'width', 'height', 'none', 'manual'})
SOURCE_RECTS = frozenset({'source_view', 'ggb_view', 'rendered_bounds', 'reference'})
INFINITE_POLICIES = frozenset({'ignore', 'clip'})
# Basis for resolving decoration sizes (`ptUnit_style`):
#   'frame'     — track the actual export crop (default). Decorations scale with
#                 how the geometry is framed; a tight `rendered_bounds` crop makes
#                 them look smaller relative to the drawing than a wide `ggb_view`.
#                 `fitView` relies on this (its source view is the previous crop).
#   'reference' — fit the full source view onto the reference canvas, independent
#                 of the chosen «Кадр»/crop. Requires a STABLE source view (a real
#                 viewport, applied once — not an iterative fit). Keeps decoration
#                 *proportion* (relative to the drawing) constant across sources —
#                 but absolute px still grow as a tighter frame zooms the geometry.
#   'output'    — anchor decoration size to the geometry's export zoom (`ptUnit`),
#                 so point/stroke/label pixels are a fixed OUTPUT size that depends
#                 ONLY on prominence — never on how the «Кадр» is sized/typed nor on
#                 the output resolution. "Exact style pixels" ("Пиксели вывода").
#   'ggb'       — «Как в GeoGebra»: decorations keep the relative size they have in
#                 the GeoGebra applet and scale UNIFORMLY with the output (a wider
#                 canvas ⇒ proportionally bigger decorations), while the frame/crop
#                 does not change them. ptUnit_style is anchored so
#                 decoration_px = authored_px * (output_width / ggb_view_width) *
#                 prominence — at the applet's own width that is exactly its px.
#                 Needs the original GeoGebra source view width.
DECORATION_SCALE_SOURCES = frozenset({'frame', 'reference', 'output', 'ggb'})
# Whether labels count toward a `rendered_bounds` crop:
#   'reserve'  — include point/element labels so an outward-placed label does not
#                clip on export (default; the historical behaviour).
#   'exclude'  — crop to the geometry alone, so a label above/beside the drawing
#                does not push the frame out (a label near the edge may clip).
RENDERED_BOUNDS_LABEL_POLICIES = frozenset({'reserve', 'exclude'})
ANCHORS = frozenset({
    'top_left', 'top', 'top_right',
    'left', 'center', 'right',
    'bottom_left', 'bottom', 'bottom_right',
})


@dataclass(frozen=True)
class ExportLayout:
    ptWidth: float
    ptHeight: float
    ptUnit: float
    ptXZero: float
    ptYZero: float
    ptUnit_style: float
    referenceWidth: float
    referenceHeight: float
    contentScale: float
    contentOffsetX: float
    contentOffsetY: float
    fit: str
    source_rect: str
    geometryScale: float | None = None
    exportScale: float | None = None
    referenceOffsetX: float | None = None
    referenceOffsetY: float | None = None
    contentFit: str | None = None
    exportFit: str | None = None
    contentSource: str | None = None

    def to_export_dict(self) -> dict:
        out = {
            'ptWidth': self.ptWidth,
            'ptHeight': self.ptHeight,
            'ptUnit': self.ptUnit,
            'ptXZero': self.ptXZero,
            'ptYZero': self.ptYZero,
            'ptUnit_style': self.ptUnit_style,
            'referenceWidth': self.referenceWidth,
            'referenceHeight': self.referenceHeight,
            'contentScale': self.contentScale,
            'contentOffsetX': self.contentOffsetX,
            'contentOffsetY': self.contentOffsetY,
            'fit': self.fit,
            'source_rect': self.source_rect,
        }
        optional = {
            'geometryScale': self.geometryScale,
            'exportScale': self.exportScale,
            'referenceOffsetX': self.referenceOffsetX,
            'referenceOffsetY': self.referenceOffsetY,
            'contentFit': self.contentFit,
            'exportFit': self.exportFit,
            'contentSource': self.contentSource,
        }
        out.update({k: v for k, v in optional.items() if v is not None})
        return out


def compute_export_layout(
    source_view: Mapping[str, float],
    *,
    export_size: Sequence[float],
    reference_size: Sequence[float] | None = None,
    fit: str = 'contain',
    source_rect: str = 'ggb_view',
    manual_scale: float | None = None,
    anchor: str = 'center',
    offset: Sequence[float] | None = None,
    padding: float = 0.0,
) -> ExportLayout:
    """Compute a final export transform from a source/reference canvas.

    ``source_view`` is the original coordinate-to-pixel mapping, typically from
    GeoGebra. ``export_size`` is the physical output canvas. ``ptUnit_style`` is
    intentionally kept at the reference scale so visual ``*_px`` style values
    scale together with the content when the final export is larger.

    ``source_rect="ggb_view"`` preserves the original GeoGebra viewport/origin.
    ``source_rect="rendered_bounds"`` is accepted for layouts whose caller has
    already replaced ``source_view`` with bounds measured from rendered
    mobjects. This pure helper does not measure scene geometry itself.
    """
    fit = _validate_choice('fit', fit, FIT_MODES)
    source_rect = _validate_choice('source_rect', source_rect, SOURCE_RECTS)
    anchor = _validate_choice('anchor', anchor, ANCHORS)

    out_w, out_h = _size2(export_size, 'export_size')
    src_w, src_h = _source_size(source_view, reference_size)
    src_unit = _positive_float(source_view.get('ptUnit', 1), 'source_view.ptUnit')
    src_xzero = float(source_view.get('ptXZero', src_w / 2) or 0)
    src_yzero = float(source_view.get('ptYZero', src_h / 2) or 0)

    # Uniform edge margin: fit the content into the canvas shrunk by `padding`
    # on every side, then shift it in by `padding`, so all four edges keep that
    # gap. `padding` is in output (canvas) pixels. Clamped so the usable area
    # never collapses.
    pad = max(0.0, float(padding or 0.0))
    pad = min(pad, max(0.0, (min(out_w, out_h) - 1.0) / 2.0))
    avail_w = out_w - 2.0 * pad
    avail_h = out_h - 2.0 * pad

    scale = _scale_for_fit(
        avail_w, avail_h, src_w, src_h,
        fit=fit, manual_scale=manual_scale,
    )
    pad_x, pad_y = _anchor_padding(avail_w - src_w * scale, avail_h - src_h * scale, anchor)
    off_x, off_y = _offset2(offset)

    content_x = pad + pad_x + off_x
    content_y = pad + pad_y + off_y

    return ExportLayout(
        ptWidth=out_w,
        ptHeight=out_h,
        ptUnit=src_unit * scale,
        ptXZero=src_xzero * scale + content_x,
        ptYZero=src_yzero * scale + content_y,
        ptUnit_style=src_unit,
        referenceWidth=src_w,
        referenceHeight=src_h,
        contentScale=scale,
        contentOffsetX=content_x,
        contentOffsetY=content_y,
        fit=fit,
        source_rect=source_rect,
    )


def compute_reference_export_layout(
    source_view: Mapping[str, float],
    *,
    reference_size: Sequence[float],
    export_size: Sequence[float],
    content: Mapping[str, Any] | None = None,
    export: Mapping[str, Any] | None = None,
) -> ExportLayout:
    """Compute the full content -> reference -> export layout.

    ``content`` controls how the construction/source rectangle is placed into
    the reference canvas. ``export`` controls how that reference canvas is then
    placed into the physical output. Style pixel values resolve against the
    content-to-reference scale, so they look authored on the reference canvas
    and scale only during the final reference-to-export stage.
    """
    content = normalize_content_options(content)
    export = normalize_export_options(export)

    reference_layout = compute_export_layout(
        source_view,
        export_size=reference_size,
        fit=content['fit'],
        source_rect=content['source'],
        manual_scale=content.get('scale'),
        anchor=content['anchor'],
        offset=content.get('offset'),
    )
    reference_view = {
        'ptUnit': reference_layout.ptUnit,
        'ptWidth': reference_layout.ptWidth,
        'ptHeight': reference_layout.ptHeight,
        'ptXZero': reference_layout.ptXZero,
        'ptYZero': reference_layout.ptYZero,
    }
    final_layout = compute_export_layout(
        reference_view,
        export_size=export_size,
        fit=export['fit'],
        source_rect='reference',
        manual_scale=export.get('scale'),
        anchor=export['anchor'],
        offset=export.get('offset'),
        # content.padding = a uniform margin (in export-canvas px) between the
        # fitted content and the canvas edges. Applied at the final stage so the
        # gap is exact in output pixels.
        padding=content.get('padding', 0.0),
    )
    return ExportLayout(
        ptWidth=final_layout.ptWidth,
        ptHeight=final_layout.ptHeight,
        ptUnit=final_layout.ptUnit,
        ptXZero=final_layout.ptXZero,
        ptYZero=final_layout.ptYZero,
        ptUnit_style=reference_layout.ptUnit,
        referenceWidth=reference_layout.ptWidth,
        referenceHeight=reference_layout.ptHeight,
        contentScale=final_layout.contentScale,
        contentOffsetX=reference_layout.contentOffsetX,
        contentOffsetY=reference_layout.contentOffsetY,
        fit=final_layout.fit,
        source_rect=content['source'],
        geometryScale=reference_layout.contentScale,
        exportScale=final_layout.contentScale,
        referenceOffsetX=final_layout.contentOffsetX,
        referenceOffsetY=final_layout.contentOffsetY,
        contentFit=content['fit'],
        exportFit=export['fit'],
        contentSource=content['source'],
    )


def normalize_content_options(content: Mapping[str, Any] | None) -> dict:
    """Return canonical content-placement options."""
    raw = dict(content or {})
    if 'source_rect' in raw and 'source' not in raw:
        raw['source'] = raw.pop('source_rect')
    source = raw.get('source', 'source_view')
    if source == 'bounds':
        source = 'rendered_bounds'
    if source == 'ggb':
        source = 'ggb_view'
    return {
        'source': _validate_choice('content.source', source, SOURCE_RECTS - {'reference'}),
        'fit': _validate_choice('content.fit', raw.get('fit', 'contain'), FIT_MODES),
        'scale': raw.get('scale', raw.get('manual_scale')),
        'anchor': _validate_choice('content.anchor', raw.get('anchor', 'center'), ANCHORS),
        'offset': raw.get('offset'),
        'padding': float(raw.get('padding', raw.get('bounds_padding', 0)) or 0),
        'infinite_policy': _validate_choice(
            'content.infinite_policy',
            raw.get('infinite_policy', 'ignore'),
            INFINITE_POLICIES,
        ),
        'bounds': raw.get('bounds'),
        'prominence': _normalize_prominence(raw.get('prominence')),
        'decoration_scale_source': _validate_choice(
            'content.decoration_scale_source',
            raw.get('decoration_scale_source', 'frame'),
            DECORATION_SCALE_SOURCES,
        ),
        'label_bounds': _validate_choice(
            'content.label_bounds',
            raw.get('label_bounds', 'reserve'),
            RENDERED_BOUNDS_LABEL_POLICIES,
        ),
    }


def _normalize_prominence(value: Any) -> float:
    """«Element prominence» — a decoration-size multiplier applied at render time.

    The layout, crop and label placement are computed at nominal prominence (1.0)
    and stay unaffected; prominence only scales the density that decoration sizes
    (points, strokes, label font, angle markers, ticks) resolve against, so the
    whole size system scales together after the style resolves — independent of
    the content source and framing. Defaults to 1.0; clamped to [0.01, 100].
    """
    try:
        p = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not p > 0:
        return 1.0
    return min(100.0, max(0.01, p))


def normalize_export_options(export: Mapping[str, Any] | None) -> dict:
    """Return canonical reference-to-output export options."""
    raw = dict(export or {})
    return {
        'size': raw.get('size'),
        'fit': _validate_choice('export.fit', raw.get('fit', 'contain'), FIT_MODES),
        'scale': raw.get('scale', raw.get('manual_scale')),
        'anchor': _validate_choice('export.anchor', raw.get('anchor', 'center'), ANCHORS),
        'offset': raw.get('offset'),
    }


def size_from_config(value: Any) -> list[Any] | None:
    """Accept ``[w, h]`` or ``{'width': w, 'height': h}`` size shapes."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        return [value.get('width'), value.get('height')]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 2:
            raise ValueError('size must be a two-item [width, height] sequence')
        return [value[0], value[1]]
    raise ValueError('size must be [width, height] or {width, height}')


def resolve_auto_size(size: Sequence[Any] | None, aspect_source: Sequence[float]) -> list[float]:
    """Resolve ``auto``/``None`` in a two-item size against an aspect ratio."""
    if size is None:
        return [float(aspect_source[0]), float(aspect_source[1])]
    if len(size) != 2:
        raise ValueError('size must be [width, height]')
    w, h = size
    src_w, src_h = _size2(aspect_source, 'aspect_source')
    w_auto = _is_auto(w)
    h_auto = _is_auto(h)
    if w_auto and h_auto:
        raise ValueError('size cannot be [auto, auto]')
    if w_auto:
        h = _positive_float(h, 'size.height')
        w = h * src_w / src_h
    elif h_auto:
        w = _positive_float(w, 'size.width')
        h = w * src_h / src_w
    else:
        w = _positive_float(w, 'size.width')
        h = _positive_float(h, 'size.height')
    return [w, h]


def reference_size_from_config(reference) -> list | None:
    """``[w, h]`` of ``reference.size`` when both are given, else ``None``."""
    if not isinstance(reference, dict):
        return None
    size = size_from_config(reference.get('size'))
    if size is None or size[0] is None or size[1] is None:
        return None
    return size


def merge_reference(style_reference, runtime_reference) -> dict:
    """The style's ``reference`` with the runtime one on top (``size`` merged by key)."""
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


def source_bounds_px_from_config(value) -> list | None:
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


def source_view_from_bounds_px(source_view, bounds_px, *, padding_px=0,
                               infinite_policy='ignore') -> dict:
    """A source view cropped to explicit source-pixel bounds (``content.bounds``)."""
    left_px, top_px, right_px, bottom_px = source_bounds_px_from_config(bounds_px)
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
        'boundsInfinitePolicy': _validate_choice('content.infinite_policy', infinite_policy,
                                                 INFINITE_POLICIES),
        'boundsSource': 'explicit',
    })
    return rendered_view


def rendered_view_from_bounds(source_view, bounds, *, padding_px=0, infinite_policy='ignore') -> dict:
    """A source view cropped to the drawing: ``bounds`` — ``(left, bottom,
    right, top)`` in scene units of the drawing as measured (``None`` for an
    empty drawing: the source view itself), ``padding_px`` source pixels
    around it."""
    if bounds is None:
        return dict(source_view)
    left_mu, bottom_mu, right_mu, top_mu = bounds
    padding_px = max(float(padding_px or 0), 0.0)
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


def static_export_dict(source_view: Mapping[str, Any], *, style_reference=None, reference=None,
                       content=None, export=None, rendered_view=None, decoration=True) -> dict:
    """The export dict ``AnimaGeoScene.applyStyle`` leaves in ``scene.style.export``.

    The same pipeline without a scene: the runtime ``reference`` over the
    style's, ``content`` placed into the reference canvas, the ``export``
    size, then the decoration density ``ptUnit_style`` (``prominence``,
    ``decoration_scale_source``). For ``content.source == 'rendered_bounds'``
    the caller measures the drawing and passes the cropped source view as
    ``rendered_view`` (``source_view_from_bounds_px`` for explicit
    ``content.bounds``); without it that source is a ``ValueError``.
    ``decoration=False`` stops before ``ptUnit_style`` is re-based: the dict
    ``applyStyle`` holds while it measures and places labels.
    """
    runtime_reference = merge_reference(style_reference, reference)
    explicit_reference_size = size_from_config(reference_size_from_config(runtime_reference))
    source_size = [source_view.get('ptWidth'), source_view.get('ptHeight')]
    reference_size = resolve_auto_size(explicit_reference_size or source_size, source_size)
    style_density_reference_size = list(reference_size)

    export_options = normalize_export_options(export)
    export_size = resolve_auto_size(size_from_config(export_options.get('size')), reference_size)
    content_options = normalize_content_options(content)
    use_rendered_bounds = content_options['source'] == 'rendered_bounds'

    layout_source_view = source_view
    if use_rendered_bounds:
        if rendered_view is None:
            raise ValueError("content.source 'rendered_bounds' needs the measured rendered_view")
        layout_source_view = rendered_view
        if explicit_reference_size is None:
            reference_size = [rendered_view.get('ptWidth'), rendered_view.get('ptHeight')]

    layout = compute_reference_export_layout(
        layout_source_view,
        reference_size=reference_size,
        export_size=export_size,
        content=content_options,
        export=export_options,
    )
    out = dict(layout_source_view)
    out.update(layout.to_export_dict())
    out['reference'] = runtime_reference
    if not decoration:
        return out

    prominence = content_options.get('prominence', 1.0) or 1.0
    decoration_source = content_options.get('decoration_scale_source')
    base = out.get('ptUnit_style')
    if decoration_source == 'output':
        geom_zoom = out.get('ptUnit')
        if geom_zoom:
            base = geom_zoom
    elif decoration_source == 'ggb':
        geom_zoom = out.get('ptUnit')
        out_w = out.get('ptWidth')
        ggb_w = source_view.get('ptWidth')
        try:
            if geom_zoom and out_w and ggb_w and float(out_w) > 0:
                base = float(geom_zoom) * float(ggb_w) / float(out_w)
        except (TypeError, ValueError):
            pass
    elif use_rendered_bounds and decoration_source == 'reference':
        try:
            density = compute_export_layout(
                source_view,
                export_size=style_density_reference_size,
                fit='contain',
                source_rect='source_view',
            ).ptUnit
        except Exception:
            density = None
        if density:
            base = density
    if base:
        out['ptUnit_style'] = base / prominence
        if prominence != 1.0:
            out['elementProminence'] = prominence
    return out


def _validate_choice(name: str, value: str, choices: frozenset[str]) -> str:
    value = str(value)
    if value not in choices:
        allowed = ', '.join(sorted(choices))
        raise ValueError(f"{name} must be one of: {allowed}")
    return value


def _is_auto(value) -> bool:
    return value is None or value == 'auto'


def _size2(value: Sequence[float], name: str) -> tuple[float, float]:
    if value is None or len(value) != 2:
        raise ValueError(f"{name} must be a two-item [width, height] sequence")
    w = _positive_float(value[0], f'{name}[0]')
    h = _positive_float(value[1], f'{name}[1]')
    return w, h


def _source_size(
    source_view: Mapping[str, float],
    reference_size: Sequence[float] | None,
) -> tuple[float, float]:
    if reference_size is not None:
        return _size2(reference_size, 'reference_size')
    return (
        _positive_float(source_view.get('ptWidth'), 'source_view.ptWidth'),
        _positive_float(source_view.get('ptHeight'), 'source_view.ptHeight'),
    )


def _positive_float(value, name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive number") from None
    if out <= 0:
        raise ValueError(f"{name} must be a positive number")
    return out


def _scale_for_fit(
    out_w: float,
    out_h: float,
    src_w: float,
    src_h: float,
    *,
    fit: str,
    manual_scale: float | None,
) -> float:
    sx = out_w / src_w
    sy = out_h / src_h
    if fit == 'contain':
        return min(sx, sy)
    if fit == 'cover':
        return max(sx, sy)
    if fit == 'width':
        return sx
    if fit == 'height':
        return sy
    if fit == 'none':
        return 1.0
    return _positive_float(manual_scale, 'manual_scale')


def _anchor_padding(extra_w: float, extra_h: float, anchor: str) -> tuple[float, float]:
    x_factor = {
        'top_left': 0.0, 'left': 0.0, 'bottom_left': 0.0,
        'top': 0.5, 'center': 0.5, 'bottom': 0.5,
        'top_right': 1.0, 'right': 1.0, 'bottom_right': 1.0,
    }[anchor]
    y_factor = {
        'top_left': 0.0, 'top': 0.0, 'top_right': 0.0,
        'left': 0.5, 'center': 0.5, 'right': 0.5,
        'bottom_left': 1.0, 'bottom': 1.0, 'bottom_right': 1.0,
    }[anchor]
    return extra_w * x_factor, extra_h * y_factor


def _offset2(value: Sequence[float] | None) -> tuple[float, float]:
    if value is None:
        return 0.0, 0.0
    if len(value) != 2:
        raise ValueError("offset must be a two-item [x, y] sequence")
    return float(value[0]), float(value[1])
