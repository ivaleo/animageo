"""``text.free`` (docs/native/ops/text.free.md): a text at a point with inserts."""
from __future__ import annotations

import math

from ...expr import format_value, split_template
from ..values import Undefined
from . import op


def insert_text(item, decimals: int) -> str:
    """The text of an insert: a number as :func:`format_value` (an angle in
    degrees with ``°``), a point as ``(x, y)``."""
    if item.type == 'point':
        return f"({format_value(item.value['x'], decimals)}, {format_value(item.value['y'], decimals)})"
    value = item.value['value']
    if item.value['unit'] == 'angle':
        return format_value(value * 180.0 / math.pi, decimals) + '°'
    return format_value(value, decimals)


@op('text.free')
def free(args, ctx):
    d = args['decimals']
    if d is None or not float(d).is_integer() or d < 0 or d > 10:
        return {'text': Undefined('invalid_parameter')}
    decimals = int(d)
    refs = args['refs']
    parts = []
    for kind, piece in split_template(args['text'].value):
        if kind == 'text':
            parts.append({'text': piece})
        else:
            parts.append({'ref': piece, 'text': insert_text(refs[piece], decimals)})
    a = args['anchor'].value
    return {'text': {'anchor': [a['x'], a['y']], 'text': ''.join(p['text'] for p in parts), 'parts': parts}}
