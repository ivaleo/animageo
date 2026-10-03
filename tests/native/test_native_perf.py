"""Speed of the reference kernel: 300 operations, p95 of 20 runs.

The contract (plan L0, task 10) is p95 <= 100 ms. The default run allows
three times that, so a slow or loaded machine does not fail the suite;
``ANIMAGEO_PERF_STRICT=1`` applies the contract threshold. Measured numbers
are printed (``pytest -s``).
"""
import math
import os
import time

import pytest

from animageo import native
from tests.native.conftest import DocBuilder

RUNS = 20
CONTRACT_MS = 100.0
THRESHOLD_MS = CONTRACT_MS if os.environ.get('ANIMAGEO_PERF_STRICT') == '1' else 3 * CONTRACT_MS


def chain_document(target_ops=300):
    """Chains of midpoints, lines and intersections, about ``target_ops`` operations."""
    b = DocBuilder('perf', bounds=(-10, -10, 10, 10))
    points = []
    for i in range(10):
        angle = 2 * math.pi * i / 10
        name = f'P{i}'
        b.free(name, round(8 * math.cos(angle), 3), round(8 * math.sin(angle), 3))
        points.append(name)
    step = 0
    while len(b.doc['operations']) < target_ops:
        m = f'M{step}'
        b.midpoint(m, points[-1], points[-4])
        l1 = f'l{step}'
        l2 = f'm{step}'
        b.line(l1, m, points[-7])
        b.line(l2, points[-2], points[-9])
        x = f'X{step}'
        b.intersect(x, l1, l2)
        points.extend([m, x])
        step += 1
    return b.doc


def percentile(samples, q):
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


@pytest.mark.slow
def test_300_ops_p95():
    doc = native.load(chain_document())
    n_ops = len(doc.operations)
    assert n_ops >= 300
    ev = native.evaluate(doc)                       # warm-up (registry cache, imports)
    defined = sum(rec['state'] == 'defined' for rec in ev.elements.values())
    assert defined >= 0.9 * len(ev.elements)
    timings = []
    for _ in range(RUNS):
        start = time.perf_counter()
        native.evaluate(doc)
        timings.append((time.perf_counter() - start) * 1000)
    p50 = percentile(timings, 0.50)
    p95 = percentile(timings, 0.95)
    print(f'\nnative.evaluate: {n_ops} ops, {defined}/{len(ev.elements)} defined, '
          f'p50 {p50:.1f} ms, p95 {p95:.1f} ms, max {max(timings):.1f} ms ({RUNS} runs)')
    assert p95 <= THRESHOLD_MS, f'p95 {p95:.1f} ms > {THRESHOLD_MS:.0f} ms'


@pytest.mark.slow
def test_300_ops_with_checks_p95():
    doc = native.load(chain_document())
    native.check(doc)
    timings = []
    for _ in range(RUNS):
        start = time.perf_counter()
        report = native.check(doc)
        timings.append((time.perf_counter() - start) * 1000)
    p95 = percentile(timings, 0.95)
    print(f'\nnative.check: p95 {p95:.1f} ms ({len(report.results)} checks)')
    assert report.ok
    assert p95 <= THRESHOLD_MS, f'p95 {p95:.1f} ms > {THRESHOLD_MS:.0f} ms'
