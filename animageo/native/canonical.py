"""Canonical JSON and content hashes (contract shared with the browser kernel).

The canonical form is what ``JSON.stringify`` prints for the same value after
the object keys are sorted:

- object keys ascend by UTF-16 code units (JavaScript string order);
- separators are ``,`` and ``:`` with no whitespace;
- strings escape only ``"``, ``\\``, the control characters below U+0020
  (``\\b \\f \\n \\r \\t`` short forms, ``\\u00XX`` otherwise) and lone
  surrogates (``\\udXXX``); everything else, Cyrillic included, is written
  as is;
- numbers follow ECMAScript ``Number.prototype.toString``: integral values
  have no decimal point, ``-0`` is ``0``, digits are the shortest that round
  trip, and the exponent form (``1e-7``, ``1.5e+21``) is used when the
  decimal exponent ``n`` is outside ``-6 < n <= 21``;
- ``NaN`` and the infinities are refused with ``ValueError``.

``content_hash`` is ``"sha256:" + hex(sha256(utf8(canonical_json(value))))``.
The shared test table lives in ``parity/v1/canonical.json``.
"""
from __future__ import annotations

import hashlib
import math
import sys

__all__ = [
    'canonical_json',
    'canonical_bytes',
    'format_number',
    'sha256_of',
]

if sys.float_repr_style != 'short':  # pragma: no cover - every CPython build we support
    raise ImportError('animageo.native needs shortest round-trip float repr')


def _shortest_digits(x: float) -> tuple[str, int]:
    """Digits ``s`` and exponent ``n`` with ``x == 0.s * 10**n`` (x > 0).

    ``repr`` yields the shortest digit string that round-trips, which is the
    ``s`` of the ECMAScript algorithm.
    """
    text = repr(x)
    if 'e' in text:
        mantissa, exp_text = text.split('e')
        exp = int(exp_text)
    else:
        mantissa, exp = text, 0
    if '.' in mantissa:
        int_part, frac_part = mantissa.split('.')
    else:
        int_part, frac_part = mantissa, ''
    digits = int_part + frac_part
    n = len(int_part) + exp
    stripped = digits.lstrip('0')
    n -= len(digits) - len(stripped)
    digits = stripped.rstrip('0')
    return digits, n


def format_number(value) -> str:
    """Format an int or float as ECMAScript ``Number.prototype.toString``.

    A Python ``int`` is first converted to the nearest double, as
    ``JSON.parse`` would read it.
    """
    if isinstance(value, bool):
        raise TypeError('booleans are not numbers in canonical JSON')
    if isinstance(value, int):
        try:
            x = float(value)
        except OverflowError as exc:
            raise ValueError(f'integer {value} is out of the double range') from exc
    elif isinstance(value, float):
        x = value
    else:
        raise TypeError(f'not a number: {type(value).__name__}')
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f'{x!r} is not allowed in canonical JSON')
    if x == 0.0:
        return '0'
    if x < 0:
        return '-' + format_number(-x)
    digits, n = _shortest_digits(x)
    k = len(digits)
    if k <= n <= 21:
        return digits + '0' * (n - k)
    if 0 < n <= 21:
        return digits[:n] + '.' + digits[n:]
    if -6 < n <= 0:
        return '0.' + '0' * (-n) + digits
    e = n - 1
    exp_text = ('+' if e >= 0 else '-') + str(abs(e))
    if k == 1:
        return digits + 'e' + exp_text
    return digits[0] + '.' + digits[1:] + 'e' + exp_text


_SHORT_ESCAPES = {
    '"': '\\"',
    '\\': '\\\\',
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
}


def _format_string(text: str) -> str:
    out = ['"']
    for ch in text:
        esc = _SHORT_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
            continue
        code = ord(ch)
        if code < 0x20 or 0xD800 <= code <= 0xDFFF:
            out.append('\\u%04x' % code)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def _utf16_key(text: str) -> bytes:
    return text.encode('utf-16-be', 'surrogatepass')


def _write(value, out: list) -> None:
    if value is None:
        out.append('null')
    elif value is True:
        out.append('true')
    elif value is False:
        out.append('false')
    elif isinstance(value, str):
        out.append(_format_string(value))
    elif isinstance(value, (int, float)):
        out.append(format_number(value))
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f'object keys must be strings, got {type(key).__name__}')
        out.append('{')
        first = True
        for key in sorted(value, key=_utf16_key):
            if not first:
                out.append(',')
            first = False
            out.append(_format_string(key))
            out.append(':')
            _write(value[key], out)
        out.append('}')
    elif isinstance(value, (list, tuple)):
        out.append('[')
        for i, item in enumerate(value):
            if i:
                out.append(',')
            _write(item, out)
        out.append(']')
    else:
        raise TypeError(f'not JSON-serialisable: {type(value).__name__}')


def canonical_json(value) -> str:
    """Return the canonical JSON text of ``value`` (dict/list/str/number/bool/None)."""
    out: list = []
    _write(value, out)
    return ''.join(out)


def canonical_bytes(value) -> bytes:
    """UTF-8 bytes of :func:`canonical_json`."""
    return canonical_json(value).encode('utf-8')


def sha256_of(value) -> str:
    """``"sha256:" + hex(sha256(canonical_bytes(value)))``."""
    return 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest()
