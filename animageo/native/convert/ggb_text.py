"""Conservative, value-checked GGB texts lowered to existing registry ops."""
from __future__ import annotations

import copy
import math
import re

from .construction import Record
from .keys import element_id, operation_id

# Only ordinary TeX: definitions, file access and unknown user macros never
# become an editable native text. This is a conversion subset, not a TeX sandbox.
_COMMANDS = frozenset(('alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho '
    'sigma tau upsilon phi chi psi omega varepsilon vartheta varpi varrho varsigma varphi '
    'Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega '
    'frac dfrac tfrac sqrt text mbox textrm textbf textit mathrm mathbf mathit mathsf mathtt '
    'mathcal mathbb overline underline vec hat bar dot ddot widehat widetilde '
    'left right big Big bigg Bigg displaystyle textstyle scriptstyle scriptscriptstyle '
    'sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh log ln exp lim min max '
    'sum prod int iint oint infty partial nabla pm mp cdot times div circ degree '
    'angle triangle square perpendicular perp parallel neq ne approx sim simeq equiv '
    'le leq leqslant ge geq geqslant ll gg in notin ni subset supset subseteq supseteq '
    'cup cap emptyset varnothing forall exists neg land lor to mapsto rightarrow leftarrow '
    'leftrightarrow Rightarrow Leftarrow Leftrightarrow ldots cdots dots '
    'langle rangle lbrace rbrace vert Vert quad qquad enspace thinspace medspace thickspace').split())
_ESCAPES = frozenset(' ,:;!%&#_{}$|')


def inline_tex(text, latex):
    """Return native inline math only when the source has the same meaning."""
    if not latex:
        if '$' in text:
            raise ValueError('обычный текст с долларом требует буквального отображения')
        return text
    s = text.strip()
    display = s.startswith(r'\[') and s.endswith(r'\]')
    if display:
        s = s[2:-2]
    elif s.startswith(r'\(') and s.endswith(r'\)'):
        s = s[2:-2]
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '\\':
            m = re.match(r'\\([A-Za-z]+|.)', s[i:])
            if m is None or m[1] not in _COMMANDS | _ESCAPES:
                raise ValueError('неподдержанная команда TeX: ' + (m[0] if m else '\\'))
            i += len(m[0])
            continue
        if ch in '&#%':
            # an alignment tab, a macro parameter or a comment outside its
            # environment is a TeX error (a comment would also eat the closing $)
            raise ValueError('неподдержанный символ TeX: ' + ch)
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        if depth < 0:
            raise ValueError('несогласованные скобки TeX')
        i += 1
    if depth:
        raise ValueError('несогласованные скобки TeX')
    if '$$' in s:
        raise ValueError('двойные доллары TeX пока не переносятся')
    parts = re.split(r'(?<!\\)\$', s)
    if len(parts) == 1:
        return '$' + (r'\displaystyle ' if display else '') + s + '$'
    if display or len(parts) % 2 == 0 or any(not p.strip() for p in parts[1::2]):
        raise ValueError('несогласованные разделители TeX')
    if any(re.search(r'[\\{}&#_^%~]', p) for p in parts[::2]):
        raise ValueError('TeX вне математического фрагмента пока не переносится')
    return s


def _source_ok(expr, labels):
    # split_text_parts is intentionally permissive for the classic renderer;
    # editable import also requires a complete concatenation, including quotes.
    names = '|'.join(re.escape(n) for n in sorted(labels, key=len, reverse=True))
    token = r'(?:(?:"(?:\\"|[^"])*")' + ('|' + names if names else '') + ')'
    return len(expr) <= 10000 and re.fullmatch(r'\s*' + token + r'(?:\s*\+\s*' + token + r')*\s*', expr) is not None


def promote_texts(doc, entries, namespace):
    """Promote only texts whose shown value and anchor evaluate exactly.

    Private anchors/measures use UUID5 keys outside the public source IDs.
    Unknown expressions keep their explicit fallback reason and no native IDs.
    """
    from .. import evaluate, load, validate
    from .style import appearance
    by_name = {e['name']: e for e in entries}
    trial = copy.deepcopy(doc)
    built = []
    for entry in entries:
        info, value = entry['info'], entry['ggb_value']
        if info['type'] != 'text' or info.get('script') or info.get('command') != 'Expression' or not value:
            continue
        try:
            if not _source_ok(info['inputs'][0], by_name) or 'template' not in value or 'shown' not in value:
                raise ValueError('выражение текста не входит в поддержанное объединение строк и объектов')
            template = inline_tex(value['template'], info.get('latex'))
            shown = inline_tex(value['shown'], info.get('latex'))
            from ..expr.template import template_problems
            if template_problems(template, len(value['refs'])):
                raise ValueError('неподдержанный шаблон текста')
            deps = [r['ggb_name'] for r in value['refs']]
            anchor_name = value.get('anchor_ref')
            if anchor_name:
                deps.append(anchor_name)
            if any(not by_name[n]['native_ids'] or by_name[n]['status'] != 'translated' for n in deps):
                raise ValueError('текст зависит от неперенесённого объекта')
            anchor = value.get('anchor')
            if not anchor_name and (not isinstance(anchor, list) or len(anchor) != 2 or
                                    not all(isinstance(v, (int, float)) and math.isfinite(v) for v in anchor)):
                raise ValueError('у текста нет конечного якоря')
        except ValueError as exc:
            entry['detail'] = str(exc)
            continue
        key = 'ggb:' + entry['name']
        added_ops, added_elements = [], []

        def emit(suffix, op, args, slot, type_):
            k = key + suffix
            oid, eid = operation_id(namespace, k), element_id(namespace, k)
            trial['operations'][oid] = {'id': oid, 'op': op, 'args': args,
                                        'outputs': [{'slot': slot, 'elementId': eid}]}
            trial['elements'][eid] = {'id': eid, 'type': type_, 'displayName': '' if suffix else entry['name'],
                                      'producer': {'operationId': oid, 'slot': slot}}
            added_ops.append(oid)
            added_elements.append(eid)
            if suffix:
                trial['appearance'][eid] = {'visible': False, 'locked': True, 'label': {'mode': 'none'}}
            return {'kind': 'ref', 'elementId': eid}

        if anchor_name:
            anchor_ref = {'kind': 'ref', 'elementId': by_name[anchor_name]['native_ids'][0]}
        else:
            anchor_ref = emit('#anchor', 'point.free', {}, 'point', 'point')
            trial['inputs'][anchor_ref['elementId']] = {'kind': 'point', 'value': anchor}
        refs = []
        for k, ref in enumerate(value['refs']):
            eid = by_name[ref['ggb_name']]['native_ids'][0]
            arg = {'kind': 'ref', 'elementId': eid}
            type_ = trial['elements'][eid]['type']
            measure = {'length': 'length', 'area': 'area'}.get(ref['as'])
            if ref['as'] == 'angle' and type_ == 'angle':
                measure = 'angle'
            if measure:
                arg = emit(f'#ref{k}', 'measure.' + measure, {'angle' if measure == 'angle' else 'of': arg},
                           'number', 'number')
            refs.append(arg)
        text = emit('', 'text.free', {'text': {'kind': 'template', 'value': template}, 'anchor': anchor_ref,
                    'refs': {'kind': 'list', 'items': refs},
                    'decimals': {'kind': 'number', 'value': value['decimals']}}, 'text', 'text')['elementId']
        trial['appearance'][text] = appearance(info, None) or {}
        built.append((entry, text, shown, deps, added_ops, added_elements))
    if not built:
        return
    # Check each text independently: a bad insert cannot suppress other texts.
    for entry, text, shown, deps, ops, elements in built:
        candidate = copy.deepcopy(doc)
        for section, ids in (('operations', ops), ('elements', elements), ('inputs', elements), ('appearance', elements)):
            candidate[section].update({k: trial[section][k] for k in ids if k in trial[section]})
        issues = validate(load(candidate, strict=False))
        if any(i.severity == 'error' for i in issues):
            entry['detail'] = 'шаблон текста не прошёл проверку native'
            continue
        ev = evaluate(candidate)
        state = ev.elements[text]
        actual = state.get('value') or {}
        if state['state'] != 'defined' or actual.get('text') != shown or actual.get('anchor') != entry['ggb_value']['anchor']:
            entry['detail'] = 'значение текста или якорь не совпадает с сохранённым GeoGebra'
            continue
        for section in ('operations', 'elements', 'inputs', 'appearance'):
            doc[section] = candidate[section]
        doc.setdefault('bindings', {}).setdefault('legacyNames', {})[text] = entry['name']
        rec = Record(entry['name'], 'ggb:' + entry['name'], entry['name'], type='text',
                     native_ids=[text], native_value={'kind': 'text', 'text': shown, 'anchor': actual['anchor']})
        entry.update(status='translated', reason=None, detail=None, value_check='passed', free=not deps,
                     native_ids=[text], depends_on=list(dict.fromkeys(deps)), rec=rec)
