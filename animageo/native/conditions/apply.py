"""Applying and releasing conditions (plan L3 §3.5–§3.6,
docs/native/conditions.md).

``apply_condition`` matches the statement against the recipes, chooses the
receiver, adds the hidden places of the recipe and redefines the receiver as
a point on the place (or on the intersection of two places). A refusal never
changes the document.
"""
from __future__ import annotations

import copy
import math
from typing import NamedTuple

from ..document import NativeDocument, as_document, bound_producer, iter_refs, validate
from ..edit import _delete as delete
from ..edit import _effects, _finish, _reach, json_copy
from ..edit import _redefine as redefine
from ..registry import registry
from ..steps import order_key
from .recipes import matches
from .statements import statement_elements, statement_problems
from .validate import MAX_CONSTRAINTS, condition_list

__all__ = ['Refusal', 'ConditionResult', 'apply_condition', 'release_condition', 'condition_candidates',
           'shape_conditions', 'SHAPES']

FREE_OPS = ('point.free', 'point.on_path')



class Refusal(NamedTuple):
    code: str
    message: str
    options: list


class ConditionResult(NamedTuple):
    """``document`` — the new document (the old one on a refusal); ``effects``
    as :func:`animageo.native.redefine` plus ``shift``; ``condition`` — the
    entry of ``conditions[]``; ``refusal`` — :class:`Refusal` or ``None``."""

    document: NativeDocument
    effects: dict
    condition: dict | None
    refusal: Refusal | None


# ── helpers ───────────────────────────────────────────────────────────────

def _producer_op(doc, el_id):
    op_id = bound_producer(doc, el_id)
    return (op_id, doc.operations[op_id]) if op_id is not None else (None, None)


def _points(doc, statement) -> list:
    return [e for e in statement_elements(statement) if doc.elements.get(e, {}).get('type') == 'point']


def _status(doc, el_id, participants) -> str:
    """``ok``, ``not_free`` or ``ancestor`` for a would-be receiver."""
    _op_id, op = _producer_op(doc, el_id)
    constrained = any(c.get('mode') == 'construct' and c.get('receiver') == el_id for c in condition_list(doc))
    if op is None or (op['op'] not in FREE_OPS and not constrained):
        return 'not_free'
    below = _reach(doc, [el_id], 'down') - {el_id}
    if below & (set(participants) - {el_id}):
        return 'ancestor'
    return 'ok'


def _condition_ops(doc) -> set:
    return {op_id for c in condition_list(doc) if c.get('mode') == 'construct' for op_id in c.get('operationIds') or ()}


def _constraints(doc, receiver) -> int:
    """Conditions on ``receiver`` plus its own path (a ``point.on_path`` not
    made by a condition)."""
    n = sum(1 for c in condition_list(doc) if c.get('mode') == 'construct' and c.get('receiver') == receiver)
    op_id, op = _producer_op(doc, receiver)
    if op is not None and op['op'] == 'point.on_path' and op_id not in _condition_ops(doc):
        n += 1
    return n


def _choose(doc, receivers, participants):
    """The default receiver: the largest order key of the producer, ties —
    the last named in the statement."""
    named = {e: i for i, e in enumerate(participants)}

    def key(el_id):
        return order_key(doc, bound_producer(doc, el_id)), named.get(el_id, -1)
    return max(receivers, key=key)


def _refuse(doc, code, message, options) -> ConditionResult:
    return ConditionResult(doc, _finish(_effects()), None, Refusal(code, message, options))


def _make_free_options(doc, participants) -> list:
    out = []
    for el_id in participants:
        _op_id, op = _producer_op(doc, el_id)
        if op is None or op['op'] == 'point.free':
            continue
        below = _reach(doc, [el_id], 'down') - {el_id}
        if below & (set(participants) - {el_id}):
            continue
        out.append(el_id)
    out.sort(key=lambda e: order_key(doc, bound_producer(doc, e)), reverse=True)
    return [{'kind': 'make_free', 'elementId': e} for e in out]


_ESCAPE = [{'kind': 'keep_as_check'}, {'kind': 'manual'}]


class _Ids:
    """The default ID factory: ``c<n>`` for a condition, ``op_<c>_<k>`` for a
    place operation, ``<c>_<name>`` for its element (``_2``, ``_3`` … on a
    clash)."""

    def __init__(self, data, factory=None):
        self.used = set(data.get('operations', {})) | set(data.get('elements', {})) | \
            {c.get('id') for c in data.get('conditions') or () if isinstance(c, dict)}
        self.factory = factory

    def make(self, kind, hint):
        if self.factory is not None:
            new = self.factory(kind, hint)
            if new in self.used:
                raise ValueError(f'id_factory gave {new!r}, which is taken')
            self.used.add(new)
            return new
        if kind == 'condition':
            n = 1
            while f'c{n}' in self.used:
                n += 1
            new = f'c{n}'
        else:
            new, n = hint, 1
            while new in self.used:
                n += 1
                new = f'{hint}_{n}'
        self.used.add(new)
        return new


def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _xy(ev, el_id):
    state = ev.elements.get(el_id)
    if state is None or state['state'] != 'defined':
        return None
    v = state['value']
    return (v['x'], v['y']) if isinstance(v, dict) else (v[0], v[1])


def _side(ev, a, b, c) -> float:
    """``+1`` or ``−1``: the sign of ``(a − b) × (c − b)`` now (``+1`` when 0)."""
    pa, pb, pc = _xy(ev, a), _xy(ev, b), _xy(ev, c)
    if None in (pa, pb, pc):
        return 1.0
    cross = (pa[0] - pb[0]) * (pc[1] - pb[1]) - (pa[1] - pb[1]) * (pc[0] - pb[0])
    return -1.0 if cross < 0 else 1.0


def _arg(spec, binds, made, ev):
    if isinstance(spec, str):
        if spec.startswith('$'):
            return _ref(made[spec])
        return _ref(binds[spec])
    if isinstance(spec, list):
        return {'kind': 'list', 'items': [_arg(s, binds, made, ev) for s in spec]}
    if 'value' in spec:
        kind, v = binds[spec['value']]
        return {'kind': 'number', 'value': v} if kind == 'num' else _ref(v)
    if 'signed_degrees' in spec:
        _kind, deg = binds[spec['signed_degrees']]
        a, b, c = (binds[x] for x in spec['side'])
        return {'kind': 'number', 'value': _side(ev, a, b, c) * deg * math.pi / 180}
    if 'signed_convex' in spec:
        a, b, c = (binds[x] for x in spec['signed_convex'])
        sign = _side(ev, a, b, c)
        two_pi = {'op': '*', 'args': [{'num': 2}, {'const': 'pi'}]}
        convex = {'fn': 'min', 'args': [{'ref': 0}, {'op': '-', 'args': [two_pi, {'ref': 0}]}]}
        return {'kind': 'expr', 'ast': {'op': '*', 'args': [{'num': sign}, convex]}}
    raise ValueError(f'unknown template argument {spec!r}')


def _distance_to(ev, el_id, xy) -> float:
    from ..kernel import paths
    state = ev.elements.get(el_id)
    if state is None or state['state'] != 'defined' or xy is None:
        return math.inf
    return paths.distance_to_path(xy[0], xy[1], 'line', state['value'])


def _max_seq(data) -> int:
    seqs = [op.get('seq', 0) for op in data['operations'].values()]
    seqs += [c.get('seq', 0) for c in data.get('conditions') or () if isinstance(c, dict)]
    return max([s for s in seqs if isinstance(s, int)] + [0])


def _place_ops(doc, recipe, binds, cid, ids, ev):
    """``(data with the places, made {"$name": elementId}, place op IDs)``."""
    from ..kernel.evaluate import evaluate
    reg = registry()
    data = json_copy(doc.data)
    made: dict = {}
    op_ids = []
    seq = _max_seq(data)
    for k, step in enumerate(s for s in recipe['template'] if 'redefine' not in s):
        record = reg.get(step['op'])
        op_id = ids.make('operation', f'op_{cid}_{k + 1}')
        args = {slot: _arg(spec, binds, made, ev) for slot, spec in step['args'].items()}
        outputs = []
        for slot_spec, name in step['outputs'].items():
            slots = slot_spec.split('|')
            chosen = slots[0]
            if len(slots) > 1:
                # the slot nearest to the receiver now, fixed from then on
                probe = json_copy(data)
                probe_ids = {s: f'__probe_{i}' for i, s in enumerate(slots)}
                probe['operations'][op_id] = {'id': op_id, 'op': step['op'], 'args': args,
                                              'outputs': [{'slot': s, 'elementId': probe_ids[s]} for s in slots]}
                types = {o['slot']: o['type'] for o in record['outputs']}
                for s in slots:
                    probe['elements'][probe_ids[s]] = {'id': probe_ids[s], 'type': types[s],
                                                       'producer': {'operationId': op_id, 'slot': s},
                                                       'displayName': ''}
                pev = evaluate(NativeDocument(probe))
                xy = _xy(ev, binds[step['nearest']])
                chosen = min(slots, key=lambda s: (_distance_to(pev, probe_ids[s], xy), slots.index(s)))
            el_id = ids.make('element', f'{cid}_{name[1:]}')
            made[name] = el_id
            out_type = next(o['type'] for o in record['outputs'] if o['slot'] == chosen)
            data['elements'][el_id] = {'id': el_id, 'type': out_type,
                                       'producer': {'operationId': op_id, 'slot': chosen}, 'displayName': ''}
            outputs.append({'slot': chosen, 'elementId': el_id})
        seq += 1
        data['operations'][op_id] = {'id': op_id, 'op': step['op'], 'args': args, 'outputs': outputs, 'seq': seq}
        appearance = data.setdefault('appearance', {})
        for out in outputs:
            appearance[out['elementId']] = {'visible': False, 'role': 'aux'}
        op_ids.append(op_id)
    return data, made, op_ids


def _onto_ray(doc, locus, xy):
    """``xy``, or — when ``xy`` is behind the origin of a ray place — the
    point of the ray at the same distance from its origin (the receiver must
    not land on the vertex of an angle)."""
    from ..kernel.evaluate import evaluate
    if doc.elements[locus]['type'] != 'ray':
        return xy
    state = evaluate(doc).elements.get(locus)
    if state is None or state['state'] != 'defined':
        return xy
    (ox, oy), (dx, dy) = state['value']['origin'], state['value']['dir']
    if (xy[0] - ox) * dx + (xy[1] - oy) * dy > 0:
        return xy
    d = math.hypot(xy[0] - ox, xy[1] - oy)
    return (ox + d * dx, oy + d * dy)


def _family(name):
    return set(registry().families.get(name, ())) | {name}


def _meet(doc, first, second):
    """``(op, [(slot, args)])`` intersecting two places, or ``None``."""
    t1, t2 = doc.elements[first]['type'], doc.elements[second]['type']
    linear, circular = _family('linear'), _family('circular')
    if t1 in linear and t2 in linear:
        return 'intersect.line_line', {'first': _ref(first), 'second': _ref(second)}, ['point']
    if t1 in linear and t2 in circular:
        return 'intersect.line_circle', {'line': _ref(first), 'circle': _ref(second)}, ['first', 'second']
    if t1 in circular and t2 in linear:
        return 'intersect.line_circle', {'line': _ref(second), 'circle': _ref(first)}, ['first', 'second']
    if t1 in circular and t2 in circular:
        return 'intersect.circle_circle', {'first': _ref(first), 'second': _ref(second)}, ['first', 'second']
    return None


def _origin(doc, receiver) -> dict:
    op_id, op = _producer_op(doc, receiver)
    entry = {'op': op['op'], 'args': copy.deepcopy(op.get('args') or {})}
    value = doc.inputs.get(receiver)
    if value is not None:
        entry['input'] = {value['kind']: copy.deepcopy(value['value'])}
    return entry


# ── candidates ────────────────────────────────────────────────────────────

def condition_candidates(doc, statement) -> list:
    """``[{elementId, ok, reason}]`` for every point of the statement, in its
    order: ``ok`` when it can be the receiver; ``reason`` ``None``,
    ``no_recipe`` (no recipe puts it in the receiver's place), ``not_free``
    or ``ancestor``. Structural."""
    doc = as_document(doc)
    participants = _points(doc, statement)
    receivers = {binds[recipe['receiver']] for recipe, binds in matches(doc, statement)}
    out = []
    for el_id in participants:
        if el_id not in receivers:
            out.append({'elementId': el_id, 'ok': False, 'reason': 'no_recipe'})
            continue
        status = _status(doc, el_id, participants)
        out.append({'elementId': el_id, 'ok': status == 'ok', 'reason': None if status == 'ok' else status})
    return out


# ── apply ─────────────────────────────────────────────────────────────────

def apply_condition(doc, condition, *, receiver=None, id_factory=None, ev=None, marks: bool = True) -> ConditionResult:
    """Apply ``condition = {statement, mode: "construct", source, shapeId?}``
    (plan L3 §3.6). Refusals: ``unsupported_condition``,
    ``receiver_not_free``, ``receiver_is_ancestor``, ``too_many_conditions``,
    ``no_intersection_now``. ``marks``: add the automatic marks of the
    condition (:func:`animageo.native.conditions.marks.add_auto_marks`; the
    web passes ``False`` when «Отмечать автоматически» is off)."""
    from ..kernel.evaluate import evaluate
    doc = as_document(doc)
    statement = condition.get('statement')
    problems = statement_problems(statement, doc)
    if problems:
        raise ValueError('; '.join(f'{p[1]}: {p[2]}' for p in problems))
    ev = ev if ev is not None else evaluate(doc)
    found = matches(doc, statement)
    participants = _points(doc, statement)
    if not found:
        return _refuse(doc, 'unsupported_condition', 'no recipe makes this condition', list(_ESCAPE))
    receivers = []
    for recipe, binds in found:
        if binds[recipe['receiver']] not in receivers:
            receivers.append(binds[recipe['receiver']])
    options = _make_free_options(doc, participants) + list(_ESCAPE)
    if receiver is not None:
        if receiver not in receivers:
            return _refuse(doc, 'unsupported_condition', f'no recipe moves {receiver!r} for this condition',
                           list(_ESCAPE))
        status = _status(doc, receiver, participants)
        if status == 'not_free':
            return _refuse(doc, 'receiver_not_free', f'{receiver!r} is not a free point', options)
        if status == 'ancestor':
            return _refuse(doc, 'receiver_is_ancestor', f'{receiver!r} is an ancestor of another participant',
                           options)
    else:
        statuses = {r: _status(doc, r, participants) for r in receivers}
        ok = [r for r in receivers if statuses[r] == 'ok']
        if not ok:
            if any(s == 'ancestor' for s in statuses.values()):
                return _refuse(doc, 'receiver_is_ancestor', 'every possible receiver is an ancestor of another '
                               'participant', options)
            return _refuse(doc, 'receiver_not_free', 'no possible receiver is free', options)
        receiver = _choose(doc, ok, participants)
    if _constraints(doc, receiver) >= MAX_CONSTRAINTS:
        return _refuse(doc, 'too_many_conditions', f'{receiver!r} already has {MAX_CONSTRAINTS} constraints',
                       list(_ESCAPE))
    recipe, binds = next((r, b) for r, b in found if b[r['receiver']] == receiver)
    ids = _Ids(doc.data, id_factory)
    cid = ids.make('condition', 'c')
    data, made, place_ops = _place_ops(doc, recipe, binds, cid, ids, ev)
    redef = next(s for s in recipe['template'] if 'redefine' in s)
    locus = _arg(redef['args']['path'], binds, made, ev)['elementId']
    rop_id, rop = _producer_op(doc, receiver)
    xy = _xy(ev, receiver)
    staged = NativeDocument(data)
    if rop['op'] == 'point.free':
        from .. import project
        target = _onto_ray(staged, locus, xy) if xy is not None else None
        t = project(staged, locus, target) if target is not None else None
        if t is None:
            return _refuse(doc, 'no_intersection_now', f'the place of {receiver!r} is not defined now',
                           list(_ESCAPE))
        result = redefine(staged, rop_id, {'op': 'point.on_path', 'args': {'path': _ref(locus)}},
                          inputs={receiver: {'kind': 'pathParameter', 'value': t}})
    else:
        old_path = next(iter(iter_refs(rop['args'].get('path') or {})), None)
        meet = _meet(staged, old_path, locus) if old_path else None
        if meet is None:
            return _refuse(doc, 'unsupported_condition', 'these two places do not intersect by an operation',
                           list(_ESCAPE))
        op_name, args, slots = meet
        best = None
        for slot in slots:
            trial = redefine(staged, rop_id, {'op': op_name, 'args': args}, slot_map={'point': slot})
            new_xy = _xy(evaluate(trial.document), receiver)
            if new_xy is None or xy is None:
                continue
            d = math.hypot(new_xy[0] - xy[0], new_xy[1] - xy[1])
            if best is None or d < best[0]:
                best = (d, trial)
        if best is None:
            return _refuse(doc, 'no_intersection_now', 'the places of the point do not meet now', list(_ESCAPE))
        result = best[1]
    new_data = json_copy(result.document.data)
    entry = {'id': cid, 'seq': _max_seq(new_data) + 1, 'mode': 'construct', 'statement': copy.deepcopy(statement),
             'receiver': receiver, 'recipe': recipe['recipe'], 'operationIds': place_ops + [rop_id]}
    previous = [c for c in condition_list(doc) if c.get('mode') == 'construct' and c.get('receiver') == receiver]
    entry['receiverOrigin'] = copy.deepcopy(previous[0].get('receiverOrigin')) if previous else _origin(doc, receiver)
    entry['source'] = condition.get('source', 'panel')
    entry['shapeId'] = condition.get('shapeId')
    new_data.setdefault('conditions', []).append(entry)
    new_doc = NativeDocument(new_data)
    errors = [i for i in validate(new_doc) if i.severity == 'error']
    if errors:
        raise AssertionError(f'recipe {recipe["recipe"]} made an invalid document: {errors}')
    effects = result.effects
    effects['added']['operations'] = sorted(set(effects['added']['operations']) | set(place_ops))
    effects['added']['elements'] = sorted(set(effects['added']['elements']) | set(made.values()))
    after = evaluate(new_doc)
    if marks:
        from .marks import add_auto_marks
        marked = add_auto_marks(new_doc, [cid], ev=after, id_factory=id_factory)
        new_doc = marked.document
        effects['added']['operations'] = sorted(set(effects['added']['operations']) |
                                                {op['id'] for op in marked.operations})
        effects['added']['elements'] = sorted(set(effects['added']['elements']) | set(marked.elements))
        effects['warnings'] = list(effects.get('warnings', [])) + marked.warnings
    new_xy = _xy(after, receiver)
    if xy is not None and new_xy is not None:
        effects['shift'] = {'elementId': receiver, 'from': list(xy), 'to': list(new_xy),
                            'distance': math.hypot(new_xy[0] - xy[0], new_xy[1] - xy[1])}
    else:
        effects['shift'] = None
    return ConditionResult(new_doc, effects, entry, None)


# ── release ───────────────────────────────────────────────────────────────

def release_condition(doc, condition_id, *, ev=None) -> ConditionResult:
    """Remove a condition: the receiver keeps its other constraints (none —
    ``point.free`` at its position, from ``receiverOrigin`` without ``ev``
    and the warning ``restored_origin``; one — ``point.on_path`` on the
    place left, at the projection); the places and marks of the condition
    go."""
    from .. import project
    from ..kernel.evaluate import evaluate
    doc = as_document(doc)
    conditions = condition_list(doc)
    cond = next((c for c in conditions if c.get('id') == condition_id), None)
    if cond is None:
        raise ValueError(f'unknown condition {condition_id!r}')
    data = json_copy(doc.data)
    data['conditions'] = [c for c in data['conditions'] if not (isinstance(c, dict) and c.get('id') == condition_id)]
    if not data['conditions']:
        del data['conditions']
    effects = _effects()
    warnings = []
    receiver = cond.get('receiver')
    place_ops = [o for o in cond.get('operationIds') or () if o in doc.operations
                 and o != bound_producer(doc, receiver or '')]
    staged = NativeDocument(data)
    if cond.get('mode') == 'construct' and receiver in doc.elements:
        rop_id, rop = _producer_op(doc, receiver)
        mine = {o['elementId'] for op_id in place_ops for o in doc.operations[op_id]['outputs']}
        mine |= set(_bound_locus(doc, cond))
        left = [r for slot, arg in sorted(rop['args'].items()) for r in iter_refs(arg) if r not in mine]
        xy = _xy(ev, receiver) if ev is not None else None
        if not left:
            if xy is None:
                origin = cond.get('receiverOrigin') or {}
                kind, value = next(iter((origin.get('input') or {}).items()), (None, None))
                if origin.get('op') == 'point.free' and kind == 'point':
                    xy = tuple(value)
                    warnings.append('restored_origin')
                else:
                    xy = _xy(evaluate(doc), receiver)
            result = redefine(staged, rop_id, {'op': 'point.free', 'args': {}}, slot_map={rop_slot(doc, receiver): 'point'},
                              inputs={receiver: {'kind': 'point', 'value': [xy[0], xy[1]]}})
        else:
            xy = xy if xy is not None else _xy(evaluate(doc), receiver)
            t = project(staged, left[0], xy)
            result = redefine(staged, rop_id, {'op': 'point.on_path', 'args': {'path': _ref(left[0])}},
                              slot_map={rop_slot(doc, receiver): 'point'},
                              inputs={receiver: {'kind': 'pathParameter', 'value': t if t is not None else 0.0}})
        staged = result.document
        for group in ('added', 'removed', 'modified'):
            for key, ids in result.effects[group].items():
                effects[group][key] = list(ids)
    gone = [o['elementId'] for op_id in place_ops for o in doc.operations[op_id]['outputs']
            if o['elementId'] in staged.elements]
    gone += [e for e, el in staged.elements.items()
             if isinstance(el.get('origin'), dict) and el['origin'].get('kind') == 'auto'
             and el['origin'].get('source') == condition_id]
    if gone:
        removed = delete(staged, sorted(set(gone)))
        staged = removed.document
        for key, ids in removed.effects['removed'].items():
            effects['removed'][key] = list(effects['removed'].get(key, [])) + list(ids)
    data = json_copy(staged.data)
    marks = data.get('suppressedMarks')
    if isinstance(marks, list):
        data['suppressedMarks'] = [m for m in marks if not (isinstance(m, dict) and m.get('source') == condition_id)]
    effects['warnings'] = list(effects.get('warnings', [])) + warnings
    effects['removed']['conditions'] = [condition_id]
    new_doc = NativeDocument(data)
    return ConditionResult(new_doc, _finish(effects), cond, None)


def _bound_locus(doc, cond) -> list:
    """The place of a condition that is an element of the document, not a
    place it made (``on_object``: the path ``W``)."""
    for recipe, binds in matches(doc, cond.get('statement') or {}):
        if recipe['recipe'] != cond.get('recipe') or binds.get(recipe['receiver']) != cond.get('receiver'):
            continue
        spec = next(s for s in recipe['template'] if 'redefine' in s)['args']['path']
        return [] if spec.startswith('$') else [binds[spec]]
    return []


def rop_slot(doc, el_id) -> str:
    return doc.elements[el_id]['producer']['slot']


# ── shapes ────────────────────────────────────────────────────────────────

def _len(p, q):
    return {'len': {'pair': [p, q]}}


def _par(a, b, c, d):
    return {'kind': 'parallel', 'a': {'pair': [a, b]}, 'b': {'pair': [c, d]}}


def _right(a, v, b):
    return {'kind': 'eq', 'left': {'angle': [{'ref': a}, {'ref': v}, {'ref': b}]}, 'right': {'deg': 90}}


SHAPES = {
    'right_triangle': (3, lambda A, B, C, D=None: [(_right(A, C, B), C)]),
    'isosceles': (3, lambda A, B, C, D=None: [({'kind': 'eq', 'left': _len(C, A), 'right': _len(C, B)}, C)]),
    'equilateral': (3, lambda A, B, C, D=None: [({'kind': 'eq', 'left': _len(A, B), 'right': _len(A, C)}, C),
                                                ({'kind': 'eq', 'left': _len(B, A), 'right': _len(B, C)}, C)]),
    'parallelogram': (4, lambda A, B, C, D: [(_par(A, B, D, C), D), (_par(A, D, B, C), D)]),
    'rhombus': (4, lambda A, B, C, D: [({'kind': 'eq', 'left': _len(A, B), 'right': _len(B, C)}, C),
                                       (_par(A, B, D, C), D), (_par(A, D, B, C), D)]),
    'rectangle': (4, lambda A, B, C, D: [(_right(A, B, C), C), (_par(A, B, D, C), D), (_par(A, D, B, C), D)]),
    'square': (4, lambda A, B, C, D: [(_right(A, B, C), C), ({'kind': 'eq', 'left': _len(B, C), 'right': _len(A, B)}, C),
                                      (_par(A, B, D, C), D), (_par(A, D, B, C), D)]),
    'trapezoid': (4, lambda A, B, C, D: [(_par(A, B, D, C), D)]),
}


def shape_conditions(doc, polygon_id, shape) -> list:
    """``[{statement, receiver}]`` that make the ``polygon.by_points``
    ``polygon_id`` the ``shape`` (:data:`SHAPES`), in the order to apply
    them; ``[]`` for another polygon (the caller refuses with
    ``unsupported_condition``). Structural."""
    doc = as_document(doc)
    if shape not in SHAPES or polygon_id not in doc.elements:
        return []
    op_id, op = _producer_op(doc, polygon_id)
    if op is None or op['op'] != 'polygon.by_points':
        return []
    vertices = list(iter_refs(op['args'].get('vertices') or {}))
    n, make = SHAPES[shape]
    if len(vertices) != n or len(set(vertices)) != n:
        return []
    return [{'statement': st, 'receiver': rec} for st, rec in make(*vertices)]
