"""Respecting current positions is inert when no label has an authored place."""
import pytest

from animageo import native
from tests.native.conftest import DocBuilder
from tests.native.test_native_layout_labels import RESPECTING


@pytest.fixture(params=['median', 'midpoints_and_intersection'])
def unplaced_document(request):
    b = DocBuilder(request.param, registry_version='1.3', bounds=(-6, -5, 10, 7))
    b.free('A', -4, -3).free('B', 7, -3).free('C', -3, 6)
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'a'), (2, 'b'), (3, 'c')])
    b.midpoint('M', 'A', 'C').segment('m', 'B', 'M')
    if request.param == 'midpoints_and_intersection':
        b.midpoint('N', 'A', 'B')
        b.line('u', 'B', 'M').line('v', 'C', 'N').intersect('X', 'u', 'v')
    # Explicit names, with no offset, hint or lock on any label.
    b.doc['appearance'] = {
        name: {'label': {'mode': 'name' if elem['type'] == 'point' else 'none'}}
        for name, elem in b.doc['elements'].items()
    }
    return b.doc


def placement_style(respect, cfg):
    return {
        # This size makes the final clearance sweep move M in the median scene.
        'defaults': {'point': {'font_size_px': 18}},
        'overlay': {'label_placement': dict(cfg, respect_current_position=respect)},
    }


@pytest.mark.parametrize('cfg', [{'enabled': True}, RESPECTING], ids=['default', 'preset'])
@pytest.mark.parametrize('canonicalize', [False, True])
def test_unplaced_labels_have_identical_layout(unplaced_document, cfg, canonicalize):
    cfg = dict(cfg, canonicalize_anchor=canonicalize)
    layouts = [native.layout_labels(unplaced_document, style_config=placement_style(respect, cfg))
               for respect in (False, True)]
    expected_names = {name for name, elem in unplaced_document['elements'].items()
                      if elem['type'] == 'point'}
    assert layouts[0].keys() == layouts[1].keys() == expected_names
    for name in expected_names:
        a, b = layouts[0][name], layouts[1][name]
        assert a['placed'] and b['placed']
        assert a['anchor'] == b['anchor'], name
        # Exact equality, including box centres and world offsets.
        assert a == b, name


@pytest.mark.manim
@pytest.mark.parametrize('content', [None, {'source': 'rendered_bounds', 'padding': 40}],
                         ids=['source-view', 'rendered-bounds'])
def test_unplaced_labels_render_identically(unplaced_document, tmp_path, content):
    pytest.importorskip('manim')
    labels = []
    for respect in (False, True):
        result = native.render(
            unplaced_document, style_config=placement_style(respect, RESPECTING),
            export_layout={'content': content} if content else None,
            fmt='svg', out=tmp_path / f'{respect}.svg')
        labels.append({name: entry['label'] for name, entry in result.report['elements'].items()
                       if entry['label'] is not None})
    assert labels[0] and labels[0] == labels[1]


@pytest.mark.manim
def test_unplaced_labels_match_in_classic_auto_place(unplaced_document):
    pytest.importorskip('manim')
    from animageo import AnimaGeoScene

    layouts = []
    for respect in (False, True):
        scene = AnimaGeoScene()
        cfg = dict(RESPECTING, enabled=False)
        scene.loadDocument(unplaced_document, style=placement_style(respect, cfg))
        scene.style_config.overlay.label_placement['enabled'] = True
        # These raw offsets and anchors determine the exact visual centres;
        # compare before render-report rounding, including a second solve.
        for _ in range(2):
            scene.autoPlaceLabels()
            layouts.append({elem.name: (tuple(elem.style['label_offset_px']), elem.style['label_anchor'])
                            for elem in scene.geo.elements if elem.style.get('_auto_placed')})
    assert layouts[0]
    assert all(layout == layouts[0] for layout in layouts[1:])
