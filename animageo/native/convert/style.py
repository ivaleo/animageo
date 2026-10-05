"""GGB style of an object → keys of ``appearance.overrides`` for the report (plan L5 §3.7).

Visibility and the label go to the document (``appearance.visible``,
``appearance.label``) always; colour, thickness, dash, point size and shape,
fill opacity go to ``elements[].ggb_style`` of the import report only — the
web decides whether to take the colours of GeoGebra (decision 8). The
conversions are those of the classic ``loadGGB`` (``ggb_parser.parse_constr``
→ ``elem.ggb_style``): thickness / 2 px, point size × 2 px, a dashed line
style → ``stroke_dash_ratio`` 0.65, the point style through
``ggb_point_style_to_elem_style``. Colours are 6-digit hex only.
"""
from __future__ import annotations

__all__ = ['ggb_style', 'appearance', 'LABEL_MODES']

# GGB <labelMode val> → native label mode (rendering.LABEL_MODES)
LABEL_MODES = {0: 'name', 1: 'name_value', 2: 'value', 3: 'caption', 9: 'caption'}
_FILLED = ('angle', 'polygon', 'arc', 'conic', 'conicpart', 'sector')


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
        if type_ in _FILLED and alpha is not None and alpha > 0:
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
            out['stroke'] = hx
            if line.get('opacity') is not None:
                out['stroke_opacity'] = round(float(line['opacity']) / 255.0, 6)
            if line.get('thickness') is not None:
                out['stroke_width_px'] = float(line['thickness']) / 2.0
            if int(line.get('type') or 0) > 0:
                out['stroke_dash_ratio'] = 0.65
    if type_ == 'point' and info.get('point_size') is not None:
        out['size_px'] = float(info['point_size']) * 2.0
    if info.get('decoration') and type_ in ('segment', 'angle'):
        out['tick_count'] = int(info['decoration']) + (1 if type_ == 'angle' else 0)
    if type_ == 'angle' and info.get('angle_style') is not None:
        out['angle_range'] = 'reflex' if info['angle_style'] == 2 else 'minor'     # as the classic loadGGB
    return {k: out[k] for k in sorted(out)}


def appearance(info: dict, native_type: str | None) -> dict:
    """``appearance`` entry of the document: visibility and the label."""
    entry: dict = {}
    if info.get('show_object') is not None:
        entry['visible'] = bool(info['show_object'])
    label = label_of(info, native_type)
    if label is not None:
        entry['label'] = label
    return entry


def label_of(info: dict, native_type: str | None):
    """``{mode, text?}`` of the GGB label, ``None`` when it is the default."""
    shown = info.get('show_label')
    if shown is None:
        return None
    mode = LABEL_MODES.get(info.get('label_mode', 0), 'name') if shown else 'none'
    out = {'mode': mode}
    if mode == 'caption' and info.get('caption') is not None:
        out['text'] = info['caption']
    if mode == 'caption' and 'text' not in out:
        out['mode'] = 'name'
    return out
