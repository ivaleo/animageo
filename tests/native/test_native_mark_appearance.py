"""Independent equality-decoration paint (1.11.0rc13)."""
import copy
import re

import pytest

from animageo import native
from animageo.native import rendering
from tests.native.conftest import DocBuilder, num, point_input

PURPLE = '#9933cc'


def drawing():
    b = DocBuilder('mark_appearance', registry_version='1.3', bounds=(-1, -1, 5, 4))
    b.free('A', 0, 0).free('B', 4, 0).free('C', 1, 3).free('D', 5, 3)
    b.segment('s', 'A', 'B').segment('t', 'C', 'D')
    b.angle('g', 'B', 'A', 'C').angle('h', 'A', 'B', 'C')
    b.equal_segments('m', 's', 't').equal_angles('n', 'g', 'h')
    b.doc['appearance'] = {e: {'label': {'mode': 'none'}} for e in b.doc['elements']}
    return b


def override(b, el, **keys):
    b.doc['appearance'].setdefault(el, {}).setdefault('overrides', {}).update(keys)


@pytest.mark.parametrize('mark, targets, field', [('m', ('s', 't'), 'ticks'), ('n', ('g', 'h'), 'angle')])
def test_independent_color_count_and_semantics(mark, targets, field):
    b = drawing()
    before = native.evaluate(b.doc).elements[mark]
    override(b, mark, stroke=PURPLE, tick_count=2)
    override(b, targets[0], stroke='#112233', fill='#ffcc00', fill_opacity=0.4)
    paint = native.resolve_paint(b.doc)
    assert not [d for d in paint['diagnostics'] if d.get('elementId') == mark]
    for target in targets:
        item = paint['elements'][target]
        assert item['stroke']['color'] == ('#112233' if target == targets[0] else '#000000')
        assert item[field]['count' if field == 'ticks' else 'arcs'] == 2
        deco = item['decoration']
        assert (deco['owner'], deco['color'], deco['count']) == (mark, PURPLE, 2)
    if field == 'angle':
        assert paint['elements'][targets[0]]['fill']['color'] == '#ffcc00'
        assert paint['elements'][targets[0]]['fill']['opacity'] == 0.4
    assert native.evaluate(b.doc).elements[mark] == before
    b.doc['appearance'][mark].pop('overrides')
    assert native.resolve_paint(b.doc)['elements'][targets[0]][field]['count' if field == 'ticks' else 'arcs'] == 1


def test_priority_sizes_hidden_undefined_and_no_mutation():
    b = drawing()
    # Insert the later ID first: insertion order cannot determine the paint.
    b.equal_segments('z', 's', 't', count=3)
    override(b, 'z', stroke='#ff0000', tick_count=3, tick_length_px=20)
    override(b, 'm', stroke=PURPLE, tick_count=2, tick_length_px=14)
    override(b, 's', stroke='#112233', tick_count=1, tick_length_px=6)
    before = copy.deepcopy(b.doc)
    out = native.resolve_paint(b.doc)['elements']
    assert (out['s']['ticks']['count'], out['s']['ticks']['lengthPx']) == (1, 6)
    assert (out['t']['ticks']['count'], out['t']['ticks']['lengthPx']) == (2, 14)
    assert out['s']['decoration']['color'] == PURPLE
    assert b.doc == before
    b.doc['appearance']['m']['visible'] = False
    out = native.resolve_paint(b.doc)['elements']
    assert (out['t']['decoration']['owner'], out['t']['decoration']['color']) == ('z', '#ff0000')
    override(b, 'n', stroke=PURPLE, tick_count=3)
    out = native.resolve_paint(b.doc, inputs={'B': point_input(0, 0)})['elements']
    assert 'decoration' not in out['h']  # the equality mark is undefined with g


def test_first_mark_without_color_keeps_its_fallback_and_plan_separates_stroke():
    b = drawing()
    b.equal_segments('z', 's', 't', count=3)
    override(b, 'z', stroke=PURPLE, tick_count=3)
    override(b, 's', stroke='#112233')
    plan, diagnostics = rendering.appearance_plan(b.doc, 100)
    assert diagnostics == []
    assert plan['s']['style']['stroke'] == '#112233'
    assert plan['s']['style']['tick_count'] == 1
    assert plan['s']['decoration'] == {'owner': 'm', 'stroke': None, 'explicit': False}
    out = native.resolve_paint(b.doc)['elements']['s']
    assert out['decoration']['color'] == '#112233'
    assert out['decoration']['owner'] == 'm'
    b.doc['appearance']['s']['visible'] = False
    assert 'decoration' not in native.resolve_paint(b.doc)['elements']['s']


@pytest.mark.parametrize('count', [0, 2, 3])
def test_equal_right_angles_obey_drawn_arc_count(count):
    b = drawing()
    override(b, 'n', stroke=PURPLE, tick_count=count)
    override(b, 'g', right_angle_marker=True)
    item = native.resolve_paint(b.doc, inputs={'C': point_input(0, 3)})['elements']['g']
    assert item['angle']['right'] is False
    assert item['decoration']['kind'] == 'arcs'
    assert item['decoration']['count'] == count


def test_colour_alone_keeps_the_right_angle_square():
    b = drawing()
    override(b, 'n', stroke=PURPLE)
    override(b, 'g', right_angle_marker=True)
    item = native.resolve_paint(b.doc, inputs={'C': point_input(0, 3)})['elements']['g']
    assert item['angle']['right'] is True
    assert item['decoration']['kind'] == 'square'
    assert item['decoration']['color'] == PURPLE


@pytest.mark.parametrize('mark, target, field', [('m', 's', 'ticks'), ('n', 'g', 'angle')])
def test_zero_hides_only_the_decoration(mark, target, field):
    b = drawing()
    override(b, mark, stroke=PURPLE, tick_count=0)
    item = native.resolve_paint(b.doc)['elements'][target]
    assert item['drawn'] and item['stroke']['color'] == '#000000'
    assert item[field]['count' if field == 'ticks' else 'arcs'] == 0
    assert item['decoration']['count'] == 0
    assert native.evaluate(b.doc).elements[mark]['value']['count'] == 1


@pytest.mark.parametrize('mark', ['m', 'n'])
@pytest.mark.parametrize('key, value', [
    ('stroke', '#abc'), ('stroke', '#12345678'), ('stroke', 'purple'), ('stroke', '#gg1122'),
    ('stroke', None), ('tick_count', -1), ('tick_count', 4), ('tick_count', 1.5),
    ('tick_count', 2.0), ('tick_count', True), ('tick_count', '2'), ('tick_count', None),
])
def test_bad_values_are_rejected_by_load_and_render_contract(mark, key, value):
    b = drawing()
    override(b, mark, **{key: value})
    with pytest.raises(native.LoadError) as error:
        native.load(b.doc)
    assert any(i.path == f'/appearance/{mark}/overrides/{key}' for i in error.value.issues)
    with pytest.raises(native.LoadError):
        native.resolve_paint(b.doc)


def test_contract_export_drives_web_override_keys():
    from animageo.native.paint import MARK_TRANSFERS, ineffective_reason, style_contract_files
    import json
    types = json.loads(style_contract_files()['keys.v1.json'])['types']
    for mark in ('mark.equal_segments', 'mark.equal_angles'):
        assert {'stroke', 'tick_count'} <= set(MARK_TRANSFERS[mark])
        assert {'stroke', 'tick_count'} <= set(types[mark]['keys']) | set(types[mark]['transfers'])
        assert ineffective_reason(mark, 'stroke') is None
        assert ineffective_reason(mark, 'tick_count') is None


def test_reusable_override_schema_matches_exported_count_contract():
    import json
    from pathlib import Path
    from animageo.native import paint
    schema = json.loads((Path(paint.__file__).parent / 'schema/construction.v1.schema.json').read_text())
    contract = schema['$defs']['equalityMarkOverrides']
    assert contract['properties']['tick_count']['enum'] == \
        native.style_keys()['types']['mark.equal_segments']['keys']['tick_count']['values']
    jsonschema = pytest.importorskip('jsonschema')
    validator = jsonschema.Draft202012Validator(contract)
    assert not list(validator.iter_errors({'stroke': PURPLE, 'tick_count': 0}))
    for bad in ({'stroke': '#123'}, {'tick_count': 4}, {'tick_count': True}, {'tick_count': 0.5}):
        assert list(validator.iter_errors(bad))


def test_timeline_diagnostics_restore_decorations_without_leaks():
    b = drawing()
    override(b, 'm', stroke=PURPLE, tick_count=2)
    override(b, 'n', stroke=PURPLE, tick_count=3)
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'m': False, 'n': False}},
        {'t': 1, 'visible': {'m': True, 'n': True}},
        {'t': 2, 'visible': {'m': False, 'n': False}},
        {'t': 3, 'visible': {'m': True, 'n': True}},
    ]}
    for t in (1, 0, 3, 2, 1):
        elements = native.resolve_paint(b.doc, t=t, timeline=timeline)['elements']
        for target, count in [('s', 2), ('g', 3)]:
            assert elements[target]['stroke']['color'] == '#000000'
            if t in (1, 3):
                assert elements[target]['decoration']['color'] == PURPLE
                assert elements[target]['decoration']['count'] == count
            else:
                assert 'decoration' not in elements[target]


@pytest.mark.manim
@pytest.mark.parametrize('mark, targets', [('m', ('s', 't')), ('n', ('g', 'h'))])
def test_svg_png_draw_independent_mark_paint(tmp_path, mark, targets):
    pytest.importorskip('manim')
    from PIL import Image
    import numpy as np
    b = drawing()
    override(b, mark, stroke=PURPLE, tick_count=2)
    if mark == 'n':
        override(b, 'g', stroke='#112233', fill='#ffcc00', fill_opacity=0.4, stroke_width_px=3)
        override(b, 'h', stroke_width_px=3)
    svg = tmp_path / f'{mark}.svg'
    result = native.render(b.doc, out=svg)
    text = svg.read_text()
    assert 'stroke="rgb(60%, 20%, 80%)"' in text
    assert 'stroke="rgb(0%, 0%, 0%)"' in text
    # Inspect the actual paths too: the semantic count remains one.
    purple = re.findall(r'<path[^>]*stroke="rgb\(60%, 20%, 80%\)"[^>]*>', text)
    assert len(purple) == 4
    for target in targets:
        assert result.report['elements'][target]['decoration']['color'] == PURPLE
    png = tmp_path / f'{mark}.png'
    native.render(b.doc, fmt='png', out=png)
    with Image.open(png) as im:
        pixels = np.asarray(im.convert('RGB')).astype(int)
    assert np.any(np.all(np.abs(pixels - [153, 51, 204]) < 10, axis=-1))
    assert np.any(np.all(pixels < 10, axis=-1))


@pytest.mark.manim
def test_seek_restores_stroke_count_and_owner_in_one_scene():
    pytest.importorskip('manim')
    from animageo import AnimaGeoScene
    b = drawing()
    override(b, 'm', stroke=PURPLE, tick_count=2)
    override(b, 'n', stroke=PURPLE, tick_count=3)
    scene = AnimaGeoScene()
    scene.loadDocument(b.doc)
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'m': False, 'n': False}},
        {'t': 1, 'visible': {'m': True, 'n': True}},
        {'t': 2, 'visible': {'m': False, 'n': False}},
    ]}
    bridged = native.timeline_to_bridge(b.doc, timeline)
    for t in (1, 0, 2, 1):
        scene.seek_keyframes(bridged, t)
        for target, count in [('s', 2), ('g', 3)]:
            ctx = scene._build_render_ctx(scene.geo.element(scene.native_names.by_id[target]), True)
            assert ctx.tick_count == (count if t == 1 else (1 if target == 'g' else 0))
            from manim import ManimColor
            assert ManimColor(ctx.tick_color).to_hex() == ManimColor(PURPLE if t == 1 else ctx.col_s).to_hex()
            group = scene.mobject(scene.native_names.by_id[target])
            # Manim pads become() with transparent pieces when the count
            # changes. Count the visible stroke layer of the current frame.
            drawn = [m for m in group.submobjects[1:] if m.get_stroke_opacity() > 0 and
                     (target == 's' or abs(m.z_index - ctx.zz - 0.1) < 1e-9)]
            assert len(drawn) == ctx.tick_count
            assert all(m.get_stroke_color().to_hex() == ManimColor(ctx.tick_color).to_hex() for m in drawn)


@pytest.mark.manim
@pytest.mark.parametrize('mark', ['m', 'n'])
def test_tikz_uses_the_independent_decoration_color_and_zero(tmp_path, mark):
    pytest.importorskip('manim')
    b = drawing()
    override(b, mark, stroke=PURPLE, tick_count=2)
    path = tmp_path / 'mark.tex'
    native.render(b.doc, fmt='tikz', out=path)
    text = path.read_text()
    definition = re.search(r'\\definecolor\{([^}]+)\}\{HTML\}\{9933CC\}', text)
    assert definition, text
    color = definition.group(1)
    assert len(re.findall(r'\\draw\[[^\n]*draw=' + re.escape(color) + r'[,\]]', text)) == 4
    override(b, mark, tick_count=0)
    native.render(b.doc, fmt='tikz', out=path)
    text = path.read_text()
    definition = re.search(r'\\definecolor\{([^}]+)\}\{HTML\}\{9933CC\}', text)
    if definition:
        assert not re.findall(r'\\draw\[[^\n]*draw=' + re.escape(definition.group(1)) + r'[,\]]', text)


@pytest.mark.manim
def test_mark_fade_affects_colored_decoration_and_preserves_body():
    pytest.importorskip('manim')
    from manim import ManimColor
    from animageo.native.document import as_document
    b = drawing()
    override(b, 'm', stroke=PURPLE, tick_count=2)
    override(b, 'n', stroke=PURPLE, tick_count=3)
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'m': False, 'n': False}},
        {'t': 1, 'visible': {'m': True, 'n': True},
         'enter': {'m': {'effect': 'fade', 'duration': 1, 'at': 0},
                   'n': {'effect': 'fade', 'duration': 1, 'at': 0}}},
        {'t': 2},
    ]}
    scene = rendering._still_scene(as_document(b.doc), None, None, {}, timeline, 0.5)
    for target, count in [('s', 2), ('g', 3)]:
        group = scene.mobject(scene.native_names.by_id[target])
        parts = group.submobjects[1:1 + count]
        assert len(parts) == count
        assert all(m.get_stroke_color().to_hex() == ManimColor(PURPLE).to_hex() for m in parts)
        assert all(m.get_stroke_opacity() == pytest.approx(0.5) for m in parts)
    line = scene.mobject(scene.native_names.by_id['s']).submobjects[0]
    assert line.get_stroke_color().to_hex() == '#000000'
    assert line.get_stroke_opacity() == 1


@pytest.mark.manim
@pytest.mark.parametrize('omit_count', [False, True])
def test_initially_undefined_mark_recovers_its_paint(omit_count):
    pytest.importorskip('manim')
    from animageo.native.document import as_document
    b = drawing()
    override(b, 'n', stroke=PURPLE, tick_count=2)
    if not omit_count:
        b.doc['operations']['op_n']['args']['count'] = num(1)
    b.doc['inputs']['B'] = point_input(0, 0)
    assert native.evaluate(b.doc).elements['n']['state'] == 'undefined'
    timeline = {'version': 2, 'keyframes': [
        {'t': 0}, {'t': 1, 'values': {'B': [4, 0]}}, {'t': 2},
    ]}
    scene = rendering._still_scene(as_document(b.doc), None, None, {}, timeline, 1)
    target = scene.geo.element(scene.native_names.by_id['g'])
    ctx = scene._build_render_ctx(target, True)
    assert ctx.tick_count == 2
    assert ctx.tick_color == PURPLE
    report = rendering.build_report(scene, b.doc, fmt='svg', inputs={'B': point_input(4, 0)})
    assert report['elements']['g']['decoration']['owner'] == 'n'
