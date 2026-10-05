"""The text of a construction (1.9.0a1, plan L3 §2.5–§2.6; docs/native/steps.md).

``describe(doc, *, values=False, phrases=None, ev=None, precision=2) → [str]``:
one line ``"<n>. <phrase>."`` per step of :func:`~animageo.native.steps.steps`.

- A group with a ``title`` is a heading ``"<n>. <title>."`` and a sub-item
  ``"<n>.<k>. <phrase>."`` per operation; a group without one joins the
  phrases of its operations with ``"; "``; a step ``text`` replaces the
  phrase (under the title as ``"<n>.1. <text>."`` when there is one).
- A phrase is the template of the operation's ``stepKind`` in
  ``phrases/ru.v1.json`` (format ``animageo-phrases/v1``): ``ops.<op>``
  when the kind covers operations with other slots, else ``text``; a
  ``context`` entry whose ``when`` holds comes first (``triangle_vertices``:
  the three points of the op — ``a, b, c`` or the vertex and the ends of
  the side — are the vertices of a ``polygon.by_points`` of three vertices,
  ``{triangle}`` is that polygon; ``three_vertices``: a polygon of three
  vertices; ``number_mover``: a locus driven by a number). Without an
  entry the descriptive ``phrases.ru`` of the registry is used. ``phrases``
  (a dict of the same format, the web overlay) overrides entries by
  ``stepKind`` and the ``given`` phrases.
- Placeholders: ``{slot}`` — an input or parameter slot, else an output
  slot; ``{out:s1,s2}`` — the named outputs, joined by ``", "``; a
  placeholder without a name becomes empty (spaces are tidied).
- Names: a polygon of ``polygon.by_points`` by its vertices (``ABC``); an
  angle of ``angle.by_points`` and a right-angle mark — ``∠ABC``; an
  equality mark — its targets; a hidden or nameless segment, line, ray or
  vector — by the two points of its producer (``BC``); otherwise
  ``displayName``, else the ID. A list of points is written together
  (``ABC``), other lists with ``", "``.
- «Дано»: the free points and numbers of a ``given`` step — «Дано: точки
  A, B, C» (and «; числа k»); three points followed by the step of a
  ``polygon.by_points`` on exactly them — «Строим треугольник ABC», and that
  polygon step gets no line of its own.
- Conditions (1.9.0a2): a ``condition`` step is ``steps.condition.text``
  («Ставим {recipe}») with ``{recipe}`` — the ``phrase.ru`` of the recipe
  filled with the names of its bindings (a number literal in the decimal
  format below, ``D`` in degrees) — followed by the phrases of the marks in
  the step. An operation whose outputs are all hidden helpers of an
  automatic mark (``origin.kind = "auto"``) has no phrase.
- The phrase of an automatic mark joined after another one starts with a
  small letter («…; отмечаем прямой угол CHA»).
- ``values=True``: after the phrase of an operation, `` (… ; …)`` with the
  values now (``ev`` or an evaluation): a visible segment ``|AB| = 2,4``
  (by its two points when the producer has them),
  an angle ``∠ABC = 35°`` (its size), a number ``k = 1,5``; for a condition
  step, every ``len`` and three-point ``angle`` of the statement (convex
  degrees). Decimal comma, at most ``precision`` digits, trailing zeros
  dropped; an undefined value is skipped.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

from .document import as_document, iter_refs
from .registry import registry
from .steps import FREE_GIVEN, steps

__all__ = ['PHRASES_FORMAT', 'describe', 'phrase_table']

PHRASES_FORMAT = 'animageo-phrases/v1'
PHRASES_PATH = Path(__file__).resolve().parent / 'phrases' / 'ru.v1.json'
_TABLE = None
_PLACEHOLDER = re.compile(r'\{([^{}]+)\}')
_ENDS = {'segment.by_points': ('a', 'b'), 'line.by_points': ('a', 'b'), 'ray.by_points': ('origin', 'through'),
         'vector.by_points': ('a', 'b')}
_FOOT = {'triangle.altitude': 'foot', 'triangle.median': 'midpoint', 'triangle.bisector': 'foot'}


def phrase_table() -> dict:
    """The shipped phrase table (a copy)."""
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(PHRASES_PATH.read_text(encoding='utf-8'))
    return copy.deepcopy(_TABLE)


def _merged(phrases) -> dict:
    table = phrase_table()
    if phrases:
        if phrases.get('format', PHRASES_FORMAT) != PHRASES_FORMAT:
            raise ValueError(f'phrases must be {PHRASES_FORMAT}')
        table['steps'].update(phrases.get('steps') or {})
        table['given'].update(phrases.get('given') or {})
    return table


def _number(value, precision: int) -> str:
    v = float(value)
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    text = f'{v:.{precision}f}'.rstrip('0').rstrip('.')
    return text.replace('.', ',')


class _Namer:
    def __init__(self, doc, precision):
        self.doc = doc
        self.precision = precision
        appearance = doc.data.get('appearance')
        self.appearance = appearance if isinstance(appearance, dict) else {}
        self.triangles = None          # {frozenset(vertices): vertices}, built on first use

    def _producer(self, el_id):
        el = self.doc.elements[el_id]
        return self.doc.operations.get(el['producer']['operationId']), el['producer']['slot']

    def _hidden(self, el_id) -> bool:
        entry = self.appearance.get(el_id)
        return isinstance(entry, dict) and entry.get('visible') is False

    def _ref(self, op, slot):
        ids = list(iter_refs(op['args'].get(slot) or {}))
        return ids[0] if len(ids) == 1 and ids[0] in self.doc.elements else None

    def ends(self, el_id):
        """The names of the two defining points of a segment-like element, or ``None``."""
        op, slot = self._producer(el_id)
        if op is None:
            return None
        if op['op'] in _ENDS:
            refs = [self._ref(op, s) for s in _ENDS[op['op']]]
            if all(refs):
                return ''.join(self.name(r) for r in refs)
        if op['op'] in _FOOT and slot != _FOOT[op['op']]:
            vertex = self._ref(op, 'vertex')
            foot = next((o['elementId'] for o in op['outputs'] if o['slot'] == _FOOT[op['op']]), None)
            if vertex and foot and self._named(foot):
                return self.name(vertex) + self.name(foot)
        return None

    def _named(self, el_id) -> bool:
        name = self.doc.elements[el_id].get('displayName')
        return isinstance(name, str) and bool(name)

    def name(self, el_id) -> str:
        el = self.doc.elements[el_id]
        type_ = el['type']
        op, _slot = self._producer(el_id)
        name = el.get('displayName') if self._named(el_id) else None
        if op is not None:
            if type_ == 'polygon' and op['op'] == 'polygon.by_points':
                return self.join(list(iter_refs(op['args'].get('vertices') or {})))
            if (type_ == 'angle' and op['op'] == 'angle.by_points') or op['op'] == 'mark.right_angle':
                refs = [self._ref(op, s) for s in ('a', 'vertex', 'b')]
                if all(refs):
                    return '∠' + ''.join(self.name(r) for r in refs)
            if op['op'] in ('mark.equal_segments', 'mark.equal_angles'):
                slot = 'segments' if op['op'] == 'mark.equal_segments' else 'angles'
                return self.join(list(iter_refs(op['args'].get(slot) or {})))
        if type_ in ('segment', 'line', 'ray', 'vector') and (name is None or self._hidden(el_id)):
            ends = self.ends(el_id)
            if ends:
                return ends
        return name if name is not None else el_id

    def join(self, ids) -> str:
        ids = [i for i in ids if i in self.doc.elements]
        names = [self.name(i) for i in ids]
        if ids and all(self.doc.elements[i]['type'] == 'point' for i in ids):
            return ''.join(names)
        if len(names) > 1:
            return ', '.join(names[:-1]) + ' и ' + names[-1]
        return ''.join(names)


def _triangle_points(op, namer):
    args = op['args']
    if all(k in args for k in ('a', 'b', 'c')):
        refs = [namer._ref(op, k) for k in ('a', 'b', 'c')]
    elif 'vertex' in args and 'side' in args:
        side = namer._ref(op, 'side')
        refs = [namer._ref(op, 'vertex')]
        side_op = namer._producer(side)[0] if side else None
        if side_op is None or side_op['op'] not in _ENDS:
            return None
        refs += [namer._ref(side_op, s) for s in _ENDS[side_op['op']]]
    else:
        return None
    if not all(refs) or any(namer.doc.elements[r]['type'] != 'point' for r in refs):
        return None
    return refs


def _triangle_polygon(namer, points):
    """The vertices of the first ``polygon.by_points`` (by operation ID)
    whose three vertices are ``points``, or ``None``."""
    if namer.triangles is None:
        namer.triangles = {}
        for op_id in sorted(namer.doc.operations):
            op = namer.doc.operations[op_id]
            if op['op'] != 'polygon.by_points':
                continue
            vertices = list(iter_refs(op['args'].get('vertices') or {}))
            if len(vertices) == 3:
                namer.triangles.setdefault(frozenset(vertices), vertices)
    return namer.triangles.get(frozenset(points))


def _when(cond, op, namer, extra) -> bool:
    if cond == 'triangle_vertices':
        points = _triangle_points(op, namer)
        vertices = _triangle_polygon(namer, points) if points else None
        if vertices is None:
            return False
        extra['triangle'] = namer.join(vertices)
        return True
    if cond == 'three_vertices':
        return op['op'] == 'polygon.by_points' and len(list(iter_refs(op['args'].get('vertices') or {}))) == 3
    if cond == 'number_mover':
        mover = namer._ref(op, 'mover')
        return mover is not None and namer.doc.elements[mover]['type'] == 'number'
    return False


def _tidy(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([,.;:])', r'\1', text)
    text = re.sub(r',(\s*,)+', ',', text)
    return text.strip().rstrip(',;').strip()


def _fill(template, op, namer, extra) -> str:
    args = op['args']
    outputs = {o['slot']: o['elementId'] for o in op['outputs'] if o['elementId'] in namer.doc.elements}

    def one(key):
        if key.startswith('out:'):
            return ', '.join(namer.name(outputs[s]) for s in key[4:].split(',') if s in outputs)
        if key in extra:
            return extra[key]
        if key in args:
            arg = args[key]
            if not isinstance(arg, dict):
                return ''
            kind = arg.get('kind')
            if kind == 'ref':
                return namer.name(arg['elementId']) if arg['elementId'] in namer.doc.elements else ''
            if kind == 'list':
                return namer.join(list(iter_refs(arg)))
            if kind == 'number':
                return _number(arg['value'], namer.precision)
            return ''
        if key in outputs:
            return namer.name(outputs[key])
        return ''

    return _tidy(_PLACEHOLDER.sub(lambda m: one(m.group(1)), template))


def _op_phrase(doc, op_id, table, namer) -> str:
    op = doc.operations[op_id]
    record = registry().get(op['op'])
    if record is None:
        return op['op']
    entry = table['steps'].get(record.get('stepKind'))
    extra: dict = {}
    if not entry:
        return _fill(record.get('phrases', {}).get('ru', op['op']), op, namer, extra)
    for item in entry.get('context') or ():
        if item.get('op') not in (None, op['op']):
            continue
        if _when(item.get('when'), op, namer, extra):
            return _fill(item['text'], op, namer, extra)
    template = (entry.get('ops') or {}).get(op['op']) or entry['text']
    return _fill(template, op, namer, extra)


def _given_phrase(doc, step, table, namer):
    points, numbers = [], []
    for op_id in step.operationIds:
        op = doc.operations[op_id]
        if op['op'] not in FREE_GIVEN:
            return None
        for out in op['outputs']:
            if out['elementId'] in doc.elements:
                (points if op['op'] == 'point.free' else numbers).append(out['elementId'])
    given = table['given']
    parts = []
    if points:
        parts.append(_fill(given['point' if len(points) == 1 else 'points'],
                           {'args': {}, 'outputs': []}, namer, {'list': ', '.join(namer.name(p) for p in points)}))
    if numbers:
        text = _fill(given['number' if len(numbers) == 1 else 'numbers'], {'args': {}, 'outputs': []}, namer,
                     {'list': ', '.join(namer.name(n) for n in numbers)})
        if not points:
            text = _fill(given['numbers_only'], {'args': {}, 'outputs': []}, namer, {'numbers': text})
        parts.append(text)
    return '; '.join(parts), points, numbers


def _auto_helper(doc, namer, op_id) -> bool:
    outs = [o['elementId'] for o in doc.operations[op_id]['outputs'] if o['elementId'] in doc.elements]
    return bool(outs) and all(isinstance(doc.elements[e].get('origin'), dict)
                              and doc.elements[e]['origin'].get('kind') == 'auto' and namer._hidden(e) for e in outs)


def _condition(doc, step):
    ids = set(step.conditionIds)
    raw = doc.data.get('conditions')
    return next((c for c in raw if isinstance(c, dict) and c.get('id') in ids), None) if isinstance(raw, list) else None


def _condition_phrase(doc, cond, table, namer) -> str | None:
    from .conditions.recipes import matches
    entry = table['steps'].get('condition') or {'text': 'Ставим {recipe}'}
    for recipe, binds in matches(doc, cond.get('statement') or {}):
        if recipe['recipe'] != cond.get('recipe') or binds.get(recipe['receiver']) != cond.get('receiver'):
            continue

        def one(m):
            value = binds.get(m.group(1))
            if isinstance(value, str):
                return namer.name(value) if value in doc.elements else value
            if isinstance(value, tuple):
                kind, v = value
                return namer.name(v) if kind == 'ref' and v in doc.elements else _number(v, namer.precision)
            return ''
        text = _PLACEHOLDER.sub(one, recipe.get('phrase', {}).get('ru', recipe['recipe']))
        return _tidy(entry['text'].replace('{recipe}', text).replace('{receiver}', namer.name(cond['receiver'])))
    return None


def _deg(radians, precision) -> str:
    return _number(radians * 180 / math.pi, precision) + '°'


def _op_values(doc, op_id, namer, ev) -> list:
    out = []
    for o in doc.operations[op_id]['outputs']:
        el_id = o['elementId']
        if el_id not in doc.elements or namer._hidden(el_id):
            continue
        state = ev.elements.get(el_id)
        if state is None or state['state'] != 'defined':
            continue
        type_, value = doc.elements[el_id]['type'], state['value']
        if type_ == 'segment':
            out.append(f'|{namer.ends(el_id) or namer.name(el_id)}| = {_number(value["length"], namer.precision)}')
        elif type_ == 'angle':
            name = namer.name(el_id)
            out.append(f'{name if name.startswith("∠") else "∠" + name} = {_deg(value["size"], namer.precision)}')
        elif type_ == 'number':
            number = value.get('value') if isinstance(value, dict) else value
            if isinstance(number, (int, float)):
                out.append(f'{namer.name(el_id)} = {_number(number, namer.precision)}')
    return out


def _statement_values(doc, statement, namer, ev) -> list:
    from .conditions.statements import _convex_angle
    out = []

    def xy(el_id):
        state = ev.elements.get(el_id)
        if state is None or state['state'] != 'defined':
            return None
        v = state['value']
        return (v['x'], v['y']) if isinstance(v, dict) else (v[0], v[1])

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get('len'), dict) and isinstance(node['len'].get('pair'), list):
                p, q = node['len']['pair']
                a, b = xy(p), xy(q)
                if None not in (a, b):
                    text = f'|{namer.name(p)}{namer.name(q)}| = {_number(math.hypot(b[0] - a[0], b[1] - a[1]), namer.precision)}'
                    if text not in out:
                        out.append(text)
                return
            if isinstance(node.get('angle'), list) and len(node['angle']) == 3:
                ids = [x.get('ref') for x in node['angle'] if isinstance(x, dict)]
                pts = [xy(i) for i in ids] if len(ids) == 3 else [None]
                if None not in pts:
                    text = f'∠{"".join(namer.name(i) for i in ids)} = {_deg(_convex_angle(*pts), namer.precision)}'
                    if text not in out:
                        out.append(text)
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(statement)
    return out


def _lower(text) -> str:
    return text[:1].lower() + text[1:]


def _auto_mark(doc, op_id) -> bool:
    return doc.operations[op_id]['op'].startswith('mark.') and any(
        isinstance(doc.elements.get(o['elementId'], {}).get('origin'), dict)
        and doc.elements[o['elementId']]['origin'].get('kind') == 'auto' for o in doc.operations[op_id]['outputs'])


def _with_values(text, items) -> str:
    return f'{text} ({"; ".join(items)})' if items else text


def describe(doc, *, values: bool = False, phrases=None, ev=None, precision: int = 2) -> list:
    """The lines of the construction (see the module docstring)."""
    doc = as_document(doc)
    if values and ev is None:
        from .kernel.evaluate import evaluate
        ev = evaluate(doc)
    table = _merged(phrases)
    namer = _Namer(doc, precision)
    order = steps(doc)
    lines = []
    n = 0
    skip = None
    for index, step in enumerate(order):
        if step.id == skip:
            continue
        n += 1
        if step.text is not None:
            if step.title is not None:
                lines += [f'{n}. {step.title}.', f'{n}.1. {step.text}.']
            else:
                lines.append(f'{n}. {step.text}.')
            continue
        if step.kind == 'given':
            given = _given_phrase(doc, step, table, namer)
            if given is not None:
                text, points, numbers = given
                nxt = order[index + 1] if index + 1 < len(order) else None
                if len(points) == 3 and not numbers and nxt is not None and nxt.kind == 'op':
                    op = doc.operations[nxt.operationIds[0]]
                    vertices = list(iter_refs(op['args'].get('vertices') or {})) \
                        if op['op'] == 'polygon.by_points' else []
                    if len(vertices) == 3 and set(vertices) == set(points):
                        text = _fill(table['given']['triangle'], {'args': {}, 'outputs': []}, namer,
                                     {'name': namer.join(vertices)})
                        skip = nxt.id
                lines.append(f'{n}. {text}.')
                continue
        cond = _condition(doc, step) if step.kind == 'condition' else None
        head = _condition_phrase(doc, cond, table, namer) if cond is not None else None
        if head is not None:
            ops = [o for o in step.operationIds if doc.operations[o]['op'].startswith('mark.')]
            if values:
                head = _with_values(head, _statement_values(doc, cond.get('statement'), namer, ev))
            phrases_ = [head] + [_lower(_op_phrase(doc, op_id, table, namer)) for op_id in ops]
        else:
            ops = [o for o in step.operationIds if not _auto_helper(doc, namer, o)]
            phrases_ = [_op_phrase(doc, op_id, table, namer) for op_id in ops]
            phrases_ = [_lower(p) if k and _auto_mark(doc, o) else p
                        for k, (p, o) in enumerate(zip(phrases_, ops))]
            if values:
                phrases_ = [_with_values(p, _op_values(doc, o, namer, ev)) for p, o in zip(phrases_, ops)]
        if step.title is not None:
            lines.append(f'{n}. {step.title}.')
            lines += [f'{n}.{k}. {p}.' for k, p in enumerate(phrases_, start=1)]
        else:
            lines.append(f'{n}. ' + '; '.join(phrases_) + '.')
    return lines
