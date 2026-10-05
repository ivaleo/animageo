"""1.11.0rc1 (L6 item 9): ``evaluate`` of 300 operations ≤ 50 ms (kernel spec
§16 L6), on two documents:

- the chain of the L0 contract (midpoints, lines, intersections);
- a mix of every operation of the registry: the parity scenes merged
  under prefixed IDs, chosen greedily to cover all ops, then filled to 300.
  A locus samples its mover (≈ 8–18 ms each, its own budget in
  ``test_native_l3a1_ops.py``), so the mix holds one locus.

p95 of 20 runs with the garbage collector off (as ``timeit``; see
``test_native_l3a2_budgets._p95``). The numbers are printed (``pytest -s``).
"""
import json
from pathlib import Path

import pytest

from animageo import native
from tests.native.test_native_l3a2_budgets import _p95
from tests.native.test_native_perf import chain_document

SCENES = Path(__file__).resolve().parents[2] / 'animageo' / 'native' / 'parity' / 'v1' / 'scenes'
BUDGET_S = 0.050
TARGET_OPS = 300


def _prefixed(value, prefix):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in ('elementId', 'operationId', 'id') and isinstance(item, str):
                out[key] = prefix + item
            elif key in ('elementIds', 'operationIds') and isinstance(item, list):
                out[key] = [prefix + x for x in item]
            else:
                out[key] = _prefixed(item, prefix)
        return out
    if isinstance(value, list):
        return [_prefixed(item, prefix) for item in value]
    return value


def _scenes():
    out = []
    for path in sorted(SCENES.glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))['document']
        if native.validate(doc):
            continue                                  # scenes of broken documents
        loci = sum(op['op'] == 'locus.of_point' for op in doc['operations'].values())
        out.append((path.stem, doc, loci))
    return out


def mix_document(target=TARGET_OPS):
    """Every op of the registry (one locus), ``target`` operations or more."""
    doc = {'format': 'animageo-construction/v1', 'documentId': 'mix', 'operationRegistryVersion': '1.5',
           'operations': {}, 'elements': {}, 'inputs': {}, 'viewDefaults': {'bounds': [-10, -10, 10, 10]}}
    scenes = _scenes()
    covered, loci, used = set(), 0, 0

    def add(scene):
        nonlocal doc, used
        prefix = f's{used}_'
        trial = json.loads(json.dumps(doc))
        for section in ('operations', 'elements', 'inputs'):
            for key, value in scene.get(section, {}).items():
                trial[section][prefix + key] = _prefixed(value, prefix)
        if native.validate(trial):
            return False
        doc, used = trial, used + 1
        return True

    remaining = list(scenes)
    while True:                                       # cover: most new ops first
        best = max(remaining, default=None,
                   key=lambda s: (len({o['op'] for o in s[1]['operations'].values()} - covered)
                                  if loci + s[2] <= 1 else -1, -len(s[1]['operations'])))
        if best is None:
            break
        gain = {o['op'] for o in best[1]['operations'].values()} - covered
        if not gain or loci + best[2] > 1:
            break
        remaining.remove(best)
        if add(best[1]):
            covered |= gain
            loci += best[2]
    for _name, scene, scene_loci in remaining:        # fill without another locus
        if len(doc['operations']) >= target:
            break
        if not scene_loci:
            add(scene)
    return doc


@pytest.fixture(scope='module')
def mix():
    return native.load(mix_document())


def test_the_mix_covers_the_registry(mix):
    ops = {op['op'] for op in mix.operations.values()}
    assert ops == set(native.registry().ops)
    assert len(mix.operations) >= TARGET_OPS
    assert sum(op['op'] == 'locus.of_point' for op in mix.operations.values()) == 1


@pytest.mark.slow
def test_evaluate_300_operations_within_50_ms(mix, capsys):
    chain = native.load(chain_document())
    rows = []
    for name, doc in (('chain', chain), ('registry mix', mix)):
        ev = native.evaluate(doc)
        defined = sum(rec['state'] == 'defined' for rec in ev.elements.values())
        p95 = _p95(lambda: native.evaluate(doc))
        rows.append((name, len(doc.operations), defined, len(ev.elements), p95))
    with capsys.disabled():
        for name, n_ops, defined, n_el, p95 in rows:
            print(f'\nnative.evaluate ({name}): {n_ops} ops, {defined}/{n_el} defined, '
                  f'p95 {p95 * 1000:.1f} ms (budget {BUDGET_S * 1000:.0f} ms)')
    for name, _n, _d, _e, p95 in rows:
        assert p95 <= BUDGET_S, f'{name}: p95 {p95 * 1000:.1f} ms > {BUDGET_S * 1000:.0f} ms'
