"""IMP-5: faithful properties and explicit refusals keep geometry editable."""
import re

import pytest

from animageo import native
from animageo.native.rendering import appearance_plan
from tests.native.ggb_imp5 import DIRECTORY, PATTERNS, bodies, dash_body, labels_body, layers_body, slider_body
from tests.native.ggb_synth import element, ggb_bytes, point
from tests.native.test_native_ggb_inline import eid, imported
from tests.native.test_native_ggb_texts import text
from tests.native.test_native_l5_ggb import NS, _check


def styled(body):
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, report)
    items = {e['ggb_name']: e for e in report['elements']}
    for item in items.values():
        for key in item['native_ids']:
            doc['appearance'].setdefault(key, {}).setdefault('overrides', {}).update(item.get('ggb_style', {}))
    return doc, items, report


def test_extended_corpus_reproduces_anonymous_sources():
    assert {p.stem for p in DIRECTORY.glob('*.ggb')} == set(bodies())
    for name, body in bodies().items():
        assert (DIRECTORY / f'{name}.ggb').read_bytes() == ggb_bytes(body)


@pytest.mark.parametrize('kind', PATTERNS)
def test_dash_has_ggb_pixel_lengths_width_opacity_and_no_path_fitting(kind):
    doc, items, _ = styled(dash_body(kind))
    key = eid(items, 's')
    for x in (1., 5., 7.13):
        paint = native.resolve_paint(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [x, 0.]}})
        stroke = paint['elements'][key]['stroke']
        assert stroke['widthPx'] == 3.
        assert stroke['opacity'] == pytest.approx(128 / 255, abs=1e-6)
        if kind:
            assert stroke['dash']['patternPx'] == PATTERNS[kind]
            assert stroke['dash']['drawn']['patternPx'] == PATTERNS[kind]
            assert stroke['dash']['fit'] == 'none'
        else:
            assert stroke['dash'] is None


def test_layers_separate_fill_stroke_and_labels_above_previous_layer():
    doc, items = imported(layers_body())
    paint = native.resolve_paint(doc)
    c, a, low = (paint['elements'][eid(items, n)] for n in ('c', 'A', 'C'))
    assert c['fill']['z'] > low['label']['z'] > a['label']['z']
    assert c['stroke']['z'] > c['fill']['z']
    assert c['label']['z'] > c['stroke']['z']
    assert paint['order'].index(eid(items, 'A')) < paint['order'].index(eid(items, 'C'))
    _, report = native.from_ggb(ggb_bytes(layers_body()), id_namespace=NS)
    assert not report['dropped']


def test_label_modes_visibility_offsets_and_live_values():
    doc, items = imported(labels_body())
    for mode, name in enumerate(('name', 'name_value', 'value', 'caption')):
        assert doc['appearance'][eid(items, f's{mode}')]['label'] == {
            'mode': name, 'offsetWorld': [.3, .2], **({'text': 'base'} if mode == 3 else {})}
    hidden = doc['appearance'][eid(items, 'H')]
    assert hidden['visible'] is False and hidden['label']['mode'] == 'none'
    plan, diagnostics = appearance_plan(doc, 50.)
    assert not diagnostics
    assert plan[eid(items, 's0')]['style']['label_offset_px'] == [15., 10.]
    before = native.resolve_paint(doc)['elements'][eid(items, 's2')]['label']['text']
    after = native.resolve_paint(doc, inputs={eid(items, 'B'): {'kind': 'point', 'value': [6., 0.]}})
    assert before != after['elements'][eid(items, 's2')]['label']['text']


@pytest.mark.parametrize('extra, code', [
    ('<labelMode val="9"/><caption val="base"/>', 'label_mode_unsupported'),
    ('<labelMode val="3"/><caption val="%n = %v"/>', 'label_caption_unsupported'),
    ('<dynamicCaption val="t"/>', 'label_caption_unsupported'),
    ('<labelMode val="2"/>', 'label_mode_unsupported'),
])
def test_unrepresentable_labels_are_hidden_with_reason(extra, code):
    body = point('A', 1., 2.).replace('<labelMode val="0"/>', extra)
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    assert any(w['code'] == code and w['ggb_name'] == 'A' for w in report['warnings'])
    assert doc['appearance'][report['elements'][0]['native_ids'][0]]['label']['mode'] == 'none'
    assert report['elements'][0]['category'] == 'editable'


def caption_owner(*, shown=True):
    return point('A', 1., 2., label_shown=shown, extra='<dynamicCaption val="t"/>').replace(
        '<labelMode val="0"/>', '<labelMode val="3"/>')


@pytest.mark.parametrize('latex, source, expected', [
    (False, '"value = " + n', 'value = 3'),
    (True, r'"\frac{1}{2} = " + n', r'$\frac{1}{2} = 3$'),
    (False, '""', ''),
    (False, '"%n is literal text"', '%n is literal text'),
])
def test_dynamic_caption_freezes_hidden_text_and_reports_simplification(latex, source, expected):
    body = (caption_owner() + element('numeric', 'n', extra='<value val="3"/>')
            + text('t', source, latex=latex, show=False))
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, report)
    items = {e['ggb_name']: e for e in report['elements']}
    owner = items['A']
    assert (owner['category'], owner['reason'], owner['value_check']) == (
        'differs', 'value_unchecked', 'not_checked')
    assert 'подпись не пересчитывается' in owner['detail']
    assert owner['label'] == {'visible': True, 'mode': 'caption', 'caption': expected}
    assert doc['appearance'][eid(items, 'A')]['label'] == {'mode': 'caption', 'text': expected}
    assert owner['depends_on'] == []
    assert doc['appearance'][eid(items, 't')]['visible'] is False
    assert any(w['code'] == 'label_caption_simplified' and w['ggb_name'] == 'A' for w in report['warnings'])
    assert not any(w['code'] == 'label_caption_unsupported' for w in report['warnings'])
    for inputs in ({}, {eid(items, 'n'): {'kind': 'number', 'value': 7.},
                       eid(items, 'A'): {'kind': 'point', 'value': [4., 5.]}}):
        assert native.resolve_paint(doc, inputs=inputs)['elements'][eid(items, 'A')]['label']['text'] == expected
    assert native.evaluate(doc, inputs={eid(items, 'A'): {'kind': 'point', 'value': [4., 5.]}}).elements[
        eid(items, 'A')]['value'] == {'x': 4., 'y': 5.}


def test_caption_snapshot_does_not_require_a_placeable_or_live_source_text():
    doc, items = imported(caption_owner() + text('t', '"point = " + A', latex=False, anchor='', show=False))
    assert items['t']['category'] == 'picture'
    assert items['A']['category'] == 'differs'
    assert doc['appearance'][eid(items, 'A')]['label'] == {'mode': 'caption', 'text': 'point = (1, 2)'}


def test_hidden_dynamic_caption_stays_hidden_without_simplifying_geometry():
    doc, items = imported(caption_owner(shown=False) + text('t', '"value"', latex=False))
    assert items['A']['category'] == 'editable'
    assert items['A']['label'] == {'visible': False, 'mode': 'none'}
    assert doc['appearance'][eid(items, 'A')]['label'] == {'mode': 'none'}


@pytest.mark.parametrize('source, latex, detail', [
    (r'"\myMacro{x}"', True, 'неподдержанная команда TeX'),
    (r'"\input{file}"', True, 'неподдержанная команда TeX'),
    (r'"\input{file}"', False, 'неподдержанная команда TeX'),
    ('"right\u202eleft"', False, 'управляющий символ'),
    ('"value" + Unknown[n]', False, 'выражение текста подписи'),
])
def test_unsafe_or_unknown_caption_text_is_hidden_with_specific_reason(source, latex, detail):
    doc, report = native.from_ggb(ggb_bytes(caption_owner() + text('t', source, latex=latex)), id_namespace=NS)
    _check(doc, report)
    owner = report['elements'][0]
    assert owner['category'] == 'editable'
    assert owner['label'] == {'visible': False, 'mode': 'none'}
    warning = next(w for w in report['warnings'] if w['ggb_name'] == 'A' and w['code'] == 'label_caption_unsupported')
    assert detail in warning['detail']
    assert doc['appearance'][owner['native_ids'][0]]['label']['mode'] == 'none'


def test_slider_step_and_animation_are_reported_and_number_remains_live():
    doc, items, report = styled(slider_body())
    key = eid(items, 'n')
    op = doc['operations'][doc['elements'][key]['producer']['operationId']]
    assert {k: v['value'] for k, v in op['args'].items()} == {'min': 1., 'max': 5., 'step': .25}
    for value, radius in ((-10., 1.), (4., 4.), (10., 5.)):
        ev = native.evaluate(doc, inputs={key: {'kind': 'number', 'value': value}})
        assert ev.elements[eid(items, 'c')]['value']['r'] == radius
    assert report['dropped'] == [{'kind': 'animation', 'count': 1, 'names': ['n']}]
    detail = next(w['detail'] for w in report['warnings'] if w['code'] == 'animation_settings_dropped')
    assert all(s in detail for s in ('playing=true', 'speed=2.5', 'step=0.25', 'type=0'))
    assert not doc.get('timeline')


@pytest.mark.parametrize('attrs, animation', [
    ('min="a" max="5"', ''), ('min="6" max="1"', ''),
    ('min="0" max="5"', '<animation step="0" speed="1" playing="false"/>'),
])
def test_unrepresentable_slider_range_is_reported_without_losing_saved_number(attrs, animation):
    body = element('numeric', 'n', extra=f'<value val="3"/><slider {attrs}/>{animation}')
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, report)
    assert report['elements'][0]['category'] == 'editable'
    assert any(w['code'] == 'slider_range_dropped' for w in report['warnings'])
    assert next(iter(doc['operations'].values()))['args'] == {}


@pytest.mark.manim
@pytest.mark.parametrize('kind', [10, 15, 20, 30])
def test_svg_and_tikz_draw_exact_dash_sequences(kind, tmp_path):
    pytest.importorskip('manim')
    doc, _, _ = styled(dash_body(kind))
    path = tmp_path / 'dash.svg'
    native.render(doc, fmt='svg', out=str(path), report=False)
    tag = next(t for t in re.findall(r'<path\b[^>]*>', path.read_text()) if 'stroke-dasharray' in t)
    values = [float(x) for x in re.split(r'[ ,]+', re.search(r'stroke-dasharray="([^"]+)"', tag)[1])]
    transform = re.search(r'transform="matrix\(([^,]+),', tag)
    scale = abs(float(transform[1])) if transform else 1.
    assert [v * scale for v in values] == pytest.approx(PATTERNS[kind], rel=1e-4)
    tex = tmp_path / 'dash.tex'
    native.render(doc, fmt='tikz', out=str(tex), report=False)
    assert tex.read_text().count('dash pattern=on') == 1
    if kind == 30:
        assert re.search(r'dash pattern=on [\d.]+pt off [\d.]+pt on [\d.]+pt off [\d.]+pt', tex.read_text())


@pytest.mark.parametrize('level', ['1.5', '11', 'bad'])
def test_invalid_layers_are_not_rounded_or_silently_lost(level):
    body = point('A', 1., 2.).replace('<layer val="0"/>', f'<layer val="{level}"/>')
    doc, report = native.from_ggb(ggb_bytes(body), id_namespace=NS)
    _check(doc, report)
    assert report['elements'][0]['category'] == 'editable'
    assert report['dropped'] == [{'kind': 'layers', 'count': 1, 'names': ['A']}]
    assert any(w['code'] == 'layer_unsupported' for w in report['warnings'])


def test_missing_view_refuses_offset_with_a_reason():
    from tests.native.ggb_synth import ggb_xml
    xml = ggb_xml(point('A', 1., 2., extra='<labelOffset x="10" y="20"/>'))
    xml = re.sub(rb'<euclidianView>.*?</euclidianView>', b'', xml)
    doc, report = native.from_ggb(ggb_bytes(xml=xml), id_namespace=NS)
    _check(doc, report)
    assert any(w['code'] == 'label_offset_dropped' for w in report['warnings'])
    assert 'offsetWorld' not in next(iter(doc['appearance'].values()))['label']


def test_explicit_solid_overrides_a_dashed_style_and_invalid_arrays_do_not_reach_cairo():
    from animageo.dash import element_dash_px, explicit_dash_px
    for invalid in (None, [], [0, 3], [True, 3], [1, float('nan')], [1, 2, 3], [1, 2] * 100):
        assert explicit_dash_px(invalid) is None
    resolve = lambda e, k, d=None: {'stroke_dash_pattern_px': [], 'stroke_dash_ratio': .5}.get(k, d)
    assert element_dash_px(None, None, resolve) is None


@pytest.mark.manim
def test_null_label_layer_uses_automatic_order_in_paint_and_renderer(tmp_path):
    pytest.importorskip('manim')
    doc, items = imported(point('A', 1., 2.))
    key = eid(items, 'A')
    automatic_z = native.resolve_paint(doc)['elements'][key]['label']['z']
    doc['appearance'][key]['overrides'] = {'z_index_label': None}
    assert native.resolve_paint(doc)['elements'][key]['label']['z'] == automatic_z
    native.render(doc, fmt='svg', out=str(tmp_path / 'automatic.svg'), report=False)
