"""GGB conic and line equations, and implicit coordinate axes."""
from __future__ import annotations

from .ggb_expr import ExprError, parse_number
from .keys import element_id, operation_id


def read_equations(infos, norm, ctx):
    kinds = {i['label']: i['type'] for i in infos}
    for info in infos:
        if info['type'] not in ('conic', 'line') or info.get('command') != 'Expression' or not info.get('inputs'):
            continue
        name = norm[info['label']]
        forced = ctx.forced.get(name)
        if forced and forced[0] not in ('parse_error', 'unsupported_signature', 'no_registry_op'):
            continue
        parts = info['inputs'][0].split('=')
        if len(parts) != 2 or not all(p.strip() for p in parts):
            ctx.forced[name] = ('formula_unsupported', 'ожидалось уравнение с двумя частями: ' + info['inputs'][0])
            continue
        try:
            ast, refs = parse_number(f'({parts[0]}) - ({parts[1]})', kinds, variables=('x', 'y'))
        except ExprError as exc:
            ctx.forced[name] = ('formula_unsupported' if info['type'] == 'line' else exc.reason,
                                f"{info['inputs'][0]}: {exc.detail}")
            continue
        ctx.forced.pop(name, None)
        ctx.formulas[name] = ast, [norm[r] for r in refs]
        ctx.equations[name] = info['type']


def check_line_orientations(document, records, infos, norm):
    """Compare the signed XML normals of equation lines after value checks."""
    import math
    from ..kernel.evaluate import evaluate
    from .values import TOL_IMPORT

    candidates = [(info, records.get(norm[info['label']])) for info in infos
                  if info['type'] == 'line' and info.get('command') == 'Expression' and info.get('coords')]
    if not candidates:
        return
    ev = evaluate(document)
    for info, rec in candidates:
        if rec is None or rec.status != 'translated' or rec.value_check != 'passed' or not rec.native_ids:
            continue
        coords = info['coords']
        a, b = coords.get('x'), coords.get('y')
        if a is None or b is None or not math.isfinite(math.hypot(a, b)) or math.hypot(a, b) == 0:
            continue
        length = math.hypot(a, b)
        state = ev.elements[rec.native_ids[0]]
        if state['state'] != 'defined':
            continue
        dx, dy = state['value']['dir']
        delta = max(abs(dx - b / length), abs(dy + a / length)) * ev.tolerances.scale
        if delta > TOL_IMPORT * ev.tolerances.scale:
            rec.value_check, rec.delta = 'failed', max(rec.delta or 0, delta)


def axis_ref(builder, name):
    """Hidden fixed anchors preserve the actual dependency on an XML axis."""
    key = 'ggb:#axis:' + name
    eid = element_id(builder.ns, key)
    if eid not in builder.doc['elements']:
        refs = []
        for suffix, xy in (('/a', [0., 0.]), ('/b', [1., 0.] if name == 'xAxis' else [0., 1.])):
            oid, pid = operation_id(builder.ns, key + suffix), element_id(builder.ns, key + suffix)
            builder.doc['operations'][oid] = {'id': oid, 'op': 'point.free', 'args': {},
                                              'outputs': [{'slot': 'point', 'elementId': pid}]}
            builder.doc['elements'][pid] = {'id': pid, 'type': 'point', 'displayName': '',
                                            'producer': {'operationId': oid, 'slot': 'point'}}
            builder.doc['inputs'][pid] = {'kind': 'point', 'value': xy}
            refs.append({'kind': 'ref', 'elementId': pid})
        oid = operation_id(builder.ns, key)
        builder.doc['operations'][oid] = {'id': oid, 'op': 'line.by_points', 'args': dict(zip(('a', 'b'), refs)),
                                          'outputs': [{'slot': 'line', 'elementId': eid}]}
        builder.doc['elements'][eid] = {'id': eid, 'type': 'line', 'displayName': '',
                                        'producer': {'operationId': oid, 'slot': 'line'}}
    return {'kind': 'ref', 'elementId': eid}
