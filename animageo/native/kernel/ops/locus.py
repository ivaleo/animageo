"""Registry 1.5: ``locus.of_point`` — the locus of a point traced while a mover
runs over its range (docs/native/ops/locus.of_point.md).

1. The mover is the point of ``point.on_path`` or the number of
   ``number.free`` with both ``min`` and ``max``; anything else is
   ``unsupported/unsupported_signature`` (a free point has no one-dimensional
   range).
2. The trace must depend on the mover (its producer is a dependent of the
   mover's producer), else ``undefined/not_dependent``.
3. The range comes from the definition, not from the mover's position:
   segment, arc ``[0, 1]``; polyline ``[0, n − 1]``; circle ``[0, 2π)``,
   polygon ``[0, n)``, sector ``[0, 3)`` — closed; line and ray — the
   parameters (frame of the producer) where the carrier enters and leaves
   the window ``B4`` (``viewDefaults.bounds`` scaled 4 times about its
   centre), a ray from ``0`` at least; a number ``[min, max]``. A window of
   no length (``(t1 − t0)·|v| ≤ tol.decide`` for a line or a ray,
   ``t1 − t0 ≤ tol.decide`` scalar for a number) is ``undefined/empty_range``.
4. ``N = 256`` samples: open ``t_k = t0 + (k·(t1 − t0))/(N − 1)``, closed
   ``t_k = t0 + (k·(t1 − t0))/N``, ``k = 0 … N − 1``.
5. At each sample the input of the mover is replaced by ``t_k`` and only the
   operations that depend on the mover and that the trace depends on are
   evaluated again (the rest of the graph keeps its values); ``points[k]`` is
   the trace ``[x, y]`` or ``null``. The document and the mover input do not
   change.
"""
from __future__ import annotations

import math
from collections import ChainMap

from ..values import Detailed, Undefined, defined_record, is_finite_value, state_record
from . import op

SAMPLES = 256
TWO_PI = 2 * math.pi
WINDOW_FACTOR = 4.0


def _ref_id(arg):
    if isinstance(arg, dict) and arg.get('kind') == 'ref':
        return arg.get('elementId')
    return None


def _downstream_ops(scope, start: str) -> set:
    users: dict = {}
    for op_id, needs in scope.deps.items():
        for dep in needs:
            users.setdefault(dep, set()).add(op_id)
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for user in users.get(cur, ()):
            if user not in seen:
                seen.add(user)
                stack.append(user)
    return seen


def _upstream_ops(scope, start: str) -> set:
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for dep in scope.deps.get(cur, ()):
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return seen


def window(bounds) -> tuple:
    """The window ``B4``: ``bounds`` scaled ``WINDOW_FACTOR`` times about its centre."""
    xmin, ymin, xmax, ymax = (float(v) for v in bounds)
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    hw = (xmax - xmin) * WINDOW_FACTOR / 2
    hh = (ymax - ymin) * WINDOW_FACTOR / 2
    return cx - hw, cy - hh, cx + hw, cy + hh


def clip_affine(origin, vector, box, lo=None):
    """``(t0, t1)`` where ``origin + t·vector`` lies in ``box`` (Liang–Barsky), ``t ≥ lo``
    when ``lo`` is given; ``None`` when the line misses the box."""
    t0, t1 = -math.inf, math.inf
    for o, v, bmin, bmax in ((origin[0], vector[0], box[0], box[2]), (origin[1], vector[1], box[1], box[3])):
        if v == 0:
            if o < bmin or o > bmax:
                return None
            continue
        a = (bmin - o) / v
        b = (bmax - o) / v
        if a > b:
            a, b = b, a
        t0 = max(t0, a)
        t1 = min(t1, b)
    if lo is not None:
        t0 = max(t0, lo)
    if not (math.isfinite(t0) and math.isfinite(t1)):
        return None
    return t0, t1


def sample_parameters(t0: float, t1: float, closed: bool, n: int = SAMPLES) -> list:
    span = t1 - t0
    if closed:
        return [t0 + (k * span) / n for k in range(n)]
    return [t0 + (k * span) / (n - 1) for k in range(n)]


def _path_range(scope, mover_op, ctx):
    """``(t0, t1, closed)`` of a ``point.on_path`` mover, or :class:`Undefined`."""
    from ..evaluate import _path_frame
    from ..numeric import default_bounds
    doc = scope.doc
    path_id = _ref_id(mover_op['args'].get('path'))
    type_ = doc.elements[path_id]['type']
    value = scope.states[path_id]['value']
    if type_ in ('segment', 'arc'):
        return 0.0, 1.0, False
    if type_ == 'polyline':
        return 0.0, float(len(value['vertices']) - 1), False
    if type_ == 'circle':
        return 0.0, TWO_PI, True
    if type_ == 'polygon':
        return 0.0, float(len(value['vertices'])), True
    if type_ == 'sector':
        return 0.0, 3.0, True
    if type_ in ('line', 'ray'):
        f = _path_frame(path_id, doc.elements, doc.operations, scope.states)
        box = window(doc.bounds or default_bounds())
        clipped = clip_affine(f.origin, f.vector, box, 0.0 if type_ == 'ray' else None)
        size = math.hypot(f.vector[0], f.vector[1])
        tol = ctx.tol.decide_length
        if clipped is None:
            return Undefined('empty_range')
        t0, t1 = clipped
        ctx.decide('empty_range', (t1 - t0) * size, tol)
        if (t1 - t0) * size <= tol:
            return Undefined('empty_range')
        return t0, t1, False
    return Undefined('unsupported_signature')


def _number_range(mover_op, ctx):
    lo = mover_op['args'].get('min')
    hi = mover_op['args'].get('max')
    if not (isinstance(lo, dict) and lo.get('kind') == 'number' and isinstance(hi, dict)
            and hi.get('kind') == 'number'):
        return Undefined('unsupported_signature')
    t0, t1 = float(lo['value']), float(hi['value'])
    tol = ctx.tol.decide_scalar
    ctx.decide('empty_range', t1 - t0, tol)
    if t1 - t0 <= tol:
        return Undefined('empty_range')
    return t0, t1, False


class _Subgraph:
    """The operations between the mover and the trace, ready to run per sample."""

    def __init__(self, scope, mover_op_id: str, trace_op_id: str):
        from ...registry import registry
        from ..evaluate import _argument_status
        doc = scope.doc
        reg = registry()
        inside = _downstream_ops(scope, mover_op_id) & _upstream_ops(scope, trace_op_id)
        self.scope = scope
        self.mover_op_id = mover_op_id
        self.steps = []
        for op_id in scope.order:
            if op_id not in inside:
                continue
            op = doc.operations[op_id]
            record = reg.get(op['op'])
            resolved = _argument_status(op, record, doc, reg) if record is not None else ('error', 'schema')
            self.steps.append((op_id, op, record, resolved))

    def run(self, mover_kind: str, t: float, trace_id: str):
        """The trace value at mover parameter ``t`` (``None`` when not defined)."""
        from ...registry import free_slot
        from ..evaluate import INPUT_DEFAULTS, build_args, valid_input
        from . import IMPLEMENTATIONS, OpContext
        scope = self.scope
        doc = scope.doc
        elements = doc.elements
        local: dict = {}
        states = ChainMap(local, scope.states)
        for op_id, op, record, resolved in self.steps:
            outs = scope.bound.get(op_id, ())
            if isinstance(resolved, tuple):
                for el_id in outs:
                    local[el_id] = state_record(resolved[0], elements[el_id]['type'], resolved[1])
                continue
            free_input = None
            if record.get('free') is not None:
                holders = [e for e in outs if elements[e]['producer']['slot'] == free_slot(record)]
                if not holders:         # no bound output: nothing to compute (as in evaluate)
                    continue
                if op_id == self.mover_op_id:
                    free_input = {'kind': mover_kind, 'value': t}
                else:
                    free_input = scope.values_in.get(holders[0])
                    if free_input is None:
                        free_input = INPUT_DEFAULTS.get(record['free']['kind'])
                if not valid_input(record['free']['kind'], free_input):
                    for el_id in outs:
                        local[el_id] = state_record('error', elements[el_id]['type'], 'schema')
                    continue
            if any(states[ref]['state'] != 'defined' for _s, _l, ids in resolved.refs for ref in ids):
                for el_id in outs:
                    local[el_id] = state_record('undefined', elements[el_id]['type'], 'upstream')
                continue
            args = build_args(record, resolved, elements, doc.operations, states)
            ctx = OpContext(scope.tol, input=free_input, operation_id=op_id, decisions=scope.decisions)
            try:
                result = IMPLEMENTATIONS[op['op']](args, ctx)
            except Exception:  # a sample with a failing operation is simply not drawn
                result = {}
            for el_id in outs:
                value = result.get(elements[el_id]['producer']['slot'])
                if isinstance(value, Detailed):
                    value = value.value
                if value is None or isinstance(value, Undefined) or not is_finite_value(value):
                    local[el_id] = state_record('undefined', elements[el_id]['type'], 'non_finite')
                else:
                    local[el_id] = defined_record(elements[el_id]['type'], value)
        record = states[trace_id]
        if record['state'] != 'defined':
            return None
        value = record['value']
        return [value['x'], value['y']]


def mover_signature(doc, mover_id: str):
    """``(mover op id, input kind)`` of a usable mover, or ``None``: the point of
    ``point.on_path`` or the number of ``number.free``."""
    el = doc.elements[mover_id]
    op_id = el['producer']['operationId']
    name = doc.operations[op_id]['op']
    if el['type'] == 'point' and name == 'point.on_path':
        return op_id, 'pathParameter'
    if el['type'] == 'number' and name == 'number.free':
        return op_id, 'number'
    return None


@op('locus.of_point')
def of_point(args, ctx):
    scope = ctx.scope
    if scope is None:      # outside an evaluation (no graph): nothing to sample
        return {'locus': Undefined('unsupported_signature')}
    doc = scope.doc
    ids = {slot: refs[0] for slot, _is_list, refs in scope.resolved.refs}
    trace_id, mover_id = ids['trace'], ids['mover']
    signature = mover_signature(doc, mover_id)
    if signature is None:
        return {'locus': Undefined('unsupported_signature')}
    mover_op_id, kind = signature
    mover_op = doc.operations[mover_op_id]
    if kind == 'number' and not all(isinstance(mover_op['args'].get(k), dict)
                                    and mover_op['args'][k].get('kind') == 'number' for k in ('min', 'max')):
        return {'locus': Undefined('unsupported_signature')}
    trace_op_id = doc.elements[trace_id]['producer']['operationId']
    if trace_op_id not in _downstream_ops(scope, mover_op_id):
        return {'locus': Undefined('not_dependent')}
    rng = _path_range(scope, mover_op, ctx) if kind == 'pathParameter' else _number_range(mover_op, ctx)
    if isinstance(rng, Undefined):
        return {'locus': rng}
    t0, t1, closed = rng
    sub = _Subgraph(scope, mover_op_id, trace_op_id)
    points = [sub.run(kind, t, trace_id) for t in sample_parameters(t0, t1, closed)]
    args['$locus'] = (doc, mover_id, kind, scope.values_in)    # for the check on_trace (full evaluations)
    args['$trace'] = trace_id
    return {'locus': {'points': points, 'range': [t0, t1], 'closed': closed}}
