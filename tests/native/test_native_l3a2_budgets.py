"""1.9.0a2: budgets of plan L3 §6 and determinism of §7 for conditions,
the general case and automatic marks."""
import copy
import json
import math
import random
import time
from pathlib import Path

import pytest

from animageo import native
from animageo.native.conditions.apply import apply_condition
from animageo.native.conditions.marks import add_auto_marks
from animageo.native.sampling import check_general
from tests.native.test_native_l3a1_ops import _trajectory
from tests.native.test_native_perf import chain_document

SCENES = Path(__file__).resolve().parents[2] / 'animageo' / 'native' / 'parity' / 'v1' / 'scenes'
L3A2_SCENES = sorted(p for p in SCENES.glob('*.json') if p.stem.startswith(('recipe_', 'shape_')))
EQUAL = {'kind': 'eq', 'left': {'len': {'pair': ['P1', 'Z']}}, 'right': {'len': {'pair': ['P1', 'P2']}}}


def _doc_of_300():
    doc = chain_document()
    doc['operationRegistryVersion'] = '1.5'
    doc['operations']['op_Z'] = {'id': 'op_Z', 'op': 'point.free', 'args': {},
                                 'outputs': [{'slot': 'point', 'elementId': 'Z'}]}
    doc['elements']['Z'] = {'id': 'Z', 'type': 'point', 'displayName': 'Z',
                            'producer': {'operationId': 'op_Z', 'slot': 'point'}}
    doc['inputs']['Z'] = {'kind': 'point', 'value': [1.0, 2.0]}
    return native.load(doc)


def _p95(fn, runs=20):
    fn()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    times.sort()
    return times[max(0, math.ceil(0.95 * runs) - 1)]


@pytest.mark.slow
def test_apply_marks_and_general_case_on_300_operations_within_budget():
    """Plan L3 §6 on 300 operations: ``apply_condition`` 30 ms (the web
    passes the evaluation it has; the result is evaluated inside; measured
    p95 ≈ 22 ms without a garbage collection), ``auto_marks`` 5 ms per
    source (≈ 2.7 ms), the general case of 50 trials 500 ms (≈ 350 ms);
    a margin of 2 for a busy machine."""
    doc = _doc_of_300()
    assert len(doc.operations) > 300
    ev = native.evaluate(doc)
    condition = {'statement': EQUAL, 'mode': 'construct'}
    result = apply_condition(doc, condition, ev=ev)
    assert result.refusal is None
    assert _p95(lambda: apply_condition(doc, condition, ev=ev)) < 0.030 * 2
    assert add_auto_marks(doc, ['op_M0'], ev=ev).operations
    assert _p95(lambda: add_auto_marks(doc, ['op_M0'], ev=ev)) < 0.005 * 2
    cid = result.condition['id']
    assert check_general(result.document, [cid])[cid]['status'] == 'passed'
    assert _p95(lambda: check_general(result.document, [cid]), runs=5) < 0.500 * 2


def _shuffled(doc, seed):
    rng = random.Random(seed)
    out = copy.deepcopy(doc)
    for section in ('operations', 'elements', 'inputs', 'appearance'):
        items = list(out.get(section, {}).items())
        rng.shuffle(items)
        out[section] = dict(items)
    return out


@pytest.mark.parametrize('path', L3A2_SCENES, ids=lambda p: p.stem)
def test_condition_scenes_ignore_key_order(path):
    doc = json.loads(path.read_text(encoding='utf-8'))['document']
    assert doc.get('conditions'), path.stem
    shuffled = _shuffled(doc, path.stem)
    assert (native.canonical_json(native.evaluate(doc).elements)
            == native.canonical_json(native.evaluate(shuffled).elements))
    assert [s.to_dict() for s in native.steps(doc)] == [s.to_dict() for s in native.steps(shuffled)]
    assert native.describe(doc, values=True) == native.describe(shuffled, values=True)
    general = native.canonical_json(check_general(doc))
    assert general == native.canonical_json(check_general(doc))          # two runs, bit for bit
    assert general == native.canonical_json(check_general(shuffled))


@pytest.mark.parametrize('path', L3A2_SCENES, ids=lambda p: p.stem)
def test_condition_scenes_same_values_forward_backward_and_after_reload(path):
    """Plan L3 §7: the slots and branches a recipe chose are in the
    document, so a trajectory of the inputs gives the same values both ways
    and after ``load → dumps → load``."""
    doc = json.loads(path.read_text(encoding='utf-8'))['document']
    forward = [native.canonical_json(native.evaluate(doc, inputs=_trajectory(doc, k)).elements)
               for k in range(50)]
    backward = [native.canonical_json(native.evaluate(doc, inputs=_trajectory(doc, k)).elements)
                for k in reversed(range(50))]
    assert forward == backward[::-1]
    again = native.dump(native.load(native.dumps(native.load(doc))))
    for k in (0, 17, 49):
        assert native.canonical_json(native.evaluate(again, inputs=_trajectory(doc, k)).elements) == forward[k]
