"""GGB style of an object → keys of ``appearance.overrides`` for the report (plan L5 §3.7).

Visibility and the label go to the document (``appearance.visible``,
``appearance.label``) always; colour, thickness, dash, point size and shape,
fill opacity go to ``elements[].ggb_style`` of the import report only — the
web decides whether to take the colours of GeoGebra (decision 8). The
conversions are those of the classic ``loadGGB`` (``ggb_parser.parse_constr``
→ ``elem.ggb_style``): thickness / 2 px, point size × 2 px, a dashed line
style → exact ``stroke_dash_pattern_px``, the point style through
``ggb_point_style_to_elem_style``, the fill of a polygon, angle, conic or arc
with its alpha — 0 as well (1.10.0a2: the shape stays without fill instead of
taking the default fill of the style). Colours are 6-digit hex only.
"""
from __future__ import annotations

import math
import re

__all__ = ['ggb_style', 'appearance', 'label_of', 'layer_overrides', 'property_warnings', 'LABEL_MODES']

# GGB <labelMode val> → native label mode (rendering.LABEL_MODES)
LABEL_MODES = {0: 'name', 1: 'name_value', 2: 'value', 3: 'caption'}
_FILLED = ('angle', 'polygon', 'arc', 'conic', 'conicpart', 'sector')
_VALUE_LABELS = ('segment', 'vector', 'polygon', 'angle', 'numeric')


def _dynamic_caption(info):
    return 'dynamic_caption' in info or re.search(r'%[nvxyz]', info.get('caption', ''))


def _label_offset(info, view):
    from .ggb import _float
    offset = info.get('label_offset')
    cs = view.find('coordSystem') if view is not None else None
    if offset is None or None in offset or cs is None:
        return None
    sx = _float(cs.attrib.get('scale'))
    sy = _float(cs.attrib.get('yscale')) if 'yscale' in cs.attrib else sx
    if sx is None or sy is None or sx <= 0 or sy <= 0:
        return None
    result = [offset[0] / sx, -offset[1] / sy]
    return result if all(math.isfinite(v) for v in result) else None


def _hex(rgb) -> str:
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def ggb_style(info: dict) -> dict:
    """``{key: value}`` of ``appearance.overrides`` for the scanned element ``info``."""
    out: dict = {}
    type_ = info.get('type')
    color = info.get('color')
    if color is not None:
        hx = _hex(color['rgb'])
        out['label_color'] = hx
        alpha = color.get('alpha')
        if type_ in _FILLED and alpha is not None:     # alpha 0 too: no fill, not the default one
            out['fill'] = hx
            out['fill_opacity'] = round(float(alpha), 6)
        if type_ == 'point':
            try:
                from ...style.enums import ggb_point_style_to_elem_style
                patch = ggb_point_style_to_elem_style(int(info.get('point_style', 0)), hx)
            except Exception:        # noqa: BLE001 — no classic style module: the colour only
                patch = {'fill': hx, 'stroke': hx}
            for key, value in patch.items():
                out[key] = value
    line = info.get('line_style')
    if line is not None:
        if color is not None:
            out['stroke'] = _hex(color['rgb'])
        if line.get('opacity') is not None:
            out['stroke_opacity'] = round(max(0., min(255., line['opacity'])) / 255.0, 6)
        width = max(0., float(line.get('thickness') or 0)) / 2.0
        if line.get('thickness') is not None:
            out['stroke_width_px'] = width
        # GeoGebra EuclidianStatic.getStroke(width, type), in screen pixels.
        patterns = {0: [], 10: [4 + width, 4.], 15: [8 + width, 8.],
                    20: [width, 3.], 30: [8 + width, 4., width, 4.]}
        pattern = patterns.get(line.get('type', 0))
        if pattern is not None:
            out['stroke_dash_pattern_px'] = pattern
            # Keep a useful approximation for older consumers of the report.
            out['stroke_dash_ratio'] = pattern[0] / sum(pattern[:2]) if pattern else 0.
            if pattern:
                out['stroke_dash_period_px'] = sum(pattern[:2])
    if type_ == 'point' and info.get('point_size') is not None:
        out['size_px'] = float(info['point_size']) * 2.0
    if info.get('decoration') and type_ in ('segment', 'angle'):
        out['tick_count'] = int(info['decoration']) + (1 if type_ == 'angle' else 0)
    if type_ == 'angle' and info.get('angle_style') is not None:
        out['angle_range'] = 'reflex' if info['angle_style'] == 2 else 'minor'     # as the classic loadGGB
    return {k: out[k] for k in sorted(out)}


def appearance(info: dict, native_type: str | None, *, view=None) -> dict:
    """``appearance`` entry of the document: visibility and the label."""
    entry: dict = {}
    if info.get('show_object') is not None:
        entry['visible'] = bool(info['show_object'])
    label = label_of(info, native_type)
    offset = _label_offset(info, view)
    if offset is not None:
        label = label or {'mode': 'name' if native_type == 'point' else 'none'}
        label['offsetWorld'] = offset
    if label is not None:
        entry['label'] = label
    return entry


def label_of(info: dict, native_type: str | None):
    """``{mode, text?}`` of the GGB label, ``None`` when it is the default."""
    shown = info.get('show_label')
    if shown is None:
        return None
    source_mode = info.get('label_mode', 0)
    mode = LABEL_MODES.get(source_mode, 'none') if shown else 'none'
    if shown and 'caption_snapshot' in info:
        return {'mode': 'caption', 'text': info['caption_snapshot']}
    if 'dynamic_caption' in info or (mode == 'caption' and _dynamic_caption(info)):
        mode = 'none'
    if mode in ('value', 'name_value') and info.get('type') not in _VALUE_LABELS:
        mode = 'none'
    out = {'mode': mode}
    if mode == 'caption' and info.get('caption') is not None:
        out['text'] = info['caption']
    if mode == 'caption' and 'text' not in out:
        out['mode'] = 'name'
    return out


def layer_overrides(info, native_type):
    """Separate GGB layers by 100 native z units, including fills and labels."""
    base = 100 * info.get('layer', 0)
    z = {'point': 50, 'angle': 3, 'polygon': .01, 'sector': .01, 'circlesegment': .01,
         'segment': 5, 'circle': 5, 'arc': 5, 'text': 50}.get(native_type, 4)
    out = {'z_index': base + z}
    if native_type in ('circle', 'arc', 'sector', 'circlesegment', 'conic'):
        out['z_index_fill'] = base + .01
    if native_type in ('point', 'segment', 'line', 'ray', 'vector', 'circle', 'arc', 'sector',
                       'circlesegment', 'conic', 'polygon', 'angle'):
        out['z_index_label'] = base + 60
    return out


def property_warnings(info, view):
    """Properties that have no faithful native representation; never run expressions."""
    out = []

    def warn(code, detail):
        out.append({'code': code, 'ggb_name': info['label'], 'detail': detail[:500]})
    if 'layer_invalid' in info:
        warn('layer_unsupported', f'Слой GeoGebra {info["layer_invalid"]} не является целым числом от 0 до 9; не перенесён.')
    if info.get('show_label'):
        mode = info.get('label_mode', 0)
        if 'caption_snapshot' in info:
            warn('label_caption_simplified', 'Сохранён текущий текст динамической подписи; подпись не пересчитывается.')
        elif mode not in LABEL_MODES or (mode in (1, 2) and info['type'] not in _VALUE_LABELS):
            warn('label_mode_unsupported', f'Режим подписи GeoGebra {mode} для {info["type"]} не переносится; подпись скрыта.')
        if 'caption_snapshot' not in info and _dynamic_caption(info) and ('dynamic_caption' in info or mode == 3):
            warn('label_caption_unsupported', 'Подпись скрыта: ' + info.get(
                'caption_error', 'подстановки GeoGebra в caption не поддерживаются.'))
    if info['type'] == 'numeric' and (info.get('show_label') or info.get('slider') is not None):
        warn('slider_display_dropped', 'Сохранено число; полоса ползунка и её подпись на холсте не переносятся.')
    if 'label_offset' in info and _label_offset(info, view) is None:
        warn('label_offset_dropped', 'Смещение подписи не переносится: нет корректного масштаба вида или координат.')
    line = info.get('line_style', {})
    if line.get('type', 0) not in (0, 10, 15, 20, 30):
        warn('line_style_unsupported', f'Неизвестный вид линии GeoGebra {line["type"]}; используется сплошная линия.')
    elif line.get('type', 0) and info['type'] in ('polygon', 'angle', 'sector'):
        warn('line_style_unsupported', f'Пунктир для {info["type"]} не поддерживается рендерером; используется сплошная линия.')
    anim = info.get('animation')
    if anim is not None:
        settings = ', '.join(f'{k}={anim[k][:80]}' for k in ('playing', 'speed', 'type', 'step') if k in anim)
        warn('animation_settings_dropped', 'Автоматический таймлайн не создаётся; настройки GeoGebra: ' + settings)
    slider = info.get('slider')
    if slider is not None:
        if any(v is None for v in slider.values()) or (slider.get('step') is not None and slider['step'] <= 0) or (
                slider.get('min') is not None and slider.get('max') is not None and slider['min'] > slider['max']):
            warn('slider_range_dropped', 'Диапазон или шаг не являются допустимыми числовыми литералами; сохранено число без диапазона.')
    return out
