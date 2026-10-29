"""GGB equations and implicit coordinate axes, without new registry ops."""
from __future__ import annotations

from .ggb_expr import ExprError, parse_number
from .keys import element_id, operation_id


def read_equations(infos, norm, ctx):
    kinds = {i['label']: i['type'] for i in infos}
    for info in infos:
        if info['type'] != 'conic' or info.get('command') != 'Expression' or not info.get('inputs'):
            continue
        name = norm[info['label']]
        forced = ctx.forced.get(name)
        if forced and forced[0] not in ('parse_error', 'unsupported_signature', 'no_registry_op'):
            continue
        parts = info['inputs'][0].split('=')
        if len(parts) != 2 or not all(p.strip() for p in parts):
            ctx.forced[name] = ('formula_unsupported', 'ожидалось уравнение коники с двумя частями')
            continue
        try:
            ast, refs = parse_number(f'({parts[0]}) - ({parts[1]})', kinds, variables=('x', 'y'))
        except ExprError as exc:
            ctx.forced[name] = (exc.reason, exc.detail)
            continue
        ctx.forced.pop(name, None)
        ctx.formulas[name] = ast, [norm[r] for r in refs]
        ctx.equations.add(name)


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
