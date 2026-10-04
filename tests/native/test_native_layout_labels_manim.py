"""``native.layout_labels`` against ``native.render`` and the classic pieces
it reuses (needs manim and LaTeX)."""
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import AnimaGeoScene, native  # noqa: E402
from animageo.export_layout import source_view_from_bounds_px, static_export_dict  # noqa: E402
from animageo.label_placement import LayoutInput, compute_label_layout  # noqa: E402
from tests.native.conftest import SCENES_DIR, read_json  # noqa: E402

PLACED = {'overlay': {'label_placement': {'enabled': True}}}
LAYOUTS = [
    None,
    {'content': {'source': 'rendered_bounds'}},
    {'content': {'source': 'rendered_bounds', 'label_bounds': 'exclude', 'padding': 20}},
    {'content': {'source': 'rendered_bounds', 'infinite_policy': 'clip'}},
    {'export': {'size': {'width': 1600, 'height': 900}, 'fit': 'contain'}},
    {'reference': {'size': {'width': 640}}, 'content': {'prominence': 1.5}},
]
SCENES = ['incircle_touch_chain', 'a3_chain', 'marks_right_angle', 'angle_points', 'line_circle_order']


def scene_doc(name):
    return read_json(SCENES_DIR / f'{name}.json')['document']


def label_boxes(report):
    return {k: v['label']['box'] for k, v in report['elements'].items() if v['label']}


@pytest.mark.parametrize('name', SCENES)
@pytest.mark.parametrize('style', [None, PLACED], ids=['plain', 'placed'])
def test_boxes_match_the_render(tmp_path, name, style):
    doc = scene_doc(name)
    for layout in LAYOUTS:
        report = native.render(doc, style_config=style, export_layout=layout, out=tmp_path / 'a.svg').report
        boxes = label_boxes(report)
        for backend in ('metrics', 'tex'):
            out = native.layout_labels(doc, style_config=style, export_layout=layout, backend=backend)
            assert sorted(out) == sorted(boxes), (layout, backend)
            for el_id, box in boxes.items():
                assert out[el_id]['box'] == pytest.approx(box, abs=0.01), (layout, backend, el_id)
            pairs = sorted([a, b] for a in out for b in out[a]['overlaps'] if a < b)
            assert pairs == report['overlaps'], (layout, backend)
            points = sorted([a, b] for a in out for b in out[a]['pointOverlaps'])
            assert points == report['pointOverlaps'], (layout, backend)


def test_pinned_suggestions_render_where_suggested(tmp_path):
    doc = scene_doc('a3_chain')
    suggested = native.layout_labels(doc, place=True)
    doc['appearance'] = {el_id: {'label': {'mode': 'name', 'offsetWorld': e['offsetWorld']},
                                 'overrides': {'label_anchor': e['anchor']}}
                         for el_id, e in suggested.items()}
    report = native.render(doc, out=tmp_path / 'p.svg').report
    for el_id, box in label_boxes(report).items():
        assert box == pytest.approx(suggested[el_id]['box'], abs=0.01), el_id


def test_layout_input_of_a_scene_places_as_the_scene():
    scene = AnimaGeoScene()
    scene.loadDocument(scene_doc('incircle_touch_chain'), style=PLACED)
    cfg = dict(scene.style_config.overlay.label_placement)
    direct = compute_label_layout(scene, cfg=cfg)
    via_input = compute_label_layout(LayoutInput.from_scene(scene), cfg=cfg)
    assert direct.keys() == via_input.keys() and direct
    for name, placement in direct.items():
        other = via_input[name]
        assert placement.label_anchor == other.label_anchor
        assert placement.offset_ggb == pytest.approx(other.offset_ggb)


@pytest.mark.parametrize('layout', [
    {},
    {'export': {'size': {'width': 1200}}},
    {'reference': {'size': {'width': 400, 'height': 400}}, 'export': {'size': {'width': 800, 'height': 600}}},
    {'content': {'padding': 30, 'prominence': 2.0}},
    {'content': {'decoration_scale_source': 'output'}, 'export': {'size': {'width': 1600}}},
    {'content': {'decoration_scale_source': 'ggb'}, 'export': {'size': {'width': 400}}},
    {'content': {'source': 'rendered_bounds', 'bounds': [100, 50, 500, 450]}},
])
def test_static_export_dict_is_the_scene_export(layout):
    doc = scene_doc('a3_chain')
    scene = AnimaGeoScene()
    scene.loadDocument(doc, reference=layout.get('reference'), content=layout.get('content'),
                       export=layout.get('export'))
    view = native.source_view(doc)
    view['ptUnit_ggb'] = view['ptUnit']
    content = layout.get('content') or {}
    rendered = (source_view_from_bounds_px(view, content['bounds']) if 'bounds' in content else None)
    static = static_export_dict(view, style_reference=scene.style_config.reference,
                                reference=layout.get('reference'), content=layout.get('content'),
                                export=layout.get('export'), rendered_view=rendered)
    assert sorted(static) == sorted(scene.style.export)
    for key, value in scene.style.export.items():
        if isinstance(value, float):
            assert static[key] == pytest.approx(value), key
        else:
            assert static[key] == value, key
