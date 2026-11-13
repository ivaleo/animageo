"""Shared scene adapter for writers that emit independent paint runs."""
from dataclasses import replace

from ..fill_order import PaintPart, order_fills, order_paint_parts, stable_index


def owner_id(scene, name):
    names = getattr(scene, 'native_names', None)
    return names.by_name.get(name, name) if names else name


def owner_name(scene, id):
    names = getattr(scene, 'native_names', None)
    return names.by_id.get(id, id) if names else id


def enabled(scene):
    return scene._fill_display_enabled()


def paint_plan(scene, runs):
    """Return the common bottom-to-top plan restricted to emitted runs.

    ``runs`` maps (owner, part) to writer-specific commands or render targets.
    No rank is written to geometry, style, or a numeric layer.
    """
    parts, fills = [], []
    local = {'fill': 0, 'body': 0, 'stroke': 1, 'ticks': 2, 'parallel': 3,
             'labelHalo': 4, 'label': 5, 'leader': 6}
    for elem in scene.geo.elements:
        if not scene._element_visible(elem):
            continue
        ctx = scene._build_render_ctx(elem, True)
        kind = type(elem.data).__name__
        if ctx.fill_part is not None and (elem.name, 'fill') in runs:
            fills.append(replace(ctx.fill_part, id=owner_id(scene, elem.name)))
        stroke = max(ctx.zz_stroke, ctx.zz + .1) if kind in ('Polygon', 'Region') else ctx.zz + .1 if kind == 'Angle' else ctx.zz
        layers = {'fill': ctx.zz_fill, 'stroke': stroke, 'body': ctx.zz,
                  'label': ctx.zz_label, 'labelHalo': ctx.zz_label,
                  'leader': ctx.zz_label - 1, 'ticks': ctx.zz, 'parallel': ctx.zz}
        for part, z in layers.items():
            if (elem.name, part) not in runs or not runs[elem.name, part]:
                continue
            if part == 'fill' and ctx.fill_part is None:
                continue
            if part in ('stroke', 'ticks', 'parallel') and (ctx.op_s <= 0 or ctx.lw <= 0):
                continue
            parts.append(PaintPart(owner_id(scene, elem.name), part, z, stable_index(scene.geo, elem, 5 if kind == 'Text' and part == 'body' else local[part])))
    for i, (owner, part, z) in enumerate((('@view.minor', 'stroke', -21), ('@view.major', 'stroke', -20),
                                         ('@view.axes', 'stroke', -10), ('@view.labels', 'label', -9))):
        if runs.get((owner, part)):
            parts.append(PaintPart(owner, part, z, (-1, i, 0)))
    fill_order = order_fills(fills, mode=scene._fill_order_mode())
    return fill_order, order_paint_parts(parts, fill_order)


def label_position(scene, elem):
    """Finite anchor for writers adding labels to previously combined paths."""
    import math
    from ..fill_order import _pattern_domain
    ctx = scene._build_render_ctx(elem, True)
    if ctx.ggb_label_point is not None:
        return tuple(map(float, ctx.ggb_label_point[:2]))
    data = elem.data
    kind = type(data).__name__
    if kind == 'Circle':
        return tuple(map(float, data.center[:2]))
    if kind == 'Conic':
        from ..geo.lib_conic import ConicType
        if data.type == ConicType.CIRCLE:
            return tuple(map(float, data.as_circle()[0]))
        if data.type == ConicType.ELLIPSE:
            return tuple(map(float, data.as_ellipse()['center']))
    if kind == 'Angle':
        from ..angle_marker import marker_extent, marker_fit
        extent = marker_extent(scene, elem)
        fit = marker_fit(scene, elem, extent)
        domain = _pattern_domain(scene, elem)
        if 'polygon' in domain:
            return tuple(domain['polygon'][2])
        x, y, _, a, b = domain['sector']
        radius = (extent.label_px - (fit.delta_px if fit else 0) + float(ctx.label_roff or 0)) / ctx.ptUnit_style
        return x + radius*math.cos((a+b)/2), y + radius*math.sin((a+b)/2)
    return None
