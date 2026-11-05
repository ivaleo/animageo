"""The renderer, TikZ and JSXGraph draw the visible part of a line or a ray
(1.12.0, ``native.line_display``): the part ``resolve_paint`` reports as
``stroke.visibleWorld``, clipped by the frame, within 0.01 px; its dashes
start at its start; without the keys every output is that of the frame."""
import json

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo.native import line_display as ld  # noqa: E402
from animageo.native import paint_fixtures  # noqa: E402
from animageo.native.paint import resolve_paint  # noqa: E402
from tests.native.test_native_line_display import H, on_line  # noqa: E402

PX = 0.01       # the tolerance of render ↔ paint, output pixels


def _scene(doc, style=None):
    from animageo.animageo import AnimaGeoScene
    scene = AnimaGeoScene()
    scene.loadDocument(doc, style=style)
    return scene


def _names(doc):
    from animageo.native.kernel.bridge import build_construction
    return build_construction(doc)[1].by_id


@pytest.mark.parametrize('case', paint_fixtures._rows(paint_fixtures._lines()), ids=lambda c: c['name'])
def test_the_renderer_draws_the_visible_part(case):
    scene = _scene(case['document'], case['style'])
    names = _names(case['document'])
    frame = tuple(scene._get_scene_bounds())
    tol = PX / case['expect']['ptUnit']
    for el_id, entry in case['expect']['elements'].items():
        world = (entry.get('stroke') or {}).get('visibleWorld')
        if world is None:
            continue
        group = scene.mobject(names[el_id])
        stroke = group.submobjects[0]
        start, end = stroke.get_start()[:2], stroke.get_end()[:2]
        drawn = ld.clip_segment(world, frame)
        assert np.allclose(start, drawn[0], rtol=0, atol=tol), (case['name'], el_id)
        assert np.allclose(end, drawn[1], rtol=0, atol=tol), (case['name'], el_id)


def test_a_clipped_dashed_part_keeps_its_phase():
    from animageo.dash import get_dash
    d = on_line(c=-5).overrides('l', line_display='incident', stroke_dash_ratio=0.5)   # C at x = −10
    scene = _scene(d.doc)
    stroke = scene.mobject(_names(d.doc)['l']).submobjects[0]
    left = scene._get_scene_bounds()[0]
    assert stroke.get_start()[0] == pytest.approx(left)
    pattern = get_dash(stroke)
    period = pattern.on + pattern.off
    assert pattern.offset == pytest.approx((left - (-10 - H)) % period)


def test_a_part_outside_the_frame_is_not_drawn():
    d = _scene_doc_outside()
    scene = _scene(d.doc)
    assert scene.mobject(_names(d.doc)['l']) is None or not scene.mobject(_names(d.doc)['l']).submobjects


def _scene_doc_outside():
    from animageo.native.paint_fixtures import _Doc
    d = _Doc('t').free('A', 20, 20).free('B', 22, 20).line('l', 'A', 'B').free('P', 1, 1)
    return d.overrides('l', line_display='incident')


def test_tikz_draws_the_clipped_part():
    from animageo.exporters.tikz.document import fmt_num
    from animageo.exporters.tikz.options import TikZOptions
    d = on_line().overrides('l', line_display='incident').line('k', 'A', 'C')
    tex = _scene(d.doc).exportTikZ()
    p = TikZOptions().coordinate_precision
    (x0, y0), (x1, y1) = resolve_paint(d.doc)['elements']['l']['stroke']['visibleWorld']
    want = f'({fmt_num(x0, p)},{fmt_num(y0, p)}) -- ({fmt_num(x1, p)},{fmt_num(y1, p)})'
    assert sum(want in line for line in tex.splitlines()) == 1


def test_jsxgraph_draws_a_static_segment():
    from animageo.exporters.jsxgraph.spec import load_schema
    d = on_line().overrides('l', line_display='incident').line('k', 'A', 'C')
    spec = json.loads(_scene(d.doc).exportJSXGraph(output='spec'))
    by_name = {e['name']: e for e in spec['elements']}
    world = resolve_paint(d.doc)['elements']['l']['stroke']['visibleWorld']
    line, frame_line = by_name['e_l'], by_name['e_k']
    assert line['engine'] == 'segment' and np.allclose(line['parents'], world, rtol=0, atol=1e-4)
    assert 'visible part as a static segment' in line['detail']
    assert frame_line['engine'] == 'line' and 'visible part' not in frame_line['detail']
    jsonschema = pytest.importorskip('jsonschema')
    jsonschema.validate(spec, load_schema())


def test_without_the_keys_every_output_is_that_of_the_frame():
    """``line_display: frame`` written out draws what no key draws: the SVG
    and the TikZ byte for byte (a line, a ray, a dashed ray, labels)."""
    import os
    import tempfile
    d = on_line().ray('r', 'B', 'C').overrides('r', stroke_dash_ratio=0.5).label('l')
    framed = json.loads(json.dumps(d.doc))
    for el_id in ('l', 'r'):
        framed['appearance'].setdefault(el_id, {}).setdefault('overrides', {}).update(line_display='frame',
                                                                                     line_overhang_px=40)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, doc in enumerate((d.doc, framed)):
            scene = _scene(doc)
            path = os.path.join(tmp, f'{i}.svg')
            scene.exportSVG(path)
            with open(path, 'rb') as fh:
                out.append((fh.read(), scene.exportTikZ()))
    assert out[0] == out[1]
