"""Printing numbers (commands.md §6).

The shortest digits that read back as the same float (Python ``repr``, the
same digits as JavaScript ``String(x)``), in plain decimal notation when
``1e-6 ≤ |x| < 1e15`` and as ``d.ddde±N`` otherwise (``1.5e-7``,
``2e+21``); ``-0.0`` prints as ``0``.
"""
from __future__ import annotations

import math
from decimal import Decimal

__all__ = ['format_number']


def format_number(value) -> str:
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f'{value!r} is not a finite number')
    if x == 0:
        return '0'
    dec = Decimal(repr(x)).normalize()
    if 1e-6 <= abs(x) < 1e15:
        text = format(dec, 'f')
        return text
    sign, digits, exponent = dec.as_tuple()
    mantissa = ''.join(str(d) for d in digits)
    exp = exponent + len(mantissa) - 1
    head = mantissa[0] + ('.' + mantissa[1:] if len(mantissa) > 1 else '')
    return f"{'-' if sign else ''}{head}e{'+' if exp >= 0 else '-'}{abs(exp)}"
