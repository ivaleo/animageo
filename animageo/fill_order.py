"""Internal, stateless fill geometry and display plans (no manim dependency).

Areas are measured in style pixels squared, before clipping or occlusion.
The structural plan deliberately keeps exact effective layers: ranks never
become numeric offsets in a user's style.
"""
from __future__ import annotations

import math
from functools import lru_cache
from dataclasses import dataclass

from .constants import Z_FILL


@dataclass(frozen=True)
class FillPart:
    id: str
    construction_index: int
    stable_index: tuple
    area_style_px2: float
    layer_z: float
    automatic: bool


@dataclass(frozen=True)
class PaintPart:
    id: str
    part: str
    layer_z: float
    stable_index: tuple


def _area_order(parts, rtol):
    pending = sorted(parts, key=lambda p: (-p.area_style_px2, p.construction_index, p.id))
    result = []
    start = 0
    while start < len(pending):
        end = start + 1
        ref = pending[start].area_style_px2
        while end < len(pending) and ref - pending[end].area_style_px2 <= rtol * ref:
            end += 1
        result.extend(sorted(pending[start:end], key=lambda p: (p.construction_index, p.id)))
        start = end
    return result


def order_fills(parts, *, mode, area_rtol=1e-9) -> tuple:
    """Fill IDs, bottom to top; fixed slots survive equal-layer sorting."""
    if mode not in ('area', 'construction'):
        raise ValueError('fill_order must be area or construction')
    parts = [p for p in parts if math.isfinite(p.area_style_px2) and p.area_style_px2 > 0]
    layer = lambda p: Z_FILL if mode == 'area' and p.automatic else p.layer_z
    ordered = sorted(parts, key=lambda p: (layer(p), p.stable_index, p.id))
    if mode == 'area':
        start = 0
        while start < len(ordered):
            end = start + 1
            while end < len(ordered) and layer(ordered[end]) == layer(ordered[start]):
                end += 1
            slots = [i for i in range(start, end) if ordered[i].automatic]
            for i, part in zip(slots, _area_order([ordered[i] for i in slots], area_rtol)):
                ordered[i] = part
            start = end
    return tuple(p.id for p in ordered)


def order_paint_parts(parts, fill_order) -> tuple:
    """Merge the fill projection into equal-layer slots of the full plan."""
    rank = {owner: i for i, owner in enumerate(fill_order)}
    ordered = sorted(parts, key=lambda p: (p.layer_z, p.stable_index, p.id, p.part))
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end].layer_z == ordered[start].layer_z:
            end += 1
        slots = [i for i in range(start, end) if ordered[i].part == 'fill' and ordered[i].id in rank]
        for i, part in zip(slots, sorted((ordered[i] for i in slots), key=lambda p: rank[p.id])):
            ordered[i] = part
        start = end
    return tuple({'id': p.id, 'part': p.part} for p in ordered)


def polygon_area(vertices, *, rule='nonzero') -> float:
    """Measure a polygon's filled set by exact linear scan strips.

    Vertices and proper edge intersections delimit strips. Within one strip
    the active edges cannot cross, so filled interval lengths are linear.
    Horizontal edges are ignored; all others use the same [low, high) rule.
    Coincident edges contribute together, including reverse/repeated edges.
    """
    return _polygon_area(tuple((float(p[0]), float(p[1])) for p in vertices), rule)


@lru_cache(maxsize=256)
def _polygon_area(vertices, rule):
    if rule not in ('nonzero', 'evenodd'):
        raise ValueError('polygon rule must be nonzero or evenodd')
    points = list(vertices)
    if len(points) < 3:
        return 0.0
    ox, oy = points[0]
    points = [(x - ox, y - oy) for x, y in points]
    if _simple_polygon(points):
        return abs(math.fsum(a[0]*b[1] - b[0]*a[1]
                             for a, b in zip(points, points[1:] + points[:1]))) / 2
    edges = [(a, b) for a, b in zip(points, points[1:] + points[:1]) if a[1] != b[1]]
    levels = {p[1] for p in points}
    for i, (a, b) in enumerate(edges):
        dx, dy = b[0] - a[0], b[1] - a[1]
        for c, d in edges[i + 1:]:
            ex, ey = d[0] - c[0], d[1] - c[1]
            den = dx * ey - dy * ex
            if den == 0:
                continue
            qx, qy = c[0] - a[0], c[1] - a[1]
            t, s = (qx * ey - qy * ex) / den, (qx * dy - qy * dx) / den
            if 0 < t < 1 and 0 < s < 1:
                levels.add(a[1] + t * dy)

    # Evaluate a reversed edge from the same lower endpoint. This makes
    # cancellation exact without erasing genuinely thin positive domains.
    scan_edges = [(a, b, 1) if b[1] > a[1] else (b, a, -1) for a, b in edges]

    def width(y):
        crossings = sorted((a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]),
                            sign)
                           for a, b, sign in scan_edges if a[1] <= y < b[1])
        winding, previous, spans = 0, 0.0, []
        for x, sign in crossings:
            if (winding != 0 if rule == 'nonzero' else winding % 2 != 0):
                spans.append(x - previous)
            winding += sign
            previous = x
        return math.fsum(spans)

    levels = sorted(levels)
    return math.fsum((hi - lo) * (width(lo + (hi - lo) / 4) + width(lo + 3 * (hi - lo) / 4)) / 2
                     for lo, hi in zip(levels, levels[1:]))


def _simple_polygon(points):
    """Conservative edge sweep: use shoelace only for a simple contour.

    X intervals prune inactive edges; disjoint Y intervals cannot intersect.
    Nonadjacent touches and overlaps use the winding-aware strip integrator,
    as do backtracking adjacent edges. Ordinary collinear vertices are safe.
    """
    edges = [(a, b) for a, b in zip(points, points[1:] + points[:1]) if a != b]
    if len(edges) < 3:
        return False
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    records = sorted((min(a[0],b[0]), max(a[0],b[0]), min(a[1],b[1]), max(a[1],b[1]), i, a, b)
                     for i, (a,b) in enumerate(edges))
    active = []
    n = len(edges)
    for record in records:
        lo, hi, bottom, top, i, a, b = record
        active = [old for old in active if old[1] >= lo]
        for _, _, old_bottom, old_top, j, c, d in active:
            if old_top < bottom or top < old_bottom:
                continue
            if (i-j) % n in (1, n-1):
                common, p, q = (a,b,c) if a == d else (b,a,d)
                if cross(common,p,q) == 0 and ((p[0]-common[0])*(q[0]-common[0]) +
                                               (p[1]-common[1])*(q[1]-common[1])) > 0:
                    return False
                continue
            u, v, w, z = cross(a,b,c), cross(a,b,d), cross(c,d,a), cross(c,d,b)
            if (u <= 0 <= v or v <= 0 <= u) and (w <= 0 <= z or z <= 0 <= w):
                return False
        active.append(record)
    return True


def circle_segment_area(radius, sweep) -> float:
    """Chord-closed arc area, stable for a small positive sweep."""
    t = float(sweep)
    delta = t**3 * (1 / 6 - t*t / 120 + t**4 / 5040 - t**6 / 362880) if abs(t) < .01 else t - math.sin(t)
    return float(radius)**2 * delta / 2


def arc_sweep(data, *, mode):
    a, b = (float(v) for v in data.angles)
    delta = b - a
    if type(data).__name__ == 'Arc':
        if mode == 'area' and (getattr(data, '_native', None) is not None or getattr(data, 'native_value', None) is not None):
            # Native angles already delimit the prepared counterclockwise
            # domain. Modulo would turn a rounded full turn into a tiny arc.
            return math.tau if abs(delta - math.tau) <= 8 * math.ulp(math.tau) else delta
        return delta % math.tau
    return delta


def fill_area(scene, elem, *, mode) -> float | None:
    """Actual finite fill domain; ``None`` means an unsupported fill type."""
    from .style.resolver import resolve
    data = elem.data
    kind = type(data).__name__
    export = getattr(getattr(scene, 'style', None), 'export', None) or {}
    unit = float(export.get('ptUnit_style', export.get('ptUnit', 1)) or 1)
    if kind == 'Polygon':
        pattern = resolve(scene, elem, 'fill_pattern', default='solid') or 'solid'
        area = polygon_area(data.vertices, rule='nonzero' if pattern == 'solid' else 'evenodd')
    elif kind == 'Circle':
        area = math.pi * float(data.radius)**2
    elif kind in ('Arc', 'CircleSegment', 'CircleSector'):
        sweep = arc_sweep(data, mode=mode)
        area = float(data.radius)**2 * sweep / 2 if kind == 'CircleSector' else circle_segment_area(data.radius, sweep)
    elif kind == 'Conic':
        from .geo.lib_conic import ConicType
        if data.type == ConicType.CIRCLE:
            area = math.pi * float(data.as_circle()[1])**2
        elif data.type == ConicType.ELLIPSE:
            a, b = data.as_ellipse()['semi_axes']
            area = math.pi * abs(float(a) * float(b))
        else:
            return 0.0
    elif kind == 'Region':
        area = float(data.native_value['area'])
        if -1e-12 <= area < 0:
            area = 0.0
    elif kind == 'Angle':
        from .angle_marker import marker_extent, marker_fit, shown_angle
        extent = marker_extent(scene, elem)
        fit = marker_fit(scene, elem, extent)
        if fit is not None and fit.hidden:
            return 0.0
        radius = extent.outer_px - (fit.delta_px if fit else 0)
        if extent.right:
            s1, s2 = data.side1, data.side2
            cross = float(s1[0]*s2[1] - s1[1]*s2[0])
            return radius**2 * abs(cross) / (math.hypot(*s1) * math.hypot(*s2)) if math.hypot(*s1) * math.hypot(*s2) else 0.0
        return radius**2 * shown_angle(data.size, resolve(scene, elem, 'angle_range', default='minor')) / 2
    else:
        return None
    if not math.isfinite(area) or area < 0:
        raise ValueError('fill_area_unavailable: invalid fill area')
    return area * unit**2


def resolve_mode(scene, *, default='construction'):
    """An explicit rendering setting wins over the caller's path default."""
    for holder in (getattr(scene, 'style_config', None), getattr(scene, 'style', None), scene):
        rendering = getattr(holder, 'rendering', None)
        if isinstance(rendering, dict) and 'fill_order' in rendering:
            mode = rendering['fill_order']
            if mode not in ('area', 'construction'):
                raise ValueError('rendering.fill_order must be area or construction')
            return mode
    return default


def finite_z(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('fill layer must be a finite number or null')
    return float(value)


def fill_layer(scene, elem, base_z, tie, *, mode):
    """Effective fill z and automatic flag, using winning-source provenance."""
    from .style.resolver import trace
    source, value = trace(scene, elem, 'z_index_fill')
    value = finite_z(value)
    if value is not None and source not in ('missing', 'intrinsic.style'):
        return value + tie, False
    legacy = type(elem.data).__name__ in ('Polygon', 'Angle')
    if legacy:
        source, value = trace(scene, elem, 'z_index')
        value = finite_z(value)
        if value is not None and source not in ('missing', 'intrinsic.style'):
            return base_z + tie, False
    if mode == 'area':
        return Z_FILL, True
    conic_combined = type(elem.data).__name__ == 'Conic' and getattr(elem.data, 'native_value', None) is None
    return (base_z if legacy or conic_combined else Z_FILL) + tie, True


def stable_index(construction, elem, local=0):
    from .geo.construction import DRAW_ORDER
    group = next((i for i, types in enumerate(DRAW_ORDER) if type(elem.data) in types), len(DRAW_ORDER))
    try:
        index = construction.elements.index(elem)
    except ValueError:
        index = 0  # CreateMObject also accepts an unregistered standalone element.
    return (group, index, local)



def _pattern_domain(scene, elem):
    from .style.resolver import resolve
    data = elem.data
    kind = type(data).__name__
    if kind == 'Polygon':
        return {'polygon': [(float(p[0]), float(p[1])) for p in data.vertices]}
    if kind == 'Circle':
        return {'circle': (*map(float, data.center[:2]), float(data.radius))}
    if kind in ('CircleSector', 'CircleSegment'):
        key = 'sector' if kind == 'CircleSector' else 'circlesegment'
        return {key: (*map(float, data.center[:2]), float(data.radius), *map(float, data.angles))}
    if kind == 'Region':
        return {'rings': data.flattened()}
    if kind == 'Angle':
        from .angle_marker import marker_extent, marker_fit, shown_angle
        extent = marker_extent(scene, elem)
        fit = marker_fit(scene, elem, extent)
        unit = float(scene.style.export.get('ptUnit_style', scene.style.export.get('ptUnit', 1)))
        r = (extent.outer_px - (fit.delta_px if fit else 0)) / unit
        vx, vy = map(float, data.vertex[:2])
        if extent.right:
            n1 = [float(v) * r / math.hypot(*data.side1) for v in data.side1]
            n2 = [float(v) * r / math.hypot(*data.side2) for v in data.side2]
            return {'polygon': [(vx, vy), (vx+n1[0], vy+n1[1]),
                                (vx+n1[0]+n2[0], vy+n1[1]+n2[1]), (vx+n2[0], vy+n2[1])]}
        angle_range = resolve(scene, elem, 'angle_range', default='minor')
        flipped = (angle_range == 'minor' and data.size > math.pi) or (angle_range == 'reflex' and data.size < math.pi)
        start = math.atan2(data.side2[1], data.side2[0]) if flipped else data.start_angle
        return {'sector': (vx, vy, r, start, start + shown_angle(data.size, angle_range))}
    return None

def make_fill_part(scene, elem, *, id, base_z, tie, mode):
    """Resolve one visible fill using the same style and geometry as drawing."""
    from .style.resolver import resolve
    if not resolve(scene, elem, 'visible', default=getattr(elem, 'visible', True)):
        return None
    kind = type(elem.data).__name__
    if kind not in ('Polygon', 'Angle', 'Circle', 'Arc', 'CircleSector', 'CircleSegment', 'Conic', 'Region'):
        return None
    pattern = resolve(scene, elem, 'fill_pattern', default='solid') or 'solid'
    # Arc and conic currently draw solid paths only, regardless of pattern keys.
    if kind in ('Arc', 'Conic'):
        pattern = 'solid'
    if pattern == 'none':
        return None
    if pattern == 'solid':
        if float(resolve(scene, elem, 'fill_opacity', default=1) or 0) <= 0:
            return None
        if kind == 'Angle':
            from .style.colorspace import same_color
            cfg = getattr(scene, 'style_config', None)
            background = getattr(getattr(scene, 'style', None), 'background', None)
            if background is None:
                background = getattr(cfg, 'presets', {}).get('color', {}).get('background', '#ffffff')
            if same_color(resolve(scene, elem, 'fill', default=background), background):
                return None
    else:
        from .hatch import hatch_spec
        export = scene.style.export
        unit = float(export.get('ptUnit_style', export.get('ptUnit', 1)))
        spec = hatch_spec(lambda e, k, d: resolve(scene, e, k, default=d), elem, unit)
        if spec['opacity'] <= 0 or spec['width_px'] <= 0:
            return None
    area = fill_area(scene, elem, mode=mode)
    if area is None or area <= 0:
        return None
    if pattern not in ('solid', 'none'):
        from .hatch import hatch_dots, pattern_segments
        domain = _pattern_domain(scene, elem)
        if domain is not None:
            marks = (hatch_dots(domain, spec['angle'], spec['spacing_mu']) if pattern == 'dots'
                     else pattern_segments(domain, pattern, spec['angle'], spec['spacing_mu']))
            if not marks:
                return None
    layer, automatic = fill_layer(scene, elem, base_z, tie, mode=mode)
    stable = stable_index(scene.geo, elem)
    return FillPart(id, stable[1], stable, area, layer, automatic)
