"""Registry 1.5 is the 1.0 contract (1.11.0rc1, L6 item 7).

``tests/native/registry_frozen_1_0.json`` holds, for registry ``1.5``, the
hash of every op record (the whole record, canonical JSON), its signature
hash, ``since`` and ``status``, and the hash of every key of the service
catalogs (``_types``, ``_policies``, ``_reasons``, ``_numeric``). Rules:

- while ``registryVersion`` is ``1.5`` nothing of it changes and nothing is
  added;
- an op is never removed (it may become ``status: deprecated`` with a new
  registry version); ``beta`` may become ``stable`` at any time (the status
  is descriptive, outside the record hash, as since registry 1.4);
- the signature of a 1.0 op never changes (a new op id instead): documents
  carry it;
- any other change of a 1.0 record needs a new registry version and the
  record's ``since`` set to it; a new op has ``since`` above ``1.5``;
- a catalog key is never removed; changing or adding one needs a new
  registry version.

The snapshot is rewritten only for a new frozen contract (2.0):
``python tests/native/test_registry_frozen_1_0.py --write``.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = REPO_ROOT / 'animageo' / 'native' / 'ops' / 'v1'
FROZEN_PATH = Path(__file__).with_name('registry_frozen_1_0.json')
FROZEN_VERSION = '1.5'
SERVICE = ('_types', '_policies', '_reasons', '_numeric')


def _version(text: str) -> tuple:
    return tuple(int(part) for part in str(text).split('.'))


def current() -> dict:
    """``{version, records: {op: record}, catalogs: {file: {key: value}}}`` from ``ops/v1``."""
    index = json.loads((OPS_DIR / 'INDEX.json').read_text(encoding='utf-8'))
    records = {}
    for path in sorted(OPS_DIR.glob('*.json')):
        if path.name == 'INDEX.json' or path.stem in SERVICE:
            continue
        for record in json.loads(path.read_text(encoding='utf-8')):
            records[record['op']] = record
    catalogs = {name: json.loads((OPS_DIR / f'{name}.json').read_text(encoding='utf-8')) for name in SERVICE}
    return {'version': index['registryVersion'], 'records': records, 'catalogs': catalogs}


def summary(state: dict) -> dict:
    from animageo.native.canonical import sha256_of
    from animageo.native.registry import signature_hash
    return {
        'registryVersion': state['version'],
        'ops': {
            op: {
                'since': record.get('since'),
                'status': record.get('status'),
                'signatureHash': signature_hash(record),
                'recordHash': sha256_of({k: v for k, v in record.items() if k != 'status'}),
            }
            for op, record in sorted(state['records'].items())
        },
        'catalogs': {name: _entries(catalog, sha256_of) for name, catalog in sorted(state['catalogs'].items())},
    }


def _entries(catalog: dict, digest) -> dict:
    """``{"reasons.upstream": hash, "scale": hash}``: a dict section by its keys."""
    out = {}
    for key, value in catalog.items():
        if isinstance(value, dict):
            out.update({f'{key}.{sub}': digest(item) for sub, item in value.items()})
        else:
            out[key] = digest(value)
    return dict(sorted(out.items()))


def freeze_problems(frozen: dict, now: dict) -> list:
    """What breaks the 1.0 contract; ``frozen`` and ``now`` are :func:`summary` results."""
    out = []
    version = now['registryVersion']
    bumped = _version(version) > _version(frozen['registryVersion'])
    if _version(version) < _version(frozen['registryVersion']):
        out.append(f'registry version {version} is below the frozen {frozen["registryVersion"]}')
    for op, was in frozen['ops'].items():
        row = now['ops'].get(op)
        if row is None:
            out.append(f'{op}: removed (an op of 1.0 is never removed; mark it deprecated)')
            continue
        if row['signatureHash'] != was['signatureHash']:
            out.append(f'{op}: signature changed (a 1.0 op keeps its signature; add a new op)')
        if row['status'] != was['status'] and not (
                (was['status'], row['status']) == ('beta', 'stable') or (bumped and row['status'] == 'deprecated')):
            out.append(f'{op}: status {was["status"]} → {row["status"]} (only beta → stable, '
                       f'or deprecated with a new registry version)')
        if row['recordHash'] != was['recordHash']:
            if not bumped:
                out.append(f'{op}: record changed without a new registry version')
            elif row['since'] != version:
                out.append(f'{op}: record changed, its since is {row["since"]}, not the new version {version}')
    for op, row in now['ops'].items():
        if op in frozen['ops']:
            continue
        if not bumped:
            out.append(f'{op}: new op without a new registry version')
        elif row['since'] is None or _version(row['since']) <= _version(frozen['registryVersion']):
            out.append(f'{op}: new op with since {row["since"]} (must be above {frozen["registryVersion"]})')
    for name, keys in frozen['catalogs'].items():
        now_keys = now['catalogs'].get(name, {})
        for key, digest in keys.items():
            if key not in now_keys:
                out.append(f'{name}.{key}: removed from the catalog')
            elif now_keys[key] != digest and not bumped:
                out.append(f'{name}.{key}: changed without a new registry version')
        for key in now_keys.keys() - keys.keys():
            if not bumped:
                out.append(f'{name}.{key}: added without a new registry version')
    return out


@pytest.fixture(scope='module')
def frozen():
    return json.loads(FROZEN_PATH.read_text(encoding='utf-8'))


def test_the_frozen_contract_is_registry_1_5(frozen):
    assert frozen['registryVersion'] == FROZEN_VERSION
    assert len(frozen['ops']) == 85


def test_the_registry_keeps_the_1_0_contract(frozen):
    assert freeze_problems(frozen, summary(current())) == []


def test_index_matches_the_records(frozen):
    """INDEX.json carries the same signature hashes (``registry index --check``)."""
    index = json.loads((OPS_DIR / 'INDEX.json').read_text(encoding='utf-8'))
    now = summary(current())
    assert {op: row['signatureHash'] for op, row in now['ops'].items()} == index['ops']


def test_the_package_reports_the_version():
    from animageo import native
    assert native.registry().version == current()['version']
    assert native.__registry_version__ == current()['version']


class TestRules:
    """The checker itself, on changed copies of the registry."""

    def state(self):
        return copy.deepcopy(current())

    def problems(self, frozen, state):
        return freeze_problems(frozen, summary(state))

    def test_a_changed_phrase_without_a_new_version(self, frozen):
        state = self.state()
        state['records']['point.midpoint']['phrases']['ru'] += ' '
        assert self.problems(frozen, state) == ['point.midpoint: record changed without a new registry version']

    def test_a_changed_phrase_with_a_new_version_and_since(self, frozen):
        state = self.state()
        state['version'] = '1.6'
        state['records']['point.midpoint']['phrases']['ru'] += ' '
        assert self.problems(frozen, state) == [
            'point.midpoint: record changed, its since is 1.0, not the new version 1.6']
        state['records']['point.midpoint']['since'] = '1.6'
        assert self.problems(frozen, state) == []

    def test_a_changed_signature(self, frozen):
        state = self.state()
        state['version'] = '1.6'
        record = state['records']['point.midpoint']
        record['since'] = '1.6'
        record['inputs'][0]['type'] = 'segment'
        assert self.problems(frozen, state) == [
            'point.midpoint: signature changed (a 1.0 op keeps its signature; add a new op)']

    def test_status(self, frozen):
        state = self.state()
        beta = sorted(op for op, r in state['records'].items() if r['status'] == 'beta')
        state['records'][beta[0]]['status'] = 'stable'
        assert self.problems(frozen, state) == []
        state['records']['point.midpoint']['status'] = 'deprecated'
        assert self.problems(frozen, state) == [
            'point.midpoint: status stable → deprecated (only beta → stable, or deprecated with a new registry version)']
        state['version'] = '1.6'
        assert self.problems(frozen, state) == []

    def test_a_removed_op(self, frozen):
        state = self.state()
        del state['records']['circle.excircle']
        assert self.problems(frozen, state) == [
            'circle.excircle: removed (an op of 1.0 is never removed; mark it deprecated)']

    def test_a_new_op(self, frozen):
        state = self.state()
        new = copy.deepcopy(state['records']['point.midpoint'])
        new['op'] = 'point.new'
        state['records']['point.new'] = new
        assert self.problems(frozen, state) == ['point.new: new op without a new registry version']
        state['version'] = '1.6'
        assert self.problems(frozen, state) == ['point.new: new op with since 1.0 (must be above 1.5)']
        new['since'] = '1.6'
        assert self.problems(frozen, state) == []

    def test_catalogs(self, frozen):
        state = self.state()
        reasons = state['catalogs']['_reasons']['reasons']
        key = sorted(reasons)[0]
        reasons[key] = {'changed': True}
        assert self.problems(frozen, state) == [f'_reasons.reasons.{key}: changed without a new registry version']
        reasons['a_new_reason'] = {}
        assert self.problems(frozen, state)[-1] == '_reasons.reasons.a_new_reason: added without a new registry version'
        state['version'] = '1.6'
        assert self.problems(frozen, state) == []
        del reasons[key]
        assert self.problems(frozen, state) == [f'_reasons.reasons.{key}: removed from the catalog']


def main(argv) -> int:
    if argv[1:] != ['--write']:
        print(__doc__)
        return 2
    FROZEN_PATH.write_text(json.dumps(summary(current()), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'wrote {FROZEN_PATH}')
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main(sys.argv))
