"""The style keys of each element type and the paint the renderer draws
(1.11.0rc3).

:func:`style_keys` is the contract of ``appearance.overrides`` by element
type: the keys the renderer of the type reads, their unit and their default
in the built-in style. ``appearance_plan`` accepts every key of
:data:`~animageo.native.rendering.APPEARANCE_STYLE_KEYS` and warns
``style_key_ineffective`` about one the element does not read
(:func:`ineffective_reason`).

The table below is the renderer's (``AnimaGeoScene._render_<type>`` and
``_build_render_ctx``): a key is listed for a type when the drawing of the
type reads it. Manim-free.
"""
from __future__ import annotations

import copy

__all__ = ['STYLE_KEYS_FORMAT', 'MARK_TRANSFERS', 'style_keys', 'ineffective_reason', 'style_type_of']

STYLE_KEYS_FORMAT = 'animageo-style-keys/v1'

# key → (unit, allowed values or None). Units: color (hex, or "stroke" — the
# stroke colour of the element), px (style pixels), opacity and ratio (0..1),
# deg, count (an integer), enum, bool, number, string.
_VALUE_ENUMS = {
    'stroke_linecap': ('butt', 'round', 'square'),
    'tick_style': ('line', 'wave'),
    'angle_range': ('minor', 'reflex'),
    'right_angle_joint': ('auto', 'bevel', 'miter', 'round'),
    'label_anchor': ('TL', 'TC', 'TR', 'ML', 'MC', 'MR', 'BL', 'BC', 'BR'),
    'fill_pattern': ('solid', 'hatch', 'crosshatch', 'dots', 'none'),
    'label_angle_unit': ('degree', 'radian'),
}
_UNITS = {
    'stroke': 'color', 'fill': 'color', 'label_color': 'color', 'hatch_color': 'color',
    'stroke_width_px': 'px', 'stroke_dash_period_px': 'px', 'size_px': 'px', 'font_size_px': 'px',
    'label_radial_offset_px': 'px', 'tick_length_px': 'px', 'tick_width_px': 'px', 'tick_shift_px': 'px',
    'tick_radius_px': 'px', 'arrow_length_px': 'px', 'arrow_width_px': 'px', 'arc_size_px': 'px',
    'arc_shift_px': 'px', 'right_angle_size_px': 'px', 'hatch_spacing_px': 'px', 'hatch_width_px': 'px',
    'stroke_opacity': 'opacity', 'fill_opacity': 'opacity', 'hatch_opacity': 'opacity',
    'stroke_dash_ratio': 'ratio',
    'hatch_angle_deg': 'deg',
    'tick_count': 'count', 'label_value_precision': 'count',
    'point_shape': 'enum', 'stroke_linecap': 'enum', 'tick_style': 'enum', 'angle_range': 'enum',
    'right_angle_joint': 'enum', 'label_anchor': 'enum', 'fill_pattern': 'enum', 'label_angle_unit': 'enum',
    'label_value_strip_zeros': 'bool', 'right_angle_marker': 'bool', 'auto_radius': 'bool',
    'label_value_separator': 'string',
    'z_index': 'number', 'z_index_fill': 'number',
}

_STROKE = ('stroke', 'stroke_width_px', 'stroke_opacity')
_DASH = ('stroke_dash_ratio', 'stroke_dash_period_px')
_FILL = ('fill', 'fill_opacity')
_HATCH = ('fill_pattern', 'hatch_angle_deg', 'hatch_spacing_px', 'hatch_width_px', 'hatch_color', 'hatch_opacity')
_TICKS = ('tick_count', 'tick_style', 'tick_length_px', 'tick_width_px', 'tick_shift_px', 'tick_radius_px')
_LABEL = ('label_color', 'font_size_px', 'label_anchor')
_VALUE = ('label_value_precision', 'label_value_strip_zeros', 'label_value_separator')
_ANGLE = ('angle_range', 'arc_size_px', 'arc_shift_px', 'tick_count', 'auto_radius', 'right_angle_marker',
          'right_angle_size_px', 'right_angle_joint', 'label_radial_offset_px', 'label_angle_unit')

# document type (a mark by its operation) → (classic style type, keys read).
_TYPES = {
    'point': ('point', ('size_px', 'point_shape') + _STROKE + _FILL + ('z_index',) + _LABEL),
    'segment': ('segment', _STROKE + ('stroke_linecap',) + _DASH + _TICKS + ('z_index',) + _LABEL + _VALUE),
    'line': ('line', _STROKE + ('stroke_linecap',) + _DASH + ('z_index',) + _LABEL),
    'ray': ('ray', _STROKE + ('stroke_linecap',) + _DASH + ('z_index',) + _LABEL),
    'vector': ('vector', _STROKE + ('stroke_linecap',) + _DASH + _TICKS + ('arrow_length_px', 'arrow_width_px')
               + ('z_index',) + _LABEL + _VALUE),
    'circle': ('circle', _STROKE + _DASH + _FILL + _HATCH + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    'arc': ('arc', _STROKE + ('stroke_linecap',) + _DASH + _FILL + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    # the stroke of a sector is solid; its cap counts without ``sector_sides``
    'sector': ('circlesector', _STROKE + ('stroke_linecap',) + _FILL + _HATCH + ('z_index', 'z_index_fill')
               + _LABEL + _VALUE),
    # the fill of a polygon lies at its ``z_index``, the stroke is solid
    'polygon': ('polygon', _STROKE + _FILL + _HATCH + ('z_index',) + _LABEL + _VALUE),
    'polyline': ('locuscurve', _STROKE + _DASH + ('z_index',)),
    'locus': ('locuscurve', _STROKE + _DASH + ('z_index',)),
    'angle': ('angle', _STROKE + _FILL + _ANGLE + ('z_index',) + _LABEL + _VALUE),
    # a right-angle mark draws the square: no arcs to count or space
    'mark.right_angle': ('angle', _STROKE + _FILL + tuple(k for k in _ANGLE if k not in ('tick_count', 'arc_shift_px'))
                         + ('z_index',) + _LABEL + _VALUE),
    'text': ('text', ('label_color', 'font_size_px', 'z_index')),
    'mark.equal_segments': (None, ()),
    'mark.equal_angles': (None, ()),
    'number': (None, ()),
    'expr': (None, ()),
    'template': (None, ()),
}

# The keys an equality mark passes to its targets (as its count becomes their
# ``tick_count``): the sizes of the ticks of a segment, the spacing of the arcs
# of an angle. An explicit key of the target wins.
MARK_TRANSFERS = {
    'mark.equal_segments': ('tick_length_px', 'tick_radius_px', 'tick_shift_px', 'tick_style', 'tick_width_px'),
    'mark.equal_angles': ('arc_shift_px',),
}

# Defaults the built-in style leaves to the renderer (``_build_render_ctx``,
# ``labels``, ``hatch``, ``dash``): ``None`` — no value (solid, automatic).
_RENDERER_DEFAULTS = {
    'stroke_dash_ratio': None, 'tick_count': 0, 'tick_style': 'line', 'tick_radius_px': None,
    'angle_range': 'minor', 'auto_radius': True, 'right_angle_marker': None, 'z_index': None,
    'z_index_fill': 0.01, 'label_value_strip_zeros': True, 'label_value_separator': ' = ',
    'label_angle_unit': 'degree', 'label_radial_offset_px': 0.0, 'point_shape': 'circle',
    'fill_pattern': 'solid', 'hatch_angle_deg': 45.0, 'hatch_spacing_px': 6.0, 'hatch_width_px': 0.75,
    'hatch_color': 'stroke', 'hatch_opacity': 1.0, 'stroke_opacity': 1, 'fill_opacity': 1,
    'stroke_width_px': 1.0, 'font_size_px': 14.0, 'tick_length_px': 0.0, 'tick_width_px': 0.0,
    'tick_shift_px': 0.0, 'arrow_length_px': 0.0, 'arrow_width_px': 0.0, 'arc_shift_px': 0.0,
    'arc_size_px': 17.0,
    # the ``rendering`` of the given style itself (``GeoStyle.rendering``, not
    # merged with the built-in one): ``label_anchor`` ``None`` is that of the
    # style, else ``BL``
    'stroke_linecap': 'butt', 'right_angle_joint': 'auto', 'label_anchor': None,
}
# Defaults from the ``rendering`` section of the built-in style (merged).
_RENDERING_DEFAULTS = {
    'label_value_precision': ('label_value_precision', 1),
    'stroke_dash_period_px': ('dash_period_px', 10),
}

_CACHE = {}


def style_type_of(doc, el_id):
    """The key of :func:`style_keys` for an element of ``doc``: its type, a
    mark by the operation that makes it (``mark.right_angle``…); ``None``
    for a mark without a known producer."""
    from .document import as_document, bound_producer
    doc = as_document(doc)
    el = doc.elements.get(el_id) or {}
    type_ = el.get('type')
    if type_ != 'mark':
        return type_
    producer = bound_producer(doc, el_id)
    op = doc.operations.get(producer) if producer is not None else None
    name = op.get('op') if isinstance(op, dict) else None
    return name if name in _TYPES else None


def ineffective_reason(type_, key):
    """Why ``key`` of ``appearance.overrides`` does nothing on an element of
    :func:`style_keys` type ``type_``, or ``None`` when it is read (or the
    type is unknown): ``not_drawn`` — the element is not drawn (a number, an
    expression, a template); ``mark_transfers_only`` — an equality mark
    passes only :data:`MARK_TRANSFERS` to its targets; ``not_read`` — the
    renderer of the type does not read the key."""
    if type_ not in _TYPES:
        return None
    if type_ in MARK_TRANSFERS:
        return None if key in MARK_TRANSFERS[type_] else 'mark_transfers_only'
    style, keys = _TYPES[type_]
    if style is None:
        return 'not_drawn'
    return None if key in keys else 'not_read'


def _builtin():
    if 'builtin' not in _CACHE:
        from ..style.config import StyleConfig
        _CACHE['builtin'] = StyleConfig.load(None)
    return _CACHE['builtin']


_MISSING = object()


def _default(cfg, style, key):
    value = cfg.defaults.get(style, key, _MISSING)
    if value is not _MISSING:
        return value
    if key in _RENDERING_DEFAULTS:
        name, fallback = _RENDERING_DEFAULTS[key]
        return cfg.rendering.get(name, fallback)
    return _RENDERER_DEFAULTS.get(key)


def _entry(cfg, type_):
    style, keys = _TYPES[type_]
    out = {'style': style, 'keys': {}}
    for key in sorted(keys):
        item = {'unit': _UNITS[key], 'default': _default(cfg, style, key)}
        values = _VALUE_ENUMS.get(key)
        if key == 'point_shape':
            from ..style.enums import POINT_SHAPES
            values = POINT_SHAPES
        if values is not None:
            item['values'] = list(values)
        out['keys'][key] = item
    if type_ in MARK_TRANSFERS:
        out['transfers'] = sorted(MARK_TRANSFERS[type_])
    return out


def style_keys() -> dict:
    """The keys of ``appearance.overrides`` each element type reads.

    ``{"format": "animageo-style-keys/v1", "types": {type: {"style":
    classic style type or None, "keys": {key: {"unit", "default"[,
    "values"]}}[, "transfers": [key, …]]}}}``. ``type`` is a document type,
    a mark by its operation (``mark.right_angle``, ``mark.equal_segments``,
    ``mark.equal_angles``); a type that is not drawn has no keys, an
    equality mark lists the keys it passes to its targets. ``default`` is
    the value under the built-in style (its ``defaults`` of the classic
    type, then its ``rendering``, then the renderer's own); ``None`` — no
    value (a solid stroke, an automatic layer or marker; ``label_anchor``:
    ``rendering.label_anchor`` of the given style, else ``BL``). A fresh
    copy.
    """
    if 'keys' not in _CACHE:
        cfg = _builtin()
        _CACHE['keys'] = {
            'format': STYLE_KEYS_FORMAT,
            'types': {type_: _entry(cfg, type_) for type_ in sorted(_TYPES)},
        }
    return copy.deepcopy(_CACHE['keys'])
