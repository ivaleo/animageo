"""``delete`` and ``redefine`` around conditions (plan L3 §3.6 «Правка»,
docs/native/conditions.md §5). Called by :func:`animageo.native.delete` and
:func:`animageo.native.redefine` when the document has conditions.

- Deleting a participant of a construct condition (anything in the closure
  of what is deleted, the receiver aside) restores the receiver first: its
  operation becomes ``receiverOrigin`` of the first condition on it (with
  its input); without a usable origin (none, or it uses a place) —
  ``point.free`` at the current position. Every condition on that receiver
  goes, with its places and automatic marks. Repeated until nothing more is
  affected, then the deletion itself.
- A condition whose receiver or a participant is gone after that (the
  receiver deleted on purpose, a ``check`` condition) is removed with its
  places and marks.
- Redefining the operation of a receiver removes the conditions on it (the
  places the new arguments do not use go, and the marks).
- ``condition_cycle``: a result in which a receiver is an ancestor of a
  participant of its condition.
"""
from __future__ import annotations

import copy

from ..document import Issue, NativeDocument, bound_producer, iter_refs
from ..edit import EditError, EditResult, _delete, _effects, _finish, _redefine, closure
from ..registry import registry
from .statements import statement_elements
from .validate import condition_list

__all__ = ['delete_with_conditions', 'redefine_with_conditions']


def _merge(effects, other) -> None:
    for group in ('added', 'removed', 'modified'):
        for key, ids in other[group].items():
            effects[group][key] = list(effects[group].get(key, [])) + list(ids)
    effects['warnings'] = list(effects.get('warnings', [])) + list(other.get('warnings', []))


def _participants(cond) -> set:
    return set(statement_elements(cond.get('statement') or {})) - {cond.get('receiver')}


def _construct(doc) -> list:
    return [c for c in condition_list(doc) if c.get('mode') == 'construct' and isinstance(c.get('receiver'), str)]


def _owned(doc, cids, keep=()) -> list:
    """The elements of the places and automatic marks of conditions ``cids``."""
    out = []
    for cond in condition_list(doc):
        if cond.get('id') not in cids:
            continue
        receiver_op = bound_producer(doc, cond['receiver']) if cond.get('receiver') in doc.elements else None
        for op_id in cond.get('operationIds') or ():
            if op_id in doc.operations and op_id != receiver_op:
                out += [o['elementId'] for o in doc.operations[op_id]['outputs'] if o['elementId'] in doc.elements]
    out += [e for e, el in doc.elements.items()
            if isinstance(el.get('origin'), dict) and el['origin'].get('kind') == 'auto'
            and el['origin'].get('source') in cids]
    return sorted(set(out) - set(keep))


def _without(doc, cids) -> NativeDocument:
    data = copy.deepcopy(doc.data)
    data['conditions'] = [c for c in data['conditions'] if not (isinstance(c, dict) and c.get('id') in cids)]
    if not data['conditions']:
        del data['conditions']
    marks = data.get('suppressedMarks')
    if isinstance(marks, list):
        data['suppressedMarks'] = [m for m in marks if not (isinstance(m, dict) and m.get('source') in cids)]
    return NativeDocument(data)


def _drop(doc, cids, effects, keep=()) -> NativeDocument:
    """Remove conditions ``cids`` with their places and marks."""
    gone = _owned(doc, cids, keep)
    staged = _without(doc, cids)
    effects['removed']['conditions'] = list(effects['removed'].get('conditions', [])) + sorted(cids)
    if gone:
        result = _delete(staged, gone)
        _merge(effects, result.effects)
        staged = result.document
    return staged


def _restore(doc, receiver, effects) -> NativeDocument:
    conds = [c for c in _construct(doc) if c['receiver'] == receiver]
    cids = {c['id'] for c in conds}
    places = set(_owned(doc, cids))
    origin = next((c.get('receiverOrigin') for c in conds if isinstance(c.get('receiverOrigin'), dict)), None)
    rop_id = bound_producer(doc, receiver)
    slot = doc.elements[receiver]['producer']['slot']
    new_op = inputs = None
    if origin and registry().get(origin.get('op')) is not None:
        refs = list(iter_refs(origin.get('args') or {}))
        if all(r in doc.elements and r not in places for r in refs):
            new_op = {'op': origin['op'], 'args': copy.deepcopy(origin.get('args') or {})}
            kind, value = next(iter((origin.get('input') or {}).items()), (None, None))
            if kind is not None:
                inputs = {receiver: {'kind': kind, 'value': copy.deepcopy(value)}}
    if new_op is None:
        from ..kernel.evaluate import evaluate
        state = evaluate(doc).elements.get(receiver)
        v = state['value'] if state and state['state'] == 'defined' else {'x': 0.0, 'y': 0.0}
        xy = [v['x'], v['y']] if isinstance(v, dict) else [v[0], v[1]]
        new_op, inputs = {'op': 'point.free', 'args': {}}, {receiver: {'kind': 'point', 'value': xy}}
        effects['warnings'] = list(effects.get('warnings', [])) + ['origin_unusable']
    out_slot = registry().get(new_op['op'])['outputs'][0]['slot']
    staged = _without(doc, cids)
    result = _redefine(staged, rop_id, new_op, slot_map={slot: out_slot}, inputs=inputs)
    _merge(effects, result.effects)
    effects['modified']['restoredFrom'] = list(effects['modified'].get('restoredFrom', [])) + [receiver]
    effects['removed']['conditions'] = list(effects['removed'].get('conditions', [])) + sorted(cids)
    gone = [e for e in places if e in result.document.elements]
    if gone:
        removed = _delete(result.document, gone)
        _merge(effects, removed.effects)
        return removed.document
    return result.document


def _stale(doc) -> set:
    out = set()
    for cond in condition_list(doc):
        if not isinstance(cond.get('id'), str):
            continue
        needed = set(statement_elements(cond.get('statement') or {}))
        if cond.get('mode') == 'construct' and isinstance(cond.get('receiver'), str):
            needed.add(cond['receiver'])
        if any(e not in doc.elements for e in needed):
            out.add(cond['id'])
    return out


def delete_with_conditions(doc, ids, *, mode='element') -> EditResult:
    effects = _effects()
    effects['removed']['conditions'] = []
    effects['modified']['restoredFrom'] = []
    ids = list(ids) if not isinstance(ids, str) else [ids]
    targets = set(ids)
    cur = doc
    done = set()
    while True:
        present = [i for i in ids if i in cur.elements]
        gone = set(cur.elements) - set(_delete(cur, present, mode=mode).document.elements) if present else set()
        receiver = next((c['receiver'] for c in _construct(cur)
                         if c['receiver'] not in targets and c['receiver'] in cur.elements
                         and c['receiver'] not in done and _participants(c) & gone), None)
        if receiver is None:
            break
        done.add(receiver)
        cur = _restore(cur, receiver, effects)
    present = [i for i in ids if i in cur.elements]
    if present:
        result = _delete(cur, present, mode=mode)
        _merge(effects, result.effects)
        cur = result.document
    stale = _stale(cur)
    if stale:
        cur = _drop(cur, stale, effects)
    return EditResult(cur, _finish(effects))


def redefine_with_conditions(doc, op_id, new_op, *, slot_map=None, inputs=None) -> EditResult:
    effects = _effects()
    effects['removed']['conditions'] = []
    mine = {c['id'] for c in _construct(doc)
            if c['receiver'] in doc.elements and bound_producer(doc, c['receiver']) == op_id}
    if mine:
        used = set(iter_refs((new_op or {}).get('args') or {})) if isinstance(new_op, dict) else set()
        places = _owned(doc, mine)
        staged = _without(doc, mine)
        result = _redefine(staged, op_id, new_op, slot_map=slot_map, inputs=inputs)
        _merge(effects, result.effects)
        effects['removed']['conditions'] = sorted(mine)
        cur = result.document
        gone = [e for e in places if e in cur.elements and e not in used]
        if gone:
            removed = _delete(cur, gone)
            _merge(effects, removed.effects)
            cur = removed.document
    else:
        result = _redefine(doc, op_id, new_op, slot_map=slot_map, inputs=inputs)
        _merge(effects, result.effects)
        cur = result.document
    issues = []
    for i, cond in enumerate(condition_list(cur)):
        receiver = cond.get('receiver')
        if cond.get('mode') != 'construct' or receiver not in cur.elements:
            continue
        below = set(closure(cur, [receiver], direction='down')) - {receiver}
        if below & _participants(cond):
            issues.append(Issue('condition_cycle', f'/conditions/{i}',
                                f"receiver {receiver!r} of condition {cond.get('id')!r} would be built on its own "
                                f"participant", elementId=receiver))
    if issues:
        raise EditError(issues)
    return EditResult(cur, _finish(effects))
