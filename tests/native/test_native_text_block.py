"""Literal text blocks: bounded content, deterministic font-metric wrapping."""
import copy
import json
from pathlib import Path

import pytest

from animageo import native
from animageo.native.text_block import (
    layout_text_block, normalize_text_block, text_block_plain_text, validate_text_block,
)


def test_web_plain_fixtures():
    cases = json.loads((Path(__file__).parent / 'fixtures/text_blocks.json').read_text())
    for case in cases:
        content = normalize_text_block(case['input'])
        assert content == {'version': 'text-block/v1', 'paragraphs': case['paragraphs']}
        assert text_block_plain_text(content) == case['normalized']
        assert validate_text_block(content) == content


@pytest.mark.parametrize('align', ['left', 'center', 'right'])
@pytest.mark.parametrize('size', [0.5, 1, 4])
def test_cyrillic_layout_alignment_size_hash(align, size):
    content = normalize_text_block('Условие задачи: найти площадь.\nРешение\n\nОтвет')
    result = layout_text_block(content, 9, size, align)
    assert result == layout_text_block(copy.deepcopy(content), 9, size, align)
    assert result['metricsVersion'] and result['hash'].startswith('sha256:')
    assert len(result['lines']) >= 5
    factor = {'left': 0, 'center': 0.5, 'right': 1}[align]
    for line in result['lines']:
        assert line['x'] == pytest.approx((9 - line['width']) * factor)
    normal = layout_text_block(content, 9, 1, align)
    assert result['lines'] == normal['lines']
    assert (result['width'], result['height']) == (normal['width'], normal['height'])
    assert native.layout_text_block is layout_text_block


def test_breaks_empty_paragraphs_literal_text():
    source = '\nСтрока\n\n\nОтвет\n\n'
    result = layout_text_block(normalize_text_block(source), 120)
    assert [line['text'] for line in result['lines']] == source.split('\n')
    literal = r'{0} %v $x$ \input{file} <b> & _ ^ ~ "'
    result = layout_text_block(normalize_text_block(literal), 120)
    assert [line['text'] for line in result['lines']] == [literal]


def test_long_word_graphemes_and_twenty_thousand_codepoints():
    source = 'е\u0301' * 70
    result = layout_text_block(normalize_text_block(source), 4)
    assert len(result['lines']) > 1
    assert ''.join(line['text'] for line in result['lines']) == source
    assert all(not line['text'].startswith('\u0301') for line in result['lines'])
    large = 'Ш' * 20000
    result = layout_text_block(normalize_text_block(large), 4)
    assert ''.join(line['text'] for line in result['lines']) == large
    assert all(line['width'] <= 4 + 1e-9 for line in result['lines'])


@pytest.mark.parametrize('text', ['a' * 20001, '\n\n' * 200, '\0', '\ud800'])
def test_content_limits(text):
    with pytest.raises(ValueError):
        normalize_text_block(text)


@pytest.mark.parametrize('kwargs', [dict(widthEm=3.99), dict(widthEm=121), dict(widthEm=True),
    dict(widthEm=float('nan')), dict(size=0.49), dict(size=4.01), dict(align='justify'),
    dict(text_style={'font_size_px': 0}), dict(text_style={'font': 'arbitrary'})])
def test_layout_limits(kwargs):
    with pytest.raises(ValueError):
        layout_text_block(normalize_text_block('text'), **kwargs)


@pytest.mark.parametrize('content', [
    {'version': 'text-block/v1', 'paragraphs': []},
    {'version': 'text-block/v1', 'paragraphs': [{'runs': [{'kind': 'inline_math', 'text': 'x'}]}]},
    {'version': 'text-block/v1', 'paragraphs': [{'runs': [{'kind': 'text', 'text': 'a\nb'}]}]},
    {'version': 'text-block/v1', 'paragraphs': [{'runs': [{'kind': 'text', 'text': ''}]}]},
    {'version': 'text-block/v1', 'paragraphs': [{'runs': []}], 'source': ''},
])
def test_canonical_content(content):
    with pytest.raises(ValueError):
        validate_text_block(content)


def test_font_coverage_failure_is_explicit():
    with pytest.raises(ValueError, match='glyph'):
        layout_text_block(normalize_text_block('中文'))


def block_doc(text='Условие задачи\nОтвет', **params):
    from tests.native.conftest import DocBuilder, num, ref
    builder = DocBuilder('block', registry_version='1.14').free('A', -3, 3)
    args = {'anchor': ref('A'), 'content': {'kind': 'text-block', 'value': normalize_text_block(text)}}
    args.update({key: {'kind': 'string' if key == 'align' else 'number', 'value': value}
                 for key, value in params.items()})
    return builder.op('op_t', 'text.block', args, [('text', 't', 'text')]).doc


def test_operation_registry_schema_and_bridge():
    from animageo.native.kernel.bridge import build_construction, from_classic
    from animageo.native.registry import registry_problems
    assert native.__registry_version__ == '1.14'
    assert native.has('text.block')
    assert registry_problems() == []
    doc = block_doc(r'Цена $5 {0} \input{test}', widthEm=12, size=0.5, align='right')
    loaded = native.load(native.canonical_json(doc))
    assert native.validate(loaded) == []
    assert native.min_registry_version(loaded) == '1.14'
    value = native.evaluate(loaded).elements['t']['value']
    assert value['content'] == doc['operations']['op_t']['args']['content']['value']
    assert value['widthEm'] == 12 and value['size'] == 0.5 and value['align'] == 'right'
    construction, names = build_construction(loaded)
    construction.rebuild(full=True)
    obj = construction.element(names.by_id['t']).data
    assert from_classic('text', obj) == value
    from animageo.geo.lib_elements import Point
    construction.update(names.by_id['A'], Point([1, -2]))
    construction.rebuild()
    moved = from_classic('text', construction.element(names.by_id['t']).data)
    assert moved == dict(value, anchor=[1, -2])
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads(Path('animageo/native/schema/construction.v1.schema.json').read_text())
    jsonschema.validate(doc, schema)


@pytest.mark.parametrize('params', [dict(widthEm=3), dict(widthEm=121), dict(size=0.4),
                                    dict(size=5), dict(align='justify')])
def test_operation_rejects_bad_parameters(params):
    doc = block_doc(**params)
    assert any(i.code == 'invalid_parameter' for i in native.validate(doc))
    assert native.evaluate(doc).elements['t']['state'] != 'defined'


def test_old_registry_refuses_block():
    doc = block_doc()
    doc['operationRegistryVersion'] = '1.13'
    assert any(i.code == 'needs_newer_registry' for i in native.validate(doc))
    assert native.evaluate(doc).elements['t']['state'] != 'defined'


def test_render_formats_share_lines(tmp_path):
    pytest.importorskip('manim')
    doc = block_doc('Ёжик {0} $x$\nДлинноесловобезпробелов\n\nОтвет', widthEm=5, align='center')
    expected = layout_text_block(doc['operations']['op_t']['args']['content']['value'], 5, align='center')
    for fmt in ('svg', 'pdf', 'tikz', 'tex', 'png', 'eps'):
        result = native.render(doc, fmt=fmt, out=tmp_path / ('block.' + fmt))
        assert result.path and Path(result.path).stat().st_size > 100
        artifact = result.report['elements']['t']['textBlock']['layout']
        assert artifact == expected
        assert result.report['elements']['t']['box'] is not None
        if fmt in ('tikz', 'tex'):
            source = Path(result.path).read_text()
            assert source.count('% text.block line ') == len(expected['lines'])
            assert 'text width=' not in source and '\\parbox' not in source


def test_block_render_errors_propagate(tmp_path, monkeypatch):
    pytest.importorskip('manim')
    import animageo.text_block_render as renderer
    def fail(*args, **kwargs):
        raise ValueError('text.block: deliberate glyph failure')
    monkeypatch.setattr(renderer, 'render_block', fail)
    with pytest.raises(ValueError, match='deliberate glyph failure'):
        native.render(block_doc(), out=tmp_path / 'failed.svg')


def test_tikz_block_errors_propagate(tmp_path, monkeypatch):
    pytest.importorskip('manim')
    import animageo.text_block_render as renderer
    def fail(*args, **kwargs):
        raise ValueError('text.block: deliberate TikZ failure')
    monkeypatch.setattr(renderer, 'emit_block', fail)
    with pytest.raises(ValueError, match='deliberate TikZ failure'):
        native.render(block_doc(), fmt='tikz', out=tmp_path / 'failed.tikz')


def test_normalization_limit_applies_after_crlf():
    text = 'a\r\n' * 10000
    assert len(text_block_plain_text(normalize_text_block(text))) == 20000


@pytest.mark.parametrize('size', [0.5, 1, 4])
def test_projection_size_and_frame(tmp_path, size):
    pytest.importorskip('manim')
    result = native.render(block_doc('Строка с переносом', widthEm=4, size=size, align='right'),
                           out=tmp_path / 'scaled.svg')
    block = result.report['elements']['t']['textBlock']
    assert block['layout']['lines'] == layout_text_block(normalize_text_block('Строка с переносом'), 4, align='right')['lines']
    assert block['emToWorld'] / size == pytest.approx(10 * 0.00103777501038 * 16 * 100 / 40)


def test_video_frame_and_visibility(tmp_path):
    pytest.importorskip('manim')
    timeline = {'version': 2, 'keyframes': [{'t': 0}, {'t': 1, 'values': {'A': [2, 1]}}]}
    doc = block_doc('Первая\n\nТретья', widthEm=5)
    expected = layout_text_block(doc['operations']['op_t']['args']['content']['value'], 5)
    for fmt in ('svg', 'png', 'tikz'):
        options = {'video': {'fps': 2, 'quality': 'low'}} if fmt == 'png' else {}
        result = native.render(doc, fmt=fmt, t=0.5, timeline=timeline,
                               out=tmp_path / ('frame.' + fmt), **options)
        assert result.report['elements']['t']['textBlock']['layout'] == expected
    video = native.render(doc, fmt='mp4', timeline=timeline, video={'fps': 2, 'quality': 'low'},
                          out=tmp_path / 'block.mp4')
    assert Path(video.path).stat().st_size > 100


def test_render_refuses_invalid_block_instead_of_omitting(tmp_path):
    with pytest.raises(ValueError, match='widthEm'):
        native.render(block_doc(widthEm=3), out=tmp_path / 'invalid.svg')


def test_raster_geometry_matches_svg_pdf_tikz(tmp_path):
    import shutil
    import subprocess
    import numpy as np
    from PIL import Image
    if not all(shutil.which(tool) for tool in ('pdflatex', 'pdftoppm')):
        pytest.skip('pdflatex and pdftoppm required')
    doc = block_doc('Ёжик {0} $x$\nДлинноесловобезпробелов\n\nОтвет', widthEm=5, align='center')
    doc['appearance'] = {'A': {'visible': False}}
    for fmt in ('png', 'pdf', 'tex'):
        native.render(doc, fmt=fmt, out=tmp_path / ('block.' + fmt), report=False)
    proc = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                           '-jobname=tikz-block', 'block.tex'], cwd=tmp_path, capture_output=True)
    assert proc.returncode == 0, proc.stdout[-2000:].decode(errors='replace')
    for name in ('block', 'tikz-block'):
        subprocess.run(['pdftoppm', '-r', '96', '-singlefile', '-png', str(tmp_path / (name + '.pdf')),
                        str(tmp_path / (name + '-raster'))], check=True, capture_output=True)
    boxes = []
    for name in ('block.png', 'block-raster.png', 'tikz-block-raster.png'):
        a = np.asarray(Image.open(tmp_path / name).convert('RGB'))
        ys, xs = np.where(a.min(axis=2) < 150)
        boxes.append(np.array([xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]))
    assert all(np.abs(boxes[0] - box).max() <= 1 for box in boxes[1:]), boxes


def test_tex_source_lines_are_bounded_for_maximum_content():
    from animageo.native.text_block import line_tex
    for text in ('Ж' * 20000, 'a' + '\u0301' * 19999):
        layout = layout_text_block(normalize_text_block(text), 4)
        assert all(max(map(len, line_tex(line).splitlines())) < 1000 for line in layout['lines'])


def test_huge_integer_is_a_field_error():
    with pytest.raises(ValueError, match='widthEm'):
        layout_text_block(normalize_text_block('text'), widthEm=10 ** 400)


def test_upstream_error_cannot_disappear_from_export(tmp_path):
    doc = block_doc()
    del doc['inputs']['A']
    with pytest.raises(ValueError, match='upstream'):
        native.render(doc, out=tmp_path / 'missing-anchor.svg')


def test_supported_t2a_punctuation_and_letters():
    source = '“Ответ” „Дано” § 5 — І і Ї ї Ґ ґ Є є Ў ў'
    assert layout_text_block(normalize_text_block(source), 120)['lines'][0]['text'] == source


def test_tikz_clips_far_lines_and_keeps_body_layer(tmp_path):
    import shutil
    import subprocess
    if not shutil.which('pdflatex'):
        pytest.skip('pdflatex required')
    result = native.render(block_doc('Ж' * 4000, widthEm=4), fmt='tex', out=tmp_path / 'long.tex')
    source = Path(result.path).read_text()
    assert '% paint {"id": "t", "part": "body"}' in source
    assert source.count('\\node[') < 100
    compiled = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'long.tex'],
                               cwd=tmp_path, capture_output=True)
    assert compiled.returncode == 0, compiled.stdout[-2000:].decode(errors='replace')


@pytest.mark.parametrize('source', ['aaaaaaaa aaaaaaaa', 'Перенос перенос'])
def test_wrap_never_introduces_a_whitespace_only_line(source):
    lines = layout_text_block(normalize_text_block(source), 4)['lines']
    assert len(lines) == 2
    assert [line['text'] for line in lines] == [source.split(' ')[0] + ' ', source.split(' ')[1]]
    assert all(line['width'] <= 4 for line in lines)


def test_huge_operation_dimension_is_bounded():
    state = native.evaluate(block_doc(widthEm=10 ** 400)).elements['t']
    assert state['state'] == 'undefined' and state['reason'] == 'invalid_parameter'


@pytest.mark.parametrize('timeline', [[], {'keyframes': [{}]}])
def test_video_preflight_preserves_timeline_errors(timeline):
    with pytest.raises(ValueError):
        native.render(block_doc(), fmt='mp4', timeline=timeline)


def test_video_preflight_is_linear_in_keyframe_count(monkeypatch):
    from animageo.native import rendering, timeline as module
    calls = []
    original = module.normalize_timeline
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    sentinel = object()
    monkeypatch.setattr(module, 'normalize_timeline', counted)
    monkeypatch.setattr(rendering, '_render_video', lambda *args, **kwargs: sentinel)
    keyframes = {'version': 2, 'keyframes': [{'t': i, 'values': {'A': [i, 0]}} for i in range(20)]}
    assert native.render(block_doc(), fmt='mp4', timeline=keyframes) is sentinel
    assert len(calls) <= 3


def test_new_parity_fixtures_replay_without_changing_old_fixtures():
    from animageo.native.parity import generate_scene, verify_fixture
    paths = sorted(Path('animageo/native/parity/v1/text_blocks').glob('*.json'))
    assert [path.name for path in paths] == ['text_block.json', 'text_block_invalid.json']
    for path in paths:
        fixture = json.loads(path.read_text())
        assert verify_fixture(fixture, str(path)) == []
        scene = {key: fixture[key] for key in ('format', 'id', 'document')}
        scene['cases'] = [{key: case[key] for key in ('name', 'inputs') if key in case}
                          for case in fixture['cases']]
        assert generate_scene(scene) == fixture


def test_report_projection_includes_effective_origin(tmp_path):
    doc = block_doc()
    doc['appearance'] = {'t': {'label': {'offsetWorld': [2, -1]}}}
    result = native.render(doc, out=tmp_path / 'offset.svg')
    assert result.report['elements']['t']['textBlock']['origin'] == [-1, 2]


@pytest.mark.parametrize('fill_order', ['construction', 'area'])
def test_tikz_preserves_block_body_z_order(tmp_path, fill_order):
    import shutil
    import subprocess
    import numpy as np
    from PIL import Image
    from tests.native.conftest import DocBuilder
    if not all(shutil.which(tool) for tool in ('pdflatex', 'pdftoppm')):
        pytest.skip('pdflatex and pdftoppm required')
    builder = DocBuilder()
    builder.doc = block_doc('MMMMMM')
    doc = builder.free('B', -2.4, 2.65).doc
    doc['appearance'] = {'A': {'visible': False},
        't': {'overrides': {'label_color': '#FF0000', 'z_index': 0}},
        'B': {'overrides': {'stroke': '#00FF00', 'fill': '#00FF00', 'fill_opacity': 1,
                            'size_px': 60, 'z_index': 25}, 'label': {'mode': 'none'}}}
    style = {'rendering': {'fill_order': fill_order}}
    for fmt in ('png', 'tex'):
        native.render(doc, fmt=fmt, style_config=style, out=tmp_path / ('z.' + fmt), report=False)
    compiled = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'z.tex'],
                               cwd=tmp_path, capture_output=True)
    assert compiled.returncode == 0, compiled.stdout[-2000:].decode(errors='replace')
    subprocess.run(['pdftoppm', '-r', '96', '-singlefile', '-png', str(tmp_path / 'z.pdf'),
                    str(tmp_path / 'z-raster')], check=True, capture_output=True)
    counts = []
    for name in ('z.png', 'z-raster.png'):
        a = np.asarray(Image.open(tmp_path / name).convert('RGB'))
        counts.append(int(((a[:, :, 0] > 150) & (a[:, :, 1] < 100) & (a[:, :, 2] < 100)).sum()))
    assert abs(counts[0] - counts[1]) <= max(10, counts[0] * 0.1), counts


@pytest.mark.parametrize('forbidden', ['\n', '\r', '\t', '\0', '\ud800', '\udfff'])
def test_schema_rejects_forbidden_final_character(forbidden):
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads(Path('animageo/native/schema/construction.v1.schema.json').read_text())
    doc = block_doc('x')
    doc['operations']['op_t']['args']['content']['value']['paragraphs'][0]['runs'][0]['text'] += forbidden
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
    with pytest.raises(native.LoadError):
        native.load(doc)


def test_tikz_does_not_build_block_mobject(tmp_path, monkeypatch):
    from animageo.animageo import AnimaGeoScene
    original = AnimaGeoScene._render_text

    def no_block(self, elem, ctx):
        assert not hasattr(elem.data, '_native_text_block')
        return original(self, elem, ctx)

    monkeypatch.setattr(AnimaGeoScene, '_render_text', no_block)
    result = native.render(block_doc(), fmt='tex', out=tmp_path / 'block.tex')
    assert result.report['elements']['t']['textBlock']['layout']['lines']
    assert '% text.block line 0:' in Path(result.path).read_text()


def test_block_visibility_is_atomic_in_native_timeline(tmp_path):
    from animageo.native.timeline import timeline_effects, timeline_to_bridge
    doc = block_doc('Первая\nВторая строка')
    timeline = {'version': 2, 'defaults': {'exit': {'effect': 'shrink', 'at': 0.4}}, 'keyframes': [
        {'t': 0, 'visible': {'t': False}},
        {'t': 1, 'visible': {'t': True}, 'enter': {'t': {'effect': 'write', 'at': 0.4}}},
        {'t': 2, 'visible': {'t': False}},
    ]}
    bridge = timeline_to_bridge(doc, timeline)
    for k, phase in ((1, 'enter'), (2, 'exit')):
        [spec] = bridge['keyframes'][k][phase].values()
        assert spec == {'effect': 'none', 'at': 0.4, 'duration': 0.0}
    for at, present in ((0.2, False), (0.5, True), (1.2, True), (1.5, False)):
        assert timeline_effects(doc, timeline, at)['t']['present'] is present
        for fmt in ('svg', 'tex'):
            rendered = native.render(doc, t=at, timeline=timeline, fmt=fmt, out=tmp_path / f'frame.{fmt}')
            record = rendered.report['elements']['t']
            assert record['visible'] is present
            if present:
                assert len(record['textBlock']['layout']['lines']) == 2


def test_scene_block_budget_refuses_before_renderer(tmp_path, monkeypatch):
    from animageo.native import rendering
    from tests.native.conftest import DocBuilder, ref
    builder = DocBuilder()
    builder.doc = block_doc('a' * 20000)
    doc = builder.op('op_other', 'text.block', {
        'anchor': ref('A'), 'content': {'kind': 'text-block', 'value': normalize_text_block('b' * 20000)},
    }, [('text', 'other', 'text')]).doc

    def should_not_import():
        pytest.fail('oversized scene reached the renderer')

    monkeypatch.setattr(rendering, '_import_scene', should_not_import)
    output = tmp_path / 'oversized.svg'
    with pytest.raises(ValueError, match=r'text.block.*scene.*limit'):
        native.render(doc, out=output)
    assert not output.exists()


def test_step_reveal_keeps_text_free_effect():
    from tests.native.conftest import DocBuilder, ref
    builder = DocBuilder()
    builder.doc = block_doc()
    doc = builder.op('op_free', 'text.free', {'anchor': ref('A'),
        'text': {'kind': 'string', 'value': 'Legacy'},
    }, [('text', 'free', 'text')]).doc
    doc['steps'] = [{'id': 'text-step', 'kind': 'group', 'operationIds': ['op_t', 'op_free']}]
    timeline = native.steps_timeline(doc).keyframes['keyframes']
    effects = {name: spec for frame in timeline for name, spec in frame.get('enter', {}).items()}
    assert effects['t']['effect'] == 'none' and effects['t']['duration'] == 0
    assert effects['free']['effect'] == 'write' and effects['free']['duration'] > 0


def test_video_reuses_line_vectors_while_anchor_moves(tmp_path, monkeypatch):
    import animageo.text_block_render as renderer
    original = renderer._line_vectors
    builds = []

    def count(layout):
        builds.append(layout['hash'])
        return original(layout)

    monkeypatch.setattr(renderer, '_line_vectors', count)
    timeline = {'version': 2, 'keyframes': [{'t': 0}, {'t': 1, 'values': {'A': [2, 1]}}]}
    video = native.render(block_doc('Ӝёлтый\nИтог'), fmt='mp4', timeline=timeline,
                          video={'fps': 8, 'quality': 'low'}, out=tmp_path / 'cached.mp4')
    assert Path(video.path).stat().st_size > 100
    assert len(builds) == 1


@pytest.mark.parametrize('fmt', ['svg', 'tex'])
@pytest.mark.parametrize('font_size', [0.001, 10001])
def test_resolved_font_size_bounds_match_layout_api(tmp_path, fmt, font_size):
    doc = block_doc()
    doc['appearance'] = {'t': {'overrides': {'font_size_px': font_size}}}
    with pytest.raises(ValueError, match=r'font_size_px.*0\.01.*10000'):
        native.render(doc, fmt=fmt, out=tmp_path / f'bad.{fmt}')


def test_precise_composite_limit_and_outline_budget():
    from animageo.native.text_block import check_render_budget
    from tests.native.conftest import DocBuilder, ref
    builder = DocBuilder()
    builder.doc = block_doc('ấ' * 20000)
    check_render_budget(native.load(builder.doc), ['op_t'])
    doc = builder.op('op_other', 'text.block', {
        'anchor': ref('A'), 'content': {'kind': 'text-block', 'value': normalize_text_block('x')},
    }, [('text', 'other', 'text')]).doc
    with pytest.raises(ValueError, match=r'scene render limit is 60000 glyphs'):
        check_render_budget(native.load(doc), ['op_t', 'op_other'])
    content = doc['operations']['op_t']['args']['content']
    content['value'] = normalize_text_block('Ӝ' * 20000)
    doc['operations']['op_other']['args']['content']['value'] = normalize_text_block('Ӝ' * 5000)
    with pytest.raises(ValueError, match=r'scene render limit is 8500000 outline points'):
        check_render_budget(native.load(doc), ['op_t', 'op_other'])


def test_preview_rejects_excessive_raster_before_scene(monkeypatch):
    from animageo.native import rendering
    monkeypatch.setattr(rendering, '_import_scene', lambda: pytest.fail('scene must not be allocated'))
    with pytest.raises(ValueError, match='scene raster limit'):
        native.render(block_doc(), fmt='png', export_layout={'export': {'ptWidth': 5000, 'ptHeight': 5000}})


def test_tikz_full_composite_block_compiles_with_default_tex_memory(tmp_path):
    import shutil
    import subprocess
    if not shutil.which('pdflatex'):
        pytest.skip('pdflatex required')
    doc = block_doc('ấ' * 20000, widthEm=120)
    doc['appearance'] = {'t': {'overrides': {'font_size_px': 2.4}}}
    native.render(doc, fmt='tex', report=False, out=tmp_path / 'full.tex')
    compiled = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'full.tex'],
                               cwd=tmp_path, capture_output=True, timeout=30)
    assert compiled.returncode == 0, compiled.stdout[-2000:].decode(errors='replace')
