"""Resolve ggb_raw values into canonical import-style dictionaries.

This mirrors the GeoGebra-to-style conversion logic of
``ggb_parser.parse_constr()`` but works from the captured ``ggb_raw`` dict
instead of re-reading XML. It is used by ``ImportPolicy.faithful()`` and
``AnimaGeo.reloadPolicy()`` to re-derive ``elem.ggb_style`` without a second
parse.
"""
from .scaling import (
    ggb_point_size_to_style,
    ggb_thickness_to_stroke_width,
    ggb_arc_size_px,
    ggb_label_offset_to_style,
)
from .enums import ggb_point_style_to_elem_style


def _rgb_to_hex(r, g, b):
    return '#%02x%02x%02x' % (r, g, b)


def _label_mode_to_style(value):
    if value in (1, 9):
        return 'label_value'
    if value == 2:
        return 'value'
    return 'label'


def resolve_ggb_style(ggb_raw: dict) -> dict:
    """Derive canonical import-style values from raw GGB values."""
    style: dict = {}
    etype = ggb_raw.get('elem_type')

    if 'decoration_lines' in ggb_raw:
        lines = ggb_raw['decoration_lines']
        if etype == 'angle':
            lines += 1
        style['tick_count'] = lines

    if 'show_object' in ggb_raw:
        style['visible'] = ggb_raw['show_object']
        style['label_visible'] = ggb_raw['show_label']

    if 'label_mode' in ggb_raw:
        style['label_mode'] = _label_mode_to_style(ggb_raw['label_mode'])

    if 'label_caption' in ggb_raw and ggb_raw.get('label_mode') in (3, 9):
        style['label_text'] = '$' + ggb_raw['label_caption'] + '$'
    if 'label_dynamic_caption' in ggb_raw and ggb_raw.get('label_mode') in (3, 9):
        style['label_dynamic_caption'] = ggb_raw['label_dynamic_caption']

    if 'angle_style' in ggb_raw:
        style['angle_range'] = 'reflex' if ggb_raw['angle_style'] == 2 else 'minor'

    if 'point_size' in ggb_raw:
        style['size_px'] = ggb_point_size_to_style(ggb_raw['point_size'])

    if 'label_offset_px' in ggb_raw:
        x, y = ggb_raw['label_offset_px']
        style['label_offset_px'] = ggb_label_offset_to_style(x, y)
    else:
        style['label_offset_px'] = [0, 0]

    if 'arc_size' in ggb_raw and etype == 'angle':
        style['arc_size_px'] = ggb_arc_size_px(ggb_raw['arc_size'])

    if 'obj_color' in ggb_raw:
        c = ggb_raw['obj_color']
        r, g, b, a = c['r'], c['g'], c['b'], c['alpha']
        hex_color = _rgb_to_hex(r, g, b)
        style['label_color'] = hex_color

        if etype in ('angle', 'polygon', 'arc', 'conic', 'conicpart'):
            style['fill'] = hex_color
            style['fill_opacity'] = a
        if etype == 'point':
            ggb_code = ggb_raw.get('point_style', 0)
            style.update(ggb_point_style_to_elem_style(ggb_code, hex_color))

        if 'line_thickness' in ggb_raw:
            thick = ggb_raw['line_thickness']
            tt = ggb_raw['line_type']
            op = ggb_raw['line_opacity']
            style['stroke'] = hex_color
            style['stroke_opacity'] = op / 255
            style['stroke_width_px'] = ggb_thickness_to_stroke_width(thick)
            if tt > 0:
                style['stroke_dash_ratio'] = 0.65

    return style
