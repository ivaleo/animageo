"""The table ``dsl_map.json``: classic command key → registry op (plan L5 §3.2).

A row is keyed by the classic dispatch key (``strFullCommand``: ``midpoint_pp``,
``intersect_lci``, ``polygon``), the same for a ``.ggb`` and a DSL scene,
because ``ggb_parser`` builds the same ``Command`` objects as the DSL. A row
is one of:

- an op row ``{factory, ggb, op, args, outputs, index?, input?}``: ``args``
  names the op slot of every classic input in order (``null`` — the input is
  not an argument, e.g. the output number; ``{"ends": [a, b]}`` — a segment
  input whose two defining points fill the slots ``a`` and ``b``),
  ``{"variadic": slot}`` puts every input into one list slot; ``outputs`` is
  a list of slots by classic output number, ``{"byValue": [slots]}`` (the slot
  of each classic output is the one whose value matches it, plan §3.4) or
  ``{"pattern": "polygon_sides" | "regular"}``; ``index`` — the classic input
  holding the output number (``base`` 1); ``input: "pathParameter"`` — the
  op is a free point on a path whose parameter is projected from the value;
- a formula row ``{factory, ggb, op: "number.expression", formula, outputs}``
  (1.10.0a2, ``mapVersion`` 2): ``formula`` is an AST v1 tree
  (``docs/native/expr.md``) whose ``{"input": i}`` nodes stand for the
  classic inputs — a number of the document becomes a ``refs`` item, a
  constant a ``num``;
- a free row ``{factory, ggb, free, value}`` (a DSL ``Point(x, y)``);
- an unmapped row ``{factory, ggb, unmapped: reason, note?}``.

``opsWithoutClassic`` lists the registry ops no classic key builds (with the
reason) and ``seedDropped`` the commands of the web seed not taken (with the
reason). The table is data of the translator: it has its own ``mapVersion``
and does not move the dev label of the library. ``mapVersion`` 3
(1.11.0rc1): the row ``cpx_to_a`` is gone with the classic command (a helper
of ``lib_elements`` that was no command, kernel spec §15).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MAP_FORMAT = 'animageo-dsl-map/v1'
MAP_PATH = Path(__file__).with_name('dsl_map.json')

UNMAPPED_REASONS = ('no_registry_op', 'formula_unsupported', 'unsupported_signature', 'dynamic_topology',
                    'random_point', 'style_only')
OUTPUT_PATTERNS = ('polygon_sides', 'regular')

__all__ = ['MAP_FORMAT', 'MAP_PATH', 'DslMap', 'dsl_map', 'map_problems']


class DslMap:
    """The loaded table: ``commands`` by classic key, ``by_ggb`` — keys by GGB name."""

    def __init__(self, data: dict):
        self.data = data
        self.version = int(data.get('mapVersion', 0))
        self.registry = data.get('registry')
        self.commands: dict = data.get('commands', {})
        self.ops_without_classic: dict = data.get('opsWithoutClassic', {})
        self.seed_dropped: dict = data.get('seedDropped', {})
        by_ggb: dict = {}
        for key, row in self.commands.items():
            for name in row.get('ggb', ()):
                by_ggb.setdefault(name, []).append(key)
        self.by_ggb = by_ggb

    def lookup(self, key: str) -> dict | None:
        """The row of classic key ``key`` (``None`` — not in the table)."""
        return self.commands.get(key)

    def ggb_names(self) -> set:
        return set(self.by_ggb)


@lru_cache(maxsize=1)
def dsl_map() -> DslMap:
    with open(MAP_PATH, encoding='utf-8') as fh:
        return DslMap(json.load(fh))


def _op_slots(op: dict) -> tuple[set, set]:
    ins = {s['slot'] for s in op.get('inputs', ())} | {s['slot'] for s in op.get('params', ())}
    outs = {s['slot'] for s in op.get('outputs', ())}
    return ins, outs


def _formula_problems(key: str, row: dict) -> list:
    """Problems of a formula row: the op, the outputs, the inputs it names and
    the tree with every input as a number."""
    from ..expr.validate import problems
    out = []
    if row.get('op') != 'number.expression':
        out.append('a formula row builds number.expression')
    if row.get('outputs') != ['number'] or 'args' in row:
        out.append('a formula row has outputs ["number"] and no args')
    arity = len(key.rpartition('_')[2])
    bad = []

    def fill(tpl):
        if not isinstance(tpl, dict):
            bad.append(repr(tpl))
            return {'num': 1.0}
        if 'input' in tpl:
            i = tpl['input']
            if not (isinstance(i, int) and not isinstance(i, bool) and 0 <= i < arity) or len(tpl) != 1:
                bad.append(f'input {i!r} of {arity}')
            return {'num': 1.0}
        if isinstance(tpl.get('args'), list):
            return {**tpl, 'args': [fill(a) for a in tpl['args']]}
        return tpl

    ast = fill(row.get('formula'))
    out += [f'formula: {b}' for b in bad]
    out += [f'formula {pointer or "/"}: {message}' for pointer, message in problems(ast, 0)]
    return out


def _slot_ok(slot: str, outs: set, repeated: set) -> bool:
    if slot in outs:
        return True
    base, _, num = slot.rpartition('.')
    return bool(base) and num.isdigit() and base in repeated


def map_problems(data: dict | None = None, *, classic_keys=None, seed: dict | None = None) -> list:
    """Problems of the table (plan §3.2, both directions): every classic key
    has a row; every op exists and its slots are the op's slots; every op of
    the registry is used or listed in ``opsWithoutClassic``; every command of
    the web seed ``seed`` (``{"commands": [names]}``) is in a row's ``ggb`` or
    in ``seedDropped``. ``classic_keys`` defaults to ``COMMAND_REGISTRY``
    (loaded lazily: it needs the classic code)."""
    from ..registry import REGISTRY_VERSION, registry
    if data is None:
        data = dsl_map().data
    out = []
    if data.get('format') != MAP_FORMAT:
        out.append(f'format must be {MAP_FORMAT}')
    if data.get('registry') != REGISTRY_VERSION:
        out.append(f'registry {data.get("registry")} != {REGISTRY_VERSION}')
    commands = data.get('commands', {})
    if classic_keys is None:
        from ...geo.lib_commands import COMMAND_REGISTRY
        classic_keys = COMMAND_REGISTRY.keys()
    classic_keys = set(classic_keys)
    for key in sorted(classic_keys - set(commands)):
        out.append(f'{key}: classic key without a row')
    for key in sorted(set(commands) - classic_keys):
        out.append(f'{key}: row without a classic key')
    reg = registry()
    used = set()
    for key, row in sorted(commands.items()):
        kinds = [k for k in ('op', 'free', 'unmapped') if k in row]
        if len(kinds) != 1:
            out.append(f'{key}: exactly one of op, free, unmapped')
            continue
        if not row.get('ggb'):
            out.append(f'{key}: no ggb names')
        if 'unmapped' in row:
            if row['unmapped'] not in UNMAPPED_REASONS:
                out.append(f'{key}: unknown reason {row["unmapped"]}')
            continue
        if 'free' in row:
            if row['free'] not in ('point', 'number', 'angle'):
                out.append(f'{key}: unknown free kind {row["free"]}')
            continue
        op = reg.ops.get(row['op'])
        if op is None:
            out.append(f'{key}: op {row["op"]} not in the registry')
            continue
        used.add(row['op'])
        if 'formula' in row:
            out.extend(f'{key}: {p}' for p in _formula_problems(key, row))
            continue
        ins, outs = _op_slots(op)
        repeated = {s['slot'] for s in op.get('outputs', ()) if s.get('repeat')}
        args = row.get('args')
        if isinstance(args, dict):
            if args.get('variadic') not in ins:
                out.append(f'{key}: variadic slot {args.get("variadic")} not an input of {row["op"]}')
        elif isinstance(args, list):
            for slot in args:
                names = slot.get('ends', []) if isinstance(slot, dict) else [slot] if slot else []
                for name in names:
                    if name not in ins:
                        out.append(f'{key}: argument slot {name} not an input of {row["op"]}')
        else:
            out.append(f'{key}: args must be a list or {{"variadic": slot}}')
        outputs = row.get('outputs')
        if isinstance(outputs, list):
            slots = outputs
        elif isinstance(outputs, dict) and 'byValue' in outputs:
            slots = outputs['byValue']
        elif isinstance(outputs, dict) and outputs.get('pattern') in OUTPUT_PATTERNS:
            slots = []
        else:
            out.append(f'{key}: bad outputs')
            slots = []
        for slot in slots:
            if not _slot_ok(slot, outs, repeated):
                out.append(f'{key}: output slot {slot} not an output of {row["op"]}')
        index = row.get('index')
        if index is not None and not (isinstance(args, list) and 0 <= index.get('input', -1) < len(args)
                                      and args[index['input']] is None):
            out.append(f'{key}: index input must be a null argument')
    without = data.get('opsWithoutClassic', {})
    for op in sorted(set(reg.ops) - used - set(without)):
        out.append(f'{op}: registry op neither used nor in opsWithoutClassic')
    for op in sorted(set(without) & used):
        out.append(f'{op}: in opsWithoutClassic but used')
    if seed is not None:
        names = {n for row in commands.values() for n in row.get('ggb', ())}
        dropped = data.get('seedDropped', {})
        for name in sorted(seed.get('commands', ())):
            if name not in names and name not in dropped:
                out.append(f'seed {name}: neither in a row nor in seedDropped')
    return out
