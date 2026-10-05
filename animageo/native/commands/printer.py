"""``print_commands``: a construction document → text of «Команды»
(commands.md §6).

One line per operation in topological order (Kahn, ties by operation ID);
hidden pair and ``∠ABC`` operations are not printed — their elements appear
in arguments as ``BC`` and ``∠ABC``. The left side lists the output names in
slot order up to the last slot that has a name or is used; a slot in the
middle without a name gets the default name the parser would give.
``parse_commands(print_commands(doc).text)`` rebuilds the same structure
(commands.md §6.3).
"""
from __future__ import annotations

from typing import NamedTuple

from ..document import as_document, bound_producer, cyclic_operations, iter_refs, op_dependencies
from ..edit import name_key
from ..kernel.evaluate import _order
from ..registry import FREE_INPUT_DEFAULTS, registry
from .build import HELPER_OPS, helper_key, is_helper, pair_op
from .issues import CommandIssue, LineError, ambiguous_name
from .lexicon import ANGLE3, INPUT, NOT, NUM, PAIR, Lexicon
from .naming import TakenKeys, next_name, pair_readings, polygon_side_names
from .numbers import format_number
from .resolve import resolve

__all__ = ['PrintResult', 'print_commands']


class PrintResult(NamedTuple):
    """``text`` — the lines joined with ``\\n`` (no trailing newline);
    ``lines`` — ``[{line, operationIds, elementIds}]``; ``issues`` —
    warnings (:class:`CommandIssue`): ``ambiguous_name``,
    ``unprintable_pair``, ``unprintable_params``, ``unprintable_operation``."""

    text: str
    lines: list
    issues: list


class _Printer:
    def __init__(self, doc, lexicon: Lexicon):
        self.doc = as_document(doc)
        self.data = self.doc.data
        self.lex = lexicon
        self.reg = registry()
        self.ops = self.doc.operations
        self.elements = self.doc.elements
        self.helpers = {op_id for op_id in self.ops if is_helper(self.data, op_id)}
        self.used = {ref for op in self.ops.values() for arg in (op.get('args') or {}).values()
                     for ref in iter_refs(arg)}
        self.names = {}
        for el_id, el in self.elements.items():
            name = el.get('displayName') if isinstance(el, dict) else None
            if isinstance(name, str) and name:
                self.names[el_id] = name
        self.taken = {name_key(n) for n in self.names.values()}     # name keys in use
        self.scope_keys = {}            # name key → element ID of the lines printed so far
        self.scope_ids = set()          # the values of scope_keys
        self.scope_points = set()       # the keys of scope_keys that are points
        self.made = {}                  # (op, point IDs) → visible operations a pair could mean
        for op_id, op in self.ops.items():
            key = None if op_id in self.helpers else helper_key(op)
            if key is not None:
                self.made.setdefault(key, []).append(op_id)
        self.issues = []
        self.left_at = []               # (line, left names) of the printed lines

    # ── names ────────────────────────────────────────────────────────────

    def _left(self, op_id: str, record: dict) -> list:
        op = self.ops[op_id]
        args = op.get('args') or {}
        slots = self.reg.output_slots(record, args)
        by_slot = {o.get('slot'): o.get('elementId') for o in op.get('outputs') or ()
                   if o.get('elementId') in self.elements}
        last = -1
        for i, slot in enumerate(slots):
            el = by_slot.get(slot)
            if el is not None and (el in self.names or el in self.used):
                last = i
        names = []
        sides = None
        for i, slot in enumerate(slots[:last + 1]):
            el = by_slot.get(slot)
            if el is not None and el in self.names:
                names.append(self.names[el])
                continue
            if slot.startswith('side.') and op.get('op') == 'polygon.by_points':
                if sides is None:
                    vertex_names = [self.names.get(r, '') for r in iter_refs(args.get('vertices'))]
                    sides = polygon_side_names(vertex_names, TakenKeys(self.taken))
                name = sides[int(slot.split('.')[1]) - 1]
                if name_key(name) in self.taken:
                    name = next_name('segment', TakenKeys(self.taken))
            else:
                name = next_name(self.reg.output_type(record, slot, args) or 'line', TakenKeys(self.taken))
            if not name:
                name = next_name('line', TakenKeys(self.taken))
            self.taken.add(name_key(name))
            if el is not None:
                self.names[el] = name
            names.append(name)
        return names

    # ── arguments ────────────────────────────────────────────────────────

    def _helper_text(self, el_id: str):
        producer = bound_producer(self.doc, el_id)
        op = self.ops[producer]
        points = [(op.get('args') or {}).get(s, {}).get('elementId') for s in HELPER_OPS[op['op']]]
        text = ''.join(self.names.get(p, '?') for p in points)
        return op['op'], points, text

    def _pair_problem(self, el_id: str, position, helper_op: str, points, text: str) -> bool:
        if helper_op == 'angle.by_points':
            parts = 3
            if position is not None and ANGLE3 not in self._accepts(position):
                return True
        else:
            parts = 2
            if position is not None and pair_op(position.type) != helper_op:
                return True
            if name_key(text) in self.scope_keys:
                return True
        point_keys = self.scope_points
        if any(p not in self.names for p in points):
            return True
        if _count_splits(text, point_keys, parts) != 1:
            return True
        # a visible element made the same way would be read instead
        for op_id in self.made.get((helper_op, tuple(points)), ()):
            if any(o.get('elementId') in self.scope_ids for o in self.ops[op_id].get('outputs') or ()):
                return True
        return False

    @staticmethod
    def _accepts(position):
        from .lexicon import _accept_set
        return _accept_set(position)

    def _ref(self, el_id: str, position):
        """``(text, kind, pair problem)`` of a reference."""
        producer = bound_producer(self.doc, el_id)
        if producer in self.helpers:
            helper_op, points, text = self._helper_text(el_id)
            problem = self._pair_problem(el_id, position, helper_op, points, text)
            if helper_op == 'angle.by_points':
                return '∠' + text, ANGLE3, problem
            return text, PAIR, problem
        name = self.names.get(el_id)
        if name is None:
            return el_id, (self.elements.get(el_id) or {}).get('type', ''), True
        el_type = self.elements[el_id].get('type')
        if position is not None and position.known:
            return 'не ' + name, NOT, False
        return name, el_type, False

    def _arg(self, arg, position):
        """``[(text, kind, problem)]`` of an argument (several for a list)."""
        if not isinstance(arg, dict):
            return [('?', '', True)]
        if arg.get('kind') == 'number':
            return [(format_number(arg.get('value')), NUM, False)]
        if arg.get('kind') == 'list':
            out = []
            for item in arg.get('items') or ():
                out.extend(self._arg(item, position))
            return out
        return [self._ref(arg.get('elementId'), position)]

    def _free_value(self, op: dict, record: dict):
        free = record.get('free')
        if free is None:
            return None
        el = next((o.get('elementId') for o in op.get('outputs') or ()
                   if o.get('slot') == record['outputs'][0]['slot']), None)
        value = self.doc.inputs.get(el) if el is not None else None
        if value is None and el is not None:
            value = FREE_INPUT_DEFAULTS.get(free['kind'])     # an absent angle input is 0
        if not isinstance(value, dict) or value.get('kind') != free['kind']:
            return None
        return value.get('value')

    def _layout(self, entry, op: dict, record: dict):
        """``(parts, dropped)`` for ``entry``: ``parts`` — the printed
        arguments ``[(text, kind, problem, position)]``, ``dropped`` — params
        or the input that could not be printed; ``None`` when ``entry``
        cannot print ``op``."""
        args = op.get('args') or {}
        value = self._free_value(op, record)
        cells = []
        for position in entry.positions:
            if position.kind == 'input':
                if position.slot not in args:
                    return None
                cells.append([(t, k, p, position) for t, k, p in self._arg(args[position.slot], position)])
            elif position.kind == 'param':
                arg = args.get(position.slot)
                cells.append(None if arg is None else [(format_number(arg.get('value')), NUM, False, position)])
            else:
                cells.append(None if value is None else [(format_number(value), NUM, False, position)])
        present = [i for i, c in enumerate(cells) if c is not None]
        last = present[-1] if present else -1
        first_gap = next((i for i in range(last + 1) if cells[i] is None), None)
        cut = last + 1 if first_gap is None else first_gap
        if cut < entry.min_args:
            return None
        dropped = [entry.positions[i].slot or INPUT for i in range(cut, len(cells)) if cells[i] is not None]
        parts = [part for c in cells[:cut] for part in c]
        return parts, dropped

    def _reads_back(self, entry, parts, op_name: str) -> bool:
        entries = self.lex.lookup(entry.name)
        try:
            res = resolve(entries, [k for _t, k, _p, _pos in parts])
        except LineError:
            return False
        return res.entry.op == op_name and not res.swapped

    def _call(self, op: dict, record: dict):
        """``(command, parts, dropped)`` for a registry operation."""
        candidates = [e for e in self.lex.entries if e.op == op['op']] + self.lex.lookup(op['op'])
        best = None
        for entry in candidates:
            layout = self._layout(entry, op, record)
            if layout is None:
                continue
            parts, dropped = layout
            if not self._reads_back(entry, parts, op['op']):
                continue
            if not dropped:
                return entry.name, parts, dropped
            if best is None or len(dropped) < len(best[2]):
                best = (entry.name, parts, dropped)
        return best

    # ── lines ────────────────────────────────────────────────────────────

    def run(self) -> PrintResult:
        deps = op_dependencies(self.doc)
        order = _order(list(self.ops), deps, cyclic_operations(deps))
        lines, out = [], []
        for op_id in order:
            if op_id in self.helpers:
                continue
            text, info = self._line(op_id, len(lines) + 1)
            lines.append(text)
            out.append(info)
            for el in info['elementIds']:
                name = self.names.get(el)
                if name and name_key(name) not in self.scope_keys:
                    self.scope_keys[name_key(name)] = el
                    self.scope_ids.add(el)
                    if self.elements[el].get('type') == 'point':
                        self.scope_points.add(name_key(name))
        self._ambiguous_names()
        return PrintResult('\n'.join(lines), out, self.issues)

    def _ambiguous_names(self) -> None:
        """``ambiguous_name`` at a left name that also reads as two point
        names of the document (commands.md §3); first on its line."""
        point_keys = {name_key(name) for el, name in self.names.items()
                      if (self.elements.get(el) or {}).get('type') == 'point'}
        found = []
        for line_no, left in self.left_at:
            column = 1
            for name in left:
                readings = pair_readings(name, point_keys)
                if readings:
                    found.append(ambiguous_name(name, readings, line_no, column))
                column += len(name) + 2
        if found:
            self.issues = sorted(self.issues + found, key=lambda i: (i.line, i.code != 'ambiguous_name'))

    def _warn(self, code: str, line: int, column: int, message: str):
        self.issues.append(CommandIssue(code, line, column, message, 'warning'))

    def _line(self, op_id: str, line_no: int):
        op = self.ops[op_id]
        record = self.reg.get(op.get('op'))
        outputs = [o.get('elementId') for o in op.get('outputs') or () if o.get('elementId') in self.elements]
        helpers = []
        for arg in (op.get('args') or {}).values():
            for ref in iter_refs(arg):
                producer = bound_producer(self.doc, ref)
                if producer in self.helpers and producer not in helpers:
                    helpers.append(producer)
        info = {'line': line_no, 'operationIds': [op_id] + helpers, 'elementIds': outputs}
        if record is None:
            parts = []
            for slot, arg in (op.get('args') or {}).items():
                parts.extend(t for t, _k, _p in self._arg(arg, None))
            for el in outputs:
                self.names.setdefault(el, self.names.get(el) or el)
            left = [self.names[el] for el in outputs]
            prefix = f"{', '.join(left)} = " if left else ''
            self.left_at.append((line_no, left))
            self._warn('unprintable_operation', line_no, len(prefix) + 1,
                       f'операции {op.get("op")} нет в реестре')
            return f"{prefix}{op.get('op')}({', '.join(parts)})", info
        left = self._left(op_id, record)
        self.left_at.append((line_no, left))
        prefix = f"{', '.join(left)} = " if left else ''
        column = len(prefix) + 1
        if op['op'] == 'point.free':
            value = self._free_value(op, record)
            if not (isinstance(value, list) and len(value) == 2):
                self._warn('unprintable_operation', line_no, column, 'у свободной точки нет координат')
                value = [0, 0]
            return f'{prefix}({format_number(value[0])}, {format_number(value[1])})', info
        if op['op'] == 'number.free' and not (op.get('args') or {}):
            value = self._free_value(op, record)
            if value is not None:
                return f'{prefix}{format_number(value)}', info
        call = self._call(op, record)
        if call is None:
            # an operation that does not fit its registry record: print what it
            # has in registry slot order, so the parser names the problem
            args = op.get('args') or {}
            order = [i['slot'] for i in record.get('inputs', ())] + [p['slot'] for p in record.get('params', ())]
            parts = []
            for slot in order + sorted(set(args) - set(order)):
                if slot in args:
                    parts.extend(t for t, _k, _p in self._arg(args[slot], None))
            self._warn('unprintable_operation', line_no, column,
                       f'операция {op["op"]} не соответствует реестру')
            return f"{prefix}{op['op']}({', '.join(parts)})", info
        command, parts, dropped = call
        text = f'{prefix}{command}('
        for i, (part, _kind, problem, _position) in enumerate(parts):
            if i:
                text += ', '
            if problem:
                self._warn('unprintable_pair', line_no, len(text) + 1,
                           f'{part} не прочитать обратно как тот же объект')
            text += part
        text += ')'
        if dropped:
            self._warn('unprintable_params', line_no, column,
                       f'не напечатаны: {", ".join(dropped)} (пропуск в середине)')
        return text, info


def _count_splits(text: str, keys: set, parts: int) -> int:
    if parts == 1:
        return 1 if text and name_key(text) in keys else 0
    total = 0
    for k in range(1, len(text)):
        if name_key(text[:k]) in keys:
            total += _count_splits(text[k:], keys, parts - 1)
    return total


def print_commands(doc, *, lexicon=None) -> PrintResult:
    """The text of «Команды» for ``doc`` (commands.md §6)."""
    lex = lexicon if isinstance(lexicon, Lexicon) else Lexicon(lexicon)
    return _Printer(doc, lex).run()
