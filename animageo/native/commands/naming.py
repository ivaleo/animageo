"""Default names of new elements (commands.md §5): the web canon
(``naming.ts``, ``canon/naming.md``, constructions spec §3.4) plus Greek
letters for angles.

- points — the next free capital Latin letter ``A…Z``, then ``A_1…Z_1``,
  ``A_2…``;
- lines, segments, rays, vectors, numbers — ``a b c d f g h j k l m n o p q
  r s t u v w`` (no ``e i x y z``), then with an index;
- circles — the same letters starting at ``c`` (``c d f … w a b``);
- polygons — ``t``, ``t_1``, ``t_2``…;
- angles — ``α β γ δ ε ζ η θ κ λ μ ν ξ π ρ σ τ φ χ ψ ω``, then with an index;
- marks and hidden elements — ``""``;
- the sides of a triangle with one-letter capital vertices — the school
  names (``side.i`` is opposite vertex ``i+2``: ``AB → c``, ``BC → a``,
  ``CA → b``) when free, the others the next free lower-case letters.

"Free" compares :func:`animageo.native.edit.name_key` (``A_{1}`` is ``A_1``).
"""
from __future__ import annotations

from ..edit import name_key

__all__ = [
    'UPPER',
    'LOWER',
    'GREEK',
    'next_name',
    'kind_of_type',
    'polygon_side_names',
    'pair_readings',
    'suggest_name',
]

UPPER = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
LOWER = tuple('abcdfghjklmnopqrstuvw')
GREEK = tuple('αβγδεζηθκλμνξπρστφχψω')

_KINDS = {
    'point': ('point',),
    'line': ('line', 'segment', 'ray', 'vector', 'number'),
    'circle': ('circle',),
    'polygon': ('polygon',),
    'angle': ('angle',),
    'none': ('mark',),
}


def kind_of_type(element_type: str) -> str:
    """The naming kind of an element type: ``point``, ``line``, ``circle``,
    ``polygon``, ``angle`` or ``none`` (no name); an unknown type is ``line``."""
    for kind, types in _KINDS.items():
        if element_type in types:
            return kind
    return 'line'


class TakenKeys(frozenset):
    """``taken`` given as name keys already (no ``name_key`` per call)."""


def _keys(taken) -> set:
    if isinstance(taken, TakenKeys):
        return set(taken)
    return {name_key(n) for n in taken if isinstance(n, str) and n}


def _first_free(letters, keys: set, start: int = 0) -> str:
    order = list(letters[start:]) + list(letters[:start])
    index = 0
    while True:
        for letter in order:
            name = f'{letter}_{index}' if index else letter
            if name not in keys:
                return name
        index += 1


def next_name(element_type: str, taken) -> str:
    """The default name of a new element of ``element_type`` given the names
    in use ``taken``; ``""`` for a mark."""
    kind = kind_of_type(element_type)
    keys = _keys(taken)
    if kind == 'point':
        return _first_free(UPPER, keys)
    if kind == 'circle':
        return _first_free(LOWER, keys, LOWER.index('c'))
    if kind == 'polygon':
        return _first_free(('t',), keys)
    if kind == 'angle':
        return _first_free(GREEK, keys)
    if kind == 'none':
        return ''
    return _first_free(LOWER, keys)


def polygon_side_names(vertex_names, taken) -> list:
    """Names of ``side.1 … side.n`` of a polygon with ``vertex_names``."""
    keys = _keys(taken)
    names = list(vertex_names)
    n = len(names)
    school = []
    if n == 3 and all(len(v) == 1 and v in UPPER for v in names):
        school = [names[(i + 2) % 3].lower() for i in range(3)]
    own = [s if s and s not in keys and s in LOWER else '' for s in school]
    keys |= {s for s in own if s}
    out = []
    for i in range(n):
        if i < len(own) and own[i]:
            out.append(own[i])
            continue
        name = _first_free(LOWER, keys)
        keys.add(name)
        out.append(name)
    return out


def pair_readings(name: str, point_keys) -> list:
    """The ways ``name`` reads as two point names: ``[(head, tail)]`` for
    every split whose parts have their :func:`name_key` in ``point_keys``
    (``BC`` with points ``B``, ``C`` → ``[("B", "C")]``)."""
    out = []
    for k in range(1, len(name)):
        head, tail = name[:k], name[k:]
        if name_key(head) in point_keys and name_key(tail) in point_keys:
            out.append((head, tail))
    return out


def suggest_name(name: str, taken) -> str:
    """A free name with the same letters and the next index: ``A`` taken → ``A_1``."""
    keys = _keys(taken)
    head = ''
    for ch in name:
        if ch.isalpha():
            head += ch
        else:
            break
    head = head or 'A'
    k = 1
    while f'{head}_{k}' in keys:
        k += 1
    return f'{head}_{k}'
