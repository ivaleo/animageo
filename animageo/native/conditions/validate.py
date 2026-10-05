"""``validate`` codes of the conditions, the suppressed marks and the origin
of automatic marks (plan L3 §3.1)."""
from __future__ import annotations

from ..document import MARK_KINDS, Issue, _pointer, bound_producer
from .statements import statement_problems

MAX_CONSTRAINTS = 2          # constraints on one point (two loci meet in it)


def condition_list(doc) -> list:
    raw = doc.data.get('conditions')
    return [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []


def condition_issues(doc) -> list:
    """Errors ``condition_unknown_element``, ``condition_unknown_operation``,
    ``condition_receiver_mismatch``, ``condition_too_many``,
    ``condition_bad_statement``, ``condition_duplicate_id``; warnings
    ``mark_origin_unknown``, ``suppressed_mark_unknown_kind``."""
    issues = []
    conditions = condition_list(doc)
    seen = set()
    per_receiver: dict = {}
    for i, cond in enumerate(conditions):
        path = f'/conditions/{i}'
        cid = cond.get('id')
        if cid in seen:
            issues.append(Issue('condition_duplicate_id', path + '/id', f'condition {cid!r} is defined twice'))
        seen.add(cid)
        if isinstance(cond.get('statement'), dict):
            for code, ppath, message, el_id in statement_problems(cond['statement'], doc, path + '/statement'):
                issues.append(Issue(code, ppath, message, elementId=el_id))
        for k, op_id in enumerate(cond.get('operationIds') or ()):
            if isinstance(op_id, str) and op_id not in doc.operations:
                issues.append(Issue('condition_unknown_operation', f'{path}/operationIds/{k}',
                                    f'operation {op_id!r} does not exist', operationId=op_id))
        receiver = cond.get('receiver')
        if cond.get('mode') == 'construct' and isinstance(receiver, str):
            if receiver not in doc.elements:
                issues.append(Issue('condition_unknown_element', path + '/receiver',
                                    f'element {receiver!r} does not exist', elementId=receiver))
            else:
                producer = bound_producer(doc, receiver)
                if producer is None or producer not in (cond.get('operationIds') or ()):
                    issues.append(Issue('condition_receiver_mismatch', path + '/receiver',
                                        f'the operation of receiver {receiver!r} is not in operationIds',
                                        elementId=receiver))
                per_receiver.setdefault(receiver, []).append(i)
    for receiver, indexes in sorted(per_receiver.items()):
        if len(indexes) > MAX_CONSTRAINTS:
            for i in indexes[MAX_CONSTRAINTS:]:
                issues.append(Issue('condition_too_many', f'/conditions/{i}/receiver',
                                    f'point {receiver!r} has more than {MAX_CONSTRAINTS} conditions',
                                    elementId=receiver))
    sources = set(doc.operations) | {c.get('id') for c in conditions}
    for el_id in sorted(doc.elements):
        origin = doc.elements[el_id].get('origin')
        if not (isinstance(origin, dict) and origin.get('kind') == 'auto'):
            continue                 # the origin of an automatic mark only; other origins belong to the web
        if not isinstance(origin.get('source'), str) or origin['source'] not in sources:
            issues.append(Issue('mark_origin_unknown', '/elements' + _pointer(el_id) + '/origin/source',
                                f"source {origin.get('source')!r} is neither an operation nor a condition",
                                elementId=el_id, severity='warning'))
    marks = doc.data.get('suppressedMarks')
    for i, mark in enumerate(marks if isinstance(marks, list) else ()):
        if isinstance(mark, dict) and isinstance(mark.get('kind'), str) and mark['kind'] not in MARK_KINDS:
            issues.append(Issue('suppressed_mark_unknown_kind', f'/suppressedMarks/{i}/kind',
                                f"kind {mark['kind']!r} is not one of {', '.join(MARK_KINDS)}",
                                severity='warning'))
    return issues
