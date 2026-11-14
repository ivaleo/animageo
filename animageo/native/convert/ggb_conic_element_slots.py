"""Injective saved-value binding for fixed conic parts and repeated lines."""
from __future__ import annotations

import copy
from itertools import permutations

from .values import compare, native_report_value


def resolve_slots(builder, op_id, info, scale):
    from .construction import _drop_operation, _expected
    from ..kernel.evaluate import evaluate

    outputs, slots, kind = info['outputs'], info['slots'], info['type']
    expected = [_expected(builder, builder.records[name]) for name, _ in outputs]
    if kind == 'line':
        finite = [v for v in expected if v is not None and v.get('value') is not None]
        if any(compare(a, b, scale)[0] == 'passed' for i, a in enumerate(finite) for b in finite[:i]):
            _drop_operation(builder, op_id, 'unsupported_signature', 'saved line multiplicity exceeds distinct conic slots')
            return
    probe = copy.deepcopy(builder.doc)
    op = probe['operations'][op_id]
    ids = {s: f'conic-element-probe-{i}' for i, s in enumerate(slots)}
    op['outputs'] = [{'slot': s, 'elementId': eid} for s, eid in ids.items()]
    for s, eid in ids.items():
        probe['elements'][eid] = {'id': eid, 'type': kind, 'displayName': '',
                                   'producer': {'operationId': op_id, 'slot': s}}
    ev = evaluate(probe)
    values = {s: native_report_value(kind, ev.elements.get(eid, {}).get('value'))
              if ev.elements.get(eid, {}).get('state') == 'defined' else None for s, eid in ids.items()}

    def score(assignment):
        finite, undefined, ordinal = 0, 0, 0
        for exp, (name, _), slot in zip(expected, outputs, assignment):
            if exp is not None and compare(exp, values[slot], scale)[0] == 'passed':
                if exp.get('value') is None:
                    undefined += 1
                else:
                    finite += 1
            ordinal += slots.index(slot) == info['ordinals'][name]
        return finite, undefined, ordinal

    if not info['repeated']:
        # Fixed anatomy has at most four outputs; coincident circle foci may
        # match both slots, and the original ordinal settles that tie.
        selected = max(permutations(slots, len(outputs)), key=score)
    else:
        # Conic line sets have at most two branches. Explicit higher ordinals
        # stay absent and cannot steal a finite branch or hide a mismatch.
        fixed = {i: slots[info['ordinals'][name]] for i, (name, _) in enumerate(outputs)
                 if info['ordinals'][name] >= 2}
        active = [i for i in range(len(outputs)) if i not in fixed]

        def assignment(values):
            choices = dict(zip(active, values))
            return [fixed[i] if i in fixed else choices[i] for i in range(len(outputs))]

        selected = max((assignment(a) for a in permutations(slots[:2], len(active))), key=score)
    by_id = {builder.element_of[name]: s for (name, _), s in zip(outputs, selected)}
    for out in builder.doc['operations'][op_id]['outputs']:
        out['slot'] = by_id[out['elementId']]
        builder.doc['elements'][out['elementId']]['producer']['slot'] = out['slot']
