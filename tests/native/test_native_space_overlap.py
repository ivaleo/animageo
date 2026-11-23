"""Positive-volume intersections of convex solids: bounded work, same answers."""
from __future__ import annotations

import math
import time

import pytest

from animageo.native.space import overlap, solids
from animageo.native.space.build import SpaceBuilder
from animageo.native.space.scene import flat_scene


def _pyramid(k, *, cx=0.0, cy=0.0, h=2.0, z=0.0, phase=0.0, tag='p'):
    base = [(cx + math.cos(2 * math.pi * i / k + phase), cy + math.sin(2 * math.pi * i / k + phase), z)
            for i in range(k)]
    return solids.pyramid(base, (cx, cy, z + h), labels=tuple(f'{tag}{i}' for i in range(k + 1)))


def test_parallel_edges_share_one_direction():
    # 200 base edges in 100 antiparallel pairs and 200 lateral edges.
    assert len(overlap._edge_directions(_pyramid(200))) == 300
    assert len(overlap._edge_directions(solids.cube(1.0))) == 3


@pytest.mark.slow
def test_a_pair_of_large_intersecting_pyramids_is_decided_quickly():
    a, b = _pyramid(400, tag='a'), _pyramid(400, cx=0.5, phase=0.3, tag='b')
    start = time.perf_counter()
    found = list(overlap.overlapping_solids([('B', b), ('A', a)]))
    elapsed = time.perf_counter() - start
    assert found == [('A', 'B', True)]
    assert elapsed < 0.5


@pytest.mark.slow
def test_large_pyramids_with_overlapping_bounds_but_apart_are_decided_quickly():
    # The boxes overlap; a lateral face of A separates the bodies.
    a, b = _pyramid(400, tag='a'), _pyramid(400, cx=1.9, cy=0.4, z=1.0, tag='b')
    start = time.perf_counter()
    found = list(overlap.overlapping_solids([('A', a), ('B', b)]))
    elapsed = time.perf_counter() - start
    assert found == []
    assert elapsed < 0.5


def _prism_and_cube(y):
    # The prism and the cube of the scene tests: at y=3 only the edge-cross
    # axis z-y separates them, at y=1 they intersect.
    b = SpaceBuilder('prism')
    b.point('KA', 0, 0, 0)
    b.point('KB', 2, 0, 0)
    b.cube('K', 'KA', 'KB', vertices=['KC', 'KD', 'KA_1', 'KB_1', 'KC_1', 'KD_1'])
    for name, (x, dy, z) in {'P': (2, 0, -1), 'Q': (3, 1, 1), 'R': (3, 3, -1),
                              'U': (2, 2, -3), 'V': (0, -2, -3)}.items():
        b.point(name, x, dy + y, z + 0.25)
    b.prism('J', ['P', 'Q', 'R', 'U'], 'V')
    return b.data()


def test_an_exhausted_axis_budget_is_reported_not_guessed(monkeypatch):
    assert flat_scene(_prism_and_cube(3))['diagnostics'] == []
    monkeypatch.setattr(overlap, 'AXIS_BUDGET', 0)
    flat = flat_scene(_prism_and_cube(3))
    assert flat['diagnostics'] == [{'code': 'overlap_order', 'id': 'J', 'otherId': 'K', 'approximate': True}]
    assert {f['solid'] for f in flat['fills']} == set()


def test_a_common_interior_point_proves_an_intersection_without_axes(monkeypatch):
    monkeypatch.setattr(overlap, 'AXIS_BUDGET', 0)
    a, b = _pyramid(12, tag='a'), _pyramid(12, cx=0.5, phase=0.2, tag='b')
    assert list(overlap.overlapping_solids([('A', a), ('B', b)])) == [('A', 'B', True)]
    # A thin wedge without a probe inside both falls back to the axes.
    assert flat_scene(_prism_and_cube(1))['diagnostics'] == [
        {'code': 'overlap_order', 'id': 'J', 'otherId': 'K', 'approximate': True}]
    monkeypatch.undo()
    assert flat_scene(_prism_and_cube(1))['diagnostics'] == [{'code': 'overlap_order', 'id': 'J', 'otherId': 'K'}]


def test_the_answer_does_not_depend_on_the_order_of_the_solids():
    a, b, c = _pyramid(12, tag='a'), _pyramid(12, cx=0.5, tag='b'), _pyramid(12, cx=5, tag='c')
    first = list(overlap.overlapping_solids([('A', a), ('B', b), ('C', c)]))
    assert first == list(overlap.overlapping_solids([('C', c), ('B', b), ('A', a)])) == [('A', 'B', True)]
