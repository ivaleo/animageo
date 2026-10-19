"""The flat scene of a space construction and its native document.

:func:`flat_scene` projects a :class:`SpaceScene` through a camera and
returns ``animageo-flat-scene/0`` — the picture the 2D painter draws, in
picture units with y up (a prototype format; it may change)::

    {"format": "animageo-flat-scene/0", "camera": {…}, "scale": S,
     "bounds": [xmin, ymin, xmax, ymax], "unit": px per picture unit,
     "solids":  [id, …],                                          # far to near
     "fills":   [{"id", "source", "role": "face" | "section" | "plane",
                  "solid": id (faces and sections),
                  "facing": "front" | "back" (faces only),
                  "polygon": [[x, y], …], "depth"}, …],          # far to near
     "strokes": [{"id", "source", "role": "edge" | "section" | "aux" | "plane",
                  "pieces": [{"a": [x, y], "b": [x, y], "t": [t0, t1],
                              "visibility": "visible" | "hidden",
                              "occluders": n, "hiddenBy": [id, …]}, …]}, …],
     "points":  [{"id", "source", "name", "at": [x, y], "depth",
                  "visibility": "visible" | "hidden"}, …],
     "diagnostics": [{"code", "id", …}, …]}

Rules of the drawing (the school ones): a solid hides what lies behind it;
the edges of a section take the visibility of the faces they lie on; planes
hide nothing, their sheets are hidden by solids like any line; a line seen
end-on (along the view ray, of zero length on the sheet) keeps its entry
with no pieces. Fills come in
painting order: the sheets of planes, then for every solid from the far one
to the near one (``solids``, by the depth of the centre) its back faces, its
sections and its front faces (a prototype rule: solids that overlap in depth
are not split). ``hiddenBy`` of a piece — the solids that hide it, far to
near (its own solid first for a hidden edge of a solid); empty when seen.

:func:`to_document` turns the flat scene into an ``animageo-construction/v1``
document of the plane: free points, segments for the pieces and polygons
for the fills, the look of every piece in ``appearance.overrides`` (keys of
the style schema; ``presets.*`` tokens are resolved by the style).
:func:`render` draws that document with :func:`animageo.native.render` —
the same renderer and export formats as a plane drawing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import vec
from .camera import Projector
from .section import plane_sheet, section, section_visibility
from .solids import scale_of
from .visibility import DECIDE_TOL, ConvexOccluder, edge_visibility, face_facing, pieces, vertex_visibility

__all__ = ['FLAT_SCENE_FORMAT', 'HIDDEN_LOOKS', 'FACE_LOOKS', 'SceneSolid', 'SceneSection', 'SceneSegment',
           'ScenePoint', 'ScenePlane', 'SpaceScene', 'flat_scene', 'to_document', 'render']

FLAT_SCENE_FORMAT = 'animageo-flat-scene/0'
MARGIN = 0.08                     # of the larger side of the picture, on every side
# The reference frame: the bounds of the flat scene across SOURCE_WIDTH px —
# the source view ``native.render`` draws the document in
# (``animageo.native.rendering.SOURCE_WIDTH``), the px of the style keys.
SOURCE_WIDTH = 800.0
MIN_PIECE_PX = 0.9                # px of the reference frame


@dataclass(frozen=True)
class SceneSolid:
    id: str
    solid: object
    vertices: bool = True         # draw and name the vertices


@dataclass(frozen=True)
class SceneSection:
    id: str
    solid: str                    # the id of a SceneSolid
    plane: object


@dataclass(frozen=True)
class SceneSegment:
    id: str
    a: tuple
    b: tuple
    role: str = 'aux'


@dataclass(frozen=True)
class ScenePoint:
    id: str
    name: str
    at: tuple


@dataclass(frozen=True)
class ScenePlane:
    """A drawn plane: ``look`` ``sheet`` (a parallelogram with a light fill),
    ``corners`` (only its corners) or ``trace`` (no sheet: the plane is seen
    by its line on the ground ``z = 0`` within the sheet and by its
    sections)."""

    id: str
    plane: object
    around: tuple
    look: str = 'sheet'
    margin: float = 0.25


@dataclass(frozen=True)
class SpaceScene:
    solids: tuple = field(default_factory=tuple)
    sections: tuple = field(default_factory=tuple)
    segments: tuple = field(default_factory=tuple)
    points: tuple = field(default_factory=tuple)
    planes: tuple = field(default_factory=tuple)


PLANE_LOOKS = ('sheet', 'corners', 'trace')
CORNER_SHARE = 0.18               # of a side of the sheet: the length of a corner stroke


def _xy(projected):
    return [projected[0], projected[1]]


def flat_scene(scene: SpaceScene, camera, *, min_piece_px=MIN_PIECE_PX, source_width=SOURCE_WIDTH) -> dict:
    """The flat scene of ``scene`` seen by ``camera``; ``ValueError("behind_eye")``
    when a perspective eye has a point of the scene behind or beside it.

    ``min_piece_px`` — a gap or a bit of a line shorter than this merges
    into its neighbour; it is in px of the reference frame: the bounds of
    the flat scene across ``source_width`` px (``unit`` px per picture
    unit), not of a canvas zoom or an export size, so that every kernel
    that draws the scene cuts the same pieces.
    """
    projector = Projector(camera)
    solids = {s.id: s for s in scene.solids}
    if len(solids) != len(scene.solids):
        raise ValueError('duplicate_id: two solids share an id')
    diagnostics = []
    cuts = []
    for cut in scene.sections:
        if cut.solid not in solids:
            raise ValueError(f'unknown_solid: section {cut.id!r} cuts {cut.solid!r}')
        result = section(solids[cut.solid].solid, cut.plane)
        if result.state != 'defined':
            diagnostics.append({'code': 'section_undefined', 'id': cut.id, 'reason': result.reason})
        cuts.append((cut, result))
    sheets = []
    for pl in scene.planes:
        if pl.look not in PLANE_LOOKS:
            raise ValueError(f'look: one of {", ".join(PLANE_LOOKS)} expected for plane {pl.id!r}')
        sheets.append((pl, plane_sheet(pl.plane, pl.around, pl.margin)))
    traces = {pl.id: _ground_trace(corners) for pl, corners in sheets if pl.look == 'trace'}

    every = [v for s in scene.solids for v in s.solid.vertices]
    every += [p for _, r in cuts for p in r.polygon]
    every += [p for s in scene.segments for p in (s.a, s.b)]
    every += [p.at for p in scene.points]
    every += [c for pl, corners in sheets if pl.look != 'trace' for c in corners]
    every += [p for trace in traces.values() if trace for p in trace]
    if not every:
        raise ValueError('empty: nothing to draw')
    scale = scale_of(every)
    projected = [projector.project(p) for p in every]
    if not projector.parallel and min(p[2] for p in projected) <= 1e-6 * scale:
        raise ValueError('behind_eye: a point of the scene is not in front of the eye')
    xs, ys = [p[0] for p in projected], [p[1] for p in projected]
    pad = MARGIN * max(max(xs) - min(xs), max(ys) - min(ys), 1e-9 * scale)
    bounds = [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]
    unit = source_width / (bounds[2] - bounds[0])

    occluders = {s.id: ConvexOccluder(s.solid, projector) for s in scene.solids}
    facing = {s.id: face_facing(s.solid, projector) for s in scene.solids}

    order = sorted(scene.solids, key=lambda s: -projector.project(s.solid.centre)[2])
    rank = {s.id: k for k, s in enumerate(order)}

    def others(owner):
        return [occ for sid, occ in occluders.items() if sid != owner]

    def stroke(stroke_id, source, role, a, b, own_hidden, owner):
        pa, pb = projector.project(a), projector.project(b)
        length = vec.norm((pb[0] - pa[0], pb[1] - pa[1], 0.0))
        if length <= DECIDE_TOL * scale:             # seen end-on (along the view ray): nothing to draw
            return {'id': stroke_id, 'source': source, 'role': role, 'pieces': []}
        min_t = min(1.0, min_piece_px / (length * unit))
        hiders = [(owner, (0.0, 1.0))] if own_hidden else []
        for sid, occ in occluders.items():
            span = occ.hidden_interval(a, b) if sid != owner else None
            if span is not None:
                hiders.append((sid, span))
        out = []
        for piece in pieces([span for _, span in hiders], min_t):
            by = sorted({sid for sid, (h0, h1) in hiders if min(h1, piece.t1) > max(h0, piece.t0)},
                        key=rank.get) if piece.hidden else []
            out.append({'a': _xy(projector.project(vec.lerp(a, b, piece.t0))),
                        'b': _xy(projector.project(vec.lerp(a, b, piece.t1))),
                        't': [piece.t0, piece.t1],
                        'visibility': 'hidden' if piece.hidden else 'visible',
                        'occluders': piece.occluders,
                        'hiddenBy': by})
        return {'id': stroke_id, 'source': source, 'role': role, 'pieces': out}

    def fill(fill_id, source, role, polygon, facing_state=None, solid=None):
        pts = [projector.project(p) for p in polygon]
        out = {'id': fill_id, 'source': source, 'role': role, 'polygon': [_xy(p) for p in pts],
               'depth': sum(p[2] for p in pts) / len(pts)}
        if solid is not None:
            out['solid'] = solid
        if facing_state is not None:
            out['facing'] = facing_state
        return out

    def far_first(items):
        return sorted(items, key=lambda f: -f['depth'])

    fills, strokes, points = [], [], []
    for pl, corners in sheets:
        if pl.look == 'sheet':
            fills.append(fill(pl.id, pl.id, 'plane', corners))
    fills = far_first(fills)

    for item in order:
        poly, sid = item.solid, item.id
        states = facing[sid]
        back = [fill(f'{sid}.face.{k}', sid, 'face', [poly.vertices[i] for i in ring], 'back', sid)
                for k, ring in enumerate(poly.faces) if states[k] == 'back']
        front = [fill(f'{sid}.face.{k}', sid, 'face', [poly.vertices[i] for i in ring], 'front', sid)
                 for k, ring in enumerate(poly.faces) if states[k] == 'front']
        fills += far_first(back)
        fills += [fill(cut.id, cut.id, 'section', list(r.polygon), solid=sid)
                  for cut, r in cuts if cut.solid == sid and r.state == 'defined']
        fills += far_first(front)

    for item in scene.solids:
        poly, sid = item.solid, item.id
        for e, visible in zip(poly.edges, edge_visibility(poly, projector, facing[sid])):
            name = f'{sid}.edge.{poly.labels[e.a]}-{poly.labels[e.b]}'
            strokes.append(stroke(name, sid, 'edge', poly.vertices[e.a], poly.vertices[e.b], not visible, sid))
    for cut, r in cuts:
        if r.state != 'defined':
            continue
        poly = solids[cut.solid].solid
        seen = section_visibility(poly, r, projector, facing[cut.solid])
        for k, ((p, q), visible) in enumerate(zip(r.edges(), seen)):
            strokes.append(stroke(f'{cut.id}.edge.{k}', cut.id, 'section', p, q, not visible, cut.solid))
    for seg in scene.segments:
        strokes.append(stroke(seg.id, seg.id, seg.role, tuple(seg.a), tuple(seg.b), False, None))
    for pl, corners in sheets:
        if pl.look == 'trace':
            if traces[pl.id]:
                strokes.append(stroke(f'{pl.id}.trace', pl.id, 'plane', *traces[pl.id], False, None))
            continue
        for k in range(4):
            a, b = corners[k], corners[(k + 1) % 4]
            if pl.look == 'sheet':
                strokes.append(stroke(f'{pl.id}.border.{k}', pl.id, 'plane', a, b, False, None))
            else:
                for j, (p, q) in enumerate(((a, vec.lerp(a, b, CORNER_SHARE)), (b, vec.lerp(b, a, CORNER_SHARE)))):
                    strokes.append(stroke(f'{pl.id}.corner.{k}.{j}', pl.id, 'plane', p, q, False, None))

    def point(point_id, source, name, at, own_hidden, owner):
        pr = projector.project(at)
        hidden = own_hidden or any(occ.hides(at) for occ in (others(owner) if owner else occluders.values()))
        return {'id': point_id, 'source': source, 'name': name, 'at': _xy(pr), 'depth': pr[2],
                'visibility': 'hidden' if hidden else 'visible'}

    for item in scene.solids:
        if not item.vertices:
            continue
        poly = item.solid
        for i, visible in enumerate(vertex_visibility(poly, projector, facing[item.id])):
            points.append(point(f'{item.id}.vertex.{poly.labels[i]}', item.id, poly.labels[i],
                                poly.vertices[i], not visible, item.id))
    for p in scene.points:
        points.append(point(p.id, p.id, p.name, tuple(p.at), False, None))

    return {'format': FLAT_SCENE_FORMAT, 'camera': camera.to_dict(), 'scale': scale, 'bounds': bounds,
            'unit': unit, 'solids': [s.id for s in order], 'fills': fills, 'strokes': strokes,
            'points': points, 'diagnostics': diagnostics}


# ── the native document of a flat scene ─────────────────────────────────

def _ground_trace(corners):
    """The segment where the sheet ``corners`` crosses the ground ``z = 0``,
    or ``None`` (a horizontal sheet, or one that does not reach the ground)."""
    tol = 1e-9 * max(1.0, scale_of(corners))
    if max(c[2] for c in corners) - min(c[2] for c in corners) <= tol:
        return None
    found = []
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        if a[2] != b[2] and min(a[2], b[2]) <= 0.0 <= max(a[2], b[2]):
            p = vec.lerp(a, b, a[2] / (a[2] - b[2]))
            if all(vec.dist(p, q) > tol for q in found):
                found.append(p)
    return (found[0], found[1]) if len(found) == 2 else None


# The look of a hidden piece (``look["hidden"]``); the default is pale
# dashes (``dashpale``). ``stroke_opacity`` is a multiplier of the opacity
# of the line (of ``ROLE_STROKES``, 1 when its role sets none).
HIDDEN_LOOKS = {
    'dashpale': {'stroke_dash_ratio': 0.55, 'stroke_dash_period_px': 8.0, 'stroke_opacity': 0.55},
    'dash': {'stroke_dash_ratio': 0.55, 'stroke_dash_period_px': 8.0},
    'thin': {'stroke_width_px': 'presets.line_width.aux', 'stroke_opacity': 0.8},
    'pale': {'stroke_opacity': 0.35},
    'none': None,
}
ROLE_STROKES = {
    'edge': {},
    'section': {'stroke': 'presets.color.accent'},
    'aux': {'stroke_width_px': 'presets.line_width.aux'},
    'plane': {'stroke': 'presets.color.aux', 'stroke_width_px': 'presets.line_width.aux'},
    'axis': {'stroke': 'presets.color.aux', 'stroke_width_px': 'presets.line_width.aux'},
}
# The fills (``look["faces"]``): ``flat`` — a light even tint, ``none`` — no
# face fills (sections and sheets keep theirs).
FACE_LOOKS = ('flat', 'none')
FILLS = {
    'face': {'fill': 'presets.color.shade', 'fill_opacity': 0.5},
    'section': {'fill': 'presets.color.accent_light', 'fill_opacity': 0.7},
    'plane': {'fill': 'presets.color.shade', 'fill_opacity': 0.6},
}
# Painting order (the z_index of the document): the sheets of planes; then
# every solid from the far one to the near one — its back faces, its
# sections, the hidden pieces it is the farthest solid to hide (the first of
# ``hiddenBy``), its front faces; then every visible piece. A layer is
# ``rank·Z_RANK + tier`` (rank 0 — the sheets, 1, 2, … — the solids of
# ``flat["solids"]``) mapped into ``[Z_LOW, Z_LOW + Z_ROOM)``: under the
# points and labels (z 50) for any number of solids. Fills of one layer go
# far to near by ``Z_STEP``. A hidden piece lies over the fill of a section:
# a dash under it would vanish.
Z_TIERS = {'plane': 0, 'back': 1, 'section': 2, 'hidden': 3, 'front': 4}
Z_RANK = 10
Z_LOW, Z_ROOM = 0.1, 45.0
Z_STEP = 1e-4


def _check_look(look):
    look = dict(look or {})
    hidden = look.get('hidden', 'dashpale')
    if hidden not in HIDDEN_LOOKS:
        raise ValueError(f'hidden: one of {", ".join(HIDDEN_LOOKS)} expected, got {hidden!r}')
    faces = look.get('faces', 'flat')
    if faces not in FACE_LOOKS:
        raise ValueError(f'faces: one of {", ".join(FACE_LOOKS)} expected, got {faces!r}')
    return hidden, faces, bool(look.get('labels', True))


def to_document(flat, *, look=None, document_id='space', registry_version=None) -> dict:
    """The ``animageo-construction/v1`` document that draws ``flat``.

    ``look``: ``{"hidden": "dashpale" | "dash" | "thin" | "pale" | "none",
    "faces": "flat" | "none", "labels": bool}``.
    """
    from ..registry import REGISTRY_VERSION
    hidden_look, faces_look, labels = _check_look(look)
    doc = {'format': 'animageo-construction/v1', 'documentId': document_id,
           'operationRegistryVersion': registry_version or REGISTRY_VERSION,
           'operations': {}, 'elements': {}, 'inputs': {}, 'appearance': {},
           'viewDefaults': {'bounds': list(flat['bounds'])}}
    counters = {}

    def new_id(prefix):
        counters[prefix] = counters.get(prefix, 0) + 1
        return f'{prefix}{counters[prefix]}'

    def add(op, args, el_type, slot, appearance, el_id, display=''):
        op_id = 'op_' + el_id
        doc['operations'][op_id] = {'id': op_id, 'op': op, 'args': args,
                                    'outputs': [{'slot': slot, 'elementId': el_id}]}
        doc['elements'][el_id] = {'id': el_id, 'type': el_type, 'displayName': display,
                                  'producer': {'operationId': op_id, 'slot': slot}}
        doc['appearance'][el_id] = appearance
        return el_id

    def helper(at):
        el_id = new_id('h')
        add('point.free', {}, 'point', 'point', {'visible': False, 'label': {'mode': 'none'}}, el_id)
        doc['inputs'][el_id] = {'kind': 'point', 'value': [float(at[0]), float(at[1])]}
        return el_id

    def ref(el_id):
        return {'kind': 'ref', 'elementId': el_id}

    rank = {sid: k + 1 for k, sid in enumerate(flat['solids'])}
    top = (len(rank) + 1) * Z_RANK                    # the layer of visible pieces

    def z_of(layer):
        return Z_LOW + layer * Z_ROOM / (top + 1)

    seen = {}
    for f in flat['fills']:
        if f['role'] == 'face' and faces_look == 'none':
            continue
        tier = f['facing'] if f['role'] == 'face' else f['role']
        layer = rank.get(f.get('solid'), 0) * Z_RANK + Z_TIERS[tier]
        k = seen.get(layer, 0)
        seen[layer] = k + 1
        z = z_of(layer) + k * Z_STEP
        overrides = dict(FILLS[f['role']])
        overrides.update({'stroke_opacity': 0.0, 'z_index': z})     # a polygon's fill lies at its z_index
        vertices = [helper(p) for p in f['polygon']]
        add('polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref(v) for v in vertices]}},
            'polygon', 'polygon', {'label': {'mode': 'none'}, 'overrides': overrides}, new_id('f'))

    for s in flat['strokes']:
        for piece in s['pieces']:
            hidden = piece['visibility'] == 'hidden'
            if hidden and HIDDEN_LOOKS[hidden_look] is None:
                continue
            overrides = dict(ROLE_STROKES.get(s['role'], {}))
            if hidden:
                opacity = overrides.get('stroke_opacity', 1.0)
                overrides.update(HIDDEN_LOOKS[hidden_look])
                if 'stroke_opacity' in HIDDEN_LOOKS[hidden_look]:
                    overrides['stroke_opacity'] = opacity * HIDDEN_LOOKS[hidden_look]['stroke_opacity']
            if hidden:
                overrides['z_index'] = z_of(min(rank[sid] for sid in piece['hiddenBy']) * Z_RANK
                                            + Z_TIERS['hidden'])
            else:
                overrides['z_index'] = z_of(top)
            a, b = helper(piece['a']), helper(piece['b'])
            add('segment.by_points', {'a': ref(a), 'b': ref(b)}, 'segment', 'segment',
                {'label': {'mode': 'none'}, 'overrides': overrides}, new_id('s'))

    for p in flat['points']:
        el_id = new_id('p')
        appearance = {'label': {'mode': 'name' if labels else 'none'},
                      'overrides': {'size_px': 'presets.point_size.aux'}}
        add('point.free', {}, 'point', 'point', appearance, el_id, display=p['name'])
        doc['inputs'][el_id] = {'kind': 'point', 'value': [float(p['at'][0]), float(p['at'][1])]}
    return doc


def render(flat, out=None, *, fmt='svg', look=None, style_config=None, export_layout=None, report=False):
    """Draw ``flat`` with :func:`animageo.native.render` (needs manim):
    ``svg``, ``png``, ``pdf``, ``eps``, ``tikz``, ``tex``; labels in pixels
    of the sheet (:func:`.bridge.sheet_layout`)."""
    from ..rendering import render as native_render
    from .bridge import sheet_layout
    return native_render(to_document(flat, look=look), style_config=style_config,
                         export_layout=sheet_layout(export_layout), fmt=fmt, out=out, report=report)
