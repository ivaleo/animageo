"""Reports of the translator: the common one of ``from_construction`` and
``import_report.v1`` of ``from_ggb`` (plan L5 §3.4 p. 6, §3.5).

Categories (W6 §0.1): ``editable`` — an operation of the registry whose value
matches (``value_check = passed``) or a free input taken from the source as
is; ``differs`` — translated, but the value does not match or is not checked
(decision 12: ``not_checked`` of a dependent is ``differs``); ``picture`` — not
translated, with a value the web can place statically (a point, a segment, a
polygon, a text), unless it depends on an unsupported object; ``unsupported``
— not translated, with a reason; ``closure`` — depends (through a chain) on an
unsupported object (reason ``depends_on_unsupported``).
"""
from __future__ import annotations

from collections import Counter

__all__ = ['REPORT_FORMAT', 'REPORT_VERSION', 'CATEGORIES', 'REASONS', 'DROPPED_KINDS', 'categorize',
           'report_problems', 'construction_report']

REPORT_FORMAT = 'animageo.import_report'
REPORT_VERSION = 1
CATEGORIES = ('editable', 'picture', 'unsupported', 'closure', 'differs')
REASONS = ('no_registry_op', 'random_point', 'formula_unsupported', 'dynamic_topology', 'style_only', 'script',
           '3d', 'cas', 'spreadsheet', 'image', 'latex_macros', 'fixed_text', 'web_capability_missing',
           'depends_on_unsupported', 'value_mismatch', 'unsupported_signature', 'list', 'macro', 'ui_object',
           'parse_error', 'slot_ambiguous', 'value_unchecked')
DROPPED_KINDS = ('script', 'animation', 'conditional_visibility', 'dynamic_color', 'layers', '3d', 'spreadsheet',
                 'cas', 'image')


def categorize(entries: list) -> list:
    """Set ``category`` and ``reason`` of report ``entries`` in source order.

    Each entry has ``name``, ``depends_on`` (names of entries), ``status``
    (``translated`` | ``untranslated``), ``reason`` (own reason when
    untranslated), ``free``, ``value_check``, ``placeable`` (the web can place
    its value) and ``picture_reason`` (``latex_macros`` / ``fixed_text`` of a
    text). Dependencies come before their dependents.
    """
    by_name = {}
    tainted = set()             # names with an unsupported ancestor (through any chain, pictures included)
    for e in entries:
        deps = [by_name[d] for d in e['depends_on'] if d in by_name]
        unsupported_above = any(d['category'] == 'unsupported' or d['name'] in tainted for d in deps)
        if unsupported_above:
            tainted.add(e['name'])
        if e['status'] == 'translated':
            if any(d['category'] in ('unsupported', 'closure', 'picture') for d in deps):
                # its input is not in the document: it cannot be translated after all
                e['status'] = 'untranslated'
                e['reason'] = 'depends_on_unsupported'
            elif e.get('free') or e['value_check'] == 'passed':
                e['category'], e['reason'] = 'editable', None
            else:
                e['category'] = 'differs'
                if e['value_check'] == 'failed':
                    e['reason'] = e.get('reason') if e.get('reason') == 'slot_ambiguous' else 'value_mismatch'
                else:
                    e['reason'] = 'value_unchecked'
        if e['status'] != 'translated':
            if unsupported_above:
                e['category'], e['reason'] = 'closure', 'depends_on_unsupported'
            elif e.get('placeable'):
                # a dependent of a picture keeps depends_on_unsupported: its input is not in the document
                e['category'] = 'picture'
                e['reason'] = e.get('picture_reason') or e['reason'] or 'no_registry_op'
            else:
                e['category'] = 'unsupported'
                e['reason'] = e['reason'] or 'no_registry_op'
            e['native_ids'] = []
            if e['category'] in ('unsupported', 'closure', 'picture'):
                e['value_check'] = 'not_checked'
        by_name[e['name']] = e
    return entries


def _closure_names(elements: list) -> set:
    roots = {e['ggb_name'] for e in elements if e['category'] == 'unsupported'}
    dependents: dict = {}
    for e in elements:
        for dep in e['depends_on']:
            dependents.setdefault(dep, []).append(e['ggb_name'])
    seen: set = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        for child in dependents.get(name, ()):
            if child not in seen and child not in roots:
                seen.add(child)
                stack.append(child)
    return seen


def report_problems(report: dict, document: dict | None = None) -> list:
    """Consistency of an ``import_report.v1`` (the rules of the web's
    ``import_report.py``, plus the categories of the library): every object
    once, the summary, known dependencies, the closure is exactly the
    dependents of unsupported objects, zero falsely editable, a native element
    of one object only, every ``native_ids`` of editable/differs in the document."""
    out = []
    if report.get('format') != REPORT_FORMAT or report.get('version') != REPORT_VERSION:
        out.append('format/version')
    elements = report.get('elements', [])
    names = [e['ggb_name'] for e in elements]
    doubled = sorted(n for n, k in Counter(names).items() if k > 1)
    if doubled:
        out.append(f'objects in several entries: {doubled[:5]}')
    if len(elements) != report['source']['objects']:
        out.append(f'{len(elements)} entries, {report["source"]["objects"]} objects')
    counted = Counter(e['category'] for e in elements)
    for cat in CATEGORIES:
        if report['summary'].get(cat) != counted.get(cat, 0):
            out.append(f'summary {cat}')
    known = set(names)
    for e in elements:
        if e['category'] not in CATEGORIES:
            out.append(f'{e["ggb_name"]}: category {e["category"]}')
        if e.get('reason') is not None and e['reason'] not in REASONS:
            out.append(f'{e["ggb_name"]}: reason {e["reason"]}')
        if any(d not in known for d in e['depends_on']):
            out.append(f'{e["ggb_name"]}: unknown dependency')
        if e['ggb_name'] in e['depends_on']:
            out.append(f'{e["ggb_name"]}: depends on itself')
        if e['category'] in ('unsupported', 'closure') and (not e.get('reason') or e['native_ids']):
            out.append(f'{e["ggb_name"]}: {e["category"]} needs a reason and no native_ids')
        if e['category'] in ('editable', 'differs') and not e['native_ids']:
            out.append(f'{e["ggb_name"]}: {e["category"]} without native_ids')
        if e['category'] == 'editable' and e['value_check'] != 'passed':
            out.append(f'{e["ggb_name"]}: editable without value_check passed')
        if e['category'] == 'differs' and e['value_check'] == 'passed':
            out.append(f'{e["ggb_name"]}: differs with value_check passed')
    expected = _closure_names(elements)
    for e in elements:
        if e['category'] == 'closure' and e['ggb_name'] not in expected:
            out.append(f'{e["ggb_name"]}: closure without an unsupported ancestor')
        if e['ggb_name'] in expected and e['category'] not in ('closure', 'picture'):
            out.append(f'{e["ggb_name"]}: depends on unsupported, category {e["category"]}')
    owners: dict = {}
    for e in elements:
        for nid in e['native_ids']:
            if nid in owners:
                out.append(f'native element {nid} of two objects')
            owners[nid] = e['ggb_name']
    if document is not None:
        missing = [nid for e in elements if e['category'] in ('editable', 'differs') for nid in e['native_ids']
                   if nid not in document.get('elements', {})]
        if missing:
            out.append(f'native_ids not in the document: {missing[:3]}')
    elif any(e['category'] in ('editable', 'differs') for e in elements):
        out.append('no document, but editable objects')
    return out


def construction_report(translation, *, include_constants=False) -> dict:
    """The common report of :func:`from_construction`: ``{elements,
    untranslated, warnings}`` (plan §3.4 p. 6) by classic name."""
    entries = []
    for name in translation.names:
        rec = translation.records[name]
        deps = []
        for inp in rec.inputs:
            r = translation.records.get(inp)
            if r is not None and r.status != 'constant' and inp not in deps:
                deps.append(inp)
        entries.append({'name': name, 'depends_on': deps, 'status': 'translated' if rec.status == 'translated'
                        else 'untranslated', 'reason': rec.reason, 'free': rec.free, 'value_check': rec.value_check,
                        'placeable': False, 'native_ids': list(rec.native_ids)})
    categorize(entries)
    elements = []
    for e in entries:
        rec = translation.records[e['name']]
        item = {'name': rec.name, 'key': rec.key, 'display': rec.display, 'command': rec.command,
                'signature': rec.signature, 'category': e['category'], 'native_ids': e['native_ids'],
                'depends_on': e['depends_on'], 'value_check': e['value_check']}
        if e.get('reason'):
            item['reason'] = e['reason']
        if rec.detail:
            item['detail'] = rec.detail
        if rec.expected is not None and e['category'] in ('editable', 'differs'):
            item['expected'] = rec.expected
        if rec.native_value is not None and e['category'] in ('editable', 'differs'):
            item['native_value'] = rec.native_value
        if rec.delta is not None and e['category'] == 'differs':
            item['delta'] = rec.delta
        elements.append(item)
    untranslated = [{'name': i['name'], 'command': i['command'], 'signature': i['signature'],
                     'reason': i.get('reason'), **({'detail': i['detail']} if i.get('detail') else {})}
                    for i in elements if i['category'] in ('unsupported', 'closure', 'picture')]
    return {'elements': elements, 'untranslated': untranslated, 'warnings': list(translation.warnings)}
