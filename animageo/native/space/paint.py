"""The paint of the plane primitives that draw a space document."""
from __future__ import annotations

from ..document import as_document
from ..paint import resolve_paint as _plane_paint
from .bridge import _plane_document, _plane_style, sheet_layout, space_style
from .document import as_space_document
from .evaluate import evaluate
from .marks import checked_marks, draw_marks, prepare_marks, projected_marks
from .scene import flat_scene

SPACE_PAINT_FORMAT = 'animageo-space-paint/v1'


def _shown(entry, channel):
    if entry is None or not entry['drawn']:
        return None
    value = entry.get(channel)
    if value is not None and (value.get('opacity', 1) <= 0 or value.get('widthPx', 1) <= 0):
        return None
    return value


def resolve_paint(doc, style_config=None, *, camera=None, inputs=None, export_layout=None):
    """The actual paint of each space primitive on the requested sheet."""
    from ...style.config import StyleConfig

    doc = as_space_document(doc)
    ev = evaluate(doc, inputs=inputs)
    flat = flat_scene(doc, camera, plane_look=space_style(style_config)['plane']['look'], evaluated=ev)
    plane, index = _plane_document(flat, doc, style_config)
    resolved = _plane_paint(plane, _plane_style(style_config), export_layout=sheet_layout(export_layout))
    elements = resolved['elements']
    strokes = []
    for stroke, ids in index['strokes']:
        parts = [{**piece, 'index': k, 'stroke': _shown(elements.get(pid), 'stroke')}
                 for k, (piece, pid) in enumerate(zip(stroke['pieces'], ids), 1)]
        strokes.append({**stroke, 'pieces': parts})
    fills = [{**f, 'fill': _shown(elements.get(fid), 'fill')} for f, fid in index['fills']]
    points = [{**p, **{key: elements[p['id']].get(key) for key in ('point', 'stroke', 'fill', 'z')}}
              for p in index['points'] if elements[p['id']]['drawn']]
    labels = []
    for src, kind, target in index['labels']:
        label = elements[target].get('label')
        if label and label.get('shown'):
            labels.append({'id': src, 'kind': kind, 'at': label['spotWorld'], 'label': label})
    marks = prepare_marks(doc, ev, flat, index)
    camera = checked_marks(marks, as_document(plane))
    resolved_marks = list(projected_marks(marks, camera, resolved['ptUnitStyle'], elements,
                                          StyleConfig.load(_plane_style(style_config))))
    return {'format': SPACE_PAINT_FORMAT, 'background': resolved['background'], 'bounds': flat['bounds'],
            'ptUnit': resolved['ptUnit'], 'ptUnitStyle': resolved['ptUnitStyle'],
            'strokes': strokes, 'fills': fills, 'points': points, 'labels': labels, 'marks': resolved_marks}


def prepare_render(flat, doc, *, style_config=None, evaluated=None):
    """Adapt a /1 flat scene and its evaluated document into a plane render job."""
    doc = as_space_document(doc)
    if evaluated is None:
        evaluated = evaluate(doc)
    plane, index = _plane_document(flat, doc, style_config)
    return {'document': plane, 'marks': prepare_marks(doc, evaluated, flat, index)}


def _decorator(doc, marks, style_config, export_layout, emitted=None):
    camera = checked_marks(marks, doc)
    if camera is None or not marks['guides']:
        return None
    from ...label_placement import _style_ptUnit

    elements = _plane_paint(doc, style_config, export_layout=export_layout)['elements']

    def decorate(scene):
        records = list(projected_marks(marks, camera, _style_ptUnit(scene.style), elements, scene.style_config))
        draw_marks(scene.geo, records)
        if emitted is not None:
            emitted.extend(records)

    return decorate


def render_plane(plane, out=None, *, marks=None, fmt='svg', style_config=None, export_layout=None, report=True):
    """Draw a prepared space sheet using the same plane renderer as native.render."""
    from ..rendering import _render
    plane = as_document(plane)
    style, layout = _plane_style(style_config), sheet_layout(export_layout)
    emitted = []
    decorate = _decorator(plane, marks, style, layout, emitted)
    result = _render(plane, out=out, fmt=fmt, style_config=style, export_layout=layout, report=report,
                     decorate=decorate)
    if result.report is not None and marks is not None:
        result.report['spaceMarks'] = emitted
    return result


def layout_plane_labels(plane, *, marks=None, style_config=None, export_layout=None, backend='metrics', place=None):
    """Run the plane label solver with the visible decorations as obstacles."""
    from ..labels.layout import _layout_labels
    plane = as_document(plane)
    style, layout = _plane_style(style_config), sheet_layout(export_layout)
    return _layout_labels(plane, style_config=style, export_layout=layout, backend=backend, place=place,
                          decorate=_decorator(plane, marks, style, layout))
