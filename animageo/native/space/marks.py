"""Derived school marks. The bridge carries geometry to the final sheet layout."""
from __future__ import annotations

import math
from types import SimpleNamespace

from ..kernel.ops import OpContext
from ..kernel.values import Undefined
from ..paint import _ticks
from . import vec
from .camera import Camera, Projector, _line_interval
from .ops import _line_carrier, _p, _plane_carrier, _point3_projection_line, _point3_projection_plane, polyhedron_of, xyz
from .section import plane_basis
from .visibility import ConvexOccluder

SPACE_MARKS_FORMAT = 'animageo-space-marks/v1'
_PERPENDICULAR = ('line3.perpendicular_line', 'line3.perpendicular_plane')
# One, two and three ticks; a further class of equal lengths has no marks of its own.
MAX_TICK_CLASSES = 3
_DIAGNOSTICS = ('mark_classes_exhausted',)


def _rounding(size):
    """The rounding of coordinates of ``size``, in their units (64 ulps)."""
    return 64 * math.ulp(size)


def _match_tol(eps, projector, *points):
    """``eps`` widened by the rounding of the world and picture coordinates of
    ``points`` seen by ``projector``: a scene far from the origin keeps its
    marks (a picture coordinate subtracts the target or the eye)."""
    camera = projector.camera
    size = max(abs(c) for p in (*points, camera.target) for c in p)
    if not projector.parallel:
        size += camera.distance
    return eps + _rounding(size)


def _square_tol(foot, length):
    """The tolerance of the right angle between two unit arms from ``foot``
    to a point at ``length``: the rounding of their coordinates."""
    return 1e-9 + _rounding(max(map(abs, foot)) + length) / length


def _on_segment(p, a, b, eps):
    length = math.dist(a, b)
    if length <= eps:
        return False
    direction = [(y - x) / length for x, y in zip(a, b)]
    offset = [y - x for x, y in zip(a, p)]
    along = sum(d * x for d, x in zip(direction, offset))
    return -eps <= along <= length + eps and math.hypot(*(x - along * d for d, x in zip(direction, offset))) <= eps


def _visible_piece(strokes, p, eps):
    return next(((pid, piece) for stroke, ids in strokes for piece, pid in zip(stroke['pieces'], ids)
                 if pid and piece['visibility'] == 'visible' and _on_segment(p, piece['a'], piece['b'], eps)), None)


def _ids(op):
    return [out['elementId'] for out in op['outputs']]


def _midpoint_guides(segments, op_id, a, middle, b, projector, eps):
    eps = _match_tol(eps, projector, a, b)
    guides = []
    for half, (start, end) in enumerate(((a, middle), (middle, b)), 1):
        at = projector.project(vec.lerp(start, end, 0.5))[:2]
        ends = [projector.project(p)[:2] for p in (start, end)]
        if math.dist(*ends) <= eps:
            continue
        for (x, y), stroke in segments:
            if not (_on_segment(start, x, y, eps) and _on_segment(end, x, y, eps)):
                continue
            visible = _visible_piece([stroke], at, eps)
            if visible is None:
                continue
            pid, piece = visible
            start2, end2 = ends
            dx, dy = end2[0] - start2[0], end2[1] - start2[1]
            guides.append({'kind': 'ticks', 'source': op_id, 'half': half, 'planeId': pid,
                           'at': at, 'direction': [dx, dy], 'layer': piece['layer']})
            break
    return guides


def _picture_vector(projector, foot, arm):
    dx, dy, dz = projector._coordinates(arm)
    if projector.parallel:
        return dx, dy
    x, y, _ = projector.project(foot)
    distance = projector.camera.distance
    return distance * dx - x * dz, distance * dy - y * dz


def _unit_picture(projector, foot, arm):
    vx, vy = _picture_vector(projector, foot, arm)
    length = math.hypot(vx, vy)
    return (vx / length, vy / length) if length > 1e-10 else (0.0, 0.0)


def _piece_room(piece, at, tangent):
    return max(sum((value - origin) * d for value, origin, d in zip(piece[k], at, tangent))
               for k in ('a', 'b'))


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _polygon_room(polygon, at, tangent, eps):
    edges = list(zip(polygon, [*polygon[1:], polygon[0]]))
    area = sum(_cross2(a, b) for a, b in edges)
    if abs(area) <= eps * eps or tangent == (0.0, 0.0):
        return 0.0
    sign = math.copysign(1, area)
    planes = [(0.0, 1.0)]
    for a, b in edges:
        edge = b[0] - a[0], b[1] - a[1]
        local = at[0] - a[0], at[1] - a[1]
        inside = sign * _cross2(edge, local) + eps * math.hypot(*edge)
        if inside < 0:
            return 0.0
        planes.append((inside, sign * _cross2(edge, tangent)))
    span = _line_interval(planes)
    return span[1] if span is not None else 0.0


def _right_guide(op_id, element_id, ref, name, args, by_id, fills, projector, near, occluders, ctx, appearance):
    eps = ctx.tol.decide_length
    overrides = (appearance.get(element_id) or {}).get('overrides') or {}
    if overrides.get('right_angle_marker') is False:
        return None
    point = _p(args['point'])
    on_line = name == _PERPENDICULAR[0]
    projection = _point3_projection_line if on_line else _point3_projection_plane
    foot = projection(args, ctx)['point']
    if isinstance(foot, Undefined):
        return None
    foot = xyz(foot)
    x, y, depth = projector.project(foot)
    at = x, y
    length = vec.dist(point, foot)
    if (length <= eps or (not projector.parallel and depth <= near)
            or any(occ.hides(foot) for occ in occluders)):
        return None
    match = _match_tol(eps, projector, foot, point)
    visible = _visible_piece(by_id.get(element_id, ()), at, match)
    if visible is None:
        return None
    pid, piece = visible
    along = vec.mul(vec.sub(point, foot), 1 / length)
    reach_along = _piece_room(piece, at, _unit_picture(projector, foot, along))
    if reach_along <= eps:
        return None
    if on_line:
        axis = _line_carrier(args['line'], ctx)
        if isinstance(axis, Undefined):
            return None
        support = _visible_piece(by_id.get(ref, ()), at, match)
        if support is None:
            return None
        if args['line'].type == 'segment3':
            value = args['line'].value
            if not _on_segment(foot, tuple(value['a']), tuple(value['b']), match):
                return None
        tangent = axis[1]
        candidates = (tangent, vec.mul(tangent, -1))
        options = [(arm, _piece_room(support[1], at, _unit_picture(projector, foot, arm))) for arm in candidates]
    else:
        _, normal = _plane_carrier(args['plane'])
        options = []
        basis = plane_basis(normal)
        candidates = (*basis, *[vec.mul(arm, -1) for arm in basis])
        polygons = [f['polygon'] for f, _ in fills if f['id'] == ref and f.get('facing') != 'back']
        for arm in candidates:
            direction = _unit_picture(projector, foot, arm)
            options.extend((arm, _polygon_room(polygon, at, direction, eps)) for polygon in polygons)
    if not options:
        return None
    tangent, reach_cross = max(options, key=lambda option: option[1])
    if (not math.isfinite(reach_cross) or reach_cross <= eps
            or abs(vec.dot(along, tangent)) > _square_tol(foot, length)):
        return None
    size = overrides.get('right_angle_size_px')
    return {'kind': 'right_angle', 'source': op_id, 'planeId': pid, 'layer': piece['layer'], 'foot': foot,
            'arms': [along, tangent], 'length': length, 'reach': [reach_along, reach_cross],
            'sizePx': size if _positive(size) or (isinstance(size, str) and size.startswith('presets.')) else None}


def prepare_marks(doc, evaluated, flat, index):
    """The visible carriers and world angle data needed on the final sheet."""
    camera = Camera.from_dict(flat['camera'])
    result = {'format': SPACE_MARKS_FORMAT, 'camera': camera.to_dict(), 'scale': flat['scale'], 'guides': [],
              'diagnostics': []}
    data, ops = doc.data, doc.operations
    settings = (data.get('viewDefaults') or {}).get('autoMarks') or {}
    appearance = data.get('appearance') or {}
    suppressed = {(item.get('source'), item.get('kind')) for item in data.get('suppressedMarks') or ()}
    relevant = [item for item in evaluated.computed.items()
                if (item[1][0] == 'point3.midpoint' and settings.get('equalities', True))
                or (item[1][0] in _PERPENDICULAR and settings.get('rightAngles', True))]
    if not relevant:
        return result
    projector = Projector(camera)
    eps = evaluated.tolerances.decide_length
    ctx = OpContext(evaluated.tolerances)
    by_id, segments = {}, []
    for stroke, ids in index['strokes']:
        sid = stroke['id']
        by_id.setdefault(sid, []).append((stroke, ids))
        state = evaluated.elements[sid]
        if state['type'] == 'segment3':
            value = state['value']
            segments.append(((tuple(value['a']), tuple(value['b'])), (stroke, ids)))
    segments.sort(key=lambda item: math.dist(*item[0]))
    visible_points = {p['id'] for p in index['points'] if p['visibility'] == 'visible'}
    occluders = [ConvexOccluder(polyhedron_of(evaluated.elements[sid]['value']), projector) for sid in flat['solids']]
    lengths = []
    for op_id, (name, args, values) in relevant:
        el_ids = _ids(ops[op_id])
        if name == 'point3.midpoint':
            if (op_id, 'equal_segments') in suppressed or not visible_points.intersection(el_ids):
                continue
            a, b = _p(args['a']), _p(args['b'])
            length = vec.dist(a, b)
            if length <= eps:
                continue
            guides = _midpoint_guides(segments, op_id, a, xyz(values['point']), b, projector, eps)
            if not guides:
                continue
            group = next((i for i, other in enumerate(lengths) if abs(length - other) <= evaluated.tolerances.check_passed),
                         len(lengths))
            if group == len(lengths):
                lengths.append(length)
            if group >= MAX_TICK_CLASSES:
                # Three ticks would claim an equality with the third class.
                result['diagnostics'].append({'code': 'mark_classes_exhausted', 'source': op_id})
                continue
            result['guides'].extend({**guide, 'count': group + 1} for guide in guides)
        elif (op_id, 'right_angle') not in suppressed:
            ref = ops[op_id]['args']['line' if name == _PERPENDICULAR[0] else 'plane'].get('elementId')
            guide = _right_guide(op_id, el_ids[0], ref, name, args, by_id, index['fills'], projector,
                                 1e-6 * flat['scale'], occluders, ctx, appearance)
            if guide is not None:
                result['guides'].append(guide)
    return result


def _finite(value):
    return type(value) in (int, float) and -math.inf < value < math.inf


def _positive(value):
    return _finite(value) and value > 0


def _coords(value, n):
    return isinstance(value, (list, tuple)) and len(value) == n and all(map(_finite, value))


def _sheet(doc):
    """The frame of the sheet widened by its size on every side, and that size."""
    bounds = (doc.data.get('viewDefaults') or {}).get('bounds')
    if not (_coords(bounds, 4) and bounds[0] < bounds[2] and bounds[1] < bounds[3]):
        raise ValueError('invalid space mark sheet')
    room = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    if not _positive(room):
        raise ValueError('invalid space mark sheet')
    return (bounds[0] - room, bounds[1] - room, bounds[2] + room, bounds[3] + room), room


def _on_sheet(point, frame):
    return (len(point) >= 2 and _finite(point[0]) and _finite(point[1])
            and frame[0] <= point[0] <= frame[2] and frame[1] <= point[1] <= frame[3])


def _diagnostics(items, limit):
    return isinstance(items, list) and len(items) <= limit and all(
        isinstance(item, dict) and set(item) == {'code', 'source'} and item['code'] in _DIAGNOSTICS
        and isinstance(item['source'], str) for item in items)


def checked_marks(sidecar, doc):
    """Accept only the data produced by the space bridge, across process boundaries.

    Every position lies on the sheet (``viewDefaults.bounds`` of the plane
    document) widened by its size; a tick direction and a reach are at most
    twice that size."""
    if sidecar is None:
        return None
    # ``diagnostics`` is new in 1.21.1; a sidecar of 1.21.0 has none.
    if (not isinstance(sidecar, dict) or set(sidecar) - {'diagnostics'} != {'format', 'camera', 'scale', 'guides'}
            or sidecar['format'] != SPACE_MARKS_FORMAT or not _positive(sidecar['scale'])
            or not isinstance(sidecar['guides'], list) or len(sidecar['guides']) > 2 * len(doc.elements)
            or not _diagnostics(sidecar.get('diagnostics', []), 2 * len(doc.elements))):
        raise ValueError('invalid space mark sidecar')
    camera = Camera.from_dict(sidecar['camera'])
    if camera.to_dict() != sidecar['camera']:
        raise ValueError('invalid space mark camera')
    if not sidecar['guides']:
        return camera
    frame, room = _sheet(doc)
    projector = Projector(camera)
    for guide in sidecar['guides']:
        if (not isinstance(guide, dict) or not isinstance(guide.get('source'), str)
                or not isinstance(guide.get('planeId'), str)
                or doc.elements.get(guide['planeId'], {}).get('type') != 'segment'
                or type(guide.get('layer')) is not int or guide['layer'] < 0):
            raise ValueError('invalid space mark carrier')
        keys = {'kind', 'source', 'planeId', 'layer'}
        if guide.get('kind') == 'ticks':
            valid = (set(guide) == keys | {'at', 'direction', 'half', 'count'} and _coords(guide['at'], 2)
                     and _coords(guide['direction'], 2) and type(guide['half']) is int and guide['half'] in (1, 2)
                     and type(guide['count']) is int and 1 <= guide['count'] <= 3
                     and _on_sheet(guide['at'], frame) and math.hypot(*guide['direction']) <= 2 * room)
        elif guide.get('kind') == 'right_angle':
            valid = (set(guide) == keys | {'foot', 'arms', 'length', 'reach', 'sizePx'} and _coords(guide['foot'], 3)
                     and isinstance(guide['arms'], (list, tuple)) and len(guide['arms']) == 2
                     and all(_coords(arm, 3) and abs(vec.norm(arm) - 1) <= 1e-9 for arm in guide['arms'])
                     and _positive(guide['length'])
                     and abs(vec.dot(*guide['arms'])) <= _square_tol(guide['foot'], guide['length'])
                     and _coords(guide['reach'], 2) and all(map(_positive, guide['reach']))
                     and max(guide['reach']) <= 2 * room and _on_sheet(projector.project(guide['foot']), frame)
                     and (guide['sizePx'] is None or _positive(guide['sizePx'])
                          or (isinstance(guide['sizePx'], str) and guide['sizePx'].startswith('presets.'))))
        else:
            valid = False
        if not valid:
            raise ValueError('invalid space mark geometry')
    return camera


def _arm(projector, foot, direction, size, near, limit):
    # Solve for the world arclength giving the requested displacement on the
    # picture. In perspective both numerator and depth are affine on the ray.
    rate = math.hypot(*_picture_vector(projector, foot, direction))
    if projector.parallel:
        length = size / rate if rate > 1e-10 else None
    else:
        _, _, depth = projector.project(foot)
        _, _, dz = projector._coordinates(direction)
        denom = rate - size * dz
        length = size * depth / denom if depth > near and rate > 1e-10 and denom > 0 else None
    if length is None or not math.isfinite(length) or (limit is not None and length > limit):
        return None
    return vec.mul(direction, length)


def projected_marks(sidecar, camera, unit, elements, cfg):
    projector = Projector(camera)
    near = 1e-6 * sidecar['scale']
    for guide in sidecar['guides']:
        item = elements.get(guide['planeId']) or {}
        stroke = item.get('stroke') or {}
        if not item.get('drawn') or stroke.get('opacity', 0) <= 0 or stroke.get('widthPx', 0) <= 0:
            continue
        common = {key: guide[key] for key in ('kind', 'source', 'layer')}
        common.update({'color': stroke['color'], 'opacity': stroke['opacity'], 'z': stroke['z'] + 0.01})
        if guide['kind'] == 'ticks':
            (x, y), (dx, dy) = guide['at'], guide['direction']
            carrier = SimpleNamespace(endpoints=((x - dx / 2, y - dy / 2), (x + dx / 2, y + dy / 2)),
                                      normal=(-dy, dx))
            style = item['ticks']
            tick = _ticks('segment', carrier, unit, {
                'tick_count': guide['count'], 'tick_length_px': style['lengthPx'],
                'tick_width_px': style['widthPx'], 'tick_shift_px': style['shiftPx'],
            }.get)
            if (tick.get('lines') and tick['lengthPx'] > 0 and tick['widthPx'] > 0
                    and all(map(math.isfinite, (c for line in tick['lines'] for c in line)))):
                yield {**common, **tick, 'half': guide['half'], 'at': [x, y]}
            continue
        size = cfg.resolve_ref(guide['sizePx'])
        if not _positive(size):
            size = cfg.resolve_ref(cfg.defaults.get('angle', 'right_angle_size_px'))
        if not _positive(size):
            continue
        foot = guide['foot']
        r = size / math.sqrt(2) / unit
        if r > min(guide['reach']):
            continue
        along, across = guide['arms']
        a = _arm(projector, foot, along, r, near, guide['length'])
        b = _arm(projector, foot, across, r, near, None)
        if a is None or b is None:
            continue
        corners = [projector.project(vec.add(foot, offset)) for offset in ((0, 0, 0), a, vec.add(a, b), b)]
        if not all(map(math.isfinite, (c for corner in corners for c in corner))):
            continue
        origin, v1, _, v2 = corners
        area = (v1[0] - origin[0]) * (v2[1] - origin[1]) - (v1[1] - origin[1]) * (v2[0] - origin[0])
        if abs(area) <= r * r * 1e-8 or (not projector.parallel and min(p[2] for p in corners) <= near):
            continue
        yield {**common, 'sizePx': size, 'widthPx': stroke['widthPx'], 'corners': [list(p[:2]) for p in corners]}


def draw_marks(construction, marks):
    """Append ordinary, unlabelled plane strokes to the renderer/solver construction."""
    import numpy as np
    from ...geo import construction as geo

    for i, mark in enumerate(marks):
        if mark['kind'] == 'ticks':
            lines = [(line[:2], line[2:]) for line in mark['lines']]
        else:
            _, a, corner, b = mark['corners']
            lines = [(a, corner), (corner, b)]
        for j, (a, b) in enumerate(lines):
            name = f'space_mark_{i}_{j}'
            elem = geo.Element(name, geo.Segment(np.array(a), np.array(b)))
            elem.style.update({'label_mode': 'none', 'stroke': mark['color'], 'stroke_opacity': mark['opacity'],
                               'stroke_width_px': mark['widthPx'], 'stroke_linecap': 'butt', 'tick_count': 0,
                               'stroke_dash_ratio': 0, 'stroke_dash_pattern_px': [], 'z_index': mark['z']})
            construction.add(elem)
