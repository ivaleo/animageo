"""How much of a corpus of ``.ggb`` files the import carries over (``import-audit``).

Every file is imported by :func:`~animageo.native.convert.from_ggb` (the IDs
come from the sha256 of the file, as with ``from-ggb`` without
``--namespace``) and counted by the categories of its report, weighted by
how often the file occurs (``weights``: ``{sha256: count}``, 1 when absent):

- ``editable``, ``picture``, ``differs`` — the objects of these categories;
  ``value_unchecked`` — the part of ``differs`` whose value is not compared;
- ``lost`` — ``unsupported`` + ``closure``;
- ``full`` — a file with a document and without lost, picture or differing
  objects and without dropped kinds; a refused file counts in ``files`` only.

``web_registry`` adds the count of a consumer that knows the registry only
up to that version (``"1.7"``): an operation whose ``since`` — or the
``familySince`` of a type in one of its family slots — is newer is not
recomputed there. An editable or differing object it produces, or that is
built on a hidden helper it produces, is a ``picture``
(``web_capability_missing``); the editable and differing objects that depend
on such a picture (``depends_on``, any chain) are ``closure``.

``python -m animageo.native import-audit <paths…> [--weights FILE] [--json OUT] [--web-registry X]``
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from .report import CATEGORIES

__all__ = ['AUDIT_FORMAT', 'AUDIT_VERSION', 'audit_files', 'audit_file', 'web_categories', 'totals', 'audit',
           'audit_line', 'registry_version']

AUDIT_FORMAT = 'animageo.import_audit'
AUDIT_VERSION = 1
COUNTS = ('editable', 'picture', 'differs', 'value_unchecked', 'unsupported', 'closure')


def registry_version(text) -> tuple:
    """``(major, minor)`` of a registry version ``"1.7"``; ``ValueError`` otherwise."""
    from ..registry import _version_tuple
    version = _version_tuple(text)
    if version is None or version < (1, 0):
        raise ValueError(f'not a registry version: {text!r}')
    return version


def audit_files(paths) -> list:
    """The files of ``paths`` (a ``.ggb`` file as given, a directory — its
    ``*.ggb`` recursively, sorted), in the order given; ``FileNotFoundError``
    for a path that does not exist."""
    from .corpus import corpus_files
    out = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            out.extend(corpus_files(path))
        elif path.is_file():
            out.append(path)
        else:
            raise FileNotFoundError(str(path))
    return out


def _counts(elements, document, dropped) -> dict:
    out = {c: sum(1 for e in elements if e['category'] == c) for c in CATEGORIES}
    out['value_unchecked'] = sum(1 for e in elements
                                 if e['category'] == 'differs' and e.get('reason') == 'value_unchecked')
    out['lost'] = out['unsupported'] + out['closure']
    out['full'] = bool(document is not None and not out['lost'] and not out['picture'] and not out['differs']
                       and not dropped)
    return out


def _required(document) -> dict:
    """``{operationId: (major, minor)}``: the registry each operation needs
    (its ``since`` and the ``familySince`` of the types in its family slots)."""
    from ..document import _needs, _version_tuple
    from ..registry import registry
    reg = registry()
    elements = document.get('elements') or {}
    out = {}
    for op_id, op in (document.get('operations') or {}).items():
        record = reg.get(op.get('op'))
        if record is None:
            continue
        versions = [_version_tuple(v) for v, _slot, _el in _needs(reg, record, op.get('args') or {}, elements)]
        out[op_id] = max([v for v in versions if v is not None], default=(1, 0))
    return out


def _down(document, seeds) -> set:
    """``seeds`` and the elements built on them in the graph of ``document``."""
    from ..document import iter_refs
    operations = document.get('operations') or {}
    users: dict = {}
    for op_id, op in operations.items():
        for arg in (op.get('args') or {}).values():
            for ref in iter_refs(arg):
                users.setdefault(ref, set()).add(op_id)
    out = set(seeds)
    stack = list(seeds)
    while stack:
        for op_id in users.get(stack.pop(), ()):
            for o in operations[op_id].get('outputs') or ():
                child = o.get('elementId')
                if child and child not in out:
                    out.add(child)
                    stack.append(child)
    return out


def web_categories(report: dict, document, version) -> list:
    """``[(ggb_name, category, reason)]`` of the report for a consumer of
    registry ``version`` (``"1.7"`` or ``(1, 7)``), in the order of the report."""
    limit = registry_version(version) if isinstance(version, str) else tuple(version)
    elements = report['elements']
    rows = {e['ggb_name']: [e['category'], e.get('reason')] for e in elements}
    if document is None:
        return [(e['ggb_name'], *rows[e['ggb_name']]) for e in elements]
    newer = {op_id for op_id, needed in _required(document).items() if needed > limit}
    produced = {}
    for op_id in newer:
        for o in document['operations'][op_id].get('outputs') or ():
            if o.get('elementId'):
                produced[o['elementId']] = op_id
    owned = {nid for e in elements for nid in e.get('native_ids') or ()}
    behind = _down(document, {eid for eid in produced if eid not in owned})
    roots = set()
    for e in elements:
        if rows[e['ggb_name']][0] in ('editable', 'differs') and any(
                nid in produced or nid in behind for nid in e.get('native_ids') or ()):
            rows[e['ggb_name']] = ['picture', 'web_capability_missing']
            roots.add(e['ggb_name'])
    dependents: dict = {}
    for e in elements:
        for dep in e.get('depends_on') or ():
            dependents.setdefault(dep, []).append(e['ggb_name'])
    stack, seen = list(roots), set(roots)
    while stack:
        for child in dependents.get(stack.pop(), ()):
            if child in seen:
                continue
            seen.add(child)
            stack.append(child)
            if rows[child][0] in ('editable', 'differs'):
                rows[child] = ['closure', 'depends_on_unsupported']
    return [(e['ggb_name'], *rows[e['ggb_name']]) for e in elements]


def audit_file(path, *, weight: int = 1, web_registry=None) -> dict:
    """The row of one file: ``path``, ``sha256``, ``weight``, ``outcome``
    (``report`` | ``refused`` with ``code`` | ``error`` with ``code`` — an
    exception of the import), ``document``, the counts of :data:`COUNTS`
    with ``lost`` and ``full``, ``dropped``, ``elements``
    (``[name, type, category, reason, command, signature]``) and, with
    ``web_registry``, ``web`` (the counts after the filter and ``changed``:
    ``[name, category, reason]`` of the objects whose category it changed)."""
    from . import ImportRefused, from_ggb
    data = Path(path).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    row = {'path': str(path), 'sha256': sha, 'weight': int(weight)}
    try:
        document, report = from_ggb(data, id_namespace=uuid.UUID(sha[:32]), name=Path(path).name)
    except ImportRefused as exc:
        return {**row, 'outcome': 'refused', 'code': exc.code}
    except Exception as exc:          # an import that fails is counted and reported, never hidden
        return {**row, 'outcome': 'error', 'code': type(exc).__name__, 'detail': str(exc)[:300]}
    dropped = sorted({d['kind'] for d in report['dropped']})
    elements = report['elements']
    row.update(outcome='report', document=document is not None, dropped=dropped,
               **_counts(elements, document, dropped))
    row['elements'] = [[e['ggb_name'], e['ggb_type'], e['category'], e.get('reason'), e.get('command'),
                        e.get('signature')] for e in elements]
    if web_registry is not None:
        web = web_categories(report, document, web_registry)
        filtered = [{**e, 'category': c, 'reason': r} for e, (_n, c, r) in zip(elements, web)]
        row['web'] = {**_counts(filtered, document, dropped),
                      'changed': [[n, c, r] for e, (n, c, r) in zip(elements, web) if c != e['category']]}
    return row


def totals(rows, key: str | None = None) -> dict:
    """Weighted totals of the rows (``key="web"`` — of their web counts):
    ``files``, ``full``, ``objects``, the counts of :data:`COUNTS`, ``lost``,
    ``refused`` and ``errors``."""
    out = {'files': 0, 'full': 0, 'objects': 0, **{c: 0 for c in COUNTS}, 'lost': 0, 'refused': 0, 'errors': 0}
    for row in rows:
        w = row['weight']
        out['files'] += w
        if row['outcome'] == 'refused':
            out['refused'] += w
        if row['outcome'] == 'error':
            out['errors'] += w
        if row['outcome'] != 'report':
            continue
        counts = row[key] if key else row
        for c in COUNTS + ('lost',):
            out[c] += w * counts[c]
        out['objects'] += w * sum(counts[c] for c in CATEGORIES)
        out['full'] += w * counts['full']
    return out


def audit(paths, *, weights=None, web_registry=None) -> dict:
    """The audit of ``paths`` (``animageo.import_audit`` v1): ``totals``
    (``library`` and, with ``web_registry``, ``web``) and ``files`` (the rows
    of :func:`audit_file`)."""
    from ... import __version__
    from ..registry import REGISTRY_VERSION
    if web_registry is not None:
        registry_version(web_registry)
    weights = weights or {}
    rows = []
    for path in audit_files(paths):
        data_sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        rows.append(audit_file(path, weight=weights.get(data_sha, 1), web_registry=web_registry))
    out = {'format': AUDIT_FORMAT, 'version': AUDIT_VERSION, 'library': __version__, 'registry': REGISTRY_VERSION,
           'webRegistry': web_registry, 'totals': {'library': totals(rows)}, 'files': rows}
    if web_registry is not None:
        out['totals']['web'] = totals(rows, 'web')
    return out


def audit_line(label: str, t: dict) -> str:
    """``<label> files N full N objects N editable N lost N picture N differs N
    value_unchecked N`` (``refused N``, ``errors N`` when there are any)."""
    text = (f"{label} files {t['files']} full {t['full']} objects {t['objects']} editable {t['editable']} "
            f"lost {t['lost']} picture {t['picture']} differs {t['differs']} value_unchecked {t['value_unchecked']}")
    for key in ('refused', 'errors'):
        if t[key]:
            text += f' {key} {t[key]}'
    return text
