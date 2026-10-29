"""Private dependency graphs of inline GGB arguments, using registry 1.7 ops."""
from __future__ import annotations

from .keys import KeyMaker, element_id, operation_id


def vector_expression(builder, sig, inputs, rec):
    """Lower vector wrappers and arithmetic without extending the registry.

    A scaled vector is the difference of two positive dilations. Both factors
    are at least one, so zero factors and zero vectors remain defined too.
    Only the displacement is used for anonymous arithmetic arguments.
    """
    supported = {'vector_p', 'vector_v', 'u_sub_v', 'mult_iv', 'mult_vi'}
    if sig not in supported or not builder.ctx.inline_formulas:
        return False
    if sig.startswith('mult_') and not KeyMaker.is_phantom(rec.name):
        return False
    counter = 0

    def emit(op, args, slot, type_, *, output=False, value=None):
        nonlocal counter
        counter += 1
        key = rec.key if output else f'{rec.key}/inline/{counter}'
        oid = operation_id(builder.ns, key)
        eid = element_id(builder.ns, key)
        builder.doc['operations'][oid] = {'id': oid, 'op': op, 'args': args,
                                          'outputs': [{'slot': slot, 'elementId': eid}]}
        if output:
            builder.add_element(rec.name, rec, oid, slot, type_)
            rec.op_id = oid
        else:
            builder.doc['elements'][eid] = {'id': eid, 'type': type_, 'displayName': '',
                                           'producer': {'operationId': oid, 'slot': slot}}
        if value is not None:
            builder.doc['inputs'][eid] = value
        return {'kind': 'ref', 'elementId': eid}

    # Resolve every input first: a failed expression must leave no orphan ops.
    args = [builder.arg_for(i, 'refs', set()) for i in inputs]
    origin = emit('point.free', {}, 'point', 'point', value={'kind': 'point', 'value': [0., 0.]})
    if sig == 'vector_p':
        emit('vector.by_points', {'a': origin, 'b': args[0]}, 'vector', 'vector', output=True)
    elif sig == 'vector_v':
        zero = emit('vector.by_points', {'a': origin, 'b': origin}, 'vector', 'vector')
        emit('transform.translate', {'obj': args[0], 'vector': zero}, 'image', 'vector', output=True)
    elif sig == 'u_sub_v':
        emit('transform.reflect_point', {'obj': args[0], 'point': origin}, 'image', 'vector', output=True)
    else:
        factor, vector = args if sig == 'mult_iv' else reversed(args)
        refs = [] if factor['kind'] == 'number' else [factor]
        term = {'num': factor['value']} if not refs else {'ref': 0}
        ends = []
        for scalar in (term, {'op': 'neg', 'args': [term]}):
            ast = {'op': '+', 'args': [{'num': 1.}, {'fn': 'max', 'args': [scalar, {'num': 0.}]}]}
            scale = emit('number.expression', {'expr': {'kind': 'expr', 'ast': ast},
                                              'refs': {'kind': 'list', 'items': refs}}, 'number', 'number')
            dilated = emit('transform.dilate', {'obj': vector, 'factor': scale, 'center': origin},
                           'image', 'vector')
            ends.append(emit('transform.translate', {'obj': origin, 'vector': dilated}, 'image', 'point'))
        emit('vector.by_points', {'a': ends[1], 'b': ends[0]}, 'vector', 'vector', output=True)
    return True


def inline_arguments(doc, entries, records, refs_of):
    """Anonymous dependencies reachable from supported source objects.

    Helpers stay outside report.native_ids: those IDs have the public naming
    contract of source objects. Their own UUID5 IDs, hidden appearance and
    dependency closure are retained in the candidate document.
    """
    allowed = {'Translate', 'Segment', 'Line', 'OrthogonalLine', 'Vector', 'Point', 'Intersect', 'Ray',
               'Circle', 'Rotate', 'Polygon', 'Parabola', 'ClosestPoint', 'Midpoint', 'PerpendicularBisector'}
    named = {eid for entry in entries for eid in entry['native_ids']}
    anonymous = {eid for rec in records.values() if KeyMaker.is_phantom(rec.name) for eid in rec.native_ids}
    anonymous.update(set(doc['elements']) - named - {
        eid for rec in records.values() if not KeyMaker.is_phantom(rec.name) for eid in rec.native_ids})
    helpers = {}
    for entry in entries:
        info = entry['info']
        supported = info.get('command') in allowed or info['type'] == 'text' or \
            info.get('command') == 'Expression' and info['type'] in ('vector', 'conic')
        if entry['status'] != 'translated' or not supported:
            continue
        for eid in entry['native_ids']:
            needed = set()
            pending = list(refs_of(eid))
            while pending:
                dep = pending.pop()
                if dep in needed or dep not in anonymous:
                    continue
                needed.add(dep)
                pending.extend(refs_of(dep))
            helpers[eid] = needed
            for dep in needed:
                doc['appearance'][dep] = {'visible': False, 'locked': True, 'label': {'mode': 'none'}}
    return helpers
