"""The flat scene of a space document: ``animageo-flat-scene/1``.

:func:`flat_scene` evaluates a space document (:mod:`.evaluate`), projects
it through a camera (``viewDefaults.camera`` unless one is given) and
returns the picture the 2D painter draws, in picture units with y up::

    {"format": "animageo-flat-scene/1", "documentId", "camera": {…},
     "scale": S, "bounds": [xmin, ymin, xmax, ymax], "unit": px per unit,
     "solids":  [elementId, …],                                   # far to near (rank 1, 2, …)
     "fills":   [{"id", "part", "role": "face" | "section" | "plane" | "polygon",
                  "solid"?, "facing"? ("front" | "back"), "polygon": [[x, y], …],
                  "depth", "layer"}, …],                          # painting order
     "strokes": [{"id", "part", "role": "edge" | "section" | "segment" | "plane",
                  "solid"?, "pieces": [{"a": [x, y], "b": [x, y], "t": [t0, t1],
                  "visibility": "visible" | "hidden", "occluders": n,
                  "hiddenBy": [solidId, …], "layer"}, …]}, …],
     "points":  [{"id", "name", "at": [x, y], "depth", "visibility"}, …],
     "diagnostics": [{"code", "id", …}, …]}

Every ``id`` is the ID of an element of the document: a face fill — its
``face.k`` element, an edge stroke — its ``edge.k`` element, a point — its
``point3`` element. ``part`` names a piece of an element that has no element
of its own: ``side.k`` of a section (its k-th side), ``border.k``,
``corner.k.j`` or ``trace`` of a plane, else ``null``.

Drawn are the defined elements whose ``appearance.<id>.visible`` is not
``false`` (an edge or a face also needs its solid drawn); a solid that is
not drawn hides nothing. Undefined elements are listed in ``diagnostics``
(``not_defined`` with ``state`` and ``reason``).

The rules of visibility are those of :mod:`.visibility` (spec §3.3): a face
is ``front`` or ``back`` (``side`` faces are not filled); an own edge and an
own vertex are seen when one of their faces is ``front``; any other line or
point is hidden by the shadow volumes of the other solids; a side of a
section takes the visibility of the face it lies on; planes hide nothing; a
line seen end-on keeps its entry with no pieces; a gap or a bit shorter
than ``min_piece_px`` px of the reference frame (``bounds`` across
``SOURCE_WIDTH`` px; ``unit``) merges into its neighbour. A point of two
solids (a vertex of both) is seen when both see it.

``appearance.<id>.visibility`` (a line or a point): ``auto`` (default) and
``strict`` — the rules above (they agree for convex solids, 3D-1); ``always``
— never hidden.

Layers (one rule for the canvas and the document, spec §3.4): ``rank·10 +
tier``; rank 0 — sheets of planes and other polygons, 1, 2, … — the solids
of ``solids``; tiers: plane 0, back faces 1, sections 2, hidden pieces 3,
front faces 4. A hidden piece lies in the tier of the farthest solid that
hides it (the first of ``hiddenBy``; for a hidden own edge — its solid),
visible pieces at ``(len(solids) + 1)·10``. Fills of a layer go far to near.
"""
from __future__ import annotations

from . import vec
from .camera import Camera, Projector
from .document import as_space_document, camera_of
from .evaluate import evaluate
from .flat import CORNER_SHARE, MARGIN, MIN_PIECE_PX, PLANE_LOOKS, SOURCE_WIDTH, Z_RANK, Z_TIERS, _ground_trace
from .ops import plane_of, polyhedron_of, xyz
from .section import Section, plane_sheet, section_visibility
from .solids import scale_of
from .visibility import DECIDE_TOL, ConvexOccluder, edge_visibility, face_facing, pieces, vertex_visibility

__all__ = ['FLAT_SCENE_FORMAT', 'VISIBILITY_POLICIES', 'flat_scene', 'solid_vertex_ids', 'drawn_elements']

FLAT_SCENE_FORMAT = 'animageo-flat-scene/1'
VISIBILITY_POLICIES = ('auto', 'always', 'strict')
SOLID_OPS = ('polyhedron.cube', 'polyhedron.prism', 'polyhedron.pyramid', 'polyhedron.tetrahedron')


def _ids(arg) -> list:
    if not isinstance(arg, dict):
        return []
    if arg.get('kind') == 'ref':
        return [arg.get('elementId')]
    if arg.get('kind') == 'list':
        return [item.get('elementId') for item in arg.get('items') or ()]
    return []


def _outputs(op) -> dict:
    return {out['slot']: out['elementId'] for out in op.get('outputs') or ()}


def solid_vertex_ids(op) -> list:
    """The element IDs of the vertices of a solid operation in the canonical
    order of its value (``None`` where an output is not bound)."""
    args, outs = op['args'], _outputs(op)
    name = op['op']
    if name == 'polyhedron.cube':
        lead = _ids(args.get('a')) + _ids(args.get('b'))
        return lead + [outs.get(f'vertex.{k}') for k in range(1, 7)]
    if name == 'polyhedron.prism':
        base = _ids(args.get('base'))
        return base + _ids(args.get('top')) + [outs.get(f'vertex.{k}') for k in range(1, len(base))]
    if name == 'polyhedron.pyramid':
        return _ids(args.get('base')) + _ids(args.get('apex'))
    if name == 'polyhedron.tetrahedron':
        return [i for slot in ('a', 'b', 'c', 'd') for i in _ids(args.get(slot))]
    return []


def _xy(p):
    return [p[0], p[1]]


def drawn_elements(doc, states) -> set:
    """The IDs of the elements :func:`flat_scene` draws (see the module docstring)."""
    appearance = doc.data.get('appearance') or {}

    def shown(el_id):
        entry = appearance.get(el_id)
        return not (isinstance(entry, dict) and entry.get('visible') is False)

    drawn = {el_id for el_id, rec in states.items() if rec['state'] == 'defined' and shown(el_id)}
    for op in doc.operations.values():
        if op['op'] not in SOLID_OPS:
            continue
        outs = _outputs(op)
        solid = outs.get('solid')
        if solid not in drawn:
            for slot, el_id in outs.items():
                if slot.startswith(('edge.', 'face.')):
                    drawn.discard(el_id)
    return drawn


def _policy(appearance, el_id) -> str:
    entry = appearance.get(el_id)
    policy = entry.get('visibility', 'auto') if isinstance(entry, dict) else 'auto'
    if policy not in VISIBILITY_POLICIES:
        raise ValueError(f'visibility of {el_id!r}: one of {", ".join(VISIBILITY_POLICIES)} expected')
    return policy


def flat_scene(doc, camera=None, *, inputs=None, plane_look='sheet', min_piece_px=MIN_PIECE_PX,
               source_width=SOURCE_WIDTH) -> dict:
    """The flat scene of the space document ``doc`` seen by ``camera`` (a
    :class:`~.camera.Camera`, its dict, or ``None`` — ``viewDefaults.camera``).

    ``plane_look`` — ``sheet`` | ``corners`` | ``trace`` (``space.plane.look``
    of the style). ``ValueError("behind_eye")`` when a perspective eye has a
    drawn point behind or beside it; ``ValueError("empty")`` when nothing is
    drawn.
    """
    if plane_look not in PLANE_LOOKS:
        raise ValueError(f'plane look: one of {", ".join(PLANE_LOOKS)} expected')
    doc = as_space_document(doc)
    if camera is None:
        camera = camera_of(doc)
    elif isinstance(camera, dict):
        camera = Camera.from_dict(camera)
    result = evaluate(doc, inputs=inputs)
    states = result.elements
    elements, ops = doc.elements, doc.operations
    appearance = doc.data.get('appearance') or {}
    drawn = drawn_elements(doc, states)
    diagnostics = [{'code': 'not_defined', 'id': el_id, 'state': rec['state'], 'reason': rec.get('reason')}
                   for el_id, rec in sorted(states.items()) if rec['state'] != 'defined']
    projector = Projector(camera)

    def value(el_id):
        return states[el_id]['value']

    def producer(el_id):
        prod = elements[el_id]['producer']
        return ops[prod['operationId']], prod['slot']

    # ── solids and what belongs to them ──
    solids = []                   # (id, poly, op)
    edge_owner, face_owner, vertex_owners = {}, {}, {}
    for op_id in sorted(ops):
        op = ops[op_id]
        if op['op'] not in SOLID_OPS:
            continue
        outs = _outputs(op)
        sid = outs.get('solid')
        if sid not in drawn:
            continue
        poly = polyhedron_of(value(sid))
        solids.append((sid, poly, op))
        canonical = {tuple(sorted(e)): k for k, e in enumerate(value(sid)['edges'], 1)}
        for k, e in enumerate(poly.edges):
            el_id = outs.get(f'edge.{canonical[(e.a, e.b)]}')
            if el_id is not None:
                edge_owner[el_id] = (sid, k, canonical[(e.a, e.b)])
        for k in range(len(poly.faces)):
            el_id = outs.get(f'face.{k + 1}')
            if el_id is not None:
                face_owner[el_id] = (sid, k)
        for i, el_id in enumerate(solid_vertex_ids(op)):
            if el_id is not None:
                vertex_owners.setdefault(el_id, []).append((sid, i))
    by_id = {sid: (poly, op) for sid, poly, op in solids}

    sections = []                 # (id, solid id, Section)
    for el_id in sorted(drawn):
        if elements[el_id]['type'] != 'section':
            continue
        op, _slot = producer(el_id)
        sid = _ids(op['args'].get('solid'))[0]
        plane = plane_of(value(_ids(op['args'].get('plane'))[0]))
        v = value(el_id)
        cut = Section(plane, tuple(tuple(p) for p in v['polygon']), tuple(tuple(f) for f in v['faces']))
        sections.append((el_id, sid, cut))

    sheets = []                   # (plane id, corners)
    for el_id in sorted(drawn):
        if elements[el_id]['type'] != 'plane':
            continue
        op, _slot = producer(el_id)
        around = [xyz(value(i)) for slot in ('a', 'b', 'c') for i in _ids(op['args'].get(slot))
                  if states.get(i, {}).get('state') == 'defined']
        around += [p for cid, _sid, cut in sections for p in cut.polygon
                   if _ids(producer(cid)[0]['args'].get('plane')) == [el_id]]
        sheets.append((el_id, plane_sheet(plane_of(value(el_id)), around, 0.25)))
    traces = {pid: _ground_trace(corners) for pid, corners in sheets} if plane_look == 'trace' else {}

    # ── the frame ──
    every = [v for _sid, poly, _op in solids for v in poly.vertices]
    every += [p for _id, _sid, cut in sections for p in cut.polygon]
    for el_id in drawn:
        t = elements[el_id]['type']
        if t == 'point3':
            every.append(xyz(value(el_id)))
        elif t == 'segment3':
            every += [tuple(value(el_id)['a']), tuple(value(el_id)['b'])]
        elif t == 'polygon3':
            every += [tuple(p) for p in value(el_id)['vertices']]
    if plane_look == 'trace':
        every += [p for trace in traces.values() if trace for p in trace]
    else:
        every += [c for _pid, corners in sheets for c in corners]
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

    occluders = {sid: ConvexOccluder(poly, projector) for sid, poly, _op in solids}
    facing = {sid: face_facing(poly, projector) for sid, poly, _op in solids}
    order = sorted(solids, key=lambda s: (-projector.project(s[1].centre)[2], s[0]))
    rank = {sid: k + 1 for k, (sid, _p, _o) in enumerate(order)}
    top = (len(rank) + 1) * Z_RANK

    def stroke(el_id, part, role, a, b, own_hidden, owner, solid=None):
        out = {'id': el_id, 'part': part, 'role': role}
        if solid is not None:
            out['solid'] = solid
        pa, pb = projector.project(a), projector.project(b)
        length = vec.norm((pb[0] - pa[0], pb[1] - pa[1], 0.0))
        out['pieces'] = []
        if length <= DECIDE_TOL * scale:              # seen end-on: nothing to draw
            return out
        min_t = min(1.0, min_piece_px / (length * unit))
        hiders = []
        if _policy(appearance, el_id) != 'always':
            if own_hidden:
                hiders.append((owner, (0.0, 1.0)))
            for sid, occ in occluders.items():
                span = occ.hidden_interval(a, b) if sid != owner else None
                if span is not None:
                    hiders.append((sid, span))
        for piece in pieces([span for _, span in hiders], min_t):
            by = sorted({sid for sid, (h0, h1) in hiders if min(h1, piece.t1) > max(h0, piece.t0)},
                        key=rank.get) if piece.hidden else []
            layer = rank[by[0]] * Z_RANK + Z_TIERS['hidden'] if piece.hidden else top
            out['pieces'].append({'a': _xy(projector.project(vec.lerp(a, b, piece.t0))),
                                  'b': _xy(projector.project(vec.lerp(a, b, piece.t1))),
                                  't': [piece.t0, piece.t1],
                                  'visibility': 'hidden' if piece.hidden else 'visible',
                                  'occluders': piece.occluders, 'hiddenBy': by, 'layer': layer})
        return out

    def fill(el_id, part, role, polygon, layer, facing_state=None, solid=None):
        pts = [projector.project(p) for p in polygon]
        out = {'id': el_id, 'part': part, 'role': role}
        if solid is not None:
            out['solid'] = solid
        if facing_state is not None:
            out['facing'] = facing_state
        out.update({'polygon': [_xy(p) for p in pts], 'depth': sum(p[2] for p in pts) / len(pts), 'layer': layer})
        return out

    def far_first(items):
        return sorted(items, key=lambda f: (-f['depth'], f['id'], f['part'] or ''))

    # ── fills ──
    ground = []
    if plane_look == 'sheet':
        ground += [fill(pid, None, 'plane', corners, Z_TIERS['plane']) for pid, corners in sheets]
    for el_id in sorted(drawn):
        if elements[el_id]['type'] == 'polygon3' and el_id not in face_owner:
            ground.append(fill(el_id, None, 'polygon', [tuple(p) for p in value(el_id)['vertices']],
                               Z_TIERS['plane']))
    fills = far_first(ground)
    faces_of = {}
    for el_id, (sid, k) in face_owner.items():
        if el_id in drawn:
            faces_of.setdefault(sid, []).append((k, el_id))
    for sid, poly, _op in order:
        states_ = facing[sid]
        r = rank[sid] * Z_RANK
        back = [fill(el_id, None, 'face', [poly.vertices[i] for i in poly.faces[k]], r + Z_TIERS['back'], 'back', sid)
                for k, el_id in sorted(faces_of.get(sid, ())) if states_[k] == 'back']
        front = [fill(el_id, None, 'face', [poly.vertices[i] for i in poly.faces[k]], r + Z_TIERS['front'], 'front',
                      sid) for k, el_id in sorted(faces_of.get(sid, ())) if states_[k] == 'front']
        fills += far_first(back)
        fills += [fill(cid, None, 'section', list(cut.polygon), r + Z_TIERS['section'], solid=sid)
                  for cid, csid, cut in sections if csid == sid]
        fills += far_first(front)

    # ── strokes ──
    strokes = []
    for sid, poly, _op in solids:
        seen = edge_visibility(poly, projector, facing[sid])
        owned = sorted((canon, k, el_id) for el_id, (s, k, canon) in edge_owner.items() if s == sid and el_id in drawn)
        for _canon, k, el_id in owned:                # in the order of the edge.k outputs
            e = poly.edges[k]
            strokes.append(stroke(el_id, None, 'edge', poly.vertices[e.a], poly.vertices[e.b], not seen[k], sid,
                                  solid=sid))
    for cid, sid, cut in sections:
        poly = by_id[sid][0]
        seen = section_visibility(poly, cut, projector, facing[sid])
        for k, ((p, q), visible) in enumerate(zip(cut.edges(), seen), 1):
            strokes.append(stroke(cid, f'side.{k}', 'section', p, q, not visible, sid, solid=sid))
    for el_id in sorted(drawn):
        if elements[el_id]['type'] == 'segment3' and el_id not in edge_owner:
            v = value(el_id)
            strokes.append(stroke(el_id, None, 'segment', tuple(v['a']), tuple(v['b']), False, None))
    for pid, corners in sheets:
        if plane_look == 'trace':
            if traces.get(pid):
                strokes.append(stroke(pid, 'trace', 'plane', *traces[pid], False, None))
            continue
        for k in range(4):
            a, b = corners[k], corners[(k + 1) % 4]
            if plane_look == 'sheet':
                strokes.append(stroke(pid, f'border.{k + 1}', 'plane', a, b, False, None))
            else:
                for j, (p, q) in enumerate(((a, vec.lerp(a, b, CORNER_SHARE)), (b, vec.lerp(b, a, CORNER_SHARE))), 1):
                    strokes.append(stroke(pid, f'corner.{k + 1}.{j}', 'plane', p, q, False, None))

    # ── points ──
    vertex_seen = {sid: vertex_visibility(poly, projector, facing[sid]) for sid, poly, _op in solids}
    points = []
    for el_id in sorted(drawn):
        if elements[el_id]['type'] != 'point3':
            continue
        at = xyz(value(el_id))
        owners = [(sid, i) for sid, i in vertex_owners.get(el_id, ()) if sid in occluders]
        own = {sid for sid, _i in owners}
        hidden = False
        if _policy(appearance, el_id) != 'always':
            hidden = any(not vertex_seen[sid][i] for sid, i in owners) or \
                any(occ.hides(at) for sid, occ in occluders.items() if sid not in own)
        pr = projector.project(at)
        points.append({'id': el_id, 'name': elements[el_id].get('displayName') or el_id, 'at': _xy(pr),
                       'depth': pr[2], 'visibility': 'hidden' if hidden else 'visible'})

    return {'format': FLAT_SCENE_FORMAT, 'documentId': doc.document_id, 'camera': camera.to_dict(),
            'scale': scale, 'bounds': bounds, 'unit': unit, 'solids': [sid for sid, _p, _o in order],
            'fills': fills, 'strokes': strokes, 'points': points, 'diagnostics': diagnostics}
