"""``parse_commands``: text of «Команды» → a construction document
(commands.md §3–§4, §8).

Lines run top to bottom; a line that fails is skipped with an issue and the
document is built from the rest. With ``base`` the text edits that document:
a line matches the operation that produced the element named first on its
left (or, for a line without such a name, an unnamed operation of ``base``
with the same definition), IDs are kept, and operations of ``base`` left
without a line are deleted with everything built on them.
"""
from __future__ import annotations

import copy
import inspect
import os
import re
import threading
import time
import uuid
from typing import NamedTuple

from ..canonical import canonical_json
from ..document import DOCUMENT_FORMAT, ID_RE, NativeDocument, as_document, iter_refs
from ..edit import EditError, _effects, _finish, delete, name_key, redefine, valid_name
from ..registry import FREE_INPUT_DEFAULTS, REGISTRY_VERSION, registry
from .issues import CommandIssue, LineError, ambiguous_name
from .lexer import tokenize
from .lexicon import ANGLE3, INPUT, NOT, NUM, PAIR, PT, Lexicon, as_lexicon, normalize_name
from .naming import TakenKeys, next_name, pair_readings, polygon_side_names, suggest_name
from .resolve import closest_name, kind_text, resolve
from .syntax import parse_line

__all__ = ['ParseResult', 'parse_commands', 'HELPER_OPS', 'helper_key', 'is_helper', 'pair_op', 'time_ordered_id']

HELPER_OPS = {
    'segment.by_points': ('a', 'b'),
    'line.by_points': ('a', 'b'),
    'angle.by_points': ('a', 'vertex', 'b'),
}


_CLOCK = threading.Lock()
_LAST = [0, -1]


def time_ordered_id() -> str:
    """A UUID with the version 7 layout, increasing within the process.

    The printer orders independent lines by operation ID (commands.md §6), so
    default IDs that grow in creation order keep lines where they were typed.
    """
    with _CLOCK:
        ms = time.time_ns() // 1_000_000
        if ms <= _LAST[0]:
            ms, seq = _LAST[0], _LAST[1] + 1
            if seq > 0xFFF:
                ms, seq = ms + 1, 0
        else:
            seq = 0
        _LAST[0], _LAST[1] = ms, seq
    rand = int.from_bytes(os.urandom(8), 'big') & ((1 << 62) - 1)
    value = ((ms & ((1 << 48) - 1)) << 80) | (0x7 << 76) | (seq << 64) | (0b10 << 62) | rand
    return str(uuid.UUID(int=value))


class ParseResult(NamedTuple):
    """``document`` — a :class:`NativeDocument`; ``effects`` — what changed
    against ``base`` (the shape of :mod:`animageo.native.edit`; everything is
    ``added`` for a new document); ``lines`` — ``[{line, operationIds,
    elementIds}]`` for the lines that stand for an operation, plus ``[{line,
    operationIds: [], elementIds: [], conditionId}]`` for a ``Проверить`` line
    and an ``Условие`` line kept as it is; ``issues`` — :class:`CommandIssue`
    by line and column; ``conditionRequests`` — ``[{line, kind: "apply" |
    "release" | "replace" | "move", statement?, receiver?, conditionId?,
    point?}]`` for the caller to carry out
    (:func:`animageo.native.commands.apply_condition_requests`); ``queries`` —
    ``[{line, kind: "relation", a, b}]`` of ``Отношение(a, b)``."""

    document: NativeDocument
    effects: dict
    lines: list
    issues: list
    conditionRequests: list = []
    queries: list = []


def helper_key(op: dict):
    """``(op, point IDs)`` of an operation that a pair or ``∠ABC`` could
    stand for (one of ``HELPER_OPS`` with element refs), or ``None``."""
    slots = HELPER_OPS.get(op.get('op'))
    args = op.get('args') or {}
    if slots is None or len(args) != len(slots):
        return None
    points = []
    for slot in slots:
        arg = args.get(slot)
        if not isinstance(arg, dict) or arg.get('kind') != 'ref':
            return None
        points.append(arg.get('elementId'))
    return op['op'], tuple(points)


def is_helper(data: dict, op_id: str) -> bool:
    """A hidden operation of a pair of points or of ``∠ABC``:
    ``segment.by_points``, ``line.by_points`` or ``angle.by_points`` whose
    outputs all have ``displayName: ""`` and ``appearance[id].visible = false``."""
    op = (data.get('operations') or {}).get(op_id)
    if not isinstance(op, dict) or op.get('op') not in HELPER_OPS:
        return False
    outputs = op.get('outputs') or []
    if not outputs:
        return False
    elements = data.get('elements') or {}
    appearance = data.get('appearance') or {}
    for out in outputs:
        el = elements.get(out.get('elementId'))
        if not isinstance(el, dict) or el.get('displayName') != '':
            return False
        look = appearance.get(out.get('elementId'))
        if not (isinstance(look, dict) and look.get('visible') is False):
            return False
    return True


def pair_op(position_type: str) -> str:
    """The operation a pair of points stands for in a slot of ``position_type``:
    ``segment.by_points`` when the slot takes a segment but not a line,
    ``line.by_points`` otherwise."""
    reg = registry()
    types = {position_type, *reg.families.get(position_type, ())}
    return 'segment.by_points' if 'segment' in types and 'line' not in types else 'line.by_points'


class _Helper:
    """A pair of points or ``∠ABC`` in an argument, before it becomes an element."""

    __slots__ = ('op', 'points')

    def __init__(self, op, points):
        self.op = op
        self.points = tuple(points)


class _Request(NamedTuple):
    op: str
    record: dict
    args: dict               # slot → argument JSON, a _Helper in place of a ref
    input: object            # the free input JSON or None
    command: str


def _version_tuple(text):
    try:
        return tuple(int(p) for p in str(text).split('.'))
    except ValueError:
        return (0,)


def _claim_names(line: str):
    """Left names of a line that may not parse: the names before the first
    ``=`` when they are a plain list."""
    text = line.split('#', 1)[0]
    if '=' not in text:
        return []
    left = text.split('=', 1)[0]
    try:
        tokens, _ = tokenize(left)
    except LineError:
        return []
    names = []
    for i, tok in enumerate(tokens):
        if i % 2 == 0 and tok.kind == 'name':
            names.append(tok.text)
        elif not (i % 2 == 1 and tok.kind == 'sym' and tok.text == ','):
            return []
    return names


_REFUSALS = {
    'type_mismatch': 'новый тип выхода не подходит строкам, которые его используют',
    'cycle': 'аргумент построен из этой же строки',
    'slot_conflict': 'два имени слева попадают в один выход',
    'missing_input': 'нет значения свободного входа',
    'input_not_free': 'значение задано не свободному выходу',
}


def _refusal_text(issue, data: dict) -> str:
    """A message for a refusal of :func:`redefine`."""
    text = _REFUSALS.get(issue.code)
    if text is None:
        return f'строку нельзя применить: {issue.message}'
    if issue.code == 'type_mismatch':
        users = re.findall(r"'([^']+)'", issue.message)
        names = []
        for op_id in users:
            op = (data.get('operations') or {}).get(op_id) or {}
            for out in op.get('outputs') or ():
                name = ((data.get('elements') or {}).get(out.get('elementId')) or {}).get('displayName')
                if name and name not in names:
                    names.append(name)
        if names:
            text += f' ({", ".join(names)})'
    return f'строку нельзя применить: {text}'


def _signature(line: str):
    """The tokens of a line without its comment, or ``None`` if it does not lex."""
    try:
        tokens, _ = tokenize(line)
    except LineError:
        return None
    return tuple((t.kind, t.text) for t in tokens) or None


class _Builder:
    def __init__(self, lexicon: Lexicon, base, id_factory, document_id):
        self.lex = lexicon
        self.reg = registry()
        if base is None:
            self.base = {
                'format': DOCUMENT_FORMAT,
                'documentId': document_id or str(uuid.uuid4()),
                'operationRegistryVersion': REGISTRY_VERSION,
                'operations': {},
                'elements': {},
                'inputs': {},
            }
            self.editing = False
        else:
            self.base = as_document(base).data
            self.editing = True
        self.W = copy.deepcopy(self.base)
        self.W.setdefault('operations', {})
        self.W.setdefault('elements', {})
        self.used_ids = set(self.W['operations']) | set(self.W['elements'])
        self.factory = id_factory
        self.factory_takes_kind = self._takes_kind(id_factory)
        self.issues = []
        self.scope = set()
        self.claims = {}            # line → base operation ID (by the first left name)
        self.matched = set()        # base operations that have a line
        self.pending = set()        # elements of base operations without a line: their names are free
        self.nameless = set()       # base operations without named outputs (matched by definition)
        self.reserved = set()       # name keys written on the left anywhere in the text
        self.defined_at = {}        # name key → the first line that writes it on the left
        self.line_no = 0
        self.lines = []
        self.warnings = []
        self._index = None          # name key → {element ID: None}: the named elements of W
        self._scope_index = None    # name key → element ID: the elements in scope
        self._scope_points = None   # the same, points only
        self._helper_index = None   # (op, point IDs) → [operation ID]: pair-like operations
        # 1.9.0a3: conditions, checks, queries and steps from comments
        self.requests = []
        self.queries = []
        self.condition_lines = []   # [{line, operationIds: [], elementIds: [], conditionId}]
        self.kept_conditions = set()        # base construct conditions with an unchanged line
        self.kept_checks = set()            # base check conditions with a line
        self.new_checks = []
        self.receiver_ops = {}              # receiver op ID → [construct condition]
        self.comments = {}                  # line → (text, comment only)
        self.failed_conditions = 0          # Условие lines with an error: they keep a condition each

    # ── IDs ──────────────────────────────────────────────────────────────

    @staticmethod
    def _takes_kind(factory) -> bool:
        if factory is None:
            return False
        try:
            params = inspect.signature(factory).parameters.values()
        except (TypeError, ValueError):
            return True
        return any(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL) for p in params)

    def new_id(self, kind: str) -> str:
        for _ in range(100000):
            if self.factory is None:
                value = time_ordered_id()
            elif self.factory_takes_kind:
                value = self.factory(kind)
            else:
                value = self.factory()
            if not isinstance(value, str) or not ID_RE.match(value):
                raise ValueError(f'id_factory returned {value!r}, not an ID ([A-Za-z0-9_-]{{1,64}})')
            if value not in self.used_ids:
                self.used_ids.add(value)
                return value
        raise ValueError('id_factory keeps returning IDs that are in use')

    # ── names ────────────────────────────────────────────────────────────

    # The indexes below grow with every line and are rebuilt (lazily) only
    # when ``W`` is replaced by ``redefine``: a text of n lines parses in
    # about linear time.

    def _dirty(self):
        """``W`` was replaced: rebuild the indexes when next needed."""
        self._index = self._scope_index = self._scope_points = self._helper_index = None

    def _name_index(self) -> dict:
        if self._index is None:
            index = {}
            for el_id, el in self.W['elements'].items():
                name = el.get('displayName') if isinstance(el, dict) else None
                if isinstance(name, str) and name:
                    index.setdefault(name_key(name), {})[el_id] = None
            self._index = index
        return self._index

    def _set_name(self, el_id: str, name: str) -> None:
        el = self.W['elements'][el_id]
        old = el.get('displayName')
        if old == name:
            return
        el['displayName'] = name
        if self._index is not None:
            if isinstance(old, str) and old:
                ids = self._index.get(name_key(old))
                if ids is not None:
                    ids.pop(el_id, None)
                    if not ids:
                        del self._index[name_key(old)]
            if name:
                self._index.setdefault(name_key(name), {})[el_id] = None
        if el_id in self.scope:
            self._scope_index = self._scope_points = None

    def _note_scope(self, el_id: str) -> None:
        if self._scope_index is None:
            return
        el = self.W['elements'].get(el_id)
        name = el.get('displayName') if isinstance(el, dict) else None
        if isinstance(name, str) and name:
            key = name_key(name)
            if key not in self._scope_index:
                self._scope_index[key] = el_id
                if el.get('type') == 'point':
                    self._scope_points[key] = el_id

    def _scope_names(self) -> dict:
        if self._scope_index is None:
            self._scope_index, self._scope_points = {}, {}
            for el_id in self.W['elements']:
                if el_id in self.scope:
                    self._note_scope(el_id)
        return self._scope_index

    def _owner(self, name: str):
        """The element of ``W`` called ``name`` whose name is not free, or ``None``."""
        for el_id in self._name_index().get(name_key(name)) or ():
            if el_id not in self.pending:
                return el_id
        return None

    def _taken(self) -> set:
        """Name keys a default name may not take: every name of ``W`` (names
        of operations left without a line included) and every name written on
        a left side."""
        return set(self._name_index()) | self.reserved

    def _all_names(self) -> TakenKeys:
        return TakenKeys(self._taken())

    def _free_pending(self, name: str):
        for el_id in list(self._name_index().get(name_key(name)) or ()):
            if el_id in self.pending:
                self._set_name(el_id, '')

    def _taken_error(self, name: str, column: int, owner: str):
        raise LineError('name_taken', column, f'имя {name} уже занято',
                        hint=suggest_name(name, self._all_names()))

    # ── arguments ────────────────────────────────────────────────────────

    def _points(self) -> dict:
        self._scope_names()
        return self._scope_points

    def _splits(self, text: str, parts: int):
        points = self._points()
        found = []

        def walk(rest, acc):
            if len(acc) == parts - 1:
                key = name_key(rest)
                if rest and key in points:
                    found.append(acc + [rest])
                return
            for k in range(1, len(rest)):
                head = rest[:k]
                if name_key(head) in points:
                    walk(rest[k:], acc + [head])

        walk(text, [])
        return [[points[name_key(p)] for p in split] for split in found], found

    def _unknown(self, text: str, column: int):
        key = name_key(text)
        elsewhere = any(isinstance(el, dict) and name_key(el.get('displayName') or '') == key
                        for el in self.W['elements'].values())
        later = self.defined_at.get(key)
        if later is not None and later > self.line_no:
            raise LineError('unknown_name', column, f'{text} задаётся ниже, в строке {later}',
                            hint='ссылаться можно только на строки выше')
        if elsewhere:
            raise LineError('unknown_name', column, f'{text} ещё не определён выше этой строки')
        raise LineError('unknown_name', column, f'нет объекта {text}')

    def _split_or_fail(self, text: str, column: int, parts: int):
        ids, names = self._splits(text, parts)
        if len(ids) == 1:
            return ids[0]
        if len(ids) > 1:
            options = ' или '.join(', '.join(split) for split in names)
            raise LineError('ambiguous_pair', column, f'{text} делится на точки по-разному', hint=options)
        self._unknown(text, column)

    def _arg_kind(self, arg):
        if arg.kind == 'number':
            return NUM, arg.value
        if arg.kind == 'point':
            return PT, arg.value
        if arg.kind == 'angle3':
            return ANGLE3, self._split_or_fail(arg.text, arg.name_column, 3)
        names = self._scope_names()
        el_id = names.get(name_key(arg.text))
        if arg.kind == 'not':
            if el_id is None:
                self._unknown(arg.text, arg.name_column)
            if self.W['elements'][el_id].get('type') != 'point':
                raise LineError('type_mismatch', arg.name_column, f'после «не» нужна точка, а {arg.text} — '
                                f'{kind_text(self.W["elements"][el_id].get("type"))}')
            return NOT, el_id
        if el_id is not None:
            return self.W['elements'][el_id].get('type'), el_id
        return PAIR, self._split_or_fail(arg.text, arg.name_column, 2)

    def _arg_json(self, position, kind, payload):
        if kind == NUM:
            return {'kind': 'number', 'value': payload}
        if kind == PAIR:
            return _Helper(pair_op(position.type), payload)
        if kind == ANGLE3:
            return _Helper('angle.by_points', payload)
        return {'kind': 'ref', 'elementId': payload}

    def _path_default(self, arg) -> float:
        if isinstance(arg, _Helper):
            path_type = self.reg.get(arg.op)['outputs'][0]['type']
        else:
            path_type = self.W['elements'][arg['elementId']].get('type')
        spec = self.reg.paths.get(path_type) or {}
        return float(spec.get('default', 0.0))

    def _request(self, st) -> _Request:
        reg = self.reg
        if st.kind == 'point':
            return _Request('point.free', reg.get('point.free'), {},
                            {'kind': 'point', 'value': [st.value[0], st.value[1]]}, '')
        if st.kind == 'number':
            return _Request('number.free', reg.get('number.free'), {},
                            {'kind': 'number', 'value': st.value}, '')
        if st.kind == 'angle3':
            points = self._split_or_fail(st.text, st.command_column, 3)
            args = {slot: {'kind': 'ref', 'elementId': p} for slot, p in zip(HELPER_OPS['angle.by_points'], points)}
            return _Request('angle.by_points', reg.get('angle.by_points'), args, None, '∠')
        entries = self.lex.lookup(st.command)
        if not entries:
            hint = closest_name(st.command, self.lex.names())
            raise LineError('unknown_command', st.command_column, f'нет команды {st.command}', hint=hint)
        kinds, payloads = [], []
        for arg in st.args:
            kind, payload = self._arg_kind(arg)
            kinds.append(kind)
            payloads.append(payload)
        res = resolve(entries, kinds, [a.column for a in st.args], st.command_column, st.command)
        if res.swapped:
            kinds, payloads = kinds[::-1], payloads[::-1]
        entry = res.entry
        record = reg.get(entry.op)
        args, value = {}, None
        for position, taken in zip(entry.positions, res.slots):
            if taken is None:
                continue
            if position.kind == 'input':
                if position.list:
                    args[position.slot] = {'kind': 'list', 'items': [
                        self._arg_json(position, kinds[i], payloads[i]) for i in taken]}
                else:
                    args[position.slot] = self._arg_json(position, kinds[taken], payloads[taken])
            elif position.kind == 'param':
                args[position.slot] = {'kind': 'number', 'value': payloads[taken]}
            else:
                value = payloads[taken]
        free_input = None
        free = record.get('free')
        if free is not None:
            kind = free['kind']
            if kind == 'point':
                free_input = {'kind': 'point', 'value': [value[0], value[1]]}
            elif kind == 'number':
                if value is None:
                    low = args.get('min')
                    value = low['value'] if isinstance(low, dict) else 0.0
                free_input = {'kind': 'number', 'value': value}
            elif kind == 'pathParameter':
                if value is None:
                    path_slot = next(i['slot'] for i in record.get('inputs', ()) if i['type'] == 'path')
                    value = self._path_default(args[path_slot])
                free_input = {'kind': 'pathParameter', 'value': value}
            elif kind in FREE_INPUT_DEFAULTS:      # an angle: 0 when left out
                free_input = {'kind': kind, 'value': FREE_INPUT_DEFAULTS[kind]['value'] if value is None else value}
        return _Request(entry.op, record, args, free_input, entry.name)

    # ── helpers (pairs and ∠ABC) ─────────────────────────────────────────

    def _note_helper(self, op_id: str) -> None:
        if self._helper_index is not None:
            key = helper_key(self.W['operations'][op_id])
            if key is not None:
                self._helper_index.setdefault(key, []).append(op_id)

    def _find_helper(self, helper: _Helper):
        if self._helper_index is None:
            self._helper_index = {}
            for op_id in self.W['operations']:
                self._note_helper(op_id)
        key = (helper.op, tuple(helper.points))
        visible = hidden = None
        for op_id in self._helper_index.get(key, ()):
            op = self.W['operations'].get(op_id)
            if op is None or helper_key(op) != key:
                continue
            out = next((o['elementId'] for o in op.get('outputs') or () if o.get('elementId') in self.W['elements']),
                       None)
            if out is None:
                continue
            if is_helper(self.W, op_id):
                hidden = hidden or out
            elif out in self.scope and visible is None:
                visible = out
        return visible or hidden

    def _make_helper(self, helper: _Helper) -> str:
        found = self._find_helper(helper)
        if found is not None:
            return found
        record = self.reg.get(helper.op)
        out = record['outputs'][0]
        op_id = self.new_id('operation')
        el_id = self.new_id('element')
        self.W['operations'][op_id] = {
            'id': op_id, 'op': helper.op,
            'args': {s: {'kind': 'ref', 'elementId': p} for s, p in zip(HELPER_OPS[helper.op], helper.points)},
            'outputs': [{'slot': out['slot'], 'elementId': el_id}],
        }
        self.W['elements'][el_id] = {'id': el_id, 'type': out['type'], 'displayName': '',
                                     'producer': {'operationId': op_id, 'slot': out['slot']}}
        self.W.setdefault('appearance', {})[el_id] = {'visible': False}
        self._note_helper(op_id)
        return el_id

    def _materialize(self, args: dict, create: bool = True):
        """``args`` with every helper made an element ref (``None`` when
        ``create`` is false and a helper does not exist yet)."""
        def one(arg):
            if isinstance(arg, _Helper):
                el_id = self._make_helper(arg) if create else self._find_helper(arg)
                return None if el_id is None else {'kind': 'ref', 'elementId': el_id}
            if isinstance(arg, dict) and arg.get('kind') == 'list':
                items = [one(item) for item in arg['items']]
                return None if any(i is None for i in items) else {'kind': 'list', 'items': items}
            return copy.deepcopy(arg)

        out = {}
        for slot, arg in args.items():
            value = one(arg)
            if value is None:
                return None
            out[slot] = value
        return out

    def _helper_ops(self, args: dict) -> list:
        out = []
        for slot in args:
            for ref in iter_refs(args[slot]):
                el = self.W['elements'].get(ref)
                op_id = (el or {}).get('producer', {}).get('operationId')
                if op_id and is_helper(self.W, op_id) and op_id not in out:
                    out.append(op_id)
        return out

    # ── lines ────────────────────────────────────────────────────────────

    def _out_slots(self, req: _Request) -> list:
        return self.reg.output_slots(req.record, req.args, self.W)

    def _check_names(self, st, slots) -> None:
        seen = set()
        for i, nm in enumerate(st.names):
            if i >= len(slots):
                raise LineError('arity', nm.column,
                                f'имён слева: {len(st.names)}, выходов у команды: {len(slots)}')
            if not valid_name(nm.text):
                raise LineError('invalid_name', nm.column, f'«{nm.text}» не годится в имена')
            key = name_key(nm.text)
            if key in seen:
                raise LineError('name_taken', nm.column, f'имя {nm.text} повторяется слева',
                                hint=suggest_name(nm.text, self._all_names()))
            seen.add(key)

    def _default_names(self, req: _Request, args: dict, slots, given: dict) -> dict:
        """Names of every slot: ``given`` (slot → name) plus defaults."""
        taken = self._taken() | {name_key(n) for n in given.values() if n}
        names = dict(given)
        if req.op == 'polygon.by_points':
            vertex_names = [self.W['elements'][r].get('displayName') or '' for r in iter_refs(args['vertices'])]
            sides = polygon_side_names(vertex_names, TakenKeys(taken))
            for i, slot in enumerate(s for s in slots if s.startswith('side.')):
                if slot not in names:
                    names[slot] = sides[i]
                    taken.add(name_key(sides[i]))
        for slot in slots:
            if slot not in names:
                name = next_name(self.reg.output_type(req.record, slot, args, self.W), TakenKeys(taken))
                names[slot] = name
                if name:
                    taken.add(name_key(name))
        return names

    def _add_element(self, op_id: str, slot: str, el_type: str, name: str) -> str:
        el_id = self.new_id('element')
        self.W['elements'][el_id] = {'id': el_id, 'type': el_type, 'displayName': name,
                                     'producer': {'operationId': op_id, 'slot': slot}}
        if name and self._index is not None:
            self._index.setdefault(name_key(name), {})[el_id] = None
        return el_id

    def _set_input(self, el_id: str, value) -> None:
        if value is None:
            return
        inputs = self.W.setdefault('inputs', {})
        if el_id not in inputs or canonical_json(inputs[el_id]) != canonical_json(value):
            inputs[el_id] = copy.deepcopy(value)

    def _record_line(self, line: int, op_id: str) -> None:
        op = self.W['operations'][op_id]
        outputs = [o['elementId'] for o in op.get('outputs') or () if o.get('elementId') in self.W['elements']]
        for el_id in outputs:
            if el_id not in self.scope:
                self.scope.add(el_id)
                self._note_scope(el_id)
        self.lines.append({'line': line, 'operationIds': [op_id] + self._helper_ops(op.get('args') or {}),
                           'elementIds': outputs})

    def _create(self, st, req: _Request) -> None:
        slots = self._out_slots(req)
        given = {}
        for i, nm in enumerate(st.names):
            owner = self._owner(nm.text)
            if owner is not None:
                self._taken_error(nm.text, nm.column, owner)
            given[slots[i]] = nm.text
        args = self._materialize(req.args)
        for name in given.values():
            self._free_pending(name)
        names = self._default_names(req, args, slots, given)
        op_id = self.new_id('operation')
        outputs = []
        free_el = None
        for slot in slots:
            el_id = self._add_element(op_id, slot, self.reg.output_type(req.record, slot, args, self.W), names[slot])
            outputs.append({'slot': slot, 'elementId': el_id})
            free_el = free_el or el_id
        self.W['operations'][op_id] = {'id': op_id, 'op': req.op, 'args': args, 'outputs': outputs}
        self._note_helper(op_id)
        if req.input is not None:
            self._set_input(free_el, req.input)
        self._record_line(st.line, op_id)

    def _update(self, st, req: _Request, op_id: str) -> None:
        old = self.W['operations'][op_id]
        old_outputs = {o['elementId']: o['slot'] for o in old.get('outputs') or ()
                       if o.get('elementId') in self.W['elements']}
        slots = self._out_slots(req)
        mapped, bind = {}, {}
        for i, nm in enumerate(st.names):
            owner = self._owner(nm.text)
            if owner in old_outputs:
                mapped[i] = owner
            elif owner is None:
                bind[i] = nm.text
            else:
                self._taken_error(nm.text, nm.column, owner)
        args = self._materialize(req.args)
        for name in bind.values():
            self._free_pending(name)
        same = (old.get('op') == req.op
                and canonical_json(old.get('args') or {}) == canonical_json(args)
                and all(old_outputs[el] == slots[i] for i, el in mapped.items()))
        if not same:
            slot_map, targets = {}, set()
            for i, el in mapped.items():
                slot_map[old_outputs[el]] = slots[i]
                targets.add(slots[i])
            for el, slot in old_outputs.items():
                if slot in slot_map:
                    continue
                if slot not in slots or slot in targets:
                    slot_map[slot] = '#drop'
            inputs = None
            if req.input is not None:
                free_slot = slots[0]
                keeper = next((el for el, slot in old_outputs.items()
                               if slot_map.get(slot, slot) == free_slot), None)
                if keeper is not None:
                    inputs = {keeper: req.input}
            try:
                result = redefine(NativeDocument(self.W), op_id, {'op': req.op, 'args': args},
                                  slot_map=slot_map, inputs=inputs)
            except EditError as exc:
                first = exc.issues[0]
                raise LineError(first.code, st.command_column or st.column,
                                _refusal_text(first, self.W)) from None
            self.W = result.document.data
            self.warnings.extend(result.effects.get('warnings') or ())
            self._dirty()
        op = self.W['operations'][op_id]
        present = {o['slot']: o['elementId'] for o in op.get('outputs') or ()
                   if o.get('elementId') in self.W['elements']}
        given = {slots[i]: name for i, name in bind.items()}
        # a changed definition names every new slot; an unchanged one only adds
        # the slots the line names
        missing = [s for s in slots if s not in present and (not same or s in given)]
        if missing:
            known = {s: self.W['elements'][e].get('displayName') or '' for s, e in present.items()}
            names = self._default_names(req, args, slots, {**known, **given})
            for slot in missing:
                present[slot] = self._add_element(op_id, slot, self.reg.output_type(req.record, slot, args, self.W),
                                                  names[slot])
        for slot, name in given.items():
            self._set_name(present[slot], name)
        op['outputs'] = [{'slot': s, 'elementId': present[s]} for s in slots if s in present]
        if req.input is not None:
            self._set_input(present[slots[0]], req.input)
        self.matched.add(op_id)
        self._record_line(st.line, op_id)

    def _definition_match(self, req: _Request):
        if not self.editing or not self.nameless:
            return None
        args = self._materialize(req.args, create=False)
        if args is None:
            return None
        inputs = {i['slot'] for i in req.record.get('inputs', ())}

        def key(a, only_inputs):
            return canonical_json({k: v for k, v in a.items() if not only_inputs or k in inputs})

        candidates = [op_id for op_id in sorted(self.nameless)
                      if op_id not in self.matched and op_id in self.W['operations']
                      and self.W['operations'][op_id].get('op') == req.op]
        # the same definition first, then the same inputs with other params
        # (a mark whose count changed keeps its ID)
        for only_inputs in (False, True):
            wanted = key(args, only_inputs)
            for op_id in candidates:
                if key(self.W['operations'][op_id].get('args') or {}, only_inputs) == wanted:
                    return op_id
        return None

    def _apply(self, st, op_id) -> None:
        if op_id is not None and op_id not in self.W['operations']:
            op_id = None
        req = self._request(st)
        slots = self._out_slots(req)
        self._check_names(st, slots)
        if op_id is None:
            op_id = self._definition_match(req)
        if op_id is None:
            self._create(st, req)
        else:
            self.matched.add(op_id)
            self._update(st, req, op_id)

    def _keep(self, line: int, op_id) -> None:
        if op_id is not None and op_id in self.W['operations']:
            self.matched.add(op_id)
            self._record_line(line, op_id)


    # ── statements (1.9.0a3) ─────────────────────────────────────────────

    def element(self, name: str):
        return self._scope_names().get(name_key(name))

    def type_of(self, el_id: str):
        return (self.W['elements'].get(el_id) or {}).get('type')

    def split(self, text: str, column: int, parts: int):
        return self._split_or_fail(text, column, parts)

    def unknown(self, text: str, column: int):
        self._unknown(text, column)

    def point(self, tok) -> dict:
        el = self.element(tok.text)
        if el is None:
            self._unknown(tok.text, tok.column)
        if self.type_of(el) != 'point':
            raise LineError('type_mismatch', tok.column, f'{tok.text} — {kind_text(self.type_of(el))}, а нужна точка')
        return {'ref': el}

    def obj(self, tokens, column: int, types=None) -> dict:
        if len(tokens) != 1 or tokens[0].kind != 'name':
            raise LineError('syntax', tokens[0].column if tokens else column, 'нужно имя объекта или пара точек')
        tok = tokens[0]
        el = self.element(tok.text)
        if el is not None:
            return {'ref': el}
        return {'pair': list(self._split_or_fail(tok.text, tok.column, 2))}

    def _statement(self, st):
        from .statements import parse_statement
        tokens = st.tokens
        receiver = None
        if st.kind == 'condition':
            from .statements import _split_commas
            parts = _split_commas(tokens)
            if len(parts) > 2:
                raise LineError('syntax', parts[2][0].column if parts[2] else st.column, 'лишний аргумент')
            if len(parts) == 2:
                tail = parts[1]
                if (len(tail) != 2 or tail[0].kind != 'name' or self.lex.keyword(tail[0].text) != 'move'
                        or tail[1].kind != 'name'):
                    raise LineError('syntax', tail[0].column if tail else st.column,
                                    f'после запятой нужно «{self.lex.word("move")} X»')
                receiver = self.point(tail[1])['ref']
                tokens = parts[0]
        return parse_statement(tokens, self, self.lex, st.command_column, NativeDocument(self.W)), receiver

    def _condition_line(self, no: int, st) -> None:
        from ..conditions.apply import _choose, _constraints, _points, _status
        from ..conditions.recipes import matches
        from .printer import _printable
        statement, receiver = self._statement(st)
        # judged without the conditions of the text applied (as in a new
        # document): receivers at their origins, no places
        doc = NativeDocument(_printable(NativeDocument(self.W))) if self.editing else NativeDocument(self.W)
        found = matches(doc, statement)
        column = st.command_column
        if not found:
            raise LineError('unsupported_condition', column, 'такое условие построить нельзя: нет рецепта',
                            hint=f'{self.lex.word("check")}(…)')
        participants = _points(doc, statement)
        receivers = list(dict.fromkeys(b[r['receiver']] for r, b in found))
        explicit = receiver is not None
        if explicit:
            if receiver not in receivers:
                raise LineError('unsupported_condition', column, 'нет рецепта, который двигает эту точку')
            status = _status(doc, receiver, participants)
            if status == 'not_free':
                raise LineError('receiver_not_free', column, 'точку нельзя двигать: она не свободна')
            if status == 'ancestor':
                raise LineError('receiver_is_ancestor', column, 'точку нельзя двигать: от неё зависят другие участники')
        else:
            statuses = {r: _status(doc, r, participants) for r in receivers}
            ok = [r for r in receivers if statuses[r] == 'ok']
            if not ok:
                if any(v == 'ancestor' for v in statuses.values()):
                    raise LineError('receiver_is_ancestor', column, 'двигать некого: точки условия задают друг друга')
                raise LineError('receiver_not_free', column, 'двигать некого: в условии нет свободной точки')
            receiver = _choose(doc, ok, participants)
        key = canonical_json(statement)
        if self.editing:
            for cond in self._base_construct():
                if cond['id'] in self.kept_conditions or canonical_json(cond.get('statement')) != key:
                    continue
                if explicit and cond.get('receiver') != receiver:
                    continue
                self.kept_conditions.add(cond['id'])
                self.condition_lines.append({'line': no, 'operationIds': [], 'elementIds': [],
                                             'conditionId': cond['id']})
                return
        on_receiver = sum(1 for r in self.requests if r['kind'] in ('apply', 'replace') and r.get('receiver') == receiver)
        on_receiver += sum(1 for c in self._base_construct() if c['id'] in self.kept_conditions
                           and c.get('receiver') == receiver)
        if _constraints(doc, receiver) + on_receiver >= 2:
            raise LineError('too_many_conditions', column, 'у точки уже два условия')
        request = {'line': no, 'kind': 'apply', 'statement': statement, 'receiver': receiver}
        if self.editing:
            free = [c for c in self._base_construct() if c['id'] not in self.kept_conditions
                    and not any(r.get('conditionId') == c['id'] for r in self.requests)]
            old = next((c for c in free if c.get('receiver') == receiver), None) or \
                next((c for c in free if canonical_json(c.get('statement')) == key), None)
            if old is not None:
                request = {'line': no, 'kind': 'replace', 'conditionId': old['id'], 'statement': statement,
                           'receiver': receiver}
        self.requests.append(request)

    def _check_line(self, no: int, st) -> None:
        from .statements import parse_statement
        tokens = st.tokens
        statement = parse_statement(tokens, self, self.lex, st.command_column, NativeDocument(self.W))
        key = canonical_json(statement)
        if self.editing:
            for cond in self.base.get('conditions') or ():
                if (isinstance(cond, dict) and cond.get('mode') == 'check' and cond.get('id') not in self.kept_checks
                        and canonical_json(cond.get('statement')) == key):
                    self.kept_checks.add(cond['id'])
                    self.condition_lines.append({'line': no, 'operationIds': [], 'elementIds': [],
                                                 'conditionId': cond['id']})
                    return
        self.new_checks.append((no, statement))

    def _relation_line(self, no: int, st) -> None:
        from .statements import parse_objects
        a, b = parse_objects(st.tokens, self, st.command_column)
        self.queries.append({'line': no, 'kind': 'relation', 'a': a, 'b': b})

    def _base_construct(self) -> list:
        return [c for c in self.base.get('conditions') or ()
                if isinstance(c, dict) and c.get('mode') == 'construct' and isinstance(c.get('id'), str)]

    def _move_receiver(self, no: int, st, op_id: str) -> None:
        """A changed point literal on the line of a receiver: the new origin
        and a ``move`` request; the operation stays."""
        conds = self.receiver_ops[op_id]
        receiver = conds[0]['receiver']
        origin = {'op': 'point.free', 'args': {}, 'input': {'point': [st.value[0], st.value[1]]}}
        for cond in self.W.get('conditions') or ():
            if isinstance(cond, dict) and cond.get('mode') == 'construct' and cond.get('receiver') == receiver:
                cond['receiverOrigin'] = copy.deepcopy(origin)
        self.requests.append({'line': no, 'kind': 'move', 'conditionId': conds[0]['id'], 'receiver': receiver,
                              'point': [st.value[0], st.value[1]]})
        self.matched.add(op_id)
        self._record_line(no, op_id)

    def _reserve_condition_ops(self) -> None:
        """Edit mode: the places of construct conditions and the automatic
        marks have no lines; they stay unless their condition goes."""
        data = self.base
        for cond in self._base_construct():
            receiver = cond.get('receiver')
            rop = ((data.get('elements') or {}).get(receiver) or {}).get('producer', {}).get('operationId')
            for op_id in cond.get('operationIds') or ():
                if op_id == rop:
                    self.receiver_ops.setdefault(op_id, []).append(cond)
                elif op_id in (data.get('operations') or {}):
                    self.matched.add(op_id)
        for op_id in auto_ops(data):
            self.matched.add(op_id)

    def _finish_conditions(self) -> None:
        conds = self.W.get('conditions')
        present = {c.get('id') for c in conds or () if isinstance(c, dict)}
        if self.editing:
            spared = self.failed_conditions
            for cond in self._base_construct():
                if cond['id'] in present and cond['id'] not in self.kept_conditions \
                        and not any(r.get('conditionId') == cond['id'] for r in self.requests):
                    if spared:
                        spared -= 1           # an Условие line with an error keeps its condition
                        continue
                    self.requests.append({'line': None, 'kind': 'release', 'conditionId': cond['id']})
            for req in list(self.requests):
                if req.get('conditionId') is not None and req.get('conditionId') not in present:
                    if req['kind'] == 'replace':
                        req['kind'] = 'apply'
                        del req['conditionId']
                    else:
                        self.requests.remove(req)
            if conds is not None:
                self.W['conditions'] = [c for c in conds if not (isinstance(c, dict) and c.get('mode') == 'check'
                                                                  and c.get('id') not in self.kept_checks)]
        if self.new_checks:
            from ..conditions.apply import _max_seq
            used = set(self.W['operations']) | set(self.W['elements']) | {
                c.get('id') for c in self.W.get('conditions') or () if isinstance(c, dict)}
            seq = _max_seq(self.W)
            n = 1
            for _no, statement in self.new_checks:
                while f'c{n}' in used:
                    n += 1
                cid = f'c{n}'
                used.add(cid)
                seq += 1
                self.W.setdefault('conditions', []).append({'id': cid, 'seq': seq, 'mode': 'check',
                                                            'statement': statement})
                self.condition_lines.append({'line': _no, 'operationIds': [], 'elementIds': [], 'conditionId': cid})
        if self.W.get('conditions') == [] and 'conditions' not in self.base:
            del self.W['conditions']
        # releases first (they free receivers and places), then the lines in order
        self.requests.sort(key=lambda r: (r['kind'] != 'release', r['line'] or 0))

    def _comment_steps(self, lines: list) -> None:
        """Explicit steps from comments (plan L3 §4.1): a comment line opens
        a group (its text is the title; «# Дано» — the «Дано» step) that runs
        to the next comment line or an empty line; a comment at the end of a
        line is the ``text`` of its step."""
        by_line = {e['line']: e['operationIds'] for e in lines if e['operationIds']}
        groups, current = [], None
        for no in range(1, self.line_count + 1):
            comment = self.comments.get(no)
            if comment is not None and comment[1]:
                title = comment[0]
                kind = 'group'
                if title and self.lex.keyword(title) == 'given':
                    kind, title = 'given', ''
                current = {'kind': kind, 'title': title, 'text': '', 'ops': [], 'first': None}
                groups.append(current)
                continue
            if no in self.blank_lines:
                current = None
                continue
            ops = by_line.get(no)
            if not ops:
                continue
            text = comment[0] if comment is not None else ''
            target = current
            if target is None:
                if not text:
                    continue
                target = {'kind': 'group', 'title': '', 'text': '', 'ops': [], 'first': None}
                groups.append(target)
            if text:
                target['text'] = f"{target['text']}; {text}" if target['text'] else text
            target['ops'].extend(ops)
            if target['first'] is None:
                target['first'] = ops[0]
        signature = [(g['title'], g['text'], [o for o in g['ops'] if not is_helper(self.W, o)]) for g in groups
                     if g['ops']]
        if self.editing and signature == (printed_step_signature(self.base, self.lex)
                                          if self.base.get('steps') else []):
            steps = []
            for step in self.base.get('steps') or ():
                if not isinstance(step, dict):
                    continue
                kept = [o for o in step.get('operationIds') or () if o in self.W['operations']]
                if kept:
                    steps.append({**copy.deepcopy(step), 'operationIds': kept})
            if steps or 'steps' in self.W:
                self.W['steps'] = steps
            if self.W.get('steps') == [] and 'steps' not in self.base:
                del self.W['steps']
            return
        base_steps = [s for s in self.base.get('steps') or () if isinstance(s, dict)]
        used_ids = set()
        out, assigned = [], set()
        for g in groups:
            ops = [o for o in dict.fromkeys(g['ops']) if o not in assigned and o in self.W['operations']]
            if not ops:
                continue
            assigned.update(ops)
            sid = next((s.get('id') for s in base_steps if g['first'] in (s.get('operationIds') or ())
                        and s.get('id') not in used_ids), None)
            if sid is None:
                n = 1
                taken = used_ids | {s.get('id') for s in base_steps}
                while f's{n}' in taken:
                    n += 1
                sid = f's{n}'
            used_ids.add(sid)
            step = {'id': sid, 'kind': g['kind'], 'operationIds': ops}
            if g['title']:
                step['title'] = g['title']
            if g['text']:
                step['text'] = g['text']
            out.append(step)
        if out:
            self.W['steps'] = out
        else:
            self.W.pop('steps', None)

    # ── run ──────────────────────────────────────────────────────────────

    def run(self, text: str) -> ParseResult:
        if not isinstance(text, str):
            raise TypeError('text must be a string')
        rows = text.split('\n')
        statements = []
        self.line_count = len(rows)
        self.blank_lines = set()
        for no, raw in enumerate(rows, 1):
            line = raw[:-1] if raw.endswith('\r') else raw
            if not line.strip():
                self.blank_lines.add(no)
            try:
                tokens, comment = tokenize(line)
            except LineError as exc:
                self.issues.append(exc.issue(no))
                statements.append((no, None, _claim_names(line)))
                continue
            if comment is not None:
                self.comments[no] = (line[comment:].strip(), not tokens)
            try:
                st = parse_line(tokens, no, self.lex)
            except LineError as exc:
                self.issues.append(exc.issue(no))
                statements.append((no, None, _claim_names(line)))
                continue
            if st is not None:
                statements.append((no, st, [n.text for n in st.names]))
        for no, _st, names in statements:
            for n in names:
                if valid_name(n):
                    self.reserved.add(name_key(n))
                    self.defined_at.setdefault(name_key(n), no)
        base_ops = self.base.get('operations') or {}
        base_elements = self.base.get('elements') or {}
        if self.editing:
            by_name = {}
            for el_id, el in base_elements.items():
                name = el.get('displayName') if isinstance(el, dict) else None
                if isinstance(name, str) and name:
                    by_name.setdefault(name_key(name), el_id)
            claimed = set()
            for no, _st, names in statements:
                if not names:
                    continue
                el_id = by_name.get(name_key(names[0]))
                op_id = ((base_elements.get(el_id) or {}).get('producer') or {}).get('operationId')
                if op_id in base_ops and op_id not in claimed and not is_helper(self.base, op_id):
                    claimed.add(op_id)
                    self.claims[no] = op_id
            for op_id, op in base_ops.items():
                if op_id in claimed or is_helper(self.base, op_id):
                    continue
                outs = [o.get('elementId') for o in op.get('outputs') or ()]
                named = [e for e in outs if (base_elements.get(e) or {}).get('displayName')]
                if named:
                    self.pending.update(named)
                else:
                    self.nameless.add(op_id)
        if self.editing:
            self._reserve_condition_ops()
        printed = self._printed_base() if self.editing else {}
        handlers = {'condition': self._condition_line, 'check': self._check_line, 'checkcall': self._check_line,
                    'relation': self._relation_line}
        for no, st, _names in statements:
            self.line_no = no
            op_id = self.claims.get(no)
            if st is not None and st.kind in handlers:
                try:
                    handlers[st.kind](no, st)
                except LineError as exc:
                    self.issues.append(exc.issue(no))
                    if st.kind == 'condition':
                        self.failed_conditions += 1
                continue
            if st is None:
                self._keep(no, op_id)
                continue
            same = self._same_as_printed(rows[no - 1], op_id, printed)
            if same is not None:
                self._keep(no, same)
                continue
            if op_id in self.receiver_ops and st.kind == 'point':
                self._move_receiver(no, st, op_id)
                continue
            try:
                self._apply(st, op_id)
            except LineError as exc:
                self.issues.append(exc.issue(no))
                self._keep(no, op_id)
        self._finish()
        self._finish_conditions()
        lines = self._final_lines()
        self._comment_steps(lines)
        self._ambiguous_names(statements, lines)
        lines = sorted(lines + [e for e in self.condition_lines
                                if any(isinstance(c, dict) and c.get('id') == e['conditionId']
                                       for c in self.W.get('conditions') or ())], key=lambda e: e['line'])
        return ParseResult(NativeDocument(self.W), self._diff(), lines,
                           sorted(self.issues, key=lambda i: (i.line, i.column)), self.requests, self.queries)

    def _ambiguous_names(self, statements, lines) -> None:
        """``ambiguous_name`` (a warning, commands.md §3) at a left name of a
        line without errors whose element also reads as two point names of
        the resulting document."""
        elements = self.W['elements']
        point_keys = {name_key(el['displayName']) for el in elements.values()
                      if isinstance(el, dict) and el.get('type') == 'point' and el.get('displayName')}
        if not point_keys:
            return
        failed = {i.line for i in self.issues if i.severity == 'error'}
        named = {e['line']: {name_key(elements[x].get('displayName') or '') for x in e['elementIds']}
                 for e in lines}
        for no, st, _names in statements:
            if st is None or no in failed:
                continue
            keys = named.get(no, ())
            for nm in st.names:
                if name_key(nm.text) in keys:
                    readings = pair_readings(nm.text, point_keys)
                    if readings:
                        self.issues.append(ambiguous_name(nm.text, readings, no, nm.column))

    def _printed_base(self) -> dict:
        """``{operationId: token signature}`` of the lines the printer gives
        for ``base``: a line typed back unchanged keeps its operation as it is,
        even when the printer could not say everything (a param after a gap,
        a pair that does not read back)."""
        from .printer import print_commands

        out = {}
        result = print_commands(NativeDocument(self.base), lexicon=self.lex)
        rows = result.text.split('\n')
        for info in result.lines:
            if not info['operationIds']:
                continue
            sig = _signature(rows[info['line'] - 1])
            if sig is not None:
                out[info['operationIds'][0]] = sig
        return out

    def _refs_in_scope(self, op_id: str) -> bool:
        op = self.W['operations'][op_id]
        for arg in (op.get('args') or {}).values():
            for ref in iter_refs(arg):
                if ref in self.scope:
                    continue
                el = self.W['elements'].get(ref)
                producer = (el or {}).get('producer', {}).get('operationId')
                if producer is None or not is_helper(self.W, producer):
                    return False
                helper = self.W['operations'][producer]
                if any(r not in self.scope for a in helper['args'].values() for r in iter_refs(a)):
                    return False
        return True

    def _same_as_printed(self, line: str, op_id, printed: dict):
        if not printed:
            return None
        sig = _signature(line.rstrip('\r'))
        if sig is None:
            return None
        if op_id is not None:
            if op_id in self.W['operations'] and printed.get(op_id) == sig and (
                    op_id in self.receiver_ops or self._refs_in_scope(op_id)):
                return op_id
            return None
        for candidate in sorted(self.nameless):
            if (candidate not in self.matched and candidate in self.W['operations']
                    and printed.get(candidate) == sig and self._refs_in_scope(candidate)):
                return candidate
        return None

    def _finish(self) -> None:
        ops = self.W['operations']
        if self.editing:
            stale = [op_id for op_id in (self.base.get('operations') or {})
                     if op_id in ops and op_id not in self.matched and not is_helper(self.base, op_id)]
            seeds = [o['elementId'] for op_id in stale for o in ops[op_id].get('outputs') or ()
                     if o.get('elementId') in self.W['elements']]
            if seeds:
                self.W = delete(NativeDocument(self.W), seeds, mode='operation').document.data
            for op_id in stale:
                self.W['operations'].pop(op_id, None)
        while True:
            ops = self.W['operations']
            used = {ref for op in ops.values() for arg in (op.get('args') or {}).values() for ref in iter_refs(arg)}
            idle = [op_id for op_id in ops if is_helper(self.W, op_id)
                    and not any(o.get('elementId') in used for o in ops[op_id].get('outputs') or ())]
            if not idle:
                break
            seeds = [o['elementId'] for op_id in idle for o in ops[op_id].get('outputs') or ()]
            self.W = delete(NativeDocument(self.W), seeds, mode='operation').document.data
        if self.W.get('appearance') == {} and 'appearance' not in self.base:
            del self.W['appearance']
        newest = max((_version_tuple((self.reg.get(op.get('op')) or {}).get('since', '0'))
                      for op in self.W['operations'].values() if self.reg.get(op.get('op'))), default=(0,))
        if newest > _version_tuple(self.W.get('operationRegistryVersion')):
            self.W['operationRegistryVersion'] = REGISTRY_VERSION

    def _diff(self) -> dict:
        effects = _effects()
        for section in ('operations', 'elements', 'inputs'):
            before = self.base.get(section) or {}
            after = self.W.get(section) or {}
            for key, value in after.items():
                if key not in before:
                    effects['added'][section].append(key)
                elif value != before[key] and canonical_json(value) != canonical_json(before[key]):
                    effects['modified'][section].append(key)
            for key in before:
                if key not in after:
                    effects['removed'][section].append(key)
        before = self.base.get('appearance') or {}
        after = self.W.get('appearance') or {}
        effects['removed']['appearance'] = [k for k in before if k not in after]
        before = {c.get('id'): c for c in self.base.get('conditions') or () if isinstance(c, dict)}
        after = {c.get('id'): c for c in self.W.get('conditions') or () if isinstance(c, dict)}
        added = [k for k in after if k not in before]
        removed = [k for k in before if k not in after]
        modified = [k for k in after if k in before and canonical_json(after[k]) != canonical_json(before[k])]
        if added or removed or modified:
            effects.setdefault('added', {})['conditions'] = added
            effects.setdefault('removed', {})['conditions'] = removed
            effects.setdefault('modified', {})['conditions'] = modified
        effects['warnings'] = list(self.warnings)
        return _finish(effects)

    def _final_lines(self) -> list:
        out = []
        ops = self.W['operations']
        elements = self.W['elements']
        for entry in self.lines:
            op_ids = [o for o in entry['operationIds'] if o in ops]
            if not op_ids or entry['operationIds'][0] not in ops:
                continue
            main = ops[entry['operationIds'][0]]
            out.append({'line': entry['line'], 'operationIds': [main['id']] + self._helper_ops(main.get('args') or {}),
                        'elementIds': [o['elementId'] for o in main.get('outputs') or ()
                                       if o.get('elementId') in elements]})
        return out


def auto_ops(data: dict) -> list:
    """Operations whose outputs are all automatic (``origin.kind = "auto"``):
    automatic marks and their helpers; «Команды» do not print them."""
    elements = data.get('elements') or {}
    out = []
    for op_id, op in (data.get('operations') or {}).items():
        outs = [elements.get(o.get('elementId')) for o in op.get('outputs') or ()]
        if outs and all(isinstance(e, dict) and isinstance(e.get('origin'), dict)
                        and e['origin'].get('kind') == 'auto' for e in outs):
            out.append(op_id)
    return out


def printed_step_signature(data, lexicon) -> list:
    """``[(title, text, visible printed op IDs)]`` of the groups the printer
    shows for ``data``: edit mode keeps the steps of ``base`` when the text
    shows the same groups."""
    from .printer import step_signature
    return step_signature(data, lexicon)


def parse_commands(text: str, *, lexicon=None, base=None, id_factory=None, document_id=None) -> ParseResult:
    """Build a document from «Команды» ``text`` (commands.md).

    ``lexicon`` — an ``animageo-lexicon/v1`` dict or a :class:`Lexicon`
    (``None``: the copy shipped with the library); ``base`` — a document to
    edit (``None``: a new document with ``document_id`` or a random ID);
    ``id_factory(kind)`` — new IDs, ``kind`` is ``"operation"`` or
    ``"element"`` (a factory without parameters is called bare; default
    :func:`time_ordered_id`); IDs already in use are skipped.
    """
    lex = as_lexicon(lexicon)
    return _Builder(lex, base, id_factory, document_id).run(text)
