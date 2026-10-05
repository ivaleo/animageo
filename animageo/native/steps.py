"""Steps of a construction (1.9.0a1, plan L3 §2.3–§2.4; docs/native/steps.md).

``steps(doc) → [Step]``: the order in which a construction is told — by
``describe``, the step list of the web and the steps of a timeline.

1. Explicit groups (``doc["steps"]``, ``kind`` given | group | condition)
   are checked (:func:`step_issues`; an error raises :class:`StepError`);
   every operation outside them is a step of its own, ``id = "op:<opId>"``,
   ``kind = "op"``.
2. Steps are ordered by their dependencies (Kahn): a step depends on another
   when one of its operations depends on one of the other's. Ties: the
   smallest order key of the step's operations (:func:`order_key`:
   operations without ``seq`` first, by ID; then by ``seq``; ties by ID),
   then the step ID. Inside a step the operations follow the same rule.
   Operations on a dependency cycle (a broken document) come last.
3. «Дано»: unless the document has an explicit ``given`` step, the longest
   prefix of ``op`` steps of ``point.free`` or ``number.free`` merges into
   the step ``id = "given"``, ``kind = "given"``.
4. ``elementIds``: the outputs of the step's operations (operation order,
   then output order) that ``appearance`` does not hide; ``auxElementIds``:
   the hidden ones (pairs, helper lines). ``conditionIds`` is empty until
   the conditions of stage 2.

``steps_merge`` and ``steps_split`` return a new ``steps`` array for the
document (structural helpers of the web API: «Объединить с предыдущим»,
«Разделить»); a result that cannot be ordered raises :class:`StepError`
with ``step_cycle``. Pure Python, no evaluation.
"""
from __future__ import annotations

import copy
import heapq
from dataclasses import dataclass, field

from .document import Issue, as_document, cyclic_operations, op_dependencies

__all__ = ['FREE_GIVEN', 'Step', 'StepError', 'assign_seq', 'order_key', 'step_issues', 'steps',
           'steps_merge', 'steps_split']

FREE_GIVEN = ('point.free', 'number.free')


@dataclass
class Step:
    """One step of :func:`steps`; ``kind`` is given | op | group | condition."""

    id: str
    kind: str
    title: str | None = None
    text: str | None = None
    operationIds: list = field(default_factory=list)
    elementIds: list = field(default_factory=list)
    auxElementIds: list = field(default_factory=list)
    conditionIds: list = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {'id': self.id, 'kind': self.kind}
        if self.title is not None:
            out['title'] = self.title
        if self.text is not None:
            out['text'] = self.text
        out.update(operationIds=list(self.operationIds), elementIds=list(self.elementIds),
                   auxElementIds=list(self.auxElementIds), conditionIds=list(self.conditionIds))
        return out


class StepError(ValueError):
    """The explicit steps of a document are wrong (``issues``: :class:`Issue` list)."""

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__('; '.join(f'{i.code}: {i.message}' for i in self.issues))


def order_key(doc, op_id: str) -> tuple:
    """The order key of an operation: ``(0, 0, id)`` without ``seq``, else ``(1, seq, id)``."""
    seq = doc.operations[op_id].get('seq')
    return (0, 0, op_id) if seq is None else (1, seq, op_id)


def _explicit(doc) -> list:
    raw = doc.data.get('steps')
    return [s for s in raw if isinstance(s, dict)] if isinstance(raw, list) else []


def _groups(doc, explicit) -> tuple:
    """``(groups, owner)``: explicit groups then one ``op`` group per other operation."""
    ops = doc.operations
    groups = []
    owner: dict = {}
    for step in explicit:
        ids = [o for o in step.get('operationIds', []) if o in ops and o not in owner]
        for op_id in ids:
            owner[op_id] = step['id']
        groups.append({'id': step['id'], 'kind': step['kind'], 'title': step.get('title'),
                       'text': step.get('text'), 'ops': ids, 'explicit': True})
    for op_id in sorted(ops):
        if op_id not in owner:
            owner[op_id] = 'op:' + op_id
            groups.append({'id': 'op:' + op_id, 'kind': 'op', 'title': None, 'text': None, 'ops': [op_id],
                           'explicit': False})
    return groups, owner


def _kahn(nodes, deps, key) -> tuple:
    """``(order, rest)``: Kahn's order of ``nodes`` (ties by ``key``) and the nodes left on cycles."""
    users: dict = {}
    indegree = {}
    for node in nodes:
        indegree[node] = len(deps[node])
        for dep in deps[node]:
            users.setdefault(dep, []).append(node)
    heap = [(key(n), n) for n in nodes if indegree[n] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _k, node = heapq.heappop(heap)
        order.append(node)
        for user in users.get(node, ()):
            indegree[user] -= 1
            if indegree[user] == 0:
                heapq.heappush(heap, (key(user), user))
    done = set(order)
    return order, sorted((n for n in nodes if n not in done), key=key)


def _ordered(doc, groups, owner) -> tuple:
    """``(ordered groups, groups left on a step cycle, op dependencies, cyclic ops)``."""
    op_deps = op_dependencies(doc)
    cyclic = cyclic_operations(op_deps)
    by_id = {g['id']: g for g in groups}
    deps = {g['id']: set() for g in groups}
    for op_id, needs in op_deps.items():
        if op_id in cyclic:
            continue
        for dep in needs:
            a, b = owner[op_id], owner[dep]
            if a != b and dep not in cyclic:
                deps[a].add(b)
    empty = (2, 0, '')

    def key(gid):
        ops = by_id[gid]['ops']
        return (min(order_key(doc, o) for o in ops) if ops else empty), gid

    order, rest = _kahn(list(by_id), deps, key)
    return [by_id[g] for g in order], [by_id[g] for g in rest], op_deps, cyclic


def step_issues(doc, *, check_cycle: bool = True) -> list:
    """The issues of the explicit steps: ``step_duplicate_id``, ``step_empty``,
    ``step_unknown_operation``, ``step_duplicate_operation``, ``step_cycle``
    (the groups cannot be ordered by their dependencies; checked only when
    the other rules hold and ``check_cycle``)."""
    doc = as_document(doc)
    explicit = _explicit(doc)
    ops = doc.operations
    issues = []
    owner: dict = {}
    seen: set = set()
    for i, step in enumerate(explicit):
        path = f'/steps/{i}'
        if step['id'] in seen:
            issues.append(Issue('step_duplicate_id', path + '/id', f"step {step['id']!r} is defined twice"))
        seen.add(step['id'])
        ids = step.get('operationIds', [])
        if not ids:
            issues.append(Issue('step_empty', path + '/operationIds', f"step {step['id']!r} has no operations"))
        for k, op_id in enumerate(ids):
            opath = f'{path}/operationIds/{k}'
            if op_id not in ops:
                issues.append(Issue('step_unknown_operation', opath, f'operation {op_id!r} does not exist',
                                    operationId=op_id))
            elif op_id in owner:
                issues.append(Issue('step_duplicate_operation', opath,
                                    f'operation {op_id!r} is already in step {owner[op_id]!r}', operationId=op_id))
            else:
                owner[op_id] = step['id']
    if issues or not check_cycle:
        return issues
    groups, owner = _groups(doc, explicit)
    _order, rest, _deps, cyclic = _ordered(doc, groups, owner)
    return _cycle_issues(explicit, rest, cyclic)


def _cycle_issues(explicit, rest, cyclic) -> list:
    """``step_cycle`` for every explicit group left unordered (none when
    the operations themselves are on a cycle: that is the document's error)."""
    if cyclic:
        return []
    index = {step['id']: i for i, step in enumerate(explicit)}
    return [Issue('step_cycle', f"/steps/{index[group['id']]}",
                  f"step {group['id']!r} cannot be ordered by the dependencies of its operations")
            for group in rest if group['explicit']]


def _visible(doc, el_id: str) -> bool:
    appearance = doc.data.get('appearance')
    entry = appearance.get(el_id) if isinstance(appearance, dict) else None
    return not (isinstance(entry, dict) and entry.get('visible') is False)


def _step_of(doc, group, op_deps) -> Step:
    ops = group['ops']
    inside = set(ops)
    deps = {o: {d for d in op_deps[o] if d in inside and d != o} for o in ops}
    order, rest = _kahn(ops, deps, lambda o: order_key(doc, o))
    shown, hidden = [], []
    for op_id in order + rest:
        for out in doc.operations[op_id]['outputs']:
            el_id = out['elementId']
            if el_id in doc.elements:
                (shown if _visible(doc, el_id) else hidden).append(el_id)
    return Step(group['id'], group['kind'], group['title'], group['text'], order + rest, shown, hidden, [])


def steps(doc) -> list:
    """The steps of ``doc`` in order (see the module docstring)."""
    doc = as_document(doc)
    explicit = _explicit(doc)
    issues = [i for i in step_issues(doc, check_cycle=False) if i.severity == 'error']
    if issues:
        raise StepError(issues)
    groups, owner = _groups(doc, explicit)
    ordered, rest, op_deps, cyclic = _ordered(doc, groups, owner)
    issues = _cycle_issues(explicit, rest, cyclic)
    if issues:
        raise StepError(issues)
    out = [_step_of(doc, g, op_deps) for g in ordered + rest]
    if any(s.kind == 'given' for s in out):
        return out
    prefix = 0
    while prefix < len(out) and out[prefix].kind == 'op' and \
            doc.operations[out[prefix].operationIds[0]]['op'] in FREE_GIVEN:
        prefix += 1
    if prefix == 0:
        return out
    head = out[:prefix]
    given = Step('given', 'given', None, None,
                 [o for s in head for o in s.operationIds],
                 [e for s in head for e in s.elementIds],
                 [e for s in head for e in s.auxElementIds], [])
    return [given] + out[prefix:]


def _new_id(used, prefix='s') -> str:
    n = 1
    while f'{prefix}{n}' in used:
        n += 1
    return f'{prefix}{n}'


def _checked(doc, new_steps) -> list:
    data = copy.deepcopy(doc.data)
    data['steps'] = new_steps
    issues = [i for i in step_issues(as_document(data)) if i.severity == 'error']
    if issues:
        raise StepError(issues)
    return new_steps


def _explicit_dict(group_or_step) -> dict:
    out = {'id': group_or_step.id, 'kind': group_or_step.kind}
    if group_or_step.title is not None:
        out['title'] = group_or_step.title
    if group_or_step.text is not None:
        out['text'] = group_or_step.text
    out['operationIds'] = list(group_or_step.operationIds)
    return out


def steps_merge(doc, step_id: str) -> list:
    """The ``steps`` array after merging step ``step_id`` into the step before it.

    The merged step keeps the ID, title and text of the previous step when
    that step is explicit (the automatic «Дано» gives the ID ``given``;
    else those of this step when explicit; else a new ``s<n>``); its kind
    is ``given`` when either is a «Дано», else ``condition`` when either is
    a condition, else ``group``; its operations are the previous step's,
    then this step's. ``ValueError``: no such step, or the first step."""
    doc = as_document(doc)
    current = steps(doc)
    ids = [s.id for s in current]
    if step_id not in ids:
        raise ValueError(f'no step {step_id!r}')
    index = ids.index(step_id)
    if index == 0:
        raise ValueError(f'step {step_id!r} is the first step')
    prev, this = current[index - 1], current[index]
    explicit = [dict(s) for s in _explicit(doc)]
    explicit_ids = [s['id'] for s in explicit]
    kinds = {prev.kind, this.kind}
    kind = 'given' if 'given' in kinds else 'condition' if 'condition' in kinds else 'group'
    used = set(explicit_ids) | set(ids)
    if prev.id in explicit_ids:
        merged_id, title, text = prev.id, prev.title, prev.text
    elif prev.kind == 'given':                       # the automatic «Дано» becomes explicit
        merged_id = 'given' if 'given' not in explicit_ids else _new_id(used)
        title, text = (this.title, this.text) if this.id in explicit_ids else (None, None)
    elif this.id in explicit_ids:
        merged_id, title, text = this.id, this.title, this.text
    else:
        merged_id, title, text = _new_id(used), None, None
    merged = Step(merged_id, kind, title, text, prev.operationIds + this.operationIds)
    out = []
    placed = False
    for step in explicit:
        if step['id'] in (prev.id, this.id):
            if not placed:
                out.append(_explicit_dict(merged))
                placed = True
            continue
        out.append(step)
    if not placed:
        out.append(_explicit_dict(merged))
    return _checked(doc, out)


def steps_split(doc, step_id: str, operation_ids) -> list:
    """The ``steps`` array after moving ``operation_ids`` of step ``step_id``
    into a new step (``s<n>``, kind ``group`` — ``condition`` for a
    condition) right after it. A «Дано» made automatically becomes explicit
    with the operations that stay. ``ValueError``: no such step, a step of
    one operation, an empty selection, the whole step, or an operation that
    is not in the step."""
    doc = as_document(doc)
    current = steps(doc)
    by_id = {s.id: s for s in current}
    step = by_id.get(step_id)
    if step is None:
        raise ValueError(f'no step {step_id!r}')
    moved = list(dict.fromkeys(operation_ids))
    if not moved or any(o not in step.operationIds for o in moved):
        raise ValueError(f'the operations to split must be some of the operations of step {step_id!r}')
    stay = [o for o in step.operationIds if o not in moved]
    if not stay:
        raise ValueError('the split must leave operations in the step')
    explicit = [dict(s) for s in _explicit(doc)]
    explicit_ids = [s['id'] for s in explicit]
    new_id = _new_id(set(explicit_ids) | set(by_id))
    new = {'id': new_id, 'kind': 'condition' if step.kind == 'condition' else 'group', 'operationIds': moved}
    kept = Step(step.id, step.kind, step.title, step.text, stay)
    out = []
    placed = False
    for item in explicit:
        if item['id'] == step.id:
            out.append(_explicit_dict(kept))
            out.append(new)
            placed = True
        else:
            out.append(item)
    if not placed:                                  # the automatic «Дано»
        out.append(_explicit_dict(kept))
        out.append(new)
    return _checked(doc, out)


def assign_seq(doc, op_ids) -> dict:
    """A copy of the document with ``seq`` = ``max(seq) + 1, …`` given to
    ``op_ids`` in that order (``max`` over the document, ``0`` without any).
    ``ValueError`` for an operation that does not exist."""
    doc = as_document(doc)
    data = copy.deepcopy(doc.data)
    ops = data['operations']
    for op_id in op_ids:
        if op_id not in ops:
            raise ValueError(f'no operation {op_id!r}')
    base = max((op['seq'] for op in ops.values() if isinstance(op.get('seq'), int)), default=0)
    for k, op_id in enumerate(op_ids, start=1):
        ops[op_id]['seq'] = base + k
    return data


