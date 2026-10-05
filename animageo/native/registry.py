"""Semantic operation registry ``ops/v1`` (contract shared with the web).

Files in ``animageo/native/ops/v1``:

- ``<group>.json`` — arrays of operation records (``point``, ``line``, …);
- ``_types.json``, ``_policies.json``, ``_reasons.json``, ``_numeric.json`` —
  service catalogs;
- ``INDEX.json`` — generated: ``{registryVersion, ops: {op: signatureHash}}``
  (``python -m animageo.native registry index``).

The signature hash covers what an operation *means* to a document — slots,
types, outputs, the free-input kind, the branch policy, orientation and the
path parameter — and nothing descriptive (phrases, checks, status, math)::

    signatureHash = "sha256:" + sha256(canonical({
        "op": op,
        "inputs":  [{"slot", "type", "list": bool = false, "min": int | null}],
        "params":  [{"slot", "type", "unit": str | null}],   # optional/default are outside
        "outputs": [{"slot", "type", "repeat": str | null}],
        "free": {...} | null,
        "branch": branch.policy | null,
        "orientation": str | null,
        "pathParam": ... | null,
    }))
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from pathlib import Path

from .canonical import sha256_of

__all__ = [
    'REGISTRY_VERSION',
    'REPEAT_MAX',
    'FREE_INPUT_DEFAULTS',
    'free_slot',
    'repeat_count',
    'Registry',
    'registry',
    'signature',
    'signature_hash',
    'build_index',
    'registry_problems',
    'write_index',
]

REGISTRY_VERSION = '1.4'
REPEAT_MAX = 100
# A free input of these kinds is optional: absent from ``inputs``, it takes this value.
FREE_INPUT_DEFAULTS = {'angle': {'kind': 'angle', 'value': 0.0}}

_SERVICE_FILES = ('_types', '_policies', '_reasons', '_numeric')
_INDEX_FILE = 'INDEX.json'
_REPEAT_SLOT = re.compile(r'^(?P<base>[A-Za-z_][A-Za-z0-9_]*)\.(?P<index>[1-9][0-9]*)$')


def free_slot(record: dict):
    """The output slot of a free operation whose element holds the input
    (its first output), or ``None`` for an operation that is not free."""
    if record.get('free') is None or not record.get('outputs'):
        return None
    return record['outputs'][0]['slot']


def repeat_count(value) -> int:
    """Slots of an output repeated by a param: ``round(value)`` when ``value``
    is a whole number in ``[1, REPEAT_MAX]``, else ``0``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    if value != value or value in (float('inf'), float('-inf')):
        return 0
    k = round(value)
    if abs(value - k) > 1e-9 or k < 1 or k > REPEAT_MAX:
        return 0
    return int(k)


def _ops_dir():
    return resources.files('animageo.native').joinpath('ops', 'v1')


def _source_ops_dir() -> Path:
    """The ``ops/v1`` directory on disk (for ``registry index``)."""
    return Path(__file__).resolve().parent / 'ops' / 'v1'


def _read_json(entry):
    return json.loads(entry.read_text(encoding='utf-8'))


def signature(record: dict) -> dict:
    """The part of a registry record that the signature hash covers."""
    branch = record.get('branch')
    return {
        'op': record['op'],
        'inputs': [
            {
                'slot': item['slot'],
                'type': item['type'],
                'list': bool(item.get('list', False)),
                'min': item.get('min'),
            }
            for item in record.get('inputs', [])
        ],
        'params': [
            {'slot': item['slot'], 'type': item['type'], 'unit': item.get('unit')}
            for item in record.get('params', [])
        ],
        'outputs': [
            {'slot': item['slot'], 'type': item['type'], 'repeat': item.get('repeat')}
            for item in record.get('outputs', [])
        ],
        'free': record.get('free'),
        'branch': branch.get('policy') if isinstance(branch, dict) else None,
        'orientation': record.get('orientation'),
        'pathParam': record.get('pathParam'),
    }


def signature_hash(record: dict) -> str:
    """``"sha256:<hex>"`` of the canonical JSON of :func:`signature`."""
    return sha256_of(signature(record))


@dataclass(frozen=True)
class Registry:
    """The loaded registry: records by op, service catalogs and the index."""

    version: str
    ops: dict
    groups: dict
    types: dict
    families: dict
    policies: dict
    reasons: dict
    numeric: dict
    index: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    number_units: dict = field(default_factory=dict)
    mark_kinds: dict = field(default_factory=dict)

    def get(self, op: str):
        return self.ops.get(op)

    def accepts(self, slot_type: str, element_type: str) -> bool:
        """True when an element of ``element_type`` fits a slot of ``slot_type``."""
        if element_type == slot_type:
            return True
        return element_type in self.families.get(slot_type, ())

    def output_type(self, record: dict, slot: str, args: dict | None = None):
        """Type of output ``slot`` of ``record``, or ``None`` if there is no such slot.

        A ``repeat`` output ``side`` over the list input ``vertices`` declares
        the slots ``side.1`` … ``side.N``, ``N`` being the number of items of
        ``args['vertices']`` (any positive index when ``args`` is not given);
        a ``repeat`` naming a param ``n`` declares :func:`repeat_count` of its
        value (the default when absent).
        """
        for out in record.get('outputs', []):
            repeat = out.get('repeat')
            if repeat is None:
                if out['slot'] == slot:
                    return out['type']
                continue
            match = _REPEAT_SLOT.match(slot)
            if match is None or match.group('base') != out['slot']:
                continue
            if args is None:
                return out['type']
            if int(match.group('index')) <= self._repeat_count(record, repeat, args):
                return out['type']
            return None
        return None

    @staticmethod
    def _repeat_count(record: dict, repeat: str, args: dict) -> int:
        for param in record.get('params', []):
            if param['slot'] == repeat:
                arg = args.get(repeat)
                if isinstance(arg, dict) and arg.get('kind') == 'number':
                    return repeat_count(arg.get('value'))
                return repeat_count(param.get('default')) if arg is None else 0
        arg = args.get(repeat)
        if isinstance(arg, dict) and arg.get('kind') == 'list' and isinstance(arg.get('items'), list):
            return len(arg['items'])
        return 0

    def output_slots(self, record: dict, args: dict) -> list:
        """All output slots of ``record`` for ``args``, in canonical order."""
        slots = []
        for out in record.get('outputs', []):
            repeat = out.get('repeat')
            if repeat is None:
                slots.append(out['slot'])
                continue
            count = self._repeat_count(record, repeat, args)
            slots.extend(f"{out['slot']}.{i}" for i in range(1, count + 1))
        return slots


def _group_entries(directory):
    entries = []
    for entry in directory.iterdir():
        name = entry.name
        if not name.endswith('.json') or name.startswith('_') or name == _INDEX_FILE:
            continue
        entries.append(entry)
    return sorted(entries, key=lambda e: e.name)


def _load(directory) -> Registry:
    ops: dict = {}
    groups: dict = {}
    for entry in _group_entries(directory):
        group = entry.name[:-len('.json')]
        records = _read_json(entry)
        groups[group] = [r['op'] for r in records]
        for record in records:
            if record['op'] in ops:
                raise ValueError(f"operation {record['op']!r} is declared twice")
            ops[record['op']] = record
    service = {name: _read_json(directory.joinpath(name + '.json')) for name in _SERVICE_FILES}
    index_entry = directory.joinpath(_INDEX_FILE)
    index = _read_json(index_entry) if index_entry.is_file() else {}
    return Registry(
        version=REGISTRY_VERSION,
        ops=ops,
        groups=groups,
        types=service['_types']['types'],
        families=service['_types'].get('families', {}),
        policies=service['_policies'].get('policies', {}),
        reasons=service['_reasons']['reasons'],
        numeric=service['_numeric'],
        index=index,
        paths=service['_types'].get('paths', {}),
        number_units=service['_types'].get('numberUnits', {}),
        mark_kinds=service['_types'].get('markKinds', {}),
    )


@lru_cache(maxsize=1)
def registry() -> Registry:
    """The registry shipped with this library (cached)."""
    return _load(_ops_dir())


def build_index(reg: Registry | None = None) -> dict:
    """The content of ``INDEX.json`` for ``reg``: ``{registryVersion, ops}``."""
    reg = reg or registry()
    return {
        'registryVersion': reg.version,
        'ops': {op: signature_hash(reg.ops[op]) for op in sorted(reg.ops)},
    }


def registry_problems(reg: Registry | None = None) -> list:
    """Inconsistencies of the registry files, as human-readable strings."""
    reg = reg or registry()
    problems = []
    known_types = set(reg.types) | set(reg.families)
    for family, members in reg.families.items():
        for member in members:
            if member not in reg.types:
                problems.append(f'family {family!r}: unknown type {member!r}')
    for type_ in reg.families.get('path', ()):
        if type_ not in reg.paths:
            problems.append(f'path type {type_!r} has no entry in _types.json paths')
    ours = _version_tuple(reg.version)
    for op, record in reg.ops.items():
        since = _version_tuple(record.get('since'))
        if since is None or since > ours:
            problems.append(f"{op}: since {record.get('since')!r} is not a registry version up to {reg.version}")
        stored = record.get('signatureHash')
        computed = signature_hash(record)
        if stored != computed:
            problems.append(f'{op}: signatureHash is {stored!r}, computed {computed}')
        for reason in record.get('undefined', []):
            if reason not in reg.reasons:
                problems.append(f'{op}: unknown reason {reason!r}')
        for item in record.get('inputs', []) + record.get('outputs', []):
            if item['type'] not in known_types:
                problems.append(f"{op}: unknown type {item['type']!r} of slot {item['slot']!r}")
        branch = record.get('branch')
        policy = branch.get('policy') if isinstance(branch, dict) else None
        if policy is not None and policy not in reg.policies:
            problems.append(f'{op}: unknown branch policy {policy!r}')
        problems.extend(_param_problems(op, record))
    for kind, op in reg.mark_kinds.items():
        record = reg.ops.get(op)
        if record is None or not any(out['type'] == 'mark' for out in record.get('outputs', [])):
            problems.append(f'mark kind {kind!r}: {op!r} is not an operation with a mark output')
    index = build_index(reg)
    if reg.index != index:
        problems.append('INDEX.json is out of date; run: python -m animageo.native registry index')
    return problems


def _param_problems(op: str, record: dict) -> list:
    """Params are numbers; an optional param may have a numeric default, a required one has none."""
    out = []
    for param in record.get('params', []):
        slot = param['slot']
        if param['type'] != 'number':
            out.append(f"{op}: param {slot!r} must have type 'number'")
        has_default = 'default' in param
        if has_default and (isinstance(param['default'], bool) or not isinstance(param['default'], (int, float))):
            out.append(f'{op}: param {slot!r} default must be a number')
        if not param.get('optional', False) and has_default:
            out.append(f'{op}: param {slot!r} is required and has a default')
    return out


def _version_tuple(text):
    try:
        major, minor = str(text).split('.')
        return int(major), int(minor)
    except ValueError:
        return None


def _dump_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def write_index(directory: Path | None = None, *, check: bool = False) -> list:
    """Refresh ``signatureHash`` fields and ``INDEX.json`` in ``directory``.

    Returns the names of the files that changed (with ``check=True``: that
    would change; nothing is written).
    """
    directory = Path(directory) if directory is not None else _source_ops_dir()
    reg = _load(directory)
    changed = []
    for entry in _group_entries(directory):
        path = Path(str(entry))
        old_text = path.read_text(encoding='utf-8')
        records = json.loads(old_text)
        for record in records:
            record['signatureHash'] = signature_hash(record)
        new_text = _dump_json(records)
        if new_text != old_text:
            changed.append(path.name)
            if not check:
                path.write_text(new_text, encoding='utf-8')
    index_path = directory / _INDEX_FILE
    new_index = _dump_json(build_index(reg))
    old_index = index_path.read_text(encoding='utf-8') if index_path.is_file() else None
    if new_index != old_index:
        changed.append(_INDEX_FILE)
        if not check:
            index_path.write_text(new_index, encoding='utf-8')
    if not check and changed:
        registry.cache_clear()
    return changed
