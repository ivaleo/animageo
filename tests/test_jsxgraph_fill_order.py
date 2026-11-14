"""Export-frame fill order is shared by standalone boards and the runtime."""
import json

import pytest

from tests.test_fill_order_defaults import classic_scene, nested_document
from animageo import AnimaGeoScene, native
from animageo.exporters.jsxgraph.spec import load_schema


def test_area_exports_snapshot_order_and_separate_fill_geometry():
    scene = classic_scene({'rendering': {'fill_order': 'area'}})
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    plan = spec['paintOrder']
    assert plan['mode'] == 'area' and plan['static'] is True
    assert plan['fillOrder'] == ['outer', 'inner']
    assert [p['id'] for p in plan['partOrder'] if p['part'] == 'fill'] == plan['fillOrder']
    elements = {e.get('name'): e for e in spec['elements']}
    for ref in plan['partOrder']:
        assert ref['targets']
        for target in ref['targets']:
            assert target['name'] in elements
    assert elements['outer']['attrs']['fillOpacity'] == 0
    fill = next(p for p in plan['partOrder'] if p['id'] == 'outer' and p['part'] == 'fill')
    assert elements[fill['targets'][0]['name']]['attrs']['fillOpacity'] == 1
    for output in ('html', 'js'):
        text = scene.exportJSXGraph(output=output)
        assert 'paintOrder' in text and 'appendChild' in text
    pytest.importorskip('jsonschema').validate(spec, load_schema())


def test_classic_without_flag_has_no_new_metadata():
    spec = json.loads(classic_scene().exportJSXGraph(output='spec'))
    assert 'paintOrder' not in spec


def test_native_export_recomputes_order_for_current_inputs():
    doc = nested_document()
    scene = AnimaGeoScene()
    scene.loadDocument(doc)
    first = json.loads(scene.exportJSXGraph(output='spec'))['paintOrder']
    scene.loadDocument(doc, inputs={'R': {'kind': 'point', 'value': [.1, 0]}})
    second = json.loads(scene.exportJSXGraph(output='spec'))['paintOrder']
    assert first['fillOrder'] == native.resolve_paint(doc)['fillOrder']
    assert second['fillOrder'] == native.resolve_paint(doc, inputs={'R': {'kind': 'point', 'value': [.1, 0]}})['fillOrder']
    assert first['fillOrder'] == list(reversed(second['fillOrder']))


def fill_order_board():
    """Live classic geometry with the same canonical owners as paint parity."""
    from animageo.geo.construction import Element
    from animageo.geo.lib_elements import Point
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('A=Point(-.5,-.5)\nB=Point(.5,-.5)\nC=Point(0,.5)\nO=Point(0,0)')
    # A point added without a defining command is a normal free board input,
    # as with GGB's free points. Derived creators keep their live references.
    scene.geo.add(Element('R', Point([3, 0])))
    scene.putCode('inner=Polygon(A,B,C)\nouter=Circle(O,R)')
    scene.geo.element('inner').style.update(fill='#ff0000', fill_opacity=1)
    scene.geo.element('outer').style.update(fill='#0000ff', fill_opacity=1)
    for name in ('A', 'B', 'C', 'O', 'R'):
        scene.geo.element(name).style.label_visible = True
    scene.style.export.update(ptWidth=600, ptHeight=400, ptUnit=50, ptUnit_style=50,
                              ptUnit_ggb=50, ptXZero=300, ptYZero=200)
    scene._set_camera_from_export(scene.style.export)
    scene.updateAllGeometry()
    return scene


def test_committed_board_matches_export_and_paint_expected_paint():
    from pathlib import Path
    root = Path(__file__).parents[1]
    fixture = json.loads((root / 'web/runtime/test/fixtures/fill_order.board.json').read_text())
    assert fixture == json.loads(fill_order_board().exportJSXGraph(output='spec'))
    paint = json.loads((root / 'animageo/native/parity/v1/paint/paint_fill_order.json').read_text())
    expected_paint = next(c['expect'] for c in paint['cases'] if c['name'] == 'nested_circle_and_polygon')
    assert fixture['paintOrder']['fillOrder'] == expected_paint['fillOrder']
    assert [{k: r[k] for k in ('id', 'part')} for r in fixture['paintOrder']['partOrder']] == expected_paint['partOrder']


def test_static_angle_label_is_a_real_render_target():
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('O=Point(0,0)\nA=Point(2,0)\nB=Point(0,2)\na=Angle(A,O,B)')
    scene.geo.element('a').style.update(fill='#00ff00', label_visible=True)
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    label = next(r for r in spec['paintOrder']['partOrder'] if r['id'] == 'a' and r['part'] == 'label')
    by_name = {e.get('name'): e for e in spec['elements']}
    target = label['targets'][0]
    el = by_name[target['name']]
    assert (el.get('engine') == 'text' and target['node'] == 'self') or el.get('attrs', {}).get('withLabel') is True


def test_named_polygon_edges_keep_independent_render_nodes_in_area_mode():
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('A=Point(0,0)\nB=Point(2,0)\nC=Point(0,2)\np,AB,BC,CA=Polygon(A,B,C)')
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    by_name = {e.get('name'): e for e in spec['elements']}
    for edge in ('AB', 'BC', 'CA'):
        assert by_name[edge].get('engine') == 'segment'
        assert by_name[edge].get('form', 'create') == 'create'


def test_standalone_js_and_spec_apply_the_same_nodes(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which('node'):
        pytest.skip('node not installed')
    root = Path(__file__).parents[1]
    scene = fill_order_board()
    (tmp_path / 'board.js').write_text(scene.exportJSXGraph(output='js'))
    (tmp_path / 'board.json').write_text(scene.exportJSXGraph(output='spec'))
    script = r'''
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const root=process.argv[1], temp=process.argv[2];
const { domEngine } = await import(pathToFileURL(root+'/web/runtime/test/paint-engine.js'));
const { createBoard } = await import(pathToFileURL(root+'/web/runtime/src/index.js'));
const spec=JSON.parse(fs.readFileSync(temp+'/board.json'));
const runtime=createBoard(spec,{}, {engine:domEngine()});
const context={JXG:domEngine(),window:{}};
vm.runInNewContext(fs.readFileSync(temp+'/board.js','utf8'),context);
const nodes=(board,S)=>spec.paintOrder.partOrder.flatMap(ref=>ref.targets.flatMap(t=> {
 const o=S[t.name]; const parts=t.node==='borders'?o.borders:[t.node==='label'?o.label:o];
 return parts.map(p=>{assert.ok(p.rendNode);return p.rendNode;});
}));
for(const [board,S] of [[runtime.board,runtime.S],[context.window.agboard,context.window.agS]]) {
 const expected=nodes(board,S), set=new Set(expected);
 assert.deepEqual(board.nodes.filter(n=>set.has(n)),expected);
 for(const ref of spec.paintOrder.partOrder) for(const t of ref.targets)
   if(t.fillRule) assert.equal(S[t.name].rendNode.getAttribute('fill-rule'),t.fillRule);
}
'''
    result = subprocess.run(['node', '--input-type=module', '-e', script, str(root), str(tmp_path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_hidden_fitted_marker_keeps_its_label():
    from pathlib import Path
    from tests.native.test_native_paint_manim import _load
    fixture = json.loads((Path(__file__).parents[1] / 'animageo/native/parity/v1/paint/paint_angle_fit.json').read_text())
    case = next(c for c in fixture['cases'] if c['name'] == 'fit_hidden')
    case['document']['appearance'].setdefault('alpha', {})['label'] = {'mode': 'name'}
    scene = _load(case)
    plan = json.loads(scene.exportJSXGraph(output='spec'))['paintOrder']
    assert 'alpha' not in plan['fillOrder']
    assert [r['part'] for r in plan['partOrder'] if r['id'] == 'alpha'] == ['label']


def test_fill_order_board_exports_a_free_radius_input():
    from animageo.geo.lib_elements import Point
    scene = fill_order_board()
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    assert next(i for i in spec['inputs'] if i['name'] == 'R') == {
        'name': 'R', 'kind': 'point', 'x': 3.0, 'y': 0.0,
    }
    point = next(e for e in spec['elements'] if e.get('name') == 'R')
    assert point['role'] == 'input' and point['attrs'].get('fixed', False) is False
    circle = next(e for e in spec['elements'] if e.get('name') == 'outer')
    assert circle['parents'] == [{'ref': 'O'}, {'ref': 'R'}]
    assert spec['paintOrder']['fillOrder'] == ['outer', 'inner']
    scene.geo.update('R', Point([.1, 0]))
    scene.updateGeoElements(scene.geo.rebuild())
    assert json.loads(scene.exportJSXGraph(output='spec'))['paintOrder']['fillOrder'] == ['inner', 'outer']
