"""Explicit parameters of Point(locus, t), independently of classic dispatch."""
from __future__ import annotations

import math


def read_locus_points(infos, norm, ctx):
    kinds = {info['label']: info['type'] for info in infos}
    for info in infos:
        args = info.get('inputs', [])
        if info.get('command') != 'Point' or len(args) != 2 or kinds.get(args[0]) != 'locus':
            continue
        name = norm[info['label']]
        forced = ctx.forced.get(name)
        if forced and forced[0] not in ('parse_error', 'unsupported_signature', 'no_registry_op'):
            continue
        raw = args[1].strip()
        if kinds.get(raw) == 'numeric':
            parameter = norm[raw]
        else:
            try:
                parameter = float(raw)
            except ValueError:
                continue
            if not math.isfinite(parameter):
                continue
        ctx.forced.pop(name, None)
        ctx.locus_points[name] = norm[args[0]], parameter
