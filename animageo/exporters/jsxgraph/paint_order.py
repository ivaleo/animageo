"""Prepare an export-frame paint plan without changing construction creators."""
from __future__ import annotations

import copy
import json
import math

from ...fill_order import _pattern_domain, arc_sweep
from ..paint_plan import enabled, owner_name, paint_plan, label_position
from .spec import SpecElement, classify_parent
from .style_map import _hex, label_name, paint_part_attrs


def _rings(scene, elem):
    domain = _pattern_domain(scene, elem)
    if domain is not None:
        if 'polygon' in domain:
            return [domain['polygon']]
        if 'rings' in domain:
            return domain['rings']
        if 'circle' in domain:
            cx, cy, r = domain['circle']
            return [_arc(cx, cy, r, 0, math.tau)]
        key = 'sector' if 'sector' in domain else 'circlesegment'
        cx, cy, r, a, b = domain[key]
        arc = _arc(cx, cy, r, a, b)
        return [[(cx, cy)] + arc] if key == 'sector' else [arc]
    data = elem.data
    if type(data).__name__ == 'Arc':
        cx, cy = data.center
        a = float(data.angles[0])
        return [_arc(cx, cy, data.radius, a, a + arc_sweep(data, mode=scene._fill_order_mode()))]
    if type(data).__name__ == 'Conic':
        from ...geo.lib_conic import ConicType
        if data.type == ConicType.CIRCLE:
            center, radius = data.as_circle()
            return [_arc(*center, radius, 0, math.tau)]
        if data.type == ConicType.ELLIPSE:
            p = data.as_ellipse()
            cx, cy = p['center']
            a, b = p['semi_axes']
            c, s = math.cos(p['rotation']), math.sin(p['rotation'])
            return [[(cx + a*math.cos(t)*c - b*math.sin(t)*s,
                      cy + a*math.cos(t)*s + b*math.sin(t)*c) for t in [math.tau*i/256 for i in range(257)]]]
    return []


def _arc(cx, cy, r, a, b):
    return [(float(cx + r*math.cos(a+(b-a)*i/256)), float(cy + r*math.sin(a+(b-a)*i/256))) for i in range(257)]


def _curve_parents(rings, *, closed):
    xs, ys = [], []
    for ring in rings:
        if not ring:
            continue
        if xs:
            xs.append(None); ys.append(None)
        for x, y in list(ring) + ([ring[0]] if closed else []):
            xs.append(float(x)); ys.append(float(y))
    return [xs, ys]


def _expression(value):
    if isinstance(value, dict):
        if 'ref' in value:
            return 'S[' + json.dumps(value['ref']) + ']'
        if 'fn' in value or 'js' in value:
            return value.get('fn', value.get('js'))
        return "{" + ",".join(json.dumps(k) + ":" + _expression(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return '[' + ','.join('NaN' if v is None else _expression(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=False)


def _statement(el):
    if el.form == 'stmt':
        return el.stmt
    if el.form == 'bind':
        return f'S[{json.dumps(el.name)}] = {el.bind};'
    return f'S[{json.dumps(el.name)}] = board.create({json.dumps(el.engine)}, [{", ".join(map(_expression, el.parents))}], {_expression(el.attrs)});'


def prepare_paint_order(ctx, model):
    scene = ctx.scene
    if not enabled(scene):
        return
    runs = {}
    by_name = {el.name: el for el in model.elements if el.form != 'stmt'}
    used = set(by_name)

    def target(owner, part, name, node='self', **attrs):
        runs.setdefault((owner, part), []).append(dict(name=name, node=node, **attrs))

    def create(owner, part, engine, parents, attrs):
        name = f'__paint_{part}_{owner}'
        suffix = 2
        while name in used:
            name = f'__paint_{part}_{owner}_{suffix}'; suffix += 1
        used.add(name)
        attrs.update(layer=9, fixed=True, highlight=False, withLabel=False, name='')
        el = SpecElement(name=name, engine=engine, parents=parents, attrs=attrs,
                         role='aux', kind=part, tracks_drag=False)
        model.elements.append(el)
        target(owner, part, name)
        return el

    def angle_label(elem, attrs=None):
        render = scene._build_render_ctx(elem, True)
        if not render.has_label:
            return
        label_attrs = copy.deepcopy((attrs or {}).get('label', {}))
        label_attrs.update(strokeColor=_hex(ctx.resolve(elem, 'label_color', default='#000000')),
                           display='internal', useMathJax=ctx.opt.mathjax,
                           fontSize=float(ctx.resolve(elem, 'font_size_px', default=14)))
        create(elem.name, 'label', 'text', [*label_position(scene, elem), label_name(ctx.label_text(elem), ctx.opt.mathjax)], label_attrs)

    _prepare_view(ctx, model, create)
    for elem in scene.geo.elements:
        el = by_name.get(elem.name)
        if not ctx.is_visible(elem):
            continue
        kind = type(elem.data).__name__
        if kind == 'Angle':
            from ...angle_marker import marker_extent, marker_fit
            from ...label_placement import angle_mark_geometry
            extent = marker_extent(scene, elem)
            fit = marker_fit(scene, elem, extent)
            hidden = fit is not None and fit.hidden
            if el is not None:
                # Use the actual fitted marker, including right-square geometry,
                # rather than the engine's independent radius heuristics.
                el.attrs.update(visible=False, withLabel=False, fillOpacity=0, strokeOpacity=0)
            if hidden:
                angle_label(elem, el.attrs if el else None)
                continue
            domain = _pattern_domain(scene, elem)
            polys = []
            if 'polygon' in domain:
                polys = [domain['polygon'][1:]]
            else:
                cx, cy, radius, a, b = domain['sector']
                unit = float(scene.style.export.get('ptUnit_style', scene.style.export.get('ptUnit', 1)))
                marks = angle_mark_geometry(scene, elem)
                if marks is not None:
                    polys = [list(arc.points) if arc.points is not None else _arc(cx, cy, arc.radius, arc.start, arc.start+arc.span) for arc in marks.arcs]
                    polys += [[(a,b),(c,d)] for a,b,c,d in marks.ticks]
                    polys += [[(tip[0],tip[1]),(tip[2],tip[3]),(tip[4],tip[5]),(tip[0],tip[1])] for tip in marks.tips]
                else:
                    polys = [_arc(cx, cy, radius-i*extent.shift_px/unit, a, b) for i in range(extent.count)]
            # Auxiliary decorations drawn by the old angle adapter are replaced
            # by this one resolved marker run.
            for aux in model.elements:
                if any(aux.name == prefix+elem.name for prefix in ('__arcs_', '__arcticks_')) or aux.name.startswith('__heads_'+elem.name+'_'):
                    aux.attrs['visible'] = False
            from .style_map import base_attrs
            attrs = base_attrs(ctx, elem)
            attrs.update(fillOpacity=0, strokeColor=_hex(getattr(elem, '_native_mark_stroke', None) or ctx.resolve(elem, 'stroke', default='#000000')))
            el = create(elem.name, 'stroke', 'curve', _curve_parents(polys, closed=False), attrs)
            model.coverage = [c for c in model.coverage if not (c[0] == elem.name and c[1] == 'skip')]
            model.coverage.append((elem.name, 'static', 'resolved angle marker at export frame'))
        if el is None:
            continue
        render = scene._build_render_ctx(elem, True)
        paint_part_attrs(el.attrs, el.engine)
        part = 'body' if kind in ('Point', 'Text') or (kind == 'Conic' and elem.data.type.name == 'POINT') else 'stroke'
        if kind != 'Angle':
            target(elem.name, part, elem.name, 'borders' if el.engine == 'polygon' else 'self')
        if render.has_label:
            halo = render.label_halo
            if halo and halo['widthPx'] > 0 and halo['opacity'] > 0:
                model.coverage.append((elem.name, 'skip', 'labelHalo is unsupported; label is exported without its outline'))
            if kind == 'Angle':
                angle_label(elem, el.attrs)
            else:
                target(elem.name, 'label', el.name, 'label')
        if kind not in ('Polygon', 'Circle', 'CircleSector', 'CircleSegment', 'Arc', 'Angle', 'Region', 'Conic') or part == 'body':
            continue
        el.attrs['fillOpacity'] = 0
        if el.engine == 'angle':
            el.attrs.update(highlightFillOpacity=0)
        if render.fill_part is None:
            continue
        pattern = ctx.resolve(elem, 'fill_pattern', default='solid') or 'solid'
        if kind in ('Arc', 'Conic'):
            pattern = 'solid'
        if pattern == 'solid':
            attrs = {'strokeWidth': 0, 'strokeOpacity': 0,
                     'fillColor': _hex(ctx.resolve(elem, 'fill', default=scene.style.background)),
                     'fillOpacity': float(ctx.resolve(elem, 'fill_opacity', default=1)), 'fillRule': 'nonzero'}
            # Retain live geometry for the existing native creators. Ordering,
            # not construction dependencies, is frozen at export time.
            if el.engine in ('circle', 'polygon', 'ellipse'):
                attrs.update(borders={'visible': False, 'strokeOpacity': 0}, vertices={'visible': False, 'withLabel': False}, center={'visible': False, 'withLabel': False})
                fill = create(elem.name, 'fill', el.engine, copy.deepcopy(el.parents), attrs)
                fill.tracks_drag = el.tracks_drag
                runs[elem.name, 'fill'][-1]['fillRule'] = 'nonzero'
            else:
                create(elem.name, 'fill', 'curve', _curve_parents(_rings(scene, elem), closed=True), attrs)
                runs[elem.name, 'fill'][-1]['fillRule'] = 'nonzero'
                model.coverage.append((elem.name, 'static', 'fill geometry sampled at export frame'))
        else:
            from ...hatch import hatch_spec, hatch_dots, pattern_segments
            domain = _pattern_domain(scene, elem)
            spec = hatch_spec(lambda e, k, d: ctx.resolve(e, k, default=d), elem, float(scene.style.export.get('ptUnit_style', scene.style.export.get('ptUnit', 1))))
            col = _hex(spec['color'] or ctx.resolve(elem, 'stroke', default='#000000'))
            if pattern == 'dots':
                for x, y in hatch_dots(domain, spec['angle'], spec['spacing_mu']):
                    create(elem.name, 'fill', 'circle', [[x, y], spec['dot_radius_mu']],
                           {'strokeWidth': 0, 'fillColor': col, 'fillOpacity': spec['opacity'], 'center': {'visible': False}})
            else:
                segments = pattern_segments(domain, pattern, spec['angle'], spec['spacing_mu'])
                polys = [[(a, b), (c, d)] for a, b, c, d in segments]
                create(elem.name, 'fill', 'curve', _curve_parents(polys, closed=False),
                       {'strokeColor': col, 'strokeWidth': spec['width_px'], 'strokeOpacity': spec['opacity'], 'fillOpacity': 0})
            model.coverage.append((elem.name, 'static', 'pattern geometry sampled at export frame; even-odd polygon support'))
    # Existing auxiliary marks remain in the owner's corresponding run.
    for el in model.elements:
        if el.name in used and el.name not in by_name:
            continue
        for elem in scene.geo.elements:
            for prefix, part in (('__arcs_', 'stroke'), ('__heads_', 'stroke'), ('__tick_', 'ticks'),
                                 ('__parallel_', 'parallel'), ('__leader_', 'leader')):
                if el.attrs.get('visible') is False:
                    continue
                if el.name == prefix + elem.name or el.name.startswith(prefix + elem.name + '_'):
                    el.attrs['layer'] = 9
                    target(elem.name, part, el.name)
    fills, plan = paint_plan(scene, runs)
    model.paint_order = {'mode': scene._fill_order_mode(), 'static': True, 'fillOrder': list(fills),
                         'partOrder': [dict(ref, targets=runs[owner_name(scene, ref['id']), ref['part']]) for ref in plan]}
    model.coverage.append(('@paint', 'static', 'paint order fixed at export frame; drag does not reorder; re-export to recompute'))
    # Rebuild only the opted-in output; classic statements remain byte-for-byte.
    model.statements = [_statement(el) for el in model.elements]


def _prepare_view(ctx, model, create):
    """Use the native view's finite snapshot, including minor grid and labels."""
    settings = getattr(ctx.scene, 'native_view', None)
    if settings is None:
        return
    from ...native.view import view_layout, view_style
    l, t, r, b = model.boundingbox
    st = view_style(ctx.scene.style_config.rendering)
    unit = float(ctx.scene.style.export.get('ptUnit_style', ctx.scene.style.export.get('ptUnit', 1)))
    layout = view_layout(settings, (l,b,r,t), margin=st['axes_font_size_px']/unit)
    model.chrome.axis = False
    model.chrome.grid = False
    for kind in ('minor','major'):
        polys = [[(x,b),(x,t)] for x in layout['grid'][kind]['x']] + [[(l,y),(r,y)] for y in layout['grid'][kind]['y']]
        prefix = 'grid_minor_' if kind == 'minor' else 'grid_'
        if polys and st[prefix+'opacity'] > 0 and st[prefix+'width_px'] > 0:
            create('@view.'+kind, 'stroke', 'curve', _curve_parents(polys, closed=False),
                   {'strokeColor': st['grid_color'], 'strokeWidth': st[prefix+'width_px'], 'strokeOpacity': st[prefix+'opacity'], 'fillOpacity': 0})
    tick = st['axes_tick_length_px']/2/unit
    polys = []
    if layout['axes']['x']:
        polys += [[(l,0),(r,0)]] + [[(x,-tick),(x,tick)] for x in layout['ticks']['x']]
    if layout['axes']['y']:
        polys += [[(0,b),(0,t)]] + [[(-tick,y),(tick,y)] for y in layout['ticks']['y']]
    if polys and st['axes_opacity'] > 0 and st['axes_width_px'] > 0:
        create('@view.axes', 'stroke', 'curve', _curve_parents(polys, closed=False),
               {'strokeColor': st['axes_color'], 'strokeWidth': st['axes_width_px'], 'strokeOpacity': st['axes_opacity'], 'fillOpacity': 0})
    if st['axes_opacity'] > 0:
        for axis in ('x','y'):
            labels = [(v,0,text) if axis=='x' else (0,v,text) for v,text in layout['numbers'][axis]]
            if layout['labels'][axis]:
                labels.append((r,0,layout['labels'][axis]) if axis=='x' else (0,t,layout['labels'][axis]))
            for x,y,text in labels:
                create('@view.labels', 'label', 'text', [x,y,text],
                       {'strokeColor': st['axes_color'], 'strokeOpacity': st['axes_opacity'], 'fontSize': st['axes_font_size_px'], 'display': 'internal'})
