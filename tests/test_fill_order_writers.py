"""Compare emitted runs, rather than numeric layer attributes, across writers."""
import json
from pathlib import Path

import pytest

from tests.native.test_native_paint_manim import _load

_FIXTURE = Path(__file__).parents[1] / 'animageo/native/parity/v1/paint/paint_fill_order.json'
_CASES = [case for case in json.loads(_FIXTURE.read_text())['cases'] if not case['name'].endswith('_construction')]


def tikz_parts(scene):
    return [json.loads(line[8:]) for line in map(str.strip, scene.exportTikZ().splitlines()) if line.startswith('% paint ')]


@pytest.mark.parametrize('case', _CASES, ids=lambda c: c['name'])
def test_area_writers_emit_the_shared_snapshot_plan(case):
    scene = _load(case)
    expected = case['expect']
    tikz = tikz_parts(scene)
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    plan = spec['paintOrder']
    jsx = [{k: ref[k] for k in ('id', 'part')} for ref in plan['partOrder']]
    assert [ref['id'] for ref in tikz if ref['part'] == 'fill'] == expected['fillOrder']
    assert plan['fillOrder'] == expected['fillOrder']
    assert tikz == expected['partOrder']
    assert jsx == expected['partOrder']


def test_full_and_zero_native_arcs_keep_export_domain_distinct():
    import math
    from animageo import AnimaGeoScene
    from animageo.geo.construction import Element
    from animageo.native.kernel.bridge import to_classic
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    arc = to_classic('arc', {'c': [0, 0], 'r': 2, 'a0': 0, 'a1': math.tau})
    elem = Element('full', arc)
    elem.style.update(fill='#ff0000', label_visible=False)
    scene.geo.add(elem)
    assert {'id': 'full', 'part': 'fill'} in tikz_parts(scene)
    assert 'arc (0:360:2)' in scene.exportTikZ()
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    assert spec['paintOrder']['fillOrder'] == ['full']
    stroke = next(e for e in spec['elements'] if e.get('name') == 'full')
    assert max(stroke['parents'][0]) - min(stroke['parents'][0]) == pytest.approx(4)
    arc.angles = [0, 0]
    assert {'id': 'full', 'part': 'fill'} not in tikz_parts(scene)
    assert json.loads(scene.exportJSXGraph(output='spec'))['paintOrder']['fillOrder'] == []


def test_circle_label_can_sit_below_a_fixed_fill_in_both_writers():
    from animageo import AnimaGeoScene
    from tests.test_fill_order_defaults import nested_document
    doc = nested_document()
    doc['appearance']['outer']['label'] = {'mode': 'name'}
    doc['appearance']['outer']['overrides'].update(z_index_label=-1, z_index_fill=100)
    s = AnimaGeoScene()
    s.loadDocument(doc)
    for refs in (tikz_parts(s), json.loads(s.exportJSXGraph(output='spec'))['paintOrder']['partOrder']):
        refs = [{k: r[k] for k in ('id', 'part')} for r in refs]
        assert refs.index({'id': 'outer', 'part': 'label'}) < refs.index({'id': 'outer', 'part': 'fill'})


@pytest.mark.parametrize('name', ['rotated_ellipse_37', 'sector_and_circle_segment_270',
                                  'right_angle_square', 'multiple_angle_arcs',
                                  'fill_order_region_annulus_fill_tool', 'fill_order_region_dots'])
def test_area_tikz_domains_compile(name, tmp_path):
    import shutil
    import subprocess
    if shutil.which('pdflatex') is None:
        pytest.skip('pdflatex not installed')
    case = next(c for c in _CASES if c['name'] == name)
    import copy
    case = copy.deepcopy(case)
    if not name.startswith('fill_order_region'):
        case['document']['viewDefaults']['bounds'] = [-3,-3,3,3]
    colors = {'conic': '#00a080', 'circle': '#c0dcff', 'sector': '#ff9966',
              'circlesegment': '#4488dd', 'arc': '#66bb66'}
    for id, element in case['document']['elements'].items():
        if element['type'] in colors:
            case['document']['appearance'].setdefault(id, {}).setdefault('overrides', {}).update(
                fill=colors[element['type']], fill_opacity=.7)
    scene = _load(case)
    scene.exportTikZ(str(tmp_path / 'frame.tex'), standalone=True)
    result = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'frame.tex'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout[-2000:]
    assert (tmp_path / 'frame.pdf').is_file()


def test_tikz_real_overlap_pixel_and_explicit_layer(tmp_path):
    import shutil
    import subprocess
    from PIL import Image
    from tests.test_jsxgraph_fill_order import fill_order_board
    if not shutil.which('pdflatex') or not shutil.which('pdftoppm'):
        pytest.skip('LaTeX/Poppler not installed')
    s = fill_order_board()
    # Remove glyphs so a pixel in the overlap measures the actual fills.
    for e in s.geo.elements:
        if type(e.data).__name__ == 'Point':
            e.style.update(visible=False)
        else:
            e.style.update(stroke_opacity=0, label_visible=False)
    for fixed, expected in ((False, (255,0,0)), (True, (0,0,255))):
        if fixed:
            s.geo.element('outer').style.z_index_fill = 100
        s.exportTikZ(str(tmp_path / 'pixel.tex'), standalone=True, frame='export')
        p = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'pixel.tex'],
                           cwd=tmp_path, capture_output=True, text=True, timeout=40)
        assert p.returncode == 0, p.stdout[-2000:]
        p = subprocess.run(['pdftoppm', '-scale-to-x', '600', '-scale-to-y', '400', '-singlefile', '-png',
                            'pixel.pdf', 'pixel'], cwd=tmp_path, capture_output=True, text=True, timeout=40)
        assert p.returncode == 0, p.stderr
        im = Image.open(tmp_path / 'pixel.png').convert('RGB')
        assert im.getpixel((300,200)) == expected


def test_leader_keeps_its_depth_below_an_intermediate_fixed_fill():
    from tests.test_fill_order_defaults import classic_scene
    s = classic_scene({'rendering': {'fill_order': 'area'}})
    s.geo.element('inner').style.update(label_visible=True, z_index_label=50,
                                       _leader=((0, 1), (0, 0)))
    s.geo.element('outer').style.z_index_fill = 49.5
    for refs in (tikz_parts(s), json.loads(s.exportJSXGraph(output='spec'))['paintOrder']['partOrder']):
        refs = [{k: r[k] for k in ('id', 'part')} for r in refs]
        assert refs.index({'id': 'inner', 'part': 'leader'}) < refs.index({'id': 'outer', 'part': 'fill'}) < refs.index({'id': 'inner', 'part': 'label'})
