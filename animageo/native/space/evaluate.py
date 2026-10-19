"""Evaluation of a space document (registry 1.6, experimental).

The contract is that of the plane (:func:`animageo.native.evaluate`):
operations in Kahn's order with ties by ID; a cycle → ``error/cycle``; an
operation not in registry 1.6 → ``unsupported`` (``space_unsupported`` for
an operation of the plane, ``newer_registry`` / ``unknown_op`` otherwise);
the argument rules of the plane (``schema``, ``type_mismatch``,
``dangling_ref``); an undefined argument → the worst state with
``upstream`` and its ``cause``; the reasons of the operation; a non-finite
value → ``undefined/non_finite``; a failing implementation →
``error/internal`` and a diagnostic.

The scale ``S`` of a space scene is the diagonal of the box of its free
points (``point3.free``), at least ``1``; tolerances are those of the plane
times ``S`` (decide ``1e-10·S``, parity ``1e-9·S``, ``S²`` for an area,
``S³`` for a volume).
"""
from __future__ import annotations

import math

from ..document import NativeDocument, bound_producer, cyclic_operations, op_dependencies
from ..kernel.evaluate import Evaluated, _argument_status, _library_version, _order, undefined_state
from ..kernel.numeric import tolerances
from ..kernel.ops import OpContext
from ..kernel.values import (
    STATE_RANK,
    Detailed,
    Input,
    Undefined,
    _compare,
    defined_record,
    is_finite_value,
    state_record,
)
from ..registry import registry as plane_registry
from .document import as_space_document, is_newer_space_registry
from .ops import IMPLEMENTATIONS
from .registry import SPACE_REGISTRY_VERSION, space_registry

__all__ = ['evaluate', 'space_scale', 'check_space_inputs', 'compare_space_values', 'valid_space_input',
           'INPUT_DEFAULTS']

INPUT_DEFAULTS = {
    'pathParameter': {'kind': 'pathParameter', 'value': 0.5},
    'surfaceParameter': {'kind': 'surfaceParameter', 'value': [0.5, 0.5]},
}
_KIND_POWER = {'length': 1, 'area': 2, 'volume': 3, 'scalar': 0}


def _finite_numbers(value, n) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == n
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in value))


def valid_space_input(kind: str, value) -> bool:
    if not isinstance(value, dict) or value.get('kind') != kind:
        return False
    v = value.get('value')
    if kind == 'point3':
        return _finite_numbers(v, 3)
    if kind == 'surfaceParameter':
        return _finite_numbers(v, 2)
    if kind == 'pathParameter':
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    return False


def _free_elements(doc: NativeDocument, reg) -> dict:
    out = {}
    for el_id in doc.elements:
        producer = bound_producer(doc, el_id)
        if producer is None:
            continue
        record = reg.get(doc.operations[producer]['op'])
        if record is not None and record.get('free') is not None and \
                doc.elements[el_id]['producer']['slot'] == record['outputs'][0]['slot']:
            out[el_id] = record['free']['kind']
    return out


def check_space_inputs(doc: NativeDocument, inputs) -> dict:
    """Validate case ``inputs`` (overrides of free input values); raise ``ValueError``."""
    if inputs is None:
        return {}
    if not isinstance(inputs, dict):
        raise ValueError('inputs must be a mapping of element ID to input value')
    free = _free_elements(doc, space_registry())
    for el_id, value in inputs.items():
        if el_id not in doc.elements:
            raise ValueError(f'input for unknown element {el_id!r}')
        kind = free.get(el_id)
        if kind is None:
            raise ValueError(f'element {el_id!r} is not a free input')
        if not valid_space_input(kind, value):
            raise ValueError(f'input of {el_id!r} must be a {kind} input')
    return dict(inputs)


def space_scale(points) -> float:
    """``S``: the diagonal of the box of ``points`` (``(x, y, z)``), at least 1."""
    pts = list(points)
    if not pts:
        return 1.0
    d = math.sqrt(sum((max(p[i] for p in pts) - min(p[i] for p in pts)) ** 2 for i in range(3)))
    return max(1.0, d)


def compare_space_values(type_info: dict, expected, actual, scale: float, path: str = 'value') -> list:
    """Differences of two values of a space type: a field of kind ``length``
    compares within ``1e-9·S``, ``area`` — ``S²``, ``volume`` — ``S³``,
    ``scalar`` — ``1e-9``; a field without a kind compares exactly."""
    out: list = []
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        if expected != actual:
            out.append(f'{path}: expected {expected!r}, got {actual!r}')
        return out
    if set(expected) != set(actual):
        out.append(f'{path}: expected fields {sorted(expected)}, got {sorted(actual)}')
        return out
    kinds = type_info.get('value', {})
    base = tolerances(scale).parity_length / scale
    for key in sorted(expected):
        kind = kinds.get(key)
        if kind is None:
            if expected[key] != actual[key]:
                out.append(f'{path}.{key}: expected {expected[key]!r}, got {actual[key]!r}')
            continue
        _compare(expected[key], actual[key], base * scale ** _KIND_POWER[kind], f'{path}.{key}', out)
    return out


def evaluate(doc, *, inputs=None, _decisions=None) -> Evaluated:
    """Evaluate the space document ``doc``; ``inputs`` overrides input values
    of free elements. The result is :class:`~animageo.native.kernel.evaluate.Evaluated`
    with ``registry`` ``1.6`` (``animageo-evaluated/v1``)."""
    doc = as_space_document(doc)
    reg = space_registry()
    plane = plane_registry()
    overrides = check_space_inputs(doc, inputs)
    values_in = dict(doc.inputs)
    values_in.update(overrides)
    ops, elements = doc.operations, doc.elements

    free = _free_elements(doc, reg)
    points = [tuple(values_in[e]['value']) for e in sorted(free)
              if free[e] == 'point3' and valid_space_input('point3', values_in.get(e))]
    scale = space_scale(points)
    tol = tolerances(scale)

    states: dict = {}
    diagnostics: list = []
    computed: dict = {}
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
    newer = is_newer_space_registry(doc.registry_version)

    def settle(op_id, state, reason, cause=None):
        for el_id in bound.get(op_id, ()):
            states[el_id] = state_record(state, elements[el_id]['type'], reason, cause=cause)

    for op_id in _order(list(ops), deps, cyclic):
        op = ops[op_id]
        if op_id in cyclic:
            settle(op_id, 'error', 'cycle')
            continue
        record = reg.get(op['op'])
        if record is None:
            if plane.get(op['op']) is not None:
                settle(op_id, 'unsupported', 'space_unsupported')
            else:
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
            if not targets:
                continue
            free_input = values_in.get(targets[0]) or INPUT_DEFAULTS.get(record['free']['kind'])
            if not valid_space_input(record['free']['kind'], free_input):
                settle(op_id, 'error', 'schema')
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
        args = {}
        for slot, is_list, ids in resolved.refs:
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
        all_defined = True
        for el_id in bound.get(op_id, ()):
            slot = elements[el_id]['producer']['slot']
            value = result.get(slot)
            if isinstance(value, Detailed):
                value = value.value
            type_ = elements[el_id]['type']
            if isinstance(value, Undefined):
                states[el_id] = state_record(undefined_state(reg, value.reason), type_, value.reason,
                                             detail=value.detail)
                all_defined = False
            elif value is None:
                diagnostics.append({'code': 'internal', 'operationId': op_id, 'op': op['op'],
                                    'message': f'no value for slot {slot!r}'})
                states[el_id] = state_record('error', type_, 'internal')
                all_defined = False
            elif not is_finite_value(value):
                states[el_id] = state_record('undefined', type_, 'non_finite')
                all_defined = False
            else:
                states[el_id] = defined_record(type_, value)
        if all_defined:
            computed[op_id] = (op['op'], args, result)

    for el_id in elements:
        if el_id not in states:
            states[el_id] = state_record('error', elements[el_id]['type'], 'schema')

    return Evaluated(
        document_id=doc.document_id,
        scale=scale,
        elements={el_id: states[el_id] for el_id in sorted(states)},
        diagnostics=diagnostics,
        tolerances=tol,
        library=_library_version(),
        registry=SPACE_REGISTRY_VERSION,
        computed=computed,
    )
