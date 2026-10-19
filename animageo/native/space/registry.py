"""The operation registry of space: registry ``1.6`` (experimental).

Registry ``1.5`` is the frozen contract of the plane (1.0); space adds to it
by registry ``1.6``, only by addition. The operations of space live in
``animageo/native/ops/v1/space`` next to the plane groups:

- ``<group>.json`` — operation records (``point3``, ``segment3``,
  ``polygon3``, ``plane``, ``polyhedron``, ``section``), the same fields as
  a plane record (:mod:`animageo.native.registry`);
- ``_types.json`` — the types, families and paths of space, added to those
  of the plane;
- ``_reasons.json`` — the reasons of registry 1.6, added to the plane
  catalog;
- ``INDEX.json`` — generated: ``{registryVersion: "1.6", extends: "1.5",
  ops: {op: signatureHash}}`` (``python -m animageo.native registry index``
  refreshes it with the plane one).

The plane registry (:func:`animageo.native.registry`, ``REGISTRY_VERSION``)
does not see these files: a plane document, its fixtures and the version
the web stamps into a new plane work stay ``1.5``.

**Repeat by a formula** (new in 1.6): an output may carry ``count``
``{"per": slot | null, "times": k, "plus": c}`` — the output declares the
slots ``<slot>.1`` … ``<slot>.N`` with ``N = k·n + c``, ``n`` being the
repeat count of the slot ``per`` by the plane rule (the items of a list
input, the value of a param), or ``N = c`` when ``per`` is ``null``. A
prism over a base of ``n`` vertices has ``2n`` vertices, ``3n`` edges and
``n + 2`` faces. The signature hash covers ``count`` when it is set (so the
hashes of records without it are those of the plane rule).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ..canonical import sha256_of
from ..registry import Registry, _version_tuple, registry, signature

__all__ = ['SPACE_REGISTRY_VERSION', 'BASE_REGISTRY_VERSION', 'SpaceRegistry', 'space_registry',
           'space_signature', 'space_signature_hash', 'build_space_index', 'space_registry_problems',
           'write_space_index', 'PLANE_OPS_IN_SPACE']

SPACE_REGISTRY_VERSION = '1.6'
BASE_REGISTRY_VERSION = '1.5'
_INDEX_FILE = 'INDEX.json'
_REPEAT_SLOT = re.compile(r'^(?P<base>[A-Za-z_][A-Za-z0-9_]*)\.(?P<index>[1-9][0-9]*)$')
# Plane operations a space document may hold: none yet (§2.3 of the spec —
# a plane construction inside a face is made of space operations in the alpha).
PLANE_OPS_IN_SPACE = frozenset()


def _ops_dir():
    return resources.files('animageo.native').joinpath('ops', 'v1', 'space')


def _source_ops_dir() -> Path:
    return Path(__file__).resolve().parents[1] / 'ops' / 'v1' / 'space'


def _read_json(entry):
    return json.loads(entry.read_text(encoding='utf-8'))


def space_signature(record: dict) -> dict:
    """:func:`animageo.native.registry.signature` plus ``count`` of the
    outputs that have one."""
    sig = signature(record)
    for out, item in zip(sig['outputs'], record.get('outputs', [])):
        if item.get('count') is not None:
            out['count'] = item['count']
    return sig


def space_signature_hash(record: dict) -> str:
    return sha256_of(space_signature(record))


class SpaceRegistry(Registry):
    """The registry of a space document: the operations of 1.6 and the
    catalogs of the plane with the additions of 1.6."""

    def output_count(self, record: dict, out: dict, args: dict, graph=None) -> int:
        """The number of slots of the ``count`` output ``out`` for ``args``."""
        count = out['count']
        per = count.get('per')
        if per is None:
            return int(count.get('plus', 0))
        n = self._repeat_count(record, per, args, graph)
        return int(count.get('times', 1)) * n + int(count.get('plus', 0)) if n > 0 else 0

    def output_type(self, record: dict, slot: str, args: dict | None = None, graph=None):
        for out in record.get('outputs', []):
            if out.get('count') is None and out.get('repeat') is None:
                if out['slot'] == slot:
                    return out['type']
                continue
            match = _REPEAT_SLOT.match(slot)
            if match is None or match.group('base') != out['slot']:
                continue
            if args is None:
                return out['type']
            index = int(match.group('index'))
            if out.get('count') is not None:
                limit = self.output_count(record, out, args, graph)
            else:
                limit = self._repeat_count(record, out['repeat'], args, graph)
            return out['type'] if index <= limit else None
        return None

    def output_slots(self, record: dict, args: dict, graph=None, _seen=frozenset()) -> list:
        slots = []
        for out in record.get('outputs', []):
            if out.get('count') is not None:
                n = self.output_count(record, out, args, graph)
            elif out.get('repeat') is not None:
                n = self._repeat_count(record, out['repeat'], args, graph, _seen)
            else:
                slots.append(out['slot'])
                continue
            slots.extend(f"{out['slot']}.{i}" for i in range(1, n + 1))
        return slots


def _group_entries(directory):
    entries = []
    for entry in directory.iterdir():
        name = entry.name
        if not name.endswith('.json') or name.startswith('_') or name == _INDEX_FILE:
            continue
        entries.append(entry)
    return sorted(entries, key=lambda e: e.name)


def _load(directory) -> SpaceRegistry:
    plane = registry()
    ops: dict = {}
    groups: dict = {}
    for entry in _group_entries(directory):
        group = entry.name[:-len('.json')]
        records = _read_json(entry)
        groups[group] = [r['op'] for r in records]
        for record in records:
            if record['op'] in ops or record['op'] in plane.ops:
                raise ValueError(f"operation {record['op']!r} is declared twice")
            ops[record['op']] = record
    types_add = _read_json(directory.joinpath('_types.json'))
    reasons_add = _read_json(directory.joinpath('_reasons.json'))['reasons']
    index_entry = directory.joinpath(_INDEX_FILE)
    index = _read_json(index_entry) if index_entry.is_file() else {}
    families = dict(plane.families)
    families.update(types_add.get('families', {}))
    paths = dict(plane.paths)
    paths.update(types_add.get('paths', {}))
    reasons = dict(plane.reasons)
    reasons.update(reasons_add)
    return SpaceRegistry(
        version=SPACE_REGISTRY_VERSION,
        ops=ops,
        groups=groups,
        types={**plane.types, **types_add['types']},
        families=families,
        policies=plane.policies,
        reasons=reasons,
        numeric=plane.numeric,
        index=index,
        paths=paths,
        number_units=plane.number_units,
        mark_kinds={},
    )


@lru_cache(maxsize=1)
def space_registry() -> SpaceRegistry:
    """The registry 1.6 of space shipped with this library (cached)."""
    return _load(_ops_dir())


def build_space_index(reg: SpaceRegistry | None = None) -> dict:
    reg = reg or space_registry()
    return {
        'registryVersion': reg.version,
        'extends': BASE_REGISTRY_VERSION,
        'ops': {op: space_signature_hash(reg.ops[op]) for op in sorted(reg.ops)},
    }


def space_registry_problems(reg: SpaceRegistry | None = None) -> list:
    """Inconsistencies of the files of registry 1.6, as strings."""
    reg = reg or space_registry()
    problems = []
    known = set(reg.types) | set(reg.families)
    ours = _version_tuple(reg.version)
    for family, members in reg.families.items():
        for member in members:
            if member not in reg.types:
                problems.append(f'family {family!r}: unknown type {member!r}')
    for op, record in reg.ops.items():
        if record.get('since') != SPACE_REGISTRY_VERSION:
            problems.append(f"{op}: since {record.get('since')!r}, an operation of space is new in "
                            f'{SPACE_REGISTRY_VERSION}')
        if _version_tuple(record.get('since')) is None or _version_tuple(record.get('since')) > ours:
            problems.append(f"{op}: since {record.get('since')!r} is not a registry version up to {reg.version}")
        if record.get('signatureHash') != space_signature_hash(record):
            problems.append(f"{op}: signatureHash is {record.get('signatureHash')!r}, "
                            f'computed {space_signature_hash(record)}')
        for reason in record.get('undefined', []):
            if reason not in reg.reasons:
                problems.append(f'{op}: unknown reason {reason!r}')
        for item in record.get('inputs', []) + record.get('outputs', []):
            if item['type'] not in known:
                problems.append(f"{op}: unknown type {item['type']!r} of slot {item['slot']!r}")
        inputs = {i['slot']: i for i in record.get('inputs', [])}
        params = {p['slot'] for p in record.get('params', [])}
        for item in record.get('outputs', []):
            repeat, count = item.get('repeat'), item.get('count')
            if repeat is not None and count is not None:
                problems.append(f"{op}: output {item['slot']!r} has both repeat and count")
            per = count.get('per') if isinstance(count, dict) else repeat
            if per is not None and per not in params and per not in inputs:
                problems.append(f"{op}: output {item['slot']!r} repeats by unknown slot {per!r}")
            if count is not None and not (isinstance(count.get('times', 1), int)
                                          and isinstance(count.get('plus', 0), int)):
                problems.append(f"{op}: output {item['slot']!r}: count times and plus are integers")
        free = record.get('free')
        if free is not None and free.get('kind') not in ('point3', 'pathParameter', 'surfaceParameter'):
            problems.append(f"{op}: unknown free kind {free.get('kind')!r}")
    if reg.index != build_space_index(reg):
        problems.append('ops/v1/space/INDEX.json is out of date; run: python -m animageo.native registry index')
    return problems


def _dump_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def write_space_index(directory: Path | None = None, *, check: bool = False) -> list:
    """Refresh ``signatureHash`` and ``INDEX.json`` of the space registry;
    the names of the files that changed (would change with ``check``)."""
    directory = Path(directory) if directory is not None else _source_ops_dir()
    changed = []
    for entry in _group_entries(directory):
        path = Path(str(entry))
        old_text = path.read_text(encoding='utf-8')
        records = json.loads(old_text)
        for record in records:
            record['signatureHash'] = space_signature_hash(record)
        new_text = _dump_json(records)
        if new_text != old_text:
            changed.append('space/' + path.name)
            if not check:
                path.write_text(new_text, encoding='utf-8')
    reg = _load(directory)
    index_path = directory / _INDEX_FILE
    new_index = _dump_json(build_space_index(reg))
    old_index = index_path.read_text(encoding='utf-8') if index_path.is_file() else None
    if new_index != old_index:
        changed.append('space/' + _INDEX_FILE)
        if not check:
            index_path.write_text(new_index, encoding='utf-8')
    if not check and changed:
        space_registry.cache_clear()
    return changed
