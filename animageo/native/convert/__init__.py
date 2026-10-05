"""Graph → operations: the classic ``Construction`` and ``.ggb`` files as
documents of ``animageo.native`` (kernel stage L5, plan L5 §3).

    doc, rep = native.from_construction(constr, mode="partial", id_namespace=ns)
    doc, rep = native.from_ggb("file.ggb", id_namespace=ns)       # rep — import_report.v1

One translator by the table ``dsl_map.json`` (:mod:`.mapping`) serves both
inputs. IDs are ``uuid5(id_namespace, key)`` (:mod:`.keys`). The modules of
this package import neither manim nor the classic code at import time;
``ggb_parser`` and ``lib_commands`` are loaded inside the functions.
"""
from __future__ import annotations

import contextlib
import copy
import logging
import re

from .construction import ConvertError, Context, translate
from .ggb import ImportRefused, LIMITS
from .keys import namespace_of
from .mapping import MAP_FORMAT, dsl_map, map_problems
from .report import REPORT_FORMAT, REPORT_VERSION, categorize, construction_report, report_problems, settle

__all__ = ['ConvertError', 'ImportRefused', 'LIMITS', 'MAP_FORMAT', 'REPORT_FORMAT', 'dsl_map', 'from_construction',
           'from_ggb', 'map_problems', 'report_problems']

_TOKEN = re.compile(r"[^\W\d][\w']*(?:_\{[^}]*\})?")


@contextlib.contextmanager
def _quiet():
    log = logging.getLogger('animageo')
    level = log.level
    log.setLevel(logging.ERROR)
    try:
        yield
    finally:
        log.setLevel(level)


def from_construction(constr, *, mode: str = 'strict', id_namespace, key_of=None, origin_of=None):
    """A classic ``Construction`` (a DSL scene) as a document and a report.

    ``key_of(name)`` gives the key of a classic name (default ``dsl:<name>``,
    phantoms ``anon:…``); ``origin_of(name)`` an ``origin`` object of its
    element. ``mode="strict"`` raises :class:`ConvertError` when anything does
    not translate; ``"partial"`` returns the document of what does, the rest
    with reasons and the closure. Returns ``(document | None, report)``,
    report ``{elements, untranslated, warnings}``.
    """
    if mode not in ('strict', 'partial'):
        raise ValueError('mode must be strict or partial')
    ns = namespace_of(id_namespace)
    display, keys = {}, {}
    if key_of is not None:
        for obj in list(constr.elements) + list(constr.vars):
            key = key_of(obj.name)
            if key:
                keys[obj.name] = str(key)
                display[obj.name] = str(key).split(':', 1)[-1]
    ctx = Context(namespace=ns, prefix='dsl', mode=mode, display=display, keys=keys, origin_of=origin_of)
    with _quiet():
        tr = translate(constr, ctx)
    rep = construction_report(tr)
    _prune(tr.document, {nid for e in rep['elements'] if e['category'] in ('editable', 'differs')
                         for nid in e['native_ids']})
    if mode == 'strict' and rep['untranslated']:
        raise ConvertError(rep['untranslated'])
    doc = tr.document if tr.document['operations'] else None
    return doc, rep


def _prune(doc: dict, keep: set) -> None:
    """Remove the elements not in ``keep`` (and operations left without outputs)."""
    for eid in [e for e in doc['elements'] if e not in keep]:
        el = doc['elements'].pop(eid)
        doc['inputs'].pop(eid, None)
        doc['appearance'].pop(eid, None)
        doc.get('bindings', {}).get('legacyNames', {}).pop(eid, None)
        op = doc['operations'].get(el['producer']['operationId'])
        if op is not None:
            op['outputs'] = [o for o in op['outputs'] if o['elementId'] != eid]
            if not op['outputs']:
                del doc['operations'][op['id']]
    if doc.get('bindings') == {'legacyNames': {}}:
        doc['bindings'] = {}


# ── .ggb ─────────────────────────────────────────────────────────────────

def _classic_parse(root, macro_root, scanned):
    """``(Construction, parse_errors)``: the classic parser on the scanned tree.
    An element the parser cannot get past is cut out of the tree (found by
    bisection over the children, at most 8 times) and reported ``parse_error``."""
    from ...geo.construction import Construction
    from ...parsers import ggb_parser
    constr_xelem = root.find('construction')
    if macro_root is not None:
        try:
            from ...parsers.ggb_macro import expand_macros_in_construction, parse_macros
            macros = parse_macros(macro_root)
            if macros:
                expand_macros_in_construction(constr_xelem, macros)
        except Exception:          # noqa: BLE001 — macros are reported, not fatal
            pass
    children = list(constr_xelem)
    removed: list = []

    def attempt(nodes):
        constr = Construction()
        constr.strict_unsupported = False
        constr.log_unsupported = False
        constr.ggb_decimals = int(scanned.get('decimals') or 2)
        constr.ggb_view_x_range = ggb_parser._view_x_range(scanned.get('view'))
        tree = copy.copy(constr_xelem)
        tree[:] = nodes
        ggb_parser.parse_constr(constr, tree)
        return constr

    nodes = list(children)
    for _ in range(9):
        try:
            return attempt(nodes), removed
        except Exception:          # noqa: BLE001 — find the child the parser cannot pass
            if len(removed) >= 8:
                break
            lo, hi = 0, len(nodes)          # prefix(lo) passes, prefix(hi) fails
            while hi - lo > 1:
                mid = (lo + hi) // 2
                try:
                    attempt(nodes[:mid])
                    lo = mid
                except Exception:  # noqa: BLE001
                    hi = mid
            bad = nodes[hi - 1]
            cut = [bad]
            if bad.tag in ('command', 'expression'):
                out = bad.find('output')
                labels = set(out.attrib.values()) if out is not None else {bad.attrib.get('label')}
                labels.discard(None)
                labels.discard('')
                cut += [n for n in nodes[hi:] if n.tag == 'element' and n.attrib.get('label') in labels]
            for n in cut:
                label = _node_label(n)
                if label not in removed:
                    removed.append(label)
            nodes = [n for n in nodes if all(n is not c for c in cut)]
    constr = Construction()
    return constr, removed + ['*']


def _node_label(node) -> str:
    """The label of a construction node for the report: its own, the first
    output of a command, or its tag (a node without either)."""
    if node.attrib.get('label'):
        return node.attrib['label']
    out = node.find('output')
    for value in (out.attrib.values() if out is not None else ()):
        if value:
            return value
    return f'<{node.tag}>'


def _labels_in(texts, labels) -> list:
    out = []
    for text in texts:
        if text in labels:
            found = [text]
        else:
            found = [t for t in _TOKEN.findall(str(text)) if t in labels]
        for t in found:
            if t not in out:
                out.append(t)
    return out


def _text_of(expr: str) -> str:
    s = expr.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"' and s.count('"') == 2:
        return s[1:-1]
    return s


def from_ggb(path_or_bytes, *, id_namespace, mode: str = 'partial', limits=None, name: str | None = None):
    """A ``.ggb`` (path or bytes) as ``(document | None, import_report.v1)``.

    Limits refuse the file before parsing (:class:`ImportRefused`); each
    ``<element>`` of the XML is one entry of the report; ``mode="strict"``
    raises :class:`ConvertError` unless every object is editable."""
    from .. import content_hash
    from ... import __version__
    from ..registry import REGISTRY_VERSION
    from .ggb import (COMMANDS_3D, DEFAULT_JS, PLACEABLE, TYPES_3D, TYPES_FORMULA, TYPES_UI, ggb_value, parse_xml,
                      read_ggb, scan, view_bounds)
    from ..document import iter_refs
    from .keys import make_id
    from .style import appearance, ggb_style, label_of
    if mode not in ('strict', 'partial'):
        raise ValueError('mode must be strict or partial')
    ns = namespace_of(id_namespace)
    lim = dict(LIMITS)
    lim.update(limits or {})
    f = read_ggb(path_or_bytes, name=name, limits=lim)
    root = parse_xml(f.xml, depth=lim['depth'])
    sc = scan(root)
    infos = sc['elements']
    if len(infos) > lim['objects']:
        raise ImportRefused('import_too_many_objects', f'объектов {len(infos)} > {lim["objects"]}')
    long_label = next((i['label'] for i in infos if len(i['label']) > lim['label_chars']), None)
    if long_label is not None:
        raise ImportRefused('ggb_invalid', f'имя объекта длиннее {lim["label_chars"]} символов: '
                                           f'{long_label[:40]}…')
    macro_root = parse_xml(f.macro_xml, depth=lim['depth']) if f.macro_xml else None
    macro_names = set()
    if macro_root is not None:
        macro_names = {m.attrib.get('cmdName') for m in macro_root.iter('macro') if m.attrib.get('cmdName')}
    with _quiet():
        constr, parse_errors = _classic_parse(root, macro_root, sc)
    from ...geo.construction import normalize_name
    labels = {i['label'] for i in infos}
    norm = {}
    for info in infos:
        label = info['label']
        norm[label] = constr.name_mapping.get(label) or normalize_name(label)
    display = {n: lab for lab, n in norm.items()}
    by_label = {i['label']: i for i in infos}

    def point_of(label):
        i = by_label.get(label)
        v = ggb_value(i) if i is not None and i['type'] == 'point' else None
        return v['value'] if v else None

    diag_outputs = {}
    for d in getattr(constr, 'command_diagnostics', []):
        for o in d.get('outputs', []):
            diag_outputs.setdefault(o, d)
    built_by_command = {str(getattr(o, 'name', o)) for cmd in constr.commands for o in cmd.outputs}
    ctx = Context(namespace=ns, prefix='ggb', mode=mode, display=display, bounds=view_bounds(sc['view']))
    ctx.xml_types = {i['label']: i['type'] for i in infos}
    for label in sc['outputs']:
        if label not in labels:
            # defined by a command but without its <element>: not an object of the report, so its
            # dependents cannot refer to it in the document
            ctx.forced[constr.name_mapping.get(label) or normalize_name(label)] = (
                'parse_error', f'у выхода команды {label[:40]} нет <element>')
    for info in infos:
        n = norm[info['label']]
        ctx.order[n] = info['order']
        t = info['type']
        command = info.get('command')
        if t not in ('conicpart', 'segment', 'ray', 'vector'):
            v = ggb_value(info, point_of)
            if v is not None and t != 'text':
                ctx.expected[n] = v
        elif t in ('segment', 'ray'):
            ctx.expected[n] = ggb_value(info)
        if t == 'point' and info.get('coords') is not None:
            v = ggb_value(info)
            if v and v['value'] is not None:
                ctx.free_points[n] = v['value']
        if t in ('numeric', 'angle') and info.get('value') is not None:
            ctx.free_numbers[n] = {'value': info['value'], 'angle': t == 'angle', **info.get('slider', {})}
        reason = None
        if info.get('script'):
            reason = ('script', 'объект со скриптом GeoGebra (скрипт не переносится)')
        elif t.lower() in TYPES_3D or info.get('is3d') or command in COMMANDS_3D:
            reason = ('3d', None)
        elif t == 'list':
            reason = ('list', None)
        elif t in TYPES_UI:
            reason = ('ui_object', None)
        elif t == 'image':
            reason = ('image', None)
        elif command and command.startswith('Random'):
            reason = ('random_point', None)
        elif n in diag_outputs and diag_outputs[n].get('reason') == 'expression_parse_error':
            # the classic kept the saved value: a free copy would be falsely editable
            reason = ('parse_error', diag_outputs[n].get('detail'))
        elif n in diag_outputs and diag_outputs[n].get('reason') == 'parametric_dependency_frozen':
            reason = ('unsupported_signature', 'сохранённое положение не воспроизводится — объект заморожен')
        elif command and command != 'Expression' and n not in built_by_command:
            # the classic kept the saved value of a command it cannot run: a free copy is falsely editable
            known = command in dsl_map().by_ggb
            reason = ('unsupported_signature' if known else 'no_registry_op',
                      f'команда {command} с такими аргументами не переносится' if known
                      else f'команда {command} не переносится')
        if reason:
            ctx.forced[n] = reason
        app = appearance(info, None)
        if app:
            ctx.appearance[n] = app
    with _quiet():
        tr = translate(constr, ctx)
    # one entry per <element>

    def root_reason(rec, seen=()):
        """The reason of a closure caused by an object outside the report (a
        phantom: an expression argument); ``None`` — the cause is a reported
        object, the closure is visible in the report."""
        for inp in rec.inputs:
            r = tr.records.get(inp)
            if r is None or inp in seen or r.status in ('translated', 'constant'):
                continue
            if r.display and r.display in labels:
                continue
            if r.status == 'untranslated':
                return r.reason
            found = root_reason(r, seen + (inp,))
            if found:
                return found
        return None

    entries = []
    for info in infos:
        label, t = info['label'], info['type']
        n = norm[label]
        rec = tr.records.get(n)
        deps = [d for d in _labels_in(info.get('inputs', []), labels) if d != label]
        if t == 'text' and info.get('command') == 'Expression':
            info['text'] = _text_of(info['inputs'][0]) if info.get('inputs') else ''
            deps = [d for d in deps if d not in ('text',)]
        value = ggb_value(info, point_of)
        placeable = t in PLACEABLE and value is not None and (value.get('value') is not None or t == 'text') \
            and (t != 'segment' or value['kind'] == 'segment')
        e = {'name': label, 'info': info, 'depends_on': deps, 'free': False, 'value_check': 'not_checked',
             'placeable': placeable, 'native_ids': [], 'ggb_value': value}
        if t == 'text':
            e['picture_reason'] = 'latex_macros' if info.get('latex') else 'fixed_text'
        if rec is None:
            e['status'] = 'untranslated'
            if n in ctx.forced:
                e['reason'] = ctx.forced[n][0]
            elif label in parse_errors or '*' in parse_errors or n in diag_outputs and \
                    diag_outputs[n].get('reason') == 'expression_parse_error':
                e['reason'] = 'parse_error'
            elif t.lower() in TYPES_FORMULA:
                e['reason'] = 'formula_unsupported'
            elif info.get('command') == 'Expression':
                e['reason'] = 'parse_error'          # an expression the classic parser did not take
            elif info.get('command') in macro_names:
                e['reason'] = 'macro'
            else:
                e['reason'] = 'no_registry_op'
            e['detail'] = None
        else:
            e['rec'] = rec
            e['status'] = 'translated' if rec.status == 'translated' else 'untranslated'
            e['reason'] = rec.reason
            if rec.status == 'closure':
                e['reason'] = root_reason(rec) or 'depends_on_unsupported'
                exprs = [x for x in info.get('inputs', []) if x not in labels]
                if e['reason'] != 'depends_on_unsupported' and exprs and not rec.detail:
                    rec.detail = f'аргумент задан выражением: {exprs[0]}'
            if e['status'] == 'untranslated' and info.get('command') in macro_names:
                e['reason'] = 'macro'
            e['detail'] = rec.detail
            e['free'] = rec.free and info.get('command') in (None, 'Expression')
            e['value_check'] = rec.value_check
            e['native_ids'] = list(rec.native_ids)
        entries.append(e)
    categorize(entries)
    doc = tr.document

    def refs_of(nid):
        el = doc['elements'].get(nid)
        op = doc['operations'].get(el['producer']['operationId']) if el else None
        return [r for arg in (op or {}).get('args', {}).values() if isinstance(arg, dict) for r in iter_refs(arg)]
    settle(entries, refs_of)
    keep = {nid for e in entries if e['category'] in ('editable', 'differs') for nid in e['native_ids']}
    # an editable/differs element produced together with a dropped one keeps only its own element
    _prune(doc, keep)
    # steps from breakpoints of the construction protocol
    steps = []
    group = []
    seq_of = {}
    for e in entries:
        if e['category'] in ('editable', 'differs'):
            el = doc['elements'].get(e['native_ids'][0])
            if el is not None:
                op_id = el['producer']['operationId']
                if op_id not in seq_of:
                    seq_of[op_id] = len(seq_of) + 1
                    group.append(op_id)
        if e['info'].get('breakpoint') and group:
            steps.append(group)
            group = []
    if steps and group:
        steps.append(group)
    for op_id, seq in seq_of.items():
        doc['operations'][op_id]['seq'] = seq
    if steps:
        doc['steps'] = [{'id': make_id(ns, f'step:{k}'), 'kind': 'group', 'operationIds': ops}
                        for k, ops in enumerate(steps, 1)]
    if doc['operations']:
        from ..document import load, validate
        issues = [i for i in validate(load(doc, strict=False)) if getattr(i, 'severity', 'error') == 'error']
        if issues:
            raise RuntimeError('from_ggb built an invalid document: '
                               + '; '.join(f'{i.code} {i.path}' for i in issues[:3]))
        document = doc
    else:
        document = None
    elements = []
    for e in entries:
        info, rec = e['info'], e.get('rec')
        item = {'ggb_name': e['name'], 'ggb_type': info['type'][:40] or 'unknown',
                'category': e['category'], 'native_ids': e['native_ids'], 'depends_on': e['depends_on'],
                'value_check': e['value_check']}
        command = info.get('command')
        if command and command != 'Expression':
            item['command'] = command[:80]
        if rec is not None and rec.signature:
            item['signature'] = rec.signature[:80]
        if e.get('reason'):
            item['reason'] = e['reason']
        if e.get('detail'):
            item['detail'] = str(e['detail'])[:300]
        if e['ggb_value'] is not None:
            item['ggb_value'] = e['ggb_value']
        if rec is not None and e['category'] in ('editable', 'differs'):
            if rec.native_value is not None:
                item['native_value'] = rec.native_value
            if rec.delta is not None and e['category'] == 'differs':
                item['delta'] = rec.delta
        lab = label_of(info, None)
        if lab is not None:
            item['label'] = {'visible': lab['mode'] != 'none', 'mode': lab['mode'],
                             **({'caption': info['caption'][:500]} if info.get('caption') else {})}
        st = ggb_style(info)
        if st:
            item['ggb_style'] = st
        if info.get('show_object') is False:
            item['hidden'] = True
        if info.get('layer'):
            item['layer'] = info['layer']
        elements.append(item)
    dropped = dict(sc['dropped'])
    if f.javascript and not DEFAULT_JS.match(f.javascript):
        dropped.setdefault('script', []).append(None)
    drop_list = []
    for kind in sorted(dropped):
        items = dropped[kind]
        entry = {'kind': kind, 'count': len(items)}
        names = [x for x in items if x]
        if names:
            entry['names'] = names[:50]
        drop_list.append(entry)
    warnings = []
    for w in tr.warnings:
        warnings.append({'code': w['code'], **({'ggb_name': display.get(w['name'], w['name'])}
                                                 if w.get('name') else {})})
    if parse_errors:
        warnings.append({'code': 'parse_error', 'detail': ', '.join(str(x) for x in parse_errors)[:500]})
    if macro_names:
        warnings.append({'code': 'macros_expanded', 'detail': ', '.join(sorted(macro_names))[:500]})
    for kind in ('conditional_visibility', 'dynamic_color', 'animation', 'layers'):
        for label in dropped.get(kind, []):
            if label:
                warnings.append({'code': f'{kind}_dropped', 'ggb_name': label})
    summary = {c: sum(1 for e in elements if e['category'] == c)
               for c in ('editable', 'picture', 'unsupported', 'closure', 'differs')}
    report = {
        'format': REPORT_FORMAT,
        'version': REPORT_VERSION,
        'library': __version__,
        'registry': REGISTRY_VERSION,
        'mapVersion': dsl_map().version,
        'source': {'name': f.name[:255], 'size': f.size, 'sha256': f.sha256,
                   'ggb_version': (sc.get('version') or '')[:40] or None, 'app': (sc.get('app') or '')[:40] or None,
                   'objects': len(elements)},
        'summary': summary,
        'elements': elements,
        'dropped': drop_list,
        'warnings': warnings,
        'document_hash': content_hash(document) if document is not None else None,
    }
    if mode == 'strict':
        bad = [{'name': e['ggb_name'], 'command': e.get('command'), 'signature': e.get('signature'),
                'reason': e.get('reason')} for e in elements if e['category'] != 'editable']
        if bad:
            raise ConvertError(bad)
    return document, report
