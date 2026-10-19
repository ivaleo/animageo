"""From a space document to a picture: the flat scene drawn by the 2D renderer.

One path (spec §3.4–3.5)::

    space document ──► flat_scene (/1) ──► to_document (a plane document)
        ──► animageo.native.render ──► SVG / PNG / PDF / EPS / TikZ

:func:`render` takes the space document; ``animageo.native.render`` hands a
space document to it, so a caller has one entry for both kinds of work.

**The plane document** (:func:`to_document`): a point — ``point.free`` with
the ID and the appearance of its ``point3`` element; a piece of a line —
``segment.by_points`` between hidden helper points, ID
``<elementId>--<k>`` (``<elementId>--<part>--<k>`` for a part, dots as
dashes), with the role and the overrides of its element; a fill —
``polygon.by_points`` ``<elementId>`` (``--<part>``) with no stroke. The
``z_index`` of every piece and fill is its layer of the flat scene mapped
into ``[0.1, 45.1)`` — under points and labels (50). An ID that would be
longer than 64 characters or taken becomes ``g<n>``.

**The style of space** (``style_config["space"]``, spec §3.5; the keys join
the style schema after P2, until then they are read here and stripped
before the 2D renderer): ``hidden`` ``{look, stroke_dash_ratio,
stroke_dash_period_px, stroke_opacity, stroke_width_scale}``, ``face``
``{look, fill, fill_opacity_front, fill_opacity_back}``, ``section``
``{stroke, fill, fill_opacity}``, ``plane`` ``{look, fill, fill_opacity,
stroke}``; a key that is absent takes the default of the spec
(:data:`SPACE_STYLE_DEFAULTS`). ``appearance.<id>.overrides.hidden_look``
sets the look of the hidden pieces of one element.

**The paint of a hidden piece** = the paint of its element ⊕
``space.hidden``: the stroke the 2D renderer draws for the piece as if seen
(``native.resolve_paint`` of the document), its opacity times the opacity
multiplier and its width times the width scale of the look, dashed by the
dash keys when the look dashes. Looks: ``dashpale`` (dashes, pale),
``dash``, ``pale``, ``thin``, ``both`` (thin and pale), ``none`` (not
drawn). The multipliers of a look are ``stroke_opacity`` /
``stroke_width_scale`` of the style when it sets them, else those of
:data:`HIDDEN_LOOKS`.

``space.face.look`` ``lit`` is drawn as ``flat`` in 3D-1 (light is later).
"""
from __future__ import annotations

import copy

from ..document import DOCUMENT_FORMAT
from ..registry import REGISTRY_VERSION
from .document import as_space_document
from .flat import PLANE_LOOKS, Z_LOW, Z_RANK, Z_ROOM, Z_STEP
from .scene import flat_scene

__all__ = ['SPACE_STYLE_DEFAULTS', 'HIDDEN_LOOKS', 'FACE_LOOKS', 'space_style', 'to_document', 'render',
           'piece_id', 'sheet_layout']

SPACE_STYLE_DEFAULTS = {
    'hidden': {'look': 'dashpale', 'stroke_dash_ratio': 0.55, 'stroke_dash_period_px': 8.0},
    'face': {'look': 'flat', 'fill': 'presets.color.shade', 'fill_opacity_front': 0.5, 'fill_opacity_back': 0.5},
    'section': {'stroke': 'presets.color.accent', 'fill': 'presets.color.accent_light', 'fill_opacity': 0.7},
    'plane': {'look': 'sheet', 'fill': 'presets.color.shade', 'fill_opacity': 0.6, 'stroke': 'presets.color.aux'},
}
# dash?, opacity multiplier, width scale
HIDDEN_LOOKS = {
    'dashpale': {'dash': True, 'stroke_opacity': 0.55, 'stroke_width_scale': 1.0},
    'dash': {'dash': True, 'stroke_opacity': 1.0, 'stroke_width_scale': 1.0},
    'pale': {'dash': False, 'stroke_opacity': 0.55, 'stroke_width_scale': 1.0},
    'thin': {'dash': False, 'stroke_opacity': 1.0, 'stroke_width_scale': 0.5},
    'both': {'dash': False, 'stroke_opacity': 0.45, 'stroke_width_scale': 0.6},
    'none': None,
}
_PALE = ('dashpale', 'pale', 'both')
_THIN = ('thin', 'both')
FACE_LOOKS = ('flat', 'lit', 'none')
_ID_LIMIT = 64


def space_style(style_config) -> dict:
    """The ``space`` section of ``style_config`` with the defaults of the
    spec; a style given by a path or a preset name has none (defaults)."""
    given = style_config.get('space') if isinstance(style_config, dict) else None
    out = copy.deepcopy(SPACE_STYLE_DEFAULTS)
    if isinstance(given, dict):
        for group, keys in given.items():
            if group in out and isinstance(keys, dict):
                out[group].update(keys)
    hidden = out['hidden']
    if hidden['look'] not in HIDDEN_LOOKS:
        raise ValueError(f"space.hidden.look: one of {', '.join(HIDDEN_LOOKS)} expected")
    if out['face']['look'] not in FACE_LOOKS:
        raise ValueError(f"space.face.look: one of {', '.join(FACE_LOOKS)} expected")
    if out['plane']['look'] not in PLANE_LOOKS:
        raise ValueError(f"space.plane.look: one of {', '.join(PLANE_LOOKS)} expected")
    return out


def _hidden_look(space, name) -> dict | None:
    if name not in HIDDEN_LOOKS:
        raise ValueError(f"hidden_look: one of {', '.join(HIDDEN_LOOKS)} expected, got {name!r}")
    base = HIDDEN_LOOKS[name]
    if base is None:
        return None
    look = dict(base)
    given = space['hidden']
    if name in _PALE and 'stroke_opacity' in given:
        look['stroke_opacity'] = float(given['stroke_opacity'])
    if name in _THIN and 'stroke_width_scale' in given:
        look['stroke_width_scale'] = float(given['stroke_width_scale'])
    look['stroke_dash_ratio'] = float(given['stroke_dash_ratio'])
    look['stroke_dash_period_px'] = float(given['stroke_dash_period_px'])
    return look


def piece_id(el_id, part, k) -> str:
    """The plane ID of the ``k``-th piece (1-based) of a stroke."""
    stem = el_id if part is None else f"{el_id}--{part.replace('.', '-')}"
    return f'{stem}--{k}'


class _Ids:
    def __init__(self, taken):
        self.taken = set(taken)
        self.n = 0

    def take(self, wanted):
        if len(wanted) <= _ID_LIMIT and wanted not in self.taken:
            self.taken.add(wanted)
            return wanted
        while True:
            self.n += 1
            alt = f'g{self.n}'
            if alt not in self.taken:
                self.taken.add(alt)
                return alt


def _element_look(appearance, el_id) -> dict:
    """The appearance of a piece taken from its element: role and overrides
    (without ``hidden_look``), no label."""
    entry = appearance.get(el_id) if isinstance(appearance, dict) else None
    out = {'label': {'mode': 'none'}}
    if isinstance(entry, dict):
        if 'role' in entry:
            out['role'] = entry['role']
        overrides = {k: v for k, v in (entry.get('overrides') or {}).items() if k != 'hidden_look'}
        if overrides:
            out['overrides'] = overrides
    return out


def to_document(flat, doc, *, style_config=None) -> dict:
    """The plane ``animageo-construction/v1`` document that draws ``flat``
    (the flat scene of the space document ``doc``) with the style
    ``style_config`` (its ``space`` section; the stroke of a hidden piece is
    resolved against the rest of it)."""
    doc = as_space_document(doc)
    space = space_style(style_config)
    appearance = doc.data.get('appearance') or {}
    elements = doc.elements
    plane = {'format': DOCUMENT_FORMAT, 'documentId': doc.document_id, 'operationRegistryVersion': REGISTRY_VERSION,
             'operations': {}, 'elements': {}, 'inputs': {}, 'appearance': {},
             'viewDefaults': {'bounds': list(flat['bounds'])}}
    ids = _Ids(p['id'] for p in flat['points'])
    top = (len(flat['solids']) + 1) * Z_RANK

    def z_of(layer):
        return Z_LOW + layer * Z_ROOM / (top + 1)

    def add(op, args, el_type, slot, look, el_id, display=''):
        op_id = ids.take('op--' + el_id)
        plane['operations'][op_id] = {'id': op_id, 'op': op, 'args': args,
                                      'outputs': [{'slot': slot, 'elementId': el_id}]}
        plane['elements'][el_id] = {'id': el_id, 'type': el_type, 'displayName': display,
                                    'producer': {'operationId': op_id, 'slot': slot}}
        plane['appearance'][el_id] = look
        return el_id

    def helper(stem, at):
        el_id = ids.take(stem)
        add('point.free', {}, 'point', 'point', {'visible': False, 'label': {'mode': 'none'}}, el_id)
        plane['inputs'][el_id] = {'kind': 'point', 'value': [float(at[0]), float(at[1])]}
        return {'kind': 'ref', 'elementId': el_id}

    # fills
    seen_layers = {}
    face_look = space['face']['look']
    for f in flat['fills']:
        role = f['role']
        if role == 'face' and face_look == 'none':
            continue
        k = seen_layers.get(f['layer'], 0)
        seen_layers[f['layer']] = k + 1
        look = _element_look(appearance, f['id'])
        overrides = {}
        if role == 'face':
            overrides = {'fill': space['face']['fill'],
                         'fill_opacity': space['face']['fill_opacity_' + f['facing']]}
        elif role == 'section':
            overrides = {'fill': space['section']['fill'], 'fill_opacity': space['section']['fill_opacity']}
        elif role == 'plane':
            overrides = {'fill': space['plane']['fill'], 'fill_opacity': space['plane']['fill_opacity']}
        overrides.update(look.get('overrides') or {})
        overrides.update({'stroke_opacity': 0.0, 'z_index': z_of(f['layer']) + k * Z_STEP})
        look['overrides'] = overrides
        stem = f['id'] if f['part'] is None else f"{f['id']}--{f['part'].replace('.', '-')}"
        fill_id = ids.take(stem)
        vertices = [helper(f'{fill_id}--v{j}', p) for j, p in enumerate(f['polygon'], 1)]
        add('polygon.by_points', {'vertices': {'kind': 'list', 'items': vertices}}, 'polygon', 'polygon', look, fill_id)

    # strokes: first as seen, then the hidden pieces from the resolved paint
    hidden_pieces = []                 # (piece id, hidden look)
    for s in flat['strokes']:
        base = _element_look(appearance, s['id'])
        role_over = {}
        if s['role'] == 'section':
            role_over = {'stroke': space['section']['stroke']}
        elif s['role'] == 'plane':
            role_over = {'stroke': space['plane']['stroke'], 'stroke_width_px': 'presets.line_width.aux'}
        entry = appearance.get(s['id']) if isinstance(appearance, dict) else None
        own = (entry.get('overrides') or {}).get('hidden_look') if isinstance(entry, dict) else None
        hidden = _hidden_look(space, own or space['hidden']['look'])
        for k, piece in enumerate(s['pieces'], 1):
            if piece['visibility'] == 'hidden' and hidden is None:
                continue
            look = copy.deepcopy(base)
            overrides = dict(role_over)
            overrides.update(look.get('overrides') or {})
            overrides['z_index'] = z_of(piece['layer'])
            look['overrides'] = overrides
            pid = ids.take(piece_id(s['id'], s['part'], k))
            a, b = helper(pid + '--a', piece['a']), helper(pid + '--b', piece['b'])
            add('segment.by_points', {'a': a, 'b': b}, 'segment', 'segment', look, pid)
            if piece['visibility'] == 'hidden':
                hidden_pieces.append((pid, hidden))

    # points
    for p in flat['points']:
        entry = appearance.get(p['id']) if isinstance(appearance, dict) else None
        look = copy.deepcopy(entry) if isinstance(entry, dict) else {}
        look.pop('visibility', None)
        add('point.free', {}, 'point', 'point', look, p['id'], display=elements[p['id']].get('displayName', ''))
        plane['inputs'][p['id']] = {'kind': 'point', 'value': [float(p['at'][0]), float(p['at'][1])]}

    if hidden_pieces:
        from ..paint import resolve_paint
        paint = resolve_paint(plane, _plane_style(style_config))['elements']
        for pid, hidden in hidden_pieces:
            stroke = (paint.get(pid) or {}).get('stroke') or {}
            overrides = plane['appearance'][pid]['overrides']
            if stroke.get('opacity') is not None:
                overrides['stroke_opacity'] = float(stroke['opacity']) * hidden['stroke_opacity']
            if stroke.get('widthPx') is not None:
                overrides['stroke_width_px'] = float(stroke['widthPx']) * hidden['stroke_width_scale']
            if hidden['dash']:
                overrides['stroke_dash_ratio'] = hidden['stroke_dash_ratio']
                overrides['stroke_dash_period_px'] = hidden['stroke_dash_period_px']
    return plane


def _plane_style(style_config):
    """``style_config`` without its ``space`` section (the 2D renderer reads the rest)."""
    if isinstance(style_config, dict) and 'space' in style_config:
        return {k: v for k, v in style_config.items() if k != 'space'}
    return style_config


def sheet_layout(export_layout):
    """The placement ``export_layout`` of :func:`animageo.native.render` for
    the plane document of a flat scene: its decorations — labels, points,
    strokes — in pixels of the sheet (1.11.0rc7). The source view of that
    document is the extent of the picture (``flat_scene.bounds``), so the
    default ``frame`` decorations followed the frame: a large sheet of a
    plane or another camera made the labels smaller. Here
    ``content.decoration_scale_source`` is ``output`` (``export_layout.py``:
    the style pixels on the sheet, times ``prominence``) unless the layout
    names its own; ``None`` stays ``None`` (no layout: the canvas is the
    source view, its pixels are the style's). A copy; the argument is not
    changed."""
    if export_layout is None:
        return None
    out = dict(export_layout)
    content = dict(out.get('content') or {})
    content.setdefault('decoration_scale_source', 'output')
    out['content'] = content
    return out


def render(doc, out=None, *, fmt='svg', style_config=None, export_layout=None, camera=None, inputs=None,
           report=True):
    """Draw the space document ``doc`` (``camera`` — ``viewDefaults.camera``
    unless given) with :func:`animageo.native.render` (needs manim): ``svg``,
    ``png``, ``pdf``, ``eps``, ``tikz``, ``tex``, under
    :func:`sheet_layout` of ``export_layout`` (labels in pixels of the
    sheet). The report's elements are those of the plane document
    (:func:`to_document`)."""
    from ..rendering import render as native_render
    doc = as_space_document(doc)
    space = space_style(style_config)
    flat = flat_scene(doc, camera, inputs=inputs, plane_look=space['plane']['look'])
    plane = to_document(flat, doc, style_config=style_config)
    return native_render(plane, style_config=_plane_style(style_config), export_layout=sheet_layout(export_layout),
                         fmt=fmt, out=out, report=report)
