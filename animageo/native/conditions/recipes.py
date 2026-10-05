"""Recipes v1 (plan L3 §3.5): a statement matched against the pattern of a
recipe gives the bindings of its variables; the receiver is the binding of
``receiver``. Files ``animageo/native/recipes/v1/*.json``, by ``priority``.

Matching (contract shared with the web):

- the forms of a statement: ``eq`` with its sides swapped; ``parallel``,
  ``perpendicular``, ``tangent`` with ``a`` and ``b`` swapped; every pair in
  both orders; every three-point angle reversed — all combinations, in this
  order (sides, objects, pairs, angles; the original first);
- a pattern node ``{"ref": "V"}`` binds ``V`` to an element ID, ``{"pair":
  ["V", "W"]}`` binds both, ``{"value": "V"}`` binds a ``num`` literal or a
  number ``ref``, ``{"deg": "D"}`` a degree literal; any other value must be
  equal; a variable bound twice must get the same value;
- ``requires``: ``point``, ``path``, ``circle`` (the element type, a path from
  the registry family), ``positive`` (a literal > 0 or a number element),
  ``angle_degrees`` (a literal in ``(0, 180)``); no other point variable
  binds the receiver's element.
"""
from __future__ import annotations

import itertools
import json
import math
from functools import lru_cache
from pathlib import Path

from ..registry import registry

RECIPES_DIR = Path(__file__).resolve().parent.parent / 'recipes' / 'v1'
RECIPE_FORMAT = 'animageo-recipe/v1'

__all__ = ['recipes', 'matches', 'forms', 'RECIPES_DIR']


@lru_cache(maxsize=1)
def _load() -> tuple:
    out = []
    for path in sorted(RECIPES_DIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('format') != RECIPE_FORMAT:
            raise ValueError(f'{path.name}: not {RECIPE_FORMAT}')
        out.append(data)
    out.sort(key=lambda r: (r['priority'], r['recipe']))
    return tuple(out)


def recipes() -> list:
    """The recipes by priority (copies)."""
    return json.loads(json.dumps(list(_load())))


def _swap_sides(st):
    if st['kind'] in ('eq', 'ne'):
        return [st, dict(st, left=st['right'], right=st['left'])]
    if st['kind'] in ('parallel', 'perpendicular', 'tangent', 'congruent'):
        return [st, dict(st, a=st['b'], b=st['a'])]
    return [st]


def _node_forms(node):
    """Every form of a node: pairs both ways, three-point angles reversed."""
    if isinstance(node, dict):
        if set(node) == {'pair'} and isinstance(node['pair'], list) and len(node['pair']) == 2:
            p, q = node['pair']
            return [{'pair': [p, q]}, {'pair': [q, p]}]
        if set(node) == {'angle'} and isinstance(node['angle'], list) and len(node['angle']) == 3:
            a, b, c = node['angle']
            return [{'angle': [a, b, c]}, {'angle': [c, b, a]}]
        keys = sorted(node)
        options = [_node_forms(node[k]) for k in keys]
        return [dict(zip(keys, combo)) for combo in itertools.product(*options)]
    if isinstance(node, list):
        options = [_node_forms(x) for x in node]
        return [list(combo) for combo in itertools.product(*options)]
    return [node]


def forms(statement) -> list:
    """The forms of a statement in matching order (the statement first)."""
    out = []
    for st in _swap_sides(statement):
        for form in _node_forms(st):
            if form not in out:
                out.append(form)
    return out


def _unify(pattern, node, binds) -> bool:
    if isinstance(pattern, dict):
        if not isinstance(node, dict):
            return False
        if set(pattern) == {'value'}:
            if set(node) == {'num'}:
                value = ('num', node['num'])
            elif set(node) == {'ref'}:
                value = ('ref', node['ref'])
            else:
                return False
            return _bind(binds, pattern['value'], value)
        if set(pattern) == {'deg'} and isinstance(pattern['deg'], str):
            return set(node) == {'deg'} and _bind(binds, pattern['deg'], ('num', node['deg']))
        if set(pattern) == {'ref'} and isinstance(pattern['ref'], str):
            return set(node) == {'ref'} and isinstance(node['ref'], str) and _bind(binds, pattern['ref'], node['ref'])
        if set(pattern) != set(node):
            return False
        return all(_unify(pattern[k], node[k], binds) for k in sorted(pattern))
    if isinstance(pattern, list):
        if not isinstance(node, list) or len(pattern) != len(node):
            return False
        if all(isinstance(p, str) for p in pattern) and all(isinstance(n, str) for n in node):
            return all(_bind(binds, p, n) for p, n in zip(pattern, node))
        return all(_unify(p, n, binds) for p, n in zip(pattern, node))
    if isinstance(pattern, (int, float)) and isinstance(node, (int, float)) and not isinstance(node, bool):
        return float(pattern) == float(node)
    return pattern == node


def _bind(binds, var, value) -> bool:
    if var in binds:
        return binds[var] == value
    binds[var] = value
    return True


def _requires_hold(doc, recipe, binds) -> bool:
    reg = registry()
    path_types = set(reg.families.get('path', ()))
    points = []
    for var, need in recipe['requires'].items():
        value = binds.get(var)
        if value is None:
            return False
        if need in ('point', 'path', 'circle'):
            el = doc.elements.get(value) if isinstance(value, str) else None
            if el is None:
                return False
            if need == 'point':
                if el['type'] != 'point':
                    return False
                points.append(value)
            elif need == 'path' and el['type'] not in path_types:
                return False
            elif need == 'circle' and el['type'] != 'circle':
                return False
        elif need == 'positive':
            kind, v = value
            if kind == 'num' and not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                return False
            if kind == 'ref' and doc.elements.get(v, {}).get('type') != 'number':
                return False
        elif need == 'angle_degrees':
            kind, v = value
            if not (kind == 'num' and isinstance(v, (int, float)) and 0 < v < 180):
                return False
    receiver = binds.get(recipe['receiver'])
    return points.count(receiver) == 1


def matches(doc, statement) -> list:
    """``[(recipe, binds)]`` of every recipe and form that match, by recipe
    priority and then form order; one entry per (recipe, receiver)."""
    out = []
    seen = set()
    all_forms = forms(statement)
    for recipe in _load():
        if recipe['condition']['kind'] != statement.get('kind'):
            continue
        for form in all_forms:
            binds: dict = {}
            if not _unify(recipe['condition']['pattern'], form, binds):
                continue
            if not _requires_hold(doc, recipe, binds):
                continue
            key = (recipe['recipe'], binds[recipe['receiver']])
            if key in seen:
                continue
            seen.add(key)
            out.append((recipe, binds))
    return out
