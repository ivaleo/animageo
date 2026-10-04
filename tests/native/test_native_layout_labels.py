"""``native.layout_labels``: label boxes of a document without manim (spec §9.3)."""
import importlib.util
import json
import math
import time

import pytest

from animageo import native
from animageo.label_placement import DEFAULT_CONFIG, _estimate_label_bbox
from animageo.labels import correctedLabel
from animageo.native.labels import tex
from animageo.native.labels.layout import frame_bounds, measure_metrics
from tests.native.conftest import SCENES_DIR, DocBuilder, point_input, read_json

BOUNDS = (-6, -4, 6, 4)
PLACED = {'overlay': {'label_placement': {'enabled': True}}}
KEYS = ['text', 'anchor', 'point', 'offsetPx', 'offsetWorld', 'box', 'leader', 'overlaps', 'pointOverlaps',
        'placed', 'locked']
CORNERS = ['TL', 'TC', 'TR', 'ML', 'MR', 'BL', 'BC', 'BR']


def builder(doc_id, bounds=BOUNDS):
    return DocBuilder(doc_id, registry_version='1.3', bounds=bounds)


def demo():
    b = builder('labels_demo')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3).free('F', 2, 2)
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'a'), (2, 'b'), (3, 'c')])
    b.midpoint('M', 'A', 'B').circle('k', 'M', 'C').angle('g', 'B', 'A', 'C')
    b.circle('z', 'F', 'F')                                   # zero radius: undefined
    b.equal_segments('e', 'a', 'b')
    b.doc['appearance'] = {'M': {'visible': False},
                           'a': {'label': {'mode': 'name'}},
                           'g': {'label': {'mode': 'value'}},
                           'z': {'label': {'mode': 'name'}},     # never drawn
                           'e': {'label': {'mode': 'name'}}}     # an equality mark has no drawing
    return b.doc


def dist_to_box(px, py, box):
    x0, y0, x1, y1 = box
    return math.hypot(px - min(max(px, x0), x1), py - min(max(py, y0), y1))


def test_entries_of_drawn_labels():
    out = native.layout_labels(demo())
    assert sorted(out) == ['A', 'B', 'C', 'F', 'a', 'g']
    for entry in out.values():
        assert list(entry) == KEYS
        x0, y0, x1, y1 = entry['box']
        assert x0 < x1 and y0 < y1
        assert entry['placed'] is False and entry['locked'] is False and entry['leader'] is None
    assert out['A']['text'] == '$A$' and out['a']['text'] == '$a$'
    assert out['g']['text'].endswith(r'^{\circ}$')
    # the built-in style draws a label from its bottom-left corner (GeoStyle.rendering has no anchor)
    assert out['A']['anchor'] == 'BL'
    # source view 800 px wide over 12 units: A at (-4, -2)
    assert out['A']['point'] == pytest.approx([400 - 4 * 800 / 12, 4 * 800 / 12 + 2 * 800 / 12], abs=1e-3)
    assert json.loads(json.dumps(out)) == out
    assert native.layout_labels(demo()) == out


def test_point_label_clears_its_marker():
    b = builder('clear')
    b.free('A', 0, 0)
    for anchor in CORNERS:
        b.doc['appearance'] = {'A': {'overrides': {'label_anchor': anchor, 'size_px': 8}}}
        entry = native.layout_labels(b.doc)['A']
        assert entry['anchor'] == anchor
        # 1 px of the source view per px of the output here; radius 4 + point_gap_px
        reach = 4 + DEFAULT_CONFIG['point_gap_px']
        assert dist_to_box(*entry['point'], entry['box']) == pytest.approx(reach, abs=1e-3), anchor
        assert entry['pointOverlaps'] == []
    b.doc['appearance'] = {'A': {'overrides': {'label_anchor': 'MC'}}}
    centred = native.layout_labels(b.doc)['A']
    assert centred['anchor'] == 'MC' and centred['pointOverlaps'] == ['A']


def test_point_label_clearance_keeps_explicit_offsets():
    b = builder('keep')
    b.free('A', 0, 0)
    b.doc['appearance'] = {'A': {'label': {'mode': 'name', 'offsetWorld': [0.0, 0.0]},
                                 'overrides': {'label_anchor': 'MC'}}}
    entry = native.layout_labels(b.doc)['A']
    assert entry['locked'] is True and entry['offsetWorld'] == [0.0, 0.0]
    assert entry['pointOverlaps'] == ['A']
    # a style offset of the type wins as well
    style = {'overlay': {'per_type': {'point': {'label_offset_px': [0.0, 0.0]}}}}
    assert native.layout_labels({**b.doc, 'appearance': {}}, style_config=style)['A']['pointOverlaps'] == ['A']


def test_overlaps_of_labels_and_points():
    b = builder('crowd')
    b.free('A', 0, 0).free('B', 0.05, 0).free('C', 0.15, 0.15).free('D', 3, 0)
    out = native.layout_labels(b.doc)
    assert 'B' in out['A']['overlaps'] and 'A' in out['B']['overlaps']
    assert 'C' in out['A']['pointOverlaps']                    # A's label covers the point C
    assert out['D']['overlaps'] == [] and out['D']['pointOverlaps'] == []


def test_place_follows_the_style_or_is_forced():
    doc = read_json(SCENES_DIR / 'a3_chain.json')['document']
    plain = native.layout_labels(doc)
    assert not any(e['placed'] for e in plain.values())
    placed = native.layout_labels(doc, style_config=PLACED)
    assert all(e['placed'] for e in placed.values())
    assert native.layout_labels(doc, place=True) == placed
    assert native.layout_labels(doc, style_config=PLACED, place=False) == plain


def test_pinning_the_layout_reproduces_it():
    doc = demo()
    doc['appearance']['T'] = {'label': {'mode': 'name'}}
    placed = native.layout_labels(doc, place=True)
    pinned = json.loads(json.dumps(doc))
    for el_id, entry in placed.items():
        record = pinned['appearance'].setdefault(el_id, {})
        record.setdefault('label', {})['offsetWorld'] = entry['offsetWorld']
        record.setdefault('overrides', {})['label_anchor'] = entry['anchor']
    again = native.layout_labels(pinned, place=True)
    assert sorted(again) == sorted(placed)
    for el_id, entry in again.items():
        assert entry['locked'] is True and entry['placed'] is False
        assert entry['box'] == pytest.approx(placed[el_id]['box'], abs=2e-3), el_id
        assert entry['anchor'] == placed[el_id]['anchor']


def test_export_layout_scales_the_boxes():
    doc = demo()
    base = native.layout_labels(doc, place=True)
    double = native.layout_labels(doc, place=True, export_layout={'export': {'size': {'width': 1600}}})
    for el_id, entry in base.items():
        (x0, y0, x1, y1), other = entry['box'], double[el_id]['box']
        # the geometry doubles; decorations follow the reference (prominence 1)
        assert other[0] + other[2] == pytest.approx(2 * (x0 + x1), abs=0.05), el_id
        assert other[1] + other[3] == pytest.approx(2 * (y0 + y1), abs=0.05), el_id


def test_rendered_bounds_keeps_the_labels_on_the_canvas():
    doc = read_json(SCENES_DIR / 'incircle_touch_chain.json')['document']
    out = native.layout_labels(doc, place=True, export_layout={'content': {'source': 'rendered_bounds'}})
    xs = [v for e in out.values() for v in (e['box'][0], e['box'][2])]
    ys = [v for e in out.values() for v in (e['box'][1], e['box'][3])]
    # the reference is the 800 px source width; the crop reserves the label boxes
    assert min(xs) >= -1e-3 and min(ys) >= -1e-3
    assert max(xs) == pytest.approx(800, abs=1e-3) or max(ys) == pytest.approx(800, abs=1e-3)


def test_inputs_and_evaluated():
    b = builder('moved')
    b.free('A', 0, 0)
    moved = native.layout_labels(b.doc, inputs={'A': point_input(1, 0)})
    assert moved['A']['point'][0] == pytest.approx(400 + 800 / 12, abs=1e-3)
    ev = native.evaluate(b.doc, inputs={'A': point_input(1, 0)})
    assert native.layout_labels(b.doc, ev, inputs={'A': point_input(1, 0)}) == moved


def test_errors():
    doc = demo()
    with pytest.raises(ValueError, match='backend'):
        native.layout_labels(doc, backend='pango')
    with pytest.raises(ValueError, match='unknown keys'):
        native.layout_labels(doc, export_layout={'frame': {}})
    with pytest.raises(ValueError):
        native.layout_labels(doc, inputs={'nope': point_input(0, 0)})


@pytest.mark.skipif(importlib.util.find_spec('manim') is not None, reason='manim is installed')
def test_tex_backend_needs_manim():
    with pytest.raises(RuntimeError, match='manim'):
        native.layout_labels(demo(), backend='tex')


def test_metrics_measurer():
    assert measure_metrics('$A$', 20.0) == tex.measure(correctedLabel('$A$'), 20.0)
    # TeX outside the subset: the classic estimate
    assert measure_metrics(r'$\frac{a}{b}$', 20.0) == _estimate_label_bbox(r'$\frac{a}{b}$', 20.0)


def test_frame_bounds():
    # wider than 16:9 — the frame spans the width and is centred vertically
    left, bottom, right, top = frame_bounds({'ptUnit': 100, 'ptWidth': 1600, 'ptHeight': 600,
                                             'ptXZero': 800, 'ptYZero': 300})
    assert (left, right) == (-8, 8)
    assert (bottom + top) / 2 == pytest.approx(0) and top - bottom == pytest.approx(9)
    # taller — the frame spans the height from the top and is centred horizontally
    left, bottom, right, top = frame_bounds({'ptUnit': 100, 'ptWidth': 600, 'ptHeight': 900,
                                             'ptXZero': 300, 'ptYZero': 900})
    assert (bottom, top) == (0, 9) and (left + right) / 2 == pytest.approx(0)
    assert right - left == pytest.approx(16)


@pytest.mark.slow
def test_hundred_labels_within_100_ms():
    import random
    rng = random.Random(7)
    b = DocBuilder('hundred', registry_version='1.3', bounds=(-10, -10, 10, 10))
    for i in range(100):
        b.free(f'P{i}', rng.uniform(-9, 9), rng.uniform(-9, 9))
    native.layout_labels(b.doc)                                # metrics and style loaded once
    best = {}
    for place in (False, True):
        times = []
        for _ in range(5):
            start = time.perf_counter()
            out = native.layout_labels(b.doc, place=place)
            times.append(time.perf_counter() - start)
        assert len(out) == 100
        best[place] = min(times)
    assert best[False] <= 0.1 and best[True] <= 0.1, best
