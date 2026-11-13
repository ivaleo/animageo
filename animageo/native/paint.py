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
import math

__all__ = ['PAINT_FORMAT', 'STYLE_KEYS_FORMAT', 'MARK_TRANSFERS', 'ineffective_reason', 'resolve_paint',
           'style_keys', 'style_type_of']

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
    # kinds of marks (animageo/mark_shapes.py)
    'arc_style': ('solid', 'dashed', 'wave'),
    'arrow_head': ('none', 'end', 'start', 'both'),
    'point_fill': ('solid', 'hollow'),
    'parallel_direction': ('forward', 'backward'),
}
# the values of a count key
_COUNT_VALUES = {'arc_tick_count': (0, 1, 2, 3), 'parallel_count': (0, 1, 2, 3)}
_UNITS = {
    'stroke': 'color', 'fill': 'color', 'label_color': 'color', 'hatch_color': 'color', 'label_halo_color': 'color',
    'stroke_width_px': 'px', 'stroke_dash_period_px': 'px', 'size_px': 'px', 'font_size_px': 'px',
    'label_radial_offset_px': 'px', 'tick_length_px': 'px', 'tick_width_px': 'px', 'tick_shift_px': 'px',
    'tick_radius_px': 'px', 'arrow_length_px': 'px', 'arrow_width_px': 'px', 'arc_size_px': 'px',
    'arc_shift_px': 'px', 'right_angle_size_px': 'px', 'hatch_spacing_px': 'px', 'hatch_width_px': 'px',
    'label_halo_px': 'px', 'parallel_size_px': 'px', 'parallel_shift_px': 'px',
    'stroke_opacity': 'opacity', 'fill_opacity': 'opacity', 'hatch_opacity': 'opacity', 'label_halo_opacity': 'opacity',
    'stroke_dash_ratio': 'ratio', 'stroke_dash_pattern_px': 'px[]', 'z_index_label': 'number',
    'hatch_angle_deg': 'deg',
    'tick_count': 'count', 'label_value_precision': 'count', 'arc_tick_count': 'count', 'parallel_count': 'count',
    'point_shape': 'enum', 'stroke_linecap': 'enum', 'tick_style': 'enum', 'angle_range': 'enum',
    'right_angle_joint': 'enum', 'label_anchor': 'enum', 'fill_pattern': 'enum', 'label_angle_unit': 'enum',
    'arc_style': 'enum', 'arrow_head': 'enum', 'point_fill': 'enum', 'parallel_direction': 'enum',
    'label_value_strip_zeros': 'bool', 'right_angle_marker': 'bool', 'auto_radius': 'bool',
    'label_value_separator': 'string',
    'z_index': 'number', 'z_index_fill': 'number',
}

_STROKE = ('stroke', 'stroke_width_px', 'stroke_opacity')
_DASH = ('stroke_dash_ratio', 'stroke_dash_period_px', 'stroke_dash_pattern_px')
_FILL = ('fill', 'fill_opacity')
_HATCH = ('fill_pattern', 'hatch_angle_deg', 'hatch_spacing_px', 'hatch_width_px', 'hatch_color', 'hatch_opacity')
_TICKS = ('tick_count', 'tick_style', 'tick_length_px', 'tick_width_px', 'tick_shift_px', 'tick_radius_px')
# the halo of a label: a stroke of its glyphs under them (``labels.resolve_label_halo``)
_HALO = ('label_halo_px', 'label_halo_color', 'label_halo_opacity')
_LABEL = ('label_color', 'font_size_px', 'label_anchor', 'z_index_label') + _HALO
_VALUE = ('label_value_precision', 'label_value_strip_zeros', 'label_value_separator')
_ANGLE = ('angle_range', 'arc_size_px', 'arc_shift_px', 'tick_count', 'auto_radius', 'right_angle_marker',
          'right_angle_size_px', 'right_angle_joint', 'label_radial_offset_px', 'label_angle_unit')
# kinds of marks (animageo/mark_shapes.py): the decoration of the arcs of an
# angle (not of a right-angle square), the chevrons of a parallel line
_ARC_DECOR = ('arc_style', 'arc_tick_count', 'tick_length_px', 'tick_shift_px', 'arrow_head', 'arrow_length_px',
              'arrow_width_px', 'stroke_dash_pattern_px')
_PARALLEL = ('parallel_count', 'parallel_size_px', 'parallel_shift_px', 'parallel_direction')

# document type (a mark by its operation) → (classic style type, keys read).
_TYPES = {
    'point': ('point', ('size_px', 'point_shape', 'point_fill') + _STROKE + _FILL + ('z_index',) + _LABEL),
    'segment': ('segment', _STROKE + ('stroke_linecap',) + _DASH + _TICKS
                + ('arrow_head', 'arrow_length_px', 'arrow_width_px') + _PARALLEL + ('z_index',) + _LABEL + _VALUE),
    'line': ('line', _STROKE + ('stroke_linecap',) + _DASH + _PARALLEL + ('z_index',) + _LABEL),
    'ray': ('ray', _STROKE + ('stroke_linecap',) + _DASH + _PARALLEL + ('z_index',) + _LABEL),
    'vector': ('vector', _STROKE + ('stroke_linecap',) + _DASH + _TICKS + ('arrow_length_px', 'arrow_width_px')
               + _PARALLEL + ('z_index',) + _LABEL + _VALUE),
    'circle': ('circle', _STROKE + _DASH + _FILL + _HATCH + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    'arc': ('arc', _STROKE + ('stroke_linecap',) + _DASH + _FILL + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    # the stroke of a sector is solid; its cap counts without ``sector_sides``
    'sector': ('circlesector', _STROKE + ('stroke_linecap',) + _FILL + _HATCH + ('z_index', 'z_index_fill')
               + _LABEL + _VALUE),
    'circlesegment': ('circlesegment', _STROKE + _FILL + _HATCH + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    # registry 1.9: the fill lies at ``z_index_fill``, the stroke above the lines as that of a
    # polygon; a dashed stroke is fitted to each ring
    'region': ('region', _STROKE + _DASH + _FILL + _HATCH + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    # a polygon keeps its legacy body layer; fill z is independent, stroke solid
    'polygon': ('polygon', _STROKE + _FILL + _HATCH + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    'polyline': ('locuscurve', _STROKE + _DASH + ('z_index',)),
    'locus': ('locuscurve', _STROKE + _DASH + ('z_index',)),
    # registry 1.6: a graph is a sampled curve without a label; a conic is
    # drawn as the classic Conic (an ellipse filled, the label on the curve)
    'function': ('function', _STROKE + _DASH + ('z_index',)),
    'conic': ('conic', _STROKE + _DASH + _FILL + ('z_index', 'z_index_fill') + _LABEL),
    'angle': ('angle', _STROKE + _FILL + _HATCH + _ANGLE + _ARC_DECOR + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    # a right-angle mark draws the square: no arcs to count, space or decorate
    # (with ``right_angle_marker: false`` it reads the keys of an angle, ``ineffective_reason``)
    'mark.right_angle': ('angle', _STROKE + _FILL + _HATCH
                         + tuple(k for k in _ANGLE if k not in ('tick_count', 'arc_shift_px'))
                         + ('z_index', 'z_index_fill') + _LABEL + _VALUE),
    'text': ('text', ('label_color', 'font_size_px', 'z_index') + _HALO),
    'mark.equal_segments': (None, ('stroke', 'tick_count')),
    'mark.equal_angles': (None, ('stroke', 'tick_count')),
    # registry 1.8: the chevrons of its targets
    'mark.parallel': (None, ('stroke', 'parallel_count', 'parallel_direction')),
    'number': (None, ()),
    'expr': (None, ()),
    'template': (None, ()),
}

# The appearance keys an equality mark contributes to its targets.
# Sizes and count keep the target's explicit priority. Since 1.11.0rc13
# stroke uses a separate decoration channel, never the target body's style;
# tick_count overrides the drawn count only, not the operation's value.
MARK_TRANSFERS = {
    'mark.equal_segments': ('stroke', 'tick_count', 'tick_length_px', 'tick_radius_px', 'tick_shift_px',
                            'tick_style', 'tick_width_px'),
    'mark.equal_angles': ('stroke', 'tick_count', 'arc_shift_px', 'arc_size_px', 'arc_style', 'arc_tick_count',
                          'tick_length_px', 'tick_shift_px'),
    # registry 1.8: the chevrons, a channel of their own (``parallelDecoration``);
    # ``parallel_direction`` turns those of every target (relative to the first)
    'mark.parallel': ('stroke', 'parallel_count', 'parallel_direction', 'parallel_shift_px', 'parallel_size_px'),
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
    # kinds of marks (``mark_shapes``): nothing more is drawn by default
    'arc_style': 'solid', 'arc_tick_count': 0, 'arrow_head': 'none', 'point_fill': 'solid',
    'parallel_count': 0, 'parallel_size_px': 8.0, 'parallel_shift_px': 3.5, 'parallel_direction': 'forward',
    # the ``rendering`` of the given style itself (``GeoStyle.rendering``, not
    # merged with the built-in one): ``label_anchor`` ``None`` is that of the
    # style, else ``BL``
    'stroke_linecap': 'butt', 'right_angle_joint': 'auto', 'label_anchor': None,
}
# Defaults from the ``rendering`` section of the built-in style (merged).
_RENDERING_DEFAULTS = {
    'label_value_precision': ('label_value_precision', 1),
    'stroke_dash_period_px': ('dash_period_px', 10),
    # ``None`` colour — the background colour
    'label_halo_px': ('label_halo_px', 0.0),
    'label_halo_color': ('label_halo_color', None),
    'label_halo_opacity': ('label_halo_opacity', 1.0),
}

# Defaults of a key by the classic type that are not in the built-in style:
# a constant, or ``(type, key)`` of the built-in style — the ticks across the
# arcs of an angle are those of a segment, the head of a segment that of a
# vector (``mark_shapes``).
_TYPE_DEFAULTS = {
    ('angle', 'tick_length_px'): ('segment', 'tick_length_px'),
    ('angle', 'tick_shift_px'): ('segment', 'tick_shift_px'),
    ('angle', 'arrow_length_px'): 6.0, ('angle', 'arrow_width_px'): 4.0,
    ('segment', 'arrow_length_px'): ('vector', 'arrow_length_px'),
    ('segment', 'arrow_width_px'): ('vector', 'arrow_width_px'),
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


def ineffective_reason(type_, key, style=None, arc_count=None):
    """Why ``key`` of ``appearance.overrides`` does nothing on an element of
    :func:`style_keys` type ``type_``, or ``None`` when it is read (or the
    type is unknown): ``not_drawn`` — the element is not drawn (a number, an
    expression, a template); ``mark_transfers_only`` — an equality mark
    passes only :data:`MARK_TRANSFERS` to its targets; ``single_arc`` —
    ``arc_shift_px`` of an angle with one arc (``tick_count`` ≤ 1, or
    ``arc_count`` — the drawn number of arcs, given by the caller); ``not_read`` — the
    renderer of the type does not read the key. ``style`` — the keys the
    element is given (1.11.0): a right-angle mark with ``right_angle_marker:
    false`` is drawn as the arcs of an angle and reads the keys of an
    angle."""
    if type_ not in _TYPES:
        return None
    if type_ == 'mark.right_angle' and (style or {}).get('right_angle_marker') is False:
        type_ = 'angle'
    if key == 'arc_shift_px' and type_ in ('angle', 'mark.equal_angles'):
        # the shift is the distance between several arcs: one arc has nothing to shift.
        # ``arc_count`` — the number of arcs drawn, known to the caller (a mark's count comes
        # from its operation, an angle's from the marks that target it); without it only an
        # explicit ``tick_count`` of ``style`` counts
        count = arc_count if arc_count is not None else (style or {}).get('tick_count')
        if isinstance(count, (int, float)) and not isinstance(count, bool) and count <= 1:
            return 'single_arc'
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
    if (style, key) in _TYPE_DEFAULTS:
        given = _TYPE_DEFAULTS[(style, key)]
        return cfg.defaults.get(*given, None) if isinstance(given, tuple) else given
    if key in _RENDERING_DEFAULTS:
        name, fallback = _RENDERING_DEFAULTS[key]
        return cfg.rendering.get(name, fallback)
    return _RENDERER_DEFAULTS.get(key)


def _entry(cfg, type_):
    style, keys = _TYPES[type_]
    out = {'style': style, 'keys': {}}
    for key in sorted(keys):
        item = {'unit': _UNITS[key], 'default': None if type_ in MARK_TRANSFERS else _default(cfg, style, key)}
        if type_ in MARK_TRANSFERS and key == 'tick_count':
            item['values'] = [0, 1, 2, 3]
        values = _VALUE_ENUMS.get(key, _COUNT_VALUES.get(key))
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
    equality mark lists the keys it contributes to its targets. Its own
    stroke and tick_count default to None (target stroke / semantic count).
    ``default`` is
    the value under the built-in style (its ``defaults`` of the classic
    type, then its ``rendering``, then the renderer's own); ``None`` — no
    value (a solid stroke, an automatic layer or marker; ``label_anchor``:
    ``rendering.label_anchor`` of the given style, else ``BL``). A fresh
    copy. 1.6: ``"view": {"section": "rendering", "keys": {…}}`` — the
    keys of the axes and the grid (``viewDefaults.axes``/``grid``), read
    from the ``rendering`` section of the style.
    """
    if 'keys' not in _CACHE:
        from .view import VIEW_STYLE_KEYS
        cfg = _builtin()
        _CACHE['keys'] = {
            'format': STYLE_KEYS_FORMAT,
            'rendering': {'keys': {'fill_order': {'unit': 'enum',
                'values': ['area', 'construction'], 'default': 'area'}}},
            'types': {type_: _entry(cfg, type_) for type_ in sorted(_TYPES)},
            'view': {'section': 'rendering', 'keys': {
                key: {'unit': unit, 'default': cfg.rendering.get(key, fallback)}
                for key, (unit, fallback) in sorted(VIEW_STYLE_KEYS.items())}},
        }
    return copy.deepcopy(_CACHE['keys'])


# ── Effective paint (resolve_paint) ─────────────────────────────────────

PAINT_FORMAT = 'animageo-paint/v1'

# ``_Z_AUTO_BY_TYPE`` of ``animageo.py`` (by the exact classic class; others
# lie at ``Z_FILL``), copied here to stay manim-free; a test compares the two.
_Z_AUTO_BY_CLASS = {'Polygon': 0.01, 'CircleSector': 0.01, 'CircleSegment': 0.01, 'Region': 0.01, 'Angle': 3.0,
                    'Segment': 5.0, 'Circle': 5.0, 'Arc': 5.0, 'Point': 50.0, 'Text': 50.0}
_Z_FILL = 0.01
_Z_FILL_LABEL = 0.1
_Z_STROKE = 5.0
_Z_LABEL = 50.0
_Z_ORDER_EPSILON = 1e-6
# the path a dash is fitted to (``AnimaGeoScene._dash_stroke``)
_DASH_FIT = {'segment': 'ends', 'vector': 'ends', 'arc': 'ends', 'circle': 'closed', 'line': 'none',
             'ray': 'none', 'region': 'closed'}
_CAPPED = ('segment', 'line', 'ray', 'vector', 'arc', 'sector')
_FILLED = ('circle', 'arc', 'sector', 'circlesegment', 'polygon', 'region')
_HATCHED = ('circle', 'sector', 'circlesegment', 'polygon', 'region')
_WITH_VALUE = ('segment', 'vector', 'circle', 'arc', 'sector', 'circlesegment', 'polygon', 'region', 'angle',
               'mark.right_angle')


def _num(value, default=0.0):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return out if math.isfinite(out) else float(default)


def _r(value):
    return None if value is None else round(float(value), 9) + 0.0


def _color(value):
    from ..style.colorspace import as_hex
    return as_hex(value) or (value if isinstance(value, str) else None)


def _apply_style_tracks(construction, final, extras, t) -> None:
    """The style tracks of ``extras`` (``rendering.timeline_extras``) at time
    ``t`` written into the elements as ``rendering._apply_extras`` leaves
    them, without the camera (the paint is in style pixels)."""
    from ..dash import rendering_dash_period_px
    from ..keyframes import KeyframeSequence
    from ..style.resolver import resolve

    seq = KeyframeSequence.from_json(extras, construction)
    if not seq.has_style_tracks():
        return

    def baseline(elem, key):
        default = rendering_dash_period_px(final) if key == 'stroke_dash_period_px' else None
        return resolve(final, elem, key, default=default)

    seq.bind_style_tracks(get_element=construction.element, resolve=baseline,
                          color_space=(final.style.rendering or {}).get('color_interpolation', 'oklab'))
    kfs = seq.keyframes
    t = max(kfs[0].t, min(float(t), kfs[-1].t))
    index = next((i for i, iv in enumerate(seq.intervals) if iv.start_t <= t <= iv.end_t), 0)

    def write(interval, p):
        for si in interval.style_interps:
            elem = construction.element(si.name)
            if elem is not None:
                elem.style[si.key] = si.at(p)

    for done in seq.intervals[:index]:
        write(done, 1.0)
        for fin in done.style_finalizers:
            elem = construction.element(fin[1])
            if elem is None:
                continue
            if fin[0] == 'set':
                elem.style[fin[2]] = fin[3]
            elif fin[3]:
                elem.style[fin[2]] = fin[4]
            elif fin[2] in elem.style:
                del elem.style[fin[2]]
    interval = seq.intervals[index]
    write(interval, 0.0 if interval.duration <= 0 else (t - interval.start_t) / interval.duration)


def _dash(final, elem, type_, data, unit, width_px, cap):
    """``{onPx, offPx, fit, drawn}`` of a dashed stroke or ``None``: the
    nominal pattern, the fit of its path and the pattern drawn
    (``dash.dash_pattern``; ``None`` for a vector, whose stem the renderer
    measures, and a sampled curve)."""
    from ..dash import dash_pattern, element_dash_px
    from ..geo import construction as geo
    nominal = element_dash_px(final, elem)
    if nominal is None:
        return None
    from ..dash import explicit_dash_px
    from ..style.resolver import resolve
    if explicit_dash_px(resolve(final, elem, 'stroke_dash_pattern_px', default=None)):
        return {'patternPx': [_r(v) for v in nominal], 'fit': 'none',
                'drawn': {'patternPx': [_r(v) for v in nominal], 'offsetPx': 0.0}}
    on_px, off_px = nominal
    fit = _DASH_FIT.get(type_)
    length = None
    if type_ in ('polyline', 'locus'):
        raw = getattr(data, 'points', None)
        pts = [(float(p[0]), float(p[1])) for p in (raw if raw is not None else ())]
        # ``_curve_polyline``: closed when the ends meet (numpy.allclose), a locus with gaps runs by runs
        closed = len(pts) > 2 and not getattr(data, 'breaks', None) and \
            all(abs(a - b) <= 1e-8 + 1e-5 * abs(b) for a, b in zip(pts[0], pts[-1]))
        fit = 'closed' if closed else 'none'
        if closed:
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    elif type_ == 'segment':
        (ax, ay), (bx, by) = data.endpoints
        length = math.hypot(bx - ax, by - ay)
        heads = _segment_heads(final, elem, data, unit)
        if heads is not None:           # the dash runs along the stem between the heads
            (ax, ay), (bx, by) = heads[1:3]
            length = math.hypot(bx - ax, by - ay)
    elif type_ == 'arc':
        a0, a1 = data.angles
        length = float(data.radius) * ((a1 - a0) % (2 * math.pi))
    elif type_ == 'circle' and isinstance(data, geo.Circle):
        length = 2 * math.pi * float(data.radius)
    elif type_ == 'function':           # open runs (``_curve_polyline``)
        fit = 'none'
    elif type_ == 'conic':              # the renderer measures an ellipse; branches are open runs
        fit = 'closed' if _conic_kind(data) == 'ellipse' else 'none'
    elif type_ == 'region':             # a pattern per ring (``_render_region``), ``drawn`` is None
        from .kernel.region import ring_length
        cap_mu = width_px / unit if cap in ('round', 'square') else 0.0
        rings = []
        for i in range(len(data.native_value['rings'])):
            pattern = dash_pattern(ring_length(data.native_value, i), on_px / unit, off_px / unit, closed=True,
                                   cap_extent_mu=cap_mu)
            rings.append({'onPx': _r(pattern.on * unit), 'offPx': _r(pattern.off * unit),
                          'offsetPx': _r(pattern.offset * unit)})
        return {'onPx': _r(on_px), 'offPx': _r(off_px), 'fit': fit, 'drawn': None, 'rings': rings}
    drawn = None
    if fit == 'none' or length is not None:
        cap_mu = width_px / unit if cap in ('round', 'square') else 0.0
        pattern = dash_pattern(length or 0.0, on_px / unit, off_px / unit, closed=(fit == 'closed'),
                               fit_ends=(fit == 'ends'), cap_extent_mu=cap_mu)
        drawn = {'onPx': _r(pattern.on * unit), 'offPx': _r(pattern.off * unit),
                 'offsetPx': _r(pattern.offset * unit)}
    return {'onPx': _r(on_px), 'offPx': _r(off_px), 'fit': fit, 'drawn': drawn}


def _conic_kind(data):
    native = getattr(data, 'native_value', None)
    return native.get('kind') if isinstance(native, dict) else None


def _ticks(type_, data, unit, value):
    """The ticks of a segment or a vector (``_append_tick_marks``): their
    style in px and, when there are any, their lines in world units
    (``lines``: ``[x1, y1, x2, y2]`` each) or the corners of the wave
    (``wave``: ``[[x, y], …]``, rounded by ``cornerRadius``, world units)."""
    count = int(_num(value('tick_count', 0), 0))
    style = value('tick_style', 'line') or 'line'
    length_px = _num(value('tick_length_px', 0.0))
    width_px = _num(value('tick_width_px', 0.0))
    shift_px = _num(value('tick_shift_px', 0.0))
    radius_px = value('tick_radius_px', None)
    out = {'count': count, 'style': style, 'lengthPx': _r(length_px), 'widthPx': _r(width_px),
           'shiftPx': _r(shift_px), 'radiusPx': None if radius_px is None else _r(_num(radius_px))}
    if count <= 0:
        return out
    (ax, ay), (bx, by) = ((float(p[0]), float(p[1])) for p in data.endpoints)
    if type_ == 'vector':
        nx, ny = ay - by, bx - ax
    else:
        nx, ny = (float(v) for v in data.normal)
    dl, nl = math.hypot(bx - ax, by - ay), math.hypot(nx, ny)
    if dl < 1e-12 or nl < 1e-12:
        return out
    vx, vy, nx, ny = (bx - ax) / dl, (by - ay) / dl, nx / nl, ny / nl
    mx, my = (ax + bx) / 2, (ay + by) / 2
    tick_len, tick_shift = length_px / unit, shift_px / unit
    if style == 'wave':
        s, l = tick_shift * 1.7, tick_len * 0.8
        radius = _num(radius_px) / unit if radius_px is not None else s * 0.45
        tt = (l - 2 * radius) / (s - 2 * radius) if s - 2 * radius else 0.0
        offset, sign, pts = tt * s / 2, 1, []
        d = s * ((1 - count) * 0.5) + s / 2 - (l / (2 * tt) if tt else 0.0)
        pts.append([mx + vx * d + nx * (l / 2) * sign, my + vy * d + ny * (l / 2) * sign])
        sign = -sign
        for i in range(1, count):
            d = s * ((1 - count) * 0.5 + i)
            pts.append([mx + vx * d + nx * offset * sign, my + vy * d + ny * offset * sign])
            sign = -sign
        d = s * ((1 + count) * 0.5) - s / 2 + (l / (2 * tt) if tt else 0.0)
        pts.append([mx + vx * d + nx * (l / 2) * sign, my + vy * d + ny * (l / 2) * sign])
        out['wave'] = [[_r(x), _r(y)] for x, y in pts]
        out['cornerRadius'] = _r(radius)
        return out
    hx, hy = nx * tick_len / 2, ny * tick_len / 2
    lines = []
    for i in range(count):
        d = tick_shift * ((1 - count) * 0.5 + i)
        cx, cy = mx + vx * d, my + vy * d
        lines.append([_r(cx + hx), _r(cy + hy), _r(cx - hx), _r(cy - hy)])
    out['lines'] = lines
    return out


def _angle(final, elem, data, unit, value):
    """The marker of an angle (``_render_angle``): the range, the base and
    the effective radius (``overlay.angle_radius``, ``auto_radius``), the
    arcs and their spacing, or the right-angle square; with
    ``rendering.angle_marker_fit`` — fitted to the sides (``fit``)."""
    from ..angle_marker import fit_settings, marker_fit
    from ..label_placement import compute_effective_arc_size_px
    from ..mark_shapes import arc_grow, arc_step_px, scene_arc_decor
    decor = scene_arc_decor(final, elem)
    angle_range = value('angle_range', 'minor') or 'minor'
    auto_radius = value('auto_radius', True)
    base_px = _num(value('arc_size_px', 17.0), 17.0)
    radius_px = float(compute_effective_arc_size_px(elem, data, final, base_px=base_px,
                                                    angle_range=angle_range, auto_radius=auto_radius))
    arcs = int(_num(value('tick_count', 0), 0))
    shift_px = _num(value('arc_shift_px', 0.0))
    size = float(data.size)
    shown = 2 * math.pi - size if (angle_range == 'minor' and size > math.pi) or \
        (angle_range == 'reflex' and size < math.pi) else size
    right = value('right_angle_marker', None)
    if getattr(elem, '_native_mark_explicit', False):
        right = False
    if right is None:
        right = abs(shown - math.pi / 2) <= 1e-8 + 1e-5 * math.pi / 2     # numpy.isclose of the renderer
        right = right and not decor.forces_arcs        # the square has no arcs to decorate
    right = bool(right)
    out = {'range': angle_range, 'autoRadius': auto_radius is not False, 'arcSizePx': _r(base_px),
           'radiusPx': _r(radius_px), 'arcs': arcs, 'arcShiftPx': _r(shift_px),
           'shownSize': _r(shown), 'right': right,
           'joint': value('right_angle_joint', (final.style.rendering or {}).get('right_angle_joint', 'auto'))}
    fit = marker_fit(final, elem) if fit_settings(final) is not None else None
    delta = fit.delta_px if fit is not None else 0.0
    if fit is not None:
        out['fit'] = {'supportWorld': [None if v is None else _r(v) for v in fit.support],
                      'limitPx': None if fit.limit_px is None else _r(fit.limit_px),
                      'clamped': fit.clamped, 'hidden': fit.hidden}
    if right:
        cfg = final.style_config.overlay.angle_radius or {}
        if cfg.get('enabled', False) and cfg.get('apply_to_right', False):
            square_px = radius_px
        else:
            square_px = _num(value('right_angle_size_px', base_px), base_px)
        if delta:
            square_px = square_px - math.sqrt(2) * delta
        out['rightSizePx'] = _r(square_px)
        r = square_px / math.sqrt(2) / unit
        vx, vy = (float(c) for c in data.vertex[:2])
        s1, s2 = ([float(c) for c in s[:2]] for s in (data.side1, data.side2))
        l1, l2 = math.hypot(*s1), math.hypot(*s2)
        if l1 > 0 and l2 > 0 and not (fit is not None and fit.hidden):
            n1 = (s1[0] * r / l1, s1[1] * r / l1)
            n2 = (s2[0] * r / l2, s2[1] * r / l2)
            out['square'] = [[_r(vx + n1[0]), _r(vy + n1[1])],
                             [_r(vx + n1[0] + n2[0]), _r(vy + n1[1] + n2[1])],
                             [_r(vx + n2[0]), _r(vy + n2[1])]]
    else:
        step = shift_px if decor.plain else arc_step_px(decor, shift_px, arcs)
        if not decor.plain:     # the floors of legibility (mark_shapes.arc_base_px)
            grown, capped = arc_grow(decor, radius_px, step, arcs, shown)
            if capped:              # the growth stops at 2 x the original: the floors yield
                out['arcGrowMaxPx'] = _r(grown)
            if grown != radius_px:
                out['arcGrowPx'] = _r(grown - radius_px)
                radius_px = grown
                out['radiusPx'] = _r(radius_px)
        if delta:
            radius_px = radius_px - delta
            out['radiusPx'] = _r(radius_px)
        drawn = 0 if fit is not None and fit.hidden else max(arcs, 0)
        radii = [radius_px + (arcs - 1 - i) * step for i in range(drawn)]
        out['arcRadiiPx'] = [_r(r) for r in radii]
        if not decor.plain and radii:
            flipped = (angle_range == 'minor' and size > math.pi) or (angle_range == 'reflex' and size < math.pi)
            if step != shift_px:
                out['arcStepPx'] = _r(step)
            out.update(_arc_marks(final, elem, data, unit, decor, radii, shown, flipped, value,
                                  'arcGrowMaxPx' in out))
    return out


def _arc_marks(final, elem, data, unit, decor, radii_px, shown, flipped, value, capped=False):
    """The decorated arcs of an angle (``mark_shapes.angle_marks``, the
    renderer's ``_append_arc_marks``), world units; only the fields of its
    decoration. A wave: each arc's samples ``φ_k = start + span·k/(16·N)``,
    ``ρ_k = r + A·sin(2π·(k mod 16)/16)``; a dashed arc: its fitted pattern."""
    from ..angle_marker import marker_extent
    from ..mark_shapes import (WAVE_AMPLITUDE_PX, WAVE_CAPPED_MIN_PERIOD_PX, WAVE_GAP_PX, WAVE_MIN_PERIOD_PX, WAVE_PERIOD_PX, WAVE_SAMPLES,
                               angle_marks, arrow_fit)
    vx, vy = (float(c) for c in data.vertex[:2])
    start = math.atan2(float(data.side2[1]), float(data.side2[0])) if flipped else float(data.start_angle)
    marks = angle_marks((vx, vy), [r / unit for r in radii_px], start, shown, flipped, decor, unit, capped)
    out = {}
    if decor.style != 'solid':
        out['arcStyle'] = decor.style
    if not marks.arcs:                  # an angle of no size: nothing is drawn
        out['arcRadiiPx'] = []
        return out
    paths = [{'radiusPx': _r(arc.radius * unit), 'startAngle': _r(arc.start), 'span': _r(arc.span)}
             for arc in marks.arcs]
    if decor.style == 'wave':
        out['wave'] = {'amplitudePx': WAVE_AMPLITUDE_PX, 'periodPx': WAVE_PERIOD_PX,
                       'samplesPerPeriod': WAVE_SAMPLES, 'gapPx': WAVE_GAP_PX, 'minPeriodPx': WAVE_MIN_PERIOD_PX,
                       'periods': marks.arcs[0].periods,
                       'arcs': [dict(path, periods=arc.periods, points=[[_r(x), _r(y)] for x, y in arc.points])
                                for path, arc in zip(paths, marks.arcs)]}
        if capped:
            out['wave']['cappedMinPeriodPx'] = WAVE_CAPPED_MIN_PERIOD_PX
    elif decor.style == 'dashed':
        out['arcDashes'] = [dict(path, onPx=_r(arc.dash.on * unit), offPx=_r(arc.dash.off * unit),
                                 offsetPx=_r(arc.dash.offset * unit), dashes=arc.dashes,
                                 periodPx=None if arc.period_px is None else _r(arc.period_px))
                            for path, arc in zip(paths, marks.arcs)]
    if decor.ticks > 0:
        out['arcTicks'] = {'count': decor.ticks, 'lengthPx': _r(decor.tick_length_px),
                           'shiftPx': _r(decor.tick_shift_px),
                           'widthPx': _r(_num(value('stroke_width_px', 1.0), 1.0)),
                           'lines': [[_r(c) for c in line] for line in marks.ticks]}
    if decor.arrow != 'none':
        length, width = arrow_fit(decor.arrow_length_px, decor.arrow_width_px, radii_px[0], shown,
                                  decor.arrow == 'both')
        outer = marks.arcs[0]
        out['arrow'] = {'head': decor.arrow, 'lengthPx': _r(decor.arrow_length_px),
                        'widthPx': _r(decor.arrow_width_px), 'drawnLengthPx': _r(length),
                        'drawnWidthPx': _r(width), 'tips': [[_r(c) for c in tip] for tip in marks.tips],
                        'stemEndAngles': [_r(outer.start), _r(outer.start + outer.span)]}
    overhang = marker_extent(final, elem).overhang_px
    if overhang:
        out['overhangPx'] = _r(overhang)
    return out


def _segment_heads(final, elem, data, unit):
    """``(head, stem_a, stem_b, tips)`` of a segment with ``arrow_head``
    (``mark_shapes.segment_arrow``) or ``None``."""
    from ..mark_shapes import scene_segment_arrow, segment_arrow
    head, length_px, width_px = scene_segment_arrow(final, elem)
    if head == 'none':
        return None
    geometry = segment_arrow(data.endpoints[0], data.endpoints[1], head, length_px, width_px, unit)
    if geometry is None:
        return None
    return (head,) + tuple(geometry)


def _parallel(final, elem, type_, data, value, unit):
    """The chevrons of a parallel line (``mark_shapes.scene_chevrons``) or
    ``None`` without them: in the middle of a segment or a vector (past its
    ticks), of the drawn part of a line or a ray, pointing along it."""
    from ..label_placement import _clipped_line_endpoints
    from ..mark_shapes import parallel_decor, scene_chevrons
    decor = parallel_decor(value)
    if decor.count <= 0:
        return None
    out = {'count': decor.count, 'sizePx': _r(decor.size_px), 'depthPx': _r(decor.size_px / 2),
           'shiftPx': _r(decor.shift_px), 'direction': decor.direction, 'chevrons': []}
    if type_ in ('segment', 'vector'):
        (ax, ay), (bx, by) = ((float(p[0]), float(p[1])) for p in data.endpoints)
        mid, v = ((ax + bx) / 2, (ay + by) / 2), (bx - ax, by - ay)
    else:
        ends = _clipped_line_endpoints(final, data)
        if ends is None:
            return out
        mid = ((ends[0][0] + ends[1][0]) / 2, (ends[0][1] + ends[1][1]) / 2)
        v = tuple(float(c) for c in data.direction[:2])
    out['chevrons'] = [[_r(c) for c in ch]
                       for ch in scene_chevrons(final, elem, mid, v, unit, ticks=type_ in ('segment', 'vector'))]
    return out


def _decoration(final, elem, type_, unit, value, stroke_color):
    """Effective equality paint shared by paint and rendered-frame reports.

    Owners are document IDs even when classic names differ from them.
    """
    owner = getattr(elem, '_native_mark_id', None)
    if owner is None:
        return None
    out = {'owner': owner, 'color': _color(getattr(elem, '_native_mark_stroke', None) or stroke_color)}
    if type_ in ('segment', 'vector'):
        ticks = _ticks(type_, elem.data, unit, value)
        out.update({k: v for k, v in ticks.items() if k not in ('lines', 'wave', 'cornerRadius')})
        if ticks.get('cornerRadius') is not None:
            out['radiusPx'] = _r(ticks['cornerRadius'] * unit)
        out['kind'] = 'ticks'
    elif type_ == 'angle':
        angle = _angle(final, elem, elem.data, unit, value)
        out.update({k: angle[k] for k in ('arcSizePx', 'radiusPx', 'arcShiftPx')})
        out.update(kind='square' if angle['right'] else 'arcs', count=1 if angle['right'] else angle['arcs'],
                   widthPx=_r(_num(value('stroke_width_px', 1), 1)))
        if 'arcStyle' in angle:
            out['arcStyle'] = angle['arcStyle']
        if 'arcTicks' in angle:
            out['arcTicks'] = angle['arcTicks']['count']
    else:
        return None
    return out


def _parallel_decoration(elem, value, stroke_color):
    """The chevrons a parallel mark gives (registry 1.8), shared by paint and
    rendered-frame reports: its document-ID ``owner``, the actual ``color``
    (the mark's stroke, else the target's), the ``count``, ``sizePx``,
    ``shiftPx`` and the ``direction`` drawn; ``None`` when no parallel mark
    owns the chevrons of ``elem``."""
    from ..mark_shapes import parallel_decor
    owner = getattr(elem, '_native_parallel_id', None)
    if owner is None:
        return None
    decor = parallel_decor(value)
    return {'owner': owner, 'color': _color(getattr(elem, '_native_parallel_stroke', None) or stroke_color),
            'count': decor.count, 'sizePx': _r(decor.size_px), 'shiftPx': _r(decor.shift_px),
            'direction': decor.direction}


def _scene_decoration(scene, elem, type_):
    """Resolve a rendered scene through the same lazy classic boundary as paint."""
    from ..label_placement import _style_ptUnit
    from ..style.resolver import resolve

    def value(key, default=None):
        return resolve(scene, elem, key, default=default)

    return _decoration(scene, elem, type_, _style_ptUnit(scene.style), value, value('stroke', scene.style.strong))


def _scene_parallel_decoration(scene, elem, type_):
    """:func:`_parallel_decoration` of a rendered scene."""
    from ..style.resolver import resolve

    def value(key, default=None):
        return resolve(scene, elem, key, default=default)

    if type_ not in ('segment', 'vector', 'line', 'ray'):
        return None
    return _parallel_decoration(elem, value, value('stroke', scene.style.strong))


def _value_format(final, value):
    from ..labels import DEFAULT_LABEL_VALUE_PRECISION, _rendering_default
    precision = value('label_value_precision',
                      _rendering_default(final, 'label_value_precision', DEFAULT_LABEL_VALUE_PRECISION))
    try:
        precision = max(0, int(precision))
    except (TypeError, ValueError):
        precision = DEFAULT_LABEL_VALUE_PRECISION
    return {'precision': precision, 'stripZeros': bool(value('label_value_strip_zeros', True)),
            'separator': str(value('label_value_separator', ' = ')),
            'angleUnit': value('label_angle_unit', 'degree')}


def _label(final, elem, value, type_, z_label):
    from ..label_placement import ANCHOR_EDGES
    from ..labels import resolve_label_halo, resolve_label_parts, resolve_label_text
    from .labels.layout import _label_geometry, _shown
    out = {'color': _color(value('label_color', '#000000')),
           'fontSizePx': _r(_num(value('font_size_px', 14.0), 14.0))}
    halo = resolve_label_halo(final, elem)
    out['halo'] = {'widthPx': _r(halo['widthPx']), 'color': halo['color'], 'opacity': _r(halo['opacity'])}
    if type_ == 'text':             # the text itself
        return out
    shown = _shown(final, elem)
    out['shown'] = shown
    anchor = value('label_anchor', (final.style.rendering or {}).get('label_anchor'))
    name = anchor if isinstance(anchor, str) and anchor in ANCHOR_EDGES else ('BL' if anchor is None else None)
    out['anchor'] = name
    if type_ in ('angle', 'mark.right_angle'):
        out['radialOffsetPx'] = _r(_num(value('label_radial_offset_px', 0.0)))
    if shown:
        out['z'] = z_label
        spot, _center, _half, off, _ = _label_geometry(final, elem, None)
        out['text'] = resolve_label_text(final, elem)
        out['parts'] = resolve_label_parts(final, elem)
        out['spotWorld'] = [_r(spot[0]), _r(spot[1])]
        out['offsetWorld'] = [_r(off[0]), _r(off[1])]
    return out


def resolve_paint(doc, style_config=None, t=None, *, timeline=None, inputs=None, export_layout=None) -> dict:
    """The paint ``native.render`` draws each element of ``doc`` with, in
    style pixels, without manim.

    ``style_config``, ``export_layout`` and ``inputs`` are those of
    ``native.render``; ``t`` with ``timeline`` — the frame of the video at
    ``t``: inputs and visibility of ``sample_timeline``, an element in an
    enter or exit effect drawn as ``timeline_effects`` says (``present``;
    its entry gains ``effect`` ``{phase, effect, progress}`` once the effect
    has begun, the paint is that of the element in full), and the style
    tracks of the timeline (its camera does not change the paint). Returns
    ``{"format": "animageo-paint/v1", "background", "ptUnit",
    "ptUnitStyle", "t", "elements": {id: entry}, "order": [id, …],
    "fillOrder": [id, …], "partOrder": [{id, part}, …], "diagnostics"}``: ``ptUnit`` — output pixels per world unit,
    ``ptUnitStyle`` — style pixels per world unit (decorations: world =
    px / ptUnitStyle), ``order`` — the drawn elements by layer, bottom up,
    ``fillOrder`` — all actual area fills, ``partOrder`` — their merge with
    nonfill parts at exact effective layers; native defaults to area order,
    classic scenes to construction. ``diagnostics`` — those of ``appearance_plan``.

    An entry: ``type``, ``styleType`` (of :func:`style_keys`), ``style``
    (the classic style type), ``drawn``; for a drawn element ``z`` (its
    layer, construction order breaking ties) and, by type, ``stroke``
    ``{color, opacity, widthPx, cap, dash}``, ``fill`` ``{color, opacity,
    isBackground, z, hatch}`` (the opacity drawn: an angle filled with the
    background colour has none), ``point`` ``{sizePx, shape, display}``,
    ``arrow`` ``{lengthPx, widthPx}``, ``ticks`` (count, style, sizes, the
    lines or the wave in world units), ``angle`` (range, base and effective
    radius, arcs or the right-angle square), ``label`` ``{shown, color,
    fontSizePx, halo, anchor, radialOffsetPx, text, parts, spotWorld,
    offsetWorld}`` (the placement solver is not run: :func:`layout_labels`
    does; ``halo`` ``{widthPx, color, opacity}`` — ``labels.resolve_label_halo``,
    ``widthPx`` ``0`` draws none; ``parts`` — the runs of ``text``
    ``[{text, italic, script}]``, ``labels.resolve_label_parts``, ``None`` for
    a caption; a free text has ``color``, ``fontSizePx`` and ``halo``) and ``value``
    ``{precision, stripZeros, separator, angleUnit}``.
    Equality targets also have ``decoration``: its document-ID ``owner``,
    actual ``color``, ``count`` and sizes in style pixels,
    separately from the target's ``stroke`` and ``fill``. The targets of a
    parallel mark (registry 1.8) have ``parallelDecoration`` ``{owner,
    color, count, sizePx, shiftPx, direction}`` beside ``parallel`` (the
    chevrons drawn), a channel of its own.
    """
    from types import SimpleNamespace

    from ..dash import element_dash_px
    from ..export_layout import normalize_content_options, rendered_view_from_bounds, \
        source_view_from_bounds_px, static_export_dict
    from ..geo import construction as geo
    from ..label_placement import DOT_SIZE_PX, LayoutInput, _style_ptUnit
    from ..style.resolver import etype_of, resolve
    from .document import as_document
    from .kernel.bridge import build_construction
    from .kernel.evaluate import check_inputs, evaluate
    from .labels.layout import _drawing_bounds, _load_style, frame_bounds, measure_metrics
    from .rendering import _check_layout, appearance_plan, apply_appearance, document_at, source_view, \
        timeline_extras

    layout = _check_layout(export_layout)
    doc = as_document(doc)
    sample = None
    if t is not None or timeline is not None:
        if t is None or timeline is None:
            raise ValueError('native.resolve_paint: t and timeline go together')
        from .timeline import sample_timeline, timeline_effects
        sample = sample_timeline(doc, timeline, t)
        merged = dict(sample['inputs'])
        merged.update(inputs or {})
        inputs = merged
        effects = timeline_effects(doc, timeline, t)
        # the frame of the video: an element in its effect is in it as the effect says
        present = dict(sample['visible'])
        present.update({el_id: e['present'] for el_id, e in effects.items()})
        doc = document_at(doc, {'visible': present})
    check_inputs(doc, inputs)
    ev = evaluate(doc, inputs=inputs)

    cfg, rendering = _load_style(style_config)
    view = source_view(doc)
    view['ptUnit_ggb'] = view['ptUnit']
    construction, names = build_construction(doc, inputs=inputs)
    construction.rebuild(full=True)
    plan, diagnostics = appearance_plan(doc, view['ptUnit'], inputs=inputs, evaluated=ev,
                                        roles=cfg.source.get('roles'))
    apply_appearance(construction, names, plan)
    kwargs = {'style_reference': getattr(cfg, 'reference', {}), 'reference': layout.get('reference'),
              'content': layout.get('content'), 'export': layout.get('export')}

    def scene(export):
        return LayoutInput(geo=construction, style=SimpleNamespace(export=export, rendering=rendering),
                           style_config=cfg, bounds=frame_bounds(export), measure_label=measure_metrics,
                           label_point_clearance=True)

    rendered = None
    content = normalize_content_options(layout.get('content'))
    if content['source'] == 'rendered_bounds':        # as layout_labels, without the placement solver
        policy = content.get('infinite_policy', 'ignore')
        if content.get('bounds') is not None:
            rendered = source_view_from_bounds_px(view, content['bounds'], infinite_policy=policy)
        else:
            reserve = content.get('label_bounds', 'reserve') != 'exclude'
            bounds = _drawing_bounds(scene(dict(view)), policy, reserve, {})
            rendered = rendered_view_from_bounds(view, bounds, infinite_policy=policy)
    export = static_export_dict(view, **kwargs, rendered_view=rendered)
    final = scene(export)
    if sample is not None:
        extras = timeline_extras(doc, timeline)
        if extras is not None:
            _apply_style_tracks(construction, final, extras, t)

    unit = float(_style_ptUnit(final.style))
    background = cfg.presets.get('color', {}).get('background', '#ffffff')
    strong = cfg.presets.get('color', {}).get('strong', '#000000')
    from ..fill_order import PaintPart, fill_layer, make_fill_part, order_fills, order_paint_parts, resolve_mode, stable_index
    mode = resolve_mode(final, default='area')
    elements, layers, fills, parts = {}, [], [], []
    for el_id in sorted(doc.elements):
        type_ = doc.elements[el_id].get('type')
        style_type = style_type_of(doc, el_id)
        elem = construction.objectByName(names.by_id[el_id])
        entry = {'type': type_, 'styleType': style_type,
                 'style': _TYPES.get(style_type, (None, ()))[0], 'drawn': False}
        elements[el_id] = entry
        effect = effects.get(el_id) if sample is not None else None
        if effect is not None and effect['progress'] > 0:
            entry['effect'] = {'phase': effect['phase'], 'effect': effect['effect'], 'progress': _r(effect['progress'])}
        if not isinstance(elem, geo.Element) or not geo.is_drawn(elem.data):
            continue
        if not resolve(final, elem, 'visible', default=getattr(elem, 'visible', True)):
            continue
        entry['drawn'] = True
        entry['style'] = etype_of(elem)
        data = elem.data

        def value(key, default=None, _elem=elem):
            return resolve(final, _elem, key, default=default)

        z = value('z_index', None)
        if z is None:
            z = _Z_AUTO_BY_CLASS.get(type(data).__name__, _Z_FILL)
        tie = construction.elements.index(elem) * _Z_ORDER_EPSILON
        entry['z'] = _r(_num(z) + tie)
        default_label_z = _Z_FILL_LABEL if _num(z) == _Z_FILL else _Z_LABEL
        label_layer = _num(value('z_index_label', None), default_label_z) + tie
        z_label = _r(label_layer)
        layers.append((_num(z) + tie, el_id))
        point = style_type == 'point'
        stroke_default = strong              # ``_build_render_ctx``: ``style.strong``, a point filled with it
        fill_default = strong if point else background
        if style_type != 'text':
            width_px = _num(value('stroke_width_px', 1.0), 1.0)
            cap = value('stroke_linecap', (rendering or {}).get('line_cap', 'butt')) \
                if style_type in _CAPPED else None
            if style_type == 'sector' and value('sector_sides', False) is True:
                cap = None
            if element_dash_px(final, elem) is not None and cap is not None:
                cap = 'butt'
            stroke = {'color': _color(value('stroke', stroke_default)),
                      'opacity': _r(_num(value('stroke_opacity', 1), 1)),
                      'widthPx': _r(width_px), 'cap': cap, 'z': entry['z']}
            if style_type in ('polygon', 'region'):     # the stroke layer above the fill (``_render_polygon``)
                stroke['z'] = _r(max(_Z_STROKE + tie, _num(z) + tie + 0.1))
            elif style_type in ('angle', 'mark.right_angle'):
                stroke['z'] = _r(_num(z) + tie + 0.1)
            if style_type in _DASH_FIT or style_type in ('polyline', 'locus', 'function', 'conic'):
                stroke['dash'] = _dash(final, elem, style_type, data, unit, width_px, cap)
            entry['stroke'] = stroke
        if style_type in _FILLED or style_type in ('angle', 'mark.right_angle', 'point') \
                or (style_type == 'conic' and _conic_kind(data) == 'ellipse'):
            color = _color(value('fill', fill_default))
            opacity = _num(value('fill_opacity', 1), 1)
            from ..style.colorspace import same_color
            is_bg = same_color(color, background)
            if style_type in ('angle', 'mark.right_angle') and is_bg:
                opacity = 0.0
            fill = {'color': color if opacity > 0 else None, 'opacity': _r(opacity), 'isBackground': is_bg}
            if not point:
                fill['z'] = _r(fill_layer(final, elem, _num(z), tie, mode=mode)[0])
            angle_pattern = style_type in ('angle', 'mark.right_angle') and \
                (value('fill_pattern', 'solid') or 'solid') != 'solid'
            if style_type in _HATCHED or angle_pattern:      # an angle reports only a pattern
                pattern = value('fill_pattern', 'solid') or 'solid'
                hatch = None
                if pattern not in ('solid', 'none'):
                    from ..hatch import hatch_spec
                    spec = hatch_spec(lambda e, k, d: resolve(final, e, k, default=d), elem, unit)
                    hatch = {'pattern': pattern, 'angleDeg': _r(math.degrees(spec['angle'])),
                             'spacingPx': _r(spec['spacing_px']), 'widthPx': _r(spec['width_px']),
                             'color': _color(spec['color']) if spec['color'] is not None else stroke['color'],
                             'opacity': _r(spec['opacity'])}
                fill['pattern'] = pattern
                fill['hatch'] = hatch
            entry['fill'] = fill
        if point:
            from ..mark_shapes import hollow_size_px, point_hole
            given = _num(value('size_px', DOT_SIZE_PX), DOT_SIZE_PX)
            # a hollow point is at least so large that its hole shows
            size = hollow_size_px(value('point_shape', 'circle'), given, value('point_fill', 'solid'),
                                  _num(export['ptUnit'], 1.0) / unit)
            entry['point'] = {'sizePx': _r(size),
                              'shape': value('point_shape', 'circle'),
                              'display': (rendering or {}).get('points_display', 'auto') or 'auto'}
            if size != given:
                entry['point']['givenSizePx'] = _r(given)
            hole = point_hole(entry['point']['shape'], size, value('point_fill', 'solid'))
            if hole is not None:        # a hole of the shape at half size, the sheet's colour on a solid sheet
                entry['point'].update(fill='hollow', ringPx=_r(hole.ring_px),
                                      hole={'shape': hole.shape, 'radiusPx': _r(hole.radius_px)},
                                      innerColor=_color(background))
        if style_type == 'vector':
            entry['arrow'] = {'lengthPx': _r(_num(value('arrow_length_px', 0.0))),
                              'widthPx': _r(_num(value('arrow_width_px', 0.0)))}
        if style_type == 'segment':
            heads = _segment_heads(final, elem, data, unit)
            if heads is not None:
                from ..mark_shapes import scene_segment_arrow
                _head, length_px, width_px = scene_segment_arrow(final, elem)
                entry['arrow'] = {'head': heads[0], 'lengthPx': _r(length_px), 'widthPx': _r(width_px),
                                  'stem': [_r(c) for c in (*heads[1], *heads[2])],
                                  'tips': [[_r(c) for c in tip] for tip in heads[3]]}
        if style_type in ('segment', 'vector', 'line', 'ray'):
            parallel = _parallel(final, elem, style_type, data, value, unit)
            if parallel is not None:
                entry['parallel'] = parallel
            parallel = _parallel_decoration(elem, value, entry.get('stroke', {}).get('color'))
            if parallel is not None:
                entry['parallelDecoration'] = parallel
        if style_type in ('segment', 'vector'):
            entry['ticks'] = _ticks(style_type, data, unit, value)
        if style_type in ('angle', 'mark.right_angle'):
            entry['angle'] = _angle(final, elem, data, unit, value)
        decoration = _decoration(final, elem, style_type, unit, value, entry.get('stroke', {}).get('color'))
        if decoration is not None:
            entry['decoration'] = decoration
        if style_type not in ('polyline', 'locus', 'function'):
            entry['label'] = _label(final, elem, value, style_type, z_label)
        if style_type in _WITH_VALUE:
            entry['value'] = _value_format(final, value)
        stable = lambda local: stable_index(construction, elem, local)
        fill_part = make_fill_part(final, elem, id=el_id, base_z=_num(z), tie=tie, mode=mode)
        if fill_part is not None:
            fills.append(fill_part)
            parts.append(PaintPart(el_id, 'fill', fill_part.layer_z, stable(0)))
        marker = entry.get('angle')
        hidden_marker = bool(((marker or {}).get('fit') or {}).get('hidden'))
        stroke_layer = _num(z) + tie
        if style_type in ('polygon', 'region'):
            stroke_layer = max(_Z_STROKE + tie, _num(z) + tie + .1)
        elif style_type in ('angle', 'mark.right_angle'):
            stroke_layer = _num(z) + tie + .1
        if style_type == 'text':
            halo = entry['label'].get('halo', {})
            if halo.get('widthPx', 0) > 0 and halo.get('opacity', 0) > 0:
                parts.append(PaintPart(el_id, 'labelHalo', _num(z) + tie, stable(4)))
            parts.append(PaintPart(el_id, 'body', _num(z) + tie, stable(5)))
        elif style_type == 'point':
            closed = entry['point']['shape'] not in ('cross', 'plus')
            visible_body = (entry['stroke']['opacity'] > 0 and width_px > 0) or \
                (closed and (entry['fill']['opacity'] > 0 or entry['point'].get('fill') == 'hollow'))
            if entry['point']['display'] != 'only_labels' and entry['point']['sizePx'] > 0 and visible_body:
                parts.append(PaintPart(el_id, 'body', _num(z) + tie, stable(0)))
        elif not hidden_marker and entry.get('stroke', {}).get('opacity', 0) > 0 and width_px > 0:
            if marker is None or marker.get('right') or marker.get('arcRadiiPx'):
                parts.append(PaintPart(el_id, 'stroke', stroke_layer, stable(1)))
        if entry.get('ticks', {}).get('count', 0) > 0:
            parts.append(PaintPart(el_id, 'ticks', _num(z) + tie, stable(2)))
        if entry.get('parallel', {}).get('chevrons'):
            parts.append(PaintPart(el_id, 'parallel', _num(z) + tie, stable(3)))
        if entry.get('label', {}).get('shown'):
            halo = entry['label'].get('halo', {})
            if halo.get('widthPx', 0) > 0 and halo.get('opacity', 0) > 0:
                parts.append(PaintPart(el_id, 'labelHalo', label_layer, stable(4)))
            parts.append(PaintPart(el_id, 'label', label_layer, stable(5)))
    from .view import view_layout, view_settings, view_style
    settings = view_settings(doc)
    if settings is not None:
        st = view_style(cfg.rendering)
        u = float(export['ptUnit'])
        left, top = -export['ptXZero']/u, export['ptYZero']/u
        rect = (left, top-int(export['ptHeight'])/u, left+int(export['ptWidth'])/u, top)
        layout = view_layout(settings, rect, margin=st['axes_font_size_px']/unit)
        for i, (kind, z) in enumerate((('minor', -21), ('major', -20))):
            if any(layout['grid'][kind].values()) and st['grid_' + ('minor_' if kind == 'minor' else '') + 'opacity'] > 0 \
                    and st['grid_' + ('minor_' if kind == 'minor' else '') + 'width_px'] > 0:
                parts.append(PaintPart('@view.' + kind, 'stroke', z, (-1, i, 0)))
        if any(layout['axes'].values()) and st['axes_opacity'] > 0:
            if st['axes_width_px'] > 0:
                parts.append(PaintPart('@view.axes', 'stroke', -10, (-1, 2, 0)))
            if any(layout['numbers'].values()) or any(layout['labels'].values()):
                parts.append(PaintPart('@view.labels', 'label', -9, (-1, 3, 0)))
    fill_order = order_fills(fills, mode=mode)
    part_order = order_paint_parts(parts, fill_order)
    order = [el_id for _, el_id in sorted(layers)]
    return {
        'format': PAINT_FORMAT,
        'background': _color(background),
        'ptUnit': _r(export['ptUnit']),
        'ptUnitStyle': _r(unit),
        't': None if sample is None else sample['t'],
        'elements': elements,
        'order': order,
        'fillOrder': list(fill_order),
        'partOrder': list(part_order),
        'diagnostics': diagnostics,
    }


# ── The style contract for code generation (``native/style``) ───────────

def _style_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent / 'style'


def style_contract_files() -> dict:
    """``{file name: bytes}`` of ``animageo/native/style``: ``builtin.json`` —
    the built-in style byte for byte (``animageo/style/builtin.json``),
    ``keys.v1.json`` — :func:`style_keys`. The web generates its base of the
    style and its keys of ``overrides`` from them."""
    import json
    from pathlib import Path

    from ..style.config import BUILTIN_STYLE_PATH
    keys = json.dumps(style_keys(), ensure_ascii=False, indent=1) + '\n'
    return {'builtin.json': Path(BUILTIN_STYLE_PATH).read_bytes(), 'keys.v1.json': keys.encode('utf-8')}


def write_style_contract(directory=None) -> list:
    """Write :func:`style_contract_files` into ``directory`` (default: the
    shipped ``animageo/native/style``); the paths written."""
    from pathlib import Path
    directory = Path(directory) if directory is not None else _style_dir()
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in sorted(style_contract_files().items()):
        path = directory / name
        path.write_bytes(data)
        written.append(path)
    return written


def check_style_contract(directory=None) -> list:
    """Files of ``directory`` that differ from :func:`style_contract_files`."""
    from pathlib import Path
    directory = Path(directory) if directory is not None else _style_dir()
    problems = []
    files = style_contract_files()
    for name, data in sorted(files.items()):
        path = directory / name
        if not path.is_file():
            problems.append(f'{path}: missing')
        elif path.read_bytes() != data:
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')) if directory.is_dir() else ():
        if path.name not in files:
            problems.append(f'{path}: not written here')
    return problems
