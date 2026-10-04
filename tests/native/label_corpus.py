"""A seeded corpus of label texts (a test helper, not a test module).

The labels of drawings as ``resolve_label_text`` writes them, before
``correctedLabel``: point names with indices and primes, Greek and Cyrillic
names, values with units and degrees, relations of two segments, captions
in text mode with inline math.
"""
import random

LATIN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LATIN_LOWER = 'abcdefghijklmnopqrstuvwxyz'
CYRILLIC = 'АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ'
CYRILLIC_LOWER = 'абвгдежзиклмнопрстуфхцчшщэюя'
GREEK = (r'\alpha', r'\beta', r'\gamma', r'\delta', r'\varepsilon', r'\varphi', r'\omega',
         r'\Omega', r'\Delta', r'\pi', r'\lambda', r'\mu', r'\theta', r'\Gamma', r'\sigma')
GREEK_UNICODE = 'αβγδεφωΩΔπλμ'
WORDS = ('Центр', 'центр', 'точка', 'середина', 'биссектриса', 'высота', 'медиана', 'радиус',
         'Center', 'point', 'midpoint', 'side', 'base', 'Ось', 'Угол', 'Шаг')
RELATIONS = (r'\parallel', r'\perp', '=', r'\neq', '<', '>', '+', '-', r'\cdot')


def _index(rng):
    kind = rng.random()
    if kind < 0.45:
        return str(rng.randint(0, 9))
    if kind < 0.6:
        return '{' + str(rng.randint(10, 99)) + '}'
    if kind < 0.8:
        return rng.choice(LATIN_LOWER)
    return '{' + rng.choice(LATIN) + rng.choice(LATIN) + '}'


def _name(rng):
    pick = rng.random()
    if pick < 0.55:
        base = rng.choice(LATIN)
    elif pick < 0.7:
        base = rng.choice(LATIN_LOWER)
    elif pick < 0.85:
        base = rng.choice(GREEK)
    else:
        base = rng.choice(CYRILLIC)
    if rng.random() < 0.4:
        base += '_' + _index(rng)
    if rng.random() < 0.15:
        base += "'" * rng.randint(1, 2)
    return base


def _number(rng):
    value = rng.uniform(-50, 200) if rng.random() < 0.2 else rng.uniform(0, 200)
    places = rng.choice((0, 1, 1, 2))
    return f'{value:.{places}f}'


def _segment(rng):
    return rng.choice(LATIN) + rng.choice(LATIN)


def label(rng) -> str:
    """One label text."""
    kind = rng.random()
    if kind < 0.40:
        return f'${_name(rng)}$'
    if kind < 0.48:
        return '$' + rng.choice(GREEK_UNICODE) + ('_' + str(rng.randint(1, 9)) if rng.random() < 0.3 else '') + '$'
    if kind < 0.56:
        return f'${rng.choice(CYRILLIC)}' + (f'_{rng.randint(1, 9)}' if rng.random() < 0.4 else '') + '$'
    if kind < 0.70:
        return f'${_name(rng)} = {_number(rng)}$'
    if kind < 0.78:
        return f'${rng.choice(GREEK)} = {rng.randint(1, 179)}' + r'^{\circ}$'
    if kind < 0.84:
        return f'${_segment(rng)} {rng.choice(RELATIONS)} {_segment(rng)}$'
    if kind < 0.88:
        return '$' + rng.choice((r'\triangle ', r'\angle ')) + ''.join(rng.sample(LATIN, 3)) + '$'
    if kind < 0.92:
        return f'${_name(rng)}^{rng.randint(2, 3)}$'
    if kind < 0.97:
        words = ' '.join(rng.choice(WORDS) for _ in range(rng.randint(1, 2)))
        return words + (f' ${_name(rng)}$' if rng.random() < 0.6 else '')
    return ''.join(rng.choice(CYRILLIC_LOWER) for _ in range(rng.randint(3, 8)))


def corpus(n=2000, seed=20261003) -> list:
    """``n`` label texts, the same for a given ``seed``."""
    rng = random.Random(seed)
    return [label(rng) for _ in range(n)]
