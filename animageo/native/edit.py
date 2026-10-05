"""Graph queries and pure edits of a construction document (kernel.md §8).

Queries return element ID lists: :func:`closure` (topological order),
:func:`dependencies`, :func:`free_inputs`. Edits return
:class:`EditResult` ``(document, effects)`` and never change their input:
:func:`delete`, :func:`redefine`, :func:`rename`. IDs are never changed or
created. A refused edit raises :class:`EditError` with its issues.

``effects`` is a JSON-ready dict; every ID list is sorted::

    {"added":    {"operations": [], "elements": [], "inputs": []},
     "removed":  {"operations": [], "elements": [], "inputs": [], "appearance": []},
     "modified": {"operations": [], "elements": [], "inputs": []},
     "warnings": [Issue.to_dict(), …]}
"""
from __future__ import annotations

import copy
import json
import unicodedata
from typing import NamedTuple

from .document import (
    Issue,
    NativeDocument,
    _op_refs,
    _pointer,
    as_document,
    bound_producer,
    cyclic_operations,
    op_dependencies,
    structure_issues,
    structure_issues_of,
    validate,
)
from .registry import FREE_INPUT_DEFAULTS, registry

__all__ = [
    'EditError',
    'EditResult',
    'closure',
    'dependencies',
    'free_inputs',
    'delete',
    'redefine',
    'rename',
    'valid_name',
    'name_key',
    'MAX_NAME_LENGTH',
]

MAX_NAME_LENGTH = 32


class EditError(ValueError):
    """An edit was refused; ``issues`` lists why (codes in kernel.md §8)."""

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__('; '.join(f'{i.code}: {i.message}' for i in self.issues) or 'edit refused')


class EditResult(NamedTuple):
    """``document`` — the edited :class:`NativeDocument`; ``effects`` — what changed."""

    document: NativeDocument
    effects: dict


def json_copy(data):
    """A deep copy of JSON data (a document): faster than ``copy.deepcopy``;
    floats round-trip exactly, tuples become lists."""
    return json.loads(json.dumps(data))


def _effects() -> dict:
    return {
        'added': {'operations': [], 'elements': [], 'inputs': []},
        'removed': {'operations': [], 'elements': [], 'inputs': [], 'appearance': []},
        'modified': {'operations': [], 'elements': [], 'inputs': []},
        'warnings': [],
    }


def _finish(effects: dict) -> dict:
    for group in ('added', 'removed', 'modified'):
        for key, ids in effects[group].items():
            effects[group][key] = sorted(set(ids))
    return effects


def _fail(code, message, path='', **ids):
    raise EditError([Issue(code, path, message, **ids)])


def _seeds(doc, ids) -> list:
    seeds = [ids] if isinstance(ids, str) else list(ids)
    for el_id in seeds:
        if el_id not in doc.elements:
            _fail('unknown_element', f'unknown element {el_id!r}', '/elements' + _pointer(el_id),
                  elementId=el_id)
    return seeds


# ── queries ──────────────────────────────────────────────────────────────


def element_order(doc) -> list:
    """Every element ID in topological order: operations in Kahn order with
    ties by operation ID (cycle members wait for nothing), the elements of one
    operation by ID, then elements without a consistent producer by ID."""
    from .kernel.evaluate import _order

    doc = as_document(doc)
    deps = op_dependencies(doc)
    produced: dict = {}
    loose = []
    for el_id in doc.elements:
        producer = bound_producer(doc, el_id)
        if producer is None:
            loose.append(el_id)
        else:
            produced.setdefault(producer, []).append(el_id)
    out = []
    for op_id in _order(list(doc.operations), deps, cyclic_operations(deps)):
        out.extend(sorted(produced.get(op_id, ())))
    return out + sorted(loose)


def _reach(doc, seeds, direction) -> set:
    ops = doc.operations
    if direction == 'down':
        produced: dict = {}
        for el_id in doc.elements:
            producer = bound_producer(doc, el_id)
            if producer is not None:
                produced.setdefault(producer, []).append(el_id)
        users: dict = {}
        for op_id, op in ops.items():
            for ref in _op_refs(op):
                users.setdefault(ref, set()).add(op_id)

        def step(el_id):
            return [e for op_id in users.get(el_id, ()) for e in produced.get(op_id, ())]
    else:
        def step(el_id):
            producer = bound_producer(doc, el_id)
            if producer is None:
                return []
            return [r for r in _op_refs(ops[producer]) if r in doc.elements]
    seen = set(seeds)
    queue = list(seeds)
    while queue:
        for nxt in step(queue.pop()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def closure(doc, ids, *, direction: str = 'down') -> list:
    """Element IDs reachable from ``ids`` through the graph, ``ids`` included,
    in topological order (:func:`element_order`).

    ``direction="down"``: the dependents (what has to go when ``ids`` go);
    ``"up"``: the ancestors (what ``ids`` are built from).
    """
    if direction not in ('down', 'up'):
        raise ValueError("direction must be 'down' or 'up'")
    doc = as_document(doc)
    seeds = [ids] if isinstance(ids, str) else list(ids)
    for el_id in seeds:
        if el_id not in doc.elements:
            raise ValueError(f'unknown element {el_id!r}')
    seen = _reach(doc, seeds, direction)
    return [e for e in element_order(doc) if e in seen]


def dependencies(doc, element_id: str) -> list:
    """The ancestors of ``element_id`` (without it), in topological order."""
    return [e for e in closure(doc, element_id, direction='up') if e != element_id]


def _free_kind(doc, el_id):
    producer = bound_producer(doc, el_id)
    if producer is None:
        return None
    record = registry().get(doc.operations[producer].get('op'))
    if record is None or record.get('free') is None:
        return None
    return record['free']['kind']


def free_inputs(doc, ids) -> list:
    """The free elements (a free producer: point, path parameter) that
    ``ids`` are built from, ``ids`` included, in topological order."""
    doc = as_document(doc)
    return [e for e in closure(doc, ids, direction='up') if _free_kind(doc, e) is not None]


# ── delete ───────────────────────────────────────────────────────────────


def _remove_elements(data: dict, gone: set, effects: dict) -> None:
    """Drop ``gone`` elements with their inputs and appearance; strip them from
    operation outputs; drop operations left without outputs or referencing
    a dropped element."""
    elements = data.get('elements') or {}
    for el_id in gone:
        if el_id in elements:
            del elements[el_id]
            effects['removed']['elements'].append(el_id)
    inputs = data.get('inputs')
    if isinstance(inputs, dict):
        for el_id in [e for e in inputs if e in gone]:
            del inputs[el_id]
            effects['removed']['inputs'].append(el_id)
    appearance = data.get('appearance')
    if isinstance(appearance, dict):
        for el_id in [e for e in appearance if e in gone]:
            del appearance[el_id]
            effects['removed']['appearance'].append(el_id)
    ops = data.get('operations') or {}
    for op_id in list(ops):
        op = ops[op_id]
        outputs = op.get('outputs') or []
        kept = [o for o in outputs if o.get('elementId') not in gone]
        refs_gone = any(ref in gone for ref in _op_refs(op))
        if (outputs and not kept) or refs_gone:
            del ops[op_id]
            effects['removed']['operations'].append(op_id)
            effects['modified']['operations'] = [o for o in effects['modified']['operations'] if o != op_id]
        elif len(kept) != len(outputs):
            op['outputs'] = kept
            effects['modified']['operations'].append(op_id)


def delete(doc, ids, *, mode: str = 'element') -> EditResult:
    """Delete elements and everything built on them.

    ``mode="element"``: ``closure(ids, "down")`` goes; an operation loses the
    outputs that went and goes when none are left. ``mode="operation"``:
    every output of the producers of ``ids`` goes too. Inputs and appearance
    of removed elements go; other sections are kept.

    Conditions (1.9.0a2, docs/native/conditions.md §5): deleting a
    participant of a construct condition restores its receiver from
    ``receiverOrigin`` first (the receiver and what is built on it stay;
    every condition on that receiver goes with its places and automatic
    marks); a condition whose receiver or participant went is removed.
    ``effects.removed.conditions``, ``effects.modified.restoredFrom`` (the
    restored receivers).
    """
    doc = as_document(doc)
    if doc.data.get('conditions'):
        from .conditions.editing import delete_with_conditions
        return delete_with_conditions(doc, ids, mode=mode)
    return _delete(doc, ids, mode=mode)


def _delete(doc, ids, *, mode: str = 'element') -> EditResult:
    """:func:`delete` without the rules of the conditions."""
    if mode not in ('element', 'operation'):
        raise ValueError("mode must be 'element' or 'operation'")
    doc = as_document(doc)
    seeds = _seeds(doc, ids)
    if mode == 'operation':
        extra = []
        for el_id in seeds:
            producer = bound_producer(doc, el_id)
            if producer is not None:
                extra.extend(o.get('elementId') for o in doc.operations[producer].get('outputs') or ()
                             if o.get('elementId') in doc.elements)
        seeds = seeds + extra
    gone = _reach(doc, seeds, 'down')
    data = json_copy(doc.data)
    effects = _effects()
    _remove_elements(data, gone, effects)
    return EditResult(NativeDocument(data), _finish(effects))


# ── redefine ─────────────────────────────────────────────────────────────


def _issue_keys(issues) -> set:
    return {(i.code, i.path, i.elementId, i.operationId) for i in issues if i.severity == 'error'}


def _users(doc, el_id) -> list:
    """``[(operationId, slot type)]`` of the operations that take ``el_id``."""
    reg = registry()
    out = []
    for op_id, op in doc.operations.items():
        record = reg.get(op.get('op'))
        for slot, arg in (op.get('args') or {}).items():
            refs = list(_op_refs({'args': {slot: arg}}))
            if el_id not in refs:
                continue
            item = next((i for i in (record or {}).get('inputs', ()) if i['slot'] == slot), None)
            out.append((op_id, item['type'] if item else None))
    return out


def redefine(doc, op_id: str, new_op: dict, *, slot_map=None, inputs=None) -> EditResult:
    """Replace the definition of operation ``op_id`` keeping its output IDs
    (see :func:`_redefine`). Conditions (1.9.0a2): redefining the operation
    of a receiver removes the conditions on it (their places and automatic
    marks go, ``effects.removed.conditions``); a result in which a receiver
    is an ancestor of a participant of its condition is refused with
    ``condition_cycle`` (one issue per condition)."""
    doc = as_document(doc)
    if doc.data.get('conditions'):
        from .conditions.editing import redefine_with_conditions
        return redefine_with_conditions(doc, op_id, new_op, slot_map=slot_map, inputs=inputs)
    return _redefine(doc, op_id, new_op, slot_map=slot_map, inputs=inputs)


def _redefine(doc, op_id: str, new_op: dict, *, slot_map=None, inputs=None, _take: bool = False) -> EditResult:
    """Replace the definition of operation ``op_id`` keeping its output IDs.

    ``new_op = {op, args, branch?}``. Outputs pair with the new op's slots by
    slot name or ``slot_map`` (``{old slot: new slot}``); an output without a
    pair goes with its dependents (warning ``output_removed``). Refusals, in
    order: ``unknown_operation``, ``unknown_op``, ``slot_conflict``,
    ``type_mismatch`` (an output's new type does not fit an operation that
    uses it), ``cycle`` (the new arguments use an output's dependents),
    ``missing_input`` (a free op without an input of its kind in ``inputs``
    or the document, unless the kind has a default in
    ``FREE_INPUT_DEFAULTS``: then no input is written), then any error :func:`validate` did not report before.
    """
    doc = as_document(doc)
    reg = registry()
    if op_id not in doc.operations:
        _fail('unknown_operation', f'unknown operation {op_id!r}', '/operations' + _pointer(op_id),
              operationId=op_id)
    if not isinstance(new_op, dict) or reg.get(new_op.get('op')) is None:
        name = new_op.get('op') if isinstance(new_op, dict) else new_op
        _fail('unknown_op', f'{name!r} is not in registry {reg.version}', '/operations' + _pointer(op_id),
              operationId=op_id)
    record = reg.get(new_op['op'])
    new_args = copy.deepcopy(new_op.get('args') or {})
    slot_map = dict(slot_map or {})
    old = doc.operations[op_id]
    old_outputs = [o for o in old.get('outputs') or () if o.get('elementId') in doc.elements]

    pairs = []        # (elementId, new slot, new type)
    unpaired = []
    taken = {}
    for out in old_outputs:
        slot = slot_map.get(out['slot'], out['slot'])
        new_type = reg.output_type(record, slot, new_args, doc)
        if new_type is None:
            unpaired.append(out['elementId'])
            continue
        if slot in taken:
            _fail('slot_conflict', f'outputs {taken[slot]!r} and {out["elementId"]!r} both map to slot {slot!r}',
                  '/operations' + _pointer(op_id, 'outputs'), operationId=op_id)
        taken[slot] = out['elementId']
        pairs.append((out['elementId'], slot, new_type))

    gone = _reach(doc, unpaired, 'down') if unpaired else set()
    bad_users = []
    for el_id, _slot, new_type in pairs:
        if new_type == doc.elements[el_id]['type']:
            continue
        for user, slot_type in _users(doc, el_id):
            if user == op_id or any(o.get('elementId') in gone for o in doc.operations[user].get('outputs') or ()):
                continue
            if slot_type is None or not reg.accepts(slot_type, new_type):
                bad_users.append(user)
    if bad_users:
        _fail('type_mismatch', f'the new output types do not fit operations {sorted(set(bad_users))}',
              '/operations' + _pointer(op_id), operationId=op_id)

    below = _reach(doc, [o['elementId'] for o in old_outputs], 'down') if old_outputs else set()
    for slot, arg in new_args.items():
        for ref in _op_refs({'args': {slot: arg}}):
            if ref in below:
                _fail('cycle', f'argument {slot!r} uses {ref!r}, which depends on operation {op_id!r}',
                      '/operations' + _pointer(op_id, 'args', slot), operationId=op_id, elementId=ref)

    new_inputs = dict(inputs or {})
    free = record.get('free')
    free_slot = record['outputs'][0]['slot'] if free is not None else None
    # ``_take``: the caller hands over a private document (``apply_condition``)
    data = doc.data if _take else json_copy(doc.data)
    effects = _effects()
    for el_id, slot, _type in pairs:
        if free is not None and slot == free_slot:
            given = new_inputs.get(el_id)
            if given is None:
                existing = doc.inputs.get(el_id)
                # an optional input (``FREE_INPUT_DEFAULTS``: the angle of
                # ``segment.from_point_length``) takes its default, as in
                # ``validate`` and ``evaluate``; no record is written
                if not (isinstance(existing, dict) and existing.get('kind') == free['kind']) \
                        and free['kind'] not in FREE_INPUT_DEFAULTS:
                    _fail('missing_input', f'{new_op["op"]} needs a {free["kind"]} input for {el_id!r}',
                          '/inputs' + _pointer(el_id), elementId=el_id)
    for el_id in new_inputs:
        if el_id not in {p[0] for p in pairs if free is not None and p[1] == free_slot}:
            _fail('input_not_free', f'element {el_id!r} is not a free output of the new operation',
                  '/inputs' + _pointer(el_id), elementId=el_id)

    op_out = {'id': op_id, 'op': new_op['op'], 'args': new_args,
              'outputs': [{'slot': slot, 'elementId': el_id} for el_id, slot, _ in pairs]}
    if new_op.get('branch') is not None:
        op_out['branch'] = copy.deepcopy(new_op['branch'])
    data['operations'][op_id] = op_out
    effects['modified']['operations'].append(op_id)
    for el_id, slot, new_type in pairs:
        el = data['elements'][el_id]
        if el['type'] != new_type or el['producer'].get('slot') != slot:
            el['type'] = new_type
            el['producer'] = {'operationId': op_id, 'slot': slot}
            effects['modified']['elements'].append(el_id)
    if new_inputs or free is None:
        data_inputs = data.setdefault('inputs', {})
        for el_id, value in new_inputs.items():
            group = 'modified' if el_id in data_inputs else 'added'
            data_inputs[el_id] = copy.deepcopy(value)
            effects[group]['inputs'].append(el_id)
        if free is None:
            for el_id, _slot, _type in pairs:
                if el_id in data_inputs:
                    del data_inputs[el_id]
                    effects['removed']['inputs'].append(el_id)
            if not data_inputs and 'inputs' not in doc.data:
                del data['inputs']
    if gone:
        _remove_elements(data, gone, effects)
        for el_id in sorted(set(unpaired)):
            effects['warnings'].append(Issue(
                'output_removed', '/elements' + _pointer(el_id),
                f'{new_op["op"]} has no slot for {el_id!r}; it was removed with its dependents',
                elementId=el_id, operationId=op_id, severity='warning').to_dict())
        effects['modified']['operations'] = [o for o in effects['modified']['operations'] if o in data['operations']]

    if _take:      # the rest of a handed-over document is well formed
        schema = structure_issues_of(data, operations=[op_id], elements=[p[0] for p in pairs],
                                     inputs=list(new_inputs))
    else:
        schema = structure_issues(data)
    result = NativeDocument(data, schema)   # ``data`` is already a private copy
    after = validate(result)
    after_keys = _issue_keys(after)
    # the old document only when needed; with ``_take`` it is gone, so every error is new
    old_keys = _issue_keys(validate(doc)) if after_keys and not _take else set()
    new_errors = after_keys - old_keys
    if new_errors:
        raise EditError([i for i in after if (i.code, i.path, i.elementId, i.operationId) in new_errors])
    return EditResult(result, _finish(effects))


# ── rename ───────────────────────────────────────────────────────────────


def _letter(ch) -> bool:
    return unicodedata.category(ch)[0] == 'L'


def _alnum(ch) -> bool:
    return _letter(ch) or unicodedata.category(ch) == 'Nd'


_SUBSCRIPTS = frozenset('₀₁₂₃₄₅₆₇₈₉')


def valid_name(name) -> bool:
    """The display name grammar (kernel.md §8)::

        name   = letter+ suffix? "'"*          (at most 32 code points)
        suffix = "_{" alnum+ "}" | "_" alnum+ | [0-9]+ | [₀-₉]+

    ``letter`` — a Unicode letter (category L*); ``alnum`` — a letter or a
    decimal digit (category Nd).
    """
    if not isinstance(name, str) or not 0 < len(name) <= MAX_NAME_LENGTH:
        return False
    n = len(name)
    i = 0
    while i < n and _letter(name[i]):
        i += 1
    if i == 0:
        return False
    if i < n and name[i] == '_':
        if name.startswith('_{', i):
            j = i + 2
            while j < n and _alnum(name[j]):
                j += 1
            if j == i + 2 or j >= n or name[j] != '}':
                return False
            i = j + 1
        else:
            j = i + 1
            while j < n and _alnum(name[j]):
                j += 1
            if j == i + 1:
                return False
            i = j
    elif i < n and '0' <= name[i] <= '9':
        while i < n and '0' <= name[i] <= '9':
            i += 1
    elif i < n and name[i] in _SUBSCRIPTS:
        while i < n and name[i] in _SUBSCRIPTS:
            i += 1
    while i < n and name[i] == "'":
        i += 1
    return i == n


def name_key(name: str) -> str:
    """The uniqueness key of a display name: ``_{x}`` is the same name as ``_x``."""
    head, sep, rest = name.partition('_{')
    if sep and '}' in rest:
        inner, _, tail = rest.partition('}')
        return f'{head}_{inner}{tail}'
    return name


def rename(doc, element_id: str, display_name: str) -> EditResult:
    """Set the ``displayName`` of an element; the graph does not change.

    Refusals: ``unknown_element``, ``invalid_name`` (grammar of
    :func:`valid_name`), ``duplicate_name`` (another element has the same
    :func:`name_key`).
    """
    doc = as_document(doc)
    _seeds(doc, [element_id])
    path = '/elements' + _pointer(element_id, 'displayName')
    if not valid_name(display_name):
        _fail('invalid_name', f'{display_name!r} is not a valid name', path, elementId=element_id)
    key = name_key(display_name)
    for other_id, el in doc.elements.items():
        other = el.get('displayName') if isinstance(el, dict) else None
        if other_id != element_id and isinstance(other, str) and name_key(other) == key:
            _fail('duplicate_name', f'{display_name!r} is already the name of {other_id!r}', path,
                  elementId=element_id)
    data = json_copy(doc.data)
    effects = _effects()
    if data['elements'][element_id].get('displayName') != display_name:
        data['elements'][element_id]['displayName'] = display_name
        effects['modified']['elements'].append(element_id)
    return EditResult(NativeDocument(data), _finish(effects))
