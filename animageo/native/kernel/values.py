"""Value encoding of ``animageo-evaluated/v1`` (``ops/v1/_types.json``).

| type      | value                                          |
|-----------|------------------------------------------------|
| point     | ``{x, y}``                                     |
| segment   | ``{a: [x, y], b: [x, y], length}``             |
| ray       | ``{origin: [x, y], dir: [x, y]}`` (``dir`` unit) |
| line      | ``{p: [x, y], dir: [x, y]}`` (``dir`` unit)    |
| circle    | ``{c: [x, y], r}``                             |
| polygon   | ``{vertices: [[x, y], ...], area}``            |
| vector    | ``{a: [x, y], b: [x, y], length}``             |
| number    | ``{value, unit}`` (unit from ``numberUnits``)  |
"""
from __future__ import annotations

import math
from typing import NamedTuple

__all__ = [
    'Undefined',
    'Detailed',
    'Input',
    'STATE_RANK',
    'is_finite_value',
    'defined_record',
    'state_record',
    'compare_values',
]

# Worst state wins when a result inherits from its inputs.
STATE_RANK = {'undefined': 1, 'unsupported': 2, 'error': 3}


class Undefined:
    """An op result slot without a value: ``reason`` from ``_reasons.json``."""

    __slots__ = ('reason', 'detail')

    def __init__(self, reason: str, detail: dict | None = None):
        self.reason = reason
        self.detail = detail

    def __eq__(self, other):
        return isinstance(other, Undefined) and (self.reason, self.detail) == (other.reason, other.detail)

    def __repr__(self):
        return f'Undefined({self.reason!r}, {self.detail!r})'


class Detailed(NamedTuple):
    """A defined op result slot with a ``detail`` (``{"multiplicity": 2}`` for
    a double root); evaluation records it as ``detail`` of a defined element."""

    value: dict
    detail: dict


class Input(NamedTuple):
    """A resolved reference argument: element type and value; ``frame`` is the
    path frame of a ``path`` slot (``kernel/paths.py``), else ``None``."""

    type: str
    value: dict
    frame: object = None


def is_finite_value(value) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(is_finite_value(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(is_finite_value(v) for v in value)
    return True


def defined_record(type_: str, value: dict, detail: dict | None = None) -> dict:
    out = {'state': 'defined', 'type': type_, 'value': value}
    if detail is not None:
        out['detail'] = detail
    return out


def state_record(state: str, type_: str, reason: str, *, cause: str | None = None,
                 detail: dict | None = None) -> dict:
    out = {'state': state, 'type': type_, 'reason': reason}
    if cause is not None:
        out['cause'] = cause
    if detail is not None:
        out['detail'] = detail
    return out


def _compare(expected, actual, tol: float, path: str, out: list) -> None:
    if isinstance(expected, bool) or isinstance(actual, bool) or expected is None or actual is None:
        if expected != actual:
            out.append(f'{path}: expected {expected!r}, got {actual!r}')
        return
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        diff = abs(float(expected) - float(actual))
        if not diff <= tol:
            out.append(f'{path}: expected {expected!r}, got {actual!r} (|diff| {diff:.3g} > tol {tol:.3g})')
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append(f'{path}: expected {len(expected)} items, got {len(actual)}')
            return
        for i, (e, a) in enumerate(zip(expected, actual)):
            _compare(e, a, tol, f'{path}[{i}]', out)
        return
    if expected != actual:
        out.append(f'{path}: expected {expected!r}, got {actual!r}')


def compare_values(type_info: dict, expected: dict, actual: dict, tolerance, path: str = 'value', *,
                   units: dict | None = None) -> list:
    """Differences of two encoded values; ``type_info`` is the ``_types.json``
    entry, ``tolerance(kind)`` gives the parity tolerance of a field kind.

    A field of kind ``by_unit`` takes the kind ``units[expected["unit"]]``
    (``_types.json → numberUnits``; the registry's when ``units`` is
    ``None``); a field without a kind, or a ``by_unit`` field of an unknown
    unit, compares exactly.
    """
    out: list = []
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        if expected != actual:
            out.append(f'{path}: expected {expected!r}, got {actual!r}')
        return out
    if set(expected) != set(actual):
        out.append(f'{path}: expected fields {sorted(expected)}, got {sorted(actual)}')
        return out
    kinds = type_info.get('value', {})
    for key in sorted(expected):
        kind = kinds.get(key)
        if kind == 'by_unit':
            if units is None:
                from ..registry import registry
                units = registry().number_units
            unit = expected.get('unit')
            kind = units.get(unit) if isinstance(unit, str) else None
        if kind is None:
            if expected[key] != actual[key]:
                out.append(f'{path}.{key}: expected {expected[key]!r}, got {actual[key]!r}')
            continue
        _compare(expected[key], actual[key], tolerance(kind), f'{path}.{key}', out)
    return out
