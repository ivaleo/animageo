"""The flicker metric of the flat scene (spec §8, gate of 3D-1).

The camera walks the orbit by azimuth ``0…360°`` with a step on a few
elevations; on every line of the flat scene (a stroke: an element, or a
part of one) the visibility is sampled at ``samples`` points ``t = (j +
½) / samples`` of its parameter, and every drawn point is sampled too. An
**event** is

- ``blink`` — the view of a sample (``visible`` | ``hidden``) changes on
  one step of the camera and comes back on the next (``a → b → a``); a true
  change (a vertex crossing the silhouette) lasts longer than a step and is
  not an event. A line seen end-on has no pieces (``none``): its length on
  the sheet passes through zero continuously, so a step through ``none``
  (``a → none → a``) is not an event, and ``none`` is not compared. A
  candidate is probed at a quarter step on both sides: when either probe
  also shows ``b`` the episode has a real width (two true changes within
  one step — a line parallel to an edge crossing it right after a boundary
  passed the sample) and is not an event; flicker of the numbers is
  narrower than that;
- ``short`` — a piece shorter than the merge threshold (``MIN_PIECE_PX`` px
  of the reference frame) on a line cut into two or more pieces
  (``min_piece_px`` — the merge threshold the flat scenes are cut with; the
  check is always against ``MIN_PIECE_PX``).

:func:`flicker_events` lists the events of one document; the gate of 3D-1
is none on the degenerate scenes of :func:`degenerate_scenes` (an edge
along the view, a face seen edge-on, a plane through vertices or along an
edge, a section touching a solid, a side of a section on an edge, points
and segments on faces, solids sharing a face).
"""
from __future__ import annotations

import math

from .build import SpaceBuilder
from .evaluate import evaluate
from .flat import MIN_PIECE_PX
from .scene import flat_scene

__all__ = ['ELEVATIONS', 'flicker_events', 'degenerate_scenes']

ELEVATIONS = (0.0, 20.0, 89.5)


def _view(stroke, t):
    for piece in stroke['pieces']:
        if piece['t'][0] <= t <= piece['t'][1]:
            return piece['visibility']
    return 'none'


def _sample(flat, samples):
    out = {}
    ts = [(j + 0.5) / samples for j in range(samples)]
    for s in flat['strokes']:
        key = (s['id'], s['part'])
        for j, t in enumerate(ts):
            out[(key, j)] = _view(s, t)
    for p in flat['points']:
        out[((p['id'], 'point'), 0)] = p['visibility']
    return out


def _short(flat, min_px):
    unit = flat['unit']
    found = []
    for s in flat['strokes']:
        if len(s['pieces']) < 2:
            continue
        for k, p in enumerate(s['pieces']):
            length = math.hypot(p['b'][0] - p['a'][0], p['b'][1] - p['a'][1]) * unit
            if length < min_px:
                found.append({'id': s['id'], 'part': s['part'], 'piece': k, 'px': length})
    return found


def flicker_events(doc, *, elevations=ELEVATIONS, step_deg=1.0, samples=32, projection='orthographic',
                   distance=None, target=None, min_piece_px=MIN_PIECE_PX) -> list:
    """The flicker events of ``doc`` on the orbit (``[{kind, …}]``; empty —
    no flicker). ``target`` — the centre of the orbit (the camera's of the
    document, else the centre of the drawn points' box)."""
    evaluated = evaluate(doc)
    steps = int(round(360.0 / step_deg))
    events = []
    if target is None:
        first = flat_scene(doc, {'azimuthDeg': 0, 'elevationDeg': 20}, evaluated=evaluated)
        target = _centre(doc, evaluated, first)
    for el in elevations:
        views = []
        for k in range(steps):
            camera = {'projection': projection, 'azimuthDeg': k * step_deg, 'elevationDeg': el,
                      'target': list(target)}
            if projection == 'perspective':
                camera['distance'] = distance
            flat = flat_scene(doc, camera, evaluated=evaluated, min_piece_px=min_piece_px)
            for item in _short(flat, MIN_PIECE_PX):
                events.append(dict(item, kind='short', azimuthDeg=k * step_deg, elevationDeg=el))
            views.append(_sample(flat, samples))
        def probe(az):
            camera = {'projection': projection, 'azimuthDeg': az, 'elevationDeg': el, 'target': list(target)}
            if projection == 'perspective':
                camera['distance'] = distance
            return _sample(flat_scene(doc, camera, evaluated=evaluated, min_piece_px=min_piece_px), samples)

        for k in range(steps):
            before, now, after = views[k - 1], views[k], views[(k + 1) % steps]
            probes = None
            for key, value in now.items():
                if value == 'none' or before.get(key, 'none') == 'none' or after.get(key, 'none') == 'none':
                    continue
                if before[key] == after[key] != value:
                    if probes is None:
                        probes = (probe(k * step_deg - step_deg / 4), probe(k * step_deg + step_deg / 4))
                    if any(p.get(key) == value for p in probes):
                        continue
                    (el_id, part), j = key
                    events.append({'kind': 'blink', 'id': el_id, 'part': part, 'sample': j,
                                   'azimuthDeg': k * step_deg, 'elevationDeg': el,
                                   'views': [before[key], value, after[key]]})
    return events


def _centre(doc, evaluated, flat):
    from .ops import xyz
    pts = [xyz(rec['value']) for rec in evaluated.elements.values()
           if rec['state'] == 'defined' and rec['type'] == 'point3']
    if not pts:
        return [0.0, 0.0, 0.0]
    return [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)]


# ── the degenerate scenes of the gate ────────────────────────────────────

def _cube(b, a=(0, 0, 0), bb=(2, 0, 0)):
    b.point('A', *a)
    b.point('B', *bb)
    return b.cube('K', 'A', 'B', vertices=['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'])


def _cut(b, solid, a, bb, c):
    for label, p in zip(('U', 'V', 'W'), (a, bb, c)):
        b.point(label, *p)
    b.plane('P', 'U', 'V', 'W')
    b.section('S', 'P', solid)


def degenerate_scenes() -> list:
    """``[(name, document)]`` — ten scenes with the degenerate cases of §3.3."""
    out = []
    b = SpaceBuilder('cube_axes')                      # edges along the view, faces edge-on at elevation 0
    _cube(b)
    out.append(('cube_axes', b.data()))
    b = SpaceBuilder('plane_through_vertices')
    _cube(b)
    _cut(b, 'K', (0, 0, 0), (2, 2, 0), (2, 2, 2))
    out.append(('plane_through_vertices', b.data()))
    b = SpaceBuilder('side_on_edge')
    _cube(b)
    _cut(b, 'K', (0, 0, 0), (2, 0, 0), (2, 2, 2))
    out.append(('side_on_edge', b.data()))
    b = SpaceBuilder('touch_vertex')
    _cube(b)
    _cut(b, 'K', (2, 2, 2), (4, 2, 0), (2, 4, 0))
    out.append(('touch_vertex', b.data()))
    b = SpaceBuilder('touch_edge')
    _cube(b)
    _cut(b, 'K', (4, 0, 0), (0, 4, 0), (2, 2, 2))
    out.append(('touch_edge', b.data()))
    b = SpaceBuilder('on_faces')
    cube = _cube(b)
    b.on_edge('M', cube.edge(9), 0.5)
    b.on_edge('N', cube.edge(3), 0.25)
    b.on_face('F', cube.face(2), 0.25, 0.75)
    b.on_face('G', cube.face(4), 0.5, 0.5)
    b.segment('s', 'F', 'G')
    b.segment('r', 'M', 'C_1')
    out.append(('on_faces', b.data()))
    b = SpaceBuilder('tetra_mid_section')
    for label, p in zip('ABCD', [(0, 0, 0), (4, 0, 0), (0, 4, 0), (0, 0, 4)]):
        b.point(label, *p)
    b.tetrahedron('T', 'A', 'B', 'C', 'D')
    b.midpoint('X', 'A', 'B')
    b.midpoint('Y', 'A', 'C')
    b.midpoint('Z', 'A', 'D')
    b.plane('P', 'X', 'Y', 'Z')
    b.section('S', 'P', 'T')
    out.append(('tetra_mid_section', b.data()))
    b = SpaceBuilder('pyramid_horizontal_section')    # the section is edge-on at elevation 0
    ids = []
    for k in range(4):
        a = math.pi / 2 * k
        ids.append(b.point(f'Q{k}', 2 * math.cos(a), 2 * math.sin(a), 0))
    b.point('X', 0, 0, 3)
    b.pyramid('Y', ids, 'X')
    _cut(b, 'Y', (0, 0, 1), (1, 0, 1), (0, 1, 1))
    out.append(('pyramid_horizontal_section', b.data()))
    b = SpaceBuilder('prism_right_hexagon')           # vertical faces edge-on at elevation 0
    ids = []
    for k in range(6):
        a = math.pi / 3 * k
        ids.append(b.point(f'Q{k}', 1.5 * math.cos(a), 1.5 * math.sin(a), 0))
    b.point('X', 1.5, 0, 3)
    b.prism('Z', ids, 'X')
    out.append(('prism_right_hexagon', b.data()))
    b = SpaceBuilder('pyramid_on_cube')               # two solids sharing a face
    _cube(b)
    b.point('S', 1, 1, 3.5)
    b.pyramid('Y', ['A_1', 'B_1', 'C_1', 'D_1'], 'S')
    out.append(('pyramid_on_cube', b.data()))
    return out
