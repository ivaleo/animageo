"""Overload resolution (commands.md §4): which lexicon entry a call means and
which argument goes to which position.

An argument is described by its *kind*: an element type (``point``,
``segment``…) or one of the ``#`` kinds of :mod:`.lexicon` (a number
literal, a point literal, ``не A``, a pair of points, ``∠ABC``). The printer
uses the same function to make sure a printed call reads back as the
operation it was printed from.
"""
from __future__ import annotations

from dataclasses import dataclass

from .issues import LineError
from .lexicon import ANGLE3, INPUT, NOT, NUM, PAIR, PT, Entry, normalize_name

__all__ = ['Resolution', 'assign', 'resolve', 'kind_text', 'signature_text', 'closest_name', 'levenshtein']

_LITERALS = frozenset({NUM, PT})

_TYPE_TEXT = {
    'point': 'точка', 'line': 'прямая', 'segment': 'отрезок', 'ray': 'луч', 'vector': 'вектор',
    'circle': 'окружность', 'polygon': 'многоугольник', 'angle': 'угол', 'number': 'число',
    'mark': 'отметка', 'linear': 'прямая, отрезок или луч', 'circular': 'окружность',
    'curve': 'линия или окружность', 'path': 'линия, окружность или многоугольник',
    NUM: 'число', PT: 'координаты', NOT: '«не A»', PAIR: 'пара точек', ANGLE3: '∠ABC',
    'pathParameter': 'параметр на пути',
    'arc': 'дуга', 'sector': 'сектор', 'polyline': 'ломаная',
    'round': 'окружность, дуга или сектор', 'vertexed': 'отрезок, ломаная или многоугольник',
}


def kind_text(kind: str) -> str:
    return _TYPE_TEXT.get(kind, kind)


@dataclass(frozen=True)
class Resolution:
    """``entry`` and, per position, the argument indices it takes: ``None``
    (left out), an index, or a list of indices (a list position).
    ``swapped`` — the two arguments of ``intersect.line_circle`` came in the
    other order."""

    entry: Entry
    slots: tuple
    swapped: bool = False


def _fits(position, kind) -> bool:
    return kind in position_accepts(position)


def position_accepts(position) -> frozenset:
    from .lexicon import _accept_set
    return _accept_set(position)


def assign(entry: Entry, kinds):
    """Per-position argument indices of ``kinds`` for ``entry``, or ``None``
    when the number of arguments does not fit. A list position takes the run
    of non-literal arguments that starts at it; literals go to the params and
    ``$input`` after it."""
    positions = entry.positions
    n = len(kinds)
    list_at = next((i for i, p in enumerate(positions) if p.list), None)
    if list_at is None:
        if not entry.min_args <= n <= len(positions):
            return None
        return tuple(list(range(n)) + [None] * (len(positions) - n))
    if n < list_at:
        return None
    run = list_at
    while run < n and kinds[run] not in _LITERALS:
        run += 1
    count = run - list_at
    tail = n - run
    tail_positions = len(positions) - list_at - 1
    if count < positions[list_at].min or tail > tail_positions:
        return None
    if list_at + 1 + tail < entry.min_args:
        return None
    slots = list(range(list_at)) + [list(range(list_at, run))] + list(range(run, n))
    slots += [None] * (len(positions) - len(slots))
    return tuple(slots)


def _mismatch(entry: Entry, slots, kinds):
    """``(matched count, first bad argument index or None)``."""
    matched, bad = 0, None
    for position, taken in zip(entry.positions, slots):
        if taken is None:
            continue
        for index in (taken if isinstance(taken, list) else [taken]):
            if _fits(position, kinds[index]):
                matched += 1
            elif bad is None or index < bad:
                bad = index
    return matched, bad


def signature_text(entry: Entry) -> str:
    parts = []
    for position in entry.positions:
        if position.kind == INPUT:
            text = 'координаты' if position.type == 'point' else 'значение'
        elif position.kind == 'param':
            text = position.slot
        elif position.known:
            text = 'не точка'
        else:
            text = kind_text(position.type)
            if position.list:
                text += ', …'
        parts.append(text + ('?' if position.optional else ''))
    return f"{entry.name}({', '.join(parts)})"


def resolve(entries, kinds, columns=None, command_column: int = 1, command: str = '') -> Resolution:
    """The resolution of a call of ``entries`` (one name) with ``kinds``;
    raises :class:`LineError` ``arity`` or ``type_mismatch``. The first
    fitting entry in lexicon order wins; ``intersect.line_circle`` also takes
    its two arguments the other way round."""
    columns = list(columns or [command_column] * len(kinds))
    best = None
    arity_ok = False
    for entry in entries:
        slots = assign(entry, kinds)
        if slots is None:
            continue
        arity_ok = True
        matched, bad = _mismatch(entry, slots, kinds)
        if bad is None:
            return Resolution(entry, slots)
        if best is None or matched > best[0]:
            best = (matched, bad, entry)
    if len(kinds) == 2:
        swapped = [kinds[1], kinds[0]]
        for entry in entries:
            if entry.op != 'intersect.line_circle':
                continue
            slots = assign(entry, swapped)
            if slots is not None and _mismatch(entry, slots, swapped)[1] is None:
                return Resolution(entry, slots, swapped=True)
    name = command or (entries[0].name if entries else '')
    hint = '; '.join(dict.fromkeys(signature_text(e) for e in entries))
    if not arity_ok:
        raise LineError('arity', command_column,
                        f'{name}: не то число аргументов ({len(kinds)})', hint=hint or None)
    _matched, bad, entry = best
    position = None
    slots = assign(entry, kinds)
    for pos, taken in zip(entry.positions, slots):
        if taken == bad or (isinstance(taken, list) and bad in taken):
            position = pos
    want = kind_text('number' if position is not None and position.kind != 'input' else
                     (position.type if position is not None else ''))
    if position is not None and position.known:
        want = '«не точка»'
    raise LineError('type_mismatch', columns[bad],
                    f'{name}: аргумент {bad + 1} — {kind_text(kinds[bad])}, ожидается {want}',
                    hint=signature_text(entry))


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def closest_name(name: str, names, limit: int = 2):
    """The command name nearest to ``name`` (at most ``limit`` edits), or ``None``."""
    key = normalize_name(name)
    best = None
    for candidate in names:
        distance = levenshtein(key, normalize_name(candidate))
        if distance <= limit and (best is None or distance < best[0]):
            best = (distance, candidate)
    return best[1] if best else None
