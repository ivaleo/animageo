"""Native inline math: real glyphs, fraction layout, raster and TikZ exports."""
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from manim import Tex, tempconfig  # noqa: E402
from PIL import Image  # noqa: E402

from animageo import AnimaGeoScene, native  # noqa: E402
from animageo.geo.lib_elements import Text, latex_escape_text, textify_cyrillic  # noqa: E402
from animageo.ui import RusTex  # noqa: E402
from tests.native.test_native_l2a5_text import text_doc  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_tex(tmp_path, monkeypatch):
    monkeypatch.setenv('openin_any', 'p')
    monkeypatch.setenv('openout_any', 'p')
    monkeypatch.setenv('TEXMFOUTPUT', str(tmp_path))
    with tempconfig({'tex_dir': str(tmp_path / 'tex-cache'), 'media_dir': str(tmp_path / 'media')}):
        yield


def drawing(content):
    doc = text_doc(content.replace('{', '{{').replace('}', '}}')).doc
    doc['viewDefaults']['bounds'] = [-2, -2, 10, 6]
    doc['appearance'] = {e: {'visible': e == 't', 'label': {'mode': 'none'}} for e in doc['elements']}
    return doc


def classic_control(scene, content, *, latex=True):
    """Render an explicit classic Text under the native element's style/view."""
    elem = scene.geo.element(scene.native_names.by_id['t'])
    elem.data = Text([('str', content)], position=elem.data.position, is_latex=latex)
    return scene.CreateMObject(elem, z_auto=True)


def points(mobject):
    return np.concatenate([leaf.points for leaf in mobject.family_members_with_points()])


def svg_paths(path):
    return [node.attrib['d'] for node in ET.parse(path).iter() if node.tag.endswith('}path')]


def test_fraction_has_numerator_superscript_bar_and_denominator():
    scene = AnimaGeoScene()
    scene.loadDocument(drawing(r'$\frac{x^{2}}{y}$'))
    actual = scene.mobject(scene.native_names.by_id['t'])
    expected = classic_control(scene, r'$\frac{x^{2}}{y}$')
    np.testing.assert_allclose(points(actual), points(expected), atol=1e-9)
    glyphs = actual.family_members_with_points()
    assert len(glyphs) == 4  # x, superscript 2, fraction rule, y; no literal commands/dollars
    bars = [g for g in glyphs if g.width > 5 * g.height]
    assert len(bars) == 1
    bar = bars[0]
    above = [g for g in glyphs if g is not bar and g.get_bottom()[1] > bar.get_center()[1]]
    below = [g for g in glyphs if g is not bar and g.get_top()[1] < bar.get_center()[1]]
    assert len(above) == 2 and len(below) == 1
    numerator, exponent = sorted(above, key=lambda g: g.get_center()[0])
    assert exponent.width < numerator.width
    assert exponent.get_center()[0] > numerator.get_center()[0]
    assert exponent.get_top()[1] > numerator.get_top()[1]
    assert exponent.get_bottom()[1] > numerator.get_bottom()[1]
    assert bar.width >= max(numerator.width, below[0].width)


@pytest.mark.parametrize('content, display', [
    (r'$\frac{x^{2}}{y}$', r'$\frac{x^{2}}{y}$'),
    ('Дано: AB = 5', 'Дано: AB = 5'),
    (r'Площадь 50% & $\frac{x^{2}}{y_{1}}$', r'Площадь 50\% \& $\frac{x^{2}}{y_{1}}$'),
    (r'Цена $5; {x} [y] \frac (a_b)', r'Цена \$5; \{x\} [y] \textbackslash{}frac (a\_b)'),
    (r'Боковая $S_{бок}=x^2$', r'Боковая $S_{бок}=x^2$'),
    (r'<script>bad()</script> \input{no-file} $x^2$',
     r'<script>bad()</script> \textbackslash{}input\{no-file\} $x^2$'),
])
def test_native_svg_png_and_compilable_tex_match_classic_control(tmp_path, content, display):
    import cairosvg

    doc = drawing(content)
    scene = AnimaGeoScene()
    scene.loadDocument(doc)
    actual = scene.mobject(scene.native_names.by_id['t'])
    expected = classic_control(scene, display)
    np.testing.assert_allclose(points(actual), points(expected), atol=1e-9)
    scene.remove(actual)
    scene.add(expected)
    scene.exportSVG(tmp_path / 'classic.svg')
    cairosvg.svg2png(url=str(tmp_path / 'classic.svg'), write_to=str(tmp_path / 'classic.png'))

    for fmt in ('svg', 'png', 'tex'):
        result = native.render(doc, fmt=fmt, out=tmp_path / ('native.' + fmt))
        box = result.report['elements']['t']['box']
        unit = result.report['canvas']['unit']
        # Report coordinates are rounded to three decimal places.
        assert box[2] - box[0] == pytest.approx(expected.width * unit, abs=0.001)
        assert box[3] - box[1] == pytest.approx(expected.height * unit, abs=0.001)
    assert svg_paths(tmp_path / 'native.svg') == svg_paths(tmp_path / 'classic.svg')
    with Image.open(tmp_path / 'native.png') as actual_png, Image.open(tmp_path / 'classic.png') as expected_png:
        np.testing.assert_array_equal(np.asarray(actual_png), np.asarray(expected_png))

    tex = (tmp_path / 'native.tex').read_text()
    assert r'\node[' in tex
    assert textify_cyrillic(display) in tex
    proc = subprocess.run(
        ['pdflatex', '-no-shell-escape', '-interaction=batchmode', '-halt-on-error', 'native.tex'],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert (tmp_path / 'native.pdf').read_bytes().startswith(b'%PDF-')


def test_malformed_math_falls_back_to_literal_text(caplog):
    content = r'Ошибка $\animageoUnknownMathCommand{x}$'
    scene = AnimaGeoScene()
    scene.loadDocument(drawing(content))
    actual = scene.mobject(scene.native_names.by_id['t'])
    assert actual is not None
    expected = classic_control(scene, content, latex=False)
    np.testing.assert_allclose(points(actual), points(expected), atol=1e-9)
    assert 'falling back to escaped plain text' in caplog.text


def test_literal_dollar_does_not_hide_a_cyrillic_math_index():
    scene = AnimaGeoScene()
    scene.loadDocument(drawing(r'Цена \$5; $S_{бок}$'))
    actual = scene.mobject(scene.native_names.by_id['t'])
    # Explicit text mode is an independent oracle for the Cyrillic glyphs.
    expected = classic_control(scene, r'Цена \textbackslash{}\$5; $S_{\text{бок}}$')
    np.testing.assert_allclose(points(actual), points(expected), atol=1e-9)


@pytest.mark.parametrize('mode', ['native', 'classic'])
@pytest.mark.parametrize('newline', ['\n', '\r\n'], ids=['lf', 'crlf'])
@pytest.mark.parametrize('body, text_mode_body, glyph_count', [
    ('Б', r'\text{Б}', 1),
    ('S_{бок}', r'S_{\text{бок}}', 4),
], ids=['letter', 'index'])
def test_escaped_newline_preserves_cyrillic_glyphs_and_contours(
        mode, newline, body, text_mode_body, glyph_count):
    source = '$' + body + '\\' + newline + '$'
    scene = AnimaGeoScene()
    scene.loadDocument(drawing(source))
    if mode == 'native':
        actual = scene.mobject(scene.native_names.by_id['t'])
    else:
        actual = classic_control(scene, source)
        text = scene.geo.element(scene.native_names.by_id['t']).data
        assert text.is_latex and not getattr(text, '_native_inline_math', False)

    assert actual is not None
    assert len(actual.family_members_with_points()) == glyph_count
    # Compile explicit text mode directly, bypassing textify_cyrillic and the
    # library renderer so the oracle cannot silently lose the same glyphs.
    expected = Tex(
        '$' + text_mode_body + '\\' + newline + '$',
        tex_template=RusTex, font_size=actual[0].font_size,
    )
    assert len(expected.family_members_with_points()) == glyph_count
    expected.move_to(actual.get_center())
    np.testing.assert_allclose(points(actual), points(expected), atol=1e-9)


def test_dynamic_formula_exports_the_current_refs(tmp_path):
    doc = text_doc(r'Число $\frac{{{0}^{{2}}}}{{y}}$, A = {1}', 'a', 'A').doc
    doc['appearance'] = {e: {'visible': e == 't', 'label': {'mode': 'none'}} for e in doc['elements']}
    first = native.render(doc, out=tmp_path / 'first.svg')
    inputs = {'a': {'kind': 'number', 'value': 3.5}, 'A': {'kind': 'point', 'value': [-1, 0.5]}}
    second = native.render(doc, inputs=inputs, fmt='tex', out=tmp_path / 'second.tex')
    tex = (tmp_path / 'second.tex').read_text()
    assert r'$\frac{3.5^{2}}{y}$' in tex and 'A = (-1, 0.5)' in tex
    assert second.report['elements']['t']['box'] != first.report['elements']['t']['box']
    assert latex_escape_text(r'\frac') not in tex
