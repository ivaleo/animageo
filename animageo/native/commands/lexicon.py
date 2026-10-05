"""The «Команды» lexicon ``animageo-lexicon/v1``: command names → operations.

::

    {"format": "animageo-lexicon/v1",
     "commands": [{"name": "Середина", "aliases": ["Midpoint"], "op": "point.midpoint",
                   "form"?: [slot | "$input", …], "minArgs"?: n},
                  {"name": "ПроверкаПараллельности", "aliases": ["AreParallel"], "check": "parallel"}, …],
     "keywords"?: {"condition": ["Условие", "Condition"], "check": ["Проверить", "Check"], …}}

An entry with ``check`` (a statement kind, :data:`CHECK_KINDS`) instead of
``op`` is a check command (plan L3 §4.1): its arguments are the objects of
the statement, it reads as ``Проверить(…)`` and prints as ``Проверить(a ∥ b)``.
``keywords`` (1.9.0a3) renames the words of the grammar; a missing key keeps
the default of :data:`DEFAULT_KEYWORDS` (the first word prints).

An entry pairs a name (and its aliases) with a registry operation; one name
may stand for several operations (overloads), told apart by the number and
the kinds of the arguments. ``form`` is the order of the positional
arguments: input slots, params and ``$input`` (the value of a free input);
by default the input slots in registry order, then the params. ``minArgs``
says how many leading positions are required; by default every position up
to the last one that cannot be left out (an input slot, a required param,
a ``$input`` without a default — the ``point`` input has none, a
``pathParameter`` defaults to the path's ``default``, a ``number`` to the
op's ``min`` or ``0``, an ``angle`` to ``0``).

Names compare without case and without whitespace (``Серединный
перпендикуляр`` is ``СерединныйПерпендикуляр``). A registry operation ID
(``point.midpoint``) is also a command name, written exactly, with the
positions: input slots, ``$input`` of a free op, params; the printer falls
back to it for an operation the lexicon does not name.

The web generates its lexicon from its registry overlay; the copy shipped
here (``lexicon.v1.json``) is the default for the command line and tests.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from ..canonical import canonical_json, sha256_of
from ..registry import FREE_INPUT_DEFAULTS, registry

__all__ = [
    'CHECK_KINDS',
    'DEFAULT_KEYWORDS',
    'INPUT',
    'LEXICON_FORMAT',
    'Entry',
    'Lexicon',
    'LexiconError',
    'Position',
    'default_lexicon',
    'lexicon_hash',
    'lexicon_problems',
    'normalize_name',
]

LEXICON_FORMAT = 'animageo-lexicon/v1'
INPUT = '$input'
DEFAULT_PATH = Path(__file__).with_name('lexicon.v1.json')

# Argument kinds a position accepts, besides element types: a number
# literal, a point literal ``(x, y)``, ``не A`` (the known point of an
# intersection), a pair of points ``BC`` and three points ``∠ABC``.
NUM, PT, NOT, PAIR, ANGLE3 = '#num', '#pt', '#not', '#pair', '#angle3'

# Words of the grammar (plan L3 §4.5); ``given`` and ``relation`` are
# additions of 1.9.0a3: a comment line «# Дано» opens the explicit «Дано»
# step, ``Отношение(a, b)`` is a query.
DEFAULT_KEYWORDS = {
    'condition': ['Условие', 'Condition'],
    'check': ['Проверить', 'Check'],
    'move': ['двигать', 'move'],
    'touches': ['касается', 'touches'],
    'not': ['не', 'not'],
    'near': ['около', 'near'],
    'given': ['Дано', 'Given'],
    'relation': ['Отношение', 'Relation'],
}
# Statement kinds a check command may stand for, with their arguments:
# two objects, a point and an object, or a list of points or lines.
CHECK_KINDS = {
    'parallel': 'two', 'perpendicular': 'two', 'tangent': 'two', 'congruent': 'two',
    'on': 'point_object', 'coincident': 'two_points',
    'collinear': 'points', 'concyclic': 'points', 'concurrent': 'lines',
}


class LexiconError(ValueError):
    """The lexicon is not usable; ``problems`` lists why."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('; '.join(self.problems))


def normalize_name(name: str) -> str:
    """The comparison key of a command name: no case, no whitespace."""
    return ''.join(str(name).split()).casefold()


def default_lexicon() -> dict:
    """A copy of the lexicon shipped with the library."""
    with open(DEFAULT_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def lexicon_hash(data: dict) -> str:
    """``sha256:`` of the canonical JSON of a lexicon (``lexiconHash`` of fixtures)."""
    return sha256_of(canonical_json(data))


@dataclass(frozen=True)
class Position:
    """One positional argument of an entry.

    ``kind``: ``input`` (an input slot), ``param`` or ``$input``. ``type``:
    the slot type, ``number`` for a param, the free kind for ``$input``.
    ``optional``: may be left out at the end. ``default``: the value used
    when a ``$input`` is left out (``None`` for a param: it stays absent).
    """

    kind: str
    slot: str | None
    type: str
    list: bool = False
    min: int = 1
    optional: bool = False
    default: object = None
    known: bool = False          # the known point of an ``other_than`` intersection


@dataclass(frozen=True)
class Entry:
    """A lexicon entry resolved against the registry."""

    index: int
    name: str
    aliases: tuple
    op: str
    positions: tuple
    min_args: int

    @property
    def keys(self) -> tuple:
        return tuple(dict.fromkeys(normalize_name(n) for n in (self.name, *self.aliases)))

    def accepts(self, position: Position) -> frozenset:
        """Argument kinds (element types and the ``#`` kinds) ``position`` takes."""
        return _accept_set(position)


def _input_default(record: dict):
    """``(has default, value)`` of the free input of ``record``."""
    free = record.get('free') or {}
    kind = free.get('kind')
    if kind == 'pathParameter':
        return True, None            # the path's default, known once the path is
    if kind == 'number':
        param = next((p for p in record.get('params', ()) if p['slot'] == 'min'), None)
        return True, None if param is not None else 0.0
    if kind in FREE_INPUT_DEFAULTS:
        return True, FREE_INPUT_DEFAULTS[kind]['value']
    return False, None


def _positions(record: dict, form) -> tuple:
    inputs = {i['slot']: i for i in record.get('inputs', ())}
    params = {p['slot']: p for p in record.get('params', ())}
    known = None
    branch = record.get('branch') or {}
    if branch.get('policy') == 'other_than':
        known = 'known'
    if form is None:
        form = [i['slot'] for i in record.get('inputs', ())] + [p['slot'] for p in record.get('params', ())]
    out = []
    for item in form:
        if item == INPUT:
            has_default, value = _input_default(record)
            out.append(Position(INPUT, None, record['free']['kind'], optional=has_default, default=value))
        elif item in inputs:
            spec = inputs[item]
            out.append(Position('input', item, spec['type'], list=bool(spec.get('list')),
                                min=int(spec.get('min') or 1), known=item == known))
        else:
            spec = params[item]
            out.append(Position('param', item, 'number', optional=bool(spec.get('optional')),
                                default=spec.get('default')))
    return tuple(out)


def _default_min_args(positions) -> int:
    last = -1
    for i, pos in enumerate(positions):
        if not pos.optional:
            last = i
    return last + 1


def _accept_set(pos: Position) -> frozenset:
    reg = registry()
    if pos.kind == 'param':
        return frozenset({NUM})
    if pos.kind == INPUT:
        return frozenset({PT}) if pos.type == 'point' else frozenset({NUM})
    if pos.known:
        return frozenset({NOT})
    types = {pos.type, *reg.families.get(pos.type, ())}
    out = set(types)
    if 'number' in types:
        out.add(NUM)
    if 'segment' in types or 'line' in types:
        out.add(PAIR)
    if 'angle' in types:
        out.add(ANGLE3)
    return frozenset(out)


def _entry_problems(i: int, entry, reg) -> list:
    where = f'commands[{i}]'
    if not isinstance(entry, dict):
        return [f'{where}: not an object']
    problems = []
    if 'check' in entry:
        unknown = sorted(set(entry) - {'name', 'aliases', 'check'})
        if unknown:
            problems.append(f'{where}: unknown keys {unknown} (a check command has name, aliases, check)')
    else:
        unknown = sorted(set(entry) - {'name', 'aliases', 'op', 'form', 'minArgs'})
        if unknown:
            problems.append(f'{where}: unknown keys {unknown}')
    name = entry.get('name')
    if not isinstance(name, str) or not normalize_name(name):
        problems.append(f'{where}: name must be a non-empty string')
    aliases = entry.get('aliases', [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) and normalize_name(a) for a in aliases):
        problems.append(f'{where}: aliases must be a list of non-empty strings')
    if 'check' in entry:
        if entry['check'] not in CHECK_KINDS:
            problems.append(f'{where}: check must be one of {sorted(CHECK_KINDS)}')
        return problems
    op = entry.get('op')
    record = reg.get(op) if isinstance(op, str) else None
    if record is None:
        problems.append(f'{where}: {op!r} is not an operation of registry {reg.version}')
        return problems
    inputs = [s['slot'] for s in record.get('inputs', ())]
    params = [p['slot'] for p in record.get('params', ())]
    form = entry.get('form')
    if form is not None:
        if not isinstance(form, list) or not all(isinstance(x, str) for x in form):
            problems.append(f'{where}: form must be a list of slot names')
            return problems
        allowed = set(inputs) | set(params) | ({INPUT} if record.get('free') else set())
        for item in form:
            if item not in allowed:
                problems.append(f'{where}: {item!r} is not an input slot, a param or $input of {op}')
        if len(set(form)) != len(form):
            problems.append(f'{where}: form repeats a slot')
        missing = [s for s in inputs if s not in form]
        if missing:
            problems.append(f'{where}: form leaves out the input slots {missing}')
        if problems:
            return problems
    positions = _positions(record, form)
    if record.get('free') and not any(p.kind == INPUT for p in positions) \
            and not _input_default(record)[0]:
        problems.append(f'{where}: {op} needs $input in its form (its input has no default)')
    seen_list = False
    for pos in positions:
        if seen_list and pos.kind == 'input':
            problems.append(f'{where}: an input slot after the list slot (only params and $input may follow it)')
        seen_list = seen_list or pos.list
    min_args = entry.get('minArgs')
    if min_args is not None:
        if not isinstance(min_args, int) or isinstance(min_args, bool) or not 0 <= min_args <= len(positions):
            problems.append(f'{where}: minArgs must be an integer in 0..{len(positions)}')
        else:
            for pos in positions[min_args:]:
                if not pos.optional:
                    problems.append(f'{where}: position {pos.slot or INPUT!r} cannot be left out (minArgs {min_args})')
    return problems


def _arg_sets(entry: Entry, n: int):
    """Accept sets of ``n`` arguments of ``entry``, or ``None`` when ``entry``
    does not take ``n`` arguments (a list position takes a run of
    non-literal arguments)."""
    positions = entry.positions
    list_at = next((i for i, p in enumerate(positions) if p.list), None)
    if list_at is None:
        if not entry.min_args <= n <= len(positions):
            return None
        return [_accept_set(p) for p in positions[:n]]
    head = [_accept_set(p) for p in positions[:list_at]]
    tail_positions = positions[list_at + 1:]
    item = _accept_set(positions[list_at])
    sets = []
    for tail in range(len(tail_positions), -1, -1):
        count = n - list_at - tail
        if count < positions[list_at].min:
            continue
        if list_at + 1 + tail < entry.min_args:
            continue
        sets = head + [item] * count + [_accept_set(p) for p in tail_positions[:tail]]
        return sets
    return None


def _overload_problems(entries) -> list:
    problems = []
    by_key = {}
    for entry in entries:
        for key in entry.keys:
            by_key.setdefault(key, []).append(entry)
    reported = set()
    for key, group in by_key.items():
        for a_i, a in enumerate(group):
            for b in group[a_i + 1:]:
                pair = (a.index, b.index)
                if pair in reported:
                    continue
                overlap = shadowed = nested = False
                for n in range(0, 12):
                    sa, sb = _arg_sets(a, n), _arg_sets(b, n)
                    if sa is None or sb is None:
                        continue
                    if all(x & y for x, y in zip(sa, sb)):
                        overlap = True
                        if all(y <= x for x, y in zip(sa, sb)):
                            shadowed = True          # the earlier entry takes everything the later does
                        elif all(x <= y for x, y in zip(sa, sb)):
                            nested = True
                        else:
                            problems.append(f'{key!r}: {a.op} and {b.op} take the same arguments '
                                            f'({n}); the overload is ambiguous')
                            reported.add(pair)
                            break
                if pair in reported or not overlap:
                    continue
                if shadowed:
                    problems.append(f'{key!r}: {b.op} (commands[{b.index}]) is unreachable: '
                                    f'{a.op} (commands[{a.index}]) comes first and takes the same arguments')
                    reported.add(pair)
                elif not nested:
                    reported.add(pair)
    return problems


def _build_entries(data: dict, reg) -> list:
    entries = []
    for i, raw in enumerate(data['commands']):
        if 'check' in raw:
            continue
        record = reg.get(raw['op'])
        positions = _positions(record, raw.get('form'))
        min_args = raw.get('minArgs')
        entries.append(Entry(i, raw['name'], tuple(raw.get('aliases', ())), raw['op'], positions,
                             _default_min_args(positions) if min_args is None else min_args))
    return entries


def lexicon_problems(data) -> list:
    """Why ``data`` is not a usable lexicon (an empty list when it is).

    Structure, operations of the registry, forms and ``minArgs``, and the
    overloads of one name: two entries may share a name when no argument
    list fits both, or when one fits a subset of what the other does and the
    narrower one comes first (it wins, §5.4 of the plan); an ambiguous or
    unreachable overload is a problem.
    """
    reg = registry()
    if not isinstance(data, dict):
        return ['the lexicon must be an object']
    problems = []
    if data.get('format') != LEXICON_FORMAT:
        problems.append(f'format must be {LEXICON_FORMAT!r}')
    unknown = sorted(set(data) - {'format', 'commands', 'keywords'})
    if unknown:
        problems.append(f'unknown keys {unknown}')
    keywords = data.get('keywords', {})
    if not isinstance(keywords, dict):
        problems.append('keywords must be an object')
    else:
        for key, words in keywords.items():
            if key not in DEFAULT_KEYWORDS:
                problems.append(f'keywords: unknown key {key!r}')
            elif not (isinstance(words, list) and words and all(isinstance(w, str) and normalize_name(w)
                                                                   and len(w.split()) == 1 for w in words)):
                problems.append(f'keywords.{key}: a non-empty list of one-word strings')
    commands = data.get('commands')
    if not isinstance(commands, list):
        return problems + ['commands must be a list']
    for i, entry in enumerate(commands):
        problems.extend(_entry_problems(i, entry, reg))
    if problems:
        return problems
    entries = _build_entries(data, reg)
    op_keys = {key for entry in entries for key in entry.keys}
    check_keys = {}
    for i, raw in enumerate(commands):
        if 'check' not in raw:
            continue
        for name in (raw['name'], *raw.get('aliases', ())):
            key = normalize_name(name)
            if key in op_keys:
                problems.append(f'commands[{i}]: the check name {name!r} is also a command name')
            elif check_keys.setdefault(key, raw['check']) != raw['check']:
                problems.append(f'commands[{i}]: the check name {name!r} stands for two statement kinds')
    words = _keywords(data)
    for key, items in words.items():
        for word in items:
            if normalize_name(word) in op_keys or normalize_name(word) in check_keys:
                problems.append(f'keywords.{key}: {word!r} is also a command name')
    return problems + _overload_problems(entries)


def _keywords(data: dict) -> dict:
    out = {k: list(v) for k, v in DEFAULT_KEYWORDS.items()}
    raw = data.get('keywords')
    if isinstance(raw, dict):
        out.update({k: list(v) for k, v in raw.items() if k in out})
    return out


class Lexicon:
    """A checked lexicon: entries by name, the printed name of an operation."""

    def __init__(self, data=None):
        data = default_lexicon() if data is None else data
        problems = lexicon_problems(data)
        if problems:
            raise LexiconError(problems)
        self.data = copy.deepcopy(data)
        self.hash = lexicon_hash(self.data)
        self.entries = _build_entries(self.data, registry())
        self._by_key = {}
        for entry in self.entries:
            for key in entry.keys:
                self._by_key.setdefault(key, []).append(entry)
        self._by_op = {}
        for entry in self.entries:
            self._by_op.setdefault(entry.op, entry)
        self.keywords = _keywords(self.data)
        self._keyword_of = {}
        for key, words in self.keywords.items():
            for word in words:
                self._keyword_of.setdefault(normalize_name(word), key)
        self.checks = {}             # name key → statement kind
        self._check_name = {}        # statement kind → printed name
        for raw in self.data['commands']:
            if 'check' in raw:
                for name in (raw['name'], *raw.get('aliases', ())):
                    self.checks.setdefault(normalize_name(name), raw['check'])
                self._check_name.setdefault(raw['check'], raw['name'])

    def keyword(self, word: str):
        """The key of :data:`DEFAULT_KEYWORDS` that ``word`` is, or ``None``."""
        return self._keyword_of.get(normalize_name(word))

    def word(self, key: str) -> str:
        """The printed word of a keyword (the first one)."""
        return self.keywords[key][0]

    def check_kind(self, name: str):
        """The statement kind of the check command ``name``, or ``None``."""
        return self.checks.get(normalize_name(name))

    def check_name(self, kind: str):
        """The printed name of the check command of ``kind``, or ``None``."""
        return self._check_name.get(kind)

    def lookup(self, name: str) -> list:
        """Entries named ``name`` in lexicon order; a registry op ID written
        exactly gives its default entry."""
        found = self._by_key.get(normalize_name(name))
        if found:
            return list(found)
        reg = registry()
        record = reg.get(name)
        if record is not None:
            form = None
            if record.get('free'):
                form = ([i['slot'] for i in record.get('inputs', ())] + [INPUT]
                        + [p['slot'] for p in record.get('params', ())])
            positions = _positions(record, form)
            return [Entry(-1, name, (), name, positions, _default_min_args(positions))]
        return []

    def entry_for(self, op: str) -> Entry | None:
        """The entry the printer uses for ``op``: the first one in lexicon
        order, or the registry fallback."""
        entry = self._by_op.get(op)
        if entry is not None:
            return entry
        found = self.lookup(op)
        return found[0] if found else None

    def names(self) -> list:
        """Every command name and alias as written, for suggestions."""
        out = []
        for entry in self.entries:
            for name in (entry.name, *entry.aliases):
                if name not in out:
                    out.append(name)
        for raw in self.data['commands']:
            if 'check' in raw:
                for name in (raw['name'], *raw.get('aliases', ())):
                    if name not in out:
                        out.append(name)
        return out
