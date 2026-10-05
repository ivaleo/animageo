"""Carrying out the condition requests of :func:`parse_commands` (plan L3
§4.2, §4.4). Computational: it evaluates the document, so the web runs it in
the sandbox (the browser — in its TypeScript copy).

::

    result = parse_commands(text, base=doc)
    applied = apply_condition_requests(result.document, result.conditionRequests)
    applied.document, applied.results      # [{line, kind, conditionId, refusal}]
"""
from __future__ import annotations

import copy
from typing import NamedTuple

from ..document import NativeDocument, as_document, bound_producer, iter_refs

__all__ = ['RequestsResult', 'apply_condition_requests']


class RequestsResult(NamedTuple):
    """``document`` — after the requests; ``results`` — ``[{line, kind,
    conditionId, refusal}]`` in request order, ``refusal`` —
    ``{code, message, options}`` or ``None`` (a refused request changes
    nothing)."""

    document: object
    results: list


def _refusal(refusal):
    if refusal is None:
        return None
    return {'code': refusal.code, 'message': refusal.message, 'options': list(refusal.options)}


def _move(doc, request):
    """Re-project the receiver onto its place at ``point`` (a receiver on a
    path; the meeting of two places has no freedom)."""
    from ..conditions.apply import _project
    from ..kernel.evaluate import evaluate
    receiver = request['receiver']
    op_id = bound_producer(doc, receiver)
    op = doc.operations.get(op_id) if op_id else None
    if op is None or op.get('op') != 'point.on_path':
        return doc
    path = next(iter(iter_refs((op.get('args') or {}).get('path') or {})), None)
    if path is None:
        return doc
    t = _project(doc, evaluate(doc), path, tuple(request['point']))
    if t is None:
        return doc
    data = copy.deepcopy(doc.data)
    data.setdefault('inputs', {})[receiver] = {'kind': 'pathParameter', 'value': t}
    return NativeDocument(data)


def apply_condition_requests(doc, requests, *, id_factory=None, marks: bool = True) -> RequestsResult:
    """Carry out ``requests`` in order: ``apply`` — :func:`apply_condition`
    (``source: "command"``, the request's receiver); ``release`` —
    :func:`release_condition` at the current position; ``replace`` — release,
    then apply (both or neither); ``move`` — the receiver's parameter becomes
    the projection of ``point`` onto its place."""
    from ..conditions.apply import apply_condition, release_condition
    from ..kernel.evaluate import evaluate
    doc = as_document(doc)
    results = []
    for request in requests:
        kind = request['kind']
        entry = {'line': request.get('line'), 'kind': kind, 'conditionId': request.get('conditionId'),
                 'refusal': None}
        if kind == 'move':
            doc = _move(doc, request)
        elif kind == 'release':
            result = release_condition(doc, request['conditionId'], ev=evaluate(doc))
            if result.refusal is None:
                doc = result.document
            entry['refusal'] = _refusal(result.refusal)
        elif kind in ('apply', 'replace'):
            start = doc
            if kind == 'replace':
                released = release_condition(doc, request['conditionId'], ev=evaluate(doc))
                if released.refusal is not None:
                    entry['refusal'] = _refusal(released.refusal)
                    results.append(entry)
                    continue
                doc = released.document
            result = apply_condition(doc, {'statement': request['statement'], 'mode': 'construct',
                                           'source': 'command'},
                                     receiver=request.get('receiver'), id_factory=id_factory, marks=marks)
            if result.refusal is not None:
                doc = start
                entry['refusal'] = _refusal(result.refusal)
            else:
                doc = result.document
                entry['conditionId'] = result.condition['id']
        else:
            raise ValueError(f'unknown request kind {kind!r}')
        results.append(entry)
    return RequestsResult(doc, results)
