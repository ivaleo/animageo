"""R4 port (``animageo/native/labels/r4.py``) against the client solver.

``fixtures/labels_r4/client_cases.json`` — the calls of the client's tests
(the 20 scenes, the style place, lines meeting at a point, the label along a
segment, pinned labels and the restored automatic place, the drag, the view
frame with an origin, the three regression scenes with and without the
default paint, the 50-label bench, the scenes of the parity check) and the
hysteresis cases; ``synthetic.json`` — random display lists with every
obstacle kind, paint and memory. Each call was recorded from the client
solver: its inputs and what it returned (a few by the tie rule, as their
headers say). Here every call is replayed: ``k`` must be equal, centres,
boxes and corners within 0.01 px. The client's own assertions are then
checked on the port's results. ``ties.json`` — structural ties (equal gaps,
mirrored places): the rule's ``k``, the same with any input moved by an ulp.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import pytest

from animageo.native.labels import r4

FIXTURES = Path(__file__).parent / 'fixtures' / 'labels_r4'
TOL = 0.01
VIEW = (640, 480)


def _cases(name):
    data = json.loads((FIXTURES / name).read_text(encoding='utf-8'))
    assert data['format'] == 'animageo-labels-r4-cases/1'
    return {c['id']: c for c in data['cases']}


CLIENT = _cases('client_cases.json')
SYNTHETIC = _cases('synthetic.json')
TIES = _cases('ties.json')


def _list(case, step):
    lst = case['steps'][step]['list']
    return case['steps'][lst['ref']]['list'] if 'ref' in lst else lst


def _run(case, step=0, memory='recorded'):
    s = case['steps'][step]
    mem = s['memory'] if memory == 'recorded' else memory
    return r4.layout(_list(case, step), s['view'], mem, s['paint'])


def _after(lst, placements):
    """The labels after the call: placed ones at their new box, the others unchanged."""
    out = []
    for lb in lst['labels']:
        p = placements.get(lb['id'])
        if p is None:
            out.append({'id': lb['id'], 'x': lb['x'], 'y': lb['y'], 'box': list(lb['box']), 'edge': lb['edge']})
        else:
            out.append({'id': lb['id'], 'x': p['x'], 'y': p['y'], 'box': list(p['box']), 'edge': lb['edge']})
    return out


def _close(a, b):
    return all(abs(x - y) <= TOL for x, y in zip(a, b, strict=True))


def _check_step(case, step):
    s = case['steps'][step]
    lst = _list(case, step)
    placements, memory, stats = _run(case, step)
    expect = s['expect']
    where = f"{case['id']} step {step}"
    assert stats == expect['stats'], where
    assert list(memory) == list(expect['memory']), where
    for key, entry in expect['memory'].items():
        assert memory[key]['k'] == entry['k'], f'{where}: {key}'
        assert (memory[key]['ax'], memory[key]['ay']) == (entry['ax'], entry['ay']), f'{where}: {key}'
    inputs = {lb['id']: lb for lb in lst['labels']}
    for lab in expect['labels']:
        p = placements.get(lab['id'])
        if p is None:
            assert inputs[lab['id']]['box'] == lab['box'], f"{where}: {lab['id']} moved without a placement"
            continue
        assert p['k'] == expect['memory'][lab['id']]['k'], f"{where}: k of {lab['id']}"
        center = ((lab['box'][0] + lab['box'][2]) / 2, (lab['box'][1] + lab['box'][3]) / 2)
        assert _close(p['center'], center), f"{where}: centre of {lab['id']}"
        assert _close(p['box'], lab['box']), f"{where}: box of {lab['id']}"
        assert _close((p['x'], p['y']), (lab['x'], lab['y'])), f"{where}: corner of {lab['id']}"
    return placements, memory, stats


# ------------------------------------------------------- every recorded call


@pytest.mark.parametrize('case_id', sorted(CLIENT))
def test_client_case(case_id):
    case = CLIENT[case_id]
    for step in range(len(case['steps'])):
        _check_step(case, step)


@pytest.mark.parametrize('case_id', sorted(SYNTHETIC))
def test_synthetic_case(case_id):
    case = SYNTHETIC[case_id]
    for step in range(len(case['steps'])):
        _check_step(case, step)


def test_memory_chains_are_consistent():
    """A step's memory is what the previous step returned (the chains were recorded in order)."""
    for case in [*CLIENT.values(), *SYNTHETIC.values(), *TIES.values()]:
        prev = None
        for s in case['steps']:
            if prev is not None and s['memory'] is not None and s['memory'] != prev:
                pytest.fail(f"{case['id']}: memory chain broken")
            if s['memory'] is not None:
                prev = s['expect']['memory']


def test_fixtures_cover_every_obstacle_kind():
    seen = set()
    for case in [*CLIENT.values(), *SYNTHETIC.values()]:
        for i in range(len(case['steps'])):
            lst = _list(case, i)
            paint = case['steps'][i]['paint'] or {'byId': {}}
            for key in ('points', 'linears', 'circles', 'polygons', 'polylines', 'ticks'):
                if lst[key]:
                    seen.add(key)
            seen |= {f"arc:{a['kind']}" for a in lst['arcs']}
            seen |= {'angle:square' for a in lst['angles'] if a['square'] is not None}
            seen |= {'angle:radii' for a in lst['angles'] if a['radii']}
            seen |= {'polyline>64' for p in lst['polylines'] if len(p['pts']) > 2 * 65}
            seen |= {'sectorSides' for v in paint['byId'].values() if v.get('sectorSides')}
            seen |= {'strokeWidth' for v in paint['byId'].values() if 'strokeWidth' in v}
            for lb in lst['labels']:
                place = lb.get('place')
                if place is None:
                    seen.add('label:fixed')
                    continue
                seen.add(f"label:{place['kind']}" + (':pinned' if place['pinned'] else ''))
                if 'along' in place:
                    seen.add('label:along')
            if 'x' in case['steps'][i]['view']:
                seen.add('view:origin')
    expected = {
        'points', 'linears', 'circles', 'polygons', 'polylines', 'ticks', 'arc:arc', 'arc:sector',
        'arc:circlesegment', 'angle:square', 'angle:radii', 'polyline>64', 'sectorSides', 'strokeWidth',
        'label:fixed', 'label:point', 'label:point:pinned', 'label:line', 'label:line:pinned', 'label:measure',
        'label:along', 'view:origin',
    }
    assert expected <= seen, expected - seen


# ------------------------------------------- the client's assertions (layout.spec)


def _overlaps(lst, after, view=VIEW):
    """Overlaps of the laid out labels (not counting the label's own line), as the client counts them."""
    out = {'labels': 0, 'points': 0, 'lines': 0, 'outside': 0}
    boxes = [lb['box'] for lb in after]
    for i, (l, t, r, b) in enumerate(boxes):
        if l < 0 or t < 0 or r > view[0] or b > view[1]:
            out['outside'] += 1
        for bl, bt, br, bb in boxes[i + 1:]:
            if min(r, br) - max(l, bl) > 0.5 and min(b, bb) - max(t, bt) > 0.5:
                out['labels'] += 1
        for p in lst['points']:
            if p['x'] + 4 > l and p['x'] - 4 < r and p['y'] + 4 > t and p['y'] - 4 < b:
                out['points'] += 1
        inner = (l + 1, t + 1, r - 1, b - 1)
        for s in lst['linears']:
            if r4.segment_hits_box(s['x1'], s['y1'], s['x2'], s['y2'], inner):
                out['lines'] += 1
    return out


def test_twenty_scenes_without_overlaps():
    report = {}
    for seed in range(1, 21):
        case = CLIENT[f'layout/scenes/seed-{seed}']
        lst = _list(case, 0)
        placements, _, _ = _run(case)
        assert len(lst['labels']) >= 4
        o = _overlaps(lst, _after(lst, placements))
        if any(o.values()):
            report[seed] = o
    assert report == {}


def test_free_point_keeps_the_style_place():
    case = CLIENT['layout/style-place']
    lst = _list(case, 0)
    placements, _, _ = _run(case)
    for lb in lst['labels']:
        p = placements[lb['id']]
        assert lb['place']['kind'] == 'point'
        assert p['x'] == pytest.approx(lb['x'], abs=1e-6)
        assert p['y'] == pytest.approx(lb['y'], abs=1e-6)


def test_point_label_leaves_meeting_lines():
    # Lines go right and up from A: the label goes left and down.
    case = CLIENT['layout/away-from-lines']
    lst = _list(case, 0)
    placements, _, _ = _run(case)
    a = placements['A']
    p = next(q for q in lst['points'] if q['id'] == 'A')
    assert a['center'][0] < p['x']
    assert a['center'][1] > p['y']


def test_segment_label_along_near_the_middle():
    case = CLIENT['layout/segment-along']
    lst = _list(case, 0)
    placements, _, _ = _run(case)
    c = placements['c']
    s = next(q for q in lst['linears'] if q['id'] == 'c')
    l, t, r, b = c['box']
    assert abs(c['center'][0] - (s['x1'] + s['x2']) / 2) < r - l + 1
    assert b <= s['y1'] - 3


def test_pinned_label_does_not_move_and_others_yield():
    case = CLIENT['layout/pinned']
    lst = _list(case, 0)
    placements, _, _ = _run(case)
    assert 'B' not in placements
    b1 = next(lb for lb in lst['labels'] if lb['id'] == 'B')['box']
    a = placements['A']['box']
    assert min(a[2], b1[2]) - max(a[0], b1[0]) <= 0.5 or min(a[3], b1[3]) - max(a[1], b1[1]) <= 0.5


def test_restore_auto_returns_to_the_former_place():
    case = CLIENT['layout/restore-auto']

    def at(step):
        placements, memory, _ = _run(case, step)
        lst = _list(case, step)
        a = next(lb for lb in _after(lst, placements) if lb['id'] == 'A')
        return (a['x'], a['y']), memory

    p0, _ = at(0)
    # A segment to the left: the clean former place stays (hysteresis)…
    assert at(1)[0] == p0
    # …although from scratch the solver takes the place opposite the segment.
    assert at(2)[0] != p0
    # Pinned (dragged): elsewhere, and the memory of the automatic place is kept.
    pinned, memory = at(3)
    assert pinned != p0
    assert 'A' in memory
    # Automatic again: back to p0.
    assert at(4)[0] == p0


def test_corner_of_the_box_is_the_style_edge():
    case = CLIENT['layout/scenes/seed-2']
    lst = _list(case, 0)
    placements, _, _ = _run(case)
    for lb in _after(lst, placements):
        l, t, r, b = lb['box']
        assert lb['x'] == pytest.approx(l + ((lb['edge'][0] + 1) / 2) * (r - l), abs=1e-6)
        assert lb['y'] == pytest.approx(t + ((1 - lb['edge'][1]) / 2) * (b - t), abs=1e-6)


def test_drag_settle_leaves_lines_clear():
    case = CLIENT['layout/drag-settle']
    lst = _list(case, 1)
    placements, _, _ = _run(case, 1)
    assert _overlaps(lst, _after(lst, placements))['lines'] == 0


def test_unmoved_elements_are_not_evaluated():
    case = CLIENT['layout/unmoved-not-reevaluated']
    _, _, stats = _run(case, 1)
    # The anchors of C, a (BC) and b (CA) moved; A, B, D, M, c are in place and clean.
    assert stats['evaluated'] <= 3
    assert stats['moved'] == 0


def test_hundred_labels_case():
    case = CLIENT['layout/budget-100']
    placements, _, stats = _run(case)
    assert len(_list(case, 0)['labels']) == 100
    assert len(placements) == 100
    assert stats == {'evaluated': 100, 'moved': 0}


def test_view_origin_moves_the_frame():
    # The place by the edge is forbidden in the window [0, 200] and free in [−100, 300].
    in_window = _run(CLIENT['layout/view-origin/window-0-200'])[0]['A']['box']
    assert in_window[2] <= 200
    shifted = _run(CLIENT['layout/view-origin/window-shifted-x'])[0]['A']['box']
    assert shifted[2] > 200
    # Origin y: window [40, 140] — the place above the anchor (y < 40) is beyond the edge.
    low = _run(CLIENT['layout/view-origin/window-shifted-y'])[0]['A']['box']
    assert low[1] >= 40


# ------------------------------------------------ regression.spec


def _laid_list(lst, placements):
    laid = copy.deepcopy(lst)
    for lb, after in zip(laid['labels'], _after(lst, placements), strict=True):
        lb['box'] = after['box']
    return laid


@pytest.mark.parametrize('scene', ['triangle-height-circle', 'arc', 'ggb-circles'])
def test_regression_scenes_clear_of_geometry(scene):
    for case_id in (f'regression/{scene}', f'regression/{scene}/default-paint'):
        case = CLIENT[case_id]
        lst = _list(case, 0)
        paint = case['steps'][0]['paint']
        placements, _, _ = _run(case)
        assert lst['labels']
        assert r4.geometry_pairs(_laid_list(lst, placements), paint) == []


def test_large_arc_hits_between_chord_ends():
    a = math.pi / 16
    x = 300 * math.cos(a)
    y = 300 * math.sin(a)
    assert r4.arc_hits_box(0, 0, 300, 0, math.pi / 8, (x - 0.5, y - 0.5, x + 0.5, y + 0.5))
    assert not r4.arc_hits_box(0, 0, 300, 0, math.pi / 8, (-301, -1, -299, 1))


@pytest.mark.slow
def test_fifty_labels_budget():
    """50 labels, a full layout without memory: p95 ≤ 100 ms."""
    case = CLIENT['regression/bench-50']
    lst = r4.DisplayList.from_dict(_list(case, 0))
    view = case['steps'][0]['view']
    assert len(lst.labels) == 50
    times = []
    for run in range(60):
        t0 = time.perf_counter()
        r4.layout(lst, view)
        if run >= 10:
            times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[math.ceil(len(times) * 0.95) - 1]
    assert p95 <= 100, f'p95 {p95:.1f} ms'


# ------------------------------------------------------------ memory


def test_same_frame_keeps_every_place():
    case = CLIENT['memory/same-frame']
    first, memory, _ = _run(case, 0)
    again, memory2, stats = r4.layout(_list(case, 1), case['steps'][1]['view'], memory)
    assert stats == {'evaluated': 0, 'moved': 0}
    assert again == first
    assert memory2 == memory


def test_anchor_shift_below_eps_keeps_the_place():
    case = CLIENT['memory/anchor-eps']
    first, memory, _ = _run(case, 0)
    moved, memory2, stats = _run(case, 1)
    assert stats == {'evaluated': 0, 'moved': 0}
    assert moved['A']['k'] == first['A']['k']
    assert (memory2['A']['ax'], memory2['A']['ay']) == (100.3, 99.8)


@pytest.mark.parametrize(('k', 'stays'), [(2, True), (3, True), (5, False)])
def test_hysteresis_needs_a_quarter_cheaper_place(k, stays):
    # Free point, style place k = 1 (cost 1.00); the remembered place k costs
    # 1 + 0.15·d + 0.02: d = 1 → 1.17, d = 2 → 1.32 (gain < 25 %, stays), d = 4 → 1.62 (moves).
    case = CLIENT[f'memory/hysteresis-k{k}']
    placements, _, stats = _run(case)
    assert stats['evaluated'] == 1
    assert placements['A']['k'] == (k if stays else 1)
    assert stats['moved'] == (0 if stays else 1)


def test_dirty_former_place_moves_even_when_still():
    placements, _, stats = _run(CLIENT['memory/prev-dirty'])
    assert placements['A']['k'] != 1
    assert stats == {'evaluated': 1, 'moved': 1}


def test_stale_memory():
    placements, memory, stats = _run(CLIENT['memory/stale'])
    assert placements['A']['k'] == 1  # k = 40 is out of range: a fresh search
    assert 'gone' not in memory
    assert stats == {'evaluated': 1, 'moved': 1}


def test_no_memory_equals_empty_memory_and_input_is_not_modified():
    for case in (CLIENT['layout/scenes/seed-3'], CLIENT['parity/segments-angles/style'], SYNTHETIC['synthetic/seed-4']):
        s = case['steps'][0]
        lst = _list(case, 0)
        assert r4.layout(lst, s['view'], None, s['paint']) == r4.layout(lst, s['view'], {}, s['paint'])
    case = SYNTHETIC['synthetic/seed-5']
    s = case['steps'][2]
    before = copy.deepcopy(s['memory'])
    lst_before = copy.deepcopy(_list(case, 2))
    r4.layout(_list(case, 2), s['view'], s['memory'], s['paint'])
    assert s['memory'] == before
    assert _list(case, 2) == lst_before


# ---------------------------------------------------------------- ties


@pytest.mark.parametrize('case_id', sorted(TIES))
def test_tie_case(case_id):
    case = TIES[case_id]
    for step in range(len(case['steps'])):
        _check_step(case, step)


def _numbers(obj, path=()):
    """Paths of the measured numbers of an input (not the corner ``edge``, not ``k``)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield path
    elif isinstance(obj, dict):
        for key, v in obj.items():
            if key not in ('edge', 'k'):
                yield from _numbers(v, (*path, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _numbers(v, (*path, i))


def _nudged(obj, path, to):
    out = copy.deepcopy(obj)
    cur = out
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = math.nextafter(float(cur[path[-1]]), to)
    return out


@pytest.mark.parametrize('case_id', sorted(TIES))
def test_one_ulp_does_not_change_k(case_id):
    """Any input moved by one ulp either way: every label keeps its k (and its box)."""
    case = TIES[case_id]
    for step, s in enumerate(case['steps']):
        expect = {key: e['k'] for key, e in s['expect']['memory'].items()}
        boxes = {lab['id']: lab['box'] for lab in s['expect']['labels']}
        inputs = {'list': _list(case, step), 'view': s['view'], 'memory': s['memory']}
        changed = []
        for path in _numbers(inputs):
            for to in (math.inf, -math.inf):
                o = _nudged(inputs, path, to)
                placements, memory, _ = r4.layout(o['list'], o['view'], o['memory'], s['paint'])
                got = {key: e['k'] for key, e in memory.items()}
                if got != expect or not all(_close(p['box'], boxes[key]) for key, p in placements.items()):
                    changed.append((path, to, got))
        assert changed == [], f"{case['id']} step {step}"


def test_equal_gaps_take_the_first_from_east():
    # Gaps from the smallest direction in [0, 2π) (a hair below 2π is 0), counter-clockwise.
    assert _run(TIES['ties/midpoint-horizontal'])[0]['M']['k'] == 2  # above
    assert _run(TIES['ties/point-on-flat-line'])[0]['P']['k'] == 2  # above
    assert _run(TIES['ties/midpoint-vertical'])[0]['M']['k'] == 4  # left
    assert _run(TIES['ties/cross'])[0]['O']['k'] == 1  # north-east


def test_half_octant_goes_up():
    # The bisector at 337.5° is east (8 ≡ 0), not south-east; at 112.5° north-west.
    assert _run(TIES['ties/half-octant-corner'])[0]['V']['k'] == 0
    s = _list(TIES['ties/half-octant-along'], 0)['labels'][0]
    x1, y1, x2, y2 = s['place']['along']
    n = (y1 - y2, x2 - x1)  # the side +n, screen axes: its normal is at -67.5° (y up)
    assert n[0] > 0 and n[1] > 0
    placements = _run(TIES['ties/half-octant-along'])[0]
    assert placements['s']['k'] == 4  # the side -n (112.5°), t = 0.5: its corner is that of north-west
    l, t, r, b = placements['s']['box']
    gap = r4.ALONG_GAP
    mx, my = x1 + (x2 - x1) * 0.5 - n[0] / math.hypot(*n) * gap, y1 + (y2 - y1) * 0.5 - n[1] / math.hypot(*n) * gap
    assert (r, b) == pytest.approx((mx, my))  # the corner facing the line: right-bottom


def test_equal_costs_keep_the_earlier_place_and_the_remembered_one():
    # 13 and 15 (outer ring, south-west and south-east) overlap the lower box equally.
    assert _run(TIES['ties/mirrored-places'])[0]['P']['k'] == 13
    placements, _, stats = _run(TIES['ties/mirrored-places/remembered'])
    assert placements['P']['k'] == 15
    assert stats == {'evaluated': 1, 'moved': 0}


# ------------------------------------------------------- determinism


def test_deterministic_and_independent_of_mapping_order():
    case = SYNTHETIC['synthetic/seed-9']
    s = case['steps'][3]
    lst = _list(case, 3)
    first = r4.layout(lst, s['view'], s['memory'], s['paint'])
    for _ in range(3):
        assert r4.layout(lst, s['view'], s['memory'], s['paint']) == first
    reversed_memory = dict(reversed(list(s['memory'].items())))
    reversed_paint = {'byId': dict(reversed(list(s['paint']['byId'].items())))}
    view = dict(reversed(list(s['view'].items())))
    placements, memory, stats = r4.layout(lst, view, reversed_memory, reversed_paint)
    assert placements == first[0]
    assert stats == first[2]
    assert {k: memory[k] for k in first[1]} == first[1]


def test_dataclass_input_equals_dict_input():
    case = CLIENT['parity/segments-angles/style']
    s = case['steps'][0]
    lst = _list(case, 0)
    as_dict = r4.layout(lst, s['view'], None, s['paint'])
    as_types = r4.layout(
        r4.DisplayList.from_dict(lst),
        r4.LayoutView(s['view']['width'], s['view']['height']),
        None,
        r4.Paint.from_dict(s['paint']) if s['paint'] else None,
    )
    assert as_types == as_dict


def test_non_finite_input_is_refused():
    lst = copy.deepcopy(_list(CLIENT['layout/style-place'], 0))
    lst['labels'][0]['ax'] = math.nan
    with pytest.raises(ValueError, match='finite'):
        r4.layout(lst, {'width': 640, 'height': 480})
    lst = copy.deepcopy(_list(CLIENT['layout/style-place'], 0))
    lst['labels'][0]['place']['kind'] = 'curve'
    with pytest.raises(ValueError, match='kind'):
        r4.layout(lst, {'width': 640, 'height': 480})


def test_dataclass_input_is_checked_as_well():
    lst = r4.DisplayList.from_dict(_list(CLIENT['layout/style-place'], 0))
    view = {'width': 640, 'height': 480}
    label = lst.labels[0]
    bad_lists = {
        'finite': [
            dataclasses.replace(lst, labels=(dataclasses.replace(label, ax=math.nan), *lst.labels[1:])),
            dataclasses.replace(lst, labels=(dataclasses.replace(label, box=(0.0, 0.0, math.inf, 1.0)), *lst.labels[1:])),
            dataclasses.replace(lst, linears=(r4.Linear('s', 0, 0, math.inf, 1),)),
            dataclasses.replace(lst, polygons=(r4.Polygon('p', (0, 0, 1, math.nan)),)),
        ],
        'kind': [
            dataclasses.replace(lst, labels=(dataclasses.replace(label, place=r4.LabelPlace('curve')), *lst.labels[1:])),
        ],
        'malformed': [
            dataclasses.replace(lst, labels=(dataclasses.replace(label, place='point'), *lst.labels[1:])),
            dataclasses.replace(lst, points=(None,)),
        ],
    }
    for match, lists in bad_lists.items():
        for bad in lists:
            with pytest.raises(ValueError, match=match):
                r4.layout(bad, view)
    with pytest.raises(ValueError, match='finite'):
        r4.geometry_pairs(bad_lists['finite'][2])
    with pytest.raises(ValueError, match='finite'):
        r4.layout(lst, r4.LayoutView(640, math.nan))
    with pytest.raises(ValueError, match='finite'):
        r4.layout(lst, view, None, r4.Paint({'s': math.inf}))


def _malformed(change):
    lst = copy.deepcopy(_list(CLIENT['layout/style-place'], 0))
    args = {'list': lst, 'view': {'width': 640, 'height': 480}, 'memory': {}, 'paint': None}
    change(args)
    return args


@pytest.mark.parametrize(
    'change',
    [
        pytest.param(lambda a: a.update(memory={'A': {'k': math.inf, 'ax': 0, 'ay': 0}}), id='memory-k-inf'),
        pytest.param(lambda a: a.update(memory={'A': {'k': math.nan, 'ax': 0, 'ay': 0}}), id='memory-k-nan'),
        pytest.param(lambda a: a.update(memory={'A': {'k': 1, 'ax': 0}}), id='memory-without-ay'),
        pytest.param(lambda a: a.update(memory={'A': 3}), id='memory-entry-not-a-mapping'),
        pytest.param(lambda a: a.update(memory=[1]), id='memory-not-a-mapping'),
        pytest.param(lambda a: a['list']['labels'][0].pop('ax'), id='label-without-ax'),
        pytest.param(lambda a: a['list']['labels'][0].update(place='point'), id='place-a-string'),
        pytest.param(lambda a: a['list']['points'].append(7), id='point-not-a-mapping'),
        pytest.param(lambda a: a['view'].pop('width'), id='view-without-width'),
        pytest.param(lambda a: a.update(view=[640, 480]), id='view-a-list'),
        pytest.param(lambda a: a.update(list=[1, 2]), id='list-a-list'),
        pytest.param(lambda a: a.update(paint={'byId': {'A': 3}}), id='paint-entry-not-a-mapping'),
        pytest.param(lambda a: a.update(paint=[1]), id='paint-a-list'),
    ],
)
def test_malformed_input_is_a_value_error(change):
    args = _malformed(change)
    with pytest.raises(ValueError):
        r4.layout(args['list'], args['view'], args['memory'], args['paint'])


def test_no_labels():
    # Without labels the client returns at once: the memory is kept as it is.
    memory = {'A': {'k': 1, 'ax': 0, 'ay': 0}}
    assert r4.layout({'points': [{'id': 'A', 'x': 1, 'y': 2}]}, {'width': 10, 'height': 10}, memory) == (
        {},
        {'A': {'k': 1, 'ax': 0.0, 'ay': 0.0}},
        {'evaluated': 0, 'moved': 0},
    )


def test_import_without_manim():
    code = 'import sys, animageo.native.labels.r4; assert "manim" not in sys.modules'
    subprocess.run([sys.executable, '-c', code], check=True)


# ------------------------------------- regions (registry 1.9): only the stroke


def _region_list(**region):
    """A region of a line, an arc of a quarter circle (screen y down) and a graph
    as a chain: the ring (100,100) → (200,100) ↷ (100,200) → back by the chain."""
    entry = {'id': 'R', 'pieces': [
        {'kind': 'segment', 'x1': 100, 'y1': 100, 'x2': 200, 'y2': 100},
        {'kind': 'arc', 'cx': 100, 'cy': 100, 'r': 100, 'start': 0, 'sweep': math.pi / 2},
        {'kind': 'chain', 'pts': [100, 200, 90, 150, 100, 100]},
    ]}
    entry.update(region)
    return {'regions': [entry]}


def test_a_stroked_region_is_an_obstacle_by_its_pieces():
    """Lines as segments, arcs as arcs, graphs as chains, the pad of its stroke;
    its fill is not an obstacle."""
    paint = {'byId': {'R': {'strokeWidth': 2}}}
    obstacles = r4.geometry_obstacles(_region_list(), paint)
    assert [oid for oid, _hit in obstacles] == ['R'] * 4
    hits = [hit for _oid, hit in obstacles]
    assert hits[0]((140, 95, 160, 98))                     # 2 px above the line: the pad is 1 + 2/2
    assert not hits[0]((140, 90, 160, 97))
    a = math.pi / 4
    x, y = 100 + 100 * math.cos(a), 100 + 100 * math.sin(a)
    assert hits[1]((x - 1, y - 1, x + 1, y + 1))
    assert not hits[1]((95, 5, 105, 15))                   # the circle beyond the sweep
    assert hits[2]((92, 160, 98, 170)) and hits[3]((92, 120, 98, 130))
    assert not any(hit((130, 120, 150, 140)) for hit in hits)   # inside: the fill


def test_a_region_without_a_stroke_is_not_an_obstacle():
    assert r4.geometry_obstacles(_region_list(), {'byId': {'R': {'strokeWidth': 0}}}) == []
    assert [oid for oid, _ in r4.geometry_obstacles(_region_list())] == ['R'] * 4


def test_a_label_leaves_the_stroke_of_a_region():
    lst = _region_list()
    lst['points'] = [{'id': 'A', 'x': 150, 'y': 104}]
    lst['labels'] = [{'id': 'A', 'ax': 150, 'ay': 104, 'box': [150, 92, 160, 108], 'edge': [-1, 0],
                      'place': {'kind': 'point', 'reach': 4}}]
    paint = {'byId': {'R': {'strokeWidth': 2}}}
    placements, _memory, _stats = r4.layout(lst, {'width': 640, 'height': 480}, None, paint)
    laid = {**lst, 'labels': [{**lst['labels'][0], 'box': list(placements['A']['box'])}]}
    assert r4.geometry_pairs(lst, paint) == [('A', 'R')]
    assert r4.geometry_pairs(laid, paint) == []


def test_region_input_is_checked():
    assert r4.DisplayList.from_dict(_region_list()) == r4.DisplayList.from_dict(
        r4._list_dict(r4.DisplayList.from_dict(_region_list())))
    with pytest.raises(ValueError, match='kind'):
        r4.geometry_obstacles(_region_list(pieces=[{'kind': 'curve', 'pts': [0, 0, 1, 1]}]))
    with pytest.raises(ValueError, match='finite'):
        r4.geometry_obstacles(_region_list(pieces=[{'kind': 'segment', 'x1': 0, 'y1': 0, 'x2': math.inf, 'y2': 1}]))
    with pytest.raises(ValueError, match='malformed|expected'):
        r4.geometry_obstacles({'regions': [{'id': 'R', 'pieces': 3}]})
