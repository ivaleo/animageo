"""A corpus of ``.ggb`` files and its expectations (plan L5 §8).

An expectation is what :func:`from_ggb` makes of a file, keyed by the sha256
of its bytes (``<expected>/<sha256>.json``): the outcome (a report or a
refusal with its code), the summary, the category and reason of every
object, the dropped kinds and the warning codes — not the IDs or the values,
so a change of the document that keeps the categories keeps the expectation.
:func:`record` writes them, :func:`verify` compares, :func:`coverage` counts
the objects of a corpus by category and by key of ``dsl_map``.

``python -m animageo.native convert corpus record|verify <dir> [--expected <dir>]``,
``python -m animageo.native convert map --coverage <dir> [--json]``.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from pathlib import Path

from .report import CATEGORIES

__all__ = ['EXPECTATION_FORMAT', 'EXPECTATION_VERSION', 'corpus_files', 'expectation', 'record', 'verify',
           'coverage', 'coverage_text']

EXPECTATION_FORMAT = 'animageo.import_expectation'
EXPECTATION_VERSION = 1


def corpus_files(directory) -> list:
    """The ``*.ggb`` files under ``directory`` (recursively), sorted by path."""
    root = Path(directory)
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.ggb'),
                  key=lambda p: p.relative_to(root).as_posix())


def _import(data: bytes, name: str):
    """``(sha256, document, report)`` or ``(sha256, None, ImportRefused)``; the IDs
    come from the sha256 of the file, as with ``from-ggb`` without ``--namespace``."""
    from . import ImportRefused, from_ggb
    sha = hashlib.sha256(data).hexdigest()
    try:
        doc, report = from_ggb(data, id_namespace=uuid.UUID(sha[:32]), name=name)
    except ImportRefused as exc:
        return sha, None, exc
    return sha, doc, report


def _expectation_of(sha: str, name: str, doc, report) -> dict:
    head = {'format': EXPECTATION_FORMAT, 'version': EXPECTATION_VERSION, 'file': name, 'sha256': sha}
    if not isinstance(report, dict):
        return {**head, 'outcome': 'refused', 'code': report.code}
    return {**head, 'outcome': 'report', 'document': doc is not None, 'summary': dict(report['summary']),
            'dropped': sorted({d['kind'] for d in report['dropped']}),
            'warnings': sorted({w['code'] for w in report['warnings']}),
            'elements': [[e['ggb_name'], e['category'], e.get('reason')] for e in report['elements']]}


def expectation(path_or_bytes, *, name: str | None = None) -> dict:
    """The expectation of one file (a path or bytes)."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data, name = bytes(path_or_bytes), name or 'file.ggb'
    else:
        data, name = Path(path_or_bytes).read_bytes(), name or Path(path_or_bytes).name
    sha, doc, report = _import(data, name)
    return _expectation_of(sha, name, doc, report)


def _dump(exp: dict) -> str:
    """JSON with one object per line: a diff of an expectation reads by object."""
    head = {k: v for k, v in exp.items() if k != 'elements'}
    text = json.dumps(head, ensure_ascii=False, indent=1)
    if 'elements' not in exp:
        return text + '\n'
    rows = ',\n'.join('  ' + json.dumps(e, ensure_ascii=False) for e in exp['elements'])
    return text[:-2] + (',\n "elements": [\n' + rows + '\n ]\n}\n' if rows else ',\n "elements": []\n}\n')


def record(directory, expected) -> list:
    """Write the expectation of every file of the corpus into ``expected``;
    the written paths (an expectation of a file outside the corpus stays)."""
    out_dir = Path(expected)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    root = Path(directory)
    for path in corpus_files(root):
        exp = expectation(path, name=path.relative_to(root).as_posix())
        target = out_dir / f'{exp["sha256"]}.json'
        target.write_text(_dump(exp), encoding='utf-8')
        written.append(target)
    return written


def _differences(exp: dict, got: dict) -> list:
    out = []
    if exp.get('outcome') != got['outcome'] or exp.get('code') != got.get('code'):
        was = exp.get('code') or exp.get('outcome')
        return [f'outcome {was} → {got.get("code") or got["outcome"]}']
    if got['outcome'] != 'report':
        return []
    if exp.get('document') != got['document']:
        out.append(f'document {exp.get("document")} → {got["document"]}')
    for cat in CATEGORIES:
        a, b = exp.get('summary', {}).get(cat, 0), got['summary'].get(cat, 0)
        if a != b:
            out.append(f'{cat} {a} → {b}')
    for key in ('dropped', 'warnings'):
        if sorted(exp.get(key, [])) != got[key]:
            out.append(f'{key} {sorted(exp.get(key, []))} → {got[key]}')
    before = {e[0]: tuple(e[1:]) for e in exp.get('elements', [])}
    now = {e[0]: tuple(e[1:]) for e in got['elements']}
    for name in before.keys() - now.keys():
        out.append(f'{name}: gone')
    for name in now.keys() - before.keys():
        out.append(f'{name}: new {now[name][0]} {now[name][1] or ""}'.rstrip())
    for name in [e[0] for e in got['elements'] if e[0] in before and before[e[0]] != now[e[0]]]:
        (c0, r0), (c1, r1) = before[name], now[name]
        out.append(f'{name}: {c0} {r0 or ""} → {c1} {r1 or ""}'.replace('  ', ' ').strip())
    return out


def verify(directory, expected) -> tuple:
    """``(problems, checked)``: every file of the corpus against its expectation —
    a file without one, a different outcome, category or reason, a report that
    breaks its rules (``report_problems``) is a problem ``"<file>: …"``."""
    from .report import report_problems
    root = Path(directory)
    exp_dir = Path(expected)
    problems = []
    files = corpus_files(root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        sha, doc, report = _import(path.read_bytes(), rel)
        got = _expectation_of(sha, rel, doc, report)
        if isinstance(report, dict):
            problems += [f'{rel}: {p}' for p in report_problems(report, doc)]
        target = exp_dir / f'{sha}.json'
        if not target.is_file():
            problems.append(f'{rel}: no expectation {target.name} (record it)')
            continue
        try:
            exp = json.loads(target.read_text(encoding='utf-8'))
        except ValueError as exc:
            problems.append(f'{rel}: {target.name} is not JSON ({exc})')
            continue
        problems += [f'{rel}: {d}' for d in _differences(exp, got)]
    return problems, len(files)


def coverage(directory) -> dict:
    """The objects of a corpus by category, and by key: the ``dsl_map`` key of a
    translated command (``signature``), else ``command:<GGB command>``, else
    ``type:<GGB type>`` (free objects, expressions)."""
    root = Path(directory)
    files = corpus_files(root)
    refused = Counter()
    categories = Counter()
    keys: dict = {}
    for path in files:
        _, _doc, report = _import(path.read_bytes(), path.name)
        if not isinstance(report, dict):
            refused[report.code] += 1
            continue
        for e in report['elements']:
            key = e.get('signature') or (f'command:{e["command"]}' if e.get('command') else f'type:{e["ggb_type"]}')
            categories[e['category']] += 1
            keys.setdefault(key, Counter())[e['category']] += 1
    total = sum(categories.values())
    return {'files': len(files), 'refused': dict(sorted(refused.items())), 'objects': total,
            'categories': {c: categories.get(c, 0) for c in CATEGORIES},
            'editable_share': round(categories.get('editable', 0) / total, 4) if total else None,
            'keys': {k: {c: v.get(c, 0) for c in CATEGORIES}
                     for k, v in sorted(keys.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))}}


def coverage_text(cov: dict) -> str:
    """:func:`coverage` as a table."""
    lines = []
    refused = ', '.join(f'{k} {v}' for k, v in cov['refused'].items())
    lines.append(f'{cov["files"]} files' + (f' ({sum(cov["refused"].values())} refused: {refused})' if refused
                                              else '') + f', {cov["objects"]} objects')
    if cov['objects']:
        lines.append(' · '.join(f'{c} {n} ({100 * n / cov["objects"]:.1f}%)' for c, n in cov['categories'].items()))
    width = max([len(k) for k in cov['keys']] + [3])
    lines.append(f'{"key":<{width}}  {"objects":>7}  ' + '  '.join(f'{c:>11}' for c in CATEGORIES))
    for key, by_cat in cov['keys'].items():
        lines.append(f'{key:<{width}}  {sum(by_cat.values()):>7}  '
                     + '  '.join(f'{by_cat[c]:>11}' for c in CATEGORIES))
    return '\n'.join(lines)
