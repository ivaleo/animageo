"""Private dependency graphs of inline GGB arguments, using registry 1.7 ops.

Every helper an import adds follows the rule of the helpers of marks of the
web (1.0.55): no name, hidden and locked, ``role: aux`` and
``origin: {kind: auto, source: <the operation it was made for>}``
(:func:`own_helpers`) — deleting that operation deletes it, another
operation still reading it takes it over (``native.edit.delete``).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .keys import KeyMaker, element_id, operation_id

HELPER_APPEARANCE = {'visible': False, 'locked': True, 'role': 'aux', 'label': {'mode': 'none'}}


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
               'Circle', 'Rotate', 'Polygon', 'Parabola', 'ClosestPoint', 'Midpoint', 'PerpendicularBisector',
               'Root', 'Roots', 'Extremum'}
    named = {eid for entry in entries for eid in entry['native_ids']}
    anonymous = {eid for rec in records.values() if KeyMaker.is_phantom(rec.name) for eid in rec.native_ids}
    anonymous.update(set(doc['elements']) - named - {
        eid for rec in records.values() if not KeyMaker.is_phantom(rec.name) for eid in rec.native_ids})
    helpers = {}
    for entry in entries:
        info = entry['info']
        tangency = info.get('command') in ('Tangent', 'Slope') and any(
            doc['operations'][doc['elements'][eid]['producer']['operationId']]['op'] in (
                'line.tangent_function_at', 'line.tangents_from_point_conic',
                'line.tangents_parallel_conic', 'line.slope')
            for eid in entry['native_ids'] if eid in doc['elements'])
        supported = info.get('command') in allowed or tangency or info['type'] == 'text' or \
            info.get('command') == 'Expression' and (info['type'] in ('point', 'vector', 'conic') or any(
                doc['operations'][doc['elements'][eid]['producer']['operationId']]['op'] == 'function.value'
                for eid in entry['native_ids'] if eid in doc['elements']))
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
            for dep in sorted(needed):
                doc['appearance'][dep] = copy.deepcopy(HELPER_APPEARANCE)
    return helpers


def own_helpers(doc, entries, helpers) -> None:
    """``origin: {kind: auto, source}`` of every helper left in ``doc``: the
    operation of the first kept object (in the order of the report) that
    needs it; a helper that already has an origin keeps it."""
    for entry in entries:
        if entry['category'] not in ('editable', 'differs'):
            continue
        for nid in entry['native_ids']:
            el = doc['elements'].get(nid)
            if el is None:
                continue
            for helper in sorted(helpers.get(nid, ())):
                h = doc['elements'].get(helper)
                if h is not None and 'origin' not in h:
                    h['origin'] = {'kind': 'auto', 'source': el['producer']['operationId']}


# -- the angle of Rotate given by angle arithmetic ----------------------------

def read_angle_arguments(infos, norm, ctx, built_by_command) -> None:
    """The angle argument of a GGB ``Rotate(obj, <expression>, center)`` read
    from its text (``ggb_expr``: ``-theta``, ``4 * (α_{2} - 90°)`` with ``°``
    as ``·(π/180)``) into ``ctx.angle_formulas``. An expression read but
    outside the formulas is kept as its refusal (``formula_unsupported``),
    also for a command the classic did not build; one not read (``parse_error``)
    leaves the classic path."""
    from .ggb_expr import ExprError, parse_number
    kinds = {i['label']: i['type'] for i in infos}
    for info in infos:
        inputs = info.get('inputs') or []
        if info.get('command') != 'Rotate' or len(inputs) != 3 or inputs[1].strip() in kinds:
            continue
        n = norm[info['label']]
        try:
            ast, refs = parse_number(inputs[1], kinds)
        except ExprError as exc:
            if exc.reason != 'formula_unsupported':
                continue
            detail = f'аргумент задан выражением: {inputs[1].strip()} ({exc.detail})'
            ctx.angle_formulas[n] = ('error', exc.reason, detail)
            forced = ctx.forced.get(n)
            if n not in built_by_command and forced is not None and forced[0] == 'unsupported_signature':
                ctx.forced[n] = (exc.reason, detail)
            continue
        ctx.angle_formulas[n] = (ast, [norm[r] for r in refs])


@dataclass
class AngleFormula:
    """The angle input ``index`` of a rotation, its ``row`` of ``dsl_map``,
    the formula and, after :meth:`resolve`, ``items``: ``(type, elementId)``."""
    index: int
    row: dict
    ast: dict
    names: list
    items: list = field(default_factory=list)

    def resolve(self, builder) -> None:
        """Find the element of every name (a number, or an angle of a figure
        measured by a helper) before anything is emitted."""
        from ..expr.validate import problems
        from .construction import NOTE_DETAILS, _Untranslated
        self.items = []
        for name in self.names:
            eid = builder.element_of.get(name)
            if eid is None:
                raise _Untranslated('depends_on_unsupported', deps=[name])
            type_ = builder.doc['elements'][eid]['type']
            if type_ not in ('number', 'angle'):
                raise _Untranslated('formula_unsupported', NOTE_DETAILS[
                    'arithmetic of points, vectors, angles or segments (number.expression takes numbers only)'])
            self.items.append((type_, eid))
        if problems(self.ast, len(self.items)):
            raise _Untranslated('formula_unsupported', 'выражение выходит за пределы формул (expr.md §2)')


def rotate_angle(builder, cmd, sig, inputs, outs):
    """The :class:`AngleFormula` of a GGB ``Rotate`` whose angle argument the
    classic made into a formula it does not translate (a phantom), when the
    import read its text; ``None`` — the classic path. The angle read but
    outside the formulas raises ``formula_unsupported``."""
    from .construction import _Untranslated
    ctx = builder.ctx
    if not ctx.inline_formulas or cmd.name != 'Rotate' or len(inputs) != 3:
        return None
    entry = next((ctx.angle_formulas[o] for o in outs if o in ctx.angle_formulas), None)
    phantom = inputs[1]
    if entry is None or not (isinstance(phantom, str) and KeyMaker.is_phantom(phantom)):
        return None
    rec = builder.records.get(phantom)
    if rec is not None and rec.status not in ('untranslated', 'closure'):
        return None                                     # the classic translated it: its formula stands
    if entry[0] == 'error':
        raise _Untranslated(entry[1], entry[2])
    prefix, _, chars = sig.rpartition('_')
    row = builder.table.lookup(f'{prefix}_{chars[0]}A{chars[2]}') if len(chars) == 3 else None
    if row is None or row.get('op') != 'transform.rotate':
        return None
    return AngleFormula(1, row, entry[0], list(entry[1]))


def angle_argument(builder, angle: AngleFormula, rec) -> dict:
    """Emit the helpers of a resolved :class:`AngleFormula` — a hidden
    ``measure.angle`` per angle of a figure, then the hidden
    ``number.expression`` — keyed ``<rec.key>/inline/<k>``; the reference to
    the expression."""
    counter = 0

    def emit(op, args):
        nonlocal counter
        counter += 1
        key = f'{rec.key}/inline/{counter}'
        oid, eid = operation_id(builder.ns, key), element_id(builder.ns, key)
        builder.doc['operations'][oid] = {'id': oid, 'op': op, 'args': args,
                                          'outputs': [{'slot': 'number', 'elementId': eid}]}
        builder.doc['elements'][eid] = {'id': eid, 'type': 'number', 'displayName': '',
                                       'producer': {'operationId': oid, 'slot': 'number'}}
        return {'kind': 'ref', 'elementId': eid}

    items = [emit('measure.angle', {'angle': {'kind': 'ref', 'elementId': eid}}) if type_ == 'angle'
             else {'kind': 'ref', 'elementId': eid} for type_, eid in angle.items]
    return emit('number.expression', {'expr': {'kind': 'expr', 'ast': copy.deepcopy(angle.ast)},
                                      'refs': {'kind': 'list', 'items': items}})
