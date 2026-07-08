"""Export-canvas layout helpers.

This module separates the source/reference canvas from the physical export
canvas. The renderer can then scale geometry to the requested output size
while resolving style pixel values against the original/reference scale.
"""
from __future__ import annotations

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
#                 prominence constant across content.source choices.
DECORATION_SCALE_SOURCES = frozenset({'frame', 'reference'})
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
