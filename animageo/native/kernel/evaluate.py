"""Evaluation of a document: values, states and reasons by element ID.

Contract (``docs/native/kernel.md``), per operation in dependency order:

1. on a dependency cycle → ``error/cycle``;
2. not in the registry → ``unsupported/unknown_op`` (``newer_registry`` when
   the document's registry version is newer than the library's);
3. argument check, slots in registry order: an argument slot the op does not
   declare → ``error/schema``; then per declared input slot: missing →
   ``error/schema``, wrong argument kind or a list shorter than ``min`` →
   ``error/type_mismatch`` (a ``number`` slot also takes a number literal),
   each reference in order: missing element → ``error/dangling_ref``,
   element type not fitting the slot → ``error/type_mismatch``; then per
   param: not a number → ``error/type_mismatch``, a required one missing →
   ``error/schema``; a free operation without a valid input value →
   ``error/schema`` (the input is the value of the element of its first
   output slot; an ``angle`` input may be absent and defaults to ``0``);
4. an input not ``defined`` → the worst input state
   (``error > unsupported > undefined``), ``reason: upstream``, ``cause`` =
   that input's ``cause`` or its ID; ties go to the first input in registry
   slot order (list items in order);
5. otherwise the implementation runs; a non-finite value becomes
   ``undefined/non_finite``, an exception ``error/internal`` plus a
   diagnostics entry.

Each element takes the result of its producer slot. An element whose
producer does not bind it, or whose slot the op does not declare, is
``error/schema``; one whose type differs from the slot type is
``error/type_mismatch``. Every element gets a record; the order of
evaluation does not change any record.

Checks (``checks.py``) run for an operation that ran, gave a value for every
slot of its result and whose every element (``producer.operationId``) is
``defined``.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from ..document import (
    NativeDocument,
    as_document,
    bound_producer,
    cyclic_operations,
    is_newer_registry,
    iter_refs,
    op_dependencies,
)
from ..registry import FREE_INPUT_DEFAULTS, REGISTRY_VERSION, free_slot, registry
from . import paths
from .numeric import Tolerances, scene_scale, tolerances
from .ops import IMPLEMENTATIONS, OpContext
from .values import (
    STATE_RANK,
    Detailed,
    Input,
    Undefined,
    defined_record,
    is_finite_value,
    state_record,
)

__all__ = ['EVALUATED_FORMAT', 'Arguments', 'Evaluated', 'evaluate', 'check_inputs', 'valid_input',
           'producer_values', 'number_literal']

EVALUATED_FORMAT = 'animageo-evaluated/v1'


def _library_version() -> str:
    from ... import __version__
    return __version__


@dataclass
class Evaluated:
    """The result of :func:`evaluate`; :meth:`to_dict` is ``animageo-evaluated/v1``."""

    document_id: str
    scale: float
    elements: dict
    diagnostics: list
    tolerances: Tolerances
    library: str = ''
    registry: str = REGISTRY_VERSION
    # operationId -> (op, args, result) for ops that ran and gave only values
    computed: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            'format': EVALUATED_FORMAT,
            'documentId': self.document_id,
            'kernel': {'library': self.library, 'registry': self.registry},
            'scale': self.scale,
            'elements': self.elements,
            'diagnostics': self.diagnostics,
        }


def _free_elements(doc: NativeDocument, reg) -> dict:
    """``{elementId: free kind}`` for the elements holding the input of a free
    operation (bound to its first output slot)."""
    out = {}
    for el_id in doc.elements:
        producer = bound_producer(doc, el_id)
        if producer is None:
            continue
        record = reg.get(doc.operations[producer]['op'])
        if record is not None and record.get('free') is not None and \
                doc.elements[el_id]['producer']['slot'] == free_slot(record):
            out[el_id] = record['free']['kind']
    return out


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _valid_point_input(value) -> bool:
    if not isinstance(value, dict) or value.get('kind') != 'point':
        return False
    xy = value.get('value')
    return isinstance(xy, (list, tuple)) and len(xy) == 2 and all(_finite(v) for v in xy)


def _valid_path_input(value) -> bool:
    if not isinstance(value, dict) or value.get('kind') != 'pathParameter':
        return False
    if not set(value) <= {'kind', 'value', 'branch'} or not _finite(value.get('value')):
        return False
    branch = value.get('branch', 1)
    return _finite(branch) and branch in (-1, 1)


def _valid_number_input(value) -> bool:
    if not isinstance(value, dict) or value.get('kind') != 'number':
        return False
    return set(value) == {'kind', 'value'} and _finite(value.get('value'))


def _valid_angle_input(value) -> bool:
    if not isinstance(value, dict) or value.get('kind') != 'angle':
        return False
    return set(value) == {'kind', 'value'} and _finite(value.get('value'))


_INPUT_VALIDATORS = {'point': _valid_point_input, 'pathParameter': _valid_path_input,
                     'number': _valid_number_input, 'angle': _valid_angle_input}
# A free input of these kinds may be absent from ``inputs``: it takes this value.
INPUT_DEFAULTS = FREE_INPUT_DEFAULTS
_INPUT_SHAPES = {
    'point': '{"kind": "point", "value": [x, y]} with finite numbers',
    'pathParameter': '{"kind": "pathParameter", "value": t, "branch"?: -1 | 1} with a finite t',
    'number': '{"kind": "number", "value": v} with a finite v',
    'angle': '{"kind": "angle", "value": radians} with a finite value',
}


def valid_input(kind: str, value) -> bool:
    """Whether ``value`` is a usable input value of a free input of ``kind``."""
    check = _INPUT_VALIDATORS.get(kind)
    return check is not None and check(value)


def check_inputs(doc: NativeDocument, inputs) -> dict:
    """Validate case ``inputs`` (overrides of free input values); raise ``ValueError``."""
    if inputs is None:
        return {}
    if not isinstance(inputs, dict):
        raise ValueError('inputs must be a mapping of element ID to input value')
    free = _free_elements(doc, registry())
    for el_id, value in inputs.items():
        if el_id not in doc.elements:
            raise ValueError(f'input for unknown element {el_id!r}')
        kind = free.get(el_id)
        if kind is None:
            raise ValueError(f'element {el_id!r} is not a free input')
        if not valid_input(kind, value):
            raise ValueError(f'input of {el_id!r} must be {_INPUT_SHAPES.get(kind, kind)}')
    return dict(inputs)


def producer_values(ref, elements, ops, states) -> tuple:
    """``(producer op name, {slot: value | [value…]})`` of a defined element:
    the values of the elements its producer's arguments reference."""
    producer = ops[elements[ref]['producer']['operationId']]
    values = {}
    for slot, arg in producer['args'].items():
        recs = [states.get(i) for i in iter_refs(arg)]
        if not recs or not all(r is not None and r['state'] == 'defined' for r in recs):
            continue
        vals = [r['value'] for r in recs]
        values[slot] = vals if arg.get('kind') == 'list' else vals[0]
    return producer['op'], values


def _path_frame(ref, elements, ops, states):
    producer_op, values = producer_values(ref, elements, ops, states)
    return paths.frame(elements[ref]['type'], states[ref]['value'], producer_op, values)


def _order(op_ids, deps, cyclic) -> list:
    """Kahn's order, ties by operation ID; cycle members wait for nothing."""
    users = {op_id: [] for op_id in op_ids}
    indegree = {}
    for op_id in op_ids:
        needs = set() if op_id in cyclic else deps[op_id]
        indegree[op_id] = len(needs)
        for dep in needs:
            users[dep].append(op_id)
    heap = [op_id for op_id, n in indegree.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        op_id = heapq.heappop(heap)
        order.append(op_id)
        for user in users[op_id]:
            indegree[user] -= 1
            if indegree[user] == 0:
                heapq.heappush(heap, user)
    return order


@dataclass
class Arguments:
    """The resolved arguments of a structurally valid call.

    ``refs`` — ``[(slot, list?, [elementId…])]`` of the reference input
    slots in registry order; ``literals`` — ``{slot: value}`` of number
    literals in ``number`` input slots; ``params`` — ``{slot: float | None}``
    of every declared param (the default, or ``None``, when absent).
    """

    refs: list
    literals: dict
    params: dict

    def __iter__(self):           # ``for slot, is_list, ids in arguments`` reads the refs
        return iter(self.refs)


def _argument_status(op, record, doc, reg):
    """``(state, reason)`` of a structurally broken call, else :class:`Arguments`.

    Order: an undeclared argument slot → ``error/schema``; input slots in
    registry order (missing → ``schema``, wrong kind or short list →
    ``type_mismatch``, dangling reference → ``dangling_ref``, element type
    not fitting → ``type_mismatch``; a ``number`` slot also takes a number
    literal); then params in registry order (not a number → ``type_mismatch``,
    a required one missing → ``schema``).
    """
    args = op['args']
    declared = {item['slot'] for item in record['inputs']} | {item['slot'] for item in record['params']}
    for slot in args:
        if slot not in declared:
            return ('error', 'schema')
    resolved = []
    literals = {}
    for item in record['inputs']:
        arg = args.get(item['slot'])
        if arg is None:
            return ('error', 'schema')
        if not item.get('list') and item['type'] == 'number' and arg.get('kind') == 'number':
            literals[item['slot']] = float(arg['value'])
            continue
        if item.get('list'):
            if arg.get('kind') != 'list':
                return ('error', 'type_mismatch')
            refs = arg.get('items') or []
            if len(refs) < (item.get('min') or 0):
                return ('error', 'type_mismatch')
        else:
            refs = [arg]
        ids = []
        for ref in refs:
            if ref.get('kind') != 'ref':
                return ('error', 'type_mismatch')
            target = doc.elements.get(ref.get('elementId'))
            if target is None:
                return ('error', 'dangling_ref')
            if not reg.accepts(item['type'], target['type']):
                return ('error', 'type_mismatch')
            ids.append(ref['elementId'])
        resolved.append((item['slot'], bool(item.get('list')), ids))
    params = {}
    for item in record['params']:
        arg = args.get(item['slot'])
        if arg is None:
            if not item.get('optional', False):
                return ('error', 'schema')
            default = item.get('default')
            params[item['slot']] = None if default is None else float(default)
            continue
        if arg.get('kind') != 'number':
            return ('error', 'type_mismatch')
        params[item['slot']] = float(arg['value'])
    return Arguments(resolved, literals, params)


def number_literal(value: float) -> Input:
    """A number literal argument as an op input (``unit: "scalar"``)."""
    return Input('number', {'value': value, 'unit': 'scalar'})


def evaluate(doc, *, inputs=None, _decisions=None) -> Evaluated:
    """Evaluate ``doc``; ``inputs`` overrides input values of free elements.

    ``doc`` may be a :class:`NativeDocument` or anything :func:`load` reads.
    """
    doc = as_document(doc)
    reg = registry()
    overrides = check_inputs(doc, inputs)
    values_in = dict(doc.inputs)
    values_in.update(overrides)
    ops = doc.operations
    elements = doc.elements

    free = _free_elements(doc, reg)
    points = [tuple(values_in[e]['value']) for e in sorted(free)
              if free[e] == 'point' and _valid_point_input(values_in.get(e))]
    scale = scene_scale(doc.bounds, points)
    tol = tolerances(scale)

    states: dict = {}
    diagnostics: list = []
    computed: dict = {}

    # Elements the graph cannot place: wrong producer binding, unknown slot, wrong type.
    bound: dict = {}
    for el_id in sorted(elements):
        el = elements[el_id]
        producer = bound_producer(doc, el_id)
        if producer is None:
            states[el_id] = state_record('error', el['type'], 'schema')
            continue
        record = reg.get(ops[producer]['op'])
        if record is not None:
            out_type = reg.output_type(record, el['producer']['slot'], ops[producer]['args'], doc)
            if out_type is None:
                states[el_id] = state_record('error', el['type'], 'schema')
                continue
            if out_type != el['type']:
                states[el_id] = state_record('error', el['type'], 'type_mismatch')
                continue
        bound.setdefault(producer, []).append(el_id)

    deps = op_dependencies(doc)
    cyclic = cyclic_operations(deps)
    newer = is_newer_registry(doc.registry_version)

    def settle(op_id, state, reason, cause=None, detail=None):
        for el_id in bound.get(op_id, ()):
            states[el_id] = state_record(state, elements[el_id]['type'], reason, cause=cause, detail=detail)

    for op_id in _order(list(ops), deps, cyclic):
        op = ops[op_id]
        if op_id in cyclic:
            settle(op_id, 'error', 'cycle')
            continue
        record = reg.get(op['op'])
        if record is None:
            settle(op_id, 'unsupported', 'newer_registry' if newer else 'unknown_op')
            continue
        resolved = _argument_status(op, record, doc, reg)
        if isinstance(resolved, tuple):
            settle(op_id, *resolved)
            continue
        free_input = None
        if record.get('free') is not None:
            targets = [e for e in bound.get(op_id, ())
                       if elements[e]['producer']['slot'] == record['outputs'][0]['slot']]
            free_input = values_in.get(targets[0]) if targets else None
            if free_input is None:
                free_input = INPUT_DEFAULTS.get(record['free']['kind'])
            if targets and not valid_input(record['free']['kind'], free_input):
                settle(op_id, 'error', 'schema')
                continue
            if not targets:
                continue
        worst = None
        for _slot, _is_list, ids in resolved.refs:
            for ref in ids:
                rec = states[ref]
                if rec['state'] == 'defined':
                    continue
                if worst is None or STATE_RANK[rec['state']] > STATE_RANK[worst[0]]:
                    worst = (rec['state'], rec.get('cause', ref))
        if worst is not None:
            settle(op_id, worst[0], 'upstream', cause=worst[1])
            continue
        args = dict(resolved.params)
        for slot, value in resolved.literals.items():
            args[slot] = number_literal(value)
        path_slots = {item['slot'] for item in record['inputs'] if item['type'] == 'path'}
        for slot, is_list, ids in resolved.refs:
            if slot in path_slots:
                items = [Input(elements[ref]['type'], states[ref]['value'],
                               _path_frame(ref, elements, ops, states)) for ref in ids]
            else:
                items = [Input(elements[ref]['type'], states[ref]['value']) for ref in ids]
            args[slot] = items if is_list else items[0]
        ctx = OpContext(tol, input=free_input, operation_id=op_id, decisions=_decisions)
        try:
            result = IMPLEMENTATIONS[op['op']](args, ctx)
        except Exception as exc:  # an implementation bug must not stop the evaluation
            diagnostics.append({'code': 'internal', 'operationId': op_id, 'op': op['op'],
                                'message': f'{type(exc).__name__}: {exc}'})
            settle(op_id, 'error', 'internal')
            continue
        details = {}
        for slot, value in list(result.items()):
            if isinstance(value, Detailed):
                result[slot] = value.value
                details[slot] = value.detail
        all_defined = True
        for el_id in bound.get(op_id, ()):
            slot = elements[el_id]['producer']['slot']
            value = result.get(slot)
            type_ = elements[el_id]['type']
            if isinstance(value, Undefined):
                states[el_id] = state_record('undefined', type_, value.reason, detail=value.detail)
            elif value is None:
                diagnostics.append({'code': 'internal', 'operationId': op_id, 'op': op['op'],
                                    'message': f'no value for slot {slot!r}'})
                states[el_id] = state_record('error', type_, 'internal')
            elif not is_finite_value(value):
                states[el_id] = state_record('undefined', type_, 'non_finite')
            else:
                states[el_id] = defined_record(type_, value, details.get(slot))
        for value in result.values():
            if isinstance(value, Undefined) or not is_finite_value(value):
                all_defined = False
                break
        if all_defined:
            computed[op_id] = (op['op'], args, result)

    for el_id in elements:
        if el_id not in states:  # a free op without an input value, or never reached
            states[el_id] = state_record('error', elements[el_id]['type'], 'schema')

    # Checks need an op that ran and whose every claimed element is defined.
    for el_id, el in elements.items():
        if states[el_id]['state'] != 'defined':
            computed.pop(el['producer']['operationId'], None)

    return Evaluated(
        document_id=doc.document_id,
        scale=scale,
        elements={el_id: states[el_id] for el_id in sorted(states)},
        diagnostics=diagnostics,
        tolerances=tol,
        library=_library_version(),
        registry=REGISTRY_VERSION,
        computed=computed,
    )
