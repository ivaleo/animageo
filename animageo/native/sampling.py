"""«Верно в общем случае» (plan L3 §3.4): a statement, a condition or a mark
checked at the current position and in ``trials`` random positions of the
free inputs. The generator is SplitMix64 with the seed of the check, so the
web reproduces every trial bit for bit (docs/native/conditions.md §4).

1. Level 1 — the current position. ``failed`` ends the check (``failed``,
   counterexample trial ``0``).
2. Seed: ``int(sha256(documentId + ":" + checkId)[:16 hex], 16)`` unless
   ``seed`` is given; ``uniform() = (next() >> 11)·2⁻⁵³``.
3. Trial ``k = 1 … trials``: the free inputs by ascending element ID;
   ``point`` — ``p + r_k·(ρ cos φ, ρ sin φ)``, ``ρ = √uniform()``,
   ``φ = 2π·uniform()``, ``r_k = 0.5·S·k/trials``, clamped to
   ``viewDefaults.bounds``; ``pathParameter`` — uniform over the range of
   the path, a line or a ray ``t + (2·uniform() − 1)·S/|v|`` (a ray not below
   ``0``); ``number`` — uniform in ``[min, max]``, without both
   ``v·(1 + uniform() − 0.5)``; ``angle`` — ``2π·uniform()``. An input
   without a value draws nothing.
4. Result: ``failed`` when a trial fails (the counterexample is the first:
   its number and inputs); ``inconclusive`` when ``undefined +
   inconclusive > trials / 5`` (10 of 50); otherwise ``passed`` — a test, not
   a proof.
"""
from __future__ import annotations

import hashlib
import math

from .conditions.statements import mark_statements, measure_statement
from .conditions.validate import condition_list
from .document import as_document
from .kernel import relations as rel

__all__ = ['seed_of', 'trial_inputs', 'check_general', 'targets_of']

TWO_PI = 2 * math.pi
RADIUS = 0.5                 # of S at the last trial
INCONCLUSIVE_SHARE = 0.2     # more than this share of unmeasured trials → inconclusive


def seed_of(document_id: str, check_id: str) -> int:
    digest = hashlib.sha256(f'{document_id}:{check_id}'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def trial_inputs(specs, values_in, rng, k, trials, scale, bounds) -> dict:
    """Free input values of trial ``k`` (1-based); draws from ``rng`` in
    ``specs`` order."""
    out = {}
    xmin, ymin, xmax, ymax = bounds
    radius = RADIUS * scale * k / trials
    for el_id, kind, info in specs:
        current = values_in.get(el_id)
        if current is None:
            continue
        if kind == 'point':
            x, y = current['value']
            rho = math.sqrt(rng.random())
            phi = TWO_PI * rng.random()
            px = _clamp(x + radius * rho * math.cos(phi), xmin, xmax)
            py = _clamp(y + radius * rho * math.sin(phi), ymin, ymax)
            out[el_id] = {'kind': 'point', 'value': [px, py]}
        elif kind == 'pathParameter':
            u = rng.random()
            lo, hi = info.get('lo'), info.get('hi')
            if lo is not None and hi is not None:
                t = lo + u * (hi - lo)
            else:
                unit = info.get('unit') or 1.0
                t = current['value'] + (2 * u - 1) * scale / unit
                if lo is not None and t < lo:
                    t = lo
            value = {'kind': 'pathParameter', 'value': t}
            if 'branch' in current:
                value['branch'] = current['branch']
            out[el_id] = value
        elif kind == 'number':
            u = rng.random()
            if 'min' in info and 'max' in info and info['max'] >= info['min']:
                v = info['min'] + u * (info['max'] - info['min'])
            else:
                v = current['value'] * (1 + u - 0.5)
            out[el_id] = {'kind': 'number', 'value': v}
        elif kind == 'angle':
            out[el_id] = {'kind': 'angle', 'value': TWO_PI * rng.random()}
    return out


def targets_of(doc) -> list:
    """``[(checkId, [statement…])]``: every condition (by its ID) and every
    mark operation (by its operation ID), in that order."""
    out = []
    for cond in condition_list(doc):
        if isinstance(cond.get('id'), str) and isinstance(cond.get('statement'), dict):
            out.append((cond['id'], [cond['statement']]))
    for op_id in sorted(doc.operations):
        items = mark_statements(doc, op_id)
        if items:
            out.append((op_id, items))
    return out


def _resolve(doc, target):
    if isinstance(target, dict):
        return '', [target]
    if isinstance(target, tuple) and len(target) == 2 and isinstance(target[1], dict):
        return target[0], [target[1]]
    if isinstance(target, str):
        for check_id, items in targets_of(doc):
            if check_id == target:
                return check_id, items
        raise ValueError(f'{target!r} is neither a condition nor a mark operation')
    raise ValueError('a target is a statement, (checkId, statement), a condition ID or a mark operation ID')


_RANK = {'unsupported': 4, 'failed': 3, 'inconclusive': 2, 'undefined': 1, 'passed': 0}


def _measure(doc, items, ev):
    """``(status, error)`` of all ``items``: the worst status, the largest error;
    ``undefined`` for an element that is not defined."""
    worst, error = 'passed', None
    for statement in items:
        status, err, detail = measure_statement(doc, statement, ev)
        if status == 'inconclusive' and detail and detail.get('reason') == 'undefined':
            status = 'undefined'
        if _RANK[status] > _RANK[worst]:
            worst = status
        if err is not None:
            error = err if error is None else max(error, err)
    return worst, error


def _one(doc, check_id, items, *, seed, trials, inputs):
    from .kernel.evaluate import check_inputs, evaluate
    from .kernel.numeric import default_bounds
    base = evaluate(doc, inputs=inputs)
    status0, error0 = _measure(doc, items, base)
    result = {'status': None, 'trials': 0, 'passed': 0, 'failed': 0, 'undefined': 0, 'inconclusive': 0,
              'counterexample': None, 'error': error0, 'seed': None}
    if status0 in ('failed', 'unsupported'):
        result['status'] = status0
        if status0 == 'failed':
            result['counterexample'] = {'trial': 0, 'inputs': {}}
        return result
    material = seed if seed is not None else seed_of(str(doc.document_id), check_id)
    result['seed'] = material
    rng = rel.SplitMix64(material)
    values_in = dict(doc.inputs)
    values_in.update(check_inputs(doc, inputs))
    specs = rel._free_specs(doc, base, values_in)
    bounds = doc.bounds or default_bounds()
    scale = base.scale
    for k in range(1, trials + 1):
        overrides = trial_inputs(specs, values_in, rng, k, trials, scale, bounds)
        merged = dict(inputs or {})
        merged.update(overrides)
        try:
            ev = evaluate(doc, inputs=merged)
            status, _err = _measure(doc, items, ev)
        except ValueError:
            status = 'undefined'
        status = 'inconclusive' if status == 'unsupported' else status
        result[status] += 1
        if status == 'failed' and result['counterexample'] is None:
            result['counterexample'] = {'trial': k, 'inputs': overrides}
    result['trials'] = trials
    if result['failed']:
        result['status'] = 'failed'
    elif result['undefined'] + result['inconclusive'] > INCONCLUSIVE_SHARE * trials:
        result['status'] = 'inconclusive'
    else:
        result['status'] = 'passed'
    return result


def check_general(doc, targets=None, *, seed=None, trials: int = 50, inputs=None) -> dict:
    """``{checkId: {status, trials, passed, failed, undefined, inconclusive,
    counterexample: {trial, inputs} | null, error, seed}}``.

    ``targets``: ``None`` — every condition and mark of the document; or a
    list of condition IDs, mark operation IDs, statements (``checkId`` ``""``)
    and ``(checkId, statement)`` pairs. ``error`` is the error at the current
    position; ``seed`` the seed of the trials (``None`` when level 1 decided).
    """
    doc = as_document(doc)
    trials = int(trials)
    if trials < 0:
        raise ValueError('trials must be >= 0')
    if targets is None:
        resolved = targets_of(doc)
    else:
        resolved = [_resolve(doc, t) for t in (targets if isinstance(targets, list) else [targets])]
    return {check_id: _one(doc, check_id, items, seed=seed, trials=trials, inputs=inputs)
            for check_id, items in resolved}
