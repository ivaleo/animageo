"""Automatic marks (plan L3 §3.7, docs/native/conditions.md §6).

``auto_marks(doc, sources, *, ev, id_factory) → [operation]`` proposes the
marks of operations and conditions (table ``animageo/native/marks/auto.v1.json``);
``add_auto_marks`` puts them into the document. Computational: the far end of
a side and the classes of equality need values.

Contract (shared with the web):

- a source is an operation ID or a condition ID; sources are taken in the
  given order, the marks of one source in the order of the table;
- a pair ``(source, kind)`` listed in ``suppressedMarks`` gives nothing; nor
  does a source that already has an automatic mark of that kind;
- right angle ``(V, H, X)``: ``X`` is the end of the side farther from ``H``
  now, ``b`` (the second defining point) on a tie;
- a segment of a mark is an existing ``segment.by_points`` on the same two
  points (either order, the smallest operation ID), else a new hidden one;
  an angle is a new hidden ``angle.by_points`` oriented to be convex now
  (``(a, v, b)`` when ``(a − v) × (b − v) ≥ 0``, else ``(b, v, a)``);
- class of equality (``count``): the count of an already marked equality of
  the same kind whose value is equal now (within ``check.passed``; lengths,
  convex angles × S), else the smallest of 1–3 not taken; all taken —
  ``count = 3`` and the warning ``mark_classes_exhausted``;
- new elements: the mark gets ``origin: {kind: "auto", source}``; the new
  helper segments and angles get the same ``origin`` (so that they go with
  the source) and ``appearance {visible: false, role: "aux"}``;
- IDs: ``id_factory(kind, hint)`` or ``mark_<source>`` … (see ``_Ids``);
  every new operation gets the next ``seq``.
"""
from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from ..document import NativeDocument, as_document, iter_refs

__all__ = ['auto_marks', 'add_auto_marks', 'auto_sources', 'AutoMarks', 'mark_table']

TABLE_PATH = Path(__file__).resolve().parent.parent / 'marks' / 'auto.v1.json'
TABLE_FORMAT = 'animageo-auto-marks/v1'
KIND_OP = {'right_angle': 'mark.right_angle', 'equal_segments': 'mark.equal_segments',
           'equal_angles': 'mark.equal_angles'}
TWO_PI = 2 * math.pi


@lru_cache(maxsize=1)
def _table() -> dict:
    data = json.loads(TABLE_PATH.read_text(encoding='utf-8'))
    if data.get('format') != TABLE_FORMAT:
        raise ValueError(f'{TABLE_PATH.name}: not {TABLE_FORMAT}')
    return data


def mark_table() -> dict:
    """The table of sources (a copy)."""
    return copy.deepcopy(_table())


class AutoMarks(NamedTuple):
    """``document`` with the marks; ``operations`` — the new operations;
    ``elements`` — the new element IDs; ``warnings``."""

    document: NativeDocument
    operations: list
    elements: list
    warnings: list


def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _xy(ev, el_id):
    state = ev.elements.get(el_id) if el_id is not None else None
    if state is None or state['state'] != 'defined':
        return None
    v = state['value']
    return (v['x'], v['y']) if isinstance(v, dict) else (v[0], v[1])


def _visible(data, el_id) -> bool:
    entry = (data.get('appearance') or {}).get(el_id)
    return not (isinstance(entry, dict) and entry.get('visible') is False)


def _arg_ref(op, slot):
    refs = list(iter_refs((op.get('args') or {}).get(slot) or {}))
    return refs[0] if len(refs) == 1 else None


def _out(op, slot):
    return next((o['elementId'] for o in op['outputs'] if o['slot'] == slot), None)


def _ends(data, el_id):
    """The two defining points of a linear element: the two point arguments
    of its producer, in argument order (``a``, ``b`` …); else ``None``."""
    el = data['elements'].get(el_id)
    if el is None:
        return None
    op = data['operations'].get(el['producer']['operationId'])
    if op is None:
        return None
    if op['op'] == 'polygon.by_points':
        vertices = list(iter_refs(op['args'].get('vertices') or {}))
        slot = el['producer']['slot']
        if slot.startswith('side.') and vertices:
            k = int(slot.split('.')[1]) - 1
            return vertices[k % len(vertices)], vertices[(k + 1) % len(vertices)]
        return None
    points = [r for _slot, arg in sorted(op['args'].items()) for r in iter_refs(arg)
              if data['elements'].get(r, {}).get('type') == 'point']
    return (points[0], points[1]) if len(points) == 2 and points[0] != points[1] else None


def _far_end(ev, h, ends):
    a, b = ends
    ph, pa, pb = _xy(ev, h), _xy(ev, a), _xy(ev, b)
    if None in (ph, pa, pb):
        return b
    da = math.hypot(pa[0] - ph[0], pa[1] - ph[1])
    db = math.hypot(pb[0] - ph[0], pb[1] - ph[1])
    return a if da > db else b


def _center(data, circle_id):
    el = data['elements'].get(circle_id)
    if el is None:
        return None
    op = data['operations'].get(el['producer']['operationId'])
    if op is None:
        return None
    if 'center' in (op.get('args') or {}):
        return _arg_ref(op, 'center')
    return _out(op, 'center')


# ── what a source asks for ────────────────────────────────────────────────
# A request: ('right_angle', (A, V, B)) | ('equal_segments', [(P, Q), …])
#          | ('equal_angles', [(A, V, B), …]) | ('equal_angles_on_line', (a, v, b, line))

def _op_requests(data, op, entry, ev) -> list:
    rule = entry['rule']
    if rule == 'foot':
        v, h, side = _arg_ref(op, entry['point']), _out(op, entry['foot']), _arg_ref(op, entry['side'])
        ends = _ends(data, side) if side else None
        if None in (v, h) or ends is None:
            return []
        if entry.get('requires') == 'visible_segment' and not _has_segment(data, v, h, visible=True):
            return []
        return [('right_angle', (v, h, _far_end(ev, h, ends)))]
    if rule == 'perpendicular':
        p, line, side = _arg_ref(op, entry['point']), _out(op, entry['line']), _arg_ref(op, entry['side'])
        ends = _ends(data, side) if side else None
        if None in (p, line, side) or ends is None:
            return []
        h = _meeting(data, line, side)
        if h is None or (_xy(ev, p) is not None and _xy(ev, h) is not None and
                         math.hypot(_xy(ev, p)[0] - _xy(ev, h)[0], _xy(ev, p)[1] - _xy(ev, h)[1]) <= ev.tolerances.decide_length):
            return []
        return [('right_angle', (p, h, _far_end(ev, h, ends)))]
    if rule == 'thales':
        a, b, circle = _arg_ref(op, entry['a']), _arg_ref(op, entry['b']), _out(op, entry['circle'])
        if None in (a, b, circle):
            return []
        out = []
        for oid in sorted(data['operations']):
            other = data['operations'][oid]
            if other['op'] == 'point.on_path' and _arg_ref(other, 'path') == circle:
                c = _out(other, 'point')
                if c is not None and _visible(data, c):
                    out.append(('right_angle', (a, c, b)))
        return out
    if rule == 'touch':
        p, circle = _arg_ref(op, entry['point']), _arg_ref(op, entry['circle'])
        o = _center(data, circle) if circle else None
        if None in (p, o) or not _visible(data, o):
            return []
        return [('right_angle', (p, t, o)) for slot in entry['touch'] for t in [_out(op, slot)] if t is not None]
    if rule == 'halves':
        m = _out(op, entry['midpoint'])
        if 'side' in entry:
            ends = _ends(data, _arg_ref(op, entry['side']) or '')
        else:
            ends = (_arg_ref(op, entry['a']), _arg_ref(op, entry['b']))
        if m is None or ends is None or None in ends:
            return []
        return [('equal_segments', [(ends[0], m), (m, ends[1])])]
    if rule == 'bisector':
        v, f = _arg_ref(op, entry['vertex']), _out(op, entry['foot'])
        ends = _ends(data, _arg_ref(op, entry['side']) or '')
        if None in (v, f) or ends is None:
            return []
        return [('equal_angles', [(ends[0], v, f), (f, v, ends[1])])]
    if rule == 'angle_bisector':
        a, v, b, line = (_arg_ref(op, entry['a']), _arg_ref(op, entry['vertex']), _arg_ref(op, entry['b']),
                         _out(op, entry['line']))
        if None in (a, v, b, line):
            return []
        return [('equal_angles_on_line', (a, v, b, line))]
    raise ValueError(f'unknown mark rule {rule!r}')


def _has_segment(data, p, q, *, visible=False):
    seg = _segment_of(data, p, q)
    return seg is not None and (not visible or _visible(data, seg))


def _segment_of(data, p, q):
    for oid in sorted(data['operations']):
        op = data['operations'][oid]
        if op['op'] == 'segment.by_points' and {_arg_ref(op, 'a'), _arg_ref(op, 'b')} == {p, q}:
            seg = _out(op, 'segment')
            if seg is not None:
                return seg
    return None


def _meeting(data, first, second):
    """A visible ``intersect.line_line`` point of ``first`` and ``second``."""
    for oid in sorted(data['operations']):
        op = data['operations'][oid]
        if op['op'] == 'intersect.line_line' and {_arg_ref(op, 'first'), _arg_ref(op, 'second')} == {first, second}:
            h = _out(op, 'point')
            if h is not None and _visible(data, h):
                return h
    return None


def _pair(node):
    if isinstance(node, dict) and isinstance(node.get('pair'), list) and len(node['pair']) == 2:
        return tuple(node['pair'])
    return None


def _angle3(node):
    if isinstance(node, dict) and isinstance(node.get('angle'), list) and len(node['angle']) == 3 \
            and all(isinstance(x, dict) and isinstance(x.get('ref'), str) for x in node['angle']):
        return tuple(x['ref'] for x in node['angle'])
    return None


def _condition_requests(cond, mark) -> list:
    st = cond.get('statement') or {}
    if mark == 'equal_segments' and st.get('kind') == 'eq':
        pairs = [_pair(side.get('len')) if isinstance(side, dict) else None for side in (st['left'], st['right'])]
        return [('equal_segments', pairs)] if None not in pairs else []
    if mark == 'right_angle':
        if st.get('kind') == 'eq':
            for side, other in ((st['left'], st['right']), (st['right'], st['left'])):
                three = _angle3(side)
                if three and isinstance(other, dict) and other.get('deg') == 90:
                    return [('right_angle', three)]
            return []
        if st.get('kind') == 'perpendicular':
            a, b = _pair(st.get('a')), _pair(st.get('b'))
            if a is None or b is None:
                return []
            common = set(a) & set(b)
            if len(common) != 1:
                return []
            v = common.pop()
            return [('right_angle', (next(x for x in a if x != v), v, next(x for x in b if x != v)))]
    if mark == 'equal_angles' and st.get('kind') == 'eq':
        angles = [_angle3(st['left']), _angle3(st['right'])]
        return [('equal_angles', angles)] if None not in angles else []
    return []


# ── building ──────────────────────────────────────────────────────────────

class _Builder:
    def __init__(self, data, ev, id_factory):
        self.data = data
        self.ev = ev
        self.factory = id_factory
        self.used = set(data['operations']) | set(data['elements']) | \
            {c.get('id') for c in data.get('conditions') or () if isinstance(c, dict)}
        self.seq = max([op.get('seq', 0) for op in data['operations'].values() if isinstance(op.get('seq'), int)] +
                       [c.get('seq', 0) for c in data.get('conditions') or ()
                        if isinstance(c, dict) and isinstance(c.get('seq'), int)] + [0])
        self.new_ops: list = []
        self.new_elements: list = []

    def make(self, kind, hint):
        if self.factory is not None:
            new = self.factory(kind, hint)
            if new in self.used:
                raise ValueError(f'id_factory gave {new!r}, which is taken')
        else:
            new, n = hint, 1
            while new in self.used:
                n += 1
                new = f'{hint}_{n}'
        self.used.add(new)
        return new

    def add(self, name, args, slot, type_, hint, source, hidden):
        op_id = self.make('operation', 'op_' + hint)
        el_id = self.make('element', hint)
        self.seq += 1
        op = {'id': op_id, 'op': name, 'args': args, 'outputs': [{'slot': slot, 'elementId': el_id}],
              'seq': self.seq}
        self.data['operations'][op_id] = op
        self.data['elements'][el_id] = {'id': el_id, 'type': type_, 'producer': {'operationId': op_id, 'slot': slot},
                                        'displayName': '', 'origin': {'kind': 'auto', 'source': source}}
        if hidden:
            self.data.setdefault('appearance', {})[el_id] = {'visible': False, 'role': 'aux'}
        self.new_ops.append(op)
        self.new_elements.append(el_id)
        return el_id


def _length(ev, p, q):
    a, b = _xy(ev, p), _xy(ev, q)
    return None if None in (a, b) else math.hypot(b[0] - a[0], b[1] - a[1])


def _convex(ev, a, v, b):
    pa, pv, pb = _xy(ev, a), _xy(ev, v), _xy(ev, b)
    if None in (pa, pv, pb):
        return None
    t = abs(math.atan2((pa[0] - pv[0]) * (pb[1] - pv[1]) - (pa[1] - pv[1]) * (pb[0] - pv[0]),
                       (pa[0] - pv[0]) * (pb[0] - pv[0]) + (pa[1] - pv[1]) * (pb[1] - pv[1])))
    return t


def _oriented(ev, a, v, b):
    pa, pv, pb = _xy(ev, a), _xy(ev, v), _xy(ev, b)
    if None in (pa, pv, pb):
        return a, v, b
    cross = (pa[0] - pv[0]) * (pb[1] - pv[1]) - (pa[1] - pv[1]) * (pb[0] - pv[0])
    return (a, v, b) if cross >= 0 else (b, v, a)


def _classes(data, ev, kind) -> list:
    """``[(count, value)]`` of the marks of ``kind`` in ``data`` now."""
    op_name = KIND_OP[kind]
    slot = 'segments' if kind == 'equal_segments' else 'angles'
    out = []
    for oid in sorted(data['operations']):
        op = data['operations'][oid]
        if op['op'] != op_name:
            continue
        raw = (op.get('args') or {}).get('count')
        count = raw.get('value', 1) if isinstance(raw, dict) else 1
        items = list(iter_refs(op['args'].get(slot) or {}))
        if not items:
            continue
        state = ev.elements.get(items[0])
        if state is None or state['state'] != 'defined':
            continue
        value = state['value']
        if kind == 'equal_segments':
            out.append((count, value['length']))
        else:
            size = value['size']
            out.append((count, min(size, TWO_PI - size) * ev.scale))
    return out


def _count(data, ev, kind, value, warnings, made=()) -> int:
    """``made``: ``(kind, count, value)`` of the marks of this call (not in ``ev``)."""
    classes = _classes(data, ev, kind) + [(c, v) for k, c, v in made if k == kind and v is not None]
    if value is not None:
        for count, other in classes:
            if abs(other - value) <= ev.tolerances.check_passed:
                return count
    taken = {c for c, _ in classes}
    for count in (1, 2, 3):
        if count not in taken:
            return count
    warnings.append('mark_classes_exhausted')
    return 3


def _suppressed(data) -> set:
    raw = data.get('suppressedMarks')
    return {(m.get('source'), m.get('kind')) for m in raw if isinstance(m, dict)} if isinstance(raw, list) else set()


def _has_auto(data, source, kind) -> bool:
    for el in data['elements'].values():
        origin = el.get('origin')
        if isinstance(origin, dict) and origin.get('kind') == 'auto' and origin.get('source') == source:
            op = data['operations'].get(el['producer']['operationId'])
            if op is not None and op['op'] == KIND_OP[kind]:
                return True
    return False


def _requests(data, source, ev) -> list:
    table = _table()
    if source in data['operations']:
        op = data['operations'][source]
        entry = table['ops'].get(op['op'])
        return _op_requests(data, op, entry, ev) if entry else []
    cond = next((c for c in data.get('conditions') or () if isinstance(c, dict) and c.get('id') == source), None)
    if cond is None:
        raise ValueError(f'{source!r} is neither an operation nor a condition')
    if cond.get('mode') != 'construct':
        return []
    entry = table['conditions'].get(cond.get('recipe'))
    return _condition_requests(cond, entry['mark']) if entry else []


def _build(doc, sources, ev, id_factory):
    from ..kernel.evaluate import evaluate
    doc = as_document(doc)
    ev = ev if ev is not None else evaluate(doc)
    from ..edit import json_copy
    data = json_copy(doc.data)
    builder = _Builder(data, ev, id_factory)
    made: list = []
    warnings: list = []
    suppressed = _suppressed(data)
    for source in sources:
        done_kinds = set()
        for kind, spec in _requests(data, source, ev):
            mark_kind = 'equal_angles' if kind == 'equal_angles_on_line' else kind
            if (source, mark_kind) in suppressed or (mark_kind not in done_kinds and _has_auto(data, source, mark_kind)):
                continue
            done_kinds.add(mark_kind)
            hint = f'mark_{source}'
            if kind == 'right_angle':
                a, v, b = spec
                if len({a, v, b}) < 3:
                    continue
                builder.add('mark.right_angle', {'a': _ref(a), 'vertex': _ref(v), 'b': _ref(b)}, 'mark', 'mark',
                            hint, source, False)
            elif kind == 'equal_segments':
                if any(p == q for p, q in spec):
                    continue
                segments = []
                for p, q in spec:
                    seg = _segment_of(data, p, q)
                    if seg is None:
                        seg = builder.add('segment.by_points', {'a': _ref(p), 'b': _ref(q)}, 'segment', 'segment',
                                          f'aux_{source}', source, True)
                    segments.append(seg)
                value = _length(ev, *spec[0])
                count = _count(data, ev, 'equal_segments', value, warnings, made)
                made.append(('equal_segments', count, value))
                builder.add('mark.equal_segments', {'segments': {'kind': 'list', 'items': [_ref(s) for s in segments]},
                                                    'count': {'kind': 'number', 'value': count}},
                            'mark', 'mark', hint, source, False)
            else:
                if kind == 'equal_angles_on_line':
                    a, v, b, line = spec
                    chord = _segment_of(data, a, b) or builder.add(
                        'segment.by_points', {'a': _ref(a), 'b': _ref(b)}, 'segment', 'segment', f'aux_{source}',
                        source, True)
                    f = builder.add('intersect.line_line', {'first': _ref(line), 'second': _ref(chord)}, 'point',
                                    'point', f'aux_{source}', source, True)
                    ev = evaluate(NativeDocument(data))
                    builder.ev = ev
                    spec = [(a, v, f), (f, v, b)]
                if any(len(set(t)) < 3 for t in spec):
                    continue
                angles = []
                for t in spec:
                    angles.append(builder.add('angle.by_points', dict(zip(('a', 'vertex', 'b'),
                                                                           map(_ref, _oriented(ev, *t)))),
                                              'angle', 'angle', f'aux_{source}', source, True))
                convex = _convex(ev, *spec[0])
                value = None if convex is None else convex * ev.scale
                count = _count(data, ev, 'equal_angles', value, warnings, made)
                made.append(('equal_angles', count, value))
                builder.add('mark.equal_angles', {'angles': {'kind': 'list', 'items': [_ref(x) for x in angles]},
                                                  'count': {'kind': 'number', 'value': count}},
                            'mark', 'mark', hint, source, False)
    return data, builder, warnings


def auto_marks(doc, sources, *, ev=None, id_factory=None) -> list:
    """The new operations (helpers, then the mark; source by source) of the
    automatic marks of ``sources`` (operation or condition IDs)."""
    _data, builder, _warnings = _build(doc, list(sources), ev, id_factory)
    return copy.deepcopy(builder.new_ops)


def add_auto_marks(doc, sources, *, ev=None, id_factory=None) -> AutoMarks:
    """:func:`auto_marks` put into a copy of the document."""
    data, builder, warnings = _build(doc, list(sources), ev, id_factory)
    return AutoMarks(NativeDocument(data), copy.deepcopy(builder.new_ops), list(builder.new_elements),
                     sorted(set(warnings)))


def auto_sources(doc) -> list:
    """Every operation whose op is in the table and every construct condition
    with a recipe in the table — the sources of «Отметить автоматически» for
    a whole document (operation IDs sorted, then conditions in order)."""
    doc = as_document(doc)
    table = _table()
    out = [oid for oid in sorted(doc.operations) if doc.operations[oid]['op'] in table['ops']]
    raw = doc.data.get('conditions')
    for cond in raw if isinstance(raw, list) else ():
        if isinstance(cond, dict) and cond.get('mode') == 'construct' and cond.get('recipe') in table['conditions']:
            out.append(cond['id'])
    return out

