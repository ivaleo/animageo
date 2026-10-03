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


def l1_mix_document(target_ops=300):
    """Rays, line×circle, circle×circle, another point and points on paths,
    about ``target_ops`` operations."""
    b = DocBuilder('perf_l1', bounds=(-10, -10, 10, 10), registry_version='1.1')
    points = []
    for i in range(10):
        angle = 2 * math.pi * i / 10
        name = f'P{i}'
        b.free(name, round(8 * math.cos(angle), 3), round(8 * math.sin(angle), 3))
        points.append(name)
    circles = []
    step = 0
    while len(b.doc['operations']) < target_ops:
        s = str(step)
        b.midpoint('M' + s, points[-1], points[-4])
        b.circle('k' + s, 'M' + s, points[-7])
        b.line('l' + s, points[-2], points[-9])
        b.line_circle('A' + s, 'B' + s, 'l' + s, 'k' + s)
        b.ray('r' + s, points[-3], 'M' + s)
        b.on_path('U' + s, 'k' + s, 0.3 + step * 0.7)
        b.on_path('V' + s, 'r' + s, 1.5)
        if circles:
            b.circle_circle('C' + s, 'D' + s, 'k' + s, circles[-1])
            b.other_than('Z' + s, 'k' + s, circles[-1], 'C' + s)
        circles.append('k' + s)
        points.extend(['M' + s, 'U' + s, 'V' + s])
        step += 1
    return b.doc


@pytest.mark.slow
def test_l1_mix_p95():
    doc = native.load(l1_mix_document())
    n_ops = len(doc.operations)
    assert n_ops >= 300
    ev = native.evaluate(doc)
    defined = sum(rec['state'] == 'defined' for rec in ev.elements.values())
    ops = {op['op'] for op in doc.operations.values()}
    assert {'intersect.line_circle', 'intersect.circle_circle', 'intersect.other_than',
            'point.on_path', 'ray.by_points'} <= ops
    assert defined >= 0.75 * len(ev.elements)
    timings = []
    for _ in range(RUNS):
        start = time.perf_counter()
        native.evaluate(doc)
        timings.append((time.perf_counter() - start) * 1000)
    p50 = percentile(timings, 0.50)
    p95 = percentile(timings, 0.95)
    print(f'\nnative.evaluate (L1 mix): {n_ops} ops, {defined}/{len(ev.elements)} defined, '
          f'p50 {p50:.1f} ms, p95 {p95:.1f} ms, max {max(timings):.1f} ms ({RUNS} runs)')
    assert p95 <= THRESHOLD_MS, f'p95 {p95:.1f} ms > {THRESHOLD_MS:.0f} ms'


@pytest.mark.slow
def test_l1_edits_p95():
    doc = native.load(l1_mix_document())
    first = sorted(e for e, el in doc.elements.items() if el['type'] == 'point')[:3]
    timings = {'closure': [], 'delete': [], 'rename': []}
    for _ in range(RUNS):
        for name, call in (('closure', lambda: native.closure(doc, first)),
                           ('delete', lambda: native.delete(doc, first[:1])),
                           ('rename', lambda: native.rename(doc, 'M0', 'N_{1}'))):
            start = time.perf_counter()
            call()
            timings[name].append((time.perf_counter() - start) * 1000)
    line = ', '.join(f'{name} p95 {percentile(t, 0.95):.1f} ms' for name, t in timings.items())
    print(f'\nnative edits (L1 mix, {len(doc.operations)} ops): {line}')
    for name, t in timings.items():
        assert percentile(t, 0.95) <= THRESHOLD_MS, name
